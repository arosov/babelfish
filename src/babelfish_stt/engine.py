import onnx_asr
import numpy as np
import logging
from pathlib import Path
from typing import Any, Optional, List
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import PipelineConfig, BabelfishConfig

logger = logging.getLogger(__name__)


class STTEngine(Reconfigurable):
    """
    Unified STT engine using onnx-asr for hardware-accelerated inference
    on AMD, Intel, and NVIDIA GPUs across Windows and Linux.
    """

    def __init__(self, config: BabelfishConfig):
        self.device_type = self._resolve_device(config.hardware.device)

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
                self.model = onnx_asr.load_model(
                    model_name,
                    path=str(model_path) if model_path.exists() else None,
                    quantization="int8",
                    providers=["CPUExecutionProvider"],
                )
            else:
                raise

    def _resolve_device(self, device: str) -> str:
        if device != "auto":
            return device

        try:
            import onnxruntime as ort

            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                return "cuda"
            if "ROCMExecutionProvider" in available:
                return "rocm"
            if "DmlExecutionProvider" in available:
                return "dml"
        except Exception:
            pass

        return "cpu"

    def _get_providers(self, device: str) -> List[Any]:
        if device == "cuda":
            return [("CUDAExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
        elif device == "dml":
            return ["DmlExecutionProvider", "CPUExecutionProvider"]
        elif device == "rocm":
            return ["ROCMExecutionProvider", "CPUExecutionProvider"]
        elif device == "openvino":
            return ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def transcribe(
        self, audio_buffer: np.ndarray, left_context_secs: float = 0.0
    ) -> str:
        if len(audio_buffer) == 0:
            return ""

        # Performance Optimization:
        # The model has high overhead for short clips but is very fast for long ones.
        # Force a minimum of 2 seconds of audio by padding with silence if needed.
        min_samples = 32000  # 2 seconds
        if len(audio_buffer) < min_samples:
            padding = np.zeros(min_samples - len(audio_buffer), dtype=np.float32)
            # Add padding to the BEGINNING so it doesn't interfere with the end-of-speech detection
            # but provides the necessary input volume for GPU kernels to run at full speed.
            input_audio = np.concatenate([padding, audio_buffer])
        else:
            input_audio = audio_buffer

        import time

        start_t = time.perf_counter()

        # onnx-asr handles the stream/context internally or we can just pass the buffer
        result = self.model.recognize(input_audio, sample_rate=16000)

        end_t = time.perf_counter()
        duration_ms = (end_t - start_t) * 1000
        audio_duration_s = len(input_audio) / 16000.0

        logger.debug(
            f"Inference: {duration_ms:.2f}ms for {audio_duration_s:.2f}s audio (RTF: {duration_ms / (audio_duration_s * 1000):.3f})"
        )

        return result.strip() if result else ""
