import torch
import numpy as np
from typing import Optional

class SileroVAD:
    """
    Lightweight wrapper for Silero VAD v5.
    """
    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        
        # Load Silero VAD from torch hub
        print("🎙️  Loading Silero VAD...")
        self.model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        (self.get_speech_timestamps, _, self.read_audio, _, _) = utils
        
        # Move to GPU if available
        if torch.cuda.is_available():
            self.model.to('cuda')
            self.device = 'cuda'
        else:
            self.device = 'cpu'
            
        self.reset_states()

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
