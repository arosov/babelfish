import torch
import numpy as np
from parakeet_stream import Parakeet
from typing import Any

class STTEngine:
    """
    Stable STT engine that transcribes complete audio buffers.
    """
    
    def __init__(self, device: str = "cpu", model_name: str = "nvidia/parakeet-tdt-0.6b-v3"):
        self.model_name = model_name
        self.device = device
        
        # Initialize Parakeet (loads model eagerly)
        # We use 'realtime' for the best speed/accuracy tradeoff in live use
        print(f"🧠 Loading STT Engine: {model_name}...")
        self.pk = Parakeet(
            model_name=model_name,
            device=device,
            config='realtime'
        )

    def transcribe(self, audio_buffer: np.ndarray) -> str:
        """
        Transcribes a complete buffer of audio.
        """
        if len(audio_buffer) == 0:
            return ""
            
        # Parakeet.transcribe is very robust for variable length audio
        result = self.pk.transcribe(audio_buffer, _quiet=True)
        return result.text.strip()
