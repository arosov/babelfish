# Babelfish STT

High-performance, low-latency Speech-to-Text (STT) for system-wide transcription
injection. One local Parakeet TDT model on one device serves two passes:
the **Ghost** pass (provisional text while speaking, never committed) and the
**Final** pass (the one committed transcript per **Utterance** — the only text
injected anywhere). See [AGENTS.md](AGENTS.md) for the philosophy and
[ADR 0004](docs/adr/0004-one-parakeet-model-on-one-device.md) for why one model
on one device won.

## 🚀 Quick Start

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

```bash
# Standalone transcription in your terminal (no flags, no network)
uv run babelfish

# Transcribe into whatever app you're focused on
uv run babelfish --type

# Run as a WebSocket service (VogonPoet mode)
uv run babelfish --server

# Or use the convenience launcher (honors the shared model cache)
scripts/run.bat   # Windows
scripts/run.sh    # Linux
```

## 🖥 Two Deployment Modes

### Standalone (default — no flags)

Fully local, no network listener. Transcripts render in the terminal:
**Ghost** text appears dim while you speak and is replaced wholesale by bold
**Final** text when the Utterance ends. Desktop toasts fire on wake/stop-word.
Nothing is ever typed into other apps.

### `--type`

Ghost text is typed live into the focused application (via clipboard paste),
removed wholesale, and replaced by Final text when the Utterance ends — the same
behavior VogonPoet drives. Composes with `--server` and
wake-words. This is an in-memory override, never written to the config file.

### `--server`

Runs service mode: the WebSocket API on port `8123` (status, transcript
stream, config hot-reload, mic test), as consumed by VogonPoet. Composes with
`--type`. VogonPoet drives the server by invoking babelfish's own
`scripts/bootstrap.py` with `VOGON_APP_DATA_DIR` set — the bootstrap then
launches `babelfish --server --port 8123` itself, so never start the service
by hand for VogonPoet use.
`--port 8124` overrides the port but **requires** `--server`.

## 🎛 Triggers

- Start in Idle. Toggle mode with `Ctrl+Space`; Push-To-Talk with `Left Shift`
  (both configurable in `babelfish.config.json`).
- `--wakeword hey_jarvis` — local openwakeword detection. The first
  `--wakeword` run downloads a few MB of openwakeword models.
- `--stopword "stop listening"` — a transcript stop-phrase; if the argument
  matches an openwakeword model name instead, it is automatically used as an
  audio stop-word model. The arg distinguishes this for you.
- `uv run babelfish --wakeword` lists the available wake-words.

## ⚙️ Configuration

Babelfish reads `babelfish.config.json` from the working directory by default.
When VogonPoet is driving, it uses `%VOGON_APP_DATA_DIR%/babelfish.config.json`.
Standalone mode reads it once at startup; in `--server` mode nearly all
settings hot-reload over the WebSocket without a restart.

`--type` sets this block in memory for the session:

```json
{
  "system_input": {
    "enabled": true,
    "type_ghost": true,
    "separator": "trailing"
  }
}
```

`separator` controls the space between consecutive Final texts, and it hot-reloads:
`trailing` (the default) types a space at the end of each Final; `leading` types it at
the start of the next one (the legacy behavior); `never` disables the separator
entirely.

You can persist the same block in your config file instead of using `--type`.

## 📦 Cache & Model Provisioning

The Parakeet model (`nemo-parakeet-tdt-0.6b-v3`, ~2.4GB) is resolved in this
order:

1. **Shared cache** — `<cache.cache_dir>/models/nemo-parakeet-tdt-0.6b-v3/`,
   where `cache.cache_dir` comes from an explicit config value or the
   `VOGON_APP_CACHE_DIR` environment variable (the VogonPoet cache).
2. **Repo-local** — `models/nemo-parakeet-tdt-0.6b-v3/` in the checkout.
3. **onnx-asr default** — the Hugging Face cache; auto-downloads ~2.4GB on
   first use, then stays cached. Standard `HF_HOME` / `HF_HUB_CACHE`
   environment variables remain respected by HF.

To reuse an existing Parakeet install from VogonPoet instead of downloading
again:

```bash
# Windows
set VOGON_APP_CACHE_DIR=F:\vogonpoet_cache
uv run babelfish
```

or set `"cache": { "cache_dir": "F:\\vogonpoet_cache" }` in your config file.
Ensure the directory contains `models/nemo-parakeet-tdt-0.6b-v3/`.

> ⚠️ **Caveat:** `scripts/bootstrap.py` is owned by babelfish itself — see
> [ADR 0006](docs/adr/0006-babelfish-owns-its-bootstrap.md). It owns
> environment sync, model provisioning, and DLL paths in both standalone and
> driven (VogonPoet-invoked) modes — do not hand-sync any of that. It runs
> automatically via `scripts/run.bat` / `scripts/run.sh` and, when VogonPoet
> drives the server, via the same script with the `VOGON_*` env contract set.
> Manual `uv sync --extra <name>` (below) is still possible for development,
> but the launchers do not need it.

## 🧩 ONNX Runtime Extras

Install via `uv sync --extra <name>`. Extras are mutually exclusive (uv
enforces it) — pick exactly one for your hardware/OS:

| Extra           | Platform | Backend                     |
|-----------------|----------|-----------------------------|
| `cpu`           | any      | CPU (also the macOS path)   |
| `nvidia-win`    | Windows  | NVIDIA CUDA (opt-in)        |
| `nvidia-linux`  | Linux    | NVIDIA CUDA (default)       |
| `windows-gpu`   | Windows  | AMD/Intel/NVIDIA via DirectML (default) |
| `intel-linux`   | Linux    | Intel OpenVINO (manual opt-in) |

Defaults are decided at config creation and are never `"auto"` —
`hardware.device` is always a concrete backend
([ADR 0007](docs/adr/0007-no-auto-concrete-backends-and-rocm-removed.md)):
Windows starts on DirectML (picking `cuda`/`cuda:N` in the UI syncs
`nvidia-win` on demand); Linux starts on CUDA when an NVIDIA driver is
detected, else CPU. Linux + AMD runs on CPU (the ROCm execution provider was
removed from ONNX Runtime ≥ 1.23).

```powershell
# Windows + NVIDIA
uv sync --extra nvidia-win
# Linux + NVIDIA
uv sync --extra nvidia-linux
```

## 🖤 Platforms

Windows and Linux are supported today. macOS is an intended future target:
the `cpu` extra is expected to work, but it is currently untested.

## ✨ Features

- **Ultra-Low Latency:** NVIDIA Parakeet TDT via `onnx-asr`, hardware-accelerated
  on CUDA, OpenVINO, and DirectML.
- **Two-Pass Pipeline:** Ghost pass for real-time feedback, Final pass for
  maximum accuracy.
- **Local Wake-word / Stop-word:** integrated `openwakeword` support.
- **Global Hotkeys:** PTT and Toggle via `pynput`.
- **Desktop Notifications:** wake/stop-word toasts in both modes.
- **WebSocket API (opt-in):** real-time configuration and transcript streaming.

## 🛠 Tech Stack

- Python 3.12 (via `uv`)
- ONNX Runtime (one wheel flavor per hardware)
- Silero VAD, OpenWakeWord
- WebSockets, notify-py

## 📖 Documentation

- [AGENTS.md](AGENTS.md): Project philosophy and evolution.
- [launcher.md](launcher.md): Detailed CLI usage and developer commands.
- [GLOSSARY.md](GLOSSARY.md): Load-bearing vocabulary (Ghost, Final, Utterance).
- [docs/adr](docs/adr/): Architecture decision records.
