# Calibration always runs at startup and never persists

Status: Accepted

Superseded in part (2026-10-05, the calibration rework): the *"the benchmark
runs on every startup"* and *"applied in memory only — never persisted"*
clauses are replaced by bench-once-per-acceleration-backend, cached in the
config file's `calibration` section and canary-checked every launch — see
[ADR 0013](0013-calibration-is-cached-per-backend.md). The silence probe, the
hand-picked tier table, and the one-scalar→bundle mapping it describes were
also removed there (real-speech probe matrix, window-from-curve, tier at the
operating point). The survivable-failure posture, the median measurement
robustness, and the no-override/no-manual-knob posture below carry forward.

Amended (2026-10-04, the Ghost rework): the tier-override concept is gone.
Calibration is unconditional — there is no `tier` in configuration to skip
it, no latch flag, and no manual override; `pipeline.performance` left the
config schema entirely and stale keys are stripped from existing files on
load. `PerformanceProfile` survives as the calibration's in-memory output
type, passed to the pipeline at construction. The decision below records
the original reasoning; the override escape hatch it introduced lasted
exactly one live run — it still let a stale concrete tier silence the
benchmark, and pacing was never a meaningful user knob.

The startup benchmark (`engine.benchmark()`, `engine.py:259-325`) mis-set this
machine: a CUDA card measured its way into the `low_power` tier — 400 ms Ghost
throttle, 1.5 s window — and the result was latched into `babelfish.config.json`
(`"tier": "low_power"`), so no later launch could correct it. The latched
profile shrank the shared audio region between consecutive Ghost windows, which
made the typed-Ghost append bug of
[ADR 0010](0010-typed-ghost-composing-is-span-based-and-shared.md) fire far
more often than the hardware justifies. Decision: the benchmark runs on every
startup, its measurement is made robust, and its result is applied in memory
only — a concrete `tier` in the config file becomes a manual override that
skips calibration, never a record the benchmark wrote.

## What the benchmark currently gets wrong

Measured on 2.5 s of digital silence, five iterations, arithmetic mean
(`engine.py:269-276`), gated on `tier == "auto"` at startup (`main.py:286-290`),
then persisted via `config_manager.update` (`config_manager.py:220-235`):

1. **The mean latches the cold start.** The first `recognize()` pays
   session/kernel init; averaging it in demotes fast hardware. Four warm ~40 ms
   samples plus one 600 ms cold sample average ~150 ms → two tiers down. The
   tier table's own boundaries (40/80/150 ms) sit exactly where a single warmup
   sample throws the vote.
2. **Persist-and-skip makes the first measurement final.** After one
   calibration run the tier is concrete, every later launch skips the
   benchmark, and no code path ever re-runs it. `server.reconfigure`
   (`server.py:108-137`) does not watch `performance` at all, so even config
   hot-reload cannot invite a re-measure.
3. **Silence measures cheap.** TDT emits no tokens on zeros, so the probe
   measures a cheaper workload than real speech — an unreliable underestimate,
   in both directions across backends.
4. **No error handling.** A transient `recognize()` failure in the 5 probes
   aborts `heavy_init()` and kills startup (`main.py:286-290`), though the
   engine init around it has a GPU→CPU fallback (`engine.py:152-170`).
5. **The CPU branch wastes its own measurement.** Five inferences run, then the
   results are discarded and overwritten with hardcoded CPU values
   (`engine.py:307-312`).
6. **The profile written is also semantically wrong.** `min_padding_s` is
   persisted as 1.0 while config schema default is 2.0 — the tier logic maps
   `low_power` → `padding = 1.0` for `min_padding_s`, so the Final pass on this
   machine runs with less right-padding than any tier intends. (Tier table at
   `engine.py:285-312`.)

## Decision

**Every startup calibrates; the file never records calibration output.**
`heavy_init()` runs the benchmark before the pipeline is built and passes
the computed profile to `StandardPipeline(..., perf=profile)` — applied
in memory only; `config_manager.update` is never called with it. There is
no configured tier to consult: no persisted-tier short-circuit, no manual
override, no latch flag. *(Amendment: originally a concrete tier in the
file meant "skip calibration" — that concept is removed; the tier lives
only as an informational label on the computed profile.)*

