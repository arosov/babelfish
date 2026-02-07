Directory structure:
└── wtransport-pywebtransport/
    ├── examples/
    │   └── interop/
    │       ├── Dockerfile
    │       └── main.py
    └── src/
        └── pywebtransport/
            ├── __init__.py
            ├── _wtransport.pyi
            ├── config.py
            ├── connection.py
            ├── constants.py
            ├── events.py
            ├── exceptions.py
            ├── py.typed
            ├── session.py
            ├── stream.py
            ├── types.py
            ├── utils.py
            ├── version.py
            ├── _adapter/
            │   ├── __init__.py
            │   ├── base.py
            │   ├── client.py
            │   ├── pending.py
            │   ├── server.py
            │   └── utils.py
            ├── _protocol/
            │   ├── __init__.py
            │   └── events.py
            ├── client/
            │   ├── __init__.py
            │   ├── client.py
            │   ├── fleet.py
            │   ├── reconnecting.py
            │   └── utils.py
            ├── manager/
            │   ├── __init__.py
            │   ├── _base.py
            │   ├── connection.py
            │   └── session.py
            ├── messaging/
            │   ├── __init__.py
            │   ├── datagram.py
            │   └── stream.py
            ├── serializer/
            │   ├── __init__.py
            │   ├── _base.py
            │   ├── json.py
            │   ├── msgpack.py
            │   └── protobuf.py
            └── server/
                ├── __init__.py
                ├── app.py
                ├── cluster.py
                ├── middleware.py
                ├── router.py
                └── server.py

================================================
FILE: examples/interop/Dockerfile
================================================
# PyWebTransport Interop Server Dockerfile

FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/wtransport/pywebtransport"
LABEL org.opencontainers.image.description="WebTransport interoperability test server"
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY dist/*.whl /tmp/

RUN pip install --no-cache-dir /tmp/*.whl uvloop && rm /tmp/*.whl

COPY examples/interop/main.py ./main.py

EXPOSE 4433/udp

ENTRYPOINT ["python", "main.py"]


================================================
FILE: examples/interop/main.py
================================================
"""WebTransport interoperability test server."""

import asyncio
import logging
from collections import deque
from typing import Any

import uvloop

from pywebtransport import ServerApp, ServerConfig, WebTransportSession, WebTransportStream
from pywebtransport import __version__ as LIB_VERSION
from pywebtransport.serializer import JSONSerializer
from pywebtransport.types import EventType
from pywebtransport.utils import generate_self_signed_cert

HOST = "::"
PORT = 4433

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("interop")


def deque_converter(o: Any) -> Any:
    """Convert deque to list for JSON serialization."""
    if isinstance(o, deque):
        return list(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


class InteropServer(ServerApp):
    """High-performance WebTransport interoperability server."""

    def __init__(self, config: ServerConfig) -> None:
        """Initialize server with JSON serializer and route registration."""
        super().__init__(config=config)
        self._serializer = JSONSerializer(dump_kwargs={"default": deque_converter})
        self._register_routes()
        logger.info("InteropServer initialized (v%s)", LIB_VERSION)

    def _register_routes(self) -> None:
        """Register request handlers."""
        self.route(path="/echo")(self.handle_echo)
        self.route(path="/stats")(self.handle_stats)
        self.route(path="/status")(self.handle_status)

    async def handle_echo(self, session: WebTransportSession, **kwargs: Any) -> None:
        """Handle bidirectional stream and datagram echo."""
        sid = session.session_id
        logger.info("Session %s: echo started", sid)

        async def on_datagram(event: Any) -> None:
            if isinstance(event.data, dict) and (data := event.data.get("data")):
                try:
                    await session.send_datagram(data=data)
                except Exception:
                    pass

        async def on_stream(event: Any) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                if isinstance(stream, WebTransportStream):
                    asyncio.create_task(self._echo_stream(stream))

        session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=on_datagram)
        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
            logger.info("Session %s: closed", sid)
        except Exception:
            pass

    async def handle_stats(self, session: WebTransportSession, **kwargs: Any) -> None:
        """Respond with current session diagnostics."""
        sid = session.session_id
        logger.info("Session %s: stats started", sid)

        async def on_stream(event: Any) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                if isinstance(stream, WebTransportStream):
                    try:
                        await stream.read_all()
                        payload = self._serializer.serialize(obj=await session.diagnostics())
                        await stream.write(data=payload)
                        await stream.write(data=b"", end_stream=True)
                    except Exception as e:
                        logger.error("Session %s: stats stream error: %s", sid, e)

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
            logger.info("Session %s: closed", sid)
        except Exception:
            pass

    async def handle_status(self, session: WebTransportSession, **kwargs: Any) -> None:
        """Respond with global server diagnostics."""
        sid = session.session_id
        logger.info("Session %s: status started", sid)

        async def on_stream(event: Any) -> None:
            if isinstance(event.data, dict) and (stream := event.data.get("stream")):
                if isinstance(stream, WebTransportStream):
                    try:
                        await stream.read_all()
                        payload = self._serializer.serialize(obj=await self.server.diagnostics())
                        await stream.write(data=payload)
                        await stream.write(data=b"", end_stream=True)
                    except Exception as e:
                        logger.error("Session %s: status stream error: %s", sid, e)

        session.events.on(event_type=EventType.STREAM_OPENED, handler=on_stream)

        try:
            await session.events.wait_for(event_type=EventType.SESSION_CLOSED)
            logger.info("Session %s: closed", sid)
        except Exception:
            pass

    async def _echo_stream(self, stream: WebTransportStream) -> None:
        """Echo data back to the client."""
        try:
            while True:
                data = await stream.read(max_bytes=65536)
                if not data:
                    break
                await stream.write(data=data)
            await stream.write(data=b"", end_stream=True)
        except Exception:
            pass


async def main() -> None:
    """Configure and start the server."""
    generate_self_signed_cert(hostname="localhost")

    config = ServerConfig(
        bind_host=HOST,
        bind_port=PORT,
        certfile="localhost.crt",
        keyfile="localhost.key",
    )

    app = InteropServer(config=config)
    logger.info("Server starting on https://[%s]:%s", HOST, PORT)

    async with app:
        await app.serve()


if __name__ == "__main__":
    try:
        uvloop.run(main())
    except KeyboardInterrupt:
        pass



================================================
FILE: src/pywebtransport/__init__.py
================================================
"""An async-native WebTransport stack for Python."""

from .client import WebTransportClient
from .config import ClientConfig, ServerConfig
from .constants import ErrorCodes
from .events import Event
from .exceptions import (
    ClientError,
    ConfigurationError,
    ConnectionError,
    DatagramError,
    ProtocolError,
    ServerError,
    SessionError,
    StreamError,
    TimeoutError,
    WebTransportError,
)
from .messaging import StructuredDatagramTransport, StructuredStream
from .server import ServerApp
from .session import WebTransportSession
from .stream import WebTransportReceiveStream, WebTransportSendStream, WebTransportStream
from .types import URL, Address, Headers
from .version import __version__

__all__: list[str] = [
    "Address",
    "ClientConfig",
    "ClientError",
    "ConfigurationError",
    "ConnectionError",
    "DatagramError",
    "ErrorCodes",
    "Event",
    "Headers",
    "ProtocolError",
    "ServerApp",
    "ServerConfig",
    "ServerError",
    "SessionError",
    "StreamError",
    "StructuredDatagramTransport",
    "StructuredStream",
    "TimeoutError",
    "URL",
    "WebTransportClient",
    "WebTransportError",
    "WebTransportReceiveStream",
    "WebTransportSendStream",
    "WebTransportSession",
    "WebTransportStream",
    "__version__",
]



================================================
FILE: src/pywebtransport/_wtransport.pyi
================================================
"""Type stubs for the Rust-backed WebTransport extension."""

from __future__ import annotations

from typing import final

from pywebtransport._protocol.events import Effect, ProtocolEvent
from pywebtransport.config import ClientConfig, ServerConfig
from pywebtransport.types import Buffer

ALPN_H3: str
USER_AGENT_HEADER: str
WEBTRANSPORT_DEFAULT_PORT: int
WEBTRANSPORT_SCHEME: str

BIDIRECTIONAL_STREAM: int
CLOSE_WEBTRANSPORT_SESSION_TYPE: int
DRAIN_WEBTRANSPORT_SESSION_TYPE: int
H3_FRAME_TYPE_CANCEL_PUSH: int
H3_FRAME_TYPE_DATA: int
H3_FRAME_TYPE_GOAWAY: int
H3_FRAME_TYPE_HEADERS: int
H3_FRAME_TYPE_MAX_PUSH_ID: int
H3_FRAME_TYPE_PUSH_PROMISE: int
H3_FRAME_TYPE_SETTINGS: int
H3_FRAME_TYPE_WEBTRANSPORT_STREAM: int
H3_STREAM_TYPE_CONTROL: int
H3_STREAM_TYPE_PUSH: int
H3_STREAM_TYPE_QPACK_DECODER: int
H3_STREAM_TYPE_QPACK_ENCODER: int
H3_STREAM_TYPE_WEBTRANSPORT: int
MAX_CLOSE_REASON_BYTES: int
MAX_DATAGRAM_SIZE: int
MAX_PROTOCOL_STREAMS_LIMIT: int
MAX_STREAM_ID: int
QPACK_DECODER_MAX_BLOCKED_STREAMS: int
QPACK_DECODER_MAX_TABLE_CAPACITY: int
SETTINGS_ENABLE_CONNECT_PROTOCOL: int
SETTINGS_H3_DATAGRAM: int
SETTINGS_QPACK_BLOCKED_STREAMS: int
SETTINGS_QPACK_MAX_TABLE_CAPACITY: int
SETTINGS_WT_INITIAL_MAX_DATA: int
SETTINGS_WT_INITIAL_MAX_STREAMS_BIDI: int
SETTINGS_WT_INITIAL_MAX_STREAMS_UNI: int
UNIDIRECTIONAL_STREAM: int
WT_DATA_BLOCKED_TYPE: int
WT_MAX_DATA_TYPE: int
WT_MAX_STREAM_DATA_TYPE: int
WT_MAX_STREAMS_BIDI_TYPE: int
WT_MAX_STREAMS_UNI_TYPE: int
WT_STREAM_DATA_BLOCKED_TYPE: int
WT_STREAMS_BLOCKED_BIDI_TYPE: int
WT_STREAMS_BLOCKED_UNI_TYPE: int

DEFAULT_ALPN_PROTOCOLS: list[str]
DEFAULT_BIND_HOST: str
DEFAULT_CLIENT_MAX_CONNECTIONS: int
DEFAULT_CLIENT_MAX_SESSIONS: int
DEFAULT_CLOSE_TIMEOUT: float
DEFAULT_CONGESTION_CONTROL_ALGORITHM: str
DEFAULT_CONNECT_TIMEOUT: float
DEFAULT_CONNECTION_IDLE_TIMEOUT: float
DEFAULT_DEV_PORT: int
DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE: bool
DEFAULT_FLOW_CONTROL_WINDOW_SIZE: int
DEFAULT_INITIAL_MAX_DATA: int
DEFAULT_INITIAL_MAX_STREAMS_BIDI: int
DEFAULT_INITIAL_MAX_STREAMS_UNI: int
DEFAULT_KEEP_ALIVE: bool
DEFAULT_LOG_LEVEL: str
DEFAULT_MAX_CAPSULE_SIZE: int
DEFAULT_MAX_CONNECTION_RETRIES: int
DEFAULT_MAX_DATAGRAM_SIZE: int
DEFAULT_MAX_EVENT_HISTORY_SIZE: int
DEFAULT_MAX_EVENT_LISTENERS: int
DEFAULT_MAX_EVENT_QUEUE_SIZE: int
DEFAULT_MAX_MESSAGE_SIZE: int
DEFAULT_MAX_PENDING_EVENTS_PER_SESSION: int
DEFAULT_MAX_RETRY_DELAY: float
DEFAULT_MAX_STREAM_READ_BUFFER: int
DEFAULT_MAX_STREAM_WRITE_BUFFER: int
DEFAULT_MAX_TOTAL_PENDING_EVENTS: int
DEFAULT_PENDING_EVENT_TTL: float
DEFAULT_READ_TIMEOUT: float
DEFAULT_RESOURCE_CLEANUP_INTERVAL: float
DEFAULT_RETRY_BACKOFF: float
DEFAULT_RETRY_DELAY: float
DEFAULT_SERVER_MAX_CONNECTIONS: int
DEFAULT_SERVER_MAX_SESSIONS: int
DEFAULT_STREAM_CREATION_TIMEOUT: float
DEFAULT_WRITE_TIMEOUT: float
SUPPORTED_CONGESTION_CONTROL_ALGORITHMS: list[str]

ERR_AEAD_LIMIT_REACHED: int
ERR_APP_AUTHENTICATION_FAILED: int
ERR_APP_CONNECTION_TIMEOUT: int
ERR_APP_INVALID_REQUEST: int
ERR_APP_PERMISSION_DENIED: int
ERR_APP_RESOURCE_EXHAUSTED: int
ERR_APP_SERVICE_UNAVAILABLE: int
ERR_APPLICATION_ERROR: int
ERR_CONNECTION_ID_LIMIT_ERROR: int
ERR_CONNECTION_REFUSED: int
ERR_CRYPTO_BUFFER_EXCEEDED: int
ERR_FINAL_SIZE_ERROR: int
ERR_FLOW_CONTROL_ERROR: int
ERR_FRAME_ENCODING_ERROR: int
ERR_H3_CLOSED_CRITICAL_STREAM: int
ERR_H3_CONNECT_ERROR: int
ERR_H3_DATAGRAM_ERROR: int
ERR_H3_EXCESSIVE_LOAD: int
ERR_H3_FRAME_ERROR: int
ERR_H3_FRAME_UNEXPECTED: int
ERR_H3_GENERAL_PROTOCOL_ERROR: int
ERR_H3_ID_ERROR: int
ERR_H3_INTERNAL_ERROR: int
ERR_H3_MESSAGE_ERROR: int
ERR_H3_MISSING_SETTINGS: int
ERR_H3_NO_ERROR: int
ERR_H3_REQUEST_CANCELLED: int
ERR_H3_REQUEST_INCOMPLETE: int
ERR_H3_REQUEST_REJECTED: int
ERR_H3_SETTINGS_ERROR: int
ERR_H3_STREAM_CREATION_ERROR: int
ERR_H3_VERSION_FALLBACK: int
ERR_INTERNAL_ERROR: int
ERR_INVALID_TOKEN: int
ERR_KEY_UPDATE_ERROR: int
ERR_LIB_CONNECTION_STATE_ERROR: int
ERR_LIB_INTERNAL_ERROR: int
ERR_LIB_SESSION_STATE_ERROR: int
ERR_LIB_STREAM_STATE_ERROR: int
ERR_NO_ERROR: int
ERR_NO_VIABLE_PATH: int
ERR_PROTOCOL_VIOLATION: int
ERR_QPACK_DECODER_STREAM_ERROR: int
ERR_QPACK_DECOMPRESSION_FAILED: int
ERR_QPACK_ENCODER_STREAM_ERROR: int
ERR_STREAM_LIMIT_ERROR: int
ERR_STREAM_STATE_ERROR: int
ERR_TRANSPORT_PARAMETER_ERROR: int
ERR_WT_APPLICATION_ERROR_FIRST: int
ERR_WT_APPLICATION_ERROR_LAST: int
ERR_WT_BUFFERED_STREAM_REJECTED: int
ERR_WT_FLOW_CONTROL_ERROR: int
ERR_WT_SESSION_GONE: int

def generate_self_signed_cert(*, hostname: str, output_dir: str = ".", validity_days: int = 365) -> tuple[str, str]:
    """Generate a self-signed certificate and key for testing."""
    ...

@final
class WebTransportEngine:
    """Orchestrates the unified protocol state machine."""

    def __new__(cls, connection_id: str, config: ClientConfig | ServerConfig, is_client: bool) -> WebTransportEngine:
        """Initialize the WebTransport engine."""
        ...

    def cleanup_stream(self, stream_id: int) -> None:
        """Clean up H3 state for a closed stream."""
        ...

    @staticmethod
    def encode_capsule(
        stream_id: int, capsule_type: int, capsule_data: bytes, end_stream: bool = False
    ) -> list[Effect]:
        """Encode a capsule and return effects to send it."""
        ...

    @staticmethod
    def encode_datagram(stream_id: int, data: Buffer | list[Buffer]) -> list[Effect]:
        """Encode a datagram and return effects to send it."""
        ...

    def encode_goaway(self) -> list[Effect]:
        """Encode a GOAWAY frame and return effects to send it."""
        ...

    def encode_headers(self, stream_id: int, status: int, end_stream: bool = False) -> list[Effect]:
        """Encode headers and return effects to send them."""
        ...

    def encode_session_request(
        self,
        stream_id: int,
        path: str,
        authority: str,
        headers: dict[str | bytes, str | bytes] | list[tuple[str | bytes, str | bytes]],
    ) -> list[Effect]:
        """Encode a WebTransport session establishment request."""
        ...

    def encode_stream_creation(self, stream_id: int, control_stream_id: int, is_unidirectional: bool) -> list[Effect]:
        """Encode the preamble for a new WebTransport stream."""
        ...

    def handle_event(self, event: ProtocolEvent, now: float) -> list[Effect]:
        """Process a single event and return resulting effects."""
        ...

    def initialize_h3_transport(self, control_id: int, encoder_id: int, decoder_id: int) -> list[Effect]:
        """Initialize HTTP/3 unidirectional streams and settings."""
        ...



================================================
FILE: src/pywebtransport/config.py
================================================
"""Structured configuration objects for clients and servers."""

from __future__ import annotations

import copy
import ssl
import types
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Self, Union, get_args, get_origin, get_type_hints

from pywebtransport.constants import (
    DEFAULT_ALPN_PROTOCOLS,
    DEFAULT_BIND_HOST,
    DEFAULT_CLIENT_MAX_CONNECTIONS,
    DEFAULT_CLIENT_MAX_SESSIONS,
    DEFAULT_CLOSE_TIMEOUT,
    DEFAULT_CONGESTION_CONTROL_ALGORITHM,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_CONNECTION_IDLE_TIMEOUT,
    DEFAULT_DEV_PORT,
    DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE,
    DEFAULT_FLOW_CONTROL_WINDOW_SIZE,
    DEFAULT_INITIAL_MAX_DATA,
    DEFAULT_INITIAL_MAX_STREAMS_BIDI,
    DEFAULT_INITIAL_MAX_STREAMS_UNI,
    DEFAULT_KEEP_ALIVE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_CAPSULE_SIZE,
    DEFAULT_MAX_CONNECTION_RETRIES,
    DEFAULT_MAX_DATAGRAM_SIZE,
    DEFAULT_MAX_EVENT_HISTORY_SIZE,
    DEFAULT_MAX_EVENT_LISTENERS,
    DEFAULT_MAX_EVENT_QUEUE_SIZE,
    DEFAULT_MAX_MESSAGE_SIZE,
    DEFAULT_MAX_PENDING_EVENTS_PER_SESSION,
    DEFAULT_MAX_RETRY_DELAY,
    DEFAULT_MAX_STREAM_READ_BUFFER,
    DEFAULT_MAX_STREAM_WRITE_BUFFER,
    DEFAULT_MAX_TOTAL_PENDING_EVENTS,
    DEFAULT_PENDING_EVENT_TTL,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_RESOURCE_CLEANUP_INTERVAL,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SERVER_MAX_CONNECTIONS,
    DEFAULT_SERVER_MAX_SESSIONS,
    DEFAULT_STREAM_CREATION_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT,
    SUPPORTED_CONGESTION_CONTROL_ALGORITHMS,
)
from pywebtransport.exceptions import ConfigurationError
from pywebtransport.types import Headers

__all__: list[str] = ["BaseConfig", "ClientConfig", "ServerConfig"]


@dataclass(kw_only=True)
class BaseConfig(ABC):
    """Base configuration class sharing common fields and logic."""

    alpn_protocols: list[str] = field(default_factory=lambda: list(DEFAULT_ALPN_PROTOCOLS))
    ca_certs: str | None = None
    certfile: str | None = None
    close_timeout: float = DEFAULT_CLOSE_TIMEOUT
    congestion_control_algorithm: str = DEFAULT_CONGESTION_CONTROL_ALGORITHM
    connection_idle_timeout: float = DEFAULT_CONNECTION_IDLE_TIMEOUT
    flow_control_window_auto_scale: bool = DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE
    flow_control_window_size: int = DEFAULT_FLOW_CONTROL_WINDOW_SIZE
    initial_max_data: int = DEFAULT_INITIAL_MAX_DATA
    initial_max_streams_bidi: int = DEFAULT_INITIAL_MAX_STREAMS_BIDI
    initial_max_streams_uni: int = DEFAULT_INITIAL_MAX_STREAMS_UNI
    keep_alive: bool = DEFAULT_KEEP_ALIVE
    keyfile: str | None = None
    log_level: str = DEFAULT_LOG_LEVEL
    max_capsule_size: int = DEFAULT_MAX_CAPSULE_SIZE
    max_connections: int
    max_datagram_size: int = DEFAULT_MAX_DATAGRAM_SIZE
    max_event_history_size: int = DEFAULT_MAX_EVENT_HISTORY_SIZE
    max_event_listeners: int = DEFAULT_MAX_EVENT_LISTENERS
    max_event_queue_size: int = DEFAULT_MAX_EVENT_QUEUE_SIZE
    max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE
    max_pending_events_per_session: int = DEFAULT_MAX_PENDING_EVENTS_PER_SESSION
    max_sessions: int
    max_stream_read_buffer: int = DEFAULT_MAX_STREAM_READ_BUFFER
    max_stream_write_buffer: int = DEFAULT_MAX_STREAM_WRITE_BUFFER
    max_total_pending_events: int = DEFAULT_MAX_TOTAL_PENDING_EVENTS
    pending_event_ttl: float = DEFAULT_PENDING_EVENT_TTL
    read_timeout: float | None = DEFAULT_READ_TIMEOUT
    resource_cleanup_interval: float = DEFAULT_RESOURCE_CLEANUP_INTERVAL
    stream_creation_timeout: float = DEFAULT_STREAM_CREATION_TIMEOUT
    write_timeout: float | None = DEFAULT_WRITE_TIMEOUT

    @classmethod
    def from_dict(cls, *, config_dict: dict[str, Any]) -> Self:
        """Create a configuration instance from a dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_dict = {k: v for k, v in config_dict.items() if k in valid_keys}

        type_hints = get_type_hints(cls)

        for key, value in filtered_dict.items():
            if key not in type_hints:
                continue

            target_type = type_hints[key]
            origin = get_origin(target_type)

            if origin is types.UnionType or origin is Union:
                args = [arg for arg in get_args(target_type) if arg is not type(None)]
                if len(args) == 1:
                    target_type = args[0]
                elif isinstance(value, str):
                    for arg in args:
                        if isinstance(arg, type) and issubclass(arg, Enum):
                            target_type = arg
                            break

            if isinstance(value, str) and isinstance(target_type, type) and issubclass(target_type, Enum):
                try:
                    filtered_dict[key] = target_type[value]
                except KeyError:
                    pass

        return cls(**filtered_dict)

    def copy(self) -> Self:
        """Create a deep copy of the configuration."""
        return copy.deepcopy(x=self)

    def to_dict(self) -> dict[str, Any]:
        """Convert the configuration to a dictionary."""
        result = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            match value:
                case ssl.VerifyMode():
                    result[field_name] = value.name
                case _:
                    result[field_name] = value
        return result

    def update(self, **kwargs: Any) -> Self:
        """Create a new config with updated values."""
        new_config = self.copy()
        for key, value in kwargs.items():
            if hasattr(new_config, key):
                setattr(new_config, key, value)
            else:
                raise ConfigurationError(
                    message=f"Unknown configuration key: '{key}'", config_key=key, config_value=value
                )
        new_config.validate()
        return new_config

    def validate(self) -> None:
        """Validate configuration options common to all config types."""
        if not self.alpn_protocols:
            raise ConfigurationError(
                message="Invalid value for 'alpn_protocols': cannot be empty",
                config_key="alpn_protocols",
                config_value=self.alpn_protocols,
            )

        if self.congestion_control_algorithm not in SUPPORTED_CONGESTION_CONTROL_ALGORITHMS:
            raise ConfigurationError(
                message=(
                    f"Invalid value for 'congestion_control_algorithm': "
                    f"must be one of {SUPPORTED_CONGESTION_CONTROL_ALGORITHMS}"
                ),
                config_key="congestion_control_algorithm",
                config_value=self.congestion_control_algorithm,
            )

        timeouts_to_check = [
            "close_timeout",
            "connection_idle_timeout",
            "pending_event_ttl",
            "read_timeout",
            "resource_cleanup_interval",
            "stream_creation_timeout",
            "write_timeout",
        ]

        for timeout_name in timeouts_to_check:
            try:
                _validate_timeout(timeout=getattr(self, timeout_name))
            except (ValueError, TypeError) as e:
                raise ConfigurationError(
                    message=f"Invalid value for '{timeout_name}': {e}",
                    config_key=timeout_name,
                    config_value=getattr(self, timeout_name),
                ) from e

        if self.flow_control_window_size <= 0:
            raise ConfigurationError(
                message="Invalid value for 'flow_control_window_size': must be positive",
                config_key="flow_control_window_size",
                config_value=self.flow_control_window_size,
            )

        if self.max_capsule_size <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_capsule_size': must be positive",
                config_key="max_capsule_size",
                config_value=self.max_capsule_size,
            )

        if self.max_connections <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_connections': must be positive",
                config_key="max_connections",
                config_value=self.max_connections,
            )

        if self.max_sessions <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_sessions': must be positive",
                config_key="max_sessions",
                config_value=self.max_sessions,
            )

        if self.max_datagram_size <= 0 or self.max_datagram_size > 65535:
            raise ConfigurationError(
                message="Invalid value for 'max_datagram_size': must be between 1 and 65535",
                config_key="max_datagram_size",
                config_value=self.max_datagram_size,
            )

        if self.max_event_history_size < 0:
            raise ConfigurationError(
                message="Invalid value for 'max_event_history_size': must be non-negative",
                config_key="max_event_history_size",
                config_value=self.max_event_history_size,
            )

        if self.max_event_listeners <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_event_listeners': must be positive",
                config_key="max_event_listeners",
                config_value=self.max_event_listeners,
            )

        if self.max_event_queue_size <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_event_queue_size': must be positive",
                config_key="max_event_queue_size",
                config_value=self.max_event_queue_size,
            )

        if self.max_message_size <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_message_size': must be positive",
                config_key="max_message_size",
                config_value=self.max_message_size,
            )

        if self.max_pending_events_per_session <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_pending_events_per_session': must be positive",
                config_key="max_pending_events_per_session",
                config_value=self.max_pending_events_per_session,
            )

        if self.max_total_pending_events <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_total_pending_events': must be positive",
                config_key="max_total_pending_events",
                config_value=self.max_total_pending_events,
            )

        if self.max_stream_read_buffer <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_stream_read_buffer': must be positive",
                config_key="max_stream_read_buffer",
                config_value=self.max_stream_read_buffer,
            )

        if self.max_stream_write_buffer <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_stream_write_buffer': must be positive",
                config_key="max_stream_write_buffer",
                config_value=self.max_stream_write_buffer,
            )


@dataclass(kw_only=True)
class ClientConfig(BaseConfig):
    """Configuration for the WebTransport client."""

    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    headers: Headers = field(default_factory=dict)
    max_connection_retries: int = DEFAULT_MAX_CONNECTION_RETRIES
    max_connections: int = DEFAULT_CLIENT_MAX_CONNECTIONS
    max_retry_delay: float = DEFAULT_MAX_RETRY_DELAY
    max_sessions: int = DEFAULT_CLIENT_MAX_SESSIONS
    retry_backoff: float = DEFAULT_RETRY_BACKOFF
    retry_delay: float = DEFAULT_RETRY_DELAY
    user_agent: str | None = None
    verify_mode: ssl.VerifyMode | None = ssl.CERT_REQUIRED

    def validate(self) -> None:
        """Validate client specific configuration."""
        super().validate()

        try:
            _validate_timeout(timeout=self.connect_timeout)
        except (ValueError, TypeError) as e:
            raise ConfigurationError(
                message=f"Invalid value for 'connect_timeout': {e}",
                config_key="connect_timeout",
                config_value=self.connect_timeout,
            ) from e

        if self.max_connection_retries < 0:
            raise ConfigurationError(
                message="Invalid value for 'max_connection_retries': must be non-negative",
                config_key="max_connection_retries",
                config_value=self.max_connection_retries,
            )
        if self.max_retry_delay <= 0:
            raise ConfigurationError(
                message="Invalid value for 'max_retry_delay': must be positive",
                config_key="max_retry_delay",
                config_value=self.max_retry_delay,
            )
        if self.retry_backoff < 1.0:
            raise ConfigurationError(
                message="Invalid value for 'retry_backoff': must be >= 1.0",
                config_key="retry_backoff",
                config_value=self.retry_backoff,
            )
        if self.retry_delay <= 0:
            raise ConfigurationError(
                message="Invalid value for 'retry_delay': must be positive",
                config_key="retry_delay",
                config_value=self.retry_delay,
            )

        has_certfile = self.certfile is not None
        has_keyfile = self.keyfile is not None
        if has_certfile != has_keyfile:
            raise ConfigurationError(
                message="TLS configuration error: 'certfile' and 'keyfile' must be provided together",
                config_key="certfile/keyfile",
                config_value=f"certfile={self.certfile}, keyfile={self.keyfile}",
            )

        allowed_verify_modes: list[ssl.VerifyMode | None] = [ssl.CERT_NONE, ssl.CERT_OPTIONAL, ssl.CERT_REQUIRED, None]
        if self.verify_mode not in allowed_verify_modes:
            raise ConfigurationError(
                message="Invalid value for 'verify_mode': unknown SSL verify mode",
                config_key="verify_mode",
                config_value=self.verify_mode,
            )


@dataclass(kw_only=True)
class ServerConfig(BaseConfig):
    """Configuration for the WebTransport server."""

    bind_host: str = DEFAULT_BIND_HOST
    bind_port: int = DEFAULT_DEV_PORT
    max_connections: int = DEFAULT_SERVER_MAX_CONNECTIONS
    max_sessions: int = DEFAULT_SERVER_MAX_SESSIONS
    verify_mode: ssl.VerifyMode = ssl.CERT_NONE

    @classmethod
    def from_dict(cls, *, config_dict: dict[str, Any]) -> Self:
        """Create a ServerConfig instance with type coercion."""
        if "bind_port" in config_dict and isinstance(config_dict["bind_port"], str):
            try:
                config_dict = config_dict.copy()
                config_dict["bind_port"] = int(config_dict["bind_port"])
            except ValueError:
                pass
        return super().from_dict(config_dict=config_dict)

    def validate(self) -> None:
        """Validate server specific configuration."""
        super().validate()

        if not self.bind_host:
            raise ConfigurationError(
                message="Invalid value for 'bind_host': cannot be empty",
                config_key="bind_host",
                config_value=self.bind_host,
            )

        try:
            _validate_port(port=self.bind_port)
        except ValueError as e:
            raise ConfigurationError(
                message=f"Invalid value for 'bind_port': {e}", config_key="bind_port", config_value=self.bind_port
            ) from e

        if self.certfile is None or self.keyfile is None:
            raise ConfigurationError(
                message="TLS configuration error: Server requires both certificate and key files",
                config_key="certfile/keyfile",
                config_value=f"certfile={self.certfile}, keyfile={self.keyfile}",
            )

        allowed_verify_modes: list[ssl.VerifyMode | None] = [ssl.CERT_NONE, ssl.CERT_OPTIONAL, ssl.CERT_REQUIRED]
        if self.verify_mode not in allowed_verify_modes:
            raise ConfigurationError(
                message="Invalid value for 'verify_mode': unknown SSL verify mode",
                config_key="verify_mode",
                config_value=self.verify_mode,
            )


def _validate_port(*, port: Any) -> None:
    """Validate that a value is a valid network port."""
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ValueError(f"Port must be an integer between 1 and 65535, got {port}")


def _validate_timeout(*, timeout: float | None) -> None:
    """Validate a timeout value."""
    if timeout is not None:
        if not isinstance(timeout, (int, float)):
            raise TypeError("Timeout must be a number or None")
        if timeout <= 0:
            raise ValueError("Timeout must be positive")



================================================
FILE: src/pywebtransport/connection.py
================================================
"""Core WebTransport connection object representing a QUIC connection."""

from __future__ import annotations

import asyncio
import uuid
import weakref
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from pywebtransport._adapter.client import create_quic_endpoint
from pywebtransport._protocol.events import (
    ConnectionClose,
    UserConnectionGracefulClose,
    UserCreateSession,
    UserGetConnectionDiagnostics,
)
from pywebtransport.constants import ErrorCodes
from pywebtransport.events import EventEmitter
from pywebtransport.exceptions import ConnectionError, SessionError, TimeoutError
from pywebtransport.session import WebTransportSession
from pywebtransport.stream import WebTransportReceiveStream, WebTransportSendStream, WebTransportStream
from pywebtransport.types import (
    Address,
    ConnectionId,
    ConnectionState,
    EventType,
    Headers,
    SessionId,
    StreamDirection,
    StreamId,
)
from pywebtransport.utils import get_logger

if TYPE_CHECKING:
    from pywebtransport._adapter.client import WebTransportClientProtocol
    from pywebtransport._adapter.server import WebTransportServerProtocol
    from pywebtransport.config import ClientConfig, ServerConfig

    type AdapterProtocol = WebTransportServerProtocol | WebTransportClientProtocol

__all__: list[str] = ["ConnectionDiagnostics", "WebTransportConnection"]

logger = get_logger(name=__name__)

type StreamHandle = WebTransportStream | WebTransportReceiveStream | WebTransportSendStream


@dataclass(kw_only=True)
class ConnectionDiagnostics:
    """A snapshot of connection diagnostics."""

    connection_id: ConnectionId
    is_client: bool
    state: ConnectionState
    max_datagram_size: int
    remote_max_datagram_frame_size: int | None
    handshake_complete: bool
    peer_settings_received: bool
    local_goaway_sent: bool
    session_count: int
    stream_count: int
    pending_request_count: int
    early_event_count: int
    connected_at: float | None
    closed_at: float | None
    active_session_handles: int
    active_stream_handles: int


class WebTransportConnection:
    """A high-level handle for a WebTransport connection over QUIC."""

    def __init__(
        self,
        *,
        config: ClientConfig | ServerConfig,
        protocol: AdapterProtocol,
        transport: asyncio.DatagramTransport,
        is_client: bool,
    ) -> None:
        """Initialize the WebTransport connection."""
        self._config = config
        self._protocol = protocol
        self._transport = transport
        self._is_client = is_client
        self._connection_id: ConnectionId = str(uuid.uuid4())
        self.events = EventEmitter(
            max_queue_size=config.max_event_queue_size,
            max_listeners=config.max_event_listeners,
            max_history=config.max_event_history_size,
        )
        self._cached_state = ConnectionState.IDLE

        self._protocol.set_status_callback(callback=self._notify_owner)

        self._session_handles: dict[SessionId, WebTransportSession] = {}
        self._stream_handles: dict[StreamId, StreamHandle] = {}

        logger.debug("WebTransportConnection %s initialized.", self.connection_id)

    @classmethod
    def accept(
        cls, *, transport: asyncio.DatagramTransport, protocol: AdapterProtocol, config: ServerConfig
    ) -> WebTransportConnection:
        """Static factory to wrap an accepted server connection."""
        connection = cls(config=config, protocol=protocol, transport=transport, is_client=False)
        return connection

    @classmethod
    async def connect(
        cls, *, host: str, port: int, config: ClientConfig, loop: asyncio.AbstractEventLoop | None = None
    ) -> WebTransportConnection:
        """Static factory to establish a client connection."""
        loop = loop or asyncio.get_running_loop()
        transport, protocol = await create_quic_endpoint(host=host, port=port, config=config, loop=loop)

        connection = cls(config=config, protocol=protocol, transport=transport, is_client=True)
        return connection

    @property
    def config(self) -> ClientConfig | ServerConfig:
        """Get the configuration associated with this connection."""
        return self._config

    @property
    def connection_id(self) -> ConnectionId:
        """Get the unique identifier for this connection."""
        return self._connection_id

    @property
    def is_client(self) -> bool:
        """Return True if this is a client-side connection."""
        return self._is_client

    @property
    def is_closed(self) -> bool:
        """Return True if the connection is closed."""
        return self.state == ConnectionState.CLOSED

    @property
    def is_closing(self) -> bool:
        """Return True if the connection is closing."""
        return self.state == ConnectionState.CLOSING

    @property
    def is_connected(self) -> bool:
        """Return True if the connection is established."""
        return self.state == ConnectionState.CONNECTED

    @property
    def local_address(self) -> Address | None:
        """Get the local address of the connection."""
        addr = self._transport.get_extra_info("sockname")
        if isinstance(addr, tuple) and len(addr) >= 2:
            return (addr[0], addr[1])
        return None

    @property
    def remote_address(self) -> Address | None:
        """Get the remote address of the connection."""
        addr = self._transport.get_extra_info("peername")
        if isinstance(addr, tuple) and len(addr) >= 2:
            return (addr[0], addr[1])
        return None

    @property
    def state(self) -> ConnectionState:
        """Get the current state of the connection."""
        return self._cached_state

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context manager."""
        await self.close()

    async def close(self, *, error_code: int = ErrorCodes.NO_ERROR, reason: str = "Closed by application") -> None:
        """Immediately close the WebTransport connection."""
        if self._cached_state == ConnectionState.CLOSED:
            return

        logger.info("Closing connection %s...", self.connection_id)

        try:
            request_id, future = self._protocol.create_request()
            event = ConnectionClose(request_id=request_id, error_code=error_code, reason=reason)
            self._protocol.send_event(event=event)

            try:
                async with asyncio.timeout(delay=5.0):
                    await future
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            except ConnectionError as e:
                if "Connection closed" in str(e):
                    logger.debug("Connection closed while waiting for close confirmation: %s", e)
                else:
                    logger.warning("Connection error during close: %s", e)
            except Exception as e:
                logger.warning("Error during close event processing: %s", e)

        finally:
            if self.is_client:
                if not self._transport.is_closing():
                    logger.debug("Closing underlying transport for connection %s", self.connection_id)
                    self._transport.close()

            self._session_handles.clear()
            self._stream_handles.clear()
            self._cached_state = ConnectionState.CLOSED
            logger.info("Connection %s close process finished.", self.connection_id)

    async def graceful_shutdown(self) -> None:
        """Gracefully shut down the connection."""
        logger.info("Initiating graceful shutdown for connection %s...", self.connection_id)

        request_id, future = self._protocol.create_request()
        event = UserConnectionGracefulClose(request_id=request_id)
        self._protocol.send_event(event=event)

        try:
            async with asyncio.timeout(delay=5.0):
                await future
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for graceful shutdown GOAWAY confirmation.")
        except Exception as e:
            logger.warning("Error during graceful shutdown: %s", e)

        await self.close(reason="Graceful shutdown complete")

    async def create_session(self, *, path: str, headers: Headers | None = None) -> WebTransportSession:
        """Create a new WebTransport session."""
        if not self.is_client:
            raise ConnectionError("Sessions can only be created by the client.")

        request_id, future = self._protocol.create_request()
        event = UserCreateSession(request_id=request_id, path=path, headers=headers if headers is not None else {})
        self._protocol.send_event(event=event)

        try:
            session_id: SessionId = await future
        except ConnectionError:
            raise
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError as e:
            raise TimeoutError(f"Session creation timed out: {e}") from e
        except Exception as e:
            raise SessionError(f"Session creation failed: {e}") from e

        session_handle = self._session_handles.get(session_id)
        if session_handle is None:
            logger.error("Internal error: Session handle %s missing after successful creation effect.", session_id)
            raise SessionError(f"Internal error creating session handle for {session_id}")

        return session_handle

    async def diagnostics(self) -> ConnectionDiagnostics:
        """Get diagnostic information about the connection."""
        request_id, future = self._protocol.create_request()
        event = UserGetConnectionDiagnostics(request_id=request_id)
        self._protocol.send_event(event=event)

        diag_data: dict[str, Any] = await future
        diag_data["active_session_handles"] = len(self._session_handles)
        diag_data["active_stream_handles"] = len(self._stream_handles)
        return ConnectionDiagnostics(**diag_data)

    def get_all_sessions(self) -> list[WebTransportSession]:
        """Get a list of all active session handles."""
        return list(self._session_handles.values())

    def _notify_owner(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Handle high-level status events from the adapter."""
        try:
            if "connection" not in data:
                data["connection"] = weakref.proxy(self)

            if "connection_id" in data:
                data["connection_id"] = self._connection_id

            if event_type == EventType.CONNECTION_ESTABLISHED:
                self._cached_state = ConnectionState.CONNECTED
            elif event_type == EventType.CONNECTION_CLOSED:
                self._cached_state = ConnectionState.CLOSED

            if event_type in (EventType.SESSION_REQUEST, EventType.SESSION_READY):
                self._handle_session_event(event_type=event_type, data=data)

            if event_type in (
                EventType.SESSION_READY,
                EventType.SESSION_CLOSED,
                EventType.SESSION_DRAINING,
                EventType.SESSION_MAX_DATA_UPDATED,
                EventType.SESSION_MAX_STREAMS_BIDI_UPDATED,
                EventType.SESSION_MAX_STREAMS_UNI_UPDATED,
                EventType.SESSION_DATA_BLOCKED,
                EventType.SESSION_STREAMS_BLOCKED,
                EventType.DATAGRAM_RECEIVED,
            ):
                self._route_session_event(event_type=event_type, data=data)
            elif event_type in (EventType.STREAM_OPENED, EventType.STREAM_CLOSED):
                self._handle_stream_event(event_type=event_type, data=data)

            self.events.emit_nowait(event_type=event_type, data=data)

        except Exception as e:
            logger.error("Error during owner notification callback: %s", e, exc_info=True)

    def _handle_session_event(self, *, event_type: EventType, data: dict[str, Any]) -> None:
        """Create or update session handles based on events."""
        session_id = data.get("session_id")
        if session_id is None:
            return

        create_handle = (not self.is_client and event_type == EventType.SESSION_REQUEST) or (
            self.is_client and event_type == EventType.SESSION_READY
        )

        if create_handle and session_id not in self._session_handles:
            path = data.get("path")
            headers = data.get("headers")

            if path is not None and headers is not None:
                session = WebTransportSession(connection=self, session_id=session_id, path=path, headers=headers)
                self._session_handles[session_id] = session
                logger.debug("Created session handle for %s", session_id)
                data["session"] = session
            else:
                logger.error("Missing metadata for session handle creation %s", session_id)

    def _route_session_event(self, *, event_type: EventType, data: dict[str, Any]) -> None:
        """Route events to existing session handles."""
        session_id = data.get("session_id")
        if session_id is None:
            return

        session = self._session_handles.get(session_id)
        if session is not None:
            data["session"] = session
            session.events.emit_nowait(event_type=event_type, data=data)

            if event_type == EventType.SESSION_CLOSED:
                self._session_handles.pop(session_id, None)
                asyncio.create_task(coro=session.events.close())

    def _handle_stream_event(self, *, event_type: EventType, data: dict[str, Any]) -> None:
        """Manage stream handles."""
        stream_id = data.get("stream_id")
        if stream_id is None:
            return

        if event_type == EventType.STREAM_OPENED:
            session_id = data.get("session_id")
            direction = data.get("direction")

            if session_id is not None and direction is not None and stream_id not in self._stream_handles:
                session = self._session_handles.get(session_id)
                if session is not None:
                    handle_class: type[StreamHandle]
                    match direction:
                        case StreamDirection.BIDIRECTIONAL:
                            handle_class = WebTransportStream
                        case StreamDirection.SEND_ONLY:
                            handle_class = WebTransportSendStream
                        case StreamDirection.RECEIVE_ONLY:
                            handle_class = WebTransportReceiveStream
                        case _:
                            logger.error("Unknown stream direction: %s", direction)
                            return

                    new_stream = handle_class(session=session, stream_id=stream_id)
                    self._stream_handles[stream_id] = new_stream
                    data["stream"] = new_stream

                    session.events.emit_nowait(event_type=event_type, data=data)
                else:
                    logger.warning("Session %s not found for stream %d", session_id, stream_id)

        elif event_type == EventType.STREAM_CLOSED:
            stream = self._stream_handles.pop(stream_id, None)
            if stream is not None:
                data["stream"] = stream
                stream.events.emit_nowait(event_type=event_type, data=data)
                asyncio.create_task(coro=stream.events.close())

    def __repr__(self) -> str:
        """Provide a developer-friendly representation."""
        return f"<WebTransportConnection id={self.connection_id} state={self._cached_state} client={self.is_client}>"



================================================
FILE: src/pywebtransport/constants.py
================================================
"""Protocol-level constants and default configuration values."""

from __future__ import annotations

from enum import IntEnum

from . import _wtransport

__all__: list[str] = [
    "ALPN_H3",
    "BIDIRECTIONAL_STREAM",
    "CLOSE_WEBTRANSPORT_SESSION_TYPE",
    "DEFAULT_ALPN_PROTOCOLS",
    "DEFAULT_BIND_HOST",
    "DEFAULT_CLIENT_MAX_CONNECTIONS",
    "DEFAULT_CLIENT_MAX_SESSIONS",
    "DEFAULT_CLOSE_TIMEOUT",
    "DEFAULT_CONGESTION_CONTROL_ALGORITHM",
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_CONNECTION_IDLE_TIMEOUT",
    "DEFAULT_DEV_PORT",
    "DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE",
    "DEFAULT_FLOW_CONTROL_WINDOW_SIZE",
    "DEFAULT_INITIAL_MAX_DATA",
    "DEFAULT_INITIAL_MAX_STREAMS_BIDI",
    "DEFAULT_INITIAL_MAX_STREAMS_UNI",
    "DEFAULT_KEEP_ALIVE",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_MAX_CAPSULE_SIZE",
    "DEFAULT_MAX_CONNECTION_RETRIES",
    "DEFAULT_MAX_DATAGRAM_SIZE",
    "DEFAULT_MAX_EVENT_HISTORY_SIZE",
    "DEFAULT_MAX_EVENT_LISTENERS",
    "DEFAULT_MAX_EVENT_QUEUE_SIZE",
    "DEFAULT_MAX_MESSAGE_SIZE",
    "DEFAULT_MAX_PENDING_EVENTS_PER_SESSION",
    "DEFAULT_MAX_RETRY_DELAY",
    "DEFAULT_MAX_STREAM_READ_BUFFER",
    "DEFAULT_MAX_STREAM_WRITE_BUFFER",
    "DEFAULT_MAX_TOTAL_PENDING_EVENTS",
    "DEFAULT_PENDING_EVENT_TTL",
    "DEFAULT_READ_TIMEOUT",
    "DEFAULT_RESOURCE_CLEANUP_INTERVAL",
    "DEFAULT_RETRY_BACKOFF",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_SERVER_MAX_CONNECTIONS",
    "DEFAULT_SERVER_MAX_SESSIONS",
    "DEFAULT_STREAM_CREATION_TIMEOUT",
    "DEFAULT_WRITE_TIMEOUT",
    "DRAIN_WEBTRANSPORT_SESSION_TYPE",
    "ErrorCodes",
    "H3_FRAME_TYPE_CANCEL_PUSH",
    "H3_FRAME_TYPE_DATA",
    "H3_FRAME_TYPE_GOAWAY",
    "H3_FRAME_TYPE_HEADERS",
    "H3_FRAME_TYPE_MAX_PUSH_ID",
    "H3_FRAME_TYPE_PUSH_PROMISE",
    "H3_FRAME_TYPE_SETTINGS",
    "H3_FRAME_TYPE_WEBTRANSPORT_STREAM",
    "H3_STREAM_TYPE_CONTROL",
    "H3_STREAM_TYPE_PUSH",
    "H3_STREAM_TYPE_QPACK_DECODER",
    "H3_STREAM_TYPE_QPACK_ENCODER",
    "H3_STREAM_TYPE_WEBTRANSPORT",
    "MAX_CLOSE_REASON_BYTES",
    "MAX_DATAGRAM_SIZE",
    "MAX_PROTOCOL_STREAMS_LIMIT",
    "MAX_STREAM_ID",
    "QPACK_DECODER_MAX_BLOCKED_STREAMS",
    "QPACK_DECODER_MAX_TABLE_CAPACITY",
    "SETTINGS_ENABLE_CONNECT_PROTOCOL",
    "SETTINGS_H3_DATAGRAM",
    "SETTINGS_QPACK_BLOCKED_STREAMS",
    "SETTINGS_QPACK_MAX_TABLE_CAPACITY",
    "SETTINGS_WT_INITIAL_MAX_DATA",
    "SETTINGS_WT_INITIAL_MAX_STREAMS_BIDI",
    "SETTINGS_WT_INITIAL_MAX_STREAMS_UNI",
    "SUPPORTED_CONGESTION_CONTROL_ALGORITHMS",
    "UNIDIRECTIONAL_STREAM",
    "USER_AGENT_HEADER",
    "WEBTRANSPORT_DEFAULT_PORT",
    "WEBTRANSPORT_SCHEME",
    "WT_DATA_BLOCKED_TYPE",
    "WT_MAX_DATA_TYPE",
    "WT_MAX_STREAM_DATA_TYPE",
    "WT_MAX_STREAMS_BIDI_TYPE",
    "WT_MAX_STREAMS_UNI_TYPE",
    "WT_STREAM_DATA_BLOCKED_TYPE",
    "WT_STREAMS_BLOCKED_BIDI_TYPE",
    "WT_STREAMS_BLOCKED_UNI_TYPE",
]

ALPN_H3: str = _wtransport.ALPN_H3
USER_AGENT_HEADER: str = _wtransport.USER_AGENT_HEADER
WEBTRANSPORT_DEFAULT_PORT: int = _wtransport.WEBTRANSPORT_DEFAULT_PORT
WEBTRANSPORT_SCHEME: str = _wtransport.WEBTRANSPORT_SCHEME

BIDIRECTIONAL_STREAM: int = _wtransport.BIDIRECTIONAL_STREAM
CLOSE_WEBTRANSPORT_SESSION_TYPE: int = _wtransport.CLOSE_WEBTRANSPORT_SESSION_TYPE
DRAIN_WEBTRANSPORT_SESSION_TYPE: int = _wtransport.DRAIN_WEBTRANSPORT_SESSION_TYPE
H3_FRAME_TYPE_CANCEL_PUSH: int = _wtransport.H3_FRAME_TYPE_CANCEL_PUSH
H3_FRAME_TYPE_DATA: int = _wtransport.H3_FRAME_TYPE_DATA
H3_FRAME_TYPE_GOAWAY: int = _wtransport.H3_FRAME_TYPE_GOAWAY
H3_FRAME_TYPE_HEADERS: int = _wtransport.H3_FRAME_TYPE_HEADERS
H3_FRAME_TYPE_MAX_PUSH_ID: int = _wtransport.H3_FRAME_TYPE_MAX_PUSH_ID
H3_FRAME_TYPE_PUSH_PROMISE: int = _wtransport.H3_FRAME_TYPE_PUSH_PROMISE
H3_FRAME_TYPE_SETTINGS: int = _wtransport.H3_FRAME_TYPE_SETTINGS
H3_FRAME_TYPE_WEBTRANSPORT_STREAM: int = _wtransport.H3_FRAME_TYPE_WEBTRANSPORT_STREAM
H3_STREAM_TYPE_CONTROL: int = _wtransport.H3_STREAM_TYPE_CONTROL
H3_STREAM_TYPE_PUSH: int = _wtransport.H3_STREAM_TYPE_PUSH
H3_STREAM_TYPE_QPACK_DECODER: int = _wtransport.H3_STREAM_TYPE_QPACK_DECODER
H3_STREAM_TYPE_QPACK_ENCODER: int = _wtransport.H3_STREAM_TYPE_QPACK_ENCODER
H3_STREAM_TYPE_WEBTRANSPORT: int = _wtransport.H3_STREAM_TYPE_WEBTRANSPORT
MAX_CLOSE_REASON_BYTES: int = _wtransport.MAX_CLOSE_REASON_BYTES
MAX_DATAGRAM_SIZE: int = _wtransport.MAX_DATAGRAM_SIZE
MAX_PROTOCOL_STREAMS_LIMIT: int = _wtransport.MAX_PROTOCOL_STREAMS_LIMIT
MAX_STREAM_ID: int = _wtransport.MAX_STREAM_ID
QPACK_DECODER_MAX_BLOCKED_STREAMS: int = _wtransport.QPACK_DECODER_MAX_BLOCKED_STREAMS
QPACK_DECODER_MAX_TABLE_CAPACITY: int = _wtransport.QPACK_DECODER_MAX_TABLE_CAPACITY
SETTINGS_ENABLE_CONNECT_PROTOCOL: int = _wtransport.SETTINGS_ENABLE_CONNECT_PROTOCOL
SETTINGS_H3_DATAGRAM: int = _wtransport.SETTINGS_H3_DATAGRAM
SETTINGS_QPACK_BLOCKED_STREAMS: int = _wtransport.SETTINGS_QPACK_BLOCKED_STREAMS
SETTINGS_QPACK_MAX_TABLE_CAPACITY: int = _wtransport.SETTINGS_QPACK_MAX_TABLE_CAPACITY
SETTINGS_WT_INITIAL_MAX_DATA: int = _wtransport.SETTINGS_WT_INITIAL_MAX_DATA
SETTINGS_WT_INITIAL_MAX_STREAMS_BIDI: int = _wtransport.SETTINGS_WT_INITIAL_MAX_STREAMS_BIDI
SETTINGS_WT_INITIAL_MAX_STREAMS_UNI: int = _wtransport.SETTINGS_WT_INITIAL_MAX_STREAMS_UNI
UNIDIRECTIONAL_STREAM: int = _wtransport.UNIDIRECTIONAL_STREAM
WT_DATA_BLOCKED_TYPE: int = _wtransport.WT_DATA_BLOCKED_TYPE
WT_MAX_DATA_TYPE: int = _wtransport.WT_MAX_DATA_TYPE
WT_MAX_STREAM_DATA_TYPE: int = _wtransport.WT_MAX_STREAM_DATA_TYPE
WT_MAX_STREAMS_BIDI_TYPE: int = _wtransport.WT_MAX_STREAMS_BIDI_TYPE
WT_MAX_STREAMS_UNI_TYPE: int = _wtransport.WT_MAX_STREAMS_UNI_TYPE
WT_STREAM_DATA_BLOCKED_TYPE: int = _wtransport.WT_STREAM_DATA_BLOCKED_TYPE
WT_STREAMS_BLOCKED_BIDI_TYPE: int = _wtransport.WT_STREAMS_BLOCKED_BIDI_TYPE
WT_STREAMS_BLOCKED_UNI_TYPE: int = _wtransport.WT_STREAMS_BLOCKED_UNI_TYPE

DEFAULT_ALPN_PROTOCOLS: list[str] = _wtransport.DEFAULT_ALPN_PROTOCOLS
DEFAULT_BIND_HOST: str = _wtransport.DEFAULT_BIND_HOST
DEFAULT_CLIENT_MAX_CONNECTIONS: int = _wtransport.DEFAULT_CLIENT_MAX_CONNECTIONS
DEFAULT_CLIENT_MAX_SESSIONS: int = _wtransport.DEFAULT_CLIENT_MAX_SESSIONS
DEFAULT_CLOSE_TIMEOUT: float = _wtransport.DEFAULT_CLOSE_TIMEOUT
DEFAULT_CONGESTION_CONTROL_ALGORITHM: str = _wtransport.DEFAULT_CONGESTION_CONTROL_ALGORITHM
DEFAULT_CONNECT_TIMEOUT: float = _wtransport.DEFAULT_CONNECT_TIMEOUT
DEFAULT_CONNECTION_IDLE_TIMEOUT: float = _wtransport.DEFAULT_CONNECTION_IDLE_TIMEOUT
DEFAULT_DEV_PORT: int = _wtransport.DEFAULT_DEV_PORT
DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE: bool = _wtransport.DEFAULT_FLOW_CONTROL_WINDOW_AUTO_SCALE
DEFAULT_FLOW_CONTROL_WINDOW_SIZE: int = _wtransport.DEFAULT_FLOW_CONTROL_WINDOW_SIZE
DEFAULT_INITIAL_MAX_DATA: int = _wtransport.DEFAULT_INITIAL_MAX_DATA
DEFAULT_INITIAL_MAX_STREAMS_BIDI: int = _wtransport.DEFAULT_INITIAL_MAX_STREAMS_BIDI
DEFAULT_INITIAL_MAX_STREAMS_UNI: int = _wtransport.DEFAULT_INITIAL_MAX_STREAMS_UNI
DEFAULT_KEEP_ALIVE: bool = _wtransport.DEFAULT_KEEP_ALIVE
DEFAULT_LOG_LEVEL: str = _wtransport.DEFAULT_LOG_LEVEL
DEFAULT_MAX_CAPSULE_SIZE: int = _wtransport.DEFAULT_MAX_CAPSULE_SIZE
DEFAULT_MAX_CONNECTION_RETRIES: int = _wtransport.DEFAULT_MAX_CONNECTION_RETRIES
DEFAULT_MAX_DATAGRAM_SIZE: int = _wtransport.DEFAULT_MAX_DATAGRAM_SIZE
DEFAULT_MAX_EVENT_HISTORY_SIZE: int = _wtransport.DEFAULT_MAX_EVENT_HISTORY_SIZE
DEFAULT_MAX_EVENT_LISTENERS: int = _wtransport.DEFAULT_MAX_EVENT_LISTENERS
DEFAULT_MAX_EVENT_QUEUE_SIZE: int = _wtransport.DEFAULT_MAX_EVENT_QUEUE_SIZE
DEFAULT_MAX_MESSAGE_SIZE: int = _wtransport.DEFAULT_MAX_MESSAGE_SIZE
DEFAULT_MAX_PENDING_EVENTS_PER_SESSION: int = _wtransport.DEFAULT_MAX_PENDING_EVENTS_PER_SESSION
DEFAULT_MAX_RETRY_DELAY: float = _wtransport.DEFAULT_MAX_RETRY_DELAY
DEFAULT_MAX_STREAM_READ_BUFFER: int = _wtransport.DEFAULT_MAX_STREAM_READ_BUFFER
DEFAULT_MAX_STREAM_WRITE_BUFFER: int = _wtransport.DEFAULT_MAX_STREAM_WRITE_BUFFER
DEFAULT_MAX_TOTAL_PENDING_EVENTS: int = _wtransport.DEFAULT_MAX_TOTAL_PENDING_EVENTS
DEFAULT_PENDING_EVENT_TTL: float = _wtransport.DEFAULT_PENDING_EVENT_TTL
DEFAULT_READ_TIMEOUT: float = _wtransport.DEFAULT_READ_TIMEOUT
DEFAULT_RESOURCE_CLEANUP_INTERVAL: float = _wtransport.DEFAULT_RESOURCE_CLEANUP_INTERVAL
DEFAULT_RETRY_BACKOFF: float = _wtransport.DEFAULT_RETRY_BACKOFF
DEFAULT_RETRY_DELAY: float = _wtransport.DEFAULT_RETRY_DELAY
DEFAULT_SERVER_MAX_CONNECTIONS: int = _wtransport.DEFAULT_SERVER_MAX_CONNECTIONS
DEFAULT_SERVER_MAX_SESSIONS: int = _wtransport.DEFAULT_SERVER_MAX_SESSIONS
DEFAULT_STREAM_CREATION_TIMEOUT: float = _wtransport.DEFAULT_STREAM_CREATION_TIMEOUT
DEFAULT_WRITE_TIMEOUT: float = _wtransport.DEFAULT_WRITE_TIMEOUT
SUPPORTED_CONGESTION_CONTROL_ALGORITHMS: list[str] = _wtransport.SUPPORTED_CONGESTION_CONTROL_ALGORITHMS


class ErrorCodes(IntEnum):
    """Enumeration of WebTransport and HTTP/3 error codes."""

    AEAD_LIMIT_REACHED = _wtransport.ERR_AEAD_LIMIT_REACHED
    APP_AUTHENTICATION_FAILED = _wtransport.ERR_APP_AUTHENTICATION_FAILED
    APP_CONNECTION_TIMEOUT = _wtransport.ERR_APP_CONNECTION_TIMEOUT
    APP_INVALID_REQUEST = _wtransport.ERR_APP_INVALID_REQUEST
    APP_PERMISSION_DENIED = _wtransport.ERR_APP_PERMISSION_DENIED
    APP_RESOURCE_EXHAUSTED = _wtransport.ERR_APP_RESOURCE_EXHAUSTED
    APP_SERVICE_UNAVAILABLE = _wtransport.ERR_APP_SERVICE_UNAVAILABLE
    APPLICATION_ERROR = _wtransport.ERR_APPLICATION_ERROR
    CONNECTION_ID_LIMIT_ERROR = _wtransport.ERR_CONNECTION_ID_LIMIT_ERROR
    CONNECTION_REFUSED = _wtransport.ERR_CONNECTION_REFUSED
    CRYPTO_BUFFER_EXCEEDED = _wtransport.ERR_CRYPTO_BUFFER_EXCEEDED
    FINAL_SIZE_ERROR = _wtransport.ERR_FINAL_SIZE_ERROR
    FLOW_CONTROL_ERROR = _wtransport.ERR_FLOW_CONTROL_ERROR
    FRAME_ENCODING_ERROR = _wtransport.ERR_FRAME_ENCODING_ERROR
    H3_CLOSED_CRITICAL_STREAM = _wtransport.ERR_H3_CLOSED_CRITICAL_STREAM
    H3_CONNECT_ERROR = _wtransport.ERR_H3_CONNECT_ERROR
    H3_DATAGRAM_ERROR = _wtransport.ERR_H3_DATAGRAM_ERROR
    H3_EXCESSIVE_LOAD = _wtransport.ERR_H3_EXCESSIVE_LOAD
    H3_FRAME_ERROR = _wtransport.ERR_H3_FRAME_ERROR
    H3_FRAME_UNEXPECTED = _wtransport.ERR_H3_FRAME_UNEXPECTED
    H3_GENERAL_PROTOCOL_ERROR = _wtransport.ERR_H3_GENERAL_PROTOCOL_ERROR
    H3_ID_ERROR = _wtransport.ERR_H3_ID_ERROR
    H3_INTERNAL_ERROR = _wtransport.ERR_H3_INTERNAL_ERROR
    H3_MESSAGE_ERROR = _wtransport.ERR_H3_MESSAGE_ERROR
    H3_MISSING_SETTINGS = _wtransport.ERR_H3_MISSING_SETTINGS
    H3_NO_ERROR = _wtransport.ERR_H3_NO_ERROR
    H3_REQUEST_CANCELLED = _wtransport.ERR_H3_REQUEST_CANCELLED
    H3_REQUEST_INCOMPLETE = _wtransport.ERR_H3_REQUEST_INCOMPLETE
    H3_REQUEST_REJECTED = _wtransport.ERR_H3_REQUEST_REJECTED
    H3_SETTINGS_ERROR = _wtransport.ERR_H3_SETTINGS_ERROR
    H3_STREAM_CREATION_ERROR = _wtransport.ERR_H3_STREAM_CREATION_ERROR
    H3_VERSION_FALLBACK = _wtransport.ERR_H3_VERSION_FALLBACK
    INTERNAL_ERROR = _wtransport.ERR_INTERNAL_ERROR
    INVALID_TOKEN = _wtransport.ERR_INVALID_TOKEN
    KEY_UPDATE_ERROR = _wtransport.ERR_KEY_UPDATE_ERROR
    LIB_CONNECTION_STATE_ERROR = _wtransport.ERR_LIB_CONNECTION_STATE_ERROR
    LIB_INTERNAL_ERROR = _wtransport.ERR_LIB_INTERNAL_ERROR
    LIB_SESSION_STATE_ERROR = _wtransport.ERR_LIB_SESSION_STATE_ERROR
    LIB_STREAM_STATE_ERROR = _wtransport.ERR_LIB_STREAM_STATE_ERROR
    NO_ERROR = _wtransport.ERR_NO_ERROR
    NO_VIABLE_PATH = _wtransport.ERR_NO_VIABLE_PATH
    PROTOCOL_VIOLATION = _wtransport.ERR_PROTOCOL_VIOLATION
    QPACK_DECODER_STREAM_ERROR = _wtransport.ERR_QPACK_DECODER_STREAM_ERROR
    QPACK_DECOMPRESSION_FAILED = _wtransport.ERR_QPACK_DECOMPRESSION_FAILED
    QPACK_ENCODER_STREAM_ERROR = _wtransport.ERR_QPACK_ENCODER_STREAM_ERROR
    STREAM_LIMIT_ERROR = _wtransport.ERR_STREAM_LIMIT_ERROR
    STREAM_STATE_ERROR = _wtransport.ERR_STREAM_STATE_ERROR
    TRANSPORT_PARAMETER_ERROR = _wtransport.ERR_TRANSPORT_PARAMETER_ERROR
    WT_APPLICATION_ERROR_FIRST = _wtransport.ERR_WT_APPLICATION_ERROR_FIRST
    WT_APPLICATION_ERROR_LAST = _wtransport.ERR_WT_APPLICATION_ERROR_LAST
    WT_BUFFERED_STREAM_REJECTED = _wtransport.ERR_WT_BUFFERED_STREAM_REJECTED
    WT_FLOW_CONTROL_ERROR = _wtransport.ERR_WT_FLOW_CONTROL_ERROR
    WT_SESSION_GONE = _wtransport.ERR_WT_SESSION_GONE



================================================
FILE: src/pywebtransport/events.py
================================================
"""Core components for the library's event-driven architecture."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pywebtransport.constants import (
    DEFAULT_MAX_EVENT_HISTORY_SIZE,
    DEFAULT_MAX_EVENT_LISTENERS,
    DEFAULT_MAX_EVENT_QUEUE_SIZE,
)
from pywebtransport.types import EventData, EventType, Future, Timeout
from pywebtransport.utils import get_logger, get_timestamp

__all__: list[str] = ["Event", "EventEmitter", "EventHandler"]

logger = get_logger(name=__name__)


@dataclass(kw_only=True, frozen=True, slots=True)
class Event:
    """A versatile base class for all system events."""

    type: EventType | str
    timestamp: float = field(default_factory=get_timestamp)
    data: EventData | None = None
    source: Any | None = None

    def __post_init__(self) -> None:
        """Handle string-based event types after initialization."""
        if isinstance(self.type, str):
            try:
                object.__setattr__(self, "type", EventType(self.type))
            except ValueError:
                logger.warning("Unknown event type string: '%s'", self.type)

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a dictionary."""
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data,
            "source": str(self.source) if self.source is not None else None,
        }

    def __repr__(self) -> str:
        """Return a detailed string representation of the event."""
        return f"Event(type={self.type}, timestamp={self.timestamp})"

    def __str__(self) -> str:
        """Return a simple string representation of the event."""
        return f"Event({self.type})"


type EventHandler = Callable[[Event], Awaitable[None] | None]


class EventEmitter:
    """An emitter for handling and dispatching events asynchronously."""

    def __init__(
        self,
        *,
        max_listeners: int = DEFAULT_MAX_EVENT_LISTENERS,
        max_history: int = DEFAULT_MAX_EVENT_HISTORY_SIZE,
        max_queue_size: int = DEFAULT_MAX_EVENT_QUEUE_SIZE,
    ) -> None:
        """Initialize the event emitter."""
        self._handlers: dict[EventType | str, list[EventHandler]] = defaultdict(list)
        self._once_handlers: dict[EventType | str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._event_queue: deque[Event] = deque(maxlen=max_queue_size)
        self._event_history: deque[Event] = deque(maxlen=max_history) if max_history > 0 else deque()
        self._processing_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._paused = False
        self._max_listeners = max_listeners
        self._max_history = max_history

    async def close(self) -> None:
        """Cancel running event processing tasks and clear all listeners."""
        if self._processing_task is not None and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        for task in self._background_tasks:
            if not task.done():
                task.cancel()

        self.remove_all_listeners()
        logger.debug("EventEmitter closed and listeners cleared")

    async def emit(self, *, event_type: EventType | str, data: EventData | None = None, source: Any = None) -> None:
        """Emit an event to all corresponding listeners."""
        event = Event(type=event_type, data=data, source=source)
        self._add_to_history(event=event)

        if self._paused:
            self._enqueue_event(event)
            return

        await self._process_event(event=event)

    def emit_nowait(self, *, event_type: EventType | str, data: EventData | None = None, source: Any = None) -> None:
        """Schedule an event emission synchronously without blocking."""
        event = Event(type=event_type, data=data, source=source)
        self._add_to_history(event=event)

        if self._paused:
            self._enqueue_event(event)
            return

        try:
            task = asyncio.create_task(coro=self._process_event(event=event))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            logger.warning("No running event loop, cannot schedule emit for %s", event_type)

    def off(self, *, event_type: EventType | str, handler: EventHandler | None = None) -> None:
        """Unregister a specific event handler or all handlers for an event."""
        if handler is None:
            self._handlers[event_type].clear()
            self._once_handlers[event_type].clear()
            logger.debug("Removed all handlers for event %s", event_type)
        else:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                logger.debug("Removed handler for event %s", event_type)
            if handler in self._once_handlers[event_type]:
                self._once_handlers[event_type].remove(handler)
                logger.debug("Removed once handler for event %s", event_type)

    def off_any(self, *, handler: EventHandler | None = None) -> None:
        """Unregister a specific wildcard handler or all wildcard handlers."""
        if handler is None:
            self._wildcard_handlers.clear()
            logger.debug("Removed all wildcard handlers")
        elif handler in self._wildcard_handlers:
            self._wildcard_handlers.remove(handler)
            logger.debug("Removed wildcard handler")

    def on(self, *, event_type: EventType | str, handler: EventHandler) -> None:
        """Register a persistent event handler."""
        handlers = self._handlers[event_type]
        if len(handlers) >= self._max_listeners:
            logger.warning("Maximum listeners (%d) exceeded for event %s", self._max_listeners, event_type)

        if handler not in handlers:
            handlers.append(handler)
            logger.debug("Registered handler for event %s", event_type)
        else:
            logger.warning("Handler already registered for event %s", event_type)

    def on_any(self, *, handler: EventHandler) -> None:
        """Register a wildcard handler for all events."""
        if handler not in self._wildcard_handlers:
            self._wildcard_handlers.append(handler)
            logger.debug("Registered wildcard handler")

    def once(self, *, event_type: EventType | str, handler: EventHandler) -> None:
        """Register a one-time event handler."""
        once_handlers = self._once_handlers[event_type]

        if handler not in once_handlers:
            once_handlers.append(handler)
            logger.debug("Registered once handler for event %s", event_type)

    def remove_all_listeners(self, *, event_type: EventType | str | None = None) -> None:
        """Remove all listeners for a specific event or for all events."""
        if event_type is None:
            self._handlers.clear()
            self._once_handlers.clear()
            self._wildcard_handlers.clear()
            logger.debug("Removed all event listeners")
        else:
            self._handlers[event_type].clear()
            self._once_handlers[event_type].clear()
            logger.debug("Removed all listeners for event %s", event_type)

    async def wait_for(
        self,
        *,
        event_type: EventType | str | list[EventType | str],
        timeout: Timeout | None = None,
        condition: Callable[[Event], bool] | None = None,
    ) -> Event:
        """Wait for a specific event or any of a list of events to be emitted."""
        future: Future[Event] = asyncio.Future()
        event_types = [event_type] if isinstance(event_type, (str, EventType)) else event_type

        async def handler(event: Event) -> None:
            try:
                if condition is None or condition(event):
                    if not future.done():
                        future.set_result(event)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

        for et in event_types:
            self.on(event_type=et, handler=handler)

        try:
            try:
                async with asyncio.timeout(delay=timeout):
                    return await future
            except asyncio.TimeoutError:
                future.cancel()
                raise
        finally:
            for et in event_types:
                self.off(event_type=et, handler=handler)

    def clear_history(self) -> None:
        """Clear the entire event history."""
        self._event_history.clear()
        logger.debug("Event history cleared")

    def get_event_history(self, *, event_type: EventType | str | None = None, limit: int = 100) -> list[Event]:
        """Get the recorded history of events."""
        if event_type is None:
            return list(self._event_history)[-limit:]

        filtered_events = [event for event in self._event_history if event.type == event_type]
        return filtered_events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the event emitter."""
        total_handlers = sum(len(handlers) for handlers in self._handlers.values())
        total_once_handlers = sum(len(handlers) for handlers in self._once_handlers.values())
        return {
            "total_handlers": total_handlers,
            "total_once_handlers": total_once_handlers,
            "wildcard_handlers": len(self._wildcard_handlers),
            "event_types": len(self._handlers),
            "history_size": len(self._event_history),
            "queued_events": len(self._event_queue),
            "paused": self._paused,
        }

    def listener_count(self, *, event_type: EventType | str) -> int:
        """Get the number of listeners for a specific event type."""
        return len(self.listeners(event_type=event_type))

    def listeners(self, *, event_type: EventType | str) -> list[EventHandler]:
        """Get all listeners for a specific event type."""
        return self._handlers[event_type][:] + self._once_handlers[event_type][:]

    def pause(self) -> None:
        """Pause event processing and queue subsequent events."""
        self._paused = True
        logger.debug("Event processing paused")

    def resume(self) -> asyncio.Task[None] | None:
        """Resume event processing and handle all queued events."""
        self._paused = False
        logger.debug("Event processing resumed")

        if self._event_queue and (self._processing_task is None or self._processing_task.done()):
            self._processing_task = asyncio.create_task(coro=self._process_queued_events())
            return self._processing_task
        return None

    def set_max_listeners(self, *, max_listeners: int) -> None:
        """Set the maximum number of listeners per event."""
        self._max_listeners = max_listeners

    def _add_to_history(self, *, event: Event) -> None:
        """Add an event to the history buffer."""
        if self._max_history > 0:
            self._event_history.append(event)

    def _enqueue_event(self, event: Event) -> None:
        """Enqueue an event safely, dropping oldest if full."""
        if self._event_queue.maxlen is not None and len(self._event_queue) >= self._event_queue.maxlen:
            logger.warning("Event queue full, dropping oldest event to make room")
        self._event_queue.append(event)

    async def _process_event(self, *, event: Event) -> None:
        """Process a single event by invoking all relevant handlers."""
        handlers_to_call: list[EventHandler] = self._handlers[event.type][:]
        once_handlers_to_call: list[EventHandler] = self._once_handlers[event.type][:]
        all_handlers = handlers_to_call + once_handlers_to_call + self._wildcard_handlers

        if once_handlers_to_call:
            self._once_handlers[event.type].clear()

        if not all_handlers:
            return

        logger.debug("Emitting event %s to %d handlers", event.type, len(all_handlers))
        for handler in all_handlers:
            try:
                result = handler(event)
                if isinstance(result, Awaitable):
                    await result
            except Exception as e:
                logger.error("Error in handler for event %s: %s", event.type, e, exc_info=True)

    async def _process_queued_events(self) -> None:
        """Process all events in the queue until it is empty."""
        while self._event_queue and not self._paused:
            event = self._event_queue.popleft()
            await self._process_event(event=event)



================================================
FILE: src/pywebtransport/exceptions.py
================================================
"""Custom exception hierarchy for the library."""

from __future__ import annotations

from typing import Any

from pywebtransport.constants import ErrorCodes
from pywebtransport.types import SessionId, SessionState, StreamState

__all__: list[str] = [
    "AuthenticationError",
    "CertificateError",
    "ClientError",
    "ConfigurationError",
    "ConnectionError",
    "DatagramError",
    "FlowControlError",
    "HandshakeError",
    "ProtocolError",
    "SerializationError",
    "ServerError",
    "SessionError",
    "StreamError",
    "TimeoutError",
    "WebTransportError",
]

_FATAL_ERROR_CODES = frozenset(
    {
        ErrorCodes.INTERNAL_ERROR,
        ErrorCodes.H3_INTERNAL_ERROR,
        ErrorCodes.PROTOCOL_VIOLATION,
        ErrorCodes.FRAME_ENCODING_ERROR,
        ErrorCodes.CRYPTO_BUFFER_EXCEEDED,
        ErrorCodes.APP_AUTHENTICATION_FAILED,
        ErrorCodes.APP_PERMISSION_DENIED,
    }
)

_RETRIABLE_ERROR_CODES = frozenset(
    {ErrorCodes.APP_CONNECTION_TIMEOUT, ErrorCodes.APP_SERVICE_UNAVAILABLE, ErrorCodes.FLOW_CONTROL_ERROR}
)


class WebTransportError(Exception):
    """The base exception for all WebTransport errors."""

    def __init__(self, message: str, *, error_code: int | None = None, details: dict[str, Any] | None = None) -> None:
        """Initialize the WebTransport error."""
        super().__init__(message)
        self.message = message
        self.error_code = error_code if error_code is not None else ErrorCodes.INTERNAL_ERROR
        self.details = details if details is not None else {}

    @property
    def category(self) -> str:
        """Return the error category based on the class name."""
        name = self.__class__.__name__
        if name.endswith("Error"):
            name = name[:-5]
        return _to_snake_case(name=name)

    @property
    def is_fatal(self) -> bool:
        """Check if the error is fatal and should terminate the connection."""
        return self.error_code in _FATAL_ERROR_CODES

    @property
    def is_retriable(self) -> bool:
        """Check if the error is transient and the operation can be retried."""
        return self.error_code in _RETRIABLE_ERROR_CODES

    def to_dict(self) -> dict[str, Any]:
        """Convert the exception to a dictionary for serialization."""
        data = {
            "type": self.__class__.__name__,
            "category": self.category,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "is_fatal": self.is_fatal,
            "is_retriable": self.is_retriable,
        }

        excluded_keys = {"message", "error_code", "details", "args"}
        for key, value in self.__dict__.items():
            if key not in excluded_keys and not key.startswith("_"):
                data[key] = value if not isinstance(value, Exception) else str(value)
        return data

    def __repr__(self) -> str:
        """Return a detailed string representation of the error."""
        args = [f"message={self.message!r}", f"error_code={hex(self.error_code)}"]
        excluded_keys = {"message", "error_code", "details", "args"}

        for key, value in self.__dict__.items():
            if key not in excluded_keys and not key.startswith("_"):
                args.append(f"{key}={value!r}")

        if self.details:
            args.append(f"details={self.details!r}")

        return f"{self.__class__.__name__}({', '.join(args)})"

    def __str__(self) -> str:
        """Return a simple string representation of the error."""
        return f"[{hex(self.error_code)}] {self.message}"


class AuthenticationError(WebTransportError):
    """An exception for authentication-related errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        auth_method: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the authentication error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.APP_AUTHENTICATION_FAILED,
            details=details,
        )
        self.auth_method = auth_method


class CertificateError(WebTransportError):
    """An exception for certificate-related errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        certificate_path: str | None = None,
        certificate_error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the certificate error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.APP_AUTHENTICATION_FAILED,
            details=details,
        )
        self.certificate_path = certificate_path
        self.certificate_error = certificate_error


class ClientError(WebTransportError):
    """An exception for client-specific errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        target_url: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the client error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.APP_INVALID_REQUEST,
            details=details,
        )
        self.target_url = target_url


class ConfigurationError(WebTransportError):
    """An exception for configuration-related errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        config_key: str | None = None,
        config_value: Any | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the configuration error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.APP_INVALID_REQUEST,
            details=details,
        )
        self.config_key = config_key
        self.config_value = config_value


class ConnectionError(WebTransportError):
    """An exception for connection-related errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        remote_address: tuple[str, int] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the connection error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.CONNECTION_REFUSED,
            details=details,
        )
        self.remote_address = remote_address


class DatagramError(WebTransportError):
    """An exception for datagram-related errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        datagram_size: int | None = None,
        max_size: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the datagram error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.INTERNAL_ERROR,
            details=details,
        )
        self.datagram_size = datagram_size
        self.max_size = max_size


class FlowControlError(WebTransportError):
    """An exception for flow control errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        stream_id: int | None = None,
        limit_exceeded: int | None = None,
        current_value: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the flow control error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.FLOW_CONTROL_ERROR,
            details=details,
        )
        self.stream_id = stream_id
        self.limit_exceeded = limit_exceeded
        self.current_value = current_value


class HandshakeError(WebTransportError):
    """An exception for handshake-related errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        handshake_stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the handshake error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.INTERNAL_ERROR,
            details=details,
        )
        self.handshake_stage = handshake_stage


class ProtocolError(WebTransportError):
    """An exception for protocol violation errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        frame_type: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the protocol error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.PROTOCOL_VIOLATION,
            details=details,
        )
        self.frame_type = frame_type


class SerializationError(WebTransportError):
    """An exception for serialization or deserialization errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        original_exception: Exception | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the serialization error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.INTERNAL_ERROR,
            details=details,
        )
        self.original_exception = original_exception


class ServerError(WebTransportError):
    """An exception for server-specific errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        bind_address: tuple[str, int] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the server error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.APP_SERVICE_UNAVAILABLE,
            details=details,
        )
        self.bind_address = bind_address


class SessionError(WebTransportError):
    """An exception for WebTransport session errors."""

    def __init__(
        self,
        message: str,
        *,
        session_id: SessionId | None = None,
        error_code: int | None = None,
        session_state: SessionState | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the session error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.INTERNAL_ERROR,
            details=details,
        )
        self.session_id = session_id
        self.session_state = session_state


class StreamError(WebTransportError):
    """An exception for stream-related errors."""

    def __init__(
        self,
        message: str,
        *,
        stream_id: int | None = None,
        error_code: int | None = None,
        stream_state: StreamState | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the stream error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.STREAM_STATE_ERROR,
            details=details,
        )
        self.stream_id = stream_id
        self.stream_state = stream_state

    def __str__(self) -> str:
        """Return a simple string representation of the error."""
        base_msg = super().__str__()
        if self.stream_id is not None:
            return f"{base_msg} (stream_id={self.stream_id})"
        return base_msg


class TimeoutError(WebTransportError):
    """An exception for timeout-related errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: int | None = None,
        timeout_duration: float | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the timeout error."""
        super().__init__(
            message=message,
            error_code=error_code if error_code is not None else ErrorCodes.APP_CONNECTION_TIMEOUT,
            details=details,
        )
        self.timeout_duration = timeout_duration
        self.operation = operation


def _to_snake_case(*, name: str) -> str:
    """Convert a CamelCase string to snake_case."""
    return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")



================================================
FILE: src/pywebtransport/py.typed
================================================
[Empty file]


================================================
FILE: src/pywebtransport/session.py
================================================
"""High-level abstraction for a WebTransport session."""

from __future__ import annotations

import asyncio
import weakref
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from pywebtransport._protocol.events import (
    UserCloseSession,
    UserCreateStream,
    UserGetSessionDiagnostics,
    UserGrantDataCredit,
    UserGrantStreamsCredit,
    UserSendDatagram,
)
from pywebtransport.constants import ErrorCodes
from pywebtransport.events import Event, EventEmitter
from pywebtransport.exceptions import ConnectionError, SessionError, StreamError, TimeoutError
from pywebtransport.stream import WebTransportSendStream, WebTransportStream
from pywebtransport.types import Address, Buffer, EventType, Headers, SessionId, SessionState, StreamId
from pywebtransport.utils import get_logger

if TYPE_CHECKING:
    from pywebtransport.connection import WebTransportConnection
    from pywebtransport.stream import StreamType


__all__: list[str] = ["SessionDiagnostics", "WebTransportSession"]

logger = get_logger(name=__name__)


@dataclass(kw_only=True)
class SessionDiagnostics:
    """A snapshot of session diagnostics."""

    session_id: SessionId
    state: SessionState
    path: str
    headers: Headers
    created_at: float
    local_max_data: int
    local_data_sent: int
    local_data_consumed: int
    peer_max_data: int
    peer_data_sent: int
    local_max_streams_bidi: int
    local_streams_bidi_opened: int
    peer_max_streams_bidi: int
    peer_streams_bidi_opened: int
    peer_streams_bidi_closed: int
    local_max_streams_uni: int
    local_streams_uni_opened: int
    peer_max_streams_uni: int
    peer_streams_uni_opened: int
    peer_streams_uni_closed: int
    pending_bidi_stream_requests: list[int]
    pending_uni_stream_requests: list[int]
    datagrams_sent: int
    datagram_bytes_sent: int
    datagrams_received: int
    datagram_bytes_received: int
    active_streams: list[StreamId]
    blocked_streams: list[StreamId]
    close_code: int | None
    close_reason: str | None
    closed_at: float | None
    ready_at: float | None


class WebTransportSession:
    """A high-level handle for a WebTransport session."""

    def __init__(
        self, *, connection: WebTransportConnection, session_id: SessionId, path: str, headers: Headers
    ) -> None:
        """Initialize the WebTransportSession handle."""
        self._connection = weakref.ref(connection)
        self._session_id = session_id
        self._path = path
        self._headers = headers
        self._cached_state = SessionState.CONNECTING

        config = connection.config
        self.events = EventEmitter(
            max_queue_size=config.max_event_queue_size,
            max_listeners=config.max_event_listeners,
            max_history=config.max_event_history_size,
        )

        self.events.on(event_type=EventType.SESSION_READY, handler=self._on_session_ready)
        self.events.on(event_type=EventType.SESSION_CLOSED, handler=self._on_session_closed)

        logger.debug("WebTransportSession handle created for session %s", self._session_id)

    @property
    def headers(self) -> Headers:
        """Get the initial request headers for this session."""
        return self._headers.copy()

    @property
    def is_closed(self) -> bool:
        """Return True if the session is closed."""
        return self._cached_state == SessionState.CLOSED

    @property
    def path(self) -> str:
        """Get the request path associated with this session."""
        return self._path

    @property
    def remote_address(self) -> Address | None:
        """Get the remote address of the peer."""
        connection = self._connection()
        if connection is not None:
            return connection.remote_address
        return None

    @property
    def session_id(self) -> SessionId:
        """Get the unique identifier for this session."""
        return self._session_id

    @property
    def state(self) -> SessionState:
        """Get the current state of the session."""
        return self._cached_state

    async def __aenter__(self) -> Self:
        """Enter async context."""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit async context, closing the session."""
        await self.close()

    async def close(self, *, error_code: int = ErrorCodes.NO_ERROR, reason: str | None = None) -> None:
        """Close the WebTransport session."""
        if self._cached_state == SessionState.CLOSED:
            return

        logger.info("Closing session %s: code=%#x reason='%s'", self.session_id, error_code, reason or "")
        connection = self._connection()
        if connection is None:
            return

        request_id, future = connection._protocol.create_request()
        event = UserCloseSession(
            request_id=request_id, session_id=self.session_id, error_code=error_code, reason=reason
        )
        connection._protocol.send_event(event=event)

        try:
            await future
        except (ConnectionError, SessionError) as e:
            logger.warning("Error initiating session close for %s: %s", self.session_id, e, exc_info=True)

    async def create_bidirectional_stream(self) -> WebTransportStream:
        """Create a new bidirectional WebTransport stream."""
        stream = await self._create_stream_internal(is_unidirectional=False)
        if not isinstance(stream, WebTransportStream):
            raise StreamError(f"Internal error: Expected bidirectional stream, got {type(stream).__name__}")
        return stream

    async def create_unidirectional_stream(self) -> WebTransportSendStream:
        """Create a new unidirectional (send-only) WebTransport stream."""
        stream = await self._create_stream_internal(is_unidirectional=True)
        if not isinstance(stream, WebTransportSendStream) or isinstance(stream, WebTransportStream):
            raise StreamError(f"Internal error: Expected unidirectional send stream, got {type(stream).__name__}")
        return stream

    async def diagnostics(self) -> SessionDiagnostics:
        """Get diagnostic information about the session."""
        connection = self._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserGetSessionDiagnostics(request_id=request_id, session_id=self.session_id)

        try:
            connection._protocol.send_event(event=event)
            diag_data: dict[str, Any] = await future
            return SessionDiagnostics(**diag_data)
        except ConnectionError as e:
            raise SessionError(f"Connection is closed, cannot get diagnostics: {e}") from e

    async def grant_data_credit(self, *, max_data: int) -> None:
        """Manually grant data flow control credit to the peer."""
        connection = self._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserGrantDataCredit(request_id=request_id, session_id=self.session_id, max_data=max_data)
        connection._protocol.send_event(event=event)
        await future

    async def grant_streams_credit(self, *, max_streams: int, is_unidirectional: bool) -> None:
        """Manually grant stream flow control credit to the peer."""
        connection = self._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserGrantStreamsCredit(
            request_id=request_id,
            session_id=self.session_id,
            max_streams=max_streams,
            is_unidirectional=is_unidirectional,
        )
        connection._protocol.send_event(event=event)
        await future

    async def send_datagram(self, *, data: Buffer | list[Buffer]) -> None:
        """Send an unreliable datagram."""
        connection = self._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserSendDatagram(request_id=request_id, session_id=self.session_id, data=data)
        connection._protocol.send_event(event=event)
        await future

    def _add_stream_handle(self, *, stream: StreamType, event_data: dict[str, Any]) -> None:
        """Register an incoming stream and re-emit the STREAM_OPENED event."""
        logger.debug("Session %s re-emitting STREAM_OPENED for stream %s", self.session_id, stream.stream_id)

        event_payload = event_data.copy()
        event_payload["stream"] = stream

        self.events.emit_nowait(event_type=EventType.STREAM_OPENED, data=event_payload)

    async def _create_stream_internal(self, *, is_unidirectional: bool) -> WebTransportStream | WebTransportSendStream:
        """Internal logic for creating a stream with timeout handling."""
        connection = self._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserCreateStream(request_id=request_id, session_id=self.session_id, is_unidirectional=is_unidirectional)
        connection._protocol.send_event(event=event)

        try:
            timeout = connection.config.stream_creation_timeout
            async with asyncio.timeout(delay=timeout):
                stream_id: StreamId = await future
        except asyncio.TimeoutError:
            logger.warning("Timeout creating stream on session %s", self.session_id)
            raise TimeoutError(f"Session {self.session_id} timed out creating stream after {timeout}s") from None
        except Exception:
            raise

        stream_handle = connection._stream_handles.get(stream_id)
        if stream_handle is None:
            logger.error("Internal error: Stream handle %d missing after creation", stream_id)
            raise StreamError(f"Internal error creating stream handle for {stream_id}")

        if not isinstance(stream_handle, (WebTransportStream, WebTransportSendStream)):
            raise StreamError(f"Invalid stream handle type for {stream_id}")

        return stream_handle

    def _on_session_closed(self, event: Event) -> None:
        """Handle session closed event to update cached state."""
        self._cached_state = SessionState.CLOSED

    def _on_session_ready(self, event: Event) -> None:
        """Handle session ready event to update cached state."""
        self._cached_state = SessionState.CONNECTED

    def __repr__(self) -> str:
        """Provide a developer-friendly representation."""
        return f"<WebTransportSession id={self.session_id} state={self._cached_state}>"



================================================
FILE: src/pywebtransport/stream.py
================================================
"""High-level abstractions for WebTransport streams."""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Self

from pywebtransport._protocol.events import (
    UserGetStreamDiagnostics,
    UserResetStream,
    UserSendStreamData,
    UserStopStream,
    UserStreamRead,
)
from pywebtransport.constants import ErrorCodes
from pywebtransport.events import Event, EventEmitter
from pywebtransport.exceptions import ConnectionError, StreamError, TimeoutError
from pywebtransport.types import Buffer, SessionId, StreamDirection, StreamId, StreamState
from pywebtransport.utils import ensure_buffer, get_logger

if TYPE_CHECKING:
    from pywebtransport.session import WebTransportSession


__all__: list[str] = [
    "StreamDiagnostics",
    "StreamType",
    "WebTransportReceiveStream",
    "WebTransportSendStream",
    "WebTransportStream",
]

DEFAULT_EVENT_HISTORY_SIZE: int = 0
DEFAULT_EVENT_QUEUE_SIZE: int = 16
DEFAULT_MAX_EVENT_LISTENERS: int = 20

logger = get_logger(name=__name__)


@dataclass(kw_only=True)
class StreamDiagnostics:
    """A snapshot of stream diagnostics."""

    stream_id: StreamId
    session_id: SessionId
    direction: StreamDirection
    state: StreamState
    created_at: float
    bytes_sent: int
    bytes_received: int
    read_buffer_size: int
    write_buffer_size: int
    close_code: int | None
    close_reason: str | None
    closed_at: float | None


class _BaseStream:
    """Base class for WebTransport stream handles."""

    _stream_id: StreamId
    events: EventEmitter

    def __init__(self, *, session: WebTransportSession, stream_id: StreamId) -> None:
        """Initialize the base stream handle."""
        self._session = weakref.ref(session)
        self._stream_id = stream_id
        self._cached_state = StreamState.OPEN
        self.events = EventEmitter(
            max_queue_size=DEFAULT_EVENT_QUEUE_SIZE,
            max_history=DEFAULT_EVENT_HISTORY_SIZE,
            max_listeners=DEFAULT_MAX_EVENT_LISTENERS,
        )
        self.events.on(event_type="stream_closed", handler=self._on_closed)

    @property
    def is_closed(self) -> bool:
        """Return True if the stream is fully closed."""
        return self._cached_state == StreamState.CLOSED

    @property
    def session(self) -> WebTransportSession:
        """Get the parent session handle."""
        session = self._session()
        if session is None:
            raise ConnectionError("Session is gone.")
        return session

    @property
    def state(self) -> StreamState:
        """Get the current state of the stream."""
        return self._cached_state

    @property
    def stream_id(self) -> StreamId:
        """Get the unique identifier for this stream."""
        return self._stream_id

    async def diagnostics(self) -> StreamDiagnostics:
        """Get diagnostic information about the stream."""
        connection = self.session._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserGetStreamDiagnostics(request_id=request_id, stream_id=self.stream_id)
        connection._protocol.send_event(event=event)

        try:
            diag_data = await future
        except ConnectionError as e:
            raise StreamError(f"Connection is closed, cannot get diagnostics: {e}", stream_id=self.stream_id) from e

        return StreamDiagnostics(**diag_data)

    def _on_closed(self, event: Event) -> None:
        """Handle stream closed event."""
        self._cached_state = StreamState.CLOSED

    def __repr__(self) -> str:
        """Provide a developer-friendly representation."""
        return f"<{self.__class__.__name__} id={self.stream_id} state={self._cached_state}>"


class WebTransportReceiveStream(_BaseStream):
    """Represents the readable side of a WebTransport stream."""

    def __init__(self, *, session: WebTransportSession, stream_id: StreamId) -> None:
        """Initialize the receive stream handle."""
        super().__init__(session=session, stream_id=stream_id)
        self._read_eof = False

    @property
    def can_read(self) -> bool:
        """Return True if the stream is readable."""
        return self._cached_state not in (StreamState.RESET_RECEIVED, StreamState.CLOSED)

    @property
    def direction(self) -> StreamDirection:
        """Get the directionality of the stream."""
        return StreamDirection.RECEIVE_ONLY

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context manager."""
        await self.stop_receiving()

    async def close(self) -> None:
        """Close the receiving side of the stream."""
        await self.stop_receiving()

    async def read(self, *, max_bytes: int = -1) -> bytes:
        """Read data from the stream."""
        if self._read_eof:
            return b""

        if self.is_closed:
            self._read_eof = True
            return b""

        connection = self.session._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()

        limit = max_bytes if max_bytes >= 0 else None
        event = UserStreamRead(request_id=request_id, stream_id=self.stream_id, max_bytes=limit)
        connection._protocol.send_event(event=event)

        try:
            data = await future
        except StreamError as e:
            if e.error_code == ErrorCodes.STREAM_STATE_ERROR:
                self._read_eof = True
                return b""
            raise

        if not data and max_bytes != 0:
            self._read_eof = True

        return bytes(data)

    async def read_all(self) -> bytes:
        """Read all data from the stream until EOF."""
        chunks: list[bytes] = []
        async for chunk in self:
            chunks.append(chunk)
        return b"".join(chunks)

    async def readexactly(self, *, n: int) -> bytes:
        """Read exactly n bytes from the stream."""
        if n < 0:
            raise ValueError("n must be a non-negative integer")
        if n == 0:
            return b""

        connection = self.session._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")
        read_timeout = connection.config.read_timeout

        chunks: list[bytes] = []
        bytes_read = 0

        try:
            async with asyncio.timeout(read_timeout):
                while bytes_read < n:
                    needed = n - bytes_read
                    chunk = await self.read(max_bytes=needed)
                    if not chunk:
                        partial = b"".join(chunks)
                        raise asyncio.IncompleteReadError(partial, n)

                    chunks.append(chunk)
                    bytes_read += len(chunk)
        except asyncio.TimeoutError:
            raise TimeoutError(f"readexactly timed out after {read_timeout}s") from None

        return b"".join(chunks)

    async def readline(self, *, limit: int = -1) -> bytes:
        """Read a line from the stream."""
        return await self.readuntil(separator=b"\n", limit=limit)

    async def readuntil(self, *, separator: bytes, limit: int = -1) -> bytes:
        """Read data from the stream until a separator is found."""
        if not separator:
            raise ValueError("Separator cannot be empty")

        connection = self.session._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")
        read_timeout = connection.config.read_timeout

        data = bytearray()
        try:
            async with asyncio.timeout(read_timeout):
                while True:
                    chunk = await self.read(max_bytes=1)
                    if not chunk:
                        raise asyncio.IncompleteReadError(bytes(data), None)
                    data.extend(chunk)
                    if data.endswith(separator):
                        return bytes(data)
                    if limit > 0 and len(data) > limit:
                        raise StreamError(f"Separator not found within limit {limit}", stream_id=self.stream_id)
        except asyncio.TimeoutError:
            raise TimeoutError(f"readuntil timed out after {read_timeout}s") from None

    async def stop_receiving(self, *, error_code: int = ErrorCodes.NO_ERROR) -> None:
        """Signal the peer to stop sending data."""
        connection = self.session._connection()
        if connection is None:
            return

        request_id, future = connection._protocol.create_request()
        event = UserStopStream(request_id=request_id, stream_id=self.stream_id, error_code=error_code)
        connection._protocol.send_event(event=event)
        await future
        self._cached_state = StreamState.RESET_RECEIVED

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Iterate over the stream chunks."""
        return self

    async def __anext__(self) -> bytes:
        """Get the next chunk of data."""
        data = await self.read()
        if not data:
            raise StopAsyncIteration
        return data


class WebTransportSendStream(_BaseStream):
    """Represents the writable side of a WebTransport stream."""

    @property
    def can_write(self) -> bool:
        """Return True if the stream is writable."""
        return self._cached_state not in (StreamState.HALF_CLOSED_LOCAL, StreamState.CLOSED, StreamState.RESET_SENT)

    @property
    def direction(self) -> StreamDirection:
        """Get the directionality of the stream."""
        return StreamDirection.SEND_ONLY

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context manager."""
        exit_error_code: int | None = None

        if isinstance(exc_val, asyncio.CancelledError):
            exit_error_code = ErrorCodes.APPLICATION_ERROR
        elif isinstance(exc_val, BaseException):
            exit_error_code = getattr(exc_val, "error_code", ErrorCodes.APPLICATION_ERROR)

        await self.close(error_code=exit_error_code)

    async def close(self, *, error_code: int | None = None) -> None:
        """Close the sending side of the stream."""
        if error_code is not None:
            await self.stop_sending(error_code=error_code)
            return

        try:
            await self.write(data=b"", end_stream=True)
            self._cached_state = StreamState.HALF_CLOSED_LOCAL
        except StreamError as e:
            logger.debug("Ignoring expected StreamError on stream %s close: %s", self.stream_id, e)
        except Exception as e:
            logger.error("Unexpected error during stream %s close: %s", self.stream_id, e, exc_info=True)
            raise

    async def stop_sending(self, *, error_code: int = ErrorCodes.NO_ERROR) -> None:
        """Stop sending data and reset the stream."""
        connection = self.session._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserResetStream(request_id=request_id, stream_id=self.stream_id, error_code=error_code)
        connection._protocol.send_event(event=event)
        await future
        self._cached_state = StreamState.RESET_SENT

    async def write(self, *, data: Buffer, end_stream: bool = False) -> None:
        """Write data to the stream."""
        try:
            buffer_data = ensure_buffer(data=data)
        except TypeError as e:
            logger.debug("Stream %d write failed pre-validation: %s", self.stream_id, e)
            raise

        if not buffer_data and not end_stream:
            return

        connection = self.session._connection()
        if connection is None:
            raise ConnectionError("Connection is gone.")

        request_id, future = connection._protocol.create_request()
        event = UserSendStreamData(
            request_id=request_id, stream_id=self.stream_id, data=buffer_data, end_stream=end_stream
        )
        connection._protocol.send_event(event=event)

        try:
            await future
        except Exception:
            raise

    async def write_all(self, *, data: Buffer, chunk_size: int = 65536, end_stream: bool = False) -> None:
        """Write buffer data to the stream in chunks."""
        try:
            buffer_data = ensure_buffer(data=data)
            offset = 0
            data_len = len(buffer_data)

            if not buffer_data and end_stream:
                await self.write(data=b"", end_stream=True)
                return

            while offset < data_len:
                chunk = buffer_data[offset : offset + chunk_size]
                offset += len(chunk)
                is_last_chunk = offset >= data_len
                await self.write(data=chunk, end_stream=end_stream if is_last_chunk else False)
        except StreamError as e:
            logger.debug("Error writing bytes to stream %d: %s", self.stream_id, e)
            raise


class WebTransportStream(_BaseStream):
    """Represents the bidirectional WebTransport stream."""

    def __init__(self, *, session: WebTransportSession, stream_id: StreamId) -> None:
        """Initialize the bidirectional stream handle."""
        super().__init__(session=session, stream_id=stream_id)
        self._reader = WebTransportReceiveStream(session=session, stream_id=stream_id)
        self._writer = WebTransportSendStream(session=session, stream_id=stream_id)

    @property
    def can_read(self) -> bool:
        """Return True if the stream is readable."""
        return self._reader.can_read

    @property
    def can_write(self) -> bool:
        """Return True if the stream is writable."""
        return self._writer.can_write

    @property
    def direction(self) -> StreamDirection:
        """Get the directionality of the stream."""
        return StreamDirection.BIDIRECTIONAL

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context manager."""
        exit_error_code: int | None = None

        if isinstance(exc_val, asyncio.CancelledError):
            exit_error_code = ErrorCodes.APPLICATION_ERROR
        elif isinstance(exc_val, BaseException):
            exit_error_code = getattr(exc_val, "error_code", ErrorCodes.APPLICATION_ERROR)

        await self.close(error_code=exit_error_code)

    async def close(self, *, error_code: int | None = None) -> None:
        """Close both sides of the stream."""
        await self._writer.close(error_code=error_code)
        stop_code = error_code if error_code is not None else ErrorCodes.NO_ERROR
        await self._reader.stop_receiving(error_code=stop_code)

    async def read(self, *, max_bytes: int = -1) -> bytes:
        """Read data from the stream."""
        return await self._reader.read(max_bytes=max_bytes)

    async def read_all(self) -> bytes:
        """Read all data from the stream until EOF."""
        return await self._reader.read_all()

    async def readexactly(self, *, n: int) -> bytes:
        """Read exactly n bytes from the stream."""
        return await self._reader.readexactly(n=n)

    async def readline(self, *, limit: int = -1) -> bytes:
        """Read a line from the stream."""
        return await self._reader.readline(limit=limit)

    async def readuntil(self, *, separator: bytes, limit: int = -1) -> bytes:
        """Read data from the stream until a separator is found."""
        return await self._reader.readuntil(separator=separator, limit=limit)

    async def stop_receiving(self, *, error_code: int = ErrorCodes.NO_ERROR) -> None:
        """Signal the peer to stop sending data."""
        await self._reader.stop_receiving(error_code=error_code)

    async def stop_sending(self, *, error_code: int = ErrorCodes.NO_ERROR) -> None:
        """Stop sending data and reset the stream."""
        await self._writer.stop_sending(error_code=error_code)

    async def write(self, *, data: Buffer, end_stream: bool = False) -> None:
        """Write data to the stream."""
        await self._writer.write(data=data, end_stream=end_stream)

    async def write_all(self, *, data: Buffer, chunk_size: int = 65536, end_stream: bool = False) -> None:
        """Write buffer data to the stream in chunks."""
        await self._writer.write_all(data=data, chunk_size=chunk_size, end_stream=end_stream)

    def _on_closed(self, event: Event) -> None:
        """Handle stream closed event and propagate to children."""
        super()._on_closed(event)
        self._reader._on_closed(event)
        self._writer._on_closed(event)

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Iterate over the stream chunks."""
        return self

    async def __anext__(self) -> bytes:
        """Get the next chunk of data."""
        return await self._reader.__anext__()


type StreamType = WebTransportStream | WebTransportReceiveStream | WebTransportSendStream



================================================
FILE: src/pywebtransport/types.py
================================================
"""Core data types and interface protocols for the library."""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AbstractAsyncContextManager as AsyncContextManager
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

__all__: list[str] = [
    "Address",
    "AsyncContextManager",
    "AsyncGenerator",
    "AsyncIterator",
    "Buffer",
    "ConnectionId",
    "ConnectionState",
    "Data",
    "ErrorCode",
    "EventData",
    "EventType",
    "Future",
    "Headers",
    "Priority",
    "RequestId",
    "SSLContext",
    "Serializer",
    "SessionId",
    "SessionProtocol",
    "SessionState",
    "StreamDirection",
    "StreamId",
    "StreamState",
    "Timeout",
    "Timestamp",
    "URL",
    "URLParts",
    "WebTransportProtocol",
    "Weight",
]


type Address = tuple[str, int]
type Buffer = bytes | bytearray | memoryview
type ConnectionId = str
type Data = bytes | bytearray | memoryview | str
type ErrorCode = int
type EventData = Any
type Future[T] = asyncio.Future[T]
type Headers = dict[str | bytes, str | bytes] | list[tuple[str | bytes, str | bytes]]
type Priority = int
type RequestId = int
type SessionId = int
type SSLContext = ssl.SSLContext
type StreamId = int
type Timeout = float | None
type Timestamp = float
type URL = str
type URLParts = tuple[str, int, str]
type Weight = int


@runtime_checkable
class Serializer(Protocol):
    """A protocol for serializing and deserializing structured data."""

    def deserialize(self, *, data: Buffer, obj_type: Any = None) -> Any:
        """Deserialize buffer into an object."""
        ...

    def serialize(self, *, obj: Any) -> bytes:
        """Serialize an object into bytes."""
        ...


@runtime_checkable
class SessionProtocol(Protocol):
    """A protocol defining the essential interface of a WebTransport session."""

    @property
    def headers(self) -> Headers:
        """Get the session headers."""
        ...

    @property
    def path(self) -> str:
        """Get the session path."""
        ...

    @property
    def remote_address(self) -> Address | None:
        """Get the remote address of the peer."""
        ...

    @property
    def session_id(self) -> SessionId:
        """Get the session ID."""
        ...

    @property
    def state(self) -> SessionState:
        """Get the current session state."""
        ...

    async def close(self, *, error_code: int = 0, reason: str | None = None) -> None:
        """Close the session."""
        ...


@runtime_checkable
class WebTransportProtocol(Protocol):
    """A protocol for the underlying WebTransport transport layer."""

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when a connection is lost."""
        ...

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Called when a connection is established."""
        ...

    def datagram_received(self, data: Buffer, addr: Address) -> None:
        """Called when a datagram is received."""
        ...

    def error_received(self, exc: Exception) -> None:
        """Called when an error is received."""
        ...


class ConnectionState(StrEnum):
    """Enumeration of connection states."""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"
    DRAINING = "draining"
    CLOSED = "closed"
    FAILED = "failed"


class EventType(StrEnum):
    """Enumeration of system event types."""

    CAPSULE_RECEIVED = "capsule_received"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_LOST = "connection_lost"
    DATAGRAM_ERROR = "datagram_error"
    DATAGRAM_RECEIVED = "datagram_received"
    DATAGRAM_SENT = "datagram_sent"
    PROTOCOL_ERROR = "protocol_error"
    SESSION_CLOSED = "session_closed"
    SESSION_DATA_BLOCKED = "session_data_blocked"
    SESSION_DRAINING = "session_draining"
    SESSION_MAX_DATA_UPDATED = "session_max_data_updated"
    SESSION_MAX_STREAMS_BIDI_UPDATED = "session_max_streams_bidi_updated"
    SESSION_MAX_STREAMS_UNI_UPDATED = "session_max_streams_uni_updated"
    SESSION_READY = "session_ready"
    SESSION_REQUEST = "session_request"
    SESSION_STREAMS_BLOCKED = "session_streams_blocked"
    SETTINGS_RECEIVED = "settings_received"
    STREAM_CLOSED = "stream_closed"
    STREAM_DATA_RECEIVED = "stream_data_received"
    STREAM_ERROR = "stream_error"
    STREAM_OPENED = "stream_opened"
    TIMEOUT_ERROR = "timeout_error"


class SessionState(StrEnum):
    """Enumeration of WebTransport session states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"
    DRAINING = "draining"
    CLOSED = "closed"


class StreamDirection(StrEnum):
    """Enumeration of stream directions."""

    BIDIRECTIONAL = "bidirectional"
    SEND_ONLY = "send_only"
    RECEIVE_ONLY = "receive_only"


class StreamState(StrEnum):
    """Enumeration of WebTransport stream states."""

    OPEN = "open"
    HALF_CLOSED_LOCAL = "half_closed_local"
    HALF_CLOSED_REMOTE = "half_closed_remote"
    RESET_SENT = "reset_sent"
    RESET_RECEIVED = "reset_received"
    CLOSED = "closed"



================================================
FILE: src/pywebtransport/utils.py
================================================
"""Shared, general-purpose utilities."""

from __future__ import annotations

import logging
import time

from pywebtransport._wtransport import generate_self_signed_cert
from pywebtransport.types import Buffer, Headers

__all__: list[str] = [
    "ensure_buffer",
    "find_header",
    "find_header_str",
    "format_duration",
    "generate_self_signed_cert",
    "get_logger",
    "get_timestamp",
    "merge_headers",
]


def ensure_buffer(*, data: Buffer | str, encoding: str = "utf-8") -> Buffer:
    """Ensure that the given data is in a buffer-compatible format."""
    match data:
        case str():
            return data.encode(encoding=encoding)
        case bytes() | bytearray() | memoryview():
            return data
        case _:
            raise TypeError(f"Expected str or Buffer, got {type(data).__name__}")


def find_header(*, headers: Headers, key: str, default: str | bytes | None = None) -> str | bytes | None:
    """Find a header value case-insensitively from a dict or list."""
    target_key = key.lower()
    target_key_bytes = target_key.encode("utf-8")

    if isinstance(headers, dict):
        if target_key in headers:
            return headers[target_key]
        return headers.get(target_key_bytes, default)

    for k, v in headers:
        if isinstance(k, bytes):
            if k.lower() == target_key_bytes:
                return v
        elif k.lower() == target_key:
            return v
    return default


def find_header_str(*, headers: Headers, key: str, default: str | None = None) -> str | None:
    """Find a header value and decode it to a string if necessary."""
    value = find_header(headers=headers, key=key)
    if value is None:
        return default

    if isinstance(value, str):
        return value

    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return default


def format_duration(*, seconds: float) -> str:
    """Format a duration in seconds into a human-readable string."""
    if seconds < 1e-6:
        return f"{seconds * 1e9:.0f}ns"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.1f}µs"
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m{secs:.1f}s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}h{minutes}m{secs:.1f}s"


def get_logger(*, name: str) -> logging.Logger:
    """Get a logger instance with a specific name."""
    return logging.getLogger(name=name)


def get_timestamp() -> float:
    """Get the current monotonic timestamp."""
    return time.perf_counter()


def merge_headers(*, base: Headers, update: Headers | None) -> Headers:
    """Merge two sets of headers, preserving list format if present."""
    if update is None:
        if isinstance(base, dict):
            return base.copy()
        return list(base)

    if isinstance(base, dict) and isinstance(update, dict):
        new_headers = base.copy()
        new_headers.update(update)
        return new_headers

    base_list = list(base.items()) if isinstance(base, dict) else list(base)
    update_list = list(update.items()) if isinstance(update, dict) else list(update)
    return base_list + update_list



================================================
FILE: src/pywebtransport/version.py
================================================
"""Defines the semantic version number for the library."""

from __future__ import annotations

import importlib.metadata

__all__: list[str] = ["__version__"]

__version__ = importlib.metadata.version("pywebtransport")



================================================
FILE: src/pywebtransport/_adapter/__init__.py
================================================
[Empty file]


================================================
FILE: src/pywebtransport/_adapter/base.py
================================================
"""Shared protocol adapter logic for client and server."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from typing import Any

from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import (
    ConnectionTerminated,
    DatagramFrameReceived,
    HandshakeCompleted,
    QuicEvent,
    StreamDataReceived,
    StreamReset,
)
from aioquic.quic.logger import QuicLoggerTrace

from pywebtransport._adapter.pending import PendingRequestManager
from pywebtransport._protocol.events import (
    CloseQuicConnection,
    CreateH3Session,
    CreateQuicStream,
    Effect,
    EmitConnectionEvent,
    EmitSessionEvent,
    EmitStreamEvent,
    InternalBindH3Session,
    InternalBindQuicStream,
    InternalCleanupEarlyEvents,
    InternalCleanupResources,
    InternalFailH3Session,
    InternalFailQuicStream,
    InternalReturnStreamData,
    LogH3Frame,
    NotifyRequestDone,
    NotifyRequestFailed,
    ProcessProtocolEvent,
    ProtocolEvent,
    RescheduleQuicTimer,
    ResetQuicStream,
    SendH3Capsule,
    SendH3Datagram,
    SendH3Goaway,
    SendH3Headers,
    SendQuicData,
    SendQuicDatagram,
    StopQuicStream,
    TransportConnectionTerminated,
    TransportDatagramFrameReceived,
    TransportHandshakeCompleted,
    TransportQuicParametersReceived,
    TransportQuicTimerFired,
    TransportStreamDataReceived,
    TransportStreamReset,
    TriggerQuicTimer,
)
from pywebtransport._wtransport import WebTransportEngine
from pywebtransport.config import ClientConfig, ServerConfig
from pywebtransport.constants import DEFAULT_MAX_EVENT_QUEUE_SIZE, ErrorCodes
from pywebtransport.exceptions import ConnectionError
from pywebtransport.types import Buffer, EventType
from pywebtransport.utils import get_logger

__all__: list[str] = []

logger = get_logger(name=__name__)


class WebTransportCommonProtocol(QuicConnectionProtocol):
    """Base adapter translating quic events to internal protocol events."""

    _quic_logger: QuicLoggerTrace | None = None

    def __init__(
        self,
        *,
        quic: QuicConnection,
        config: ClientConfig | ServerConfig,
        is_client: bool,
        stream_handler: Any = None,
        loop: asyncio.AbstractEventLoop | None = None,
        max_event_queue_size: int = DEFAULT_MAX_EVENT_QUEUE_SIZE,
    ) -> None:
        """Initialize the common protocol adapter."""
        super().__init__(quic=quic, stream_handler=stream_handler)
        self._loop = loop if loop is not None else asyncio.get_running_loop()
        self._config = config
        self._is_client = is_client
        self._max_event_queue_size = max_event_queue_size
        self._timer_handle: asyncio.TimerHandle | None = None

        self._pending_manager = PendingRequestManager()

        self._engine = WebTransportEngine(connection_id=str(quic.host_cid), config=config, is_client=is_client)

        self._resource_gc_timer: asyncio.TimerHandle | None = None
        self._early_event_cleanup_timer: asyncio.TimerHandle | None = None

        self._pending_effects: deque[Effect] = deque()
        self._is_processing_effects = False
        self._status_callback: Callable[[EventType, dict[str, Any]], None] | None = None

    def close_connection(self, *, error_code: int, reason_phrase: str | None = None) -> None:
        """Close the QUIC connection."""
        if self._quic._close_event is not None:
            return

        self._quic.close(error_code=error_code, reason_phrase=reason_phrase if reason_phrase is not None else "")
        self.transmit()
        self._cancel_maintenance_timers()
        self._pending_manager.fail_all(exception=ConnectionError(f"Connection closed: {reason_phrase}"))

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle connection loss."""
        if self._timer_handle is not None:
            self._timer_handle.cancel()
            self._timer_handle = None

        self._cancel_maintenance_timers()

        event_to_send: TransportConnectionTerminated | None = None
        already_closing_locally = self._quic._close_event is not None

        if exc is None and already_closing_locally:
            pass
        else:
            if exc is not None:
                code = getattr(exc, "error_code", ErrorCodes.INTERNAL_ERROR)
                reason = str(exc)
            else:
                code = ErrorCodes.NO_ERROR
                reason = "Connection closed"
            event_to_send = TransportConnectionTerminated(error_code=code, reason_phrase=reason)

        if event_to_send is not None:
            self._push_event_to_engine(event=event_to_send)

        self._pending_manager.fail_all(exception=exc if exc is not None else ConnectionError("Connection lost"))
        super().connection_lost(exc)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle connection being made."""
        super().connection_made(transport)
        self._setup_maintenance_timers()

    def create_request(self) -> tuple[int, asyncio.Future[Any]]:
        """Create a new tracked request."""
        return self._pending_manager.create_request()

    def get_next_available_stream_id(self, *, is_unidirectional: bool) -> int:
        """Get the next available stream ID from the QUIC connection."""
        return self._quic.get_next_available_stream_id(is_unidirectional=is_unidirectional)

    def get_server_name(self) -> str | None:
        """Get the server name (SNI) from the QUIC configuration."""
        return self._quic.configuration.server_name

    def handle_timer_now(self) -> None:
        """Handle the QUIC timer expiry."""
        self._quic.handle_timer(now=self._loop.time())

        event = self._quic.next_event()
        while event is not None:
            self.quic_event_received(event=event)
            event = self._quic.next_event()

        self.transmit()

    def log_event(self, *, category: str, event: str, data: dict[str, Any]) -> None:
        """Log an H3 event via the QUIC logger."""
        if self._quic_logger is not None:
            self._quic_logger.log_event(category=category, event=event, data=data)

    def quic_event_received(self, event: QuicEvent) -> None:
        """Translate aioquic events into internal ProtocolEvents."""
        match event:
            case HandshakeCompleted():
                self._on_handshake_completed()
            case ConnectionTerminated(error_code=error_code, reason_phrase=reason_phrase):
                logger.debug(
                    "QUIC ConnectionTerminated event received: code=%#x reason='%s'", error_code, reason_phrase
                )
                self._push_event_to_engine(
                    event=TransportConnectionTerminated(error_code=error_code, reason_phrase=reason_phrase)
                )
            case DatagramFrameReceived(data=data):
                self._push_event_to_engine(event=TransportDatagramFrameReceived(data=data))
            case StreamDataReceived(data=data, end_stream=end_stream, stream_id=stream_id):
                self._push_event_to_engine(
                    event=TransportStreamDataReceived(data=data, end_stream=end_stream, stream_id=stream_id)
                )
            case StreamReset(error_code=error_code, stream_id=stream_id):
                self._push_event_to_engine(event=TransportStreamReset(error_code=error_code, stream_id=stream_id))
            case _:
                pass

    def reset_stream(self, *, stream_id: int, error_code: int) -> None:
        """Reset the sending side of a QUIC stream."""
        if self._quic._close_event is not None:
            return

        try:
            self._quic.reset_stream(stream_id=stream_id, error_code=error_code)
            self.transmit()
        except (AssertionError, ValueError):
            logger.debug("Dropping ResetQuicStream for stream %d: Stream unknown or state conflict.", stream_id)

    def schedule_timer_now(self) -> None:
        """Schedule the next QUIC timer callback."""
        if self._timer_handle is not None:
            self._timer_handle.cancel()

        timer_at = self._quic.get_timer()
        if timer_at is not None:
            self._timer_handle = self._loop.call_at(timer_at, self._handle_timer)

    def send_datagram_frame(self, *, data: Buffer | list[Buffer]) -> None:
        """Send a QUIC datagram frame (supports Scatter/Gather)."""
        if self._quic._close_event is not None:
            logger.debug("Attempted to send datagram while connection is closing.")
            return

        bytes_data: bytes
        if isinstance(data, list):
            bytes_data = b"".join(data)
        else:
            bytes_data = bytes(data)

        self._quic.send_datagram_frame(data=bytes_data)
        self.transmit()

    def send_event(self, *, event: ProtocolEvent) -> None:
        """Send a user-initiated event to the engine."""
        self._push_event_to_engine(event=event)

    def send_stream_data(self, *, stream_id: int, data: bytes, end_stream: bool = False) -> None:
        """Send data on a QUIC stream."""
        if self._quic._close_event is not None:
            if data or not end_stream:
                logger.debug("Attempted to send stream data while connection is closing (stream %d).", stream_id)
                return

        try:
            self._quic.send_stream_data(stream_id=stream_id, data=data, end_stream=end_stream)
            self.transmit()
        except (AssertionError, ValueError):
            logger.debug("Dropping SendQuicData for stream %d: Stream unknown or state conflict.", stream_id)

    def set_status_callback(self, *, callback: Callable[[EventType, dict[str, Any]], None]) -> None:
        """Set the callback for high-level status events."""
        self._status_callback = callback

    def stop_stream(self, *, stream_id: int, error_code: int) -> None:
        """Stop the receiving side of a QUIC stream."""
        try:
            self._quic.stop_stream(stream_id=stream_id, error_code=error_code)
        except (AssertionError, ValueError):
            logger.debug("Dropping StopQuicStream for stream %d: Stream unknown or state conflict.", stream_id)

    def transmit(self) -> None:
        """Transmit pending QUIC packets."""
        transport = self._transport
        if (
            transport is not None
            and hasattr(transport, "is_closing")
            and not transport.is_closing()
            and hasattr(transport, "sendto")
        ):
            packets = self._quic.datagrams_to_send(now=self._loop.time())
            is_client = self._quic.configuration.is_client
            for data, addr in packets:
                try:
                    if is_client:
                        transport.sendto(data)
                    else:
                        transport.sendto(data, addr)
                except (ConnectionRefusedError, OSError) as e:
                    logger.debug("Failed to send UDP packet: %s", e)
                except Exception as e:
                    logger.error("Unexpected error during transmit: %s", e, exc_info=True)

    def _allocate_stream_id(self, *, is_unidirectional: bool) -> int:
        """Atomically allocate and reserve a stream ID."""
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=is_unidirectional)
        self._quic.send_stream_data(stream_id=stream_id, data=b"", end_stream=False)
        return stream_id

    def _cancel_maintenance_timers(self) -> None:
        """Cancel internal maintenance timers."""
        if self._resource_gc_timer is not None:
            self._resource_gc_timer.cancel()
            self._resource_gc_timer = None
        if self._early_event_cleanup_timer is not None:
            self._early_event_cleanup_timer.cancel()
            self._early_event_cleanup_timer = None

    def _execute_effects(self, *, effects: list[Effect]) -> None:
        """Execute effects returned by the engine."""
        for effect in effects:
            self._pending_effects.append(effect)

        if self._is_processing_effects:
            return

        self._is_processing_effects = True
        try:
            while self._pending_effects:
                effect = self._pending_effects.popleft()
                self._process_single_effect(effect=effect)
        finally:
            self._is_processing_effects = False

    def _handle_early_event_cleanup_timer(self) -> None:
        """Trigger early event cleanup in the engine."""
        self._early_event_cleanup_timer = None
        self._push_event_to_engine(event=InternalCleanupEarlyEvents())
        if self._config.pending_event_ttl > 0:
            self._early_event_cleanup_timer = self._loop.call_later(
                self._config.pending_event_ttl, self._handle_early_event_cleanup_timer
            )

    def _handle_resource_gc_timer(self) -> None:
        """Trigger resource GC in the engine."""
        self._resource_gc_timer = None
        self._push_event_to_engine(event=InternalCleanupResources())
        if self._config.resource_cleanup_interval > 0:
            self._resource_gc_timer = self._loop.call_later(
                self._config.resource_cleanup_interval, self._handle_resource_gc_timer
            )

    def _handle_timer(self) -> None:
        """Handle the QUIC timer expiry by injecting an event."""
        self._timer_handle = None
        self._push_event_to_engine(event=TransportQuicTimerFired())

    def _on_handshake_completed(self) -> None:
        """Handle QUIC handshake completion."""
        self._push_event_to_engine(event=TransportHandshakeCompleted())

        self._quic_logger = getattr(self._quic, "_quic_logger", None)

        control_id = self._quic.get_next_available_stream_id(is_unidirectional=True)
        encoder_id = self._quic.get_next_available_stream_id(is_unidirectional=True)
        decoder_id = self._quic.get_next_available_stream_id(is_unidirectional=True)

        init_effects = self._engine.initialize_h3_transport(
            control_id=control_id, encoder_id=encoder_id, decoder_id=decoder_id
        )
        self._execute_effects(effects=init_effects)

        remote_max_datagram_frame_size = getattr(self._quic, "_remote_max_datagram_frame_size", None)
        if remote_max_datagram_frame_size is not None:
            self._push_event_to_engine(
                event=TransportQuicParametersReceived(remote_max_datagram_frame_size=remote_max_datagram_frame_size)
            )

    def _process_single_effect(self, *, effect: Effect) -> None:
        """Process a single side effect."""
        match effect:
            case SendQuicData(stream_id=sid, data=d, end_stream=es):
                self.send_stream_data(stream_id=sid, data=bytes(d), end_stream=es)

            case SendQuicDatagram(data=d):
                self.send_datagram_frame(data=d)

            case ResetQuicStream(stream_id=sid, error_code=ec):
                self.reset_stream(stream_id=sid, error_code=ec)

            case StopQuicStream(stream_id=sid, error_code=ec):
                self.stop_stream(stream_id=sid, error_code=ec)

            case CloseQuicConnection(error_code=ec, reason=r):
                self.close_connection(error_code=ec, reason_phrase=r)

            case NotifyRequestDone(request_id=rid, result=res):
                self._pending_manager.complete_request(request_id=rid, result=res)

            case NotifyRequestFailed(request_id=rid, exception=exc):
                self._pending_manager.fail_request(request_id=rid, exception=exc)

            case CreateH3Session(request_id=rid, path=p, headers=h):
                try:
                    stream_id = self._allocate_stream_id(is_unidirectional=False)
                    server_name = self.get_server_name()
                    authority = server_name if server_name is not None else ""
                    h3_effects = self._engine.encode_session_request(
                        stream_id=stream_id, path=p, headers=h, authority=authority
                    )
                    self._execute_effects(effects=h3_effects)
                    self._push_event_to_engine(event=InternalBindH3Session(request_id=rid, stream_id=stream_id))
                except Exception as e:
                    self._push_event_to_engine(event=InternalFailH3Session(request_id=rid, exception=e))

            case CreateQuicStream(request_id=rid, session_id=sid, is_unidirectional=uni):
                try:
                    stream_id = self._allocate_stream_id(is_unidirectional=uni)
                    control_stream_id = sid
                    h3_effects = self._engine.encode_stream_creation(
                        stream_id=stream_id, control_stream_id=control_stream_id, is_unidirectional=uni
                    )
                    self._execute_effects(effects=h3_effects)
                    self._push_event_to_engine(
                        event=InternalBindQuicStream(
                            request_id=rid, stream_id=stream_id, session_id=sid, is_unidirectional=uni
                        )
                    )
                except Exception as e:
                    self._push_event_to_engine(
                        event=InternalFailQuicStream(request_id=rid, session_id=sid, is_unidirectional=uni, exception=e)
                    )

            case SendH3Headers(stream_id=sid, status=s, end_stream=end):
                h3_effects = self._engine.encode_headers(stream_id=sid, status=s, end_stream=end)
                self._execute_effects(effects=h3_effects)

            case SendH3Capsule(stream_id=sid, capsule_type=t, capsule_data=d, end_stream=es):
                h3_effects = self._engine.encode_capsule(
                    stream_id=sid, capsule_type=t, capsule_data=bytes(d), end_stream=es
                )
                self._execute_effects(effects=h3_effects)

            case SendH3Datagram(stream_id=sid, data=d):
                h3_effects = self._engine.encode_datagram(stream_id=sid, data=d)
                self._execute_effects(effects=h3_effects)

            case SendH3Goaway():
                h3_effects = self._engine.encode_goaway()
                self._execute_effects(effects=h3_effects)

            case RescheduleQuicTimer():
                self.schedule_timer_now()

            case TriggerQuicTimer():
                self.handle_timer_now()

            case ProcessProtocolEvent(event=evt):
                immediate_effects = self._engine.handle_event(event=evt, now=self._loop.time())
                self._pending_effects.extendleft(reversed(immediate_effects))

            case EmitConnectionEvent(event_type=et, data=d):
                if self._status_callback is not None:
                    self._status_callback(et, d)

            case EmitSessionEvent(event_type=et, data=d):
                if self._status_callback is not None:
                    self._status_callback(et, d)

            case EmitStreamEvent(event_type=et, data=d):
                if self._status_callback is not None:
                    self._status_callback(et, d)

            case LogH3Frame(category=c, event=e, data=d):
                self.log_event(category=c, event=e, data=d)

            case InternalReturnStreamData(stream_id=sid, data=d):
                self._push_event_to_engine(event=InternalReturnStreamData(stream_id=sid, data=d))

            case _:
                pass

    def _push_event_to_engine(self, *, event: ProtocolEvent) -> None:
        """Push an event to the engine and execute resulting effects."""
        effects = self._engine.handle_event(event=event, now=self._loop.time())
        self._execute_effects(effects=effects)
        self.transmit()

    def _setup_maintenance_timers(self) -> None:
        """Start internal maintenance timers."""
        if self._config.resource_cleanup_interval > 0:
            self._resource_gc_timer = self._loop.call_later(
                self._config.resource_cleanup_interval, self._handle_resource_gc_timer
            )
        if self._config.pending_event_ttl > 0:
            self._early_event_cleanup_timer = self._loop.call_later(
                self._config.pending_event_ttl, self._handle_early_event_cleanup_timer
            )



================================================
FILE: src/pywebtransport/_adapter/client.py
================================================
"""Internal aioquic protocol adapter and connection factory for the client-side."""

from __future__ import annotations

import asyncio

from aioquic.quic.connection import QuicConnection

from pywebtransport._adapter.base import WebTransportCommonProtocol
from pywebtransport._adapter.utils import create_quic_configuration
from pywebtransport.config import ClientConfig
from pywebtransport.utils import get_logger

__all__: list[str] = []

logger = get_logger(name=__name__)


class WebTransportClientProtocol(WebTransportCommonProtocol):
    """Adapt aioquic client events and actions for the WebTransportEngine."""

    def __init__(
        self,
        *,
        quic: QuicConnection,
        config: ClientConfig,
        loop: asyncio.AbstractEventLoop | None = None,
        max_event_queue_size: int,
        stream_handler: asyncio.Protocol | None = None,
    ) -> None:
        """Initialize the client protocol adapter."""
        super().__init__(
            quic=quic,
            config=config,
            is_client=True,
            stream_handler=stream_handler,
            loop=loop,
            max_event_queue_size=max_event_queue_size,
        )


async def create_quic_endpoint(
    *, host: str, port: int, config: ClientConfig, loop: asyncio.AbstractEventLoop
) -> tuple[asyncio.DatagramTransport, WebTransportClientProtocol]:
    """Establish the underlying QUIC transport and protocol."""
    quic_config = create_quic_configuration(
        alpn_protocols=config.alpn_protocols,
        ca_certs=config.ca_certs,
        certfile=config.certfile,
        congestion_control_algorithm=config.congestion_control_algorithm,
        idle_timeout=config.connection_idle_timeout,
        is_client=True,
        keyfile=config.keyfile,
        max_datagram_size=config.max_datagram_size,
        server_name=host,
        verify_mode=config.verify_mode,
    )

    quic_connection = QuicConnection(configuration=quic_config)
    protocols: list[WebTransportClientProtocol] = []

    def protocol_factory() -> WebTransportClientProtocol:
        protocol = WebTransportClientProtocol(
            quic=quic_connection, config=config, loop=loop, max_event_queue_size=config.max_event_queue_size
        )
        protocols.append(protocol)
        return protocol

    logger.debug("Creating datagram endpoint to %s:%d", host, port)

    try:
        transport, protocol = await loop.create_datagram_endpoint(
            protocol_factory=protocol_factory, remote_addr=(host, port)
        )
    except Exception:
        for protocol in protocols:
            protocol.close_connection(error_code=0, reason_phrase="Handshake failed")
        raise

    logger.debug("Datagram endpoint created.")

    client_protocol = protocol
    client_protocol._quic.connect(addr=(host, port), now=loop.time())
    client_protocol.transmit()

    return transport, client_protocol



================================================
FILE: src/pywebtransport/_adapter/pending.py
================================================
"""Internal manager for pending asyncio requests."""

from __future__ import annotations

import asyncio
import itertools
from typing import Any

from pywebtransport.types import Future, RequestId

__all__: list[str] = []


class PendingRequestManager:
    """Manage lifecycle of pending asynchronous requests."""

    def __init__(self) -> None:
        """Initialize the pending request manager."""
        self._requests: dict[RequestId, Future[Any]] = {}
        self._counter = itertools.count()

    def create_request(self) -> tuple[RequestId, Future[Any]]:
        """Create a new pending request and return its ID and Future."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        request_id = next(self._counter)
        self._requests[request_id] = future
        return request_id, future

    def complete_request(self, *, request_id: RequestId, result: Any) -> None:
        """Complete a pending request with a result."""
        future = self._requests.pop(request_id, None)
        if future is not None and not future.done():
            future.set_result(result)

    def fail_request(self, *, request_id: RequestId, exception: Exception) -> None:
        """Fail a pending request with an exception."""
        future = self._requests.pop(request_id, None)
        if future is not None and not future.done():
            future.set_exception(exception)

    def fail_all(self, *, exception: Exception) -> None:
        """Fail all pending requests with the given exception."""
        while self._requests:
            _, future = self._requests.popitem()
            if not future.done():
                future.set_exception(exception)



================================================
FILE: src/pywebtransport/_adapter/server.py
================================================
"""Internal aioquic protocol adapter and factory for the server-side."""

from __future__ import annotations

import asyncio
from asyncio import BaseTransport
from collections.abc import Callable
from typing import Any

from aioquic.asyncio.server import QuicServer
from aioquic.asyncio.server import serve as quic_serve
from aioquic.quic.connection import QuicConnection

from pywebtransport._adapter.base import WebTransportCommonProtocol
from pywebtransport._adapter.utils import create_quic_configuration
from pywebtransport.config import ServerConfig
from pywebtransport.utils import get_logger

__all__: list[str] = []

logger = get_logger(name=__name__)

type ConnectionCreator = Callable[[WebTransportServerProtocol, BaseTransport], None]


class WebTransportServerProtocol(WebTransportCommonProtocol):
    """Adapt aioquic server events and actions for the WebTransportEngine."""

    _connection_creator: ConnectionCreator
    _server_config: ServerConfig

    def __init__(
        self,
        *,
        quic: QuicConnection,
        server_config: ServerConfig,
        connection_creator: ConnectionCreator,
        stream_handler: Any = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize the server protocol adapter."""
        super().__init__(
            quic=quic,
            config=server_config,
            is_client=False,
            stream_handler=stream_handler,
            loop=loop,
            max_event_queue_size=server_config.max_event_queue_size,
        )
        self._server_config = server_config
        self._connection_creator = connection_creator

    def connection_made(self, transport: BaseTransport) -> None:
        """Handle connection establishment."""
        super().connection_made(transport)
        logger.debug("Adapter connection_made, calling connection creator.")
        self._connection_creator(self, transport)


async def create_server(
    *, host: str, port: int, config: ServerConfig, connection_creator: ConnectionCreator
) -> QuicServer:
    """Start an aioquic server with the given configuration."""
    quic_config = create_quic_configuration(
        alpn_protocols=config.alpn_protocols,
        ca_certs=config.ca_certs,
        certfile=config.certfile,
        congestion_control_algorithm=config.congestion_control_algorithm,
        idle_timeout=config.connection_idle_timeout,
        is_client=False,
        keyfile=config.keyfile,
        max_datagram_size=config.max_datagram_size,
        verify_mode=config.verify_mode,
    )

    def protocol_factory(quic: QuicConnection, stream_handler: Any = None, **kwargs: Any) -> WebTransportServerProtocol:
        return WebTransportServerProtocol(
            quic=quic, server_config=config, connection_creator=connection_creator, stream_handler=stream_handler
        )

    return await quic_serve(host=host, port=port, configuration=quic_config, create_protocol=protocol_factory)



================================================
FILE: src/pywebtransport/_adapter/utils.py
================================================
"""Utilities specific to the adapter layer."""

from __future__ import annotations

from typing import Any

from aioquic.quic.configuration import QuicConfiguration

__all__: list[str] = []


def create_quic_configuration(
    *,
    alpn_protocols: list[str],
    ca_certs: str | None = None,
    certfile: str | None = None,
    congestion_control_algorithm: str,
    idle_timeout: float,
    is_client: bool,
    keyfile: str | None = None,
    max_datagram_size: int,
    server_name: str | None = None,
    verify_mode: Any = None,
) -> QuicConfiguration:
    """Create a QUIC configuration from specific parameters."""
    config = QuicConfiguration(
        alpn_protocols=alpn_protocols,
        cafile=ca_certs,
        congestion_control_algorithm=congestion_control_algorithm,
        idle_timeout=idle_timeout,
        is_client=is_client,
        max_datagram_frame_size=max_datagram_size,
        server_name=server_name,
        verify_mode=verify_mode,
    )

    if certfile is not None and keyfile is not None:
        config.load_cert_chain(certfile=certfile, keyfile=keyfile)

    return config



================================================
FILE: src/pywebtransport/_protocol/__init__.py
================================================
"""Low-level implementation of the WebTransport over H3 protocol."""

__all__: list[str] = []



================================================
FILE: src/pywebtransport/_protocol/events.py
================================================
"""Internal events, commands, and effects for the protocol engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pywebtransport.types import Buffer, ErrorCode, EventType, Headers, RequestId, SessionId, StreamId

__all__: list[str] = []


@dataclass(kw_only=True, frozen=True, slots=True)
class ProtocolEvent:
    """Base class for all events processed by the _WebTransportEngine."""


@dataclass(kw_only=True, frozen=True, slots=True)
class InternalBindH3Session(ProtocolEvent):
    """Internal command to bind a created H3 session to the state."""

    request_id: RequestId
    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class InternalBindQuicStream(ProtocolEvent):
    """Internal command to bind a created QUIC stream to the state."""

    request_id: RequestId
    stream_id: StreamId
    session_id: SessionId
    is_unidirectional: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class InternalCleanupEarlyEvents(ProtocolEvent):
    """Internal command signaling the engine to clean up the early event buffer."""


@dataclass(kw_only=True, frozen=True, slots=True)
class InternalCleanupResources(ProtocolEvent):
    """Internal command signaling the engine to garbage collect closed resources."""


@dataclass(kw_only=True, frozen=True, slots=True)
class InternalFailH3Session(ProtocolEvent):
    """Internal command to handle a failed H3 session creation attempt."""

    request_id: RequestId
    exception: Exception


@dataclass(kw_only=True, frozen=True, slots=True)
class InternalFailQuicStream(ProtocolEvent):
    """Internal command to handle a failed QUIC stream creation attempt."""

    request_id: RequestId
    session_id: SessionId
    is_unidirectional: bool
    exception: Exception


@dataclass(kw_only=True, frozen=True, slots=True)
class InternalReturnStreamData(ProtocolEvent):
    """Internal command to return unconsumed data to a stream buffer."""

    stream_id: StreamId
    data: Buffer


@dataclass(kw_only=True, frozen=True, slots=True)
class TransportConnectionTerminated(ProtocolEvent):
    """Event indicating the underlying QUIC connection was terminated."""

    error_code: ErrorCode
    reason_phrase: str


@dataclass(kw_only=True, frozen=True, slots=True)
class TransportDatagramFrameReceived(ProtocolEvent):
    """Event for a raw datagram frame received from QUIC."""

    data: Buffer


@dataclass(kw_only=True, frozen=True, slots=True)
class TransportHandshakeCompleted(ProtocolEvent):
    """Event signaling QUIC handshake completion is processed."""


@dataclass(kw_only=True, frozen=True, slots=True)
class TransportQuicParametersReceived(ProtocolEvent):
    """Event signaling peer's QUIC transport parameters are received."""

    remote_max_datagram_frame_size: int


@dataclass(kw_only=True, frozen=True, slots=True)
class TransportQuicTimerFired(ProtocolEvent):
    """Event signaling the transport timer has fired."""


@dataclass(kw_only=True, frozen=True, slots=True)
class TransportStreamDataReceived(ProtocolEvent):
    """Event for raw stream data received from QUIC."""

    data: Buffer
    end_stream: bool
    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class TransportStreamReset(ProtocolEvent):
    """Event for a stream reset received from QUIC."""

    error_code: ErrorCode
    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class H3Event(ProtocolEvent):
    """Base class for all H3 protocol engine semantic events."""


@dataclass(kw_only=True, frozen=True, slots=True)
class CapsuleReceived(H3Event):
    """Represent an HTTP Capsule received on a stream."""

    capsule_data: Buffer
    capsule_type: int
    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class ConnectStreamClosed(H3Event):
    """H3 event signaling the CONNECT stream was cleanly closed."""

    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class DatagramReceived(H3Event):
    """Represent a WebTransport datagram received."""

    data: Buffer
    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class GoawayReceived(H3Event):
    """Represent an H3 GOAWAY frame received on the control stream."""


@dataclass(kw_only=True, frozen=True, slots=True)
class HeadersReceived(H3Event):
    """Represent a HEADERS frame received on a stream."""

    headers: Headers
    stream_id: StreamId
    stream_ended: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class SettingsReceived(H3Event):
    """Represent an H3 SETTINGS frame received and parsed."""

    settings: dict[int, int]


@dataclass(kw_only=True, frozen=True, slots=True)
class WebTransportStreamDataReceived(H3Event):
    """Represent semantic data received on an established WebTransport stream."""

    data: Buffer
    session_id: SessionId
    stream_id: StreamId
    stream_ended: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class UserEvent[T](ProtocolEvent):
    """Base class for commands originating from the user-facing API."""

    request_id: RequestId


@dataclass(kw_only=True, frozen=True, slots=True)
class ConnectionClose(UserEvent[None]):
    """User or internal command to close the entire connection."""

    error_code: ErrorCode
    reason: str | None


@dataclass(kw_only=True, frozen=True, slots=True)
class UserAcceptSession(UserEvent[None]):
    """User command to accept a pending session."""

    session_id: SessionId


@dataclass(kw_only=True, frozen=True, slots=True)
class UserCloseSession(UserEvent[None]):
    """User command to close an active session."""

    session_id: SessionId
    error_code: ErrorCode
    reason: str | None


@dataclass(kw_only=True, frozen=True, slots=True)
class UserConnectionGracefulClose(UserEvent[None]):
    """User command to gracefully close the connection."""


@dataclass(kw_only=True, frozen=True, slots=True)
class UserCreateSession(UserEvent[SessionId]):
    """User command to create a new WebTransport session."""

    path: str
    headers: Headers


@dataclass(kw_only=True, frozen=True, slots=True)
class UserCreateStream(UserEvent[StreamId]):
    """User command to create a new stream."""

    session_id: SessionId
    is_unidirectional: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class UserGetConnectionDiagnostics(UserEvent[dict[str, Any]]):
    """User command to get connection diagnostics."""


@dataclass(kw_only=True, frozen=True, slots=True)
class UserGetSessionDiagnostics(UserEvent[dict[str, Any]]):
    """User command to get session diagnostics."""

    session_id: SessionId


@dataclass(kw_only=True, frozen=True, slots=True)
class UserGetStreamDiagnostics(UserEvent[dict[str, Any]]):
    """User command to get stream diagnostics."""

    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class UserGrantDataCredit(UserEvent[None]):
    """User command to manually grant data credit."""

    session_id: SessionId
    max_data: int


@dataclass(kw_only=True, frozen=True, slots=True)
class UserGrantStreamsCredit(UserEvent[None]):
    """User command to manually grant stream credit."""

    session_id: SessionId
    max_streams: int
    is_unidirectional: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class UserRejectSession(UserEvent[None]):
    """User command to reject a pending session."""

    session_id: SessionId
    status_code: int


@dataclass(kw_only=True, frozen=True, slots=True)
class UserResetStream(UserEvent[None]):
    """User command to reset the sending side of a stream."""

    stream_id: StreamId
    error_code: ErrorCode


@dataclass(kw_only=True, frozen=True, slots=True)
class UserSendDatagram(UserEvent[None]):
    """User command to send a datagram."""

    session_id: SessionId
    data: Buffer | list[Buffer]


@dataclass(kw_only=True, frozen=True, slots=True)
class UserSendStreamData(UserEvent[None]):
    """User command to send data on a stream."""

    stream_id: StreamId
    data: Buffer
    end_stream: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class UserStopStream(UserEvent[None]):
    """User command to stop the receiving side of a stream."""

    stream_id: StreamId
    error_code: ErrorCode


@dataclass(kw_only=True, frozen=True, slots=True)
class UserStreamRead(UserEvent[bytes]):
    """User command to read data from a stream."""

    stream_id: StreamId
    max_bytes: int | None


@dataclass(kw_only=True, frozen=True, slots=True)
class Effect:
    """Base class for all side effects returned by the state machine."""


@dataclass(kw_only=True, frozen=True, slots=True)
class CleanupH3Stream(Effect):
    """Effect instructing Engine to cleanup H3-level stream state."""

    stream_id: StreamId


@dataclass(kw_only=True, frozen=True, slots=True)
class CloseQuicConnection(Effect):
    """Effect to close the entire QUIC connection."""

    error_code: ErrorCode
    reason: str | None


@dataclass(kw_only=True, frozen=True, slots=True)
class CreateH3Session(Effect):
    """Effect instructing Engine to initiate H3 session creation."""

    request_id: RequestId
    path: str
    headers: Headers


@dataclass(kw_only=True, frozen=True, slots=True)
class CreateQuicStream(Effect):
    """Effect instructing Adapter to create a new QUIC stream."""

    request_id: RequestId
    session_id: SessionId
    is_unidirectional: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class EmitConnectionEvent(Effect):
    """Effect to emit an event on the WebTransportConnection."""

    event_type: EventType
    data: dict[str, Any]


@dataclass(kw_only=True, frozen=True, slots=True)
class EmitSessionEvent(Effect):
    """Effect to emit an event on the WebTransportSession."""

    session_id: SessionId
    event_type: EventType
    data: dict[str, Any]


@dataclass(kw_only=True, frozen=True, slots=True)
class EmitStreamEvent(Effect):
    """Effect to emit an event on the WebTransportStream."""

    stream_id: StreamId
    event_type: EventType
    data: dict[str, Any]


@dataclass(kw_only=True, frozen=True, slots=True)
class LogH3Frame(Effect):
    """Effect instructing Adapter to log an H3-level frame."""

    category: str
    event: str
    data: dict[str, Any]


@dataclass(kw_only=True, frozen=True, slots=True)
class NotifyRequestDone(Effect):
    """Effect to notify that a user request has completed successfully."""

    request_id: RequestId
    result: Any


@dataclass(kw_only=True, frozen=True, slots=True)
class NotifyRequestFailed(Effect):
    """Effect to notify that a user request has failed."""

    request_id: RequestId
    exception: Exception


@dataclass(kw_only=True, frozen=True, slots=True)
class ProcessProtocolEvent(Effect):
    """Effect instructing the Adapter to re-process a protocol event."""

    event: ProtocolEvent


@dataclass(kw_only=True, frozen=True, slots=True)
class RescheduleQuicTimer(Effect):
    """Effect instructing the Adapter to schedule the next QUIC timer."""


@dataclass(kw_only=True, frozen=True, slots=True)
class ResetQuicStream(Effect):
    """Effect to reset the sending side of a QUIC stream."""

    stream_id: StreamId
    error_code: ErrorCode


@dataclass(kw_only=True, frozen=True, slots=True)
class SendH3Capsule(Effect):
    """Effect instructing Engine to encode and send an H3 Capsule."""

    stream_id: StreamId
    capsule_type: int
    capsule_data: Buffer
    end_stream: bool = False


@dataclass(kw_only=True, frozen=True, slots=True)
class SendH3Datagram(Effect):
    """Effect instructing Engine to encode and send an H3 Datagram."""

    stream_id: StreamId
    data: Buffer | list[Buffer]


@dataclass(kw_only=True, frozen=True, slots=True)
class SendH3Goaway(Effect):
    """Effect instructing Engine to encode and send an H3 GOAWAY frame."""


@dataclass(kw_only=True, frozen=True, slots=True)
class SendH3Headers(Effect):
    """Effect instructing Engine to send simple H3 status headers."""

    stream_id: StreamId
    status: int
    end_stream: bool = True


@dataclass(kw_only=True, frozen=True, slots=True)
class SendQuicData(Effect):
    """Effect to send data on a QUIC stream."""

    stream_id: StreamId
    data: Buffer
    end_stream: bool = False


@dataclass(kw_only=True, frozen=True, slots=True)
class SendQuicDatagram(Effect):
    """Effect to send a QUIC datagram frame."""

    data: Buffer | list[Buffer]


@dataclass(kw_only=True, frozen=True, slots=True)
class StopQuicStream(Effect):
    """Effect to stop the receiving side of a QUIC stream."""

    stream_id: StreamId
    error_code: ErrorCode


@dataclass(kw_only=True, frozen=True, slots=True)
class TriggerQuicTimer(Effect):
    """Effect instructing the Adapter to handle the QUIC timer."""



================================================
FILE: src/pywebtransport/client/__init__.py
================================================
"""Client-side interface for the WebTransport protocol."""

from .client import ClientDiagnostics, ClientStats, WebTransportClient
from .fleet import ClientFleet
from .reconnecting import ReconnectingClient

__all__: list[str] = [
    "ClientDiagnostics",
    "ClientFleet",
    "ClientStats",
    "ReconnectingClient",
    "WebTransportClient",
]



================================================
FILE: src/pywebtransport/client/client.py
================================================
"""Client-side entry point for WebTransport connections."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import asdict, dataclass, field
from types import TracebackType
from typing import Any, Self

from pywebtransport.client.utils import normalize_headers, parse_webtransport_url
from pywebtransport.config import ClientConfig
from pywebtransport.connection import WebTransportConnection
from pywebtransport.events import EventEmitter
from pywebtransport.exceptions import ClientError, ConnectionError, TimeoutError
from pywebtransport.manager.connection import ConnectionManager
from pywebtransport.session import WebTransportSession
from pywebtransport.types import URL, ConnectionState, EventType, Headers
from pywebtransport.utils import format_duration, get_logger, get_timestamp, merge_headers
from pywebtransport.version import __version__

__all__: list[str] = ["ClientDiagnostics", "ClientStats", "WebTransportClient"]

logger = get_logger(name=__name__)


@dataclass(frozen=True, kw_only=True)
class ClientDiagnostics:
    """An immutable snapshot of the client's health and statistics."""

    stats: ClientStats
    connection_states: dict[ConnectionState, int]

    @property
    def issues(self) -> list[str]:
        """Get a list of potential issues based on current diagnostics."""
        issues: list[str] = []
        stats_dict = self.stats.to_dict()

        connections_attempted = stats_dict.get("connections_attempted", 0)
        success_rate = stats_dict.get("success_rate", 1.0)
        if connections_attempted > 10 and success_rate < 0.9:
            issues.append(f"Low connection success rate: {success_rate:.2%}")

        avg_connect_time = stats_dict.get("avg_connect_time", 0.0)
        if avg_connect_time > 5.0:
            issues.append(f"Slow average connection time: {avg_connect_time:.2f}s")

        return issues


@dataclass(kw_only=True)
class ClientStats:
    """Stores client-wide connection statistics."""

    created_at: float = field(default_factory=get_timestamp)
    connections_attempted: int = 0
    connections_successful: int = 0
    connections_failed: int = 0
    total_connect_time: float = 0.0
    min_connect_time: float = float("inf")
    max_connect_time: float = 0.0

    @property
    def avg_connect_time(self) -> float:
        """Get the average connection time."""
        if self.connections_successful == 0:
            return 0.0

        return self.total_connect_time / self.connections_successful

    @property
    def success_rate(self) -> float:
        """Get the connection success rate."""
        if self.connections_attempted == 0:
            return 1.0

        return self.connections_successful / self.connections_attempted

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to a dictionary."""
        data = asdict(obj=self)
        data["avg_connect_time"] = self.avg_connect_time
        data["success_rate"] = self.success_rate
        data["uptime"] = get_timestamp() - self.created_at
        if data["min_connect_time"] == float("inf"):
            data["min_connect_time"] = 0.0
        return data


class WebTransportClient(EventEmitter):
    """A client for establishing WebTransport connections and sessions."""

    def __init__(self, *, config: ClientConfig | None = None) -> None:
        """Initialize the WebTransport client."""
        self._config = config if config is not None else ClientConfig()
        super().__init__(
            max_queue_size=self._config.max_event_queue_size,
            max_listeners=self._config.max_event_listeners,
            max_history=self._config.max_event_history_size,
        )
        self._connection_manager = ConnectionManager(max_connections=self._config.max_connections)
        self._default_headers: Headers = []
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None
        self._stats = ClientStats()

        logger.info("WebTransport client initialized")

    @property
    def config(self) -> ClientConfig:
        """Get the client's configuration object."""
        return self._config

    @property
    def is_closed(self) -> bool:
        """Check if the client is closed."""
        return self._closed

    async def __aenter__(self) -> Self:
        """Enter the async context for the client."""
        await self._connection_manager.__aenter__()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context and close the client."""
        await self.close()

    async def close(self) -> None:
        """Close the client and all underlying connections."""
        if self._close_task is not None and not self._close_task.done():
            await self._close_task
            return

        if self._closed:
            return

        self._close_task = asyncio.create_task(coro=self._close_implementation())
        await self._close_task

    async def connect(
        self, *, url: URL, timeout: float | None = None, headers: Headers | None = None
    ) -> WebTransportSession:
        """Connect to a WebTransport server and return a session."""
        if self._closed:
            raise ClientError(message="Client is closed")

        host, port, path = parse_webtransport_url(url=url)
        connect_timeout = timeout if timeout is not None else self._config.connect_timeout
        logger.info("Connecting to %s:%s%s", host, port, path)
        self._stats.connections_attempted += 1

        connection: WebTransportConnection | None = None
        success = False
        start_time = get_timestamp()

        try:
            async with asyncio.timeout(delay=connect_timeout):
                merged_headers = merge_headers(base=self._default_headers, update=headers)
                normalized_headers = normalize_headers(headers=merged_headers)

                has_ua = False
                if isinstance(normalized_headers, dict):
                    has_ua = "user-agent" in normalized_headers
                else:
                    has_ua = any(key == "user-agent" for key, _ in normalized_headers)

                if not has_ua:
                    default_ua = (
                        self._config.user_agent
                        if self._config.user_agent is not None
                        else f"PyWebTransport/{__version__}"
                    )
                    if isinstance(normalized_headers, dict):
                        normalized_headers["user-agent"] = default_ua
                    else:
                        normalized_headers.append(("user-agent", default_ua))

                conn_config = self._config.update(headers=normalized_headers)

                connection = await WebTransportConnection.connect(
                    host=host, port=port, config=conn_config, loop=asyncio.get_running_loop()
                )

                if connection.state != ConnectionState.CONNECTED:
                    logger.debug("Waiting for connection establishment events...")
                    await connection.events.wait_for(
                        event_type=[
                            EventType.CONNECTION_ESTABLISHED,
                            EventType.CONNECTION_FAILED,
                            EventType.CONNECTION_CLOSED,
                        ]
                    )

                if connection.state != ConnectionState.CONNECTED:
                    raise ConnectionError(message=f"Connection failed state={connection.state}")

                await self._connection_manager.add_connection(connection=connection)

                logger.debug("Initiating session creation...")
                session = await connection.create_session(path=path, headers=normalized_headers)
                logger.debug("Session creation successful: %s", session.session_id)

                elapsed = get_timestamp() - start_time
                self._update_success_stats(connect_time=elapsed)
                logger.info("Session established to %s in %s", url, format_duration(seconds=elapsed))
                success = True
                return session

        except asyncio.TimeoutError as e:
            self._stats.connections_failed += 1
            stage = (
                "session negotiation"
                if connection is not None and connection.is_connected
                else "QUIC connection establishment"
            )
            logger.error(
                "Connection timeout to %s during %s after %s", url, stage, format_duration(seconds=connect_timeout)
            )
            raise TimeoutError(message=f"Connection timeout to {url} during {stage}") from e
        except ConnectionRefusedError as e:
            self._stats.connections_failed += 1
            logger.error("Connection refused by %s:%d", host, port)
            raise ConnectionError(message=f"Connection refused by {host}:{port}") from e
        except Exception as e:
            self._stats.connections_failed += 1
            logger.error("Failed to connect to %s: %s", url, e, exc_info=True)
            if "certificate verify failed" in str(e):
                raise ConnectionError(message=f"Certificate verification failed for {url}: {e}") from e
            raise ClientError(message=f"Failed to connect to {url}: {e}") from e
        finally:
            if not success and connection is not None and not connection.is_closed:
                await connection.close()

    async def diagnostics(self) -> ClientDiagnostics:
        """Get a snapshot of the client's diagnostics and statistics."""
        connections = await self._connection_manager.get_all_resources()
        state_counts = Counter(conn.state for conn in connections)

        return ClientDiagnostics(stats=self._stats, connection_states=dict(state_counts))

    def set_default_headers(self, *, headers: Headers) -> None:
        """Set default headers for all subsequent connections."""
        self._default_headers = merge_headers(base=[], update=headers)

    async def _close_implementation(self) -> None:
        """Internal implementation of client closure."""
        logger.info("Closing WebTransport client...")
        self._closed = True
        await self._connection_manager.shutdown()
        logger.info("WebTransport client closed.")

    def _update_success_stats(self, *, connect_time: float) -> None:
        """Update connection statistics on a successful connection."""
        self._stats.connections_successful += 1
        self._stats.total_connect_time += connect_time
        self._stats.min_connect_time = min(self._stats.min_connect_time, connect_time)
        self._stats.max_connect_time = max(self._stats.max_connect_time, connect_time)

    def __str__(self) -> str:
        """Format a concise summary of client information for logging."""
        status = "closed" if self.is_closed else "open"
        conn_count = len(self._connection_manager)
        return f"WebTransportClient(status={status}, connections={conn_count})"



================================================
FILE: src/pywebtransport/client/fleet.py
================================================
"""High-level client for managing a fleet of client instances."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Self

from pywebtransport.client.client import WebTransportClient
from pywebtransport.exceptions import ClientError
from pywebtransport.session import WebTransportSession
from pywebtransport.types import URL
from pywebtransport.utils import get_logger

__all__: list[str] = ["ClientFleet"]

logger = get_logger(name=__name__)

DEFAULT_MAX_CONCURRENT_HANDSHAKES: int = 50


class ClientFleet:
    """Manages a fleet of WebTransportClient instances to distribute load."""

    def __init__(
        self, *, clients: list[WebTransportClient], max_concurrent_handshakes: int = DEFAULT_MAX_CONCURRENT_HANDSHAKES
    ) -> None:
        """Initialize the client fleet."""
        if not clients:
            raise ValueError("ClientFleet requires at least one client instance.")

        self._clients = clients
        self._current_index = 0
        self._active = False
        self._connect_sem = asyncio.Semaphore(max_concurrent_handshakes)

    async def __aenter__(self) -> Self:
        """Enter the async context and activate all clients in the fleet."""
        self._active = True
        successful_clients: list[WebTransportClient] = []

        async def _startup_wrapper(client: WebTransportClient) -> None:
            await client.__aenter__()
            successful_clients.append(client)

        try:
            async with asyncio.TaskGroup() as tg:
                for client in self._clients:
                    tg.create_task(coro=_startup_wrapper(client))
        except* Exception as eg:
            logger.error("Failed to activate clients in fleet: %s", eg.exceptions, exc_info=eg)
            self._active = False

            if successful_clients:
                try:
                    async with asyncio.TaskGroup() as cleanup_tg:
                        for client in successful_clients:
                            cleanup_tg.create_task(coro=client.__aexit__(None, None, None))
                except* Exception as cleanup_eg:
                    logger.error(
                        "Error during fleet cleanup after activation failure: %s",
                        cleanup_eg.exceptions,
                        exc_info=cleanup_eg,
                    )
            raise eg

        logger.info("ClientFleet activated with %d clients", len(self._clients))
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context and close all clients in the fleet."""
        self._active = False
        try:
            async with asyncio.TaskGroup() as tg:
                for client in self._clients:
                    tg.create_task(coro=client.__aexit__(exc_type, exc_val, exc_tb))
        except* Exception as eg:
            logger.error("Error closing clients in fleet: %s", eg.exceptions, exc_info=eg)

    async def connect_all(self, *, url: URL) -> list[WebTransportSession]:
        """Connect all clients in the fleet to the specified URL."""
        self._check_active()

        async def safe_connect(client: WebTransportClient) -> WebTransportSession | None:
            try:
                async with self._connect_sem:
                    return await client.connect(url=url)
            except Exception as e:
                logger.warning("Client failed to connect: %s", e)
                return None

        tasks: list[asyncio.Task[WebTransportSession | None]] = []
        async with asyncio.TaskGroup() as tg:
            for client in self._clients:
                tasks.append(tg.create_task(coro=safe_connect(client)))

        sessions: list[WebTransportSession] = []
        for task in tasks:
            result = task.result()
            if result is not None:
                sessions.append(result)

        return sessions

    def get_client(self) -> WebTransportClient:
        """Get an active client from the fleet using a round-robin strategy."""
        self._check_active()

        client = self._clients[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._clients)
        return client

    def get_client_count(self) -> int:
        """Get the number of clients currently in the fleet."""
        return len(self._clients)

    def _check_active(self) -> None:
        """Check if the fleet is active."""
        if not self._active:
            raise ClientError(
                message=(
                    "ClientFleet has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )



================================================
FILE: src/pywebtransport/client/reconnecting.py
================================================
"""Client wrapper for automatic reconnection logic."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Self

from pywebtransport.client.client import WebTransportClient
from pywebtransport.events import EventEmitter
from pywebtransport.exceptions import ClientError, ConnectionError, TimeoutError
from pywebtransport.session import WebTransportSession
from pywebtransport.types import URL, EventType, SessionState
from pywebtransport.utils import get_logger

__all__: list[str] = ["ReconnectingClient"]

logger = get_logger(name=__name__)


class ReconnectingClient(EventEmitter):
    """A client that automatically reconnects based on the provided configuration."""

    def __init__(self, *, url: URL, client: WebTransportClient) -> None:
        """Initialize the reconnecting client."""
        self._config = client.config
        super().__init__(
            max_queue_size=self._config.max_event_queue_size,
            max_listeners=self._config.max_event_listeners,
            max_history=self._config.max_event_history_size,
        )
        self._url = url
        self._client = client
        self._session: WebTransportSession | None = None
        self._tg: asyncio.TaskGroup | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._closed = False
        self._is_initialized = False
        self._connected_event = asyncio.Event()
        self._crashed_exception: BaseException | None = None

    @property
    def is_connected(self) -> bool:
        """Check if the client is currently connected with a ready session."""
        return (
            self._session is not None
            and self._session.state == SessionState.CONNECTED
            and self._connected_event.is_set()
        )

    async def __aenter__(self) -> Self:
        """Enter the async context and start the reconnect loop."""
        if self._closed:
            raise ClientError(message="Client is already closed")
        if self._is_initialized:
            return self

        self._tg = asyncio.TaskGroup()
        await self._tg.__aenter__()

        self._reconnect_task = self._tg.create_task(coro=self._reconnect_loop())
        self._is_initialized = True
        logger.info("ReconnectingClient started for URL: %s", self._url)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context and ensure the client is closed."""
        await self.close()
        if self._tg is not None:
            await self._tg.__aexit__(exc_type, exc_val, exc_tb)

    async def close(self) -> None:
        """Close the reconnecting client and all its resources."""
        if self._closed:
            return

        logger.info("Closing reconnecting client")
        self._closed = True
        self._connected_event.set()

        if self._reconnect_task is not None and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        if self._session is not None:
            try:
                await self._session.close()
            except Exception as e:
                logger.warning("Error closing session: %s", e)
            finally:
                self._session = None

        logger.info("Reconnecting client closed")

    async def get_session(self, *, wait_timeout: float = 5.0) -> WebTransportSession:
        """Get the current session and wait for a connection if necessary."""
        if self._closed:
            raise ClientError(message="Client is closed")

        if self._crashed_exception is not None:
            raise ClientError(message="Background reconnection task crashed") from self._crashed_exception

        if self._tg is None:
            raise ClientError(
                message=(
                    "ReconnectingClient has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        async with asyncio.timeout(delay=wait_timeout):
            while True:
                await self._connected_event.wait()

                if self._closed:
                    raise ClientError(message="Client closed while waiting for session")

                if self._crashed_exception is not None:
                    raise ClientError(message="Background task crashed") from self._crashed_exception

                session = self._session
                if session is not None and not session.is_closed:
                    return session

                if self._reconnect_task is not None and self._reconnect_task.done():
                    if self._reconnect_task.cancelled():
                        raise ClientError(message="Reconnection task cancelled.")
                    if exc := self._reconnect_task.exception():
                        raise ClientError(message=f"Reconnection task failed: {exc}") from exc
                    raise ClientError(message="Reconnection task finished unexpectedly.")

                self._connected_event.clear()

    async def _reconnect_loop(self) -> None:
        """Manage the connection lifecycle with an exponential backoff retry strategy."""
        retry_count = 0
        max_retries = self._config.max_connection_retries if self._config.max_connection_retries >= 0 else float("inf")
        initial_delay = self._config.retry_delay
        backoff_factor = self._config.retry_backoff
        max_delay = self._config.max_retry_delay

        try:
            while not self._closed:
                try:
                    self._session = await self._client.connect(url=self._url)
                    logger.info("Successfully connected to %s", self._url)

                    self._connected_event.set()
                    await self.emit(
                        event_type=EventType.CONNECTION_ESTABLISHED,
                        data={"session": self._session, "attempt": retry_count + 1},
                    )
                    retry_count = 0

                    if self._session.state != SessionState.CLOSED:
                        await self._session.events.wait_for(event_type=EventType.SESSION_CLOSED)

                    self._connected_event.clear()

                    if not self._closed:
                        logger.warning("Connection to %s lost, attempting to reconnect...", self._url)
                        await self.emit(event_type=EventType.CONNECTION_LOST, data={"url": self._url})

                except (ConnectionError, TimeoutError, ClientError) as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error("Max retries (%d) exceeded for %s", max_retries, self._url)
                        await self.emit(
                            event_type=EventType.CONNECTION_FAILED,
                            data={"reason": "max_retries_exceeded", "last_error": str(e)},
                        )
                        break

                    delay = min(initial_delay * (backoff_factor ** (retry_count - 1)), max_delay)
                    logger.warning(
                        "Connection attempt %d failed for %s, retrying in %.1fs: %s",
                        retry_count,
                        self._url,
                        delay,
                        e,
                        exc_info=True,
                    )
                    await asyncio.sleep(delay=delay)

                finally:
                    if self._session is not None:
                        try:
                            await self._session.close()
                        except Exception as e:
                            logger.debug("Error closing old session during reconnect: %s", e)
                        finally:
                            self._session = None

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._crashed_exception = e
            logger.critical("Reconnection loop crashed: %s", e, exc_info=True)
            self._connected_event.set()
        finally:
            self._connected_event.set()
            logger.info("Reconnection loop finished.")



================================================
FILE: src/pywebtransport/client/utils.py
================================================
"""Shared utility functions for client-side components."""

from __future__ import annotations

import urllib.parse

from pywebtransport.constants import WEBTRANSPORT_DEFAULT_PORT, WEBTRANSPORT_SCHEME
from pywebtransport.types import URL, Headers, URLParts

__all__: list[str] = ["normalize_headers", "parse_webtransport_url"]


def normalize_headers(*, headers: Headers) -> Headers:
    """Normalize header keys to lowercase."""
    if isinstance(headers, dict):
        return {key.lower(): value for key, value in headers.items()}
    return [(key.lower(), value) for key, value in headers]


def parse_webtransport_url(*, url: URL) -> URLParts:
    """Parse a WebTransport URL into its host, port, and path components."""
    parsed = urllib.parse.urlparse(url=url)
    if parsed.scheme != WEBTRANSPORT_SCHEME:
        raise ValueError(f"Unsupported scheme '{parsed.scheme}'. Must be '{WEBTRANSPORT_SCHEME}'")

    if not parsed.hostname:
        raise ValueError("Missing hostname in URL")

    port = parsed.port if parsed.port is not None else WEBTRANSPORT_DEFAULT_PORT

    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += f"?{parsed.query}"

    return (parsed.hostname, port, path)



================================================
FILE: src/pywebtransport/manager/__init__.py
================================================
"""Resource lifecycle managers."""

from .connection import ConnectionManager
from .session import SessionManager

__all__: list[str] = ["ConnectionManager", "SessionManager"]



================================================
FILE: src/pywebtransport/manager/_base.py
================================================
"""Reusable base class for managing event-driven resources."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, ClassVar, Protocol, Self, runtime_checkable

from pywebtransport.events import Event, EventEmitter
from pywebtransport.types import EventType
from pywebtransport.utils import get_logger

__all__: list[str] = []


@runtime_checkable
class ManageableResource(Protocol):
    """Define the protocol for a resource manageable by this class."""

    events: EventEmitter

    @property
    def is_closed(self) -> bool:
        """Check if the resource is currently closed."""
        ...


logger = get_logger(name=__name__)


class BaseResourceManager[ResourceId, ResourceType: ManageableResource](ABC):
    """Manage the lifecycle of concurrent resources abstractly via events."""

    _log: ClassVar[logging.Logger] = logger
    _resource_closed_event_type: ClassVar[EventType]

    def __init__(self, *, resource_name: str, max_resources: int) -> None:
        """Initialize the base resource manager."""
        self._resource_name = resource_name
        self._max_resources = max_resources
        self._lock: asyncio.Lock | None = None
        self._resources: dict[ResourceId, ResourceType] = {}
        self._stats = {"total_created": 0, "total_closed": 0, "current_count": 0, "max_concurrent": 0}
        self._is_shutting_down = False
        self._event_handlers: dict[ResourceId, tuple[EventEmitter, Callable[[Event], Awaitable[None]]]] = {}

    async def __aenter__(self) -> Self:
        """Enter async context and initialize resources."""
        self._lock = asyncio.Lock()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit async context and shut down the manager."""
        await self.shutdown()

    async def shutdown(self) -> None:
        """Shut down the manager and all associated resources."""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        self._log.info("Shutting down %s manager", self._resource_name)

        await self._close_all_resources()
        self._log.info("%s manager shutdown complete", self._resource_name)

    async def add_resource(self, *, resource: ResourceType) -> None:
        """Add a new resource and subscribe to its closure event."""
        if self._lock is None:
            raise RuntimeError(f"{self.__class__.__name__} is not activated. Use 'async with'.")

        if resource.is_closed:
            raise RuntimeError(f"Cannot add closed {self._resource_name}")

        resource_id = self._get_resource_id(resource=resource)
        emitter = resource.events

        async with self._lock:
            if self._is_shutting_down:
                self._log.warning("Attempted to add resource %s during shutdown.", resource_id)
                await self._close_resource(resource=resource)
                raise RuntimeError(f"{self.__class__.__name__} is shutting down")

            if resource.is_closed:
                raise RuntimeError(f"Cannot add closed {self._resource_name}")

            if resource_id in self._resources:
                self._log.debug("Resource %s already managed.", resource_id)
                return

            if 0 < self._max_resources <= len(self._resources):
                self._log.error(
                    "Maximum %s limit (%d) reached. Cannot add %s.",
                    self._resource_name,
                    self._max_resources,
                    resource_id,
                )
                await self._close_resource(resource=resource)
                raise RuntimeError(f"Maximum {self._resource_name} limit reached")

            async def closed_handler_wrapper(event: Event) -> None:
                """Handle resource closure event."""
                event_resource_id: ResourceId | None = None
                if isinstance(event.data, dict):
                    event_resource_id = event.data.get(f"{self._resource_name}_id")

                if event_resource_id is not None and event_resource_id != resource_id:
                    self._log.error(
                        "Resource ID mismatch in close event for %s (Expected %s, Got: %s).",
                        self._resource_name,
                        resource_id,
                        event_resource_id,
                    )

                await self._handle_resource_closed(resource_id=resource_id)

            emitter.once(event_type=self._resource_closed_event_type, handler=closed_handler_wrapper)
            self._event_handlers[resource_id] = (emitter, closed_handler_wrapper)

            if self._check_is_closed(resource=resource):
                try:
                    emitter.off(event_type=self._resource_closed_event_type, handler=closed_handler_wrapper)
                except (ValueError, KeyError):
                    pass
                del self._event_handlers[resource_id]
                raise RuntimeError(f"Cannot add {self._resource_name}: closed during registration")

            self._resources[resource_id] = resource
            self._stats["total_created"] += 1
            self._update_stats_unsafe()

            self._log.debug("Added %s %s (total: %d)", self._resource_name, resource_id, self._stats["current_count"])

    async def get_all_resources(self) -> list[ResourceType]:
        """Retrieve a list of all current resources."""
        if self._lock is None:
            return []
        async with self._lock:
            return list(self._resources.values())

    async def get_resource(self, *, resource_id: ResourceId) -> ResourceType | None:
        """Retrieve a resource by its ID."""
        if self._lock is None:
            return None
        async with self._lock:
            return self._resources.get(resource_id)

    async def get_stats(self) -> dict[str, Any]:
        """Get detailed statistics about the managed resources."""
        if self._lock is None:
            return {}
        async with self._lock:
            stats = self._stats.copy()
            stats["current_count"] = len(self._resources)
            stats["active"] = len(self._resources)
            stats[f"max_{self._resource_name}s"] = self._max_resources
            return stats

    def _check_is_closed(self, *, resource: ResourceType) -> bool:
        """Check if the resource is currently closed."""
        return resource.is_closed

    async def _close_all_resources(self) -> None:
        """Close all currently managed resources."""
        if self._lock is None:
            return

        resources_to_close: list[ResourceType] = []
        async with self._lock:
            if not self._resources:
                return
            resources_to_close = list(self._resources.values())
            self._log.info("Closing %d managed %ss", len(resources_to_close), self._resource_name)

            for _, (emitter, handler) in self._event_handlers.items():
                try:
                    emitter.off(event_type=self._resource_closed_event_type, handler=handler)
                except (ValueError, KeyError):
                    pass
            self._event_handlers.clear()
            self._resources.clear()

        try:
            async with asyncio.TaskGroup() as tg:
                for resource in resources_to_close:
                    tg.create_task(coro=self._close_resource(resource=resource))
        except* Exception as eg:
            self._log.error(
                "Errors occurred while closing managed %ss: %s", self._resource_name, eg.exceptions, exc_info=eg
            )

        async with self._lock:
            self._stats["total_closed"] += len(resources_to_close)
            self._update_stats_unsafe()
        self._log.info("All managed %ss processed for closure.", self._resource_name)

    @abstractmethod
    async def _close_resource(self, *, resource: ResourceType) -> None:
        """Close a single resource."""
        raise NotImplementedError

    @abstractmethod
    def _get_resource_id(self, *, resource: ResourceType) -> ResourceId:
        """Get the unique ID from a resource object."""
        raise NotImplementedError

    async def _handle_resource_closed(self, *, resource_id: ResourceId) -> None:
        """Handle the closure event for a managed resource."""
        if self._lock is None:
            return

        async with self._lock:
            if resource_id in self._event_handlers:
                self._event_handlers.pop(resource_id)

            removed_resource = self._resources.pop(resource_id, None)
            if removed_resource is not None:
                self._stats["total_closed"] += 1
                self._update_stats_unsafe()
                self._log.debug(
                    "Removed closed %s %s (total: %d)", self._resource_name, resource_id, self._stats["current_count"]
                )

    def _update_stats_unsafe(self) -> None:
        """Update internal statistics."""
        current_count = len(self._resources)
        self._stats["current_count"] = current_count
        self._stats["max_concurrent"] = max(self._stats["max_concurrent"], current_count)

    def __len__(self) -> int:
        """Return the current number of managed resources."""
        return len(self._resources)



================================================
FILE: src/pywebtransport/manager/connection.py
================================================
"""Manager for handling numerous concurrent connection lifecycles."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, ClassVar

from pywebtransport.connection import WebTransportConnection
from pywebtransport.manager._base import BaseResourceManager
from pywebtransport.types import ConnectionId, EventType
from pywebtransport.utils import get_logger

__all__: list[str] = ["ConnectionManager"]

logger = get_logger(name=__name__)


class ConnectionManager(BaseResourceManager[ConnectionId, WebTransportConnection]):
    """Manage multiple WebTransport connections using event-driven cleanup."""

    _log = logger
    _resource_closed_event_type: ClassVar[EventType] = EventType.CONNECTION_CLOSED

    def __init__(self, *, max_connections: int) -> None:
        """Initialize the connection manager."""
        super().__init__(resource_name="connection", max_resources=max_connections)
        self._closing_tasks: set[asyncio.Task[None]] = set()

    async def shutdown(self) -> None:
        """Shut down the manager and ensure all closing tasks complete."""
        await super().shutdown()

        if self._closing_tasks:
            self._log.debug("Waiting for %d closing tasks to complete", len(self._closing_tasks))
            await asyncio.gather(*self._closing_tasks, return_exceptions=True)

    async def add_connection(self, *, connection: WebTransportConnection) -> ConnectionId:
        """Add a new connection and subscribe to its closure event."""
        await super().add_resource(resource=connection)
        return connection.connection_id

    async def remove_connection(self, *, connection_id: ConnectionId) -> WebTransportConnection | None:
        """Manually remove a connection from management."""
        if self._lock is None:
            return None

        removed_connection: WebTransportConnection | None = None
        async with self._lock:
            if connection_id in self._event_handlers:
                self._event_handlers.pop(connection_id)

            removed_connection = self._resources.pop(connection_id, None)
            if removed_connection is not None:
                self._stats["total_closed"] += 1
                self._update_stats_unsafe()
                self._schedule_close(connection=removed_connection)
                self._log.debug(
                    "Manually removed connection %s (total: %d)", connection_id, self._stats["current_count"]
                )

        return removed_connection

    async def get_stats(self) -> dict[str, Any]:
        """Get detailed statistics about the managed connections."""
        stats = await super().get_stats()
        if self._lock is not None:
            async with self._lock:
                states: defaultdict[str, int] = defaultdict(int)
                for conn in self._resources.values():
                    states[conn.state.value] += 1
                stats["states"] = dict(states)
        return stats

    async def _close_resource(self, *, resource: WebTransportConnection) -> None:
        """Close a single connection resource."""
        if not resource.is_closed:
            await resource.close()

    def _get_resource_id(self, *, resource: WebTransportConnection) -> ConnectionId:
        """Get the unique ID from a connection object."""
        return resource.connection_id

    async def _handle_resource_closed(self, *, resource_id: ConnectionId) -> None:
        """Handle the closure event for a managed resource."""
        if self._lock is None:
            return

        conn: WebTransportConnection | None = None
        async with self._lock:
            if resource_id in self._event_handlers:
                self._event_handlers.pop(resource_id)

            conn = self._resources.pop(resource_id, None)
            if conn is not None:
                self._stats["total_closed"] += 1
                self._update_stats_unsafe()
                self._schedule_close(connection=conn)
                self._log.debug("Passive cleanup: Connection %s removed and close scheduled.", resource_id)

    def _schedule_close(self, *, connection: WebTransportConnection) -> None:
        """Schedule an asynchronous close task for a connection."""
        if connection.is_closed:
            return

        task = asyncio.create_task(coro=connection.close())
        self._closing_tasks.add(task)
        task.add_done_callback(self._closing_tasks.discard)



================================================
FILE: src/pywebtransport/manager/session.py
================================================
"""Manager for concurrent session lifecycles."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, ClassVar

from pywebtransport.constants import ErrorCodes
from pywebtransport.manager._base import BaseResourceManager
from pywebtransport.session import WebTransportSession
from pywebtransport.types import EventType, SessionId, SessionState
from pywebtransport.utils import get_logger

__all__: list[str] = ["SessionManager"]

logger = get_logger(name=__name__)


class SessionManager(BaseResourceManager[SessionId, WebTransportSession]):
    """Manage multiple WebTransport sessions using event-driven cleanup."""

    _log = logger
    _resource_closed_event_type: ClassVar[EventType] = EventType.SESSION_CLOSED

    def __init__(self, *, max_sessions: int) -> None:
        """Initialize the session manager."""
        super().__init__(resource_name="session", max_resources=max_sessions)

    async def add_session(self, *, session: WebTransportSession) -> SessionId:
        """Add a new session and subscribe to its closure event."""
        await super().add_resource(resource=session)
        return session.session_id

    async def remove_session(self, *, session_id: SessionId) -> WebTransportSession | None:
        """Manually remove a session from management."""
        if self._lock is None:
            return None

        removed_session: WebTransportSession | None = None
        async with self._lock:
            if session_id in self._event_handlers:
                emitter, handler = self._event_handlers.pop(session_id)
                try:
                    emitter.off(event_type=self._resource_closed_event_type, handler=handler)
                except (ValueError, KeyError):
                    pass

            removed_session = self._resources.pop(session_id, None)
            if removed_session is not None:
                self._stats["total_closed"] += 1
                self._update_stats_unsafe()
                self._log.debug("Manually removed session %s (total: %d)", session_id, self._stats["current_count"])

        return removed_session

    async def get_sessions_by_state(self, *, state: SessionState) -> list[WebTransportSession]:
        """Retrieve sessions that are in a specific state."""
        if self._lock is None:
            return []
        async with self._lock:
            return [session for session in self._resources.values() if session.state == state]

    async def get_stats(self) -> dict[str, Any]:
        """Get detailed statistics about the managed sessions."""
        stats = await super().get_stats()
        if self._lock is not None:
            async with self._lock:
                states: defaultdict[str, int] = defaultdict(int)
                for session in self._resources.values():
                    states[session.state.value] += 1
                stats["states"] = dict(states)
        return stats

    async def _close_resource(self, *, resource: WebTransportSession) -> None:
        """Close a single session resource."""
        if not resource.is_closed:
            await resource.close(error_code=ErrorCodes.NO_ERROR, reason="Session manager shutdown")

    def _get_resource_id(self, *, resource: WebTransportSession) -> SessionId:
        """Get the unique ID from a session object."""
        return resource.session_id



================================================
FILE: src/pywebtransport/messaging/__init__.py
================================================
"""High-level structured messaging over streams and datagrams."""

from .datagram import StructuredDatagramTransport
from .stream import StructuredStream

__all__: list[str] = ["StructuredDatagramTransport", "StructuredStream"]



================================================
FILE: src/pywebtransport/messaging/datagram.py
================================================
"""High-level wrapper for structured data over datagrams."""

from __future__ import annotations

import asyncio
import struct
import weakref
from typing import TYPE_CHECKING, Any

from pywebtransport.events import Event
from pywebtransport.exceptions import ConfigurationError, SerializationError, SessionError, TimeoutError
from pywebtransport.types import EventType, Serializer
from pywebtransport.utils import get_logger

if TYPE_CHECKING:
    from pywebtransport.session import WebTransportSession


__all__: list[str] = ["StructuredDatagramTransport"]

logger = get_logger(name=__name__)


class StructuredDatagramTransport:
    """Send and receive structured objects over datagrams."""

    _HEADER_FORMAT = "!H"
    _HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)

    def __init__(self, *, session: WebTransportSession, serializer: Serializer, registry: dict[int, type[Any]]) -> None:
        """Initialize the structured datagram transport."""
        if len(set(registry.values())) != len(registry):
            raise ConfigurationError(message="Types in the structured datagram registry must be unique.")

        self._session = weakref.ref(session)
        self._serializer = serializer
        self._registry = registry
        self._class_to_id = {v: k for k, v in registry.items()}

        self._incoming_obj_queue: asyncio.Queue[Any | object] | None = None
        self._queue_size: int = 0
        self._closed = False
        self._is_initialized = False
        self._sentinel = object()
        self._handler_ref: Any = None

    @property
    def is_closed(self) -> bool:
        """Check if the structured datagram transport is closed."""
        session = self._session()
        return self._closed or session is None or session.is_closed

    async def __aenter__(self) -> StructuredDatagramTransport:
        """Enter the async context manager."""
        self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context manager."""
        await self.close()

    async def close(self) -> None:
        """Close the structured transport and unsubscribe from events."""
        if self._closed:
            return

        self._closed = True
        if self._handler_ref is not None:
            session = self._session()
            if session is not None:
                try:
                    session.events.off(event_type=EventType.DATAGRAM_RECEIVED, handler=self._handler_ref)
                except (ValueError, KeyError):
                    pass
            self._handler_ref = None

        if self._incoming_obj_queue is not None:
            self._incoming_obj_queue.put_nowait(item=self._sentinel)

    def initialize(self, *, queue_size: int = 100) -> None:
        """Initialize the resources for the transport synchronously."""
        if self._is_initialized:
            return

        self._queue_size = queue_size
        self._incoming_obj_queue = asyncio.Queue(maxsize=self._queue_size)

        session = self._session()
        if session is not None:
            if session.is_closed:
                raise SessionError(message="Cannot initialize transport, parent session is closed.")

            weak_self = weakref.ref(self)

            async def handler(event: Event) -> None:
                transport = weak_self()
                if transport is None:
                    return
                await transport._on_datagram_received(event=event)

            self._handler_ref = handler
            session.events.on(event_type=EventType.DATAGRAM_RECEIVED, handler=handler)
        else:
            raise SessionError(message="Cannot initialize transport, parent session is already gone.")

        self._is_initialized = True

    async def receive_obj(self, *, timeout: float | None = None) -> Any:
        """Receive and deserialize a Python object from a datagram."""
        if self.is_closed:
            raise SessionError(message="Structured transport is closed.")
        if not self._is_initialized or self._incoming_obj_queue is None:
            raise SessionError(message="Structured transport has not been initialized.")

        try:
            async with asyncio.timeout(delay=timeout):
                obj = await self._incoming_obj_queue.get()
            if obj is self._sentinel:
                raise SessionError(message="Structured transport was closed while receiving.")
            return obj
        except asyncio.TimeoutError:
            raise TimeoutError(message=f"Receive object timeout after {timeout}s") from None

    async def send_obj(self, *, obj: Any) -> None:
        """Serialize and send a Python object as a datagram."""
        session = self._session()
        if session is None or session.is_closed:
            raise SessionError(message="Session is closed, cannot send object.")
        if not self._is_initialized:
            raise SessionError(message="Structured transport has not been initialized.")

        obj_type = type(obj)
        type_id = self._class_to_id.get(obj_type)
        if type_id is None:
            raise SerializationError(message=f"Object of type '{obj_type.__name__}' is not registered.")

        header = struct.pack(self._HEADER_FORMAT, type_id)
        payload = self._serializer.serialize(obj=obj)

        await session.send_datagram(data=[header, payload])

    async def _on_datagram_received(self, *, event: Event) -> None:
        """Handle incoming raw datagrams and place them in the object queue."""
        if self._closed or not isinstance(event.data, dict) or self._incoming_obj_queue is None:
            return

        datagram: bytes | None = event.data.get("data")
        if not datagram:
            return

        try:
            view = memoryview(datagram)
            if len(view) < self._HEADER_SIZE:
                return

            header_view = view[: self._HEADER_SIZE]
            payload_view = view[self._HEADER_SIZE :]

            type_id = struct.unpack(self._HEADER_FORMAT, header_view)[0]
            message_class = self._registry.get(type_id)

            if message_class is None:
                raise SerializationError(message=f"Received unknown message type ID: {type_id}")

            obj = self._serializer.deserialize(data=payload_view, obj_type=message_class)

            try:
                self._incoming_obj_queue.put_nowait(item=obj)
            except asyncio.QueueFull:
                session = self._session()
                session_id = session.session_id if session is not None else "unknown"
                logger.warning("Structured datagram queue full for session %s; dropping datagram.", session_id)

        except (struct.error, SerializationError) as e:
            logger.warning("Failed to deserialize structured datagram: %s", e)
        except Exception as e:
            logger.error("Error in datagram receive handler: %s", e, exc_info=True)



================================================
FILE: src/pywebtransport/messaging/stream.py
================================================
"""High-level wrapper for structured data over a reliable stream."""

from __future__ import annotations

import asyncio
import struct
from typing import TYPE_CHECKING, Any

from pywebtransport.constants import ErrorCodes
from pywebtransport.exceptions import ConfigurationError, SerializationError, StreamError
from pywebtransport.types import Serializer

if TYPE_CHECKING:
    from pywebtransport.stream import WebTransportStream


__all__: list[str] = ["StructuredStream"]


class StructuredStream:
    """A high-level wrapper for sending and receiving structured objects."""

    _HEADER_FORMAT = "!HI"
    _HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)

    def __init__(
        self,
        *,
        stream: WebTransportStream,
        serializer: Serializer,
        registry: dict[int, type[Any]],
        max_message_size: int,
    ) -> None:
        """Initialize the structured stream wrapper."""
        if len(set(registry.values())) != len(registry):
            raise ConfigurationError(message="Types in the structured stream registry must be unique.")

        self._stream = stream
        self._serializer = serializer
        self._registry = registry
        self._max_message_size = max_message_size
        self._class_to_id = {v: k for k, v in registry.items()}
        self._write_lock = asyncio.Lock()

    @property
    def is_closed(self) -> bool:
        """Check if the underlying stream is closed."""
        return self._stream.is_closed

    @property
    def stream_id(self) -> int:
        """Get the underlying stream ID."""
        return self._stream.stream_id

    async def close(self) -> None:
        """Close the underlying stream."""
        await self._stream.close()

    async def receive_obj(self) -> Any:
        """Receive and deserialize a Python object from the stream."""
        try:
            header_bytes = await self._stream.readexactly(n=self._HEADER_SIZE)
        except asyncio.IncompleteReadError as e:
            if not e.partial:
                raise StreamError(
                    message="Stream closed cleanly", error_code=ErrorCodes.NO_ERROR, stream_id=self.stream_id
                ) from e
            raise StreamError(
                message="Stream closed while waiting for message header.",
                error_code=ErrorCodes.H3_MESSAGE_ERROR,
                stream_id=self.stream_id,
            ) from e

        type_id, payload_len = struct.unpack(self._HEADER_FORMAT, header_bytes)

        if payload_len > self._max_message_size:
            await self._stream.stop_receiving(error_code=ErrorCodes.APPLICATION_ERROR)
            raise SerializationError(
                message=f"Incoming message size {payload_len} exceeds the configured limit of {self._max_message_size}."
            )

        message_class = self._registry.get(type_id)
        if message_class is None:
            raise SerializationError(message=f"Received unknown message type ID: {type_id}")

        try:
            payload = await self._stream.readexactly(n=payload_len)
        except asyncio.IncompleteReadError as e:
            raise StreamError(
                message=f"Stream closed prematurely while reading payload of size {payload_len} for type ID {type_id}.",
                error_code=ErrorCodes.H3_MESSAGE_ERROR,
                stream_id=self.stream_id,
            ) from e

        return self._serializer.deserialize(data=payload, obj_type=message_class)

    async def send_obj(self, *, obj: Any) -> None:
        """Serialize and send a Python object over the stream."""
        obj_type = type(obj)
        type_id = self._class_to_id.get(obj_type)
        if type_id is None:
            raise SerializationError(message=f"Object of type '{obj_type.__name__}' is not registered.")

        payload = self._serializer.serialize(obj=obj)
        payload_len = len(payload)
        header = struct.pack(self._HEADER_FORMAT, type_id, payload_len)
        full_packet = header + payload

        async with self._write_lock:
            await self._stream.write(data=full_packet)

    def __aiter__(self) -> StructuredStream:
        """Return self as the asynchronous iterator."""
        return self

    async def __anext__(self) -> Any:
        """Receive the next object in the async iteration."""
        try:
            return await self.receive_obj()
        except StreamError as e:
            if e.error_code in (ErrorCodes.NO_ERROR, ErrorCodes.H3_NO_ERROR):
                raise StopAsyncIteration
            raise



================================================
FILE: src/pywebtransport/serializer/__init__.py
================================================
"""Pluggable serializers for structured data transmission."""

from .json import JSONSerializer
from .msgpack import MsgPackSerializer
from .protobuf import ProtobufSerializer

__all__: list[str] = ["JSONSerializer", "MsgPackSerializer", "ProtobufSerializer"]



================================================
FILE: src/pywebtransport/serializer/_base.py
================================================
"""Base class for serializers handling dataclass conversion."""

from __future__ import annotations

import types
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Union, get_args, get_origin

from pywebtransport.exceptions import SerializationError

__all__: list[str] = []


_FIELDS_CACHE: dict[type[Any], tuple[Any, ...]] = {}


def _get_cached_fields(*, cls: type[Any]) -> tuple[Any, ...]:
    if cls in _FIELDS_CACHE:
        return _FIELDS_CACHE[cls]

    cls_fields = fields(cls)
    _FIELDS_CACHE[cls] = cls_fields
    return cls_fields


class BaseDataclassSerializer:
    """Base class providing recursive dict-to-dataclass conversion."""

    _MAX_RECURSION_DEPTH = 64

    def convert_to_type(self, *, data: Any, target_type: Any, depth: int = 0) -> Any:
        """Recursively convert a decoded object to a specific target type."""
        if depth > self._MAX_RECURSION_DEPTH:
            raise SerializationError(message="Maximum recursion depth exceeded during deserialization.")

        if target_type is Any:
            return data

        if data is None:
            origin = get_origin(target_type)
            if origin is Union or origin is types.UnionType:
                if type(None) in get_args(target_type):
                    return None
            return None

        origin = get_origin(target_type)
        args = get_args(target_type)

        if origin is Union or origin is types.UnionType:
            non_none_types = [t for t in args if t is not type(None)]

            for candidate in non_none_types:
                candidate_origin = get_origin(candidate) or candidate
                if isinstance(data, candidate_origin):
                    return self.convert_to_type(data=data, target_type=candidate, depth=depth)

            for candidate in non_none_types:
                try:
                    return self.convert_to_type(data=data, target_type=candidate, depth=depth)
                except (TypeError, ValueError, SerializationError):
                    continue

        if isinstance(target_type, type):
            if is_dataclass(target_type) and isinstance(data, dict):
                return self.from_dict_to_dataclass(data=data, cls=target_type, depth=depth + 1)

            if issubclass(target_type, Enum):
                try:
                    return target_type(data)
                except ValueError as e:
                    raise SerializationError(message=f"Invalid value '{data}' for enum {target_type.__name__}") from e

        if origin in (list, tuple, set) or target_type in (list, tuple, set):
            if isinstance(data, (list, tuple, set)):
                container = origin or target_type
                if not args:
                    return container(data)
                inner_type = args[0]
                items = [self.convert_to_type(data=item, target_type=inner_type, depth=depth + 1) for item in data]
                return container(items)

        if (origin is dict or target_type is dict) and isinstance(data, dict):
            if not args:
                return data
            key_type, value_type = args
            return {
                self.convert_to_type(data=k, target_type=key_type, depth=depth + 1): self.convert_to_type(
                    data=v, target_type=value_type, depth=depth + 1
                )
                for k, v in data.items()
            }

        if callable(target_type) and not isinstance(data, target_type):
            try:
                return target_type(data)
            except (TypeError, ValueError):
                pass

        return data

    def from_dict_to_dataclass(self, *, data: dict[str, Any], cls: type[Any], depth: int) -> Any:
        """Recursively convert a dictionary to a dataclass instance."""
        if depth > self._MAX_RECURSION_DEPTH:
            raise SerializationError(message="Maximum recursion depth exceeded during dataclass unpacking.")

        constructor_args = {}
        for field in _get_cached_fields(cls=cls):
            if field.name in data:
                field_value = data[field.name]
                constructor_args[field.name] = self.convert_to_type(
                    data=field_value, target_type=field.type, depth=depth + 1
                )

        try:
            return cls(**constructor_args)
        except TypeError as e:
            raise SerializationError(
                message=f"Failed to unpack dictionary to dataclass {cls.__name__}.", original_exception=e
            ) from e



================================================
FILE: src/pywebtransport/serializer/json.py
================================================
"""Serializer implementation using the JSON format."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pywebtransport.exceptions import SerializationError
from pywebtransport.serializer._base import BaseDataclassSerializer
from pywebtransport.types import Buffer, Serializer

__all__: list[str] = ["JSONSerializer"]


class JSONSerializer(BaseDataclassSerializer, Serializer):
    """Serializer for encoding and decoding using the JSON format."""

    def __init__(self, *, dump_kwargs: dict[str, Any] | None = None, load_kwargs: dict[str, Any] | None = None) -> None:
        """Initialize the JSON serializer."""
        self._dump_kwargs = dump_kwargs.copy() if dump_kwargs is not None else {}
        self._load_kwargs = load_kwargs.copy() if load_kwargs is not None else {}
        self._user_default = self._dump_kwargs.pop("default", None)

    def convert_to_type(self, *, data: Any, target_type: Any, depth: int = 0) -> Any:
        """Recursively convert a decoded object to a specific target type."""
        if isinstance(data, str) and target_type in (bytes, bytearray):
            try:
                decoded = base64.b64decode(data)
                if target_type is bytearray:
                    return bytearray(decoded)
                return decoded
            except (ValueError, TypeError):
                pass

        return super().convert_to_type(data=data, target_type=target_type, depth=depth)

    def deserialize(self, *, data: Buffer, obj_type: Any = None) -> Any:
        """Deserialize a JSON byte string into a Python object."""
        try:
            if isinstance(data, memoryview):
                data = bytes(data)

            decoded_obj = json.loads(s=data, **self._load_kwargs)

            if obj_type is None:
                return decoded_obj
            return self.convert_to_type(data=decoded_obj, target_type=obj_type)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise SerializationError(
                message="Data is not valid JSON or cannot be unpacked.", original_exception=e
            ) from e

    def serialize(self, *, obj: Any) -> bytes:
        """Serialize a Python object into a JSON byte string."""
        try:
            return json.dumps(obj=obj, default=self._default_handler, **self._dump_kwargs).encode("utf-8")
        except TypeError as e:
            raise SerializationError(
                message=f"Object of type {type(obj).__name__} is not JSON serializable.", original_exception=e
            ) from e

    def _default_handler(self, o: Any) -> Any:
        """Handle types not natively supported by JSON."""
        match o:
            case bytes() | bytearray() | memoryview():
                return base64.b64encode(o).decode("ascii")
            case uuid.UUID():
                return str(o)
            case Enum():
                return o.value
            case set() | frozenset():
                return list(o)
            case datetime():
                return o.isoformat()
            case _ if is_dataclass(o) and not isinstance(o, type):
                return asdict(obj=o)
            case _:
                if self._user_default is not None:
                    return self._user_default(o)
                raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")



================================================
FILE: src/pywebtransport/serializer/msgpack.py
================================================
"""Serializer implementation using the MsgPack format."""

from __future__ import annotations

import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, cast

from pywebtransport.exceptions import ConfigurationError, SerializationError
from pywebtransport.serializer._base import BaseDataclassSerializer
from pywebtransport.types import Buffer, Serializer

try:
    import msgpack
except ImportError:
    msgpack = None


__all__: list[str] = ["MsgPackSerializer"]


class MsgPackSerializer(BaseDataclassSerializer, Serializer):
    """Serializer for encoding and decoding using the MsgPack format."""

    def __init__(
        self, *, pack_kwargs: dict[str, Any] | None = None, unpack_kwargs: dict[str, Any] | None = None
    ) -> None:
        """Initialize the MsgPack serializer."""
        if msgpack is None:
            raise ConfigurationError(
                message="The 'msgpack' library is required for MsgPackSerializer.",
                config_key="dependency.msgpack",
                details={"installation_guide": "Please install it with: pip install pywebtransport[msgpack]"},
            )

        self._pack_kwargs = pack_kwargs.copy() if pack_kwargs is not None else {}
        self._unpack_kwargs = unpack_kwargs.copy() if unpack_kwargs is not None else {}
        self._user_default = self._pack_kwargs.pop("default", None)

    def deserialize(self, *, data: Buffer, obj_type: Any = None) -> Any:
        """Deserialize a MsgPack byte string into a Python object."""
        try:
            unpack_kwargs = {"raw": False, **self._unpack_kwargs}
            decoded_obj = msgpack.unpackb(packed=data, **unpack_kwargs)

            if obj_type is None:
                return decoded_obj
            return self.convert_to_type(data=decoded_obj, target_type=obj_type)
        except (msgpack.UnpackException, TypeError, ValueError) as e:
            raise SerializationError(
                message="Data is not valid MsgPack or cannot be unpacked.", original_exception=e
            ) from e

    def serialize(self, *, obj: Any) -> bytes:
        """Serialize a Python object into a MsgPack byte string."""
        try:
            return cast(bytes, msgpack.packb(o=obj, default=self._default_handler, **self._pack_kwargs))
        except TypeError as e:
            raise SerializationError(
                message=f"Object of type {type(obj).__name__} is not MsgPack serializable.", original_exception=e
            ) from e

    def _default_handler(self, o: Any) -> Any:
        """Handle types not natively supported by MsgPack."""
        match o:
            case uuid.UUID():
                return str(o)
            case Enum():
                return o.value
            case set() | frozenset():
                return list(o)
            case datetime():
                return o.isoformat()
            case _ if is_dataclass(o) and not isinstance(o, type):
                return asdict(obj=o)
            case _:
                if self._user_default is not None:
                    return self._user_default(o)
                raise TypeError(f"Object of type {type(o).__name__} is not MsgPack serializable")



================================================
FILE: src/pywebtransport/serializer/protobuf.py
================================================
"""Serializer implementation using the Protocol Buffers format."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pywebtransport.exceptions import ConfigurationError, SerializationError
from pywebtransport.types import Buffer, Serializer

try:
    from google.protobuf.message import DecodeError, Message
except ImportError:
    Message = None
    DecodeError = None

if TYPE_CHECKING:
    from google.protobuf.message import Message as MessageType


__all__: list[str] = ["ProtobufSerializer"]


class ProtobufSerializer(Serializer):
    """Serializer for encoding and decoding using the Protobuf format."""

    def __init__(self) -> None:
        """Initialize the Protobuf serializer."""
        if Message is None:
            raise ConfigurationError(
                message="The 'protobuf' library is required for ProtobufSerializer.",
                config_key="dependency.protobuf",
                details={"installation_guide": "Please install it with: pip install pywebtransport[protobuf]"},
            )

    def deserialize(self, *, data: Buffer, obj_type: Any = None) -> MessageType:
        """Deserialize bytes into an instance of the specified Protobuf message class."""
        if obj_type is None:
            raise SerializationError(message="Protobuf deserialization requires a specific 'obj_type'.")

        if not issubclass(obj_type, Message):
            raise SerializationError(
                message=f"Target type '{obj_type.__name__}' is not a valid Protobuf Message class."
            )

        if isinstance(data, memoryview):
            data = bytes(data)

        instance = obj_type()

        try:
            instance.ParseFromString(serialized=data)
            return instance
        except (DecodeError, Exception) as e:
            raise SerializationError(
                message=f"Failed to deserialize data into '{obj_type.__name__}'.", original_exception=e
            ) from e

    def serialize(self, *, obj: Any) -> bytes:
        """Serialize a Protobuf message object into bytes."""
        if not isinstance(obj, Message):
            raise SerializationError(message=f"Object of type '{type(obj).__name__}' is not a valid Protobuf Message.")

        try:
            return cast(bytes, obj.SerializeToString())
        except Exception as e:
            raise SerializationError(message=f"Failed to serialize Protobuf message: {e}", original_exception=e) from e



================================================
FILE: src/pywebtransport/server/__init__.py
================================================
"""Server-side framework for WebTransport applications."""

from .app import ServerApp
from .cluster import ServerCluster
from .middleware import (
    AuthHandlerProtocol,
    MiddlewareManager,
    MiddlewareProtocol,
    MiddlewareRejected,
    StatefulMiddlewareProtocol,
    create_auth_middleware,
    create_cors_middleware,
    create_logging_middleware,
    create_rate_limit_middleware,
)
from .router import RequestRouter, SessionHandler
from .server import ServerDiagnostics, ServerStats, WebTransportServer

__all__: list[str] = [
    "AuthHandlerProtocol",
    "MiddlewareManager",
    "MiddlewareProtocol",
    "MiddlewareRejected",
    "RequestRouter",
    "ServerApp",
    "ServerCluster",
    "ServerDiagnostics",
    "ServerStats",
    "SessionHandler",
    "StatefulMiddlewareProtocol",
    "WebTransportServer",
    "create_auth_middleware",
    "create_cors_middleware",
    "create_logging_middleware",
    "create_rate_limit_middleware",
]



================================================
FILE: src/pywebtransport/server/app.py
================================================
"""High-level application framework for building WebTransport servers."""

from __future__ import annotations

import asyncio
import http
import weakref
from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

from pywebtransport._protocol.events import UserAcceptSession, UserCloseSession, UserRejectSession
from pywebtransport.config import ServerConfig
from pywebtransport.connection import WebTransportConnection
from pywebtransport.constants import ErrorCodes
from pywebtransport.events import Event
from pywebtransport.exceptions import ConnectionError, ServerError
from pywebtransport.server.middleware import (
    MiddlewareManager,
    MiddlewareProtocol,
    MiddlewareRejected,
    StatefulMiddlewareProtocol,
)
from pywebtransport.server.router import RequestRouter, SessionHandler
from pywebtransport.server.server import WebTransportServer
from pywebtransport.session import WebTransportSession
from pywebtransport.types import EventType
from pywebtransport.utils import get_logger

__all__ = ["ServerApp"]

logger = get_logger(name=__name__)


class ServerApp:
    """Implement a high-level WebTransport application with routing and middleware."""

    def __init__(self, *, config: ServerConfig | None = None) -> None:
        """Initialize the server application."""
        self._server = WebTransportServer(config=config)
        self._router = RequestRouter()
        self._middleware_manager = MiddlewareManager()
        self._stateful_middleware: list[StatefulMiddlewareProtocol] = []
        self._startup_handlers: list[Callable[[], Any]] = []
        self._shutdown_handlers: list[Callable[[], Any]] = []
        self._tg: asyncio.TaskGroup | None = None
        self._handler_tasks: weakref.WeakSet[asyncio.Task[Any]] = weakref.WeakSet()
        self._server.on(event_type=EventType.SESSION_REQUEST, handler=self._handle_session_request)

    @property
    def server(self) -> WebTransportServer:
        """Get the underlying WebTransportServer instance."""
        return self._server

    async def __aenter__(self) -> Self:
        """Enter the async context and run startup procedures."""
        await self._server.__aenter__()
        self._tg = asyncio.TaskGroup()
        await self._tg.__aenter__()
        await self.startup()
        logger.info("ServerApp started.")
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context and run shutdown procedures."""
        try:
            await self.shutdown()
            if self._tg is not None:
                await self._tg.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            await self._server.close()
            logger.info("ServerApp stopped.")

    def run(self, *, host: str | None = None, port: int | None = None, **kwargs: Any) -> None:
        """Run the server application in a new asyncio event loop."""
        final_host = host if host is not None else self.server.config.bind_host
        final_port = port if port is not None else self.server.config.bind_port

        async def main() -> None:
            async with self:
                await self.serve(host=final_host, port=final_port, **kwargs)

        try:
            asyncio.run(main=main())
        except KeyboardInterrupt:
            logger.info("Server stopped by user.")

    async def serve(self, *, host: str | None = None, port: int | None = None, **kwargs: Any) -> None:
        """Start the server and serve forever."""
        if self._tg is None:
            raise ServerError(
                message=(
                    "ServerApp has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        final_host = host if host is not None else self.server.config.bind_host
        final_port = port if port is not None else self.server.config.bind_port
        await self._server.listen(host=final_host, port=final_port)
        await self._server.serve_forever()

    async def shutdown(self) -> None:
        """Run shutdown handlers and exit stateful middleware."""
        for handler in self._shutdown_handlers:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

        for middleware in reversed(self._stateful_middleware):
            await middleware.__aexit__(None, None, None)

        if self._handler_tasks:
            logger.info("Cancelling %d active handler tasks...", len(self._handler_tasks))
            for task in self._handler_tasks:
                if not task.done():
                    task.cancel()
            logger.info("Active handler tasks cancelled, awaiting termination in TaskGroup.")

    async def startup(self) -> None:
        """Run startup handlers and enter stateful middleware."""
        for middleware in self._stateful_middleware:
            await middleware.__aenter__()

        for handler in self._startup_handlers:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    def add_middleware(self, *, middleware: MiddlewareProtocol) -> None:
        """Add a middleware to the processing chain."""
        self._middleware_manager.add_middleware(middleware=middleware)
        if isinstance(middleware, StatefulMiddlewareProtocol):
            self._stateful_middleware.append(middleware)

    def middleware(self, middleware_func: MiddlewareProtocol) -> MiddlewareProtocol:
        """Register a middleware function."""
        self.add_middleware(middleware=middleware_func)
        return middleware_func

    def on_shutdown[F: Callable[..., Any]](self, handler: F) -> F:
        """Register a handler to run on application shutdown."""
        self._shutdown_handlers.append(handler)
        return handler

    def on_startup[F: Callable[..., Any]](self, handler: F) -> F:
        """Register a handler to run on application startup."""
        self._startup_handlers.append(handler)
        return handler

    def pattern_route(self, *, pattern: str) -> Callable[[SessionHandler], SessionHandler]:
        """Register a session handler for a URL pattern."""

        def decorator(handler: SessionHandler) -> SessionHandler:
            self._router.add_pattern_route(pattern=pattern, handler=handler)
            return handler

        return decorator

    def route(self, *, path: str) -> Callable[[SessionHandler], SessionHandler]:
        """Register a session handler for a specific path."""

        def decorator(handler: SessionHandler) -> SessionHandler:
            self._router.add_route(path=path, handler=handler)
            return handler

        return decorator

    async def _dispatch_to_handler(self, *, session: WebTransportSession) -> None:
        """Find the route handler and create a background task to run it."""
        route_result = self._router.route_request(session=session)

        connection = session._connection()

        if connection is None:
            logger.error("Cannot dispatch handler, connection is missing.")
            return

        if route_result is None:
            logger.warning(
                "No route found for session %s (path: %s). Rejecting with %s.",
                session.session_id,
                session.path,
                http.HTTPStatus.NOT_FOUND,
            )
            request_id, future = connection._protocol.create_request()
            event = UserRejectSession(
                request_id=request_id, session_id=session.session_id, status_code=http.HTTPStatus.NOT_FOUND
            )
            connection._protocol.send_event(event=event)
            await future
            return

        handler, params = route_result
        logger.info("Routing session request for path '%s' to handler '%s'", session.path, handler.__name__)

        try:
            accept_req_id, accept_fut = connection._protocol.create_request()
            accept_event = UserAcceptSession(request_id=accept_req_id, session_id=session.session_id)
            connection._protocol.send_event(event=accept_event)
            await accept_fut
        except Exception as e:
            logger.error("Failed to accept session %s: %s", session.session_id, e, exc_info=True)
            return

        if self._tg is not None:
            handler_task = self._tg.create_task(
                coro=self._run_handler_safely(handler=handler, session=session, params=params)
            )
            self._handler_tasks.add(handler_task)
            logger.info("Handler task created and tracked for session %s", session.session_id)
        else:
            logger.error("TaskGroup not initialized. Handler cannot be dispatched.")

    async def _get_session_from_event(self, *, event: Event) -> WebTransportSession | None:
        """Validate event data and retrieve the existing WebTransportSession handle."""
        if not isinstance(event.data, dict):
            logger.warning("Session request event data is not a dictionary")
            return None

        session = event.data.get("session")
        if not isinstance(session, WebTransportSession):
            logger.warning("Invalid or missing 'session' handle in session request.")
            return None

        connection = event.data.get("connection")
        if not isinstance(connection, WebTransportConnection):
            logger.warning("Invalid 'connection' object in session request")
            return None

        session_conn = session._connection()

        if session_conn is not connection:
            logger.error(
                "Session handle %s does not belong to connection %s", session.session_id, connection.connection_id
            )
            return None

        if not connection.is_connected:
            logger.warning("Connection %s is not in connected state", connection.connection_id)
            return None

        logger.info("Processing session request: session_id=%s, path='%s'", session.session_id, session.path)

        if self.server.session_manager is not None:
            try:
                await self.server.session_manager.add_session(session=session)
            except Exception as e:
                logger.error(
                    "Failed to register session %s with SessionManager: %s", session.session_id, e, exc_info=True
                )

        return session

    async def _handle_session_request(self, event: Event) -> None:
        """Orchestrate the handling of an incoming session request."""
        session: WebTransportSession | None = None
        event_data = event.data if isinstance(event.data, dict) else {}

        connection: WebTransportConnection | None = event_data.get("connection")
        session_id_from_data: int | None = event_data.get("session_id")

        try:
            session = await self._get_session_from_event(event=event)

            if session is None:
                return

            await self._middleware_manager.process_request(session=session)
            await self._dispatch_to_handler(session=session)

        except MiddlewareRejected as e:
            logger.warning(
                "Session request for path '%s' rejected by middleware: %s",
                session.path if session is not None else "unknown",
                e,
            )
            sid = session.session_id if session is not None else session_id_from_data
            if connection is not None and sid is not None:
                request_id, future = connection._protocol.create_request()
                reject_event = UserRejectSession(request_id=request_id, session_id=sid, status_code=e.status_code)
                connection._protocol.send_event(event=reject_event)
                await future
            if session is not None and not session.is_closed:
                await session.close()

        except Exception as e:
            sid = session.session_id if session is not None else session_id_from_data
            logger.error("Error handling session request for session %s: %s", sid, e, exc_info=True)
            try:
                if connection is not None and sid is not None:
                    request_id, future = connection._protocol.create_request()
                    close_event = UserCloseSession(
                        request_id=request_id,
                        session_id=sid,
                        error_code=ErrorCodes.INTERNAL_ERROR,
                        reason="Internal server error handling request",
                    )
                    connection._protocol.send_event(event=close_event)
                    await future
                if session is not None and not session.is_closed:
                    await session.close()
            except Exception as cleanup_error:
                logger.error("Error during session request error cleanup: %s", cleanup_error, exc_info=cleanup_error)

    async def _run_handler_safely(
        self, *, handler: SessionHandler, session: WebTransportSession, params: dict[str, Any]
    ) -> None:
        """Wrap the session handler execution with error handling and resource cleanup."""
        try:
            logger.debug("Handler starting for session %s", session.session_id)
            await handler(session, **params)
            logger.debug("Handler completed for session %s", session.session_id)
        except Exception as handler_error:
            logger.error("Handler error for session %s: %s", session.session_id, handler_error, exc_info=True)
        finally:
            if not session.is_closed:
                try:
                    logger.debug("Closing session %s after handler completion/error.", session.session_id)
                    await session.close()
                except ConnectionError as e:
                    logger.debug(
                        "Session %s cleanup: Connection closed implicitly or Engine stopped (%s).",
                        session.session_id,
                        e,
                    )
                except Exception as close_error:
                    logger.error(
                        "Unexpected error closing session %s: %s", session.session_id, close_error, exc_info=True
                    )



================================================
FILE: src/pywebtransport/server/cluster.py
================================================
"""Utility for managing a cluster of server instances."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, Self, cast

from pywebtransport.config import ServerConfig
from pywebtransport.exceptions import ServerError
from pywebtransport.server.server import WebTransportServer
from pywebtransport.types import ConnectionState, SessionState
from pywebtransport.utils import get_logger

__all__: list[str] = ["ServerCluster"]

logger = get_logger(name=__name__)


class ServerCluster:
    """Manages the lifecycle of multiple WebTransport server instances."""

    def __init__(self, *, configs: list[ServerConfig]) -> None:
        """Initialize the server cluster."""
        self._configs = list(configs)
        self._servers: list[WebTransportServer] = []
        self._running = False
        self._lock: asyncio.Lock | None = None
        self._shutdown_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Check if the cluster is currently running."""
        return self._running

    async def __aenter__(self) -> Self:
        """Enter the async context and start all servers."""
        self._lock = asyncio.Lock()
        await self.start_all()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context and stop all servers."""
        await self.stop_all()

    async def add_server(self, *, config: ServerConfig) -> WebTransportServer | None:
        """Add and start a new server in the running cluster."""
        if self._lock is None:
            raise ServerError(
                message=(
                    "ServerCluster has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        async with self._lock:
            if not self._running:
                self._configs.append(config)
                logger.info("Cluster not running. Server config added for next start.")
                return None

        try:
            server = await self._create_and_start_server(config=config)
        except Exception as e:
            logger.error("Failed to add server to cluster: %s", e, exc_info=True)
            return None

        return await self._finalize_added_server(server=server, config=config)

    async def get_cluster_stats(self) -> dict[str, Any]:
        """Get deeply aggregated statistics for the entire cluster."""
        if self._lock is None:
            raise ServerError(
                message=(
                    "ServerCluster has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        servers_snapshot: list[WebTransportServer]
        async with self._lock:
            servers_snapshot = list(self._servers)

        if not servers_snapshot:
            return {
                "server_count": 0,
                "total_connections_accepted": 0,
                "total_connections_rejected": 0,
                "total_connections_active": 0,
                "total_sessions_active": 0,
            }

        tasks = []
        try:
            async with asyncio.TaskGroup() as tg:
                for s in servers_snapshot:
                    tasks.append(tg.create_task(coro=s.diagnostics()))
        except* Exception as eg:
            logger.error("Failed to fetch stats from some servers: %s", eg.exceptions, exc_info=True)
            raise eg

        diagnostics_list = [task.result() for task in tasks if task.done() and not task.exception()]

        agg_stats: dict[str, Any] = {
            "server_count": len(servers_snapshot),
            "total_connections_accepted": 0,
            "total_connections_rejected": 0,
            "total_connections_active": 0,
            "total_sessions_active": 0,
        }
        for diag in diagnostics_list:
            agg_stats["total_connections_accepted"] += diag.stats.connections_accepted
            agg_stats["total_connections_rejected"] += diag.stats.connections_rejected
            agg_stats["total_connections_active"] += diag.connection_states.get(ConnectionState.CONNECTED, 0)
            agg_stats["total_sessions_active"] += diag.session_states.get(SessionState.CONNECTED, 0)

        return agg_stats

    async def get_server_count(self) -> int:
        """Get the number of running servers in the cluster."""
        if self._lock is None:
            raise ServerError("Cluster not activated.")
        async with self._lock:
            return len(self._servers)

    async def get_servers(self) -> list[WebTransportServer]:
        """Get a thread-safe copy of all active servers in the cluster."""
        if self._lock is None:
            raise ServerError("Cluster not activated.")
        async with self._lock:
            return list(self._servers)

    async def remove_server(self, *, host: str, port: int) -> bool:
        """Remove and stop a specific server from the cluster by its config address."""
        if self._lock is None:
            raise ServerError(
                message=(
                    "ServerCluster has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        server_to_remove: WebTransportServer | None = None
        async with self._lock:
            for server in self._servers:
                if server.config.bind_host == host and server.config.bind_port == port:
                    server_to_remove = server
                    break

            if server_to_remove is not None:
                self._servers.remove(server_to_remove)
                self._configs = [c for c in self._configs if not (c.bind_host == host and c.bind_port == port)]
            else:
                logger.warning("Server with config %s:%s not found in cluster.", host, port)
                return False

        await server_to_remove.close()
        logger.info("Removed server from cluster: %s:%s", host, port)
        return True

    async def serve_forever(self) -> None:
        """Run the cluster indefinitely until interrupted."""
        if self._lock is None:
            raise ServerError("Cluster not activated.")

        if not self._running:
            raise ServerError("Cluster is not running.")

        logger.info("Cluster serving forever. Press Ctrl+C to stop.")
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("serve_forever cancelled.")
        except Exception as e:
            logger.error("Error during serve_forever wait: %s", e)
        finally:
            logger.info("serve_forever loop finished.")

    async def start_all(self) -> None:
        """Start all servers in the cluster concurrently."""
        if self._lock is None:
            raise ServerError(
                message=(
                    "ServerCluster has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        async with self._lock:
            if self._running:
                return

            configs_to_start = list(self._configs)
            self._running = True
            self._shutdown_event.clear()

        async def safe_start(config: ServerConfig) -> WebTransportServer | None:
            try:
                return await self._create_and_start_server(config=config)
            except Exception as e:
                logger.error(
                    "Failed to start server on %s:%s: %s", config.bind_host, config.bind_port, e, exc_info=True
                )
                return None

        tasks: list[asyncio.Task[WebTransportServer | None]] = []
        async with asyncio.TaskGroup() as tg:
            for config in configs_to_start:
                tasks.append(tg.create_task(coro=safe_start(config)))

        started_servers: list[WebTransportServer] = []
        for task in tasks:
            server = task.result()
            if server is not None:
                started_servers.append(server)

        async with self._lock:
            self._servers.extend(started_servers)
            logger.info("Cluster started. %d/%d servers active.", len(self._servers), len(configs_to_start))

    async def stop_all(self) -> None:
        """Stop all servers in the cluster concurrently."""
        if self._lock is None:
            raise ServerError(
                message=(
                    "ServerCluster has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        servers_to_stop: list[WebTransportServer] = []
        async with self._lock:
            if not self._running:
                return
            servers_to_stop = list(self._servers)
            self._servers.clear()
            self._running = False
            self._shutdown_event.set()

        if servers_to_stop:
            try:
                async with asyncio.TaskGroup() as tg:
                    for server in servers_to_stop:
                        tg.create_task(coro=server.close())
            except* Exception as eg:
                logger.error("Errors occurred while stopping server cluster: %s", eg.exceptions, exc_info=True)
                raise eg

            logger.info("Stopped server cluster")

    async def _create_and_start_server(self, *, config: ServerConfig) -> WebTransportServer:
        """Create, activate, and start a single server instance."""
        server = WebTransportServer(config=config)
        await server.__aenter__()

        try:
            await server.listen()
        except Exception:
            await server.close()
            raise
        return server

    async def _finalize_added_server(
        self, *, server: WebTransportServer, config: ServerConfig
    ) -> WebTransportServer | None:
        """Register a newly started server if the cluster is still running."""
        async with cast(asyncio.Lock, self._lock):
            if not self._running:
                logger.warning("Cluster stopped while new server was starting. Shutting down new server.")
                await server.close()
                return None

            self._configs.append(config)
            self._servers.append(server)
            logger.info("Added server to cluster: %s", server.local_address)
            return server



================================================
FILE: src/pywebtransport/server/middleware.py
================================================
"""Core framework and common implementations for server middleware."""

from __future__ import annotations

import asyncio
import fnmatch
import http
import time
from collections import deque
from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from pywebtransport.exceptions import ServerError
from pywebtransport.types import Headers, SessionProtocol
from pywebtransport.utils import find_header_str, get_logger

__all__: list[str] = [
    "AuthHandlerProtocol",
    "MiddlewareManager",
    "MiddlewareProtocol",
    "MiddlewareRejected",
    "RateLimiter",
    "StatefulMiddlewareProtocol",
    "create_auth_middleware",
    "create_cors_middleware",
    "create_logging_middleware",
    "create_rate_limit_middleware",
]

logger = get_logger(name=__name__)

DEFAULT_RATE_LIMIT_MAX_REQUESTS: int = 100
DEFAULT_RATE_LIMIT_WINDOW: int = 60
DEFAULT_RATE_LIMIT_CLEANUP_INTERVAL: int = 300
DEFAULT_RATE_LIMIT_MAX_TRACKED_IPS: int = 10000


class MiddlewareRejected(Exception):
    """Exception raised by middleware to reject a session request with specific details."""

    def __init__(self, status_code: int = http.HTTPStatus.FORBIDDEN, headers: Headers | None = None) -> None:
        """Initialize the rejection exception."""
        super().__init__(f"Request rejected with status {status_code}")
        self.status_code = status_code
        self.headers = headers if headers is not None else {}


@runtime_checkable
class AuthHandlerProtocol(Protocol):
    """A protocol for authentication handlers."""

    async def __call__(self, *, headers: Headers) -> bool:
        """Perform authentication check on headers."""
        ...


@runtime_checkable
class MiddlewareProtocol(Protocol):
    """A protocol for a middleware object."""

    async def __call__(self, *, session: SessionProtocol) -> None:
        """Process a session request. Raise MiddlewareRejected to deny."""
        ...


@runtime_checkable
class StatefulMiddlewareProtocol(MiddlewareProtocol, Protocol):
    """A protocol for middleware that requires lifecycle management."""

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        ...

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context manager."""
        ...


class MiddlewareManager:
    """Manages a chain of server middleware."""

    def __init__(self) -> None:
        """Initialize the middleware manager."""
        self._middleware: list[MiddlewareProtocol] = []

    def add_middleware(self, *, middleware: MiddlewareProtocol) -> None:
        """Add a middleware to the chain."""
        self._middleware.append(middleware)

    def get_middleware_count(self) -> int:
        """Get the number of registered middleware."""
        return len(self._middleware)

    async def process_request(self, *, session: SessionProtocol) -> None:
        """Process a request through the middleware chain."""
        for middleware in self._middleware:
            try:
                await middleware(session=session)
            except MiddlewareRejected:
                raise
            except Exception as e:
                logger.error("Middleware error: %s", e, exc_info=True)
                raise MiddlewareRejected(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR) from e

    def remove_middleware(self, *, middleware: MiddlewareProtocol) -> None:
        """Remove a middleware from the chain."""
        if middleware in self._middleware:
            self._middleware.remove(middleware)


class RateLimiter:
    """A stateful, concurrent-safe rate-limiting middleware."""

    def __init__(
        self,
        *,
        max_requests: int = DEFAULT_RATE_LIMIT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW,
        cleanup_interval: int = DEFAULT_RATE_LIMIT_CLEANUP_INTERVAL,
        max_tracked_ips: int = DEFAULT_RATE_LIMIT_MAX_TRACKED_IPS,
    ) -> None:
        """Initialize the rate limiter."""
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._cleanup_interval = cleanup_interval
        self._max_tracked_ips = max_tracked_ips
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()
        self._tg: asyncio.TaskGroup | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._is_closing = False

    async def __aenter__(self) -> Self:
        """Initialize resources and start the cleanup task."""
        self._is_closing = False
        self._tg = asyncio.TaskGroup()
        await self._tg.__aenter__()
        self._start_cleanup_task()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Stop the background cleanup task and release resources."""
        self._is_closing = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()

        if self._tg is not None:
            await self._tg.__aexit__(exc_type, exc_val, exc_tb)

        self._cleanup_task = None
        self._tg = None

    async def _periodic_cleanup(self) -> None:
        """Periodically remove stale IP entries from the tracker."""
        while True:
            try:
                await asyncio.sleep(delay=self._cleanup_interval)
                if self._is_closing:
                    break

                async with self._lock:
                    current_time = time.perf_counter()
                    cutoff_time = current_time - self._window_seconds
                    ips_to_remove: list[str] = []

                    for ip, timestamps in self._requests.items():
                        while timestamps and timestamps[0] < cutoff_time:
                            timestamps.popleft()
                        if not timestamps:
                            ips_to_remove.append(ip)

                    for ip in ips_to_remove:
                        del self._requests[ip]

                    if ips_to_remove:
                        logger.debug("Cleaned up %d stale IP entries.", len(ips_to_remove))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in RateLimiter cleanup task: %s", e, exc_info=True)
                await asyncio.sleep(delay=1.0)

    def _start_cleanup_task(self) -> None:
        """Create and start the periodic cleanup task if not already running."""
        if self._tg is not None and (self._cleanup_task is None or self._cleanup_task.done()):
            self._cleanup_task = self._tg.create_task(coro=self._periodic_cleanup())

    async def __call__(self, *, session: SessionProtocol) -> None:
        """Apply rate limiting to an incoming session."""
        if self._tg is None:
            raise ServerError(
                message=(
                    "RateLimiter has not been activated. It must be used as an "
                    "asynchronous context manager (`async with ...`)."
                )
            )

        client_ip = "unknown"
        if session.remote_address is not None:
            client_ip = session.remote_address[0]

        current_time = time.perf_counter()

        async with self._lock:
            if client_ip not in self._requests:
                if len(self._requests) >= self._max_tracked_ips:
                    self._requests.clear()
                    logger.warning(
                        "Rate limiter IP tracking limit (%d) reached. Flushed all records.", self._max_tracked_ips
                    )
                self._requests[client_ip] = deque()

            client_timestamps = self._requests[client_ip]
            cutoff_time = current_time - self._window_seconds

            while client_timestamps and client_timestamps[0] < cutoff_time:
                client_timestamps.popleft()

            if len(client_timestamps) >= self._max_requests:
                logger.warning("Rate limit exceeded for IP %s", client_ip)
                raise MiddlewareRejected(
                    status_code=http.HTTPStatus.TOO_MANY_REQUESTS, headers={"retry-after": str(self._window_seconds)}
                )

            client_timestamps.append(current_time)


def create_auth_middleware(*, auth_handler: AuthHandlerProtocol) -> MiddlewareProtocol:
    """Create an authentication middleware with a custom handler."""

    async def middleware(*, session: SessionProtocol) -> None:
        try:
            if not await auth_handler(headers=session.headers):
                raise MiddlewareRejected(status_code=http.HTTPStatus.UNAUTHORIZED)
        except MiddlewareRejected:
            raise
        except Exception as e:
            logger.error("Authentication handler error: %s", e, exc_info=True)
            raise MiddlewareRejected(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR) from e

    return middleware


def create_cors_middleware(*, allowed_origins: list[str]) -> MiddlewareProtocol:
    """Create a CORS middleware to validate the Origin header."""

    async def cors_middleware(*, session: SessionProtocol) -> None:
        origin = find_header_str(headers=session.headers, key="origin")
        if origin is None or not origin:
            logger.warning("CORS check failed: 'Origin' header missing.")
            raise MiddlewareRejected(status_code=http.HTTPStatus.FORBIDDEN)

        match_found = False
        for pattern in allowed_origins:
            if fnmatch.fnmatch(name=origin, pat=pattern):
                match_found = True
                break

        if not match_found:
            logger.warning("CORS check failed: Origin '%s' not allowed.", origin)
            raise MiddlewareRejected(status_code=http.HTTPStatus.FORBIDDEN)

    return cors_middleware


def create_logging_middleware() -> MiddlewareProtocol:
    """Create a simple request logging middleware."""

    async def middleware(*, session: SessionProtocol) -> None:
        remote_address_str = "unknown"
        if session.remote_address is not None:
            addr = session.remote_address
            remote_address_str = f"{addr[0]}:{addr[1]}"

        logger.info("Session request: path='%s' from=%s", session.path, remote_address_str)

    return middleware


def create_rate_limit_middleware(
    *,
    max_requests: int = DEFAULT_RATE_LIMIT_MAX_REQUESTS,
    window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW,
    cleanup_interval: int = DEFAULT_RATE_LIMIT_CLEANUP_INTERVAL,
    max_tracked_ips: int = DEFAULT_RATE_LIMIT_MAX_TRACKED_IPS,
) -> RateLimiter:
    """Create a stateful rate-limiting middleware instance."""
    return RateLimiter(
        max_requests=max_requests,
        window_seconds=window_seconds,
        cleanup_interval=cleanup_interval,
        max_tracked_ips=max_tracked_ips,
    )



================================================
FILE: src/pywebtransport/server/router.py
================================================
"""Request router for path-based session handling."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any, Pattern

from pywebtransport.session import WebTransportSession
from pywebtransport.utils import get_logger

__all__: list[str] = ["RequestRouter", "SessionHandler"]

type SessionHandler = Callable[..., Awaitable[None]]

logger = get_logger(name=__name__)


class RequestRouter:
    """Route session requests to handlers based on path matching."""

    def __init__(self) -> None:
        """Initialize the request router."""
        self._routes: dict[str, SessionHandler] = {}
        self._pattern_routes: list[tuple[Pattern[str], SessionHandler]] = []
        self._default_handler: SessionHandler | None = None

    def route_request(self, *, session: WebTransportSession) -> tuple[SessionHandler, dict[str, Any]] | None:
        """Route a request to the appropriate handler based on the session's path."""
        path = session.path

        if path in self._routes:
            return (self._routes[path], {})

        for pattern, pattern_handler in self._pattern_routes:
            match = pattern.fullmatch(path)
            if match is not None:
                return (pattern_handler, match.groupdict())

        if self._default_handler is not None:
            return (self._default_handler, {})

        return None

    def add_pattern_route(self, *, pattern: str, handler: SessionHandler) -> None:
        """Add a route for a regular expression pattern."""
        try:
            compiled_pattern = re.compile(pattern)
            self._pattern_routes.append((compiled_pattern, handler))
            logger.debug("Added pattern route: %s", pattern)
        except re.error as e:
            logger.error("Invalid regex pattern '%s': %s", pattern, e, exc_info=True)
            raise

    def add_route(self, *, path: str, handler: SessionHandler, override: bool = False) -> None:
        """Add a route for an exact path match."""
        if path in self._routes and not override:
            raise ValueError(f"Route for path '{path}' already exists.")
        self._routes[path] = handler
        logger.debug("Added route: %s", path)

    def remove_pattern_route(self, *, pattern: str) -> None:
        """Remove a route for a regular expression pattern."""
        original_len = len(self._pattern_routes)
        self._pattern_routes = [(p, h) for p, h in self._pattern_routes if p.pattern != pattern]
        if len(self._pattern_routes) < original_len:
            logger.debug("Removed pattern route: %s", pattern)

    def remove_route(self, *, path: str) -> None:
        """Remove a route for an exact path match."""
        if path in self._routes:
            del self._routes[path]
            logger.debug("Removed route: %s", path)

    def set_default_handler(self, *, handler: SessionHandler) -> None:
        """Set a default handler for routes that are not matched."""
        self._default_handler = handler
        logger.debug("Set default handler")

    def get_all_routes(self) -> dict[str, SessionHandler]:
        """Get a copy of all registered exact-match routes."""
        return self._routes.copy()

    def get_route_handler(self, *, path: str) -> SessionHandler | None:
        """Get the handler for a specific path (exact match only)."""
        return self._routes.get(path)

    def get_route_stats(self) -> dict[str, Any]:
        """Get statistics about the configured routes."""
        return {
            "exact_routes": len(self._routes),
            "pattern_routes": len(self._pattern_routes),
            "has_default_handler": self._default_handler is not None,
        }



================================================
FILE: src/pywebtransport/server/server.py
================================================
"""Core server implementation for accepting WebTransport connections."""

from __future__ import annotations

import asyncio
from asyncio import BaseTransport, DatagramTransport
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast

from aioquic.asyncio.server import QuicServer

from pywebtransport._adapter.server import WebTransportServerProtocol, create_server
from pywebtransport.config import ServerConfig
from pywebtransport.connection import WebTransportConnection
from pywebtransport.events import Event, EventEmitter
from pywebtransport.exceptions import ServerError
from pywebtransport.manager.connection import ConnectionManager
from pywebtransport.manager.session import SessionManager
from pywebtransport.types import Address, ConnectionState, EventType, SessionState
from pywebtransport.utils import get_logger, get_timestamp

__all__ = ["ServerDiagnostics", "ServerStats", "WebTransportServer"]

logger = get_logger(name=__name__)


@dataclass(frozen=True, kw_only=True)
class ServerDiagnostics:
    """A structured, immutable snapshot of a server's health."""

    is_serving: bool
    stats: ServerStats
    connection_states: dict[ConnectionState, int]
    max_connections: int
    session_states: dict[SessionState, int]
    certfile_path: str
    cert_file_exists: bool
    keyfile_path: str
    key_file_exists: bool

    @property
    def issues(self) -> list[str]:
        """Get a list of potential issues based on the current diagnostics."""
        issues: list[str] = []
        stats_dict = self.stats.to_dict()

        if not self.is_serving:
            issues.append("Server is not currently serving.")

        total_attempts = stats_dict.get("total_connections_attempted", 0)
        success_rate = stats_dict.get("success_rate", 1.0)
        connections_rejected = stats_dict.get("connections_rejected", 0)

        if total_attempts > 20 and success_rate < 0.9:
            issues.append(f"High connection rejection rate: {connections_rejected}/{total_attempts}")

        active_connections = self.connection_states.get(ConnectionState.CONNECTED, 0)
        if self.max_connections > 0 and (active_connections / max(1, self.max_connections)) > 0.9:
            issues.append(f"High connection usage: {active_connections / self.max_connections:.1%}")

        if self.certfile_path and not self.cert_file_exists:
            issues.append(f"Certificate file not found: {self.certfile_path}")
        if self.keyfile_path and not self.key_file_exists:
            issues.append(f"Key file not found: {self.keyfile_path}")

        return issues


@dataclass(kw_only=True)
class ServerStats:
    """Represent statistics for the server."""

    start_time: float | None = None
    connections_accepted: int = 0
    connections_rejected: int = 0
    connection_errors: int = 0
    protocol_errors: int = 0

    @property
    def total_connections_attempted(self) -> int:
        """Get the total number of connections attempted."""
        return self.connections_accepted + self.connections_rejected

    @property
    def success_rate(self) -> float:
        """Get the connection success rate."""
        total = self.total_connections_attempted
        if total == 0:
            return 1.0
        return self.connections_accepted / total

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to a dictionary."""
        data = asdict(obj=self)
        data["total_connections_attempted"] = self.total_connections_attempted
        data["success_rate"] = self.success_rate
        data["uptime"] = (get_timestamp() - self.start_time) if self.start_time is not None else 0.0
        return data


class WebTransportServer(EventEmitter):
    """Manage the lifecycle and connections for the WebTransport server."""

    def __init__(self, *, config: ServerConfig | None = None) -> None:
        """Initialize the WebTransport server."""
        self._config = config if config is not None else ServerConfig()
        self._config.validate()
        super().__init__(
            max_queue_size=self._config.max_event_queue_size,
            max_listeners=self._config.max_event_listeners,
            max_history=self._config.max_event_history_size,
        )
        self._serving, self._closing = False, False
        self._server: QuicServer | None = None
        self._connection_manager = ConnectionManager(max_connections=self._config.max_connections)
        self._session_manager = SessionManager(max_sessions=self._config.max_sessions)
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._stats = ServerStats()
        self._shutdown_event = asyncio.Event()
        self._close_task: asyncio.Task[None] | None = None
        logger.info("WebTransport server initialized.")

    @property
    def config(self) -> ServerConfig:
        """Get the server's configuration object."""
        return self._config

    @property
    def connection_manager(self) -> ConnectionManager:
        """Get the server's connection manager instance."""
        return self._connection_manager

    @property
    def is_serving(self) -> bool:
        """Check if the server is currently serving."""
        return self._serving

    @property
    def local_address(self) -> Address | None:
        """Get the local address the server is bound to."""
        if self._server is not None:
            try:
                transport = self._server._transport
                if transport is not None:
                    return cast(Address | None, transport.get_extra_info("sockname"))
            except (OSError, AttributeError):
                return None
        return None

    @property
    def session_manager(self) -> SessionManager:
        """Get the server's session manager instance."""
        return self._session_manager

    async def __aenter__(self) -> Self:
        """Enter the async context for the server."""
        await self._connection_manager.__aenter__()
        await self._session_manager.__aenter__()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Exit the async context and close the server."""
        await self.close()

    async def close(self) -> None:
        """Gracefully shut down the server and its resources."""
        if self._close_task is not None and not self._close_task.done():
            await self._close_task
            return

        if not self._serving:
            return

        self._close_task = asyncio.create_task(coro=self._close_implementation())
        await self._close_task

    async def listen(self, *, host: str | None = None, port: int | None = None) -> None:
        """Start the server and begin listening for connections."""
        if self._serving:
            raise ServerError(message="Server is already serving")

        bind_host = host if host is not None else self._config.bind_host
        bind_port = port if port is not None else self._config.bind_port

        logger.info("Starting WebTransport server on %s:%s", bind_host, bind_port)

        try:
            self._server = await create_server(
                host=bind_host, port=bind_port, config=self._config, connection_creator=self._create_connection_callback
            )
            self._serving = True
            self._stats.start_time = get_timestamp()
            logger.info("WebTransport server listening on %s", self.local_address)
        except FileNotFoundError as e:
            logger.critical("Certificate/Key file error: %s", e)
            raise ServerError(message=f"Certificate/Key file error: {e}") from e
        except Exception as e:
            logger.critical("Failed to start server: %s", e, exc_info=True)
            raise ServerError(message=f"Failed to start server: {e}") from e

    async def serve_forever(self) -> None:
        """Run the server indefinitely until interrupted."""
        if not self._serving or self._server is None:
            raise ServerError(message="Server is not listening")

        logger.info("Server is running. Press Ctrl+C to stop.")
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("serve_forever cancelled.")
        except Exception as e:
            logger.error("Error during serve_forever wait: %s", e)
        finally:
            logger.info("serve_forever loop finished.")

    async def diagnostics(self) -> ServerDiagnostics:
        """Get a snapshot of the server's diagnostics and statistics."""
        async with asyncio.TaskGroup() as tg:
            conn_task = tg.create_task(coro=self._connection_manager.get_all_resources())
            sess_task = tg.create_task(coro=self._session_manager.get_all_resources())

        connections = conn_task.result()
        sessions = sess_task.result()
        connection_states = Counter(conn.state for conn in connections)
        session_states = Counter(sess.state for sess in sessions)

        cert_path = self.config.certfile
        key_path = self.config.keyfile

        def check_files() -> tuple[bool, bool]:
            c_exists = Path(cert_path).exists() if cert_path is not None and cert_path else False
            k_exists = Path(key_path).exists() if key_path is not None and key_path else False
            return c_exists, k_exists

        loop = asyncio.get_running_loop()
        cert_exists, key_exists = await loop.run_in_executor(None, check_files)

        return ServerDiagnostics(
            is_serving=self.is_serving,
            stats=self._stats,
            connection_states=dict(connection_states),
            max_connections=self.config.max_connections,
            session_states=dict(session_states),
            certfile_path=cert_path if cert_path is not None else "",
            cert_file_exists=cert_exists,
            keyfile_path=key_path if key_path is not None else "",
            key_file_exists=key_exists,
        )

    async def _close_implementation(self) -> None:
        """Internal implementation of server closure."""
        logger.info("Closing WebTransport server...")
        self._serving = False
        self._closing = True

        for task in self._background_tasks:
            if not task.done():
                task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(coro=self._connection_manager.shutdown())
                tg.create_task(coro=self._session_manager.shutdown())
        except* Exception as eg:
            logger.error("Errors occurred during manager shutdown: %s", eg.exceptions, exc_info=eg)

        if self._server is not None:
            self._server.close()

        self._shutdown_event.set()

        self._closing = False
        logger.info("WebTransport server closed.")

    def _create_connection_callback(self, protocol: WebTransportServerProtocol, transport: BaseTransport) -> None:
        """Create a new WebTransportConnection from the protocol."""
        logger.debug("Creating WebTransportConnection via callback.")

        if not hasattr(transport, "sendto"):
            logger.error("Received transport without 'sendto' method: %s", type(transport).__name__)
            if not transport.is_closing():
                transport.close()
            return

        try:
            connection = WebTransportConnection.accept(
                transport=cast(DatagramTransport, transport), protocol=protocol, config=self._config
            )
            task = asyncio.create_task(coro=self._initialize_and_register_connection(connection=connection))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except Exception as e:
            logger.error("Error creating WebTransportConnection in callback: %s", e, exc_info=True)
            if not transport.is_closing():
                transport.close()

    async def _initialize_and_register_connection(self, connection: WebTransportConnection) -> None:
        """Initialize connection engine and register with manager."""

        async def forward_session_request(event: Event) -> None:
            event_data = event.data.copy() if isinstance(event.data, dict) else {}
            event_data["connection"] = connection

            session = event_data.get("session")
            if session is not None:
                try:
                    await self._session_manager.add_session(session=session)
                except Exception as e:
                    logger.error("Failed to register session %s: %s", session.session_id, e)

            await self.emit(event_type=EventType.SESSION_REQUEST, data=event_data)

        connection.events.on(event_type=EventType.SESSION_REQUEST, handler=forward_session_request)

        try:
            await self._connection_manager.add_connection(connection=connection)
            self._stats.connections_accepted += 1
            logger.info("New connection registered: %s", connection.connection_id)
        except Exception as e:
            self._stats.connections_rejected += 1
            self._stats.connection_errors += 1
            logger.error("Failed to initialize/register new connection: %s", e, exc_info=True)
            connection.events.off(event_type=EventType.SESSION_REQUEST, handler=forward_session_request)
            if not connection.is_closed:
                await connection.close()
        else:

            async def cleanup_listener(event: Event) -> None:
                connection.events.off(event_type=EventType.SESSION_REQUEST, handler=forward_session_request)

            connection.events.once(event_type=EventType.CONNECTION_CLOSED, handler=cleanup_listener)

    def __str__(self) -> str:
        """Format a concise summary of server information for logging."""
        status = "serving" if self.is_serving else "stopped"
        address_info = self.local_address
        address_str = f"{address_info[0]}:{address_info[1]}" if address_info is not None else "unknown"
        conn_count = len(self._connection_manager)
        sess_count = len(self._session_manager)
        return (
            f"WebTransportServer(status={status}, "
            f"address={address_str}, "
            f"connections={conn_count}, "
            f"sessions={sess_count})"
        )


