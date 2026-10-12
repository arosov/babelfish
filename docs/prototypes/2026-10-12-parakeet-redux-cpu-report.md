# Prototype report: Parakeet Redux on CPU — Photon vs onnx-asr

**Date:** 2026-10-12 · **Plan:** `~/.opencode/plan/parakeet-redux-prototypes.md`
**Machine:** i9-9900K (AVX2, no AVX-512/VNNI), RTX 2080 SUPER (unused — all runs CPU-forced), Windows, Python 3.12, onnx-asr 0.12.0, ORT 1.30.0.

## Method (deviations from the plan, all deliberate)

- **Replay fixtures instead of live mic dictation:** all runs streamed the 5 bundled
  calibration fixtures (dictation_fr 15.3 s, joke 18.6 s, hello_hello 2.9 s,
  multiple_words 3.9 s, unicode_speech 2.3 s) through the real pipeline via the
  `--replay` harness (real-time paced; identical Ghost dynamics), capture JSON per
  run. Reproducible and mic-independent.
- **CPU-forced all runs** (`--cpu` / in-memory `device="cpu"`): apples-to-apples with
  Track A's Photon CPU requirement.
- **Weights swap in the shared cache**, not repo-local `models/`:
  `resolve_model_path` checks `cache.cache_dir` **first**, so the swap that actually
  changes what loads is `F:\vogonpoet_cache\models\nemo-parakeet-tdt-0.6b-v3`. The
  original fp32 v3 dir was parked as `…-v3int8-baseline` during Track B and restored
  after. The Redux export stays staged at repo-local
  `models/nemo-parakeet-tdt-0.6b-v3-redux-export` (4 files, ~418 MB) for future A/B.
- **Runs used a scratch config copy** (`.scratch_logs/cfg/babelfish.config.json`,
  `system_input.enabled=false` — replay forbids typing). The real
  `babelfish.config.json` was **never modified**; the CPU calibration profiles were
  persisted into the scratch copy only. `git status` shows exactly two new paths:
  `scripts/prototype_redux_photon.py` and the gitignored `.scratch_logs/` (+ gitignored
  `models/…redux-export`).

## Comparison table (all numbers this machine, CPU)

| Metric | Baseline v3 fp32 (ORT) | Redux int4 (ORT, Track B) | Redux (Photon, Track A) |
|---|---|---|---|
| Weights on disk | 2.44 GB (+41 MB) | 343.8 MB + 72.5 MB decoder | — |
| Model load (cpu) | 3.86 s | **1.00 s** | refused at startup |
| Calibration bench → window / tier / throttle | 3.0 s / MEDIUM / 250 ms | 3.0 s / MEDIUM / 400 ms | — |
| Operating cost @ 3.0 s window (cohort) | 187.3 ms | 215.0 ms (+15%) | — |
| Steady-state Ghost window (dictation_fr, 3.0 s) | 192–215 ms (RTF 0.064–0.072) | 243–261 ms (RTF 0.081–0.087) | — |
| Steady-state Ghost window (joke, 3.0 s) | 162–187 ms (RTF 0.054–0.062) | 182–203 ms (RTF 0.060–0.068) | — |
| ⚡ First Ghost onset (dictation_fr / hello_hello / joke / multiple_words / unicode_speech) | 384 / 384 / 384 / **128** / 384 ms | 544 / 576 / 544 / **128** / 576 ms | — |
| Ghost frames captured (5 fixtures) | 102 / 18 / 92 / 22 / 16 | 62 / 8 / 80 / 16 / 10 | — |
| Final pass (calibration cells) | multiple_words 201.7 ms, hello_hello 200.8 ms, joke 780.4 ms, dictation_fr 823.7 ms (RTFx 19×) | dictation_fr 705.5 ms (RTFx 22×) | — |
| Transcript quality (final text, 5 fixtures) | reference | **equivalent** (see below) | — |

Notes:
- First-Ghost deltas are mostly the throttle/window protocol (250→400 ms), not raw
  inference: first-ghost *inference* ms is 107–126 (v3) vs 119–149 (Redux).
- Steady-state cadence stayed real-time in both runs (RTF ≤ 0.087, throttle-spaced
  submits); more throttle → fewer ghost frames, same coverage.
