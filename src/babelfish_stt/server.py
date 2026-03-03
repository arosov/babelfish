import asyncio
import json
import logging
import os
import shutil
import subprocess
import platform
from typing import Set, Dict, Optional, Any

import websockets
from pydantic import BaseModel
from notifypy import Notify

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
        self.pipeline.on_mode_change = self._on_pipeline_mode_change
        # Apply persisted mic test state if it was set during bootstrap
        self.pipeline.set_test_mode(self.mic_test_enabled)

    def _on_pipeline_state_change(self, is_speaking: bool):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_status(is_speaking=is_speaking), self._loop
            )

    def _on_pipeline_mode_change(self, is_idle: bool):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_status(is_idle=is_idle), self._loop
            )

    async def broadcast_status(
        self, is_speaking: Optional[bool] = None, is_idle: Optional[bool] = None
    ) -> None:
        if is_speaking is None and self.pipeline:
            is_speaking = self.pipeline.is_speaking
        if is_idle is None and self.pipeline:
            is_idle = self.pipeline.is_idle

        status_msg = {
            "type": "status",
            "vad_state": "listening" if is_speaking else "idle",
            "engine_state": "ready",
            "mode": "wakeword" if is_idle else "active",
        }
        await self.broadcast_message(status_msg)

    async def broadcast_event(self, event_name: str) -> None:
        event_msg = {
            "type": "event",
            "event": event_name,
        }
        await self.broadcast_message(event_msg)

    def _send_desktop_notification(
        self, title: str, message: str, timeout_sec: int = 4
    ):
        """Sends a cross-platform desktop notification with best-effort timeout support."""
        if platform.system().lower() == "linux":
            # On Linux, notify-send is the most reliable way to respect the timeout
            notify_send = shutil.which("notify-send")
            if notify_send:
                try:
                    subprocess.Popen(
                        [
                            notify_send,
                            "-t",
                            str(timeout_sec * 1000),
                            "-a",
                            "VogonPoet",
                            title,
                            message,
                        ]
                    )
                    return
                except Exception as e:
                    logger.error(f"notify-send failed: {e}")

        # Fallback for Windows/macOS or if notify-send is missing
        try:
            notification = Notify()
            notification.application_name = "VogonPoet"
            notification.title = title
            notification.message = message
            # notifypy doesn't support timeout directly, but we use it as fallback
            notification.send(block=False)
        except Exception as e:
            logger.error(f"notifypy failed: {e}")

    def trigger_event(self, event_name: str):
        logger.info(f"Triggering event: {event_name}")

        # Send desktop notification if enabled
        if self.config_manager.config.ui.notifications:
            if event_name == "wakeword_detected":
                self._send_desktop_notification(
                    "VogonPoet", "Wake word detected, listening"
                )
            elif event_name == "stop_word_detected":
                self._send_desktop_notification("VogonPoet", "Stop word detected, idle")

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_event(event_name), self._loop
            )
        else:
            logger.warning(f"Loop not running, cannot broadcast event: {event_name}")

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
            old_device = self.initial_config.hardware.device
            current_active = self.initial_config.hardware.active_device

            # Recalculate restart requirement on every config update
            self.restart_required = False
            hw_changed = False

            if new_device != old_device:
                # If we were in auto, and user selected the explicit active device, no restart needed
                is_same_as_active = (
                    old_device == "auto"
                    and new_device == current_active
                    and new_device != "cpu"
                )

                if not is_same_as_active:
                    # Check if hot-reload is possible
                    can_hot_reload = False
                    if self.pipeline and hasattr(self.pipeline, "engine"):
                        can_hot_reload = self.pipeline.engine.can_hot_reload(new_device)

                    if not can_hot_reload:
                        hw_changed = True

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

            # Always update initial_config to match current state to avoid stale comparisons
            # Preserve runtime stats if the incoming config has them as 0/None
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

        # 2. Send current status (engine state, vad state, mode)
        if self.pipeline:
            status_msg = {
                "type": "status",
                "vad_state": "listening" if self.pipeline.is_speaking else "idle",
                "engine_state": "ready",
                "mode": "wakeword" if self.pipeline.is_idle else "active",
            }
            if websocket:
                await websocket.send(json.dumps(status_msg))
            else:
                await self.broadcast_message(status_msg)

        # 3. Send full config
        config_data = self.config_manager.config.model_dump()

        # If restart is required, clear runtime VRAM stats to avoid showing stale data
        if self.restart_required:
            config_data.get("hardware", {}).pop("vram_total_gb", None)
            config_data.get("hardware", {}).pop("vram_used_baseline_gb", None)
            config_data.get("hardware", {}).pop("vram_used_model_gb", None)
            config_data.get("hardware", {}).pop("active_device", None)
            config_data.get("hardware", {}).pop("active_device_name", None)

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
                # Propagation can involve heavy model loading, offload to thread
                await asyncio.to_thread(self.config_manager.update, changes)

                # Broadcast updated config to ALL clients
                config_data = self.config_manager.config.model_dump()

                # If restart is required, clear runtime VRAM stats to avoid showing stale data
                if self.restart_required:
                    config_data.get("hardware", {}).pop("vram_total_gb", None)
                    config_data.get("hardware", {}).pop("vram_used_baseline_gb", None)
                    config_data.get("hardware", {}).pop("vram_used_model_gb", None)
                    config_data.get("hardware", {}).pop("active_device", None)
                    config_data.get("hardware", {}).pop("active_device_name", None)
                    logger.info(
                        "Cleared VRAM stats from config broadcast due to pending restart"
                    )

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
                app_data_dir = os.environ.get("VOGON_APP_DATA_DIR")
                words = list_wakewords(app_data_dir)

                # Build metadata for custom models
                metadata = {}
                for word in words:
                    if word.endswith("*"):
                        metadata[word] = {"is_custom": True}

                response = {
                    "type": "wakewords_list",
                    "data": words,
                    "metadata": metadata,
                }
                await websocket.send(json.dumps(response))

            elif msg_type == "set_mic_test":
                enabled = message.get("enabled", False)
                logger.info(f"Received set_mic_test request: enabled={enabled}")
                self.mic_test_enabled = enabled
                if self.pipeline:
                    self.pipeline.set_test_mode(enabled)
                response = {"type": "mic_test_status", "enabled": enabled}
                await websocket.send(json.dumps(response))

            elif msg_type == "force_listen":
                logger.info("Received force_listen request")
                if self.pipeline:
                    self.pipeline.request_mode(is_idle=False, force=False)

            elif msg_type == "toggle_listening":
                logger.info("Received toggle_listening request")
                if self.pipeline:
                    self.pipeline.request_mode(
                        is_idle=not self.pipeline.is_idle, force=True
                    )

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

        import sys
        import errno

        max_retries = 30
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                self._server = await websockets.serve(
                    self.handle_connection,
                    self.server_config.host,
                    self.server_config.port,
                )
                return
            except OSError as e:
                is_port_in_use = e.errno == errno.EADDRINUSE or (
                    sys.platform == "win32" and e.winerror == 10048
                )
                if is_port_in_use and attempt < max_retries - 1:
                    logger.warning(
                        f"Port {self.server_config.port} in use, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    raise
