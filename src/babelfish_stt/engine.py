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
        # We use 'realtime' for CUDA and 'low_latency' for CPU to maintain responsiveness
        self.preset = 'realtime' if device == 'cuda' else 'low_latency'
        print(f"🧠 Loading STT Engine: {model_name} on {device} (preset: {self.preset})...")
        self.pk = Parakeet(
            model_name=model_name,
            device=device,
            config=self.preset
        )

    def set_quality(self, level: str):
        """
        Switch model quality/latency preset instantly.
        Supports quality levels ('max', 'high', 'good', 'low', 'realtime') 
        and preset names ('balanced', 'ultra_realtime', etc.)
        """
        self.pk.with_config(level)

    def transcribe(self, audio_buffer: np.ndarray, left_context_secs: float = 0.0) -> str:
        """
        Transcribes a complete buffer of audio with optional left context for accuracy.
        """
        if len(audio_buffer) == 0:
            return ""
            
        # Parakeet.transcribe is very robust for variable length audio
        # Using with_params to inject context if provided
        if left_context_secs > 0:
            result = self.pk.with_params(left_context_secs=left_context_secs).transcribe(audio_buffer, _quiet=True)
        else:
            result = self.pk.transcribe(audio_buffer, _quiet=True)
            
        return result.text.strip()
