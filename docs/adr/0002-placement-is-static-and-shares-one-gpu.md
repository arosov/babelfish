# Placement is decided once per process and both stages share one GPU

> **SUPERSEDED by [ADR 0004](0004-one-parakeet-model-on-one-device.md).** This decision
> was never implemented — there is one model on one device, and no placement modes — and
> is abandoned. Kept for the record.

Which execution providers the two stages run on is decided at process start from a
placement mode, and never changes while running. `split` (the default) runs the Ghost
model on the GPU and the Final model on the CPU. `all-gpu` runs both on the GPU. `cpu`
runs both on the CPU. Placement is set from the command line; the frontend may choose it
and restart the process, but babelfish itself does not migrate a model mid-session.

When both stages are on the GPU they go to the same one GPU — the highest-VRAM card, or
the one named explicitly in `hardware.device`.

## Considered Options

**Spreading the stages across multiple GPUs.** Rejected: a machine with two cards that
are each individually marginal is not a configuration worth supporting, and supporting it
would require per-stage device selection in configuration — a schema change, Kotlin
changes, and a UI concept, for a machine we would not expect to see in practice.

**Migrating the Final model to the GPU mid-utterance when the transcript grows long.** The
rationale for running both on the GPU is that long final transcripts are slow on CPU. But
utterance length is not knowable in advance, so this would mean tearing down and
reinitialising an ONNX session while the user is mid-sentence and eating a multi-second
latency cliff at the worst possible moment. Rejected for a static decision at startup.

**Reporting placement per device.** Rejected: it is not knowable. Free VRAM is readable
only on NVIDIA, via `nvidia-smi --showmeminfo`; `get_gpu_info` reports total, not free, and
returns `cuda_available: False` for ROCm, OpenVINO, and DirectML entirely. On those
backends the only available policy is optimistic load with fallback.

## Consequences

**`HardwareStatus` stops being single-valued.** `active_device` and `vram_used_model_gb`
describe one model load and become wrong under two. Status must report a device per stage,
which is a change to `babelfish_schema.json`, the Kotlin codegen, and the schema
freshness test.

**A per-model bug is a new failure mode.** The two stages can land on different devices,
or one can fail to load and fall back while the other does not. Startup must tolerate a
stage whose model is unavailable rather than treating it as fatal.