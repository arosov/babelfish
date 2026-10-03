# VogonPoet - Babelfish Server

Babelfish is a high-performance, low-latency Speech-to-Text (STT) backend designed to provide system-wide transcription injection. It serves as the core engine for a Kotlin-based frontend application, delivering real-time, hardware-accelerated transcription with minimal overhead.

## 🚀 Vision & Evolution

The project has evolved from a `RealtimeSTT` wrapper into a custom, optimized pipeline:

1.  **Step 1: Streaming Foundation (Completed)** - Transitioned from Whisper to an ONNX-based Parakeet TDT model (`nemo-parakeet-tdt-0.6b-v3`) for cross-platform GPU support.
2.  **Step 2: Two Passes, One Model (Current)** - A single Parakeet model serves two passes within one engine:
    *   **Ghost pass:** Throttled re-transcription of a sliding window of in-progress audio, for immediate visual feedback. Never committed; replaced wholesale when speech ends.
    *   **Final pass:** Whole-utterance transcription, once, at silence. The only text injected into the focused application.
3.  **Step 3: Hardware-Aware Device Resolution (Current)** - Startup probes GPUs per backend (NVIDIA/AMD/Intel/DirectML) and resolves exactly one device for the engine — the highest-VRAM discrete card, an explicit `hardware.device`, or CPU fallback. See [ADR 0004](docs/adr/0004-one-parakeet-model-on-one-device.md).

A two-model design (a streaming Nemotron decoder for the Ghost pass beside Parakeet for the Final pass) was explored and abandoned before implementation — see [ADR 0004](docs/adr/0004-one-parakeet-model-on-one-device.md) for why one model on one device won.

## 🛠 Tech Stack

*   **Backend:** Python 3.12+, managed via `uv`.
*   **STT Engine:** NVIDIA Parakeet TDT via `onnx-asr`, one model instance serving both passes. Supports CUDA (NVIDIA), OpenVINO (Intel), and DirectML (Windows Unified) — one ONNX Runtime wheel flavor per install. `hardware.device` is always a concrete backend: Windows defaults to DirectML, Linux to CUDA (NVIDIA driver present) else CPU; ROCm is removed ([ADR 0007](docs/adr/0007-no-auto-concrete-backends-and-rocm-removed.md)).
*   **Wake-word / Stop-word:** `openwakeword` for local, low-power keyword detection (Start/Stop triggers).
*   **Communication:** WebSockets for bidirectional communication with the frontend (configuration, status, and transcripts).
*   **Global Control:** `pynput` for system-wide hotkeys (Push-To-Talk, Toggle mode).
*   **Notifications:** `notify-py` for platform-native status alerts.

## 🧠 Philosophy: Server as the Brain

Babelfish is designed to be autonomous and hardware-aware:
*   **Concrete Device Resolution:** `hardware.device` always names a concrete backend (no `"auto"`). The bootstrap syncs the ORT wheel flavor that device needs (Windows: `windows-gpu` by default, `nvidia-win` only for an explicit CUDA request; Linux: `nvidia-linux` only when the device asks for CUDA *and* an NVIDIA driver is detected), and `placement.resolve_device` honors the device, degrading to CPU with a warning when its provider is missing or the value is stale. Multi-GPU is supported by picking the highest-VRAM discrete card within the requested backend; the choice is made once at process start.
*   **Startup Self-Calibration:** A startup benchmark calibrates the Ghost pass cadence (`ghost_throttle_ms`, `ghost_window_s` in `PerformanceProfile`) to the model's measured latency.
*   **Dynamic Configuration:** Supports hot-reloading of nearly all settings (wakewords, sensitivities, hotkeys) via the WebSocket API without restarting the engine.
*   **Unified Pipeline:** Manages the entire audio lifecycle: VAD (Silero) -> Wake-word (OpenWakeWord) -> Ghost pass -> Final pass -> Injection/Display. Control-word audio trimming is accepted intent ([ADR 0003](docs/adr/0003-control-words-are-trimmed-from-audio.md)) but **not yet implemented** — control-word audio currently stays in the transcription buffer.

## 📦 Distribution & Orchestration

The server runs as a background service when driven by VogonPoet, and is also
directly usable standalone from a terminal (no flags, no network). Interaction
is primarily via the `babelfish` CLI tool provided by the package:
*   `uv run babelfish` - Standalone mode (default): terminal transcripts, no WebSocket listener.
*   `uv run babelfish --type` - Standalone + type Ghost/Final text into the focused app (in-memory override).
*   `uv run babelfish --server` - Service mode: WebSocket API for VogonPoet (behaves as before).
*   `uv run babelfish --wakeword hey_jarvis` - Starts with specific wakeword activation.
*   `uv run babelfish --wakeword` - Lists available wake-words.
*   `uv run babelfish --cpu` - Forces CPU execution even if a GPU is available.
*   `uv run babelfish --port 8124` - Overrides the WebSocket port (requires `--server`; default 8123).
*   `uv run babelfish --stopword "stop listening"` - Sets a word that ends transcription.

Convenience launchers `scripts/run.bat` / `scripts/run.sh` resolve uv, seed the
shared cache env vars (`VOGON_APP_CACHE_DIR`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`,
`UV_CMD`), and delegate to babelfish's own `scripts/bootstrap.py` (ADR 0006) —
the single owner of hardware detection, ORT-flavor sync with self-heal, model
provisioning, and DLL-path injection. Both standalone and driven (VogonPoet)
modes run through it; CLI args pass through.
Model resolution order: shared cache (`cache.cache_dir` or `VOGON_APP_CACHE_DIR`) →
repo-local `models/` → onnx-asr HF cache (auto-download).

Detailed execution patterns and developer commands are documented in `launcher.md`.

## 🧩 Integrated Knowledge

This project distills patterns from:
*   `RealtimeSTT`: Original inspiration for the loop management.
*   `parakeet-stream`: Core TDT streaming logic.
*   `onnx-asr`: The production-grade ONNX wrapper for Parakeet models.
*   `speaches`: Hardware-aware resource management and model handling.

## Agent skills

### Explore subagent

Use the `explore` subagent for codebase navigation and lookups (finding files by pattern, searching for symbols or keywords, answering "how does X work?" questions). It runs on a free model, so prefer delegating searches to it instead of spending the main session's context — this keeps the primary agent's budget focused on actual engineering work.

### Issue tracker

GitHub Issues for arosov/babelfish via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical labels used as-is. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (root `GLOSSARY.md` + `docs/adr/`). See `docs/agents/domain.md`.

Vocabulary is load-bearing here: **Ghost** and **Final** are the two kinds of transcript
text, and **Utterance** is one stretch of speech. Do not introduce `interim`, `preview`,
`partial`, or `draft` as synonyms — `GLOSSARY.md` lists them as avoided deliberately.
