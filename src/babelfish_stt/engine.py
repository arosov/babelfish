import onnx_asr
import onnxruntime
import numpy as np
import logging
import os
import threading
import sys
from pathlib import Path
from typing import Any, Optional, List, Dict
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import PipelineConfig, BabelfishConfig
from babelfish_stt.hardware import get_memory_usage, get_device_name
from babelfish_stt.placement import onnx_providers, resolve_device
from pydantic import BaseModel

# nvidia-smi reports GPUs in PCI bus order, so pin CUDA ordinals to bus ids
# before any ONNX Runtime session is created in this process.
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

logger = logging.getLogger(__name__)

# GPU backend -> (required provider, ORT flavor package), used by
# _degraded_device_fix to print the exact remediation when ORT lacks the
# provider a resolved device needs. The uv extra is derived below (cuda
# is platform-dependent). Mirrors ORT_FLAVOR in scripts/bootstrap.py —
# the engine-side loud fallback of the bootstrap's verify-and-self-heal.
_DEGRADED_FIX: Dict[str, tuple] = {
    "cuda": ("CUDAExecutionProvider", "onnxruntime-gpu"),
    "dml": ("DmlExecutionProvider", "onnxruntime-directml"),
    "rocm": ("ROCMExecutionProvider", "onnxruntime-rocm"),
    "openvino": ("OpenVINOExecutionProvider", "onnxruntime-openvino"),
    "coreml": ("CoreMLExecutionProvider", "onnxruntime"),
}
_BACKEND_EXTRA = {
    "dml": "windows-gpu",
    "rocm": "amd-linux",
    "openvino": "intel-linux",
    "coreml": "cpu",
}


def _degraded_device_fix(device: str) -> Optional[str]:
    """Remediation text when ORT lacks the provider `device` needs, else None.

    A resolved GPU device whose provider is missing from
    `get_available_providers()` usually means another ORT flavor wheel
    (plain / gpu / directml / openvino / rocm all ship the same top-level
    `onnxruntime/` package) currently owns the pyd — a shadowed install.
    """
    backend = device.partition(":")[0]
    if backend == "cuda":
        extra = "nvidia-win" if sys.platform == "win32" else "nvidia-linux"
    else:
        extra = _BACKEND_EXTRA.get(backend)
    entry = _DEGRADED_FIX.get(backend)
    if not extra or not entry:
        return None
    required, package = entry
    available = list(onnxruntime.get_available_providers())
    if required in available:
        return None
    return (
        f"Device {device} requested but {required} is not available "
        f"(providers: {available}). Likely a shadowed ORT install. "
        f"Fix: uv sync --extra {extra} --reinstall-package {package}"
    )


def resolve_model_path(
    cache_dir: Optional[str], base_dir: Path, model_name: str
) -> Optional[Path]:
    """
    Model resolution order:
    1. Shared cache dir (config `cache.cache_dir`, auto-populated from
       VOGON_APP_CACHE_DIR) — e.g. VogonPoet's provisioned cache.
    2. Repo-local models/ directory.
    3. None -> onnx-asr default path (HF cache; auto-downloads on first use).
    """
    candidates = []

    if cache_dir:
        candidates.append(("shared-cache", Path(cache_dir) / "models" / model_name))

    candidates.append(("repo", base_dir / "models" / model_name))

    for source, candidate in candidates:
        if candidate.exists():
            logger.info(f"📦 Model source ({source}): {candidate}")
            return candidate

    logger.info(
        "📦 No local model found; onnx-asr will use its default HF cache "
        "(auto-download on first use)."
    )
    return None


