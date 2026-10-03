# Babelfish Launcher

This document tracks the `uv` commands and operational patterns used to run, test, and develop the Babelfish server.

## 🚀 Execution Commands

### Standalone Start (default)
Runs fully local with no network listener: Ghost dim / Final bold in the terminal.
```bash
uv run babelfish
```

### Type into the Focused App
Ghost typed live into whatever window has focus, replaced by Final when the
Utterance ends (in-memory override, never saved to the config).
```bash
uv run babelfish --type
```

### Service Mode (VogonPoet)
Exposes the WebSocket API on port `8123` (status, transcript stream, config
hot-reload, mic test). Composes with `--type`:
```bash
uv run babelfish --server
uv run babelfish --server --type
```
VogonPoet's `bootstrap.py` already launches with `--server --port 8123`, so
manual starts for VogonPoet use are unnecessary.

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

### Convenience Launchers
`scripts/run.bat` / `scripts/run.sh` pipe their arguments straight through to
the CLI and set `VOGON_APP_CACHE_DIR` (if not already set) so the shared
Parakeet cache is reused instead of re-downloading ~2.4GB. They also reuse
VogonPoet's uv when present: `%LOCALAPPDATA%\VogonPoet\Cache\bin\uv.exe` on
Windows (falling back to `uv` on PATH); on Linux, the app cache bin dir
(`~/.cache/vogonpoet/bin`) if populated, then `uv` on PATH:
```bash
scripts/run.bat --wakeword hey_jarvis --cpu
scripts/run.sh --type --server
```

### Shared Model Cache
Model resolution order: `cache.cache_dir` (config, or `VOGON_APP_CACHE_DIR`
env) → repo-local `models/nemo-parakeet-tdt-0.6b-v3/` → onnx-asr's default HF
cache (auto-download on first run). To reuse the VogonPoet cache:
```bash
set VOGON_APP_CACHE_DIR=F:\vogonpoet_cache   # Windows
VOGON_APP_CACHE_DIR=/path/to/vogonpoet_cache # Linux
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

- **WebSocket Port:** Bound only in `--server` mode; default `8123`
  (configurable via `config.json` or `--port 8124`; `--port` requires `--server`).
- **Models:** Resolved from the shared cache (`VOGON_APP_CACHE_DIR` /
  `cache.cache_dir`), then repo-local `models/`, otherwise the onnx-asr HF
  cache (auto-download). The primary model is `nemo-parakeet-tdt-0.6b-v3`.
- **Startup Calibration:** The server benchmarks the model on startup to set the Ghost pass cadence (`ghost_throttle_ms`, `ghost_window_s`).
- **Hotkeys:** 
  - `Ctrl+Space` (default): Toggle Mode (Listen/Idle).
  - `Left Shift` (default): Push-To-Talk (PTT).
