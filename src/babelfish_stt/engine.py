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
        self.device_type = config.hardware.device

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

    def reconfigure(self, config: PipelineConfig) -> None:
        pass

    def set_quality(self, level: str):
        pass

    def transcribe(
        self, audio_buffer: np.ndarray, left_context_secs: float = 0.0
    ) -> str:
        if len(audio_buffer) == 0:
            return ""

        # onnx-asr handles the stream/context internally or we can just pass the buffer
        # For parakeet-tdt, it's an offline model in onnx-asr wrapper
        result = self.model.recognize(audio_buffer, sample_rate=16000)

        return result.strip() if result else ""
