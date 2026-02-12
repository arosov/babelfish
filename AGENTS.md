# VogonPoet - Babelfish Server

Babelfish is a high-performance, low-latency Speech-to-Text (STT) backend designed to provide system-wide transcription injection. It serves as the core engine for a Kotlin-based frontend application, delivering real-time, hardware-accelerated transcription with minimal overhead.

## 🚀 Vision & Evolution

The project has evolved from a `RealtimeSTT` wrapper into a custom, optimized pipeline:

1.  **Step 1: Streaming Foundation (Completed)** - Transitioned from Whisper to a unified ONNX-based Parakeet TDT model (`nemo-parakeet-tdt-0.6b-v3`) for superior streaming latency and cross-platform GPU support.
2.  **Step 2: Intelligent Pipeline (Active)** - Implemented a two-pass system:
    *   **Ghost Pass:** Low-latency, sliding-window transcription for real-time visual feedback.
    *   **Final Pass:** Full-context transcription for maximum accuracy once speech ends.
3.  **Step 3: LLM Optimization (Future)** - Integration of local, low-latency LLMs to post-process, correct, and optimize the transcribed text.

## 🛠 Tech Stack

*   **Backend:** Python 3.12+, managed via `uv`.
*   **STT Engine:** `onnx-asr` running NVIDIA Parakeet TDT. Supports CUDA (NVIDIA), ROCm (AMD), OpenVINO (Intel), and DirectML (Windows Unified).
*   **Wake-word / Stop-word:** `openwakeword` for local, low-power keyword detection (Start/Stop triggers).
*   **Communication:** WebSockets for bidirectional communication with the frontend (configuration, status, and transcripts).
*   **Global Control:** `pynput` for system-wide hotkeys (Push-To-Talk, Toggle mode).
*   **Notifications:** `notify-py` for platform-native status alerts.

## 🧠 Philosophy: Server as the Brain

Babelfish is designed to be autonomous and hardware-aware:
*   **Hardware Auto-Discovery:** Probes for GPU capabilities (NVIDIA/AMD/Intel/DirectML) on startup and selects the best available backend.
*   **Self-Calibration:** Runs internal benchmarks during bootstrap to determine optimal performance tiers (Ultra/High/Medium/Low) based on inference latency.
*   **Dynamic Configuration:** Supports hot-reloading of nearly all settings (wakewords, sensitivities, hotkeys) via the WebSocket API without restarting the engine.
*   **Unified Pipeline:** Manages the entire audio lifecycle: VAD (Silero) -> Wake-word (OpenWakeWord) -> STT (Parakeet) -> Injection/Display.

## 📦 Distribution & Orchestration

The server runs as a background service. Interaction is primarily via the `babelfish` CLI tool provided by the package:
*   `uv run babelfish` - Starts the server with optimal hardware defaults.
*   `uv run babelfish --wakeword hey_jarvis` - Starts with specific wakeword activation.

Detailed execution patterns and developer commands are documented in `launcher.md`.

## 🧩 Integrated Knowledge

This project distills patterns from:
*   `RealtimeSTT`: Original inspiration for the loop management.
*   `parakeet-stream`: Core TDT streaming logic.
*   `onnx-asr`: The production-grade ONNX wrapper for Parakeet models.
*   `speaches`: Hardware-aware resource management and model handling.
