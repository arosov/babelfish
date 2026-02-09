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
        self.active_session_ids: Set[str] = set() # Track handled sessions to avoid duplicates
        self.control_streams: dict[str, WebTransportStream] = {} # Map session_id to control stream
        
        # Ensure certs exist
        if not self.server_config.cert_path or not self.server_config.key_path:
            # Check if default files already exist to avoid regenerating on every restart
            default_cert = "127.0.0.1.crt"
            default_key = "127.0.0.1.key"
            
            import os
            if os.path.exists(default_cert) and os.path.exists(default_key):
                logger.info(f"Using existing self-signed certificate: {default_cert}")
                self.server_config.cert_path = default_cert
                self.server_config.key_path = default_key
            else:
                # Generate default ones if not provided.
                # WebTransport spec requires max 14 days validity for hash pinning.
                logger.info("Generating new self-signed certificate...")
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
                keep_alive=True,
            )
        )
        
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route(path="/config")
        async def config_handler(session: WebTransportSession) -> None:
            await self.handle_session(session)

    async def handle_session(self, session: WebTransportSession):
        sid = session.session_id
        if sid in self.active_session_ids:
            logger.debug(f"Session {sid} already being handled. Duplicate handler waiting for closure.")
            try:
                await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
            except Exception:
                pass
            return
        
        self.active_session_ids.add(sid)
        logger.info(f"Client connected to /config: session_id={sid}")
        
        # Debug logger for all events in this session
        def on_any_event(event: Event):
            logger.debug(f"[Session {sid}] Event: {event.type}")
        session.events.on_any(handler=on_any_event)

        # Wait for session to be fully established if it isn't yet
        from pywebtransport.types import SessionState
        if session.state != SessionState.CONNECTED:
            logger.debug(f"Session {sid} in state {session.state}, waiting for READY...")
            try:
                await session.events.wait_for(event_type=EventType.SESSION_READY, timeout=5.0)
                logger.debug(f"Session {sid} is now READY")
            except asyncio.TimeoutError:
                logger.warning(f"Session {sid} timed out waiting for READY event (current state: {session.state})")
            except Exception as e:
                logger.error(f"Error waiting for session {sid} ready: {e}")

        self.sessions.add(session)
        
        async def on_stream(event: Event) -> None:
            logger.debug(f"Event STREAM_OPENED received for session {sid}")
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                if isinstance(stream, WebTransportStream):
                    # Only respond to client-initiated streams (ID % 4 == 0)
                    if stream.stream_id % 4 == 0:
                        logger.debug(f"Control stream established by client {sid} (id={stream.stream_id})")
                        # Store this stream as the control channel for this session
                        self.control_streams[sid] = stream
                        
                        # Send initial config in a background task to avoid deadlocking the event loop
                        asyncio.create_task(self.send_config_to_stream(stream))
                        
                        # Start reading commands in a background task
                        task = asyncio.create_task(self.read_commands_from_stream(stream, sid))
                        task.add_done_callback(lambda t: logger.debug(f"Read commands task for {sid} finished"))

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)
        
        try:
            # Wait for session to close
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
        except Exception as e:
            logger.error(f"Error in session {sid}: {e}")
        finally:
            self.sessions.remove(session)
            self.active_session_ids.discard(sid)
            if sid in self.control_streams:
                del self.control_streams[sid]
            logger.info(f"Client disconnected: session_id={sid}")

    async def read_commands_from_stream(self, stream: WebTransportStream, sid: str):
        logger.debug(f"Starting command reader for session {sid}, stream {stream.stream_id}")
        buffer = b""
        while not stream.is_closed:
            try:
                chunk = await stream.read(max_bytes=4906)
                if not chunk:
                    logger.debug(f"Stream {stream.stream_id} reached EOF (read returned empty)")
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line: # ignore empty lines
                        logger.debug(f"Received raw line from {sid}: {line.decode('utf-8', errors='replace')}")
                        await self.process_command(line, sid)
            except Exception as e:
                logger.error(f"Error reading from stream {stream.stream_id}: {e}")
                break
        logger.debug(f"Command reader for session {sid}, stream {stream.stream_id} stopped")

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
        # Use a lock to prevent concurrent writes to the same stream
        if not hasattr(stream, "_write_lock"):
            stream._write_lock = asyncio.Lock()
        
        if stream._write_lock.locked():
             logger.debug(f"Skipping concurrent config push for stream {stream.stream_id}")
             return

        async with stream._write_lock:
            logger.debug(f"Preparing to send config to stream {stream.stream_id}")
            
            if not stream.can_write:
                logger.warning(f"Stream {stream.stream_id} is not writable (state: {stream.state})")
                return

            try:
                # DIAGNOSTICS CHECK: Log stream state before writing
                try:
                    diag = await stream.diagnostics()
                    logger.debug(f"Pre-write diagnostics: {diag}")
                except Exception as d_err:
                    logger.warning(f"Could not get pre-write diagnostics: {d_err}")

                config_data = self.config_manager.config.model_dump()
                logger.debug("Config model dumped successfully")
                message = {
                    "type": "config",
                    "data": config_data
                }
                data = json.dumps(message).encode('utf-8') + b"\n"
                logger.debug(f"Sending {len(data)} bytes to stream {stream.stream_id}")
                
                # Use a timeout to prevent hanging if the transport buffer is full or peer is not ACKing
                async with asyncio.timeout(10.0):
                    await stream.write_all(data=data, end_stream=False)
                logger.info(f"Configuration sent to stream {stream.stream_id}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout sending config to stream {stream.stream_id} (10.0s exceeded)")
                # Try to log diagnostics if possible
                try:
                    diag = await stream.diagnostics()
                    logger.error(f"Stream diagnostics: {diag}")
                except Exception as diag_err:
                    logger.error(f"Could not get diagnostics: {diag_err}")
            except Exception as e:
                logger.error(f"Failed to send config to stream {stream.stream_id}: {e}", exc_info=True)

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