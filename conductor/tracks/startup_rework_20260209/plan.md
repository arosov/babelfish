# Implementation Plan - Startup Sequence Rework

## Phase 1: Hardware-First Probe & Mic Validation
Refactor the hardware discovery logic to be the first point of entry and enforce strict microphone requirements.

- [x] Task: Create tests for strict hardware probing
    - [x] Write test to verify server exits when no microphone is detected
    - [x] Write test to verify VRAM detection logic correctly reports availability
- [x] Task: Update `HardwareManager` and `main.py` entry point
    - [x] Implement early hardware probing in `main.py`
    - [x] Add microphone existence check and `sys.exit(1)` on failure
- [x] Task: Conductor - User Manual Verification 'Hardware-First Probe & Mic Validation' (Protocol in workflow.md)

## Phase 2: Enhanced Config Validation & Optimal Defaults
Implement the logic to validate `config.json` against current hardware and generate resource-aware defaults.

- [x] Task: Create tests for config validation and default generation
    - [x] Write test to verify invalid JSON triggers default generation
    - [x] Write test to verify missing hardware sections trigger default generation
    - [x] Write test to verify 6GB VRAM threshold for CUDA vs. CPU mode selection
    - [x] Write test to verify generated config is saved to disk immediately
- [x] Task: Refactor `ConfigManager` validation logic
    - [x] Implement integrity checks for JSON and Pydantic models
    - [x] Implement hardware-to-config cross-referencing (mic ID and GPU availability)
    - [x] Implement `generate_optimal_defaults` logic with 6GB VRAM logic and 1-pass mode
- [ ] Task: Conductor - User Manual Verification 'Enhanced Config Validation & Optimal Defaults' (Protocol in workflow.md)

## Phase 3: Orchestration Refactoring
Reorganize the main startup sequence to follow the refined flow.

- [x] Task: Create integration test for the new startup sequence
    - [x] Verify execution order: Hardware -> Config -> WebServer -> Pipeline
- [x] Task: Refactor `Server` and `main.py` for sequential startup
    - [x] Ensure `ServerApp` (WebTransport) starts and is ready before `AudioPipeline` initialization
    - [x] Update logging to provide clear feedback on each phase of startup
- [x] Task: Conductor - User Manual Verification 'Orchestration Refactoring' (Protocol in workflow.md)
