import queue
import sounddevice as sd
import numpy as np
from typing import Generator, Optional

class AudioStreamer:
    """
    Manages real-time microphone audio capture using sounddevice.
    """
    
    def __init__(self, sample_rate: int = 16000, device_index: Optional[int] = None):
        self.sample_rate = sample_rate
        self.device_index = device_index if device_index is not None else sd.default.device[0]
        self.audio_queue = queue.Queue()
        self.is_running = False

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice to capture audio."""
        if status:
            # We could log this if needed
            pass
        self.audio_queue.put(indata.copy().flatten())

    def stream(self) -> Generator[np.ndarray, None, None]:
        """
        Starts the microphone stream and yields audio chunks.
        """
        self.is_running = True
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            device=self.device_index,
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.1) # 100ms chunks
        ):
            while self.is_running:
                try:
                    # Yield chunks from the queue
                    chunk = self.audio_queue.get(timeout=0.1)
                    yield chunk
                except queue.Empty:
                    continue

    def stop(self):
        """Stops the audio stream."""
        self.is_running = False

    def _stream_generator(self):
        # Helper for testing/mocking
        return self.stream()
