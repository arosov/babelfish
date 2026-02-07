# Implementation Plan: Streaming Foundation (parakeet-stream)

This plan outlines the steps to create a modular, low-latency STT pipeline using `parakeet-stream`, executable via `uv`.

## Phase 1: Project Scaffolding & Dependency Management [checkpoint: 348da92]
Establish the project structure and configure `uv` for automatic dependency and model management.

- [x] Task: Initialize `pyproject.toml` with `uv` to manage dependencies (including `parakeet-stream`). 71f8466
- [x] Task: Create the project directory structure (`babelfish_stt/` package and `babelfish.py` entry point). 03af513
- [x] Task: Conductor - User Manual Verification 'Phase 1: Project Scaffolding' (Protocol in workflow.md) 348da92

## Phase 2: Core STT Module Implementation
Implement the decoupled logic for hardware detection and `parakeet-stream` orchestration.

- [x] Task: Implement `hardware.py` module for CUDA detection and basic resource reporting. 7139650
- [x] Task: Implement `engine.py` module to encapsulate `parakeet-stream` initialization and "Fast" preset configuration. 1b1dc2c
- [x] Task: Implement `audio.py` module to manage microphone streams using `parakeet-stream`'s native interface. eecc6b6
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Core STT Module' (Protocol in workflow.md)

## Phase 3: Orchestration & Terminal UI
Connect the modules in `babelfish.py` and implement the real-time streaming display logic.

- [ ] Task: Implement `display.py` module for terminal-based, word-by-word streaming updates.
- [ ] Task: Implement the main loop in `babelfish.py` to orchestrate audio capture, STT processing, and display.
- [ ] Task: Implement graceful shutdown (Ctrl+C) and resource cleanup.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Orchestration & UI' (Protocol in workflow.md)

## Phase 4: Verification & Portability
Ensure the "uv one-liner" works as expected and the pipeline meets performance goals.

- [ ] Task: Verify the `uv run babelfish.py` command downloads models and starts transcription automatically.
- [ ] Task: Perform end-to-end testing of real-time transcription latency and terminal output accuracy.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Verification' (Protocol in workflow.md)
