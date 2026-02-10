import queue
import sounddevice as sd
import numpy as np
import soxr
import logging
from typing import Generator, Optional
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import BabelfishConfig

logger = logging.getLogger(__name__)


class AudioStreamer(Reconfigurable):
    """
    Hardware-aware audio capture with low-latency resampling.
    """

    def __init__(self, sample_rate: int = 16000, device_index: Optional[int] = None):
        self.target_rate = sample_rate
        self.device_index = (
            device_index if device_index is not None else sd.default.device[0]
        )

        # Query hardware capabilities
        device_info = sd.query_devices(self.device_index, "input")
        self.native_rate = int(device_info["default_samplerate"])
        self.mic_name = device_info["name"]

        self.audio_queue = queue.Queue()
        self.is_running = False

        # Only resample if hardware rate differs from target
        self.needs_resampling = self.native_rate != self.target_rate

        # Buffer for accumulating audio to ensure consistent chunk sizes
        self._chunk_buffer = np.array([], dtype=np.float32)

        if self.needs_resampling:
            print(
                f"🔄 Resampling enabled: {self.native_rate}Hz -> {self.target_rate}Hz (via soxr)"
            )
        else:
            print(f"🎯 Native match: {self.native_rate}Hz")

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice to capture audio."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        data = indata.copy().flatten()

        # Debug: check RMS
        rms = np.sqrt(np.mean(data**2))
        if rms > 0.001:
            logger.debug(f"Audio captured: RMS={rms:.6f}")

        # Resample if needed (to 16kHz target rate)
        if self.needs_resampling:
            data = soxr.resample(data, self.native_rate, self.target_rate)

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
            dtype="float32",
            device=self.device_index,
            callback=self._audio_callback,
            blocksize=hw_blocksize,
        ):
            while self.is_running:
                try:
                    # Get audio from queue and accumulate in buffer
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    self._chunk_buffer = np.concatenate(
                        [self._chunk_buffer, audio_chunk]
                    )

                    # Yield fixed-size chunks while we have enough data
                    while len(self._chunk_buffer) >= chunk_size:
                        yield self._chunk_buffer[:chunk_size]
                        self._chunk_buffer = self._chunk_buffer[chunk_size:]

                except queue.Empty:
                    continue

    def stop(self):
        """Stops the audio stream."""
        self.is_running = False

    def drain(self):
        """Clears any pending audio in the queue and internal buffer."""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        # Clear the internal chunk buffer
        self._chunk_buffer = np.array([], dtype=np.float32)

    def reconfigure(self, config: BabelfishConfig) -> None:
        """Reconfigure audio stream with new hardware settings."""
        new_device_index = (
            config.hardware.microphone_index
            if config.hardware.microphone_index is not None
            else sd.default.device[0]
        )

        if new_device_index != self.device_index:
            print(f"🎤 Switching microphone: {self.device_index} -> {new_device_index}")

            # Stop current stream
            was_running = self.is_running
            self.stop()

            # Wait a moment for stream to close
            import time

            time.sleep(0.1)

            # Update device
            self.device_index = new_device_index

            # Query new hardware capabilities
            device_info = sd.query_devices(self.device_index, "input")
            self.native_rate = int(device_info["default_samplerate"])
            self.mic_name = device_info["name"]

            # Update resampling flag
            self.needs_resampling = self.native_rate != self.target_rate

            print(f"🎤 New microphone: {self.mic_name} @ {self.native_rate}Hz")

            if self.needs_resampling:
                print(
                    f"🔄 Resampling enabled: {self.native_rate}Hz -> {self.target_rate}Hz"
                )
            else:
                print(f"🎯 Native match: {self.native_rate}Hz")

            # Clear queue
            self.drain()

            # Restart if it was running
            if was_running:
                self.is_running = True


class HistoryBuffer:
    """
    Maintains a fixed-size sliding window of audio samples.
    """

    def __init__(self, maxlen_samples: int = 64000):  # 4s @ 16kHz
        self.maxlen = maxlen_samples
        self.buffer = np.array([], dtype=np.float32)

    def append(self, chunk: np.ndarray):
        """Adds a new chunk and trims the buffer to maxlen."""
        self.buffer = np.concatenate([self.buffer, chunk])
        if len(self.buffer) > self.maxlen:
            self.buffer = self.buffer[-self.maxlen :]

    def get_all(self) -> np.ndarray:
        """Returns the entire current buffer."""
        return self.buffer

    def clear(self):
        """Clears the buffer."""
        self.buffer = np.array([], dtype=np.float32)
