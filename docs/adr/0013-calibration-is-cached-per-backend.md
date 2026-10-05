# Calibration is cached per acceleration backend and canary-checked every launch

Status: Accepted

Supersedes two clauses of [ADR 0011](0011-calibration-always-runs-and-never-persists.md):
*"the benchmark runs on every startup"* and *"applied in memory only — never
persisted"* — including that ADR's 2026-10-04/05 amendments. The benchmark now
runs its full probe matrix once per acceleration backend, persists the result
in the config file's top-level `calibration` section keyed by a fingerprint,
and every later launch verifies the stored profile with a **canary** — one
discarded warm-up plus one inference at the stored operating point — before
reusing it. ADR 0011's other decisions (no tier override, no manual knob,
survivable fallback posture, `PerformanceProfile` as the output type,
un-bundled constant `min_padding_s`) are unchanged.

## Why the ADR 0011 posture had to go

ADR 0011 replaced a latched benchmark with an always-runs benchmark scored on
2.5 s of **digital silence** against a hand-picked tier table
(40/80/150 ms → throttle/window/min-padding bundle). Measured against real
speech on this machine (Oct 5 2026), that posture is wrong in four ways:

1. **Silence is not a Ghost-shaped probe.** Silence 2.5 s on CUDA = 45.8 ms →
   tier `high`; the same card measures 30–39 ms on real speech cells →
   `ultra`. The table demoted the card purely on probe workload.
2. **One scalar cannot serve both passes.** Ghost windows rank CUDA 37 <
   CPU 172 < DML 261 ms; Final utterances (15–18 s) rank CUDA 135 < DML 369 <
   CPU 727 ms. DML is the slowest Ghost backend and 2× faster than CPU at
   Final on this machine. A single tier is one number for a two-dimensional
   reality.
3. **The window must come from a measured curve.** DML's cost is bimodal in
   window length: ~57 ms at ≤2.0 s windows, ~260 ms at ≥2.3 s (4.5×) in its
   Oct-5-morning regime. The old table gave tier `high` (from a 69.5 ms
   silence probe) → window 2.5 s → landed exactly in DML's slow regime.
4. **The tier table has no derivation.** Introduced in `d41a37e`
   (2026-02-11): hand-picked boundaries over one scalar mapping to a
   three-field bundle, with a `low_power → min_padding 1.0` semantic bug
   ADR 0011 already flagged.

## The probe matrix (real speech, bundled, raw)

Five real-speech fixtures ship as package data
(`src/babelfish_stt/calibration_assets/`, ~1.4 MB, copied as-is from the
test corpus — offline-safe startup, no download machinery for a payload
this size): `unicode_speech` (2.30 s), `multiple_words` (3.86 s),
`hello_hello` (2.93 s), `joke` (18.57 s), `dictation_fr` (15.33 s).
16 kHz mono, no clipping, natively at realistic mic level
(RMS 0.011–0.024). They are fed **raw** — no RMS normalization (measured
~8% effect and not workload-neutral in principle), so probe bytes are
identical on every backend.

- **Ghost cells:** 5 fixtures × candidate windows {1.0, 1.5, 2.0, 2.5, 3.0},
  sliced **onset-aligned** (each fixture's leading silence is skipped so
  every cell contains speech — onset slices can transcribe `""`, measuring
  a cheaper workload than intended). Per cell: 1 discarded warm-up + 3
  timed probes, per-cell median. 2.0 must stay in the set — the DML cliff
  edge.
- **Cohorts and outlier rule:** the cohort for a window column is the
  median of its 5 fixture cells; any cell median > 2× its column's cohort
  is dropped and logged, and the cohort recomputed from survivors.
- **Final cells:** per fixture longer than 2.6 s, one discarded warm-up +
  one full-length pass → informational Final RTFx. The warm-up is load-
  bearing: a full-length audio is a new input shape the matrix never saw
  (slices cap at the largest candidate window), and the first inference at
  a new shape pays a large one-time cost (measured on CUDA: 157 ms vs
  ~37 ms warmed for a 3.9 s clip; 223 ms vs ~135 ms for an 18.6 s clip).
  Without it the persisted RTFx under-reports steady state by 2–4×.

## Operating-point assignment

