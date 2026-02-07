# Plan: Configuration Management & Frontend Interaction

This plan outlines the integration of a Pydantic-based configuration system with WebTransport support for real-time frontend interaction.

## Phase 1: Core Configuration Schema & Persistence [checkpoint: eaec2b3]
Establish the foundational Pydantic models and the logic for loading, saving, and validating configuration.

- [x] Task: Define Pydantic models for all configuration categories (Hardware, Pipeline, Voice, UI) in `src/babelfish_stt/config.py`. 3f2b4ef
- [x] Task: Write tests for configuration validation, default values, and serialization. 05c3c69
- [x] Task: Implement atomic save/load logic in a new `ConfigManager` class. 0f65456
- [x] Task: Write tests for configuration persistence to `config.json`. 0f65456
- [x] Task: Conductor - User Manual Verification 'Phase 1: Core Configuration Schema & Persistence' (Protocol in workflow.md) eaec2b3

## Phase 2: WebTransport Configuration API
Implement the communication layer for exchanging configuration data with the frontend.

- [x] Task: Update the WebTransport server to send the current configuration on client connection. 5c48bb9
- [ ] Task: Implement the `update_config` command handler in the WebTransport message loop.
- [ ] Task: Write integration tests for sending and receiving configuration updates over WebTransport.
- [ ] Task: Implement error reporting to the client when validation fails.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: WebTransport Configuration API' (Protocol in workflow.md)

## Phase 3: Hot-Reloading Logic
Integrate the configuration system with the STT pipeline to apply changes dynamically.

- [ ] Task: Implement a "Reconfigurable" interface or mixin for pipeline components.
- [ ] Task: Wire up hot-reloadable settings (presets, VAD, UI) to update components in real-time.
- [ ] Task: Implement the "Restart Required" signaling logic for critical hardware changes.
- [ ] Task: Write tests for dynamic setting updates without process restart.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Hot-Reloading Logic' (Protocol in workflow.md)