import asyncio
import json
import logging
from typing import Set, Dict, Optional, Any

import websockets
from pydantic import BaseModel

from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.hardware import list_microphones, list_hardware
from babelfish_stt.wakeword import list_wakewords
from babelfish_stt.config import BabelfishConfig

logger = logging.getLogger(__name__)


class BabelfishServer(Reconfigurable):
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.initial_config = config_manager.config.model_copy(deep=True)
        self.server_config = config_manager.config.server
        self.active_connections: Set[Any] = (
            set()
        )  # Use Any to avoid version mismatch in type hints
        self.pipeline = None
        self.restart_required = False
        self._loop = None
        self.last_bootstrap_message: Optional[dict] = None
        self.mic_test_enabled = False  # Persisted state for race condition fix

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        self.pipeline.on_state_change = self._on_pipeline_state_change
        # Apply persisted mic test state if it was set during bootstrap
        self.pipeline.set_test_mode(self.mic_test_enabled)

    def _on_pipeline_state_change(self, is_speaking: bool):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_status(is_speaking), self._loop
            )

    async def broadcast_status(self, is_speaking: bool) -> None:
        status_msg = {
            "type": "status",
            "vad_state": "listening" if is_speaking else "idle",
            "engine_state": "ready",
        }
        await self.broadcast_message(status_msg)

    async def broadcast_bootstrap_status(self, message: str) -> None:
        status_msg = {
            "type": "status",
            "message": message,
            "vad_state": "bootstrapping",
        }
        self.last_bootstrap_message = status_msg
        await self.broadcast_message(status_msg)

    async def broadcast_message(self, message: dict) -> None:
        if not self.active_connections:
            return

        data = json.dumps(message)

        # Create a list to avoid issues if set changes during iteration
        for websocket in list(self.active_connections):
            try:
                await websocket.send(data)
            except Exception as e:
                logger.error(f"Failed to send message to websocket: {e}")
                self.active_connections.discard(websocket)

    def reconfigure(self, config: BaseModel) -> None:
        if isinstance(config, BabelfishConfig):
            new_device = config.hardware.device
            new_auto = config.hardware.auto_detect

            old_device = self.initial_config.hardware.device
            old_auto = self.initial_config.hardware.auto_detect

            current_active = self.initial_config.hardware.active_device

            # Restart is required if:
            # 1. auto_detect toggled
            # 2. auto_detect is False and device changed
            # 3. Switching from auto_detect=True to a specific device that ISN'T the current active one
            hw_changed = False
            if new_auto != old_auto:
                # Toggling auto-detect always triggers a restart to be safe,
                # UNLESS we are switching from manual to auto and the manual device
                # was already 'auto' (which shouldn't happen but let's be safe).
                hw_changed = True
            elif not new_auto:  # Stayed in manual mode
                if new_device != old_device:
                    hw_changed = True

            # If stayed in auto mode (new_auto == True and old_auto == True),
            # we NEVER trigger a restart based on the 'device' field because it's ignored anyway.

            server_changed = (
                config.server.host != self.initial_config.server.host
                or config.server.port != self.initial_config.server.port
            )

            if hw_changed or server_changed:
                logger.info(
                    f"Critical configuration change detected. Restart required. "
                    f"(hw_changed={hw_changed}, server_changed={server_changed})"
                )
                self.restart_required = True
            else:
                # If no restart required, update initial_config to match current state
                # but preserve runtime stats if the incoming config has them as 0/None
                # (which happens if the client sends a partial draft)
                self.initial_config = config.model_copy(deep=True)
                if self.initial_config.hardware.active_device is None:
                    self.initial_config.hardware.active_device = current_active

    async def handle_connection(self, websocket):
        logger.info(
            f"New WebSocket connection established from {websocket.remote_address}"
        )
        self.active_connections.add(websocket)

        try:
            # Send initial state immediately upon connection
            await self.send_initial_state(websocket)

            async for message_str in websocket:
                try:
                    await self.process_json_command(websocket, message_str)
                except Exception as e:
                    logger.error(f"Error processing command: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed: {websocket.remote_address}")
        finally:
            self.active_connections.discard(websocket)

    async def send_initial_state(self, websocket=None):
        # 1. Send current bootstrap status if we are still bootstrapping
        if self.last_bootstrap_message:
            if websocket:
                await websocket.send(json.dumps(self.last_bootstrap_message))
            else:
                await self.broadcast_message(self.last_bootstrap_message)

        # 2. Send full config
        config_data = self.config_manager.config.model_dump()
        message = {
            "type": "config",
            "data": config_data,
            "restart_required": self.restart_required,
        }
        if websocket:
            await websocket.send(json.dumps(message))
        else:
            await self.broadcast_message(message)

    async def process_json_command(self, websocket, message_str: str):
        if not message_str.strip():
            return

        try:
            message = json.loads(message_str)
            msg_type = message.get("type")

            if msg_type == "update_config":
                changes = message.get("data", {})
                logger.info(f"Received config update: {json.dumps(changes)}")
                self.config_manager.update(changes)
                # Broadcast updated config to ALL clients
                config_data = self.config_manager.config.model_dump()
                update_msg = {
                    "type": "config",
                    "data": config_data,
                    "restart_required": self.restart_required,
                }
                await self.broadcast_message(update_msg)

            elif msg_type == "list_microphones":
                logger.info(f"Received list_microphones request")
                mics = list_microphones()
                response = {"type": "microphones_list", "data": mics}
                await websocket.send(json.dumps(response))

            elif msg_type == "list_hardware":
                logger.info(f"Received list_hardware request")
                hw = list_hardware()
                response = {"type": "hardware_list", "data": hw}
                await websocket.send(json.dumps(response))

            elif msg_type == "list_wakewords":
                logger.info(f"Received list_wakewords request")
                words = list_wakewords()
                response = {"type": "wakewords_list", "data": words}
                await websocket.send(json.dumps(response))

            elif msg_type == "set_mic_test":
                enabled = message.get("enabled", False)
                logger.info(f"Received set_mic_test request: enabled={enabled}")
                self.mic_test_enabled = enabled
                if self.pipeline:
                    self.pipeline.set_test_mode(enabled)
                response = {"type": "mic_test_status", "enabled": enabled}
                await websocket.send(json.dumps(response))

            elif msg_type == "hello":
                logger.debug(f"Received HELLO")
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message_str}")

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        logger.info(
            f"Starting WebSocket server on {self.server_config.host}:{self.server_config.port}"
        )

        self._server = await websockets.serve(
            self.handle_connection, self.server_config.host, self.server_config.port
        )
