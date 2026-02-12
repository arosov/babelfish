import openwakeword
from openwakeword.model import Model
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
import threading
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import VoiceConfig


def list_wakewords() -> List[str]:
    """Lists all available pretrained wakewords."""
    paths = openwakeword.get_pretrained_model_paths() or []
    # Extract filename without extension and remove common version suffixes
    # Paths look like: /path/to/models/hey_jarvis_v0.1.tflite
    names = set()
    for p in paths:
        filename = Path(p).stem
        # Remove common versioning patterns like _v0.1, _v1.0
        import re

        base_name = re.sub(r"_v\d+(\.\d+)*$", "", filename)
        names.add(base_name)
    return sorted(list(names))


class WakeWordEngine(Reconfigurable):
    """
    A wrapper around openWakeWord for local keyword detection.
    """

    def __init__(self, model_name: Optional[str] = None):
        self._lock = threading.Lock()
        self.model_name = model_name
        self.oww_model: Optional[Model] = None
        self._load_model()

    def _load_model(self):
        """Loads the model specified by self.model_name. Must be called under lock or in init."""
        if not self.model_name:
            self.oww_model = None
            return

        # openwakeword.Model takes a list of paths.
        # Get all pretrained paths and filter for the one we want
        pretrained_paths = openwakeword.get_pretrained_model_paths() or []
        target_paths = [p for p in pretrained_paths if self.model_name in p]

        if not target_paths:
            # Fallback or empty model if not found
            self.oww_model = None
        else:
            # Use wakeword_models instead of wakeword_model_paths for 0.6.0
            self.oww_model = Model(wakeword_models=[target_paths[0]])

    def reconfigure(self, config: BaseModel) -> None:
        """Update wakeword model based on config."""
        if isinstance(config, VoiceConfig):
            with self._lock:
                if config.wakeword != self.model_name:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"Reconfiguring WakeWordEngine: {self.model_name} -> {config.wakeword}"
                    )
                    self.model_name = config.wakeword
                    self._load_model()

    @property
    def active_wakeword(self) -> Optional[str]:
        """Returns the currently active wakeword name."""
        with self._lock:
            return self.model_name if self.oww_model else None

    def process_chunk(self, chunk: np.ndarray) -> Dict[str, float]:
        """
        Process an audio chunk and return detection probabilities.

        Args:
            chunk: A numpy array of 16kHz audio data.

        Returns:
            A dictionary mapping keyword names to detection probabilities.
            Keys are normalized to remove version suffixes if they match the model name.
        """
        # openwakeword expects 16-bit signed integers (int16).
        # Our streamer provides float32 normalized to [-1, 1].
        if chunk.dtype != np.int16:
            # Scale to int16 range
            chunk_int16 = (chunk * 32767).astype(np.int16)
        else:
            chunk_int16 = chunk

        with self._lock:
            if not self.oww_model:
                return {}

            # The predict method returns a dictionary of probabilities
            prediction = self.oww_model.predict(chunk_int16)

        # Handle cases where predict might return a tuple (depending on version/flags)
        if isinstance(prediction, tuple):
            prediction = prediction[0]

        # Normalize keys: if 'hey_jarvis_v0.1' is in prediction and we asked for 'hey_jarvis',
        # map it to 'hey_jarvis'.
        normalized = {}
        target_name = self.model_name
        for k, v in prediction.items():
            if target_name and k.startswith(target_name):
                normalized[target_name] = v
            else:
                normalized[k] = v
        return normalized

    def detect(self, chunk: np.ndarray, threshold: float = 0.5) -> bool:
        """
        Convenience method to return True if the target wakeword is detected
        above the given threshold.
        """
        probabilities = self.process_chunk(chunk)
        with self._lock:
            if not self.model_name:
                return False
            return probabilities.get(self.model_name, 0.0) >= threshold

    def reset(self):
        """Resets the internal state of the wake-word model."""
        with self._lock:
            if self.oww_model:
                self.oww_model.reset()
