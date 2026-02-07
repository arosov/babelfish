# Specification - Configuration Management & Frontend Interaction

## Overview
This track introduces a robust configuration management system to Babelfish, enabling real-time interaction with a Kotlin-based frontend. Babelfish will serve as the "brain," maintaining a source of truth for defaults and hardware-optimized settings, while allowing the frontend to reconfigure the system via WebTransport.

## Functional Requirements
- **Pydantic-Based Schema:** Implement strict configuration models using Pydantic for validation, serialization, and default management.
- **WebTransport Configuration API:**
    - Babelfish must broadcast its current configuration and hardware-discovered defaults upon client connection.
    - Implement a command handler for `update_config` messages sent from the frontend.
- **Persistence:** Automatically persist valid configuration changes to `config.json`.
- **Hot-Reloading:**
    - Immediate application of non-critical settings (quality presets, VAD sensitivity, UI formatting, stop-words).
    - Signal "restart required" for critical hardware changes (e.g., GPU selection) that cannot be hot-swapped safely.
- **Exposed Categories:**
    - **Hardware:** GPU selection, VRAM limits, audio device selection.
    - **Pipeline:** Quality/latency presets for Ghost (Fast) and Anchor (Solid) passes.
    - **Voice Control:** Wake-word settings (sensitivity, model) and stop-word lists.
    - **UI/Display:** Formatting preferences and output verbosity.

## Non-Functional Requirements
- **Robustness:** Invalid configuration updates from the frontend must be rejected with clear error messages, leaving the current state untouched.
- **Atomicity:** Saving to `config.json` should be atomic to prevent file corruption.

## Acceptance Criteria
- [ ] Babelfish successfully loads configuration from `config.json` using Pydantic models.
- [ ] The frontend receives the current configuration immediately after WebTransport handshake.
- [ ] Sending a valid `update_config` message via WebTransport updates the internal state and the `config.json` file.
- [ ] Changes to presets or UI formatting are reflected in the pipeline behavior without a process restart.
- [ ] Sending an invalid configuration (e.g., wrong data types) results in an error message sent back to the client.

## Out of Scope
- Implementation of the Kotlin frontend UI itself.
- High-level orchestration of multi-server configurations.