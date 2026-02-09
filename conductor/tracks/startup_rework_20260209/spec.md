# Specification - Startup Sequence Rework

## Overview
This track refactors the Babelfish startup sequence to prioritize hardware availability and resource-aware configuration. The server will act as the "brain" by ensuring that the audio pipeline only starts with a valid configuration that matches the current system state, or by generating a safe "optimal" default.

## Functional Requirements
- **Hardware-First Probe:**
    - Execute `HardwareManager.probe()` before any other logic.
    - Validate microphone availability. Exit with a clear error message if no input device is detected.
    - Report available VRAM for all detected GPUs.
- **Strict Config Validation:**
    - Check for JSON integrity and presence of all required Pydantic models (Hardware, Pipeline, Voice, UI, Server).
    - Validate that configured `device_id` (Audio) and GPU indices are still valid and present.
- **Intelligent Default Generation:**
    - If validation fails, generate a configuration with:
        - `pipeline.mode`: `single_pass`
        - `hardware.device`: `cuda` if any GPU has >= 6GB VRAM, else `cpu`.
    - Automatically select the best available microphone as the default.
- **Persistence:**
    - Save the generated optimal configuration to `config.json` immediately.
- **Orchestration Flow:**
    1. Hardware Detection.
    2. Config Load & Validation.
    3. (If invalid) Generate & Save Defaults.
    4. Start WebTransport Server (allow frontend to connect).
    5. Initialize and Start Audio Pipeline.

## Non-Functional Requirements
- **Robustness:** The server must not enter a "half-started" state where the webserver is up but the pipeline is unconfigured or crashing due to missing hardware.
- **Feedback:** Provide clear console logging during each step of the startup sequence.

## Acceptance Criteria
- [ ] Server crashes gracefully if no microphone is found.
- [ ] Server successfully falls back to CPU mode if a GPU is present but has < 6GB VRAM.
- [ ] Modifying `config.json` to an invalid state (e.g., non-existent audio device) triggers a reset to optimal defaults.
- [ ] Webserver starts before the pipeline to ensure the frontend can receive initialization logs/state.
- [ ] Generated defaults are written to disk.

## Out of Scope
- Dynamic hardware hot-plugging (e.g., plugging in a mic while the server is running).
- Multi-GPU load balancing.
