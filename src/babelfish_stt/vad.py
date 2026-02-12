import torch
import numpy as np
import logging
from typing import Optional
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import VoiceConfig

logger = logging.getLogger(__name__)


class SileroVAD(Reconfigurable):
    """
    Lightweight wrapper for Silero VAD v5.
    """

    config_key = "voice"

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate

        # Load Silero VAD from torch hub
        logger.info("🎙️  Loading Silero VAD...")
        self.model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        (self.get_speech_timestamps, _, self.read_audio, _, _) = utils

        # Stay on CPU for compatibility
        self.device = "cpu"
        self.model.to("cpu")

        self.reset_states()

    def reconfigure(self, config: BaseModel) -> None:
        """Apply new configuration to VAD."""
        if isinstance(config, VoiceConfig):
            # Map sensitivity (0.1-0.9) to threshold (0.9-0.1)
            # Higher sensitivity = Lower threshold = Easier to trigger
            self.threshold = 1.0 - config.wakeword_sensitivity
            # Clamp to safe range to avoid extremes
            self.threshold = max(0.05, min(0.95, self.threshold))
            logger.info(
                f"VAD threshold updated to {self.threshold:.2f} (Sensitivity: {config.wakeword_sensitivity:.2f})"
            )

    def reset_states(self):
        """Resets the VAD model state."""
        self.model.reset_states()

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Detects if speech is present in the current audio chunk.

        Args:
            audio_chunk: 1D numpy array of audio samples (float32)

        Returns:
            bool: True if speech probability > threshold
        """
        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio_chunk).to(self.device)

        # Silero expects (batch, samples)
        if audio_tensor.dim() == 1:
            audio_tensor = audio_tensor.unsqueeze(0)

        # Get speech probability
        with torch.no_grad():
            speech_prob = self.model(audio_tensor, self.sample_rate).item()

        return speech_prob > self.threshold
