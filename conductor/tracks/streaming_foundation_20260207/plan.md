# Implementation Plan: Streaming Foundation (parakeet-stream)

This plan outlines the steps to create a modular, low-latency STT pipeline using `parakeet-stream`, executable via `uv`.

## Phase 1: Project Scaffolding & Dependency Management [checkpoint: 348da92]
Establish the project structure and configure `uv` for automatic dependency and model management.

- [x] Task: Initialize `pyproject.toml` with `uv` to manage dependencies (including `parakeet-stream`). 71f8466
- [x] Task: Create the project directory structure (`babelfish_stt/` package and `babelfish.py` entry point). 03af513
- [x] Task: Conductor - User Manual Verification 'Phase 1: Project Scaffolding' (Protocol in workflow.md) 348da92

## Phase 2: Core STT Module Implementation [checkpoint: d2c3ecf]
Implement the decoupled logic for hardware detection and `parakeet-stream` orchestration.

- [x] Task: Implement `hardware.py` module for CUDA detection and basic resource reporting. 7139650
- [x] Task: Implement `engine.py` module to encapsulate `parakeet-stream` initialization and "Fast" preset configuration. 1b1dc2c
- [x] Task: Implement `audio.py` module to manage microphone streams using `parakeet-stream`'s native interface. eecc6b6
- [x] Task: Conductor - User Manual Verification 'Phase 2: Core STT Module' (Protocol in workflow.md) d2c3ecf

## Phase 3: Orchestration & Terminal UI [checkpoint: 40044dd]
Connect the modules in `babelfish.py` and implement the real-time streaming display logic.

- [x] Task: Implement `display.py` module for terminal-based, word-by-word streaming updates. b72d915
- [x] Task: Implement the main loop in `babelfish.py` to orchestrate audio capture, STT processing, and display. 18f10a7
- [x] Task: Implement graceful shutdown (Ctrl+C) and resource cleanup. 18f10a7
- [x] Task: Conductor - User Manual Verification 'Phase 3: Orchestration & UI' (Protocol in workflow.md) 40044dd

## Phase 4: Verification & Portability [checkpoint: da77ce5]
Ensure the "uv one-liner" works as expected and the pipeline meets performance goals.

- [x] Task: Verify the `uv run babelfish.py` command downloads models and starts transcription automatically. da77ce5
- [x] Task: Perform end-to-end testing of real-time transcription latency and terminal output accuracy. da77ce5
- [x] Task: Conductor - User Manual Verification 'Phase 4: Verification' (Protocol in workflow.md) da77ce5

## Implementation Notes: Industry Standard Upgrade
The pipeline was refactored from a simple streaming loop to a robust VAD-driven architecture:
1. **Silero VAD v5** acts as the gatekeeper, segmenting speech into utterances.
2. **soxr Resampling** ensures hardware compatibility by capturing at native rates.
3. **Pulse/PipeWire Priority** ensures the correct system microphone is selected automatically.
4. **Segmented Transcribing** provides the model with full sentence context for maximum accuracy.
