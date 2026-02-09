# Architectural Guide: Migrating from pywebtransport to raw aioquic

This document outlines the strategy for replacing the high-level `pywebtransport` library with a direct `aioquic` implementation. This transition is motivated by the need for granular control over QUIC transport parameters to ensure stable communication with the `kwtransport` (Kotlin/Rust wtransport) client on localhost.

## 1. Context & Motivation
`pywebtransport` provides a convenient abstraction but hides the low-level QUIC/H3 state machine. When facing "Loss Detection" spam or "Blocked Stream" issues on `127.0.0.1`, direct access to `aioquic` allows us to:
- Manually grant flow control credits (`MAX_DATA` / `MAX_STREAM_DATA`).
- Fine-tune MTU and Datagram sizes to match the `wtransport` Rust backend expectations.
- Debug the exact frames (e.g., `ACK_FREQUENCY`) being exchanged during the handshake.

## 2. Interop with `kwtransport` (wtransport)
The `wtransport` Rust crate is strictly compliant with the WebTransport over HTTP/3 draft. To satisfy a `kwtransport` client, the raw `aioquic` server must:
1.  **Negotiate ALPN `h3`**: The client will fail immediately if QUIC ALPN is not strictly `h3`.
2.  **Support Extended CONNECT**: WebTransport is established via an HTTP/3 `CONNECT` request with the `:protocol: webtransport` pseudo-header.
3.  **Handle SETTINGS**: The server must send `SETTINGS_ENABLE_CONNECT_PROTOCOL = 1` and `SETTINGS_H3_DATAGRAM = 1`.

## 3. Implementation Strategy

### A. Transport Configuration
Initialize `QuicConfiguration` with aggressive defaults for local development. `wtransport` can be sensitive to small initial windows.

```python
from aioquic.quic.configuration import QuicConfiguration

quic_config = QuicConfiguration(
    is_client=False,
    alpn_protocols=["h3"],
    # High initial limits prevent the "Blocked Stream" timeout
    max_data=10**7,
    max_stream_data=10**6,
    # Standard MTU for local loopback
    max_datagram_size=1200,
    idle_timeout=30.0
)
```

### B. The Protocol Wrapper
To keep the codebase clean, encapsulate `aioquic` logic in a `BabelfishH3Protocol`. This class handles the translation of QUIC frames into WebTransport events.

```python
from aioquic.asyncio import QuicConnectionProtocol
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived, WebTransportStreamFrameReceived

class BabelfishH3Protocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # H3Connection manages the HTTP/3 state machine on top of QUIC
        self._h3 = H3Connection(self._quic)
        self._session_id = None

    def quic_event_received(self, event):
        # Feed all QUIC events (StreamData, ConnectionTerminated) to H3
        for h3_event in self._h3.handle_event(event):
            self._handle_h3_event(h3_event)

    def _handle_h3_event(self, event):
        if isinstance(event, HeadersReceived):
            # 1. Inspect headers for ':protocol': 'webtransport'
            # 2. If path is '/config', send 200 OK
            self._h3.send_headers(
                stream_id=event.stream_id,
                headers=[(b":status", b"200"), (b"sec-webtransport-http3-draft", b"draft02")]
            )
            self._session_id = event.stream_id
            
        elif isinstance(event, WebTransportStreamFrameReceived):
            # This is where your actual Babelfish logic hooks in
            # event.session_id will match the CONNECT stream_id
            self.on_data_received(event.stream_id, event.data)
```

### C. Replacing BabelfishServer.start
The entry point in `server.py` should transition from `ServerApp` to the standard `asyncio` UDP server pattern.

```python
from aioquic.asyncio import serve

async def start(self):
    # This replaces self.app.serve(...)
    await serve(
        host=self.server_config.host,
        port=self.server_config.port,
        configuration=self.quic_config,
        create_protocol=BabelfishH3Protocol, # Pass your wrapper here
    )
```

## 4. Keeping it "Clean" (Avoiding the Mess)
1.  **Decouple H3 from Logic**: The `BabelfishH3Protocol` should not contain business logic. It should emit events or call a callback-interface implemented by the `BabelfishServer` class.
2.  **Explicit Handshake State**: Maintain a clear state machine for the session (Handshaking -> Active -> Closed). `kwtransport` will close the connection if it receives stream data before the `200 OK` headers are fully processed.
3.  **Buffer Management**: `aioquic` is essentially non-blocking but requires you to manage your own `asyncio.Queue` if you want to implement high-level `read()`/`write()` calls like those in `pywebtransport`.

## 5. Debugging Checklist
- **`kwtransport` error `UnknownProtocol`**: Check if ALPN is `h3`.
- **`kwtransport` error `SessionRejected`**: Ensure the `:status: 200` headers are sent via `H3Connection.send_headers`.
- **Packet Loss on 127.0.0.1**: Disable `iptables` or `nftables` UDP rate-limiting. Some Linux distributions treat high-frequency UDP on loopback as a potential DoS.
