import queue
import sounddevice as sd
import numpy as np
import soxr
from typing import Generator, Optional

class AudioStreamer:
    """
    Hardware-aware audio capture with low-latency resampling.
    """
    
    def __init__(self, sample_rate: int = 16000, device_index: Optional[int] = None):
        self.target_rate = sample_rate
        self.device_index = device_index if device_index is not None else sd.default.device[0]
        
        # Query hardware capabilities
        device_info = sd.query_devices(self.device_index, 'input')
        self.native_rate = int(device_info['default_samplerate'])
        self.mic_name = device_info['name']
        
        self.audio_queue = queue.Queue()
        self.is_running = False
        
        # Only resample if hardware rate differs from target
        self.needs_resampling = self.native_rate != self.target_rate
        
        if self.needs_resampling:
            print(f"🔄 Resampling enabled: {self.native_rate}Hz -> {self.target_rate}Hz (via soxr)")
        else:
            print(f"🎯 Native match: {self.native_rate}Hz")

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice to capture audio."""
        if status:
            # Silence internal overflows/underflows for now
            pass
            
        data = indata.copy().flatten()
        
        if self.needs_resampling:
            # Low-latency resampling via soxr
            resampled = soxr.resample(data, self.native_rate, self.target_rate)
            self.audio_queue.put(resampled)
        else:
            self.audio_queue.put(data)

    def stream(self, chunk_size: int = 512) -> Generator[np.ndarray, None, None]:
        """
        Starts the microphone stream. 
        Note: chunk_size here is in TARGET (16kHz) samples.
        """
        self.is_running = True
        
        # We calculate the hardware blocksize based on the ratio to maintain 
        # the requested 16kHz chunk timing.
        ratio = self.native_rate / self.target_rate
        hw_blocksize = int(chunk_size * ratio)
        
        with sd.InputStream(
            samplerate=self.native_rate,
            channels=1,
            dtype='float32',
            device=self.device_index,
            callback=self._audio_callback,
            blocksize=hw_blocksize
        ):
            while self.is_running:
                try:
                    chunk = self.audio_queue.get(timeout=0.1)
                    yield chunk
                except queue.Empty:
                    continue

    def stop(self):
        """Stops the audio stream."""
        self.is_running = False

    def drain(self):
        """Clears any pending audio in the queue."""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
