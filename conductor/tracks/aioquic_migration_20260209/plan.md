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

## Phase 2: Core Protocol Implementation
- [ ] Task: Create `BabelfishH3Protocol` in `src/babelfish_stt/server.py`.
    - [ ] Write tests for the protocol wrapper (mocking `aioquic` events).
    - [ ] Implement `BabelfishH3Protocol` inheriting from `QuicConnectionProtocol`.
    - [ ] Initialize `H3Connection` within the protocol.
    - [ ] Implement `quic_event_received` to route events to the H3 state machine.
- [ ] Task: Implement Extended CONNECT Handshake.
    - [ ] Write tests for the `HeadersReceived` handling logic.
    - [ ] Handle `HeadersReceived` in the protocol, checking for `:protocol: webtransport`.
    - [ ] Send `200 OK` response headers with the required `sec-webtransport-http3-draft` header.
- [ ] Task: Implement Bidirectional Stream Handling.
    - [ ] Write tests for data exchange over bidirectional streams.
    - [ ] Handle `WebTransportStreamFrameReceived` and route data to `BabelfishServer`.
    - [ ] Implement a method in the protocol to send data back to the client over a specific stream.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Core Protocol Implementation' (Protocol in workflow.md)

## Phase 3: Server Integration and Verification
- [ ] Task: Refactor `BabelfishServer.start` to use `aioquic.asyncio.serve`.
    - [ ] Configure `QuicConfiguration` with the parameters specified in the migration guide (`alpn_protocols=["h3"]`, high flow control limits).
    - [ ] Replace the `pywebtransport` server initialization with `serve(...)`.
    - [ ] Ensure the existing `BabelfishServer` logic for `/config` is hooked into the new protocol.
- [ ] Task: End-to-End Verification.
    - [ ] Run the server and verify it accepts connections on the configured port.
    - [ ] Use a test client (or `kwtransport` if available) to verify the full handshake and config exchange.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Server Integration and Verification' (Protocol in workflow.md)
