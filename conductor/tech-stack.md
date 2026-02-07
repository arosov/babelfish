# Tech Stack - Babelfish

## Core Backend
- **Language:** Python 3.10+
- **Package Management & Distribution:** `uv` (for high-speed dependency resolution and one-liner execution)
- **Communication Protocol:** WebTransport (for low-latency, bidirectional streaming of pipeline progress and results)

## Pipeline Engines
- **Voice Activity Detection (VAD):** [Silero VAD](https://github.com/snakers4/silero-vad) - High-performance, pre-trained VAD with native Python support.
- **Speech-to-Text (STT):** [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) - Re-implementation of OpenAI's Whisper using CTranslate2 for significant speedups and reduced memory usage.
- **Large Language Model (LLM):** *TBD* (Requirement: Optimized for extremely low-latency token-by-token processing of incoming word streams).

## Hardware Abstraction & Acceleration
- **Frameworks:** CTranslate2 (via Faster-Whisper), ONNX Runtime (for Silero).
- **Backends:** NVIDIA (CUDA), AMD (ROCm/MIOpen), and CPU (AVX/OpenMP).

## Development & Distribution
- **Build System:** `hatch` or `flit` (configured for `uv` compatibility).
- **Logging:** Structured logging for high-fidelity CLI output and system health monitoring.