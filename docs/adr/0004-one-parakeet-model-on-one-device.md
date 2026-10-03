# One Parakeet model serves both passes, on one device

Babelfish runs a single Parakeet TDT model (`nemo-parakeet-tdt-0.6b-v3`, via `onnx-asr`),
loaded once by `STTEngine`. The Ghost pass re-transcribes a sliding window of in-progress
audio on a throttle; the Final pass transcribes the completed utterance once. Both passes
call the same engine, on the same device, resolved once at process start.

This supersedes [ADR 0001](0001-each-stage-owns-its-own-model.md) (each stage owns its own
model) and [ADR 0002](0002-placement-is-static-and-shares-one-gpu.md) (placement modes).
Neither was ever implemented: the code never grew a second model, a role registry, or a
`--placement` flag. The decision is recorded here so it is not silently re-litigated.

## Considered Options

**Two stages, two models** (ADR 0001/0002). The Ghost Stage would have used a
Nemotron-family streaming decoder on the GPU while Parakeet served the Final Stage on the
CPU. Rejected, for three reasons:

- **ONNX Runtime DLL management makes the split impractical.** Serving two different ONNX
  model stacks side by side in one process (sherpa-onnx for a streaming Nemotron model
  next to onnx-asr's ORT sessions) means coexisting runtime wheels and conflicting DLL
  load orders on Windows. This was known the last time the project was worked on and had
  to be rediscovered.
- **Over-engineering for a pet project.** A second model, a stage-to-model binding, and a
  placement vocabulary are all machinery for an accuracy/latency win that the sliding
  window Ghost pass already approximates.
- **The `split` placement was the worst part.** Ghost-on-GPU / Final-on-CPU exists only
  to keep two runtimes apart; once there is one model, there is nothing to split.

**Streaming decoder via sherpa-onnx only.** Keeping Parakeet for the Final pass and adding
a sherpa-onnx streaming model for the Ghost pass alone. Rejected for the same DLL-conflict
reason: the packaging problem is between the two runtimes, not between the two models.

**Status quo ante** (chosen). One model, two passes, one device — which is also what the
device-resolution code (`placement.resolve_device`) already expresses.

## Consequences

**Self-calibration stays.** The startup benchmark, the throttle and sliding-window fields
on `PerformanceProfile`, and the tiers in `engine.benchmark()` remain canonical: with one
model serving both cadences, measuring its latency against the Ghost throttle is exactly
the right calibration. ADR 0001's claim that self-calibration is gone is reversed.

**`ghost_throttle_ms` is minimum spacing, not a gate.** Since the reactive-Ghost rework,
the throttle no longer delays display of an inference that already finished: Ghost text
is shown as soon as inference completes, and `ghost_throttle_ms` only spaces out Ghost
*submits* (the last mile — focused-app rendering or typed injection — lives outside
Babelfish and is tuned per user, so inference speed alone does not set the visual cadence).
`0` is cleanly defined as "submit as soon as the worker is free". See the
Reactive Ghost Pass plan.

**`min_padding_s` is a one-model workaround again — Final-only.** Right-padding a buffer
with zeros works around TDT behaviour on incomplete audio; it now feeds the Final pass
only. The Ghost pass has its own `ghost_padding_s` (default 1.0 — bumped from 0.0 after
live testing showed the first, unpadded windows transcribe to empty text, delaying the
first *visible* Ghost by ~400ms). The one-padding doctrine ("`min_padding_s` feeds both
passes") is split by this rework.

**Spelling assumptions are safe.** Downstream code may again assume both kinds of
transcript text come from the same model's formatting.

**Ghost latency is bounded by Parakeet.** The Ghost pass is only as fresh as the throttle
and window allow, and each update pays a whole-window decode. If a true incremental
decoder is ever wanted, that is a new decision with new research — the previous
investigation was deleted rather than archived.

**One device, resolved once.** `hardware.device` (or `auto` → highest-VRAM discrete GPU,
falling back to CPU) applies to the whole engine. There is no per-stage device and no
placement mode to configure.
