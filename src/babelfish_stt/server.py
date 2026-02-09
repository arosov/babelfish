import asyncio
import json
import logging
from typing import Set, Dict, Optional, Any

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3Connection, H3_ALPN, FrameType
from aioquic.h3.events import HeadersReceived, WebTransportStreamDataReceived, H3Event
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, ConnectionTerminated, ProtocolNegotiated
from aioquic.buffer import encode_uint_var

from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.reconfigurable import Reconfigurable

logger = logging.getLogger(__name__)

class BabelfishH3Protocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._h3: Optional[H3Connection] = None
        self._session_id: Optional[int] = None
        self.babelfish_server: Optional["BabelfishServer"] = None

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            self._h3 = H3Connection(self._quic, enable_webtransport=True)
        elif isinstance(event, ConnectionTerminated):
            if self.babelfish_server:
                self.babelfish_server.on_session_closed(self)

        if self._h3 is not None:
            for h3_event in self._h3.handle_event(event):
                self._handle_h3_event(h3_event)

    def _handle_h3_event(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived):
            headers = dict(event.headers)
            method = headers.get(b":method")
            protocol = headers.get(b":protocol")
            path = headers.get(b":path")

            if method == b"CONNECT" and protocol == b"webtransport":
                logger.info(f"WebTransport session requested on {path}")
                # We respond 200 OK for any path for now, or we could check path == b"/config"
                self._h3.send_headers(
                    stream_id=event.stream_id,
                    headers=[
                        (b":status", b"200"),
                        (b"sec-webtransport-http3-draft", b"draft02"),
                    ],
                )
                self._session_id = event.stream_id
                if self.babelfish_server:
                    self.babelfish_server.on_session_established(self, event.stream_id)

        elif isinstance(event, WebTransportStreamDataReceived):
            if self.babelfish_server:
                self.babelfish_server.on_data_received(self, event.stream_id, event.data)

    def send_data(self, stream_id: int, data: bytes) -> None:
        if self._h3:
            self._quic.send_stream_data(stream_id, data)
            self.transmit()

class BabelfishServer(Reconfigurable):
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.initial_config = config_manager.config.model_copy(deep=True)
        self.server_config = config_manager.config.server
        self.sessions: Dict[BabelfishH3Protocol, int] = {}  # Map protocol to session_id
        self.active_streams: Dict[BabelfishH3Protocol, Set[int]] = {} # Map protocol to set of stream_ids
        self.buffers: Dict[tuple[BabelfishH3Protocol, int], bytes] = {} # Map (protocol, stream_id) to buffer
        self.pipeline = None
        self.restart_required = False

        self.quic_config = QuicConfiguration(
            is_client=False,
            alpn_protocols=H3_ALPN,
            max_data=10**7,
            max_stream_data=10**6,
            max_datagram_frame_size=65536,
            idle_timeout=30.0,
        )
        
        # Load certificate
        if self.server_config.cert_path and self.server_config.key_path:
            self.quic_config.load_cert_chain(
                self.server_config.cert_path, self.server_config.key_path
            )

    def reconfigure(self, config: "BabelfishConfig") -> None:
        from babelfish_stt.config import BabelfishConfig
        if isinstance(config, BabelfishConfig):
            hw_changed = (
                config.hardware.device != self.initial_config.hardware.device or
                config.hardware.microphone_index != self.initial_config.hardware.microphone_index
            )
            server_changed = (
                config.server.host != self.initial_config.server.host or
                config.server.port != self.initial_config.server.port
            )
            
            if hw_changed or server_changed:
                logger.info("Critical configuration change detected. Restart required.")
                self.restart_required = True
            else:
                self.restart_required = False

    def on_session_established(self, protocol: BabelfishH3Protocol, session_id: int) -> None:
        self.sessions[protocol] = session_id
        self.active_streams[protocol] = set()
        logger.info(f"Session established: {session_id}")

    def on_session_closed(self, protocol: BabelfishH3Protocol) -> None:
        if protocol in self.sessions:
            del self.sessions[protocol]
        if protocol in self.active_streams:
            del self.active_streams[protocol]
        
        # Clean up buffers
        keys_to_del = [k for k in self.buffers.keys() if k[0] == protocol]
        for k in keys_to_del:
            del self.buffers[k]
            
        logger.info("Session closed")

    def on_data_received(self, protocol: BabelfishH3Protocol, stream_id: int, data: bytes) -> None:
        logger.debug(f"Data received on stream {stream_id}: {data}")
        
        key = (protocol, stream_id)
        if key not in self.buffers:
            self.buffers[key] = b""
            if protocol in self.active_streams:
                self.active_streams[protocol].add(stream_id)
                logger.info(f"Discovered control stream {stream_id} for session {self.sessions[protocol]}")
                # Send initial config immediately upon stream discovery
                asyncio.create_task(self.send_config_to_stream(protocol, stream_id))

        self.buffers[key] += data
        
        if b"\n" in self.buffers[key]:
            lines = self.buffers[key].split(b"\n")
            # Keep the last partial line in buffer
            self.buffers[key] = lines.pop()
            
            for line in lines:
                # We process even empty lines if they were intended as pings, 
                # but process_command will likely ignore them.
                asyncio.create_task(self.process_command(protocol, stream_id, line))

    async def process_command(self, protocol: BabelfishH3Protocol, stream_id: int, line: bytes):
        if not line.strip():
            return

        try:
            message = json.loads(line.decode("utf-8"))
            msg_type = message.get("type")
            
            if msg_type == "update_config":
                changes = message.get("data", {})
                logger.info(f"Received config update on stream {stream_id}")
                self.config_manager.update(changes)
                await self.broadcast_config()
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {line.decode('utf-8', errors='replace')}")
        except Exception as e:
            logger.error(f"Error processing command: {e}")

    async def send_config_to_stream(self, protocol: BabelfishH3Protocol, stream_id: int):
        # If this is the first time sending on this stream, we might need 
        # to send the WebTransport stream header (0x41 + session_id)
        # depending on whether aioquic already sent it or not.
        # Actually, for bidirectional streams created by the client,
        # the server SHOULD also send the header according to some draft versions.
        
        # Let's try sending it if we haven't sent anything yet.
        if not hasattr(protocol, "_sent_streams"):
            protocol._sent_streams = set()
        
        if stream_id not in protocol._sent_streams:
            session_id = protocol._session_id
            header = encode_uint_var(FrameType.WEBTRANSPORT_STREAM) + encode_uint_var(session_id)
            protocol._quic.send_stream_data(stream_id, header)
            protocol._sent_streams.add(stream_id)

        config_data = self.config_manager.config.model_dump()
        message = {
            "type": "config",
            "data": config_data,
            "restart_required": self.restart_required
        }
        data = (json.dumps(message) + "\n").encode("utf-8")
        logger.debug(f"Sending config to stream {stream_id} ({len(data)} bytes)")
        protocol.send_data(stream_id, data)

    async def broadcast_config(self) -> None:
        for protocol, streams in self.active_streams.items():
            for stream_id in streams:
                await self.send_config_to_stream(protocol, stream_id)

    async def start(self) -> None:
        logger.info(f"Starting aioquic server on {self.server_config.host}:{self.server_config.port}")
        
        def create_protocol(*args, **kwargs):
            protocol = BabelfishH3Protocol(*args, **kwargs)
            protocol.babelfish_server = self
            return protocol

        await serve(
            host=self.server_config.host,
            port=self.server_config.port,
            configuration=self.quic_config,
            create_protocol=create_protocol,
        )
        # Keep running
        await asyncio.Future()
