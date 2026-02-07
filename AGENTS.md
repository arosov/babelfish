# VogonPoet - Babelfish Server

Babelfish is a high-performance, low-latency Speech-to-Text (STT) backend designed to provide system-wide transcription injection (similar to BetterDictation). It serves as the core engine for a Kotlin-based frontend application.

## 🚀 Vision & Evolution

The goal is to build a top-of-the-line low-latency pipeline by combining the best open-source components:

1.  **Step 1: Streaming Foundation** - Reproduce a `RealtimeSTT`-style pipeline but utilizing `parakeet-stream` (NVIDIA Parakeet TDT) instead of Whisper for superior streaming latency.
2.  **Step 2: Two-Pass Refinement** - Upgrade to a two-pass system using two distinct models to balance speed and final accuracy.
3.  **Step 3: LLM Optimization** - Integrate a local, low-latency LLM to post-process and optimize the transcribed text output.

## 🛠 Tech Stack

*   **Backend:** Python, orchestrated via `uv` for seamless dependency management and execution.
*   **STT Engine:** `parakeet-stream` for its aggressive latency-tuning capabilities.
*   **Communication:** WebTransport for high-speed, low-latency local communication with the frontend.
*   **Frontend:** Kotlin-based UI that manages the server lifecycle (start/stop/restart).
*   **Targets:** Windows (Windows Services) and Linux (Systemd).

## 🧠 Philosophy: Server as the Brain

Babelfish is designed to be the "brain" of the STT system. It doesn't just execute commands; it autonomously manages the environment to ensure optimal performance:
*   **Hardware Auto-Discovery:** On startup, it probes for GPU availability, selects the best card, and reports VRAM capacity to optimize model loading.
*   **Intelligent Defaults:** It automatically identifies and selects the most appropriate audio input devices if not explicitly configured.
*   **Configuration Authority:** While the frontend provides a UI for human interaction, the server maintains the source of truth for configuration, providing sensible defaults that work out-of-the-box.

## 📦 Distribution & Orchestration

The server is designed to be run as a background service. Developers and the frontend app interact with it via `uv` one-liners. All available commands and execution patterns are documented in `launcher.md`.

## 🧩 Integrated Knowledge

This project leverages insights and code patterns from:
*   `RealtimeSTT`: Loop management and VAD integration.
*   `parakeet-stream`: Streaming TDT implementation and quality presets.
*   `speaches`: OpenAI-compatible serving, dynamic model handling, and hardware-aware resource management.

