from dataclasses import dataclass
from typing import Optional, Tuple
import logging
import sys

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GpuDevice:
    device: str
    name: str
    total_gb: float
    integrated: bool = False


@dataclass(frozen=True)
class HardwareFacts:
    providers: Tuple[str, ...] = ()
    gpus: Tuple[GpuDevice, ...] = ()
    platform: str = ""
    machine: str = ""


# Backends that own an ONNX Runtime provider, with the provider that enables each.
# OpenVINO is a manual opt-in extra (never auto-selected); coreml/metal stay
# macOS-only passthroughs.
_BACKENDS = (
    ("cuda", "CUDAExecutionProvider"),
    ("dml", "DmlExecutionProvider"),
    ("openvino", "OpenVINOExecutionProvider"),
)
_PROVIDER = dict(_BACKENDS)
# Used when the backend's provider is available but no device could be enumerated.
# OpenVINO has none: without an enumerated GPU its default device is the CPU.
_DEFAULT_DEVICE = {"cuda": "cuda:0", "dml": "dml:0"}


def _best(candidates):
    # Integrated GPUs report shared system memory, so a discrete card outranks them whatever the totals say.
    return max(candidates, key=lambda g: (not g.integrated, g.total_gb))


def _best_of(backend: str, facts: HardwareFacts):
    if _PROVIDER[backend] not in facts.providers:
        return None
    candidates = [g for g in facts.gpus if g.device.startswith(backend + ":")]
    return _best(candidates).device if candidates else _DEFAULT_DEVICE.get(backend)


def best_gpu_device(facts: HardwareFacts) -> Optional[str]:
    """The best available GPU device across provider backends, or None when
    no GPU backend is usable in this ORT install.

    Priority order mirrors engine/placement conventions: CUDA first, then
    DirectML, then OpenVINO (the manual opt-in still wins nothing here —
    it is last). Within a backend, the highest-VRAM discrete card wins
    (same rule as resolve_device). Used by `babelfish --gpu` (ADR 0014):
    the CLI's in-memory device override.
    """
    for backend in ("cuda", "dml", "openvino"):
        if _PROVIDER[backend] in facts.providers:
            device = _best_of(backend, facts)
            if device:
                return device
    return None


def resolve_device(requested: str, facts: HardwareFacts) -> str:
    """Resolves a concrete `hardware.device` value to a runnable device id.

    `hardware.device` always holds a concrete backend (ADR 0007): a bare
    backend name picks that backend's highest-VRAM discrete device, an exact
    id is honoured as-is, and anything unknown degrades to CPU (with a
    warning) so a stale config can't wedge the engine. Requests whose
    provider is not installed also degrade to CPU — there is no backend
    re-ordering fallback anymore.
    """
    if requested == "cpu":
        return "cpu"

    backend = requested.partition(":")[0]
    if backend in _PROVIDER:
        provider = _PROVIDER[backend]
        if provider not in facts.providers:
            logger.warning(
                f"Device '{requested}' requested but {provider} is not installed; "
                "falling back to CPU"
            )
            return "cpu"
        if ":" in requested:
            # Exact id: honoured as pinned, never re-selected by VRAM.
            return requested
        return _best_of(backend, facts) or requested

    # macOS passthroughs ("coreml", "metal") and other already-concrete ids.
    if requested in ("coreml", "metal"):
        return requested

    logger.warning(
        f"Unknown device '{requested}' requested; falling back to CPU"
    )
    return "cpu"


def _index(qualifier: str) -> int:
    if not qualifier:
        return 0
    try:
        return int(qualifier)
    except ValueError:
        logger.warning(f"Invalid device index '{qualifier}', falling back to device 0")
        return 0


def onnx_providers(device: str) -> list:
    """ONNX Runtime providers for a Babelfish device id, with CPU as the fallback provider."""
    cpu = "CPUExecutionProvider"
    backend, _, qualifier = device.partition(":")
    if backend == "cuda":
        return [("CUDAExecutionProvider", {"device_id": _index(qualifier)}), cpu]
    if backend == "dml":
        return [("DmlExecutionProvider", {"device_id": _index(qualifier)}), cpu]
    if backend == "openvino":
        if qualifier:
            return [("OpenVINOExecutionProvider", {"device_type": qualifier}), cpu]
        return ["OpenVINOExecutionProvider", cpu]
    if device == "coreml" or (device == "metal" and sys.platform == "darwin"):
        return ["CoreMLExecutionProvider", cpu]
    return [cpu]