**The Ghost window comes from the measured curve, not a tier lookup:** the
largest candidate window whose column cohort stays within
max(**budget 200 ms**, **1.5× the best column's cohort**). The budget keeps
a flat-cost backend (CPU: per-call-overhead bound, measured flat
~110–230 ms) on the max window; the headroom multiple lets a uniformly
slow backend still spread to larger windows when nothing got relatively
worse. A cliff-shaped backend lands below its cliff.

**Tier and throttle come from the cost AT the chosen window** — the
operating point. The throttle floors are the UX cadence anchors and are
unchanged (100/150/250/400 ms). The boundaries are re-derived from those
floors instead of hand-picked: pacing is `max(cost, throttle)`, so each
tier's boundary is the operating cost below which its throttle still paces
submissions with ~2× headroom — **<50 `ultra`, <100 `high`, <200 `medium`,
≥200 `low_power`**, anchored to the cadence each tier promises, not to
hardware classes.

**`min_padding_s` is constant 2.0** — quality-driven, un-bundled from the
tier (fixes the `low_power → 1.0` bug). `ghost_padding_s` stays fixed 1.0
(ADR 0010-era live finding).

Measured with this implementation (medians; VOGON shared-cache model):

| Backend | Cohorts @1.0/1.5/2.0/2.5/3.0 (ms) | Window | Cost @ window | Tier | Throttle | Final RTFx |
|---|---|---|---|---|---|---|
| CUDA | 28.6 / 32.7 / 31.9 / 34.1 / 36.2 | 3.0 s | 36.3 | `ultra` | 100 | 123× |
| DML | 50.1 / 227 / 262 / 270 / 288 | 1.0 s | 50.1 | `high` | 150 | 29× |
| CPU | 122.8 / 140.3 / 151.5 / 166.2 / 195.5 | 3.0 s | 195.5 | `medium` | 250 | 20× |

The DML label was `high` before this rework too — the label is nearly
cosmetic; the operating point (the ~260 ms/submit window-2.5 regime) was
the product, and it is now chosen from the curve. On the Oct-5-morning
regime (cliff at 2.0→2.3 s) the same machinery picks window 2.0 s at
~57 ms, as the rework plan expected.

## Persistence: the `calibration` section + canary

**Cache, keyed by fingerprint.** A new top-level config section
`calibration` — deliberately NOT `pipeline.performance`, which keeps its
live strip-migration semantics from the ADR 0011 rework:

```
calibration: {schema_version, profiles: {fingerprint: entry}}
```

`entry` holds the profile fields (throttle/window/paddings/tier) plus
`operating_cost_ms`, `final_rtfx`, the full measured cell table (`cells`),
and `benched_at`. The store is capped at **4 entries** (one per
acceleration backend), pruned oldest-first by `benched_at`.

**Fingerprint** = resolved backend + resolved device name + quantization +
model name + bench schema version + **onnxruntime version + onnx-asr
version**. It uses the **resolved** backend (`engine.device_type` after
init — the GPU→CPU fallback reassigns it in place) so a driver-broken
launch can't poison a `dml` entry with CPU measurements, and it never
names `"auto"` (ADR 0007's no-auto posture applies to cache keys too).

**`calibrate()` flow:** fingerprint → **miss:** run the matrix, persist,
return. **Hit:** run one canary probe — 1 discarded warm-up + 1 inference
at the stored operating point (the canary fixture's own stored cell, so
the comparison is exact). Within **±25%**: return the stored profile —
zero matrix cost. Outside: invalidate, run the full matrix **that
launch**, overwrite the entry. The warm-up matters: on a cache hit the
canary is the session's first inference, and its cold session/kernel init
would otherwise read as deviation and defeat the cache.

**Tier hysteresis:** a re-bench landing within **±15% of a boundary** keeps
the previous entry's tier label; the fields (window/throttle) take the new
measured values regardless — the label is nearly cosmetic, the operating
point is the product. This is for CPU, which straddles the 200 ms boundary
across days/sessions (145–227 ms observed).

**Crash posture:** a probe crash or partial failure persists nothing and
falls back to `PerformanceProfile()` defaults — the survivable posture is
unchanged. There is no manual override knob.

## Why a canary instead of just caching

Measured on this machine: DML's cost is bimodal **across sessions** — one
session measured the same cells (same audio, byte-identical model, same
venv, same load mode) at ~70 ms @2.5 s; three later sessions all measured
~235–262 ms, rock-stable (±2 ms) within each session. RMS normalization
was worth only ~8%; neither load mode nor model source nor gain explains
the flip — some session-level state (driver/thermal/DML cache) does. The
Oct-5 rework pass later measured the **cliff position itself** move: the
morning sessions had the fast regime extend to 2.0 s windows; two
consecutive later sessions measured it end at 1.0 s (with the 1.0 s cost
sitting exactly on the 50 ms `ultra` boundary — 49.2 vs 50.1 ms across two
sessions). A fingerprint cannot see any of this; a one-shot benchmark
could cache the lucky session's operating point forever; always-benching
pays the full matrix every launch to catch what the canary catches for
one warm-up + one inference. The canary is the replacement for ADR 0011's
"always runs everything".

## Consequences

**First launch per acceleration backend pays the full matrix** (~104
inferences: measured 5.7 s CUDA, ~25 s DML, ~20 s CPU against the ~4 s
model load). **Every later launch pays one warm-up + one canary
inference** (measured 0.10–0.35 s calibrate time) unless the canary flags
a regime change. That is the trade ADR 0011 refused to make; the canary
makes it safe: a cached profile is only ever reused when this session's
own inference agrees with it.

**The config file gains a `calibration` section** — bench output, not user
configuration: stripping/migrating `pipeline.performance` (still done on
load) must preserve it. The WebSocket config broadcast includes it
(diagnostic value).

**Cost flips self-heal within one launch,** including the much-faster
direction (a session that suddenly runs 4× faster than the stored profile
is also a regime change worth re-benching over).

**Tests.** Coverage pins: onset-aligned slicing; cohort/outlier drop;
window selection (flat → max, cliff → below the cliff, budget/headroom
binding); the boundary table and hysteresis (kept label, measured
throttle); fingerprint rotation on any component change (including the
resolved-backend rule on a broken dml request); cache miss/hit/deviate
flow; stale schema or versions → miss; prune at cap; raising probes →
defaults and nothing persisted; the strip-migration preserving
`calibration`.
