# Babelfish owns its bootstrap, standalone and driven alike

Babelfish ships its own `scripts/bootstrap.py` and its launchers run through it, in both
standalone terminal mode and when driven by VogonPoet. The bootstrap is the single owner
of environment provisioning: hardware detection, `uv sync` with the right ORT extra, model
provisioning, and DLL-path setup for the ONNX Runtime execution provider. VogonPoet stops
injecting its own copy of the script and instead invokes babelfish's, selecting the
driven mode via the existing `VOGON_*` environment-variable contract.

Until this decision, the provisioning logic lived in `VogonPoet`'s resources
(`composeApp/src/jvmMain/resources/scripts/bootstrap.py`), injected into the bundled
babelfish zip at build time. A dev checkout of babelfish had no equivalent: its own
`scripts/run.bat` resolved uv and the shared caches, then ran `uv run babelfish` directly,
with no DLL-path setup, no ORT-flavor sync, and no model provisioning of its own.

## Why

Running `scripts/run.bat` standalone produced a silent CPU fallback with an error banner:

```
[E:onnxruntime:...] Error loading ".../onnxruntime/capi/onnxruntime_providers_cuda.dll"
which depends on "cublasLt64_12.dll" which is missing.
```

The GPU wheel (`onnxruntime-gpu`, plus the pip `nvidia-*-cu12` packages) was installed;
the DLLs were on disk under `.venv/Lib/site-packages/nvidia/<lib>/bin/`. The failure is a
loader-path problem: on Windows, nothing in babelfish's code or launchers puts those
scattered `bin/` directories on the DLL search path, so ORT's CUDA provider bridge cannot
resolve its dependencies, catches the failure in `engine.py`, and silently retries on CPU
— which also poisons the startup benchmark: the config self-calibrated to CPU-tier ghost
cadence from a run whose only deficiency was a missing `PATH` entry.

VogonPoet did not have this bug because its bootstrap does the work babelfish lacks:
`get_env_with_dll_injection()` prepends ONNX Runtime's `capi/` directory plus every
`site-packages/nvidia/*` DLL directory to the child's `PATH` (or `LD_LIBRARY_PATH` on
Linux) before exec'ing babelfish's server. Babelfish's own launcher skips all of that,
and copying it piecemeal into `run.bat` would fork the logic between repos.

Two probabilities made piecemeal fixing unattractive: the same hole would need re-fixing
for model download when no VogonPoet cache exists, and the driver venv drifts from the
driven one (a mixed `onnxruntime` 1.24.2 + `onnxruntime-gpu` 1.23.2 install was found in
this repo's `.venv` — the artifact of hardware-mode switches that the driven bootstrap's
marker/reinstall mechanism heals, and a plain `uv run` in a terminal bypasses).

The root inconvenience was owning the environment halves in two places. Babelfish is
already the autonomous, hardware-aware component by design (hardware probing, device
resolution, self-calibration all live here — see [ADR 0004](0004-one-parakeet-model-on-one-device.md)
for the one-model/one-device decision). Provisioning the environment that model runs in
is the same responsibility, just earlier in the lifecycle.

## Considered Options

**Patch the launchers with PATH prepends** (chosen for tests only). Prepend
`.venv/Lib/site-packages/nvidia/*/bin` plus `onnxruntime/capi` in `scripts/run.bat` /
`run.sh`. Minimal diff, unblocks CUDA in the existing flow. Rejected as the full fix: it
duplicates the DLL knowledge again (the repo's own `tests/AUDIO_VERIFICATION_TESTS.md`
already contains these recipes as manual workarounds), does nothing about model
provisioning or venv drift, and leaves the provisioning contract documented only in
`readme.md` caveats.

**Register DLL directories in-process only** (`os.add_dll_directory` at engine init).
Also necessary — see Consequences — but insufficient alone: it cannot pick the right ORT
flavor (`uv sync --extra nvidia-win` vs `--extra cpu`) nor download the model, which is
the other half of "fully standalone".

**Keep bootstrap.py in VogonPoet.** Status quo. Rejected: the script's own location
logic is already two-headed ("Prod babelfish dir not found, searching for dev location…")
because it is owned by the wrong project. Every babelfish repo checkout is
self-inconsistent without VogonPoet, and the release process must carry a file that
barely belongs to it.

