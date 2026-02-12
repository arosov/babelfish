import queue
import sounddevice as sd
import numpy as np
import soxr
import logging
import time
from typing import Generator, Optional
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import BabelfishConfig

from babelfish_stt.hardware import find_microphone_index_by_name

logger = logging.getLogger(__name__)


class AudioStreamer(Reconfigurable):
    """
    Hardware-aware audio capture with low-latency resampling.
    """

    def __init__(self, sample_rate: int = 16000, microphone_name: Optional[str] = None):
        self.target_rate = sample_rate

        # Resolve name to index
        device_index = None
        if microphone_name:
            device_index = find_microphone_index_by_name(microphone_name)
            if device_index is None:
                logger.warning(
                    f"Microphone '{microphone_name}' not found. Falling back to default."
                )

        self.device_index = (
            device_index if device_index is not None else sd.default.device[0]
        )

        # Query hardware capabilities
        self._update_device_info()

        self.audio_queue = queue.Queue()
        self.is_running = False
        self.restart_required = False

        # Buffer for accumulating audio to ensure consistent chunk sizes
        self._chunk_buffer = np.array([], dtype=np.float32)

    def _update_device_info(self):
        try:
            device_info = sd.query_devices(self.device_index, "input")
            self.native_rate = int(device_info["default_samplerate"])
            self.mic_name = device_info["name"]

            # Only resample if hardware rate differs from target
            self.needs_resampling = self.native_rate != self.target_rate

            if self.needs_resampling:
                logger.info(
                    f"🔄 Resampling enabled: {self.native_rate}Hz -> {self.target_rate}Hz (via soxr)"
                )
            else:
                logger.info(f"🎯 Native match: {self.native_rate}Hz")
        except Exception as e:
            logger.error(
                f"Failed to query device info for index {self.device_index}: {e}"
            )
            # Fallback to sensible defaults to prevent crashes
            self.native_rate = 16000
            self.mic_name = "Unknown"
            self.needs_resampling = False

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice to capture audio."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        data = indata.copy().flatten()

        # Debug: check RMS
        rms = np.sqrt(np.mean(data**2))
        if rms > 0.001:
            # logger.debug(f"Audio captured: RMS={rms:.6f}")
            pass

        # Resample if needed (to 16kHz target rate)
        if self.needs_resampling:
            data = soxr.resample(data, self.native_rate, self.target_rate)

        if len(data) > 0:
            self.audio_queue.put(data)
        else:
            logger.warning("Captured empty audio data")

    def stream(self, chunk_size: int = 512) -> Generator[np.ndarray, None, None]:
        """
        Starts the microphone stream.
        Note: chunk_size here is in TARGET (16kHz) samples.
        """
        self.is_running = True

        while self.is_running:
            # We calculate the hardware blocksize based on the ratio to maintain
            # the requested 16kHz chunk timing.
            ratio = self.native_rate / self.target_rate
            hw_blocksize = int(chunk_size * ratio)

            try:
                with sd.InputStream(
                    samplerate=self.native_rate,
                    channels=1,
                    dtype="float32",
                    device=self.device_index,
                    callback=self._audio_callback,
                    blocksize=hw_blocksize,
                ):
                    logger.info(
                        f"🎤 Stream started on device {self.device_index} ({self.mic_name})"
                    )

                    while self.is_running and not self.restart_required:
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
            except Exception as e:
                logger.error(f"Stream error on device {self.device_index}: {e}")
                time.sleep(1)  # Prevent tight error loop

            if self.restart_required:
                logger.info("🎤 Restarting stream with new configuration...")
                self.restart_required = False
                self.drain()
                # Loop continues and recreates InputStream with new settings

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

    def reconfigure(self, config: BaseModel) -> None:
        """Reconfigure audio stream with new hardware settings."""
        if not isinstance(config, BabelfishConfig):
            return

        microphone_name = config.hardware.microphone_name

        # Resolve name to index
        new_device_index = None
        if microphone_name:
            new_device_index = find_microphone_index_by_name(microphone_name)

        if new_device_index is None:
            new_device_index = sd.default.device[0]

        if new_device_index != self.device_index:
            logger.info(
                f"🎤 Switching microphone: {self.device_index} -> {new_device_index}"
            )

            # Update device index
            self.device_index = new_device_index

            # Query new info
            self._update_device_info()

            # Signal restart
            self.restart_required = True


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
