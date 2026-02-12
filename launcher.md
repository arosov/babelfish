# Babelfish Launcher

This document tracks the `uv` commands and operational patterns used to run, test, and develop the Babelfish server.

## 🚀 Execution Commands

### Standard Server Start
Starts the server with automatic hardware discovery (CUDA/ROCm/DirectML/CPU).
```bash
uv run babelfish
```

### Start with Wake-Word
Enables `openwakeword` activation.
```bash
uv run babelfish --wakeword hey_jarvis
```

### List Available Wake-Words
```bash
uv run babelfish --wakeword
```

### Force CPU Mode
Useful for debugging or low-power environments.
```bash
uv run babelfish --cpu
```

## 🛠 Developer Commands

### Generate Configuration Schema
Generates the JSON schema for the WebSocket configuration protocol.
```bash
./scripts/generate_schema.sh
```

### Run Tests
```bash
uv run pytest
```

### Clean Environment
Wipes the `uv` cache if dependencies get corrupted.
```bash
./wipe_uv_cache.sh
```

## ⚙️ Operational Details

- **WebSocket Port:** Defaults to `5000` (configurable via `config.json`).
- **Models:** Models are stored in the `./models` directory. The primary model is `nemo-parakeet-tdt-0.6b-v3`.
- **Hardware:** The server benchmarks itself on startup to set the `PerformanceTier`.
- **Hotkeys:** 
  - `F19` (default): Toggle Mode (Listen/Idle).
  - `F20` (default): Push-To-Talk (PTT).
