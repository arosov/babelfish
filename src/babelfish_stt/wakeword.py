import openwakeword
from openwakeword.model import Model
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path


def list_wakewords() -> List[str]:
    """Lists all available pretrained wakewords."""
    paths = openwakeword.get_pretrained_model_paths()
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


class WakeWordEngine:
    """
    A wrapper around openWakeWord for local keyword detection.
    """

    def __init__(self, model_name: str = "hey_jarvis"):
        self.model_name = model_name
        # openwakeword.Model takes a list of paths.

        # Get all pretrained paths and filter for the one we want
        pretrained_paths = openwakeword.get_pretrained_model_paths()
        target_paths = [p for p in pretrained_paths if model_name in p]

        if not target_paths:
            self.oww_model = Model()
        else:
            # Use wakeword_models instead of wakeword_model_paths for 0.6.0
            self.oww_model = Model(wakeword_models=[target_paths[0]])

    def process_chunk(self, chunk: np.ndarray) -> Dict[str, float]:
        """
        Process an audio chunk and return detection probabilities.

        Args:
            chunk: A numpy array of 16kHz audio data.

        Returns:
            A dictionary mapping keyword names to detection probabilities.
            Keys are normalized to remove version suffixes if they match the model name.
        """
        # openWakeWord expects 16-bit signed integers (int16).
        # Our streamer provides float32 normalized to [-1, 1].
        if chunk.dtype != np.int16:
            # Scale to int16 range
            chunk_int16 = (chunk * 32767).astype(np.int16)
        else:
            chunk_int16 = chunk

        # The predict method returns a dictionary of probabilities
        prediction = self.oww_model.predict(chunk_int16)

        # Normalize keys: if 'hey_jarvis_v0.1' is in prediction and we asked for 'hey_jarvis',
        # map it to 'hey_jarvis'.
        normalized = {}
        for k, v in prediction.items():
            if k.startswith(self.model_name):
                normalized[self.model_name] = v
            else:
                normalized[k] = v
        return normalized

    def reset(self):
        """Resets the internal state of the wake-word model."""
        self.oww_model.reset()
