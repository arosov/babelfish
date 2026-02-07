# Tech Stack - Babelfish

## Core Backend
- **Language:** Python 3.12+
- **Package Management & Distribution:** `uv` (for high-speed dependency resolution and service execution)
- **Communication Protocol:** WebTransport (for ultra-low-latency bidirectional streaming)

## Pipeline Engines
- **Speech-to-Text (Primary):** [parakeet-stream](https://github.com/maximerivest/parakeet-stream) - Utilizing NVIDIA Parakeet TDT for extreme latency tuning.
- **Speech-to-Text (Secondary/Shadow):** *TBD* (Phase 2 integration).
- **Voice Activity Detection (VAD):** [Silero VAD](https://github.com/snakers4/silero-vad) or [WebRTCVAD](https://github.com/wiseman/py-webrtcvad) via `RealtimeSTT` loop management.
- **Large Language Model (LLM):** *TBD* (Phase 3 integration: optimized local models like Llama-3-8B-Instruct or Phi-3).

## Hardware & OS Targets
- **Platforms:** Windows (Windows Services), Linux (Systemd).
- **Acceleration:** NVIDIA CUDA (Primary target).

## Distribution & Orchestration
- **Launcher:** Custom Python scripts invoked via `uv run`.
- **Service Management:** Designed for integration with Kotlin-based frontend controller.