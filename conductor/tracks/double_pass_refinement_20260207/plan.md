# Implementation Plan: Two-Pass Refinement System (Optional)

This plan outlines the steps to implement a togglable two-pass transcription system, ensuring coexistence with the existing single-pass pipeline.

## Phase 1: Mode Selection & Orchestration Refactor
Enable selecting between Single-Pass and Double-Pass modes via CLI/Configuration.

- [x] Task: Update `main.py` to support a `--double-pass` flag using `argparse`. 226f46e
- [x] Task: Refactor the main loop to delegate to specialized `SinglePassPipeline` or `DoublePassPipeline` handlers. c89bce5
- [ ] Task: Verify the `SessionStart` hook successfully injects technical context and the model uses it to answer basic architectural questions.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Mode Selection' (Protocol in workflow.md)

## Phase 2: Double-Pass Engine & History
Extend the engine and buffer management to support refinements.

- [ ] Task: Update `STTEngine` to support rapid preset switching (`realtime` <-> `balanced`) and context-aware `transcribe` calls.
- [ ] Task: Implement `HistoryBuffer` to maintain the 4-second sliding window required for Pass 2.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Engine & History' (Protocol in workflow.md)

## Phase 3: Refinement Logic & Alignment
Implement the core refinement triggers and the contextual merge logic.

- [ ] Task: Implement `HybridTrigger` (2s timer + VAD pause) to activate Pass 2.
- [ ] Task: Implement `AlignmentManager` to handle "Contextual Merge" (using last words of Pass 2 as Pass 1 prefix context).
- [ ] Task: Implement the "Catch-up" mechanism to process backlogged audio after a Pass 2 compute.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Refinement & Alignment' (Protocol in workflow.md)

## Phase 4: UI Styles & E2E Verification
Finalize the visual representation and ensure both modes work flawlessly.

- [ ] Task: Update `TerminalDisplay` to support ANSI styles (e.g., dimmed for Ghost, bold for Anchor).
- [ ] Task: Perform E2E tests verifying that switching modes works as expected and Double-Pass is seamless.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: UI & E2E' (Protocol in workflow.md)