- The long-form Final pass is **faster** on Redux (int4 packs the encoder → less
  memory traffic on long audio): 823.7 → 705.5 ms on dictation_fr.
- Transcript equivalence (final text): all 5 fixtures transcribe identically modulo
  tiny noise-axis wobbles (`"Ew, that's th…"` → `"You, that's…"`, one lost comma on
  unicode_speech) — consistent with the model card (English 6.55 vs 6.26 WER, noise
  is Redux's worst axis).

## Calibration behavior findings (ADR 0013 in the wild)

- The canary **caught the weights swap**: Redux canary 245.4 ms vs stored 191.8 ms
  (beyond ±25%) → automatic re-bench. Correct behavior.
- **Fingerprint collision caveat:** the fingerprint is
  `cpu|CPU|None|nemo-parakeet-tdt-0.6b-v3|1|1.30.0|0.12.0` for *any* weights sitting
  in the dir — baseline's CPU bench was silently overwritten by the Redux bench
  (same key, last bench wins). If Redux-on-ORT ever becomes a real mode, the
  fingerprint needs a weights-identity component (e.g. model dir content hash).
  Not fixed here (out of scope, throwaway prototype).
- No `hardware.quantization` change needed (already `null`); the export has no
  `encoder-model.int8.onnx`, and `quantization=None` loaded the MatMulNBits encoder
  on CPUExecutionProvider without issue.

## Track A — Photon: documented refusal (verbatim)

`scripts/prototype_redux_photon.py` (the only repo file added) subclasses `STTEngine`
overriding only the model-load path (`md.photon("moondream/parakeet-redux",
device="cpu")` wrapped as `recognize(audio, sample_rate) -> str`); everything else
(padding protocol, calibration plumbing, engine lock, pipeline wiring,
`run_stt_loop` with `listen_immediately=True`) is inherited. Install itself was fine:
`uv run --with moondream` → moondream 2.6.x + kestrel 0.9.x + **torch 2.14.1+cpu**,
44 packages in ~11 s, all in the uv overlay (project venv untouched).

The load refuses (plan outcome 2, "clean negative finding"):

```
NotImplementedError: ternary weights need an int8 matrix-multiply kernel on the CPU
(avx512vnni, avxvnni or avx2 on x86; neon-i8mm, neon-dotprod or neon-mull on aarch64);
the path in use here is 'scalar', so there is nothing to run them on here
```

**CI cross-check (repo inspection):** the public `m87-labs/kestrel` repo ships
`tests/asr/test_parakeet_ternary_cpu.py` — a CPU-transcribe test through the ternary
path (`device="cpu"`, tiny synthetic export) that would fail on any Windows AVX2-only
box with exactly our probe error. But the public repo contains **no CI workflows at
all** (no `.github/` — the kestrel-kernels payload docstring cites a
`.github/workflows/kestrel-kernels.yml` that lives in the private
`kestrel-proprietary` tree, where CI runs on their own Modal fleet). The public PR
bodies cite Modal-based validation only. Net: nothing in their visible CI has ever
executed the ternary ISA dispatch on Windows hardware, and the payload's own
"carries it on every platform, CI asserts" claim covers payload *presence*, not the
per-platform ISA dispatch.

**Characterization (probed, not hand-waved):** on this same process/machine,
`torch.backends.cpu.get_cpu_capability()` → `AVX2`, while
`kestrel_kernels._cpu.gemm_isa_available('avx2')` → `False`
(`avx_vnni`/`avx512vnni` also False; `scalar` True). oneDNN sees AVX2; kestrel's
protected CPU payload (`kestrel_cpu.kstlc`, 51 KB) probes scalar for every ISA.
Forced-path test (`kestrel_kernels.ternary.set_gemm_isa('avx2')` before load — now a
built-in test hook via `REDUX_FORCE_ISA=avx2`): the model **loads** (the probe is the
only load-time blocker), but the **first real matmul then raises**
`ValueError: no 'avx2' matrix-multiply path on this machine`. Ground truth: the
Windows cp312 payload genuinely does not ship the AVX2 (nor VNNI) ternary-GEMM path
its own load-time error message says it wants; this is a build-shipping gap, not a
hardware floor and not fixable by any additional package. **Python-version escape
hatch closed:** every Windows amd64 wheel tag (cp310, cp311, cp312, cp313, cp314,
kestrel-kernels 0.7.5 — probed per tagged build) reports `avx2=False` / `scalar`
uncorrected, while the Linux build of the same project selects `avx2` on a
same-ISA-profile Comet Lake i5-10300H at 13.98× real-time (independent third-party
measurement, github.com/chethan62/parakeet-redux-local). The kernels are packed,
protected, and licensed under M87 Labs' non-reverse-engineering agreement, so the
only licensed fixes are an upstream Windows-wheel rebuild or running the Linux
wheel (e.g. WSL2). No other SIMD lever applies
on this chip (AVX2 int8 without VNNI is emulated and modest; there is no AVX-512/BF16
here). Per the plan, not chased further: the 113×-CPU claims presumably come from
builds/platforms where the x86 path ships.

## Verdict

**Redux is viable on this machine's CPU only via onnx-asr (Track B), and the trade
is footprint-for-Ghost-speed, not a free win:**

- Redux-ORT costs ~15% more per Ghost window on CPU (int4 dequant overhead dominates
  short windows) but transcribes long-form ~15% faster, loads 3.9× faster, and is
  ~7× smaller on disk. Transcripts are equivalent.
- The stock pipeline handled the swap with zero code changes; calibration adapted
  the throttle (250→400 ms) to keep cadence guarantees, and the canary caught the
  swap. The only shared-code gap found is the **fingerprint/weights-identity
  collision** (same key for different weights) — a real integration blocker to solve
  before Redux could become a default.
- The `mrfakename` int8-decoder contingency was **not needed**: the decoder does not
  show up hot in the per-window profile (encoder + dequant dominate at 3.0 s windows);
  noted as motivation for a later follow-up only if window size grows.
- Photon cannot run here today: the Windows cp312 kestrel payload ships without the
  AVX2/VNNI ternary-GEMM path (proven by the forced-ISA test above), so no package
  or configuration on this machine can serve it. Re-evaluate only after an upstream
  kestrel-kernels fix; the prototype script is ready (`REDUX_FORCE_ISA` hook for
  future builds).
- The fastest per-window CPU path on this chip is the fp32 v3 encoder (187 ms
  cohort @ 3.0 s) — Redux's int4 packing optimizes footprint and long-form traffic,
  not short-window CPU latency without VNNI. The big latency lever on this machine
  is the GPU (existing CUDA profile: 32.7 ms @ 3.0 s, ~5.7× the CPU).
- Day-to-day usage: `scripts/run_redux.bat` (and `script`/`--restore-only`) runs the
  stock pipeline on Redux weights with run.bat semantics (live mic, terminal Ghost
  updates, `--type` passthrough, auto swap/restore); Track A's live-mic mode lives
  in `scripts/prototype_redux_photon.py` (default mic; `--replay` for fixtures).

**Recommendation:** keep fp32 v3 as the default; keep the Redux-ORT export staged
for low-disk/low-VRAM targets, gated behind a weights-identity-aware fingerprint and
an explicit config choice. Re-bench Photon after a kestrel fix.

**Addendum — decision (2026-10-12, post-experiment):** Redux via onnx-asr was
validated live on this machine (RTF 0.05–0.09, 12–18× real-time on AVX2-only CPU,
transcripts equivalent, loads 3.9× faster) and **adopted for daily CPU dictation
use via `scripts/run_redux.bat`** (weights-swap launcher, live mic, terminal Ghost
updates, `--type` passthrough). The Photon/kestrel path is **parked**: the gap is an
upstream Windows-wheel build issue (documented above), and measuring it again on
any future kestrel-kernels release takes one probe —
`uv run --no-project --python 3.12 --with kestrel-kernels python .scratch_logs/probe_isa.py`
— plus `REDUX_FORCE_ISA=avx2` only if the probe stays false while the payload
learns the path. One useful remaining datapoint, zero cost once an AM5 (Zen 4/5,
AVX-512 VNNI) machine is at hand: run the same probe there to establish whether the
Windows payload ships only the `avx512vnni` tier — that would restrict the Windows
gap to AVX2-only machines (the 2017–2022 Intel desktop install base) and sharpen
the upstream issue accordingly. Filing the upstream issue remains optional and
idempotent.
