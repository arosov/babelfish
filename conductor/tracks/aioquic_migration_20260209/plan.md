# Implementation Plan - aioquic_migration_20260209

Migrate Babelfish server from `pywebtransport` to a raw `aioquic` implementation for better stability and control.

## Phase 1: Environment Cleanup and Preparation [checkpoint: f2f0a22]
- [x] Task: Remove `pywebtransport` dependency. ddd9351
    - [x] Remove `pywebtransport` from `pyproject.toml` and any lock files.
    - [x] Uninstall the package from the local development environment.
    - [x] Clean up any unused imports or legacy `pywebtransport` boilerplate in `src/babelfish_stt/server.py`.
- [x] Task: Install `aioquic`. 3aa3395
    - [x] Add `aioquic` to `pyproject.toml`.
    - [x] Run `uv sync` or equivalent to update the environment.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Environment Cleanup and Preparation' (Protocol in workflow.md) f2f0a22

## Phase 2: Core Protocol Implementation [checkpoint: 59b0adc]
- [x] Task: Create `BabelfishH3Protocol` in `src/babelfish_stt/server.py`. b4046a1
    - [x] Write tests for the protocol wrapper (mocking `aioquic` events).
    - [x] Implement `BabelfishH3Protocol` inheriting from `QuicConnectionProtocol`.
    - [x] Initialize `H3Connection` within the protocol.
    - [x] Implement `quic_event_received` to route events to the H3 state machine.
- [x] Task: Implement Extended CONNECT Handshake. b4046a1
    - [x] Write tests for the `HeadersReceived` handling logic.
    - [x] Handle `HeadersReceived` in the protocol, checking for `:protocol: webtransport`.
    - [x] Send `200 OK` response headers with the required `sec-webtransport-http3-draft` header.
- [x] Task: Implement Bidirectional Stream Handling. b4046a1
    - [x] Write tests for data exchange over bidirectional streams.
    - [x] Handle `WebTransportStreamDataReceived` and route data to `BabelfishServer`.
    - [x] Implement a method in the protocol to send data back to the client over a specific stream.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Core Protocol Implementation' (Protocol in workflow.md) 59b0adc

## Phase 3: Server Integration and Verification [checkpoint: cea8992]
- [x] Task: Refactor `BabelfishServer.start` to use `aioquic.asyncio.serve`. e22be5f
    - [x] Configure `QuicConfiguration` with the parameters specified in the migration guide (`alpn_protocols=["h3"]`, high flow control limits).
    - [x] Replace the `pywebtransport` server initialization with `serve(...)`.
    - [x] Ensure the existing `BabelfishServer` logic for `/config` is hooked into the new protocol.
- [x] Task: End-to-End Verification. 12a5865
    - [x] Run the server and verify it accepts connections on the configured port.
    - [x] Use a test client (or `kwtransport` if available) to verify the full handshake and config exchange.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Server Integration and Verification' (Protocol in workflow.md) cea8992
