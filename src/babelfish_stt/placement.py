from dataclasses import dataclass
from typing import Tuple
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


# Backends in the order "auto" prefers them, with the ONNX Runtime provider that enables each.
_BACKENDS = (
    ("cuda", "CUDAExecutionProvider"),
    ("rocm", "ROCMExecutionProvider"),
    ("dml", "DmlExecutionProvider"),
    ("openvino", "OpenVINOExecutionProvider"),
)
_PROVIDER = dict(_BACKENDS)
# Used when the backend's provider is available but no device could be enumerated.
# OpenVINO has none: without an enumerated GPU its default device is the CPU.
_DEFAULT_DEVICE = {"cuda": "cuda:0", "rocm": "rocm:0", "dml": "dml:0"}


def _best(candidates):
    # Integrated GPUs report shared system memory, so a discrete card outranks them whatever the totals say.
    return max(candidates, key=lambda g: (not g.integrated, g.total_gb))


def _best_of(backend: str, facts: HardwareFacts):
    if _PROVIDER[backend] not in facts.providers:
        return None
    candidates = [g for g in facts.gpus if g.device.startswith(backend + ":")]
    return _best(candidates).device if candidates else _DEFAULT_DEVICE.get(backend)


def _is_apple_silicon(facts: HardwareFacts) -> bool:
    machine = facts.machine.lower()
    return facts.platform == "darwin" and ("arm" in machine or "aarch64" in machine)


def resolve_device(requested: str, facts: HardwareFacts) -> str:
    if requested in ("auto", "cuda"):
        for backend, _ in _BACKENDS:
            device = _best_of(backend, facts)
            if device:
                return device
        if _is_apple_silicon(facts) and "CoreMLExecutionProvider" in facts.providers:
            return "coreml"
        return "cpu"
    if requested in _PROVIDER:
        return _best_of(requested, facts) or requested
    if requested.startswith("cuda:") and _PROVIDER["cuda"] not in facts.providers:
        return _best_of("dml", facts) or requested
    return requested


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
    if backend == "rocm":
        if qualifier:
            return [("ROCMExecutionProvider", {"device_id": _index(qualifier)}), cpu]
        return ["ROCMExecutionProvider", cpu]
    if backend == "openvino":
        if qualifier:
            return [("OpenVINOExecutionProvider", {"device_type": qualifier}), cpu]
        return ["OpenVINOExecutionProvider", cpu]
    if device == "coreml" or (device == "metal" and sys.platform == "darwin"):
        return ["CoreMLExecutionProvider", cpu]
    return [cpu]
