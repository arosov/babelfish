# Implementation Plan - push_config_on_connect_20260209

Refine the Babelfish server to proactively push the configuration only once, upon discovery of the first client-initiated bidirectional stream.

## Phase 1: Logic Refinement
- [x] Task: Update session tracking to identify the "primary" control stream. 59b6c0e
    - [x] Add a `primary_stream_id` or `first_stream_detected` flag to the session state in `BabelfishServer`.
    - [x] Implement logic in `on_data_received` to distinguish between client-initiated bidirectional streams and others.
    - [x] Ensure `send_config_to_stream` is only called automatically for the very first client-initiated bidirectional stream.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Logic Refinement' (Protocol in workflow.md)

## Phase 2: Verification
- [ ] Task: Write automated tests for one-time configuration push.
    - [ ] Create a test case that connects a client and opens multiple bidirectional streams.
    - [ ] Assert that the configuration JSON is received on the first stream.
    - [ ] Assert that subsequent streams do not receive an unsolicited configuration push.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Verification' (Protocol in workflow.md)
