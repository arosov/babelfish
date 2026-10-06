# AMD accelerates via MIGraphX on Linux only; Windows stays DirectML for every vendor; Intel gets OpenVINO defaults/opt-in

Date: 2026-10-04
Status: Proposed — decision made, implementation pending (a follow-up
session implements the pyproject/bootstrap/placement/hardware/engine
branches, the tests, and the README selection matrix).

## Context

ADR 0007 removed ROCm and left Linux + AMD on CPU "until the MIGraphX EP
matures", kept OpenVINO as a never-auto-selected manual opt-in, and made
`openvino` devices on Windows unsyncable (the bootstrap always picks the
DirectML flavor there). Research (Oct 2026) changed three facts:

- AMD now officially publishes `onnxruntime-migraphx` wheels from its own
  index (`rocm.frameworks.amd.com` / `repo.radeon.com`), current line
  `1.23.2+rocm7.14.0` (also built against ROCm 10 previews), manylinux
  `cp312` only. They **require system ROCm installed first** — the wheel
  does not replace the ROCm runtime. ADR 0007's "no official wheel past the
  frozen 1.22.2.post1" claim was about `onnxruntime-rocm` (the deleted ROCm
  EP) and remains true; MIGraphX is its successor.
- The OpenVINO EP ships official wheels for **both Windows and Linux**
  (`onnxruntime-openvino==1.24.1` ↔ OpenVINO 2025.4.1), covering Intel
  CPUs, iGPUs, dGPUs, and NPUs. Caveat: the **Windows** wheel does not
  bundle OpenVINO libraries — a separate `openvino` pip wheel is required
  alongside it on Windows (the Linux wheel is self-contained).
- Windows MIGraphX does not exist as a reachable path: AMD's wheel matrix
  is manylinux-only (no `win_amd64` ever), the Windows HIP SDK brings a
  subset of ROCm that excludes MIGraphX, and Microsoft's Windows ML
  MIGraphX EP component (Win11 26H1, AMD driver 25.10.13.09+, not
  GenAI-ready) is only consumable through the Windows ML EP catalog — not
  from ORT-python with `onnx_asr`.

## Decision

**`migraphx` is a new concrete backend (Linux-only); per-vendor defaults
are decided at config creation, never re-derived (ADR 0007's rule stands).**

- New device values: `"migraphx"` / `"migraphx:N"` (concrete-backend naming,
  like `openvino`/`dml`; `"rocm"` stays retired and legacy `rocm*` values
  keep migrating to the platform default — no collision with the migration
  shim).
- **Linux defaults**: NVIDIA → `cuda`; else AMD + MIGraphX/ROCm runtime
  detected → `migraphx`; else Intel GPU → `openvino` (was: CPU); else
  `cpu`. The bootstrap syncs the matching `amd-linux` extra only when the
  device asks for MIGraphX *and* the ROCm runtime is actually present;
  otherwise it warns and syncs CPU. **ROCm itself is never installed by
  the bootstrap** — it is a documented system prerequisite, detected
  (ldconfig/`/opt/rocm/lib`), never provisioned.
- **Windows stays DirectML-first for every vendor** (download-minimal:
  one ~15 MB wheel accelerates AMD/Intel/NVIDIA alike). CUDA (~2 GB cu13
  set) syncs only when the device string explicitly asks for it.
- **Windows Intel opt-in**: `hardware.device = "openvino"` on Windows now
  syncs an `intel-win` flavor pinning **both** wheels —
  `onnxruntime-openvino==1.24.1` and the `openvino` runtime wheel —
  because the Windows OVEP wheel does not bundle the OpenVINO libraries.
  The Linux `intel-linux` extra stays single-wheel.
- **Wheel pins**: `onnxruntime-openvino==1.24.1` (current latest, already
  pinned), `onnxruntime-directml==1.24.4` (unchanged, frozen upstream),
  `onnxruntime-migraphx==1.23.2` from AMD's index (requires a `uv` index
  entry pointing at AMD's wheel host, `cp312` only — matches our floor).
- **Windows MIGraphX is rejected.** We will not build, fork, or distribute
  custom Windows ORT+MIGraphX wheels (no vendor ships the pieces; the
  per-GPU-arch kernel channels and cp312-locked builds make it a permanent
  distribution project — the exact frozen-wheel trap ADR 0007 escaped).
  WSL2 is likewise rejected: it would split the process and break
  system-wide hotkeys/clipboard injection/mic capture (against ADR 0004's
  one-process design). **Revisit trigger**: AMD ships a Windows
  `onnxruntime-ep-migraphx` plugin wheel, or the Windows ML MIGraphX EP
  component becomes reachable from ORT-python and GenAI-capable. Until
  then, Windows AMD = DirectML, recorded as deliberate.
- The README gets the authoritative platform × hardware selection matrix
  (defaults, opt-ins, and what each download costs).

## Consequences

- Linux + AMD (with ROCm installed) finally gets GPU acceleration;
  without ROCm it stays CPU with a warning pointing at the prerequisite.
- iGPU-only Linux Intel machines now default to OpenVINO: a larger wheel
  (~84 MB vs the CPU wheel) — accepted; the perf gain is worth the size,
  and the default is still decided once, at config creation.
- Existing configs are never re-derived: Linux+AMD users who sat on `cpu`
  since ADR 0007 opt in by setting `hardware.device = "migraphx"`.
- Windows AMD users remain on DirectML with no superior option; the
  expected MIGraphX win there (≈1.5–3× on encoder-shaped models) is
  consciously declined because Ghost-pass cadence self-calibrates
  (ADR 0004's benchmark tiers) — latency headroom, not raw speed, is the
  binding constraint on this workload.
- ADR 0007 stands except where superseded here: its device-value rules,
  migration shims, and no-auto principle are untouched; only "Linux + AMD
  runs on CPU" and "Intel is manual-only" are outdated by this ADR.
