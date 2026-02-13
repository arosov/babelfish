import onnxruntime as ort
import numpy as np
import logging
import urllib.request
from typing import Optional, Any
from pathlib import Path
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import VoiceConfig

logger = logging.getLogger(__name__)


class SileroVAD(Reconfigurable):
    """
    State-of-the-art VAD using Silero VAD v5 on ONNX Runtime.
    Optimized for minimal CPU usage via single-thread execution.
    """

    config_key = "voice"

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate

        # Default model search
        base_dir = Path(__file__).resolve().parent.parent.parent
        models_dir = base_dir / "models"
        models_dir.mkdir(exist_ok=True)
        model_path = models_dir / "silero_vad.onnx"

        # Auto-download if missing
        if not model_path.exists():
            url = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
            logger.info(f"📥 Downloading Silero VAD ONNX model from {url}...")
            try:
                urllib.request.urlretrieve(url, model_path)
                logger.info(f"✅ Model downloaded to {model_path}")
            except Exception as e:
                logger.error(f"Failed to download Silero VAD model: {e}")
                # Fallback path if you have it in another common location or raise error
                raise FileNotFoundError(
                    f"Silero VAD model missing and download failed. Please place it at {model_path}"
                )

        # Configure ONNX Session for minimal CPU footprint
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        logger.info("🎙️ Loading Silero VAD (ONNX)...")
        try:
            self.session = ort.InferenceSession(
                str(model_path), sess_options=opts, providers=["CPUExecutionProvider"]
            )
        except Exception as e:
            logger.error(f"Failed to load Silero VAD ONNX: {e}")
            raise

        self.reset_states()

    def reset_states(self):
        """Resets the VAD model RNN state."""
        self._state = np.zeros((2, 1, 128)).astype("float32")
        self._context = np.zeros((1, 64)).astype("float32")

    def reconfigure(self, config: BaseModel) -> None:
        """Apply new configuration to VAD."""
        if isinstance(config, VoiceConfig):
            self.threshold = 1.0 - config.wakeword_sensitivity
            self.threshold = max(0.05, min(0.95, self.threshold))
            logger.info(f"VAD threshold updated to {self.threshold:.2f}")

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Detects if speech is present using incremental block processing.
        """
        block_size = 512
        if len(audio_chunk) < block_size:
            return False

        # Ensure float32
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)

        num_blocks = len(audio_chunk) // block_size
        has_speech = False

        for i in range(num_blocks):
            start = i * block_size
            end = start + block_size
            block = audio_chunk[start:end]

            # Silero VAD v5 ONNX expects [batch, samples]
            if len(block.shape) == 1:
                block_in = np.expand_dims(block, axis=0)
            else:
                block_in = block

            # Concatenate with context (64 samples)
            # Input size becomes 512 + 64 = 576
            input_tensor = np.concatenate([self._context, block_in], axis=1)

            # Update context for next iteration (last 64 samples of current block)
            self._context = block_in[:, -64:]

            # Prepare inputs for Silero VAD v5
            inputs = {
                "input": input_tensor,
                "sr": np.array(self.sample_rate, dtype=np.int64),  # Scalar
                "state": self._state,
            }

            # Inference
            outputs = self.session.run(None, inputs)
            out, state_out = outputs

            # Update state
            self._state = state_out

            # Check probability - handle various output formats safely
            # Output 'out' can be [batch, 1] or just [1]
            prob = out
            while isinstance(prob, (np.ndarray, list)):
                if len(prob) == 0:
                    prob = 0.0
                    break
                prob = prob[0]

            prob_any: Any = prob
            speech_prob = (
                float(prob_any) if not isinstance(prob_any, (np.ndarray, list)) else 0.0
            )

            # Diagnostic logging (can be commented out after verification)
            # max_amp = np.max(np.abs(block))
            # if max_amp > 0.05 or speech_prob > 0.01:
            #    logger.info(
            #        f"VAD: Amp={max_amp:.4f}, Prob={speech_prob:.4f}, Thresh={self.threshold}"
            #    )

            if speech_prob > self.threshold:
                has_speech = True

        return has_speech
