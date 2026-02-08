import asyncio
import json
import logging
from typing import Set
from pywebtransport import ServerApp, ServerConfig, WebTransportSession, WebTransportStream
from pywebtransport.events import Event
from pywebtransport.types import EventType
from pywebtransport.utils import generate_self_signed_cert
from babelfish_stt.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class BabelfishServer:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.server_config = config_manager.config.server
        self.sessions: Set[WebTransportSession] = set()
        self.control_streams: dict[str, WebTransportStream] = {} # Map session_id to control stream
        
        # Ensure certs exist
        if not self.server_config.cert_path or not self.server_config.key_path:
            # Generate default ones if not provided.
            # WebTransport spec requires max 14 days validity for hash pinning.
            cert_path, key_path = generate_self_signed_cert(
                hostname="127.0.0.1", 
                validity_days=10
            )
            self.server_config.cert_path = cert_path
            self.server_config.key_path = key_path
            
        self.app = ServerApp(
            config=ServerConfig(
                certfile=self.server_config.cert_path,
                keyfile=self.server_config.key_path,
            )
        )
        
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route(path="/config")
        async def config_handler(session: WebTransportSession) -> None:
            await self.handle_session(session)

    async def handle_session(self, session: WebTransportSession):
        sid = session.session_id
        logger.info(f"Client connected to /config: session_id={sid}")
        self.sessions.add(session)
        
        async def on_stream(event: Event) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                if isinstance(stream, WebTransportStream):
                    # Only respond to client-initiated streams (ID % 4 == 0)
                    if stream.stream_id % 4 == 0:
                        logger.debug(f"Control stream established by client {sid} (id={stream.stream_id})")
                        # Store this stream as the control channel for this session
                        self.control_streams[sid] = stream
                        # Send initial config
                        asyncio.create_task(self.send_config_to_stream(stream))
                        # Start reading commands
                        asyncio.create_task(self.read_commands_from_stream(stream, sid))

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)
        
        try:
            # Wait for session to close
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception as e:
            logger.error(f"Error in session {sid}: {e}")
        finally:
            self.sessions.remove(session)
            if sid in self.control_streams:
                del self.control_streams[sid]
            logger.info(f"Client disconnected: session_id={sid}")

    async def read_commands_from_stream(self, stream: WebTransportStream, sid: str):
        buffer = b""
        while not stream.is_closed:
            try:
                chunk = await stream.read(max_bytes=4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line: # ignore empty lines
                        await self.process_command(line, sid)
            except Exception as e:
                logger.error(f"Error reading from stream {stream.stream_id}: {e}")
                break

    async def process_command(self, data: bytes, sid: str):
        try:
            message = json.loads(data)
            msg_type = message.get("type")
            
            if msg_type == "update_config":
                changes = message.get("data", {})
                logger.info(f"Received config update from {sid}")
                self.config_manager.update(changes)
                await self.broadcast_config()
            else:
                logger.warning(f"Unknown message type from {sid}: {msg_type}")
                if sid in self.control_streams:
                    await self.send_error_to_stream(self.control_streams[sid], f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received from {sid}")
            if sid in self.control_streams:
                await self.send_error_to_stream(self.control_streams[sid], "Invalid JSON")
        except Exception as e:
            logger.error(f"Error processing command from {sid}: {e}")
            if sid in self.control_streams:
                await self.send_error_to_stream(self.control_streams[sid], str(e))

    async def send_error_to_stream(self, stream: WebTransportStream, message: str):
        """Sends an error message to a specific stream."""
        error_msg = {
            "type": "error",
            "message": message
        }
        try:
            data = json.dumps(error_msg).encode('utf-8') + b"\n"
            await stream.write_all(data=data, end_stream=False)
        except Exception as e:
            logger.error(f"Failed to send error to stream {stream.stream_id}: {e}")

    async def send_config_to_stream(self, stream: WebTransportStream):
        """Sends the current configuration to a specific stream."""
        config_data = self.config_manager.config.model_dump()
        message = {
            "type": "config",
            "data": config_data
        }
        try:
            # We DON'T close the stream here (end_stream=False) because we want to reuse it
            # for future updates (broadcasts). The client should read continuously.
            # We append a newline delimiter so the client can process messages.
            data = json.dumps(message).encode('utf-8') + b"\n"
            await stream.write_all(data=data, end_stream=False)
        except Exception as e:
            logger.error(f"Failed to send config to stream {stream.stream_id}: {e}")

    async def broadcast_config(self):
        """Broadcasts the current configuration to all connected clients via their control streams."""
        if not self.control_streams:
            return
            
        tasks = [self.send_config_to_stream(stream) for stream in self.control_streams.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self):
        logger.info(f"Starting WebTransport server on https://{self.server_config.host}:{self.server_config.port}/config")
        async with self.app:
            await self.app.serve(host=self.server_config.host, port=self.server_config.port)
