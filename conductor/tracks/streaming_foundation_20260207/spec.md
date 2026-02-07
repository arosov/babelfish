# Specification: Streaming Foundation (parakeet-stream)

## Overview
This track focuses on establishing the core audio pipeline for Babelfish using `parakeet-stream`. The goal is to create a standalone, portable implementation accessible via a single `uv` command. This iteration moves away from a server-client architecture to focus on a high-performance, local-first streaming experience.

## Functional Requirements
- **Entry Point:** A `babelfish.py` script at the project root.
- **Modular Architecture:** `babelfish.py` should act as a clean orchestrator. Logic for audio handling, STT processing, and display management should be decoupled into separate modules (e.g., in a `src/` or package structure) to avoid a "god script" pattern.
- **Distribution:** Support execution via a `uv` one-liner (e.g., `uv run babelfish.py`) that handles dependency installation and model downloads automatically.
- **Audio Input:** Real-time microphone capture using `parakeet-stream`'s native capabilities.
- **STT Engine:** Integration of `parakeet-stream` using the **Fast** preset for ultra-low latency.
- **Terminal UI:** 
    - Real-time word-by-word streaming display (live-updating the current line).
    - Clear visual feedback for finalized transcriptions.

## Non-Functional Requirements
- **Low Latency:** Optimized for immediate transcription feedback.
- **Portability:** Minimal manual setup; dependencies and models should be managed by the script/uv.
- **Hardware Awareness:** Basic detection of CUDA availability to prefer GPU acceleration if present.

## Acceptance Criteria
- [ ] Executing `uv run babelfish.py` successfully initializes the microphone.
- [ ] Transcription starts automatically after initialization.
- [ ] The terminal displays words as they are recognized in real-time.
- [ ] Finalized segments are printed clearly without duplication.
- [ ] The script handles Ctrl+C gracefully, stopping the stream and cleaning up resources.
- [ ] Code is organized into logical modules rather than being contained entirely within `babelfish.py`.

## Out of Scope
- WebTransport server/client communication.
- Multi-pass (Shadow STT) refinement.
- LLM post-processing.
- Audio file or System Loopback input.