**Move bootstrap.py to babelfish** (chosen). One owner, two modes of the same logic, and
the VogonPoet contract reduced to env-vars + a script path.

## The contract

VogonPoet tells babelfish what it wants to happen by setting environment variables
before invoking `scripts/bootstrap.py`:

- **`VOGON_APP_DATA_DIR`** set → driven mode: stay a status WebSocket on port 8123, write
  the PID file, and finally launch `babelfish --server --port 8123` as before, emitting
  the same stdout markers the Kotlin backend scrapes (`BOOTSTRAP SERVER STARTED`,
  `Launching Babelfish`, and downstream `SERVER: WebSockets running on`), and the same
  status shapes `{"type":"status","message":…,"vad_state":"bootstrapping"}`.
- **`VOGON_APP_CACHE_DIR`** → where both sides put the uv caches, the hw-mode marker and
  the model.
- **`UV_CMD`** → uv binary (managed by VogonPoet or on PATH).
- **`VOGON_FORCE_CPU`**, and the config key `hardware.device`, behave as before.

Absent those variables, the script is pure standalone: detect hardware → sync the right
ORT extra → provision the Parakeet model from its HF repo if not cached → build the DLL
env → exec `uv run --no-sync babelfish <passthrough args>` in the foreground, all logging
to stdout/stderr, no server and no WebSocket bootstrap phase.

Both modes share: `HardwareDetector.get_best_mode()`, the `.last_hw_mode` marker plus
`uv sync --extra <extra> --reinstall-package <ort-flavor>` self-heal (this is what fixes
mixed ORT wheel installs — the duplicate `onnxruntime` + `onnxruntime-gpu` found in this
repo's venv), model provisioning from `istupakov/parakeet-tdt-0.6b-v3-onnx`, and the DLL
injection. The launcher scripts only resolve uv, seed the shared cache variables, and
delegate; no hardware or DLL logic ever lives in `.bat`/`.sh` again.

## Consequences

**VogonPoet changes are part of this decision** (same release window):

- `bundleBabelfish` stops overwriting `<bundle>/scripts/bootstrap.py` with its resource
  copy — the babelfish zip now carries the script natively. Delete the VogonPoet-owned
  copy once babelfish's version is canonical in a published babelfish release.
- `findDevBootstrap()` prefers `<devBackend>/scripts/bootstrap.py` and falls back to the
  resource copy during transition.
- Everything else on the Kotlin side already conforms: the env contract, stdout scraping,
  and status-message handling are the contract, and they are unchanged.

**A standalone checkout is now honestly standalone.** `run.bat` works from a fresh
machine: uv resolved (existing logic), shared caches seeded (existing logic), the proper
ORT flavor synced, the model downloaded to `VOGON_APP_CACHE_DIR`/`models` if absent, DLLs
registered, server started. No VogonPoet install assumed beyond what `run.bat` already
does for uv and `VOGON_APP_CACHE_DIR`.

**The `--no-sync` + `--reinstall-package` pair is where CPU↔GPU switching self-heals.**
The hw-mode marker decides when to re-sync (the marker lives in the shared
cache, so the standalone and driven flows agree on what the venv currently contains), and
the ORT-flavor reinstall pins out stale wheels. This is precisely the correction needed
for the mixed installs observed here; it is retained as-is, belonging to the script not
to either consumer of it.

**In-process DLL registration is also added.** `register_nvidia_dll_dirs()` in
`babelfish_stt/hardware.py` performs the same directory registration (and PATH prepend on
Windows) before any onnxruntime import. It is a safety net for paths that skip the
bootstrap (`uv run babelfish` in tests, CI runs), and it makes the resolved DLL
directories observable at startup, so a silent provider failure again reported as "DLL
missing" can be seen in logs rather than inferred from VRAM deltas.

**The standalone flow also kills the silent CPU-fallback failure mode.** When the CUDA
provider is requested but its DLLs are unresolvable, the fallback to CPU still happens
(that robustness lives in `engine.py` and is worth keeping), but the launch path no
longer makes it happen in the first place.

**Bootstrap in-code documentation, not duplicated README knowledge.** `readme.md`'s
caveat that "VogonPoet's bootstrap.py owns DLL paths" is now inaccurate and should be
updated to point at babelfish's own `scripts/bootstrap.py` as owned here, invoked
(possibly, but not necessarily, by VogonPoet).
