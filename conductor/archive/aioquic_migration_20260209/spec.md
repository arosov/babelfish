# Specification - Track: aioquic_migration_20260209

## Overview
This track involves migrating the Babelfish server's communication layer from `pywebtransport` to a raw `aioquic` implementation. This change is driven by the need for granular control over QUIC transport parameters and strict HTTP/3 compliance to ensure stable interoperability with the `kwtransport` (Kotlin/Rust) client.

## Goals
- Replace the high-level `pywebtransport` abstraction with a direct `aioquic` and `H3Connection` implementation.
- Achieve strict compatibility with `kwtransport` by implementing the Extended CONNECT protocol.
- Simplify the dependency tree by removing `pywebtransport`.

## Functional Requirements
- **ALPN Negotiation:** The server must strictly negotiate `h3` during the QUIC handshake.
- **Extended CONNECT Support:** Implement the HTTP/3 `CONNECT` method with the `:protocol: webtransport` pseudo-header to establish sessions.
- **Bidirectional Streams:** Support bidirectional streams specifically for the `/config` endpoint to handle newline-delimited JSON configuration exchanges.
- **Direct Server Integration:** The `BabelfishH3Protocol` will receive a reference to the `BabelfishServer` instance and call its methods directly to handle session lifecycle and data events.
- **Aggressive Flow Control:** Configure `QuicConfiguration` with high initial limits (`max_data=10^7`, `max_stream_data=10^6`) to prevent "Blocked Stream" timeouts on localhost.

## Non-Functional Requirements
- **Latency:** Maintain or improve the low-latency characteristics of the communication layer.
- **Robustness:** Ensure proper handling of connection terminations and stream closures to avoid resource leaks.

## Acceptance Criteria
- [ ] `pywebtransport` is removed from `pyproject.toml` and the codebase.
- [ ] The server successfully completes a QUIC handshake with ALPN `h3`.
- [ ] A `kwtransport` client can successfully establish a WebTransport session via the `/config` path.
- [ ] Configuration updates (client-to-server and server-to-client) work correctly over bidirectional streams.
- [ ] The server handles multiple concurrent connections/sessions if initiated (though the primary use case is 1:1).

## Out of Scope
- Implementation of WebTransport Datagrams (unless required later).
- Implementation of Unidirectional Streams (unless required later).
- Support for multiple ALPN protocols beyond `h3`.
