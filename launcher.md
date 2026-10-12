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
Useful for debugging or low-power environments — also forces the coherent
CPU path through the bootstrap (ADR 0014: sync, provisioning, and launch
all follow the CPU; no GPU wheel is synced).
```bash
uv run babelfish --cpu
```

### Force GPU Mode (one run)
Flips to the best detected GPU backend in memory (never saved; ADR 0014).
GPU devices keep the fp32 v3 weights card. Mutually exclusive with `--cpu`.
First use syncs the GPU flavor wheel + fp32 weights (several GB).
```bash
uv run babelfish --gpu
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
  marker matches **and** a live ORT-flavor check passes → provision the
  Parakeet model if absent → build the DLL env → foreground
  `uv run --no-sync babelfish <passthrough args>`.
- **Flavor from the effective device (ADR 0007 + ADR 0014):** the device
  is the sole key for the flavor, the weight card, and provisioning —
  Windows and Linux alike, the fresh default is **CPU** (the small plain
  onnxruntime wheel + the Redux int4 card). CUDA is an explicit opt-in
  (hardware.device "cuda"/"cuda:N" → `nvidia-win`/`nvidia-linux`); other
  values ride `windows-gpu` on Windows / `cpu` on Linux;
  `intel-linux` is a manual opt-in and never auto-selected. The
  overrides every layer honors: `VOGON_FORCE_CPU=1` and a
  `--cpu`/`--gpu` CLI passthrough. When the effective device differs
  from the config's, one line says so (`Effective device: cpu (config
  says cuda; …)`). Legacy device values (`""`, `"auto"`, `rocm*`) map to
  the platform default (cpu) with one log line — the running server
  migrates the config file itself.
- **Driven** (`VOGON_APP_DATA_DIR` set, as VogonPoet does): same provisioning
  plus a status WebSocket on port 8123 (the UI shows progress), a PID file,
  and a final `babelfish --server --port 8123` launch. The stdout markers the
  frontend scrapes (`BOOTSTRAP SERVER STARTED`, `Launching Babelfish`) and
  the `{"type":"status",...,"vad_state":"bootstrapping"}` status shapes are
  part of the contract — keep them stable when editing the script.
- The sync gate (`ensure_ort_env`) re-verifies the installed onnxruntime
  against the mode's execution provider even when the marker matches
  (heals out-of-band shadow installs, H1), verifies again after each sync
  and only then writes the marker (so a same-sync ordering race can't
  record a broken env as success, H2), retries the sync once, and
  refuses to launch (standalone: exit 1; driven: failure status) if the
  intended provider is still missing after both attempts.
- `UV_CMD` picks the uv binary; `VOGON_FORCE_CPU` forces CPU mode for the
  whole pipeline — detection/sync, provisioning, and launch — not just the
  runtime flag (ADR 0014). A `--cpu` in the CLI passthrough behaves the
  same.
- The CPU card's calibration fingerprint carries the weights identity
  (ADR 0014): swapping the fp32 and redux cards between launches re-benches
  once and persists two profiles under distinct keys (the prototype
  measured a silent profile overwrite without this).

### Shared Model Cache
Weights are a **device-keyed ladder** (ADR 0014): `device=cpu` →
`models/nemo-parakeet-tdt-0.6b-v3-redux/` (~418 MB, provisioning from
`eschmidbauer/parakeet-redux-onnx` at a pinned revision, SHA-256 digests
logged at first provision); any GPU device → `models/nemo-parakeet-tdt-0.6b-v3/`
(~2.4 GB, `istupakov/parakeet-tdt-0.6b-v3-onnx`).
`hardware.model` (`"v3"` | `"redux"`) forces one card.
Each card follows the search order: `cache.cache_dir` (config, or
`VOGON_APP_CACHE_DIR` env) → repo-local `models/` → onnx-asr's default HF
cache (auto-download on first run). Both cards may sit side by side in the
shared cache (delete the unused one manually to reclaim space):
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
- **Models:** A device-keyed weights ladder (ADR 0014): `cpu` →
  `nemo-parakeet-tdt-0.6b-v3-redux` (Parakeet Redux int4, ~418 MB, the
  out-of-the-box default), any GPU backend → `nemo-parakeet-tdt-0.6b-v3`
  (fp32 v3). Resolved from the shared cache (`VOGON_APP_CACHE_DIR` /
  `cache.cache_dir`), then repo-local `models/`, otherwise the onnx-asr HF
  cache (auto-download). `hardware.model` ("v3" | "redux") forces one card;
  GPU + int4 is out of scope for now.
- **Startup Calibration:** Bench once per acceleration backend, cached in the config file's top-level `calibration` section (ADR 0013, superseding ADR 0011's always-runs posture): a real-speech probe matrix picks the Ghost window from the measured cost curve and the tier/throttle at that operating point; every later launch reuses the stored profile after a single canary inference agrees (±25%), re-benching only on regime change. No tier override, no manual knob. The profile is calibration output applied in memory, never configuration. The Ghost *display* cadence is owned by inference completion, not the throttle.
- **Hotkeys:** 
  - `Ctrl+Space` (default): Toggle Mode (Listen/Idle).

## 🤝 VogonPoet coordination (ADR 0014)

The fresh-config default device is now `cpu` server-side. If VogonPoet
*creates* the first-run `babelfish.config.json` itself, its own creation
default may still write `dml` today. That is a valid explicit GPU opt-in —
the fp32 v3 card + a GPU flavor wheel — and keeps working unchanged, but
the app's first-run UX then downloads 2.4 GB and syncs a GPU wheel where
the server default would have pulled 418 MB on CPU. Two options,
own side decision: switch the Kotlin provisioner's creation default to
`cpu` (synchronized change), or accept app-overrides-user in the interim
and revisit later. Everything else (driven-mode provisioning, status
markers, launch contract) is unchanged.

Historical note: `scripts/run_redux.py` / `run_redux.bat` (the weights-swap
day-to-day launcher from the Oct 2026 prototype pass) is now largely
superseded — a plain CPU run *is* the redux card, provisioned into its own
directory. The script stays untouched for the A/B workflows that need the
fp32 bytes physically parked in the shared cache dir (e.g. while the
VogonPoet side still provisions the fp32 card) and needs no maintenance.