class STTEngine(Reconfigurable):
    """
    Unified STT engine using onnx-asr for hardware-accelerated inference
    on AMD, Intel, and NVIDIA GPUs across Windows and Linux.
    """

    MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"

    config_key = "pipeline"

    def __init__(self, config: BabelfishConfig):
        self._lock = threading.Lock()
        # Resolve target device
        target_device = config.hardware.device
        self.device_type = self._resolve_device(target_device)
        self.config_ref = config  # Keep reference to update status

        # Model resolution order:
        # 1. Shared cache dir (config `cache.cache_dir`, auto-populated from
        #    VOGON_APP_CACHE_DIR) — e.g. VogonPoet's provisioned cache.
        # 2. Repo-local models/ directory (used when running from a checkout
        #    with a local model copy).
        # 3. onnx-asr default path (HF cache; auto-downloads on first use).
        model_path = self._resolve_model_path(config)

        # Quantization Policy: full precision everywhere by default.
        # An explicit hardware.quantization setting is still honoured.
        if self.device_type != "cpu":
            quantization = None
            logger.info("🚀 GPU mode: Forcing highest precision quantization.")
        else:
            quantization = config.hardware.quantization
            logger.info(f"🐌 CPU mode: Using quantization={quantization}")

        # Map Babelfish device to ONNX Runtime providers
        providers = self._get_providers(self.device_type)

        # A GPU device resolved while its provider is missing from the
        # installed onnxruntime means a shadowed/flavor-mismatched install:
        # say so loudly instead of silently degrading to CPU.
        degraded_fix = _degraded_device_fix(self.device_type)
        if degraded_fix:
            logger.warning(f"⚠️ {degraded_fix}")

        logger.info(f"🚀 Initializing onnx-asr (Providers: {providers})...")

        # Measure Baseline Memory (Before loading model)
        mem_before = get_memory_usage(self.device_type)

        try:
            self.model = onnx_asr.load_model(
                self.MODEL_NAME,
                path=str(model_path) if model_path else None,
                quantization=quantization,
                providers=providers,
            )
        except Exception as e:
            logger.error(f"Failed to load onnx-asr model: {e}")
            # Fallback to CPU if GPU fails
            if self.device_type != "cpu":
                # If the GPU load failed because its provider is missing
                # (shadowed ORT install), say so loudly with the exact fix.
                fallback_fix = _degraded_device_fix(self.device_type)
                if fallback_fix:
                    logger.warning(f"⚠️ {fallback_fix}")
                logger.warning("Retrying with CPU provider...")
                self.device_type = "cpu"  # Update device type to cpu
                self.model = onnx_asr.load_model(
                    self.MODEL_NAME,
                    path=str(model_path) if model_path else None,
                    quantization=None,
                    providers=["CPUExecutionProvider"],
                )
            else:
                raise

        # Measure Memory After loading and update config
        mem_after = get_memory_usage(self.device_type)

        try:
            self.config_ref.status.active_device = self.device_type
            self.config_ref.status.active_device_name = get_device_name(
                self.device_type
            )
            self.config_ref.status.vram_total_gb = float(mem_after["total"])
            self.config_ref.status.vram_used_baseline_gb = float(mem_before["used"])
            self.config_ref.status.vram_used_model_gb = float(mem_after["used"])

            logger.info(
                f"📊 VRAM Status: Total={self.config_ref.status.vram_total_gb:.2f}GB, "
                f"Baseline={self.config_ref.status.vram_used_baseline_gb:.2f}GB, "
                f"ModelLoaded={self.config_ref.status.vram_used_model_gb:.2f}GB "
                f"(Delta: {self.config_ref.status.vram_used_model_gb - self.config_ref.status.vram_used_baseline_gb:.2f}GB)"
            )
        except (TypeError, ValueError, AttributeError):
            # Handle mocks in tests or missing data
            logger.info(
                f"📊 VRAM Status: Total={mem_after['total']}GB, Baseline={mem_before['used']}GB, ModelLoaded={mem_after['used']}GB"
            )

    def _resolve_model_path(self, config: BabelfishConfig) -> Optional[Path]:
        """
        Returns the first existing local model directory, or None to let
        onnx-asr use its default HF cache (auto-download on first use).
        """
        cache_dir = config.cache.cache_dir

        # Repo checkout layout: src/babelfish_stt/engine.py -> repo root
        base_dir = Path(__file__).resolve().parent.parent.parent
        return resolve_model_path(cache_dir, base_dir, self.MODEL_NAME)

    def _resolve_device(self, device: str) -> str:
        from babelfish_stt.hardware import probe_hardware_facts

        return resolve_device(device, probe_hardware_facts())

    def _get_providers(self, device: str) -> List[Any]:
        return onnx_providers(device)

    def reconfigure(self, config: BaseModel) -> None:
        """STTEngine reconfigure (called by ConfigManager)."""
        # Currently STTEngine doesn't have much to hot-reload from PipelineConfig
        # as most hardware settings require a restart which is handled by BabelfishServer.
        pass

    def transcribe(
        self,
        audio_buffer: np.ndarray,
        padding_s: float = 2.0,
    ) -> str:
        if len(audio_buffer) == 0:
            return ""

        # Performance Optimization:
        # The model has high overhead for short clips but is very fast for long ones.
        # Force a minimum duration of audio by padding with silence if needed.
        min_samples = int(padding_s * 16000)
        if len(audio_buffer) < min_samples:
            padding = np.zeros(min_samples - len(audio_buffer), dtype=np.float32)
            # Add padding to the END to preserve audio onset at the beginning
            # This is critical for accurate transcription of the first words
            input_audio = np.concatenate([audio_buffer, padding])
        else:
            input_audio = audio_buffer

        import time

        start_t = time.perf_counter()

        with self._lock:
            # onnx-asr handles the stream/context internally or we can just pass the buffer
            result = self.model.recognize(input_audio, sample_rate=16000)

        end_t = time.perf_counter()
        duration_ms = (end_t - start_t) * 1000
        audio_duration_s = len(input_audio) / 16000.0

        logger.debug(
            f"Inference: {duration_ms:.2f}ms for {audio_duration_s:.2f}s audio (RTF: {duration_ms / (audio_duration_s * 1000):.3f})"
        )

        return result.strip() if result else ""

    def benchmark(self) -> dict:
        """
        Runs dummy inferences to measure hardware performance and determine optimal tiers.
        Returns a PerformanceProfile dictionary.
        """
        logger.info("⏱️ Starting hardware self-calibration...")

        import time

        # Test 1: Ghost pass (2.5s window)
        test_audio = np.zeros(int(16000 * 2.5), dtype=np.float32)
        measurements = []
        for _ in range(5):
            start = time.perf_counter()
            self.transcribe(test_audio, padding_s=2.0)
            measurements.append((time.perf_counter() - start) * 1000)

        avg_latency = sum(measurements) / len(measurements)
        logger.info(f"⏱️ Calibration: Avg Ghost Latency = {avg_latency:.2f}ms")

        # Tier logic
        # Spacing values are the minimum spacing between Ghost submits.
        # min_padding_s feeds the Final pass only; the Ghost pass uses
        # ghost_padding_s (1.0 — bumped from 0.0 after live testing showed
        # the first unpadded windows transcribe to "", delaying the first
        # visible Ghost by ~400ms).
        if avg_latency < 40:
            tier = "ultra"
            throttle = 100
            window = 3.0
            padding = 2.0
        elif avg_latency < 80:
            tier = "high"
            throttle = 150
            window = 2.5
            padding = 2.0
        elif avg_latency < 150:
            tier = "medium"
            throttle = 250
            window = 2.0
            padding = 1.5
        else:
            tier = "low_power"
            throttle = 400
            window = 1.5
            padding = 1.0

        ghost_padding = 1.0  # keeps the first, short windows text-capable
        if self.device_type == "cpu":
            tier = "cpu"
            throttle = 300
            window = 1.0  # Sliding window: bounded Ghost inference on CPU too
            padding = 0
            ghost_padding = 0.0  # 1s window already bounds CPU Ghost audio

        logger.info(
            f"⏱️ Calibration complete: Tier={tier.upper()}, Spacing={throttle}ms, "
            f"Window={window}s"
        )

        return {
            "tier": tier,
            "ghost_throttle_ms": throttle,
            "ghost_window_s": window,
            "ghost_padding_s": ghost_padding,
            "min_padding_s": padding,
        }
