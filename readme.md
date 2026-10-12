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

- Start in Idle. Toggle mode with `Ctrl+Space` (configurable in
  `babelfish.config.json`).
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

Weights come as a per-device **ladder**
([ADR 0014](docs/adr/0014-cpu-default-with-device-keyed-weights-ladder.md)):
the CPU default loads the **Parakeet Redux int4** card
(`nemo-parakeet-tdt-0.6b-v3-redux`, ~418 MB, from
`eschmidbauer/parakeet-redux-onnx` at a pinned revision); any GPU backend
keeps the fp32 card (`nemo-parakeet-tdt-0.6b-v3`, ~2.4 GB, from
`istupakov/parakeet-tdt-0.6b-v3-onnx`) — GPU int4 is deliberately out of
scope. Transcripts are equivalent on the bundled fixtures (measured live,
Oct 2026): the 7× smaller card optimizes footprint and first-run download,
not short-window CPU latency.

Each card is resolved in this order:

1. **Shared cache** — `<cache.cache_dir>/models/<card-name>/`, where
   `cache.cache_dir` comes from an explicit config value or the
   `VOGON_APP_CACHE_DIR` environment variable (the VogonPoet cache).
2. **Repo-local** — `models/<card-name>/` in the checkout.
3. **onnx-asr default** — the Hugging Face cache; auto-downloads on first
   use, then stays cached (GPU devices only — a cpu device materializes
   its own card instead, ADR 0014). Standard `HF_HOME` / `HF_HUB_CACHE`
   environment variables remain respected by HF.

The ladder is strict with no user override:

- **cpu implies redux** — the engine materializes the card itself when it
  is missing (an idempotent pinned download); offline without the card
  refuses to start rather than serve fp32.
- **redux never loads on a GPU backend** — GPU int4 is out of scope; a GPU
  card experiment would be a placement change, not a ladder flag.
- Both cards may sit side by side in the cache (~2.9 GB combined worst
  case).

To reuse an existing Parakeet install from VogonPoet instead of downloading
again:

```bash
# Windows
set VOGON_APP_CACHE_DIR=F:\vogonpoet_cache
uv run babelfish
```

or set `"cache": { "cache_dir": "F:\\vogonpoet_cache" }` in your config file.
Ensure the directory contains `models/<card-name>/` for the card your device
resolves.

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
| `cpu`           | any      | CPU (**default**; also the macOS path) |
| `nvidia-win`    | Windows  | NVIDIA CUDA (opt-in)        |
| `nvidia-linux`  | Linux    | NVIDIA CUDA (opt-in)        |
| `windows-gpu`   | Windows  | AMD/Intel/NVIDIA via DirectML (opt-in) |
| `intel-linux`   | Linux    | Intel OpenVINO (manual opt-in) |

Defaults are decided at config creation and are never `"auto"` —
`hardware.device` is always a concrete backend
([ADR 0007](docs/adr/0007-no-auto-concrete-backends-and-rocm-removed.md),
[ADR 0014](docs/adr/0014-cpu-default-with-device-keyed-weights-ladder.md)).
Every platform starts on **CPU** (with the Redux int4 weights); GPUs are an
explicit opt-in — write `hardware.device` in the config, or pass
`babelfish --gpu` for one in-memory override. A GPU config syncs its
wheel on demand: `cuda`/`cuda:N` → `nvidia-win`/`nvidia-linux`,
`dml` → `windows-gpu`. Linux + AMD runs on CPU (the ROCm execution provider
was removed from ONNX Runtime ≥ 1.23).
Existing `dml`/`cuda` configs keep working unchanged (they stay on fp32 v3).

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
- **Self-Calibrating, Bench-Once-Per-Backend:** a real-speech probe matrix
  benches the model once per acceleration backend and caches the result in
  the config's `calibration` section ([ADR 0013](docs/adr/0013-calibration-is-cached-per-backend.md));
  every launch canary-checks it with a single inference (±25%) and re-benches
  only on regime change.
- **Local Wake-word / Stop-word:** integrated `openwakeword` support.
- **Global Hotkeys:** Toggle via `pynput`.
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
