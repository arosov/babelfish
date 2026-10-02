# VogonPoet - Babelfish Server

Babelfish is a high-performance, low-latency Speech-to-Text (STT) backend designed to provide system-wide transcription injection. It serves as the core engine for a Kotlin-based frontend application, delivering real-time, hardware-accelerated transcription with minimal overhead.

## 🚀 Vision & Evolution

The project has evolved from a `RealtimeSTT` wrapper into a custom, optimized pipeline:

1.  **Step 1: Streaming Foundation (Completed)** - Transitioned from Whisper to an ONNX-based Parakeet TDT model (`nemo-parakeet-tdt-0.6b-v3`) for cross-platform GPU support.
2.  **Step 2: Two Stages, Two Models (Active)** - Split the old two-pass system into two stages, each owning the model it uses. See [ADR 0001](docs/adr/0001-each-stage-owns-its-own-model.md):
    *   **Ghost Stage:** Stateful incremental decoding of in-progress audio, for immediate visual feedback. Never committed; replaced wholesale when speech ends.
    *   **Final Stage:** Whole-utterance transcription, once, for maximum accuracy. The only text injected into the focused application.

Each stage is written against its own model rather than parameterised by it. There is no role registry and no model selection in configuration — models are constants in source.

## 🛠 Tech Stack

*   **Backend:** Python 3.12+, managed via `uv`.
*   **STT Engine:** Two independent models. The Final Stage uses NVIDIA Parakeet TDT via `onnx-asr`; the Ghost Stage uses a Nemotron-family speech model for incremental decoding. Supports CUDA (NVIDIA), ROCm (AMD), OpenVINO (Intel), and DirectML (Windows Unified).
*   **Wake-word / Stop-word:** `openwakeword` for local, low-power keyword detection (Start/Stop triggers).
*   **Communication:** WebSockets for bidirectional communication with the frontend (configuration, status, and transcripts).
*   **Global Control:** `pynput` for system-wide hotkeys (Push-To-Talk, Toggle mode).
*   **Notifications:** `notify-py` for platform-native status alerts.

## 🧠 Philosophy: Server as the Brain

Babelfish is designed to be autonomous and hardware-aware:
*   **Hardware Auto-Discovery:** Probes for GPU capabilities (NVIDIA/AMD/Intel/DirectML) on startup and selects the best available backend. Multi-GPU is supported; by default both stages share the highest-VRAM card.
*   **Placement Mode:** Chooses which providers the two stages run on — `split` (Ghost on GPU, Final on CPU, the default), `all-gpu`, or `cpu`. Decided once at process start; see [ADR 0002](docs/adr/0002-placement-is-static-and-shares-one-gpu.md). There is no self-calibration and no performance tier: the Ghost model's own streaming cadence sets its update rate.
*   **Dynamic Configuration:** Supports hot-reloading of nearly all settings (wakewords, sensitivities, hotkeys) via the WebSocket API without restarting the engine.
*   **Unified Pipeline:** Manages the entire audio lifecycle: VAD (Silero) -> Wake-word (OpenWakeWord) -> Ghost Stage -> Final Stage -> Injection/Display. Control-word audio is trimmed from the transcription buffer; see [ADR 0003](docs/adr/0003-control-words-are-trimmed-from-audio.md).

## 📦 Distribution & Orchestration

The server runs as a background service. Interaction is primarily via the `babelfish` CLI tool provided by the package:
*   `uv run babelfish` - Starts the server with optimal hardware defaults.
*   `uv run babelfish --wakeword hey_jarvis` - Starts with specific wakeword activation.
*   `uv run babelfish --placement all-gpu` - Runs both stages on the GPU instead of the default `split`.
*   `uv run babelfish --no-strip-control-words` - Keeps control words in the transcript, for debugging.

Detailed execution patterns and developer commands are documented in `launcher.md`.

## 🧩 Integrated Knowledge

This project distills patterns from:
*   `RealtimeSTT`: Original inspiration for the loop management.
*   `parakeet-stream`: Core TDT streaming logic.
*   `onnx-asr`: The production-grade ONNX wrapper for Parakeet models.
*   `speaches`: Hardware-aware resource management and model handling.

## Agent skills

### Issue tracker

GitHub Issues for arosov/babelfish via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical labels used as-is. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (root `GLOSSARY.md` + `docs/adr/`). See `docs/agents/domain.md`.

Vocabulary is load-bearing here: **Ghost** and **Final** are the two kinds of transcript
text, **Ghost Stage** and **Final Stage** are the units that own the models, and
**Utterance** is one stretch of speech. Do not introduce `interim`, `preview`, `partial`,
or `draft` as synonyms — `GLOSSARY.md` lists them as avoided deliberately.
