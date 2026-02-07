# Implementation Plan: Voice-Activated Control (Wake-Word & Stop-Word)

This plan outlines the steps to integrate local wake-word detection and text-based stop-word control into Babelfish.

## Phase 1: Wake-Word Integration (openWakeWord) [checkpoint: 3f0fb58]
Integrate the `openWakeWord` engine to enable starting transcription via voice.

- [x] Task: Install `openWakeWord` and necessary ONNX dependencies. d18665f
- [x] Task: Implement `WakeWordEngine` wrapper in `src/babelfish_stt/wakeword.py` to handle ONNX model loading and inference. 1825eda
- [x] Task: Write Tests: Verify `WakeWordEngine` correctly detects keywords in sample audio buffers. 1825eda
- [x] Task: Implement: Develop the `WakeWordEngine` logic. 1825eda
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Wake-Word Integration' (Protocol in workflow.md)

## Phase 2: Stop-Word Logic & State Management [checkpoint: e8f5431]
Implement the text-based stop-word detection and the IDLE/LISTENING state machine.

- [x] Task: Implement `StopWordDetector` in `src/babelfish_stt/pipeline.py` with strict matching logic. cdb29cb
- [x] Task: Write Tests: Verify `StopWordDetector` identifies stop phrases in various transcript strings. cdb29cb
- [x] Task: Implement: Develop the `StopWordDetector` logic. cdb29cb
- [x] Task: Update `Pipeline` base class and implementations to support an `IDLE` state. cdb29cb
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Stop-Word & State' (Protocol in workflow.md)

## Phase 3: CLI Integration & Orchestration [checkpoint: 94db750]
Update the main entry point to support new flags and orchestrate the state transitions.

- [x] Task: Update `main.py` to support `--wakeword` and `--stopword` flags. e6d7fa6
- [x] Task: Refactor `run_babelfish` to handle the `IDLE` state (running WakeWord detection) and `LISTENING` state (running STT). e6d7fa6
- [x] Task: Write Tests: Verify CLI arguments are correctly parsed and passed to the orchestration loop. e6d7fa6
- [x] Task: Implement: Update `main.py` and orchestration logic. e6d7fa6
- [ ] Task: Conductor - User Manual Verification 'Phase 3: CLI & Orchestration' (Protocol in workflow.md)

## Phase 4: Logging & E2E Verification
Finalize the feature with detailed logging and end-to-end testing.

- [x] Task: Implement event logging for state changes, including timestamps and confidence scores. 73b425c
- [x] Task: Write Tests: Perform E2E tests verifying the full lifecycle (Launch IDLE -> Wake-Word -> LISTENING -> Stop-Word -> IDLE). 73b425c
- [x] Task: Implement: Finalize logging and perform E2E fixes. 73b425c
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Logging & E2E' (Protocol in workflow.md)