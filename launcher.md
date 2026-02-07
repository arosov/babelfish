# Babelfish Launcher

This document tracks the `uv` commands and scripts used to run, test, and deploy the Babelfish server.

## 🚀 Development Commands

### Start STT Server (Current)
Runs the main STT entry point with `parakeet-stream` and `RealtimeSTT` dependencies.
```bash
uv run --index https://download.pytorch.org/whl/cu121 --with-requirements requirements_stt.txt --with RealtimeSTT python run_stt.py
```

## 🛠 Future Commands (Draft)
*   **Step 1 (Single Pass):** `uv run python run_stt.py --engine parakeet`
*   **Step 2 (Two-Pass):** `uv run python run_stt.py --engine dual-pass`
*   **Step 3 (LLM Enabled):** `uv run python run_stt.py --llm local`

## ⚙️ Environment Notes
*   **CUDA 12.1:** Primary target for GPU acceleration.
*   **WebTransport Port:** (To be defined in config.json)
