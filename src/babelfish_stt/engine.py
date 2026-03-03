import onnx_asr
import numpy as np
import logging
import threading
import sys
from pathlib import Path
from typing import Any, Optional, List
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import PipelineConfig, BabelfishConfig
from babelfish_stt.hardware import get_memory_usage, get_device_name
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class STTEngine(Reconfigurable):
    """
    Unified STT engine using onnx-asr for hardware-accelerated inference
    on AMD, Intel, and NVIDIA GPUs across Windows and Linux.
    """

    # config_key = "pipeline"  # Change this to None in main.py registration or remove

    def __init__(self, config: BabelfishConfig):
        self._lock = threading.RLock()
        # Resolve target device
        target_device = config.hardware.device
        self.device_type = self._resolve_device(target_device)
        self.config_ref = config  # Keep reference to update status

        # Default model search
        base_dir = Path(__file__).resolve().parent.parent.parent
        models_dir = base_dir / "models"

        # We expect bootstrap.py to have provisioned the model here
        model_name = "nemo-parakeet-tdt-0.6b-v3"
        model_path = models_dir / model_name

        # Quantization Policy:
        # GPU: Force highest (None)
        # CPU: Allow config or default to int8
        if self.device_type != "cpu":
            quantization = None
            logger.info("🚀 GPU mode: Forcing highest precision quantization.")
        else:
            quantization = config.hardware.quantization or "int8"
            logger.info(f"🐌 CPU mode: Using quantization={quantization}")

        # Map Babelfish device to ONNX Runtime providers
        providers = self._get_providers(self.device_type)

        logger.info(f"🚀 Initializing onnx-asr (Providers: {providers})...")

        # Measure Baseline Memory (Before loading model)
        mem_before = get_memory_usage(self.device_type)

        try:
            self.model = onnx_asr.load_model(
                model_name,
                path=str(model_path) if model_path.exists() else None,
                quantization=quantization,
                providers=providers,
            )
        except Exception as e:
            logger.error(f"Failed to load onnx-asr model: {e}")
            # Fallback to CPU if GPU fails
            if self.device_type != "cpu":
                logger.warning("Retrying with CPU provider...")
                self.device_type = "cpu"  # Update device type to cpu
                self.model = onnx_asr.load_model(
                    model_name,
                    path=str(model_path) if model_path.exists() else None,
                    quantization="int8",
                    providers=["CPUExecutionProvider"],
                )
            else:
                raise

        # Measure Memory After loading and update config
        mem_after = get_memory_usage(self.device_type)

        try:
            self.config_ref.hardware.active_device = self.device_type
            self.config_ref.hardware.active_device_name = get_device_name(
                self.device_type
            )
            self.config_ref.hardware.vram_total_gb = float(mem_after["total"])
            self.config_ref.hardware.vram_used_baseline_gb = float(mem_before["used"])
            self.config_ref.hardware.vram_used_model_gb = float(mem_after["used"])

            logger.info(
                f"📊 VRAM Status: Total={self.config_ref.hardware.vram_total_gb:.2f}GB, "
                f"Baseline={self.config_ref.hardware.vram_used_baseline_gb:.2f}GB, "
                f"ModelLoaded={self.config_ref.hardware.vram_used_model_gb:.2f}GB "
                f"(Delta: {self.config_ref.hardware.vram_used_model_gb - self.config_ref.hardware.vram_used_baseline_gb:.2f}GB)"
            )
        except (TypeError, ValueError):
            # Handle mocks in tests or missing data
            logger.info(
                f"📊 VRAM Status: Total={mem_after['total']}GB, Baseline={mem_before['used']}GB, ModelLoaded={mem_after['used']}GB"
            )

    def _resolve_device(self, device: str) -> str:
        try:
            import onnxruntime as ort

            available = ort.get_available_providers()
        except Exception:
            available = []

        # 1. Handle "Auto" or generic "cuda" requests
        if device == "auto" or device == "cuda":
            if "CUDAExecutionProvider" in available:
                # Find the best GPU index
                from babelfish_stt.hardware import get_best_gpu_index

                best_idx = get_best_gpu_index()
                logger.info(f"🤖 Auto-selecting best GPU: cuda:{best_idx}")
                return f"cuda:{best_idx}"

            # Mac Logic: Prioritize CoreML only on Apple Silicon (arm64)
            if sys.platform == "darwin":
                import platform

                arch = platform.machine().lower()
                if "arm" in arch or "aarch64" in arch:
                    if "CoreMLExecutionProvider" in available:
                        return "coreml"
                # Fallback to CPU for Intel Macs (x86_64) unless manually forced

            if "ROCMExecutionProvider" in available:
                return "rocm"
            if "DmlExecutionProvider" in available:
                return "dml:0"

            return "cpu"

        # 2. Smart fallback for explicit requests
        if device.startswith("cuda") and "CUDAExecutionProvider" not in available:
            if "DmlExecutionProvider" in available:
                logger.warning(
                    f"Requested '{device}' but CUDA provider not found. Falling back to DirectML."
                )
                return "dml:0"

        return device

    def _get_providers(self, device: str) -> List[Any]:
        if device == "coreml" or (sys.platform == "darwin" and device == "metal"):
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]

        # Generic Mac with explicit device selection is handled by specific branches below or fallbacks

        if device == "cuda":
            # Should have been resolved to cuda:X by _resolve_device, but safe fallback
            return [("CUDAExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
        elif device.startswith("cuda:"):
            try:
                # Extract device ID from string "cuda:1" -> 1
                dev_id = int(device.split(":")[1])
                return [
                    ("CUDAExecutionProvider", {"device_id": dev_id}),
                    "CPUExecutionProvider",
                ]
            except ValueError:
                logger.warning(
                    f"Invalid CUDA device format '{device}', falling back to device 0"
                )
                return [
                    ("CUDAExecutionProvider", {"device_id": 0}),
                    "CPUExecutionProvider",
                ]
        elif device == "dml":
            return [
                ("DmlExecutionProvider", {"device_id": 0}),
                "CPUExecutionProvider",
            ]
        elif device.startswith("dml:"):
            try:
                dev_id = int(device.split(":")[1])
                return [
                    ("DmlExecutionProvider", {"device_id": dev_id}),
                    "CPUExecutionProvider",
                ]
            except ValueError:
                return [
                    ("DmlExecutionProvider", {"device_id": 0}),
                    "CPUExecutionProvider",
                ]
        elif device == "rocm":
            return ["ROCMExecutionProvider", "CPUExecutionProvider"]
        elif device == "openvino":
            return ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def can_hot_reload(self, new_device: str) -> bool:
        """Check if the device can be changed without a process restart."""
        # 1. 'auto' can always be handled by the engine's internal resolver or hot-reloaded if it maps to current
        if new_device == "auto":
            return True

        # 2. Check compatibility for hot-reload
        # We need to know what's PHYSICALLY available vs what's in the environment
        try:
            import onnxruntime as ort

            available = ort.get_available_providers()
        except ImportError:
            available = []

        # If user requests a specific provider, it MUST be in 'available' for hot-reload
        # Otherwise we need a restart to allow bootstrap.py to sync the right package.
        if new_device.startswith("cuda"):
            return "CUDAExecutionProvider" in available
        if new_device.startswith("dml"):
            return "DmlExecutionProvider" in available
        if new_device == "rocm":
            return "ROCMExecutionProvider" in available
        if new_device == "cpu":
            return True  # CPU is always compatible with any ORT package
        if new_device == "coreml" or new_device == "metal":
            return "CoreMLExecutionProvider" in available

        return False

    def reconfigure(self, config: BaseModel) -> None:
        """STTEngine reconfigure (called by ConfigManager)."""
        if not isinstance(config, BabelfishConfig):
            # ConfigManager passes sub-configs based on config_key ("pipeline"),
            # but we need "hardware" too. Actually, ConfigManager can pass the full config.
            # In main.py: config_manager.register(engine)
            # Since STTEngine has config_key = "pipeline", it only gets PipelineConfig.
            # Let's change config_key to None so it gets the full BabelfishConfig.
            return

        new_device = config.hardware.device
        if new_device == "auto":
            new_device = self._resolve_device("auto")

        # Normalize cuda:0, dml:0, etc.
        new_device_resolved = self._resolve_device(new_device)
        if new_device_resolved == self.device_type:
            logger.info(
                f"STT: Device {new_device_resolved} already active. Skipping reload."
            )
            return

        # Check compatibility for hot-reload
        # Compatible if switching between CPU and a provider available in current env
        try:
            import onnxruntime as ort

            available = ort.get_available_providers()
        except ImportError:
            available = []

        is_compatible = False
        if new_device_resolved == "cpu":
            is_compatible = True
        elif (
            new_device_resolved.startswith("cuda")
            and "CUDAExecutionProvider" in available
        ):
            is_compatible = True
        elif (
            new_device_resolved.startswith("dml")
            and "DmlExecutionProvider" in available
        ):
            is_compatible = True
        elif new_device_resolved == "rocm" and "ROCMExecutionProvider" in available:
            is_compatible = True
        elif (
            new_device_resolved == "openvino"
            and "OpenVINOExecutionProvider" in available
        ):
            is_compatible = True
        elif new_device_resolved == "coreml" and "CoreMLExecutionProvider" in available:
            is_compatible = True

        if not is_compatible:
            logger.info(
                f"STT: Device switch {self.device_type} -> {new_device_resolved} requires process restart."
            )
            # Note: We don't signal restart_required here, BabelfishServer does that.
            return

        # Hot-reload the engine
        logger.info(
            f"🔄 STT: Hot-reloading engine: {self.device_type} -> {new_device_resolved}"
        )
        with self._lock:
            # 1. Release current model
            self.model = None

            # 2. Update device type
            self.device_type = new_device_resolved

            # 3. Reload model with new providers
            providers = self._get_providers(self.device_type)

            # Quantization Policy
            if self.device_type != "cpu":
                quantization = None
            else:
                quantization = config.hardware.quantization or "int8"

            # Default model search (re-resolve paths)
            base_dir = Path(__file__).resolve().parent.parent.parent
            models_dir = base_dir / "models"
            model_name = "nemo-parakeet-tdt-0.6b-v3"
            model_path = models_dir / model_name

            mem_before = get_memory_usage(self.device_type)
            try:
                self.model = onnx_asr.load_model(
                    model_name,
                    path=str(model_path) if model_path.exists() else None,
                    quantization=quantization,
                    providers=providers,
                )
            except Exception as e:
                logger.error(f"Failed to hot-reload onnx-asr model: {e}")
                # Fallback to CPU
                self.device_type = "cpu"
                self.model = onnx_asr.load_model(
                    model_name,
                    path=str(model_path) if model_path.exists() else None,
                    quantization="int8",
                    providers=["CPUExecutionProvider"],
                )

            mem_after = get_memory_usage(self.device_type)
            self.config_ref.hardware.active_device = self.device_type
            self.config_ref.hardware.active_device_name = get_device_name(
                self.device_type
            )
            self.config_ref.hardware.vram_total_gb = float(mem_after["total"])
            self.config_ref.hardware.vram_used_baseline_gb = float(mem_before["used"])
            self.config_ref.hardware.vram_used_model_gb = float(mem_after["used"])

            # 4. Re-calibrate performance if it wasn't manual
            if config.pipeline.performance.tier != "manual":
                logger.info("⏱️ STT: Re-calibrating performance after hot-reload...")
                perf_data = self.benchmark()
                # Update the config object so following components (pipeline) see the new values
                config.pipeline.performance.tier = perf_data["tier"]
                config.pipeline.performance.ghost_throttle_ms = perf_data[
                    "ghost_throttle_ms"
                ]
                config.pipeline.performance.ghost_window_s = perf_data["ghost_window_s"]
                config.pipeline.performance.min_padding_s = perf_data["min_padding_s"]

            logger.info(
                f"✅ STT: Engine hot-reloaded successfully on {self.device_type}"
            )

    def transcribe(
        self,
        audio_buffer: np.ndarray,
        left_context_secs: float = 0.0,
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
            if self.model is None:
                logger.warning("STT: Model is not loaded. Skipping transcription.")
                return ""
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

        if self.device_type == "cpu":
            tier = "cpu"
            throttle = 300
            window = 0  # Full buffer
            padding = 0

        logger.info(
            f"⏱️ Calibration complete: Tier={tier.upper()}, Throttle={throttle}ms, Window={window}s"
        )

        return {
            "tier": tier,
            "ghost_throttle_ms": throttle,
            "ghost_window_s": window,
            "min_padding_s": padding,
        }
