# Specification: Voice-Activated Control (Wake-Word & Stop-Word)

## Overview
This track implements an optional voice-controlled state management system for Babelfish. It allows the system to start transcribing upon detection of a specific "Wake-Word" and stop transcribing upon detection of a "Stop-Word" phrase. Both features are designed to be fully independent, allowing users to enable one or both.

## Functional Requirements
- **Wake-Word Detection (Start Trigger):**
    - **Backend Engine:** Integrate `openWakeWord` (ONNX-based) for high-performance, local detection.
    - **Idle State:** When a wake-word is configured, the system starts in an `IDLE` state (recording audio but not transcribing).
    - **Activation:** On detection of the wake-word, the system transitions to the `LISTENING` state and begins the STT transcription pipeline.
- **Stop-Word Detection (Stop Trigger):**
    - **Detection Mechanism:** Perform a text-based scan of the incoming "Fast Ghost" or "Solid Anchor" transcript stream.
    - **Matching Logic:** Use strict matching for the stop-word phrase (or a list of phrases) to prevent accidental triggers.
    - **Deactivation:** On detection of the stop-word, the system transitions back to the `IDLE` state, stopping transcription updates.
- **Independent Configuration:**
    - The wake-word and stop-word can be set to different values.
    - Either feature can be enabled or disabled independently via configuration or CLI flags.
- **Internal Event Logging:**
    - Log specific events for state changes, including timestamps and confidence scores (for `openWakeWord` detections) to the internal logs.

## Non-Functional Requirements
- **Resource Efficiency:** `openWakeWord` should run efficiently in the background without impacting STT performance.
- **Minimal Latency:** Text-based stop-word detection must occur in real-time as transcripts are generated.

## Acceptance Criteria
- [ ] The system remains in `IDLE` mode at startup if a wake-word is provided.
- [ ] Saying the wake-word successfully transitions the system to `LISTENING` mode.
- [ ] Saying the exact stop-word phrase successfully transitions the system back to `IDLE` mode.
- [ ] Both features work independently (e.g., stop-word only mode or wake-word only mode).
- [ ] Detection events and confidence scores are accurately logged.

## Out of Scope
- Audio feedback/sound effects (beeps) on detection.
- Natural Language Understanding (NLU) for complex stop commands.
- Parallel wake-word detection for the stop trigger.