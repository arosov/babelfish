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
Babelfish's own `bootstrap.py` runs before the server in both standalone and
driven modes, so for VogonPoet use manual starts are unnecessary — set the
`VOGON_*` env contract and invoke `scripts/bootstrap.py` (or let VogonPoet
do it). To drive it by hand:
```bash
VOGON_APP_DATA_DIR=/path/to/appdata uv run --no-project --python 3.12.8 scripts/bootstrap.py
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

### Convenience Launchers
`scripts/run.bat` / `scripts/run.sh` resolve uv, seed the shared cache
variables (`VOGON_APP_CACHE_DIR`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`,
`UV_CMD`), and delegate everything to babelfish's own
`scripts/bootstrap.py` — hardware detection, `uv sync` with the right ORT
extra (with the `.last_hw_mode` marker / `--reinstall-package` self-heal),
Parakeet model provisioning, and DLL-path injection, then the CLI launch.
They reuse VogonPoet's uv when present:
`%LOCALAPPDATA%\VogonPoet\Cache\bin\uv.exe` on Windows (falling back to `uv`
on PATH); on Linux, the app cache bin dir (`~/.cache/vogonpoet/bin`) if
populated, then `uv` on PATH:
```bash
scripts/run.bat --wakeword hey_jarvis --cpu
scripts/run.sh --type --server
```

### Bootstrap Modes
`scripts/bootstrap.py` is the single owner of environment provisioning
(ADR 0006) and selects its flow from the environment:
- **Standalone** (no `VOGON_*` variables): detect hardware → `uv sync --extra
  <extra> --reinstall-package <ort-flavor>` unless the `.last_hw_mode`
  marker matches → provision the Parakeet model if absent → build the DLL
  env → foreground `uv run --no-sync babelfish <passthrough args>`.
- **Driven** (`VOGON_APP_DATA_DIR` set, as VogonPoet does): same provisioning
  plus a status WebSocket on port 8123 (the UI shows progress), a PID file,
  and a final `babelfish --server --port 8123` launch. The stdout markers the
  frontend scrapes (`BOOTSTRAP SERVER STARTED`, `Launching Babelfish`) and
  the `{"type":"status",...,"vad_state":"bootstrapping"}` status shapes are
  part of the contract — keep them stable when editing the script.
- `UV_CMD` picks the uv binary; `VOGON_FORCE_CPU` (or `hardware.device` ==
  `"cpu"` in the config) forces `--cpu` at runtime without changing the
  synced environment.

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
