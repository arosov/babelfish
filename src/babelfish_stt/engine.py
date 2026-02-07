import torch
from parakeet_stream import StreamingTranscriber, TranscriberConfig
from typing import Iterable, Any

class STTEngine:
    """
    Encapsulates the parakeet-stream engine with optimized settings for low-latency streaming.
    """
    
    def __init__(self, device: str = "cpu", model_name: str = "nvidia/parakeet-tdt-0.6b-v3"):
        self.model_name = model_name
        # "Fast" Preset configuration
        self.config = TranscriberConfig(
            model_name=model_name,
            device=device,
            chunk_secs=1.0,           # Short chunks for faster updates
            left_context_secs=5.0,    # Sufficient context for accuracy
            right_context_secs=1.0,   # Minimal look-ahead for lower latency
        )
        
        self.transcriber = StreamingTranscriber(config=self.config)
        
        # Eagerly initialize the model so it doesn't happen during the first audio chunk
        print(f"🧠 Loading STT Engine: {model_name}...")
        self.transcriber._initialize_model()

    def transcribe_stream(self, audio_data: Any) -> Iterable[Any]:
        """
        Transcribes an audio stream (numpy array or tensor).
        Returns an iterator of segments.
        """
        return self.transcriber.stream(audio_data)
