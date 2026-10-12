# CPU default with a device-keyed weights ladder

Status: Accepted

Implemented from the integration plan `~/.opencode/plan/redux-default.md`,
from the measured evidence in
[the Parakeet Redux CPU prototype report](../prototypes/2026-10-12-parakeet-redux-cpu-report.md)
(plan predecessor: Track B validated the whole mechanism live).

## Decision

New users get **Parakeet Redux int4 via onnx-asr on CPU** as the
out-of-the-box default, on **Windows and Linux alike**, instead of the
GPU-first default (DirectML on Windows, CUDA on Linux). GPUs remain an
explicit opt-in that keeps the fp32 v3 model. Concretely:

1. **The fresh-config default device is `cpu` on every platform** (D2).
   ADR 0007 is untouched: `"cpu"` is a concrete backend, never `"auto"`.
   GPUs are reached two ways: write `hardware.device` in the config
   (existing `dml`/`cuda` values keep working, unchanged, on fp32 v3), or
   pass the new `babelfish --gpu` flag — an in-memory override to the best
   detected backend, the mirror of `--cpu`.
2. **The weights ladder is device-keyed (D3):** `cpu` resolves
   `models/nemo-parakeet-tdt-0.6b-v3-redux`, any GPU backend resolves
   `models/nemo-parakeet-tdt-0.6b-v3`. `MODEL_NAME` stays the onnx-asr
   registry key — whatever weights sit in the resolved directory get
   loaded (the load-bearing property Track B exercised with zero code
   changes). The ladder is strict: no cross-card fallback. `hardware.model`
   (`"v3" | "redux"`, new optional config key, default device-derived)
   forces one card — the A/B knob on a GPU machine. GPU + int4 MatMulNBits
   is deliberately out of scope (GPU users keep the model we already test).
3. **Device decides flavor, provisioning, and launch (D1).** One helper,
   `_effective_device()`, is consumed by detection, provisioning, and the
   launch plan: `VOGON_FORCE_CPU` / `--cpu` CLI passthrough → cpu, config
   `hardware.device` as written, legacy `''`/`auto`/`rocm*` → platform
   default. A forced-CPU run syncs no GPU wheel and provisions no GPU
   weights — the layering anomaly observed 2026-10-12 (GPU environment
   spinning up around a CPU inference) is structurally gone, and the
   startup banner states the effective device whenever it differs from
   the config's.
4. **Provisioning is device-keyed (D4).** The CPU card comes from
   `eschmidbauer/parakeet-redux-onnx` at a pinned revision
   (`1c285ba78d6f1880803f65355133a5ad3559a407`, CC-BY-4.0 derivative of
   moondream/parakeet-redux), exactly four files (`config.json`,
   `vocab.txt`, `encoder-model.onnx`, `decoder_joint-model.onnx`) — never
   the repo extras — with SHA-256 digests logged at first provision. GPU
   provisioning is unchanged. `hardware.model` redirects provisioning so
   bootstrap and engine never disagree about the card.
5. **Calibration fingerprints gain weights identity (D5).**
   `weights_identity(model_dir)` — SHA-256 over file names + sizes, plus
   full content of the small files — so an fp32 bench and a redux bench
   can never share one key (the prototype's measured silent-overwrite
   bug). `CALIBRATION_SCHEMA_VERSION` bumps to 2: stored v1 entries are
   ignored once and re-benched. Every other ADR 0013 mechanism (cap 4,
   tier hysteresis, canary ±25%) is unchanged.

## Why CPU + redux as the default

The Track B prototype measured, on the real pipeline, on an AVX2-only CPU:

- **Footprint:** 418 MB on disk and a 418 MB first-run provisioning
  funnel, vs 2.44 GB — a ~6× lighter first run.
- **Load:** 3.9× faster model load (1.00 s vs 3.86 s on CPU).
- **Quality:** transcripts equivalent to fp32 v3, word-for-word on all 5
  bundled fixtures modulo tiny noise-axis wobbles.
- **Latency:** 12–18× real-time Ghost on that same desktop, steady-state
  RTF ≤ 0.087 under the live `OMP_NUM_THREADS=1` caps; the int4 dequant
  overhead costs ~15% more per 3-s Ghost window than fp32, and long-form
  Final passes run ~15% *faster*.

The trade is deliberately accepted: raw short-window CPU latency was
never the plan's goal — on this machine the fp32 v3 encoder measured
~15% faster per 3-s window — because the default install base is
dominated by machines where a 2.4 GB GPU-first download plus a GPU
wheel sync buys complexity the CPU path avoids. The big latency lever
(that class of machine's GPU) remains one config edit away and keeps
today's exact behavior.

## Consequences

- **First-run download and model load rotate with the weights card.** A
  later card change re-triggers provisioning (skip-if-present still keyed
  by the directory) and re-benches calibration once (schema v2 weights
  component), then caches.
- **Both cards may share the cache side by side** (~2.9 GB worst case) on
  a mixed machine. No automatic pruning; a user can delete the unused
  card. Documented in `launcher.md`.
- **The engine-side subprocess `--cpu`/effective-device rules and the
  bootstrap's are one helper's semantics** — tests pin that a config that
  says `cuda` but runs under `VOGON_FORCE_CPU` produces zero GPU flavor
  sync and zero GPU provisioning.
- **VogonPoet coordination note:** if VogonPoet *creates* a first-run
  config itself, its own default device may still say `dml` today. Such a
  config is a valid explicit GPU opt-in (the fp32 v3 path) and keeps
  working; for the CPU default to be the first-run experience there as
  well, the Kotlin provisioner's creation default should switch to `cpu`
  in a synchronized change (accepting app-overrides-user in the interim).
- **Camera-shy leftovers:** `scripts/run_redux.py` and the staged
  `models/nemo-parakeet-tdt-0.6b-v3-redux-export` keep their prototype
  roles (weights-swap launcher / staged export for future GPU int4 A/B);
  the day-to-day CPU path no longer needs them — the default engine run
  on a CPU device *is* the redux card.

## Tests

Coverage pins: the effective-device override routed at detection (env and
CLI passthrough, banner logged; pure-GPU/pure-CPU configs unchanged by
Phase A); cpu-device flavor selection (Windows + Linux); launch-plan
`--cpu` append without double-flagging; the provisioning card table
(device → dir/repo/revision/patterns; `hardware.model` redirect); models
destination resolution; the engine ladder (cpu → redux, gpu → fp32,
override forces one card, strict no-cross-card fallback, weights tag in
the log line and capture header); fingerprint keying by the weights
component (identical cards identical, size/content changes rotate,
fp32-CPU vs redux-CPU distinct entries); stale store re-bench.