**Robust measurement.** One warm-up inference is performed and discarded; the
tier decision uses the **median** of the five probes, not the mean.
*(Amendment 2026-10-05, CPU calibration enabled: all devices probe — the
"probes are skipped entirely when `device_type == "cpu"`" clause is removed
and the CPU tier is no longer fixed. CPU latency spans a wide range in the
wild (RTFx ~1–36, from Cortex A53 to 9800X3D-class), so a single hardcoded
CPU tier cannot serve that spread, and on this machine CPU latency is
per-call-overhead-bound rather than audio-length-bound — measured flat
~190–220 ms from 1.0 s to 3.0 s windows, landing `low_power`. The measurement
picked the `low_power` values over the old hardcoded ones
(throttle 300 / window 1.0 / ghost_padding 0.0), whose
`ghost_padding_s=0.0` is exactly the combination `PerformanceProfile`'s
docstring warns produces empty `""` first windows. Probes cost ~6 ×
~200 ms ≈ 1.2 s of startup on CPU, accepted against the ~4 s model load.
On probe failure, CPU falls back to the same generic
`PerformanceProfile()` defaults as every other device — one posture for
all backends.)* The silence-workload skew is documented in a comment and
accepted: it biases against fast tiers (measured latency under-reads
speech latency), which errs toward a conservative tier, and fixing it
would mean synthesising speech-like audio for no demonstrated need.

**Survivable failure.** Calibration is wrapped in try/except: on any exception,
log a warning and fall back to `PerformanceProfile()` defaults
(`config.py:48-56`) rather than aborting startup — the same fallback posture
engine init already has for device-load failure.

## Consequences

**Startup costs ~6 inferences** (~6 × tens-of-ms on an `ultra`-class GPU,
~6 × ~200 ms ≈ 1.2 s on CPU — under the 2026-10-05 amendment, CPU no longer
skips them) for every launch. That is the price of never trusting a stale
profile.

**The "Calibrating Performance…" status appears every launch.** It is the
normal startup contract, not a one-time event.

**`ghost_throttle_ms` remains what ADR 0004 says it is** — minimum spacing
between submits, not a display gate — and the exaggeration in AGENTS.md:30 and
launcher.md:136 ("calibrates the Ghost pass cadence") gets corrected when docs
are touched next; calibration sets the pacing and window fields, and the
display cadence remains owned by inference completion plus the last mile.

**A previously latched `low_power` profile self-heals.** On this machine the
next `auto` launch recalibrates with the robust measurement and should land
`ultra` or `high` — a larger Ghost window and tighter cadence, which also
enlarges the shared audio region ADR 0010's composer aligns on.

**What was almost chosen, and why not:**

- *Fix the measurement, keep the latch.* The stale-profile bug survives; the
  user must hand-reset `tier` to `"auto"` per machine change.
- *Fingerprint re-benchmark (device+model+ORT fingerprint persisted with the
  tier).* Less startup work, but adds persisted state to keep in sync, and the
  fingerprint cannot see performance drift that changes no fingerprint
  component (driver updates, thermal behaviour). Always-runs is simpler and
  the cost is single-digit milliseconds-scale inferences.
- *Persist only if the tier changed* (write-on-change). Keeps a file-writing
  path that must be explained and tested; in-memory-only is the same effect
  with less mechanism.

**Tests.** Benchmark tests cover: a cold-start-shaped sample list (one large
first sample) does not demote the tier under median; a spiked series does not
demote under median; the CPU branch runs probes and measures a tier from the
table (the fixed CPU tier is gone — amended 2026-10-05); a raising benchmark
falls back to `PerformanceProfile()` defaults and startup proceeds; calibration
is unconditional (no configuration can skip it); no benchmark path writes
`pipeline.performance` to the config file; stale `pipeline.performance` keys
are stripped from existing files on load, idempotently.
