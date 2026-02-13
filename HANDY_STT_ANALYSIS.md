# Handy STT Application: Technical Analysis

This document provides a technical breakdown of the audio pipeline and LLM post-processing implementation within the Handy STT application.

---

## 1. Audio Pipeline Architecture

The pipeline is designed as a high-performance, linear sequence optimized for low-latency desktop use.

### Stage 1: Capture (Microphone)

- **Library:** `cpal`
- **Implementation:** `src-tauri/src/audio_toolkit/audio/recorder.rs`
- **Process:**
  - Spawns a dedicated high-priority worker thread.
  - Captures audio in real-time, converting multi-channel input to **Mono f32** (averaging channels).
  - Uses Rust channels (`mpsc`) to stream chunks to the consumer loop.

### Stage 2: Preprocessing

- **Resampling:** All audio is resampled to **16,000 Hz** (Whisper's requirement) using the `rubato` library or linear interpolation.
- **VAD (Voice Activity Detection):** Uses **Silero VAD v4** (via ONNX) to distinguish speech from noise.

### Stage 3: Buffering & Accumulation

- **Mechanism:** While the user holds the recording shortcut, valid speech frames are pushed into a `Vec<f32>` buffer.
- **Stateful Filtering:** Silence is discarded, but "padding" frames are kept (see Smoothed VAD) to ensure sentence integrity.

### Stage 4: Transcription (Inference)

- **Library:** `transcribe-rs`
- **Engines:** Supports Whisper, Moonshine, and others.
- **Logic:** The accumulated buffer is sent to the local model (loaded once at startup and kept warm in VRAM/RAM).

### Stage 5: Output (Delivery)

- **Mechanism:** `src-tauri/src/clipboard.rs`
- **Process:**
  1. Saves current clipboard state.
  2. Copies transcription to clipboard.
  3. Simulates system-level paste shortcut (`Cmd+V` or `Ctrl+V`).
  4. Restores original clipboard state.
  5. (Optional) Simulates typing for apps that block clipboard access.

---

## 2. Deep Dive: Smoothed VAD Logic

The `SmoothedVad` wrapper (`src-tauri/src/audio_toolkit/vad/smoothed.rs`) is critical for preventing "choppy" audio.

### The Problem

Raw VAD models often flicker (Silence -> Speech -> Silence) during short pauses or soft syllables.

### The Solution: Temporal Smoothing

- **Pre-Roll (Prefill):** A rolling `VecDeque` buffer stores the last ~300ms of audio. When speech is detected, the algorithm flushes this entire buffer _before_ the current frame. This catches the start of words (e.g., the "h" in "hello").
- **Onset Threshold:** Requires `N` consecutive "speech" frames before triggering the **Recording** state. Filters out mouth clicks and background pops.
- **Hangover (Post-Roll):** After the VAD says "Silence," the system continues recording for `M` frames (e.g., 300-500ms). This bridges the gap between words in a natural sentence.

---

## 3. LLM Post-Processing

Handy supports an optional "refinement" step using Large Language Models.

### Architecture

The app uses a provider-based client (`src-tauri/src/llm_client.rs`) that abstracts different backends:

- **Cloud:** OpenAI, Anthropic, Groq, Cerebras, OpenRouter (via HTTPS/JSON).
- **Local:** Ollama (OpenAI-compatible) and Apple Intelligence.

### The Post-Processing Prompt

The default prompt uses a "rules-based" instruction set rather than a vague "fix this" request:

```text
Clean this transcript:
1. Fix spelling, capitalization, and punctuation errors
2. Convert number words to digits (twenty-five → 25)
3. Replace spoken punctuation with symbols (period → .)
4. Remove filler words (um, uh)
5. Keep the language in the original version

Preserve exact meaning and word order. Do not paraphrase.
Return only the cleaned transcript.

Transcript:
${output}
```

### Apple Intelligence Integration

On macOS (Silicon), the app uses a **Swift/Rust FFI bridge**.

- **Implementation:** `src-tauri/swift/apple_intelligence.swift`.
- **Structured Output:** To prevent the model from adding conversational filler, the Swift code enforces a structured schema (`CleanedTranscript`), forcing the model to return _only_ the specific text field required.

---

## 4. Key Takeaways for Engine Improvement

1.  **Thread Isolation:** Keep the capture/VAD thread separate from the transcription thread to avoid UI hangs or audio dropouts.
2.  **Pre-Roll is Non-Negotiable:** Without a ~200ms pre-roll buffer, you will consistently lose the first consonant of every recording.
3.  **Structured Output:** When using small local LLMs for post-processing, use structured output (JSON/Schema) to eliminate "Here is your cleaned text:" preambles.
4.  **Resample Early:** Resample audio to the model's expected rate (16kHz) immediately upon capture to simplify all downstream logic.
