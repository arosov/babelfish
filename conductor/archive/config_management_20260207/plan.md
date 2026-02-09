# Plan: Configuration Management & Frontend Interaction

This plan outlines the integration of a Pydantic-based configuration system with WebTransport support for real-time frontend interaction.

## Phase 1: Core Configuration Schema & Persistence [checkpoint: eaec2b3]
Establish the foundational Pydantic models and the logic for loading, saving, and validating configuration.

- [x] Task: Define Pydantic models for all configuration categories (Hardware, Pipeline, Voice, UI) in `src/babelfish_stt/config.py`. 3f2b4ef
- [x] Task: Write tests for configuration validation, default values, and serialization. 05c3c69
- [x] Task: Implement atomic save/load logic in a new `ConfigManager` class. 0f65456
- [x] Task: Write tests for configuration persistence to `config.json`. 0f65456
- [x] Task: Conductor - User Manual Verification 'Phase 1: Core Configuration Schema & Persistence' (Protocol in workflow.md) eaec2b3

## Phase 2: WebTransport Configuration API [checkpoint: d606e06]
Implement the communication layer for exchanging configuration data with the frontend.

- [x] Task: Update the WebTransport server to send the current configuration on client connection. 5c48bb9
- [x] Task: Implement the `update_config` command handler in the WebTransport message loop. 7b6edf4
- [x] Task: Write integration tests for sending and receiving configuration updates over WebTransport. 7b6edf4
- [x] Task: Implement error reporting to the client when validation fails. 7b6edf4
- [x] Task: Conductor - User Manual Verification 'Phase 2: WebTransport Configuration API' (Protocol in workflow.md) d606e06

## Phase 3: Hot-Reloading Logic [checkpoint: 1e6e2d4]
Integrate the configuration system with the STT pipeline to apply changes dynamically.

- [x] Task: Implement a "Reconfigurable" interface or mixin for pipeline components. 6f6d100
- [x] Task: Wire up hot-reloadable settings (presets, VAD, UI) to update components in real-time. aa99543
- [x] Task: Implement the "Restart Required" signaling logic for critical hardware changes. 8f7c96f
- [x] Task: Write tests for dynamic setting updates without process restart. 8f7c96f
- [x] Task: Conductor - User Manual Verification 'Phase 3: Hot-Reloading Logic' (Protocol in workflow.md) 1e6e2d4