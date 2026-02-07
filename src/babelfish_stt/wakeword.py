import openwakeword
from openwakeword.model import Model
import numpy as np
from typing import Dict, List, Optional

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
            self.oww_model = Model(
                wakeword_model_paths=[target_paths[0]]
            )

    def process_chunk(self, chunk: np.ndarray) -> Dict[str, float]:
        """
        Process an audio chunk and return detection probabilities.
        
        Args:
            chunk: A numpy array of 16kHz audio data.
            
        Returns:
            A dictionary mapping keyword names to detection probabilities.
            Keys are normalized to remove version suffixes if they match the model name.
        """
        # The predict method returns a dictionary of probabilities
        prediction = self.oww_model.predict(chunk)
        
        # Normalize keys: if 'hey_jarvis_v0.1' is in prediction and we asked for 'hey_jarvis', 
        # map it to 'hey_jarvis'.
        normalized = {}
        for k, v in prediction.items():
            if k.startswith(self.model_name):
                normalized[self.model_name] = v
            else:
                normalized[k] = v
        return normalized
