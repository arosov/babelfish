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

    config_key = None  # Reconfigures based on full config

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

        self.audio_queue = queue.Queue(
            maxsize=500
        )  # Increased from 100 to handle blocking transcription times
        self.is_running = False
        self.restart_required = False

        # Buffer for accumulating audio to ensure consistent chunk sizes
        self._chunk_list = []
        self._chunk_buffer_len = 0

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

        # Keep callback minimal: copy data and put in queue
        try:
            self.audio_queue.put_nowait(indata.copy().flatten())
        except queue.Full:
            # Drop audio if queue is full to avoid blocking the callback
            pass

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
                            # Get raw audio from queue
                            raw_audio = self.audio_queue.get(timeout=0.1)

                            # Resample outside of callback
                            if self.needs_resampling:
                                audio_chunk = soxr.resample(
                                    raw_audio, self.native_rate, self.target_rate
                                )
                            else:
                                audio_chunk = raw_audio

                            if len(audio_chunk) == 0:
                                continue

                            # Accumulate in list (more efficient than np.concatenate on every small chunk)
                            self._chunk_list.append(audio_chunk)
                            self._chunk_buffer_len += len(audio_chunk)

                            # Yield fixed-size chunks while we have enough data
                            while self._chunk_buffer_len >= chunk_size:
                                # Only concatenate when we have enough to yield
                                full_buffer = np.concatenate(self._chunk_list)
                                yield full_buffer[:chunk_size]

                                # Keep the remainder
                                remainder = full_buffer[chunk_size:]
                                if len(remainder) > 0:
                                    self._chunk_list = [remainder]
                                    self._chunk_buffer_len = len(remainder)
                                else:
                                    self._chunk_list = []
                                    self._chunk_buffer_len = 0

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
        self._chunk_list = []
        self._chunk_buffer_len = 0

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
