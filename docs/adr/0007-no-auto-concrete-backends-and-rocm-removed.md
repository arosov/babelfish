# No "auto" — concrete backends; Windows defaults DirectML, Linux defaults CUDA; ROCm removed

Date: 2026-10-03
Status: Accepted

## Context

`hardware.device` had a magic `"auto"` value. Its meaning was fractured across four
layers that each re-derived it differently: the UI offered "Auto Detect" as the top
entry, `config.py` defaulted to `"auto"`, `placement.resolve_device` re-ranked every
backend (CUDA > ROCm > DML > OpenVINO > CPU) on each startup, and
`scripts/bootstrap.py` ran its own GPU detection that could pick a *different* ORT
wheel flavor than the device the engine would finally resolve. A machine with an
AMD card and an NVIDIA driver, or a machine whose flavor wheel was swapped
out-of-band, could bootstrap into an environment the runtime then partially
undo — or silently degrade.

Two external facts forced a cleanup at the same time:

- The ROCm execution provider was removed from ONNX Runtime's source tree in 1.23;
  no official `onnxruntime-rocm` wheel past the frozen 1.22.2.post1 third-party
  build will ever exist. Linux + AMD has no GPU path going forward (the future AMD
  option is the MIGraphX EP — separate work).
- On Windows, DirectML runs on every GPU vendor (AMD, Intel, NVIDIA) from a small
  wheel, while the CUDA wheel drags ~2 GB of cu13 pip libraries. Auto-mode's default
  of CUDA-first on Windows paid that cost for everyone, even users who never need
  CUDA.

## Decision

**`hardware.device` is always a concrete backend; "auto" is deleted.**

- Concrete values: `"dml"` / `"dml:N"`, `"cuda"` / `"cuda:N"`, `"cpu"`, plus specific
  ids from `list_hardware` (e.g. `"openvino:GPU.0"`), which pass through as before.
- **Windows default = `"dml"`** — the small `windows-gpu` (`onnxruntime-directml`)
  wheel. CUDA is on demand: the UI dropdown offers `cuda`/`cuda:N`, and selecting it
  makes the bootstrap sync `nvidia-win` once (the uv cache stays warm for switching
  back to DML).
- **Linux default = `"cuda"` when an NVIDIA driver is detected, else `"cpu"`** —
  decided **at config creation** (fresh defaults and legacy migration), never
  re-derived at runtime. The bootstrap only syncs `nvidia-linux` when the device
  asks for CUDA *and* NVIDIA is actually detected; a pinned CUDA request without a
  driver logs a warning and syncs the CPU flavor (the runtime degrades to CPU).
- **ROCm is deleted everywhere**: the `amd-linux` extra and `onnxruntime-rocm` are
  purged from `pyproject.toml`/`uv.lock`, and the ROCm branches are removed from the
  bootstrap, `placement`, `hardware`, and `engine`. Legacy `"rocm"`/`"rocm:N"` device
  values migrate to the platform default (Linux + AMD → CPU).
- **Legacy migration**: `"auto"`, `""`, and `rocm*` device values are rewritten to the
  platform default. The runtime `ConfigManager` rewrites the config file; the
  bootstrap only maps the value for its own flavor decision (one log line, no file
  write — the runtime owns the file).
- **`placement.resolve_device` no longer re-orders backends.** A bare backend name
  (`"cuda"`, `"dml"`) picks that backend's highest-VRAM discrete device *if its
  provider is installed*; otherwise it degrades to CPU with a warning — there is no
  cross-backend fallback (the old `cuda` → DML re-ranking is gone). Exact ids are
  honored as pinned (provider presence validated). Unknown/stale values degrade to
  CPU with a warning.
- **Intel/OpenVINO stays a documented manual opt-in**: the `intel-linux` extra is
  never auto-selected by the bootstrap; the user installs it themselves.
- **macOS**: fresh configs default to `"cpu"`; Metal/CoreML passthroughs are intact
  but low priority.
- **VogonPoet cache warmup** primes only `windows-gpu` on Windows (the old two-phase
  CUDA+DML warmup downloaded the whole cu13 set for every user); Linux/macOS keep
  priming both sets.
- Because device values are now always concrete, a device change in the UI always
  restarts the engine (the old auto↔active-device skip-restart comparison is dead).

## Consequences

- One source of truth: what is in the config is what runs (modulo provider
  availability, which is validated loudly rather than silently re-ranked away).
- Windows users get a ~50 MB wheel instead of ~2 GB by default; CUDA costs one
  dropdown selection.
- Linux + AMD machines now run on CPU. This is accepted until the MIGraphX EP
  matures; keeping a dead ROCm flavor would have blocked `uv lock` maintenance.
- `"openvino"` devices on Linux do not trigger a bootstrap sync (`intel-linux` must
  already be installed; a warning notes it is not synced).
