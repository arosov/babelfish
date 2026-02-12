# Babelfish STT Server

High-performance, low-latency Speech-to-Text (STT) backend for system-wide transcription.

## 🚀 Quick Start

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

```bash
# Start the server
uv run babelfish

# Start with a specific wakeword
uv run babelfish --wakeword hey_jarvis
```

## ✨ Features

- **Ultra-Low Latency:** Uses NVIDIA Parakeet TDT via `onnx-asr`.
- **Two-Pass Pipeline:** Ghost pass for real-time feedback, Final pass for maximum accuracy.
- **Hardware Agnostic:** Supports CUDA, ROCm, OpenVINO, and DirectML.
- **Local Wake-word:** Integrated `openwakeword` support.
- **Global Hotkeys:** PTT and Toggle support via `pynput`.
- **WebSocket API:** Real-time configuration and transcription streaming.

## 🛠 Tech Stack

- Python 3.12
- ONNX Runtime (with GPU acceleration)
- Silero VAD
- OpenWakeWord
- WebSockets

## 📖 Documentation

- [AGENTS.md](AGENTS.md): Project philosophy and evolution.
- [launcher.md](launcher.md): Detailed CLI usage and developer commands.
