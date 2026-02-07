# Specification: Two-Pass Refinement System (Fast Ghost + Solid Anchor)

## Overview
This track implements a sophisticated two-pass transcription system for Babelfish. It combines ultra-low-latency "Ghost" feedback with periodic high-accuracy "Solid Anchor" refinements. A key requirement is that this system must be **optional**, allowing the user to toggle between the existing robust single-pass pipeline and this new two-pass refinement system.

## Functional Requirements
- **Dual-Pass Orchestration:**
    - **Pass 1 (Fast Ghost):** Uses the `ultra_realtime` or `realtime` preset to generate immediate, word-by-word feedback (target latency: ~300-500ms).
    - **Pass 2 (Solid Anchor):** Periodically switches the engine to the `balanced` preset to refine the recent audio history (target latency: ~2s).
- **Technical Context Injection (SessionStart Hook):**
    - The system must include a `SessionStart` hook that pre-scans all linked codebases (`RealtimeSTT`, `parakeet-stream`, `speaches`).
    - This hook must inject a technical overview (structure, key audio files, and README summaries) into the model's memory at startup to reduce redundant tool calls and provide immediate architectural awareness.
- **Optionality & Mode Selection:**
    - The system must support a toggle (e.g., a `--double-pass` flag or a configuration setting) to select the pipeline mode.
    - **Single-Pass (Default):** Maintain the existing VAD-driven segmented architecture.
    - **Double-Pass:** Enable the Ghost + Anchor refinement logic.
- **Hybrid Trigger Logic:**
    - Pass 2 triggers automatically every 2 seconds of active speech.
    - Pass 2 triggers immediately if the VAD detects a natural pause or end-of-utterance.
- **Contextual Sliding Window:**
    - Pass 2 processes a 4-second sliding window of audio to ensure high grammatical accuracy and stable transitions.
- **Stateful Alignment (Contextual Merge):**
    - After a Pass 2 refinement, Pass 1 must align its next "ghost" stream by using the last 3-4 words of the refined text as contextual prefix.
- **Terminal UI Enhancements:**
    - Support for simultaneous display of "refined" and "ghost" text on the same line.
    - **Visual Distinction:** Refined text (Solid Anchor) should be displayed in a bright/bold style, while unrefined text (Fast Ghost) should be dimmed or italicized.

## Non-Functional Requirements
- **Minimal Code Duplication:** Leverage existing `AudioStreamer`, `SileroVAD`, and core `STTEngine` logic for both modes.
- **Zero-Reload Switching:** Utilize Parakeet's ability to switch presets without reloading model weights.
- **Catch-up Processing:** Efficiently process audio captured while the engine is busy with a refinement pass.

## Acceptance Criteria
- [ ] The system starts in "Single-Pass" mode by default.
- [ ] Enabling "Double-Pass" mode results in immediate "dimmed" text followed by "bright" refinements.
- [ ] Transition between refined and ghost text is seamless in Double-Pass mode.
- [ ] Both modes are stable and accurately reflect the spoken audio.
- [ ] Code is organized to avoid "god script" patterns when handling both modes.

## Out of Scope
- Multi-model refinement.
- LLM-based post-processing.
