import numpy as np
import time
from typing import List, Optional
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import (
    VoiceConfig,
    UIConfig,
    PipelineConfig,
    PerformanceProfile,
)


class Pipeline(Reconfigurable):
    def __init__(self):
        self.is_idle = False
        self.stop_detector: Optional[StopWordDetector] = None
        self.on_state_change = None  # Callback(is_speaking: bool)
        self.on_mode_change = None  # Callback(is_idle: bool)
        self.test_mode = False  # When True, run VAD only and drop audio

    def set_idle(self, idle: bool):
        if self.is_idle != idle:
            self.is_idle = idle
            # Reset state on ANY transition to ensure clean start/stop
            self.reset_state()
            if self.on_mode_change:
                self.on_mode_change(idle)

    def reset_state(self):
        """Resets internal audio buffers and VAD states."""
        pass

    def set_test_mode(self, enabled: bool):
        """Enable/disable microphone test mode. When enabled, VAD runs but audio is dropped."""
        self.test_mode = enabled

    def _notify_state_change(self, is_speaking: bool):
        if self.on_state_change:
            self.on_state_change(is_speaking)

    def process_chunk(self, chunk: np.ndarray, now_ms: float) -> bool:
        """
        Returns True if a state transition occurred (e.g., stop word detected).
        """
        raise NotImplementedError

    def reconfigure(self, config: BaseModel) -> None:
        """Pipeline base reconfiguration (e.g., logic shifts if needed)"""
        pass


class StopWordDetector(Reconfigurable):
    """
    Detects stop phrases in transcript strings.
    """

    def __init__(self, stop_words: List[str]):
        self.stop_words = [w.lower().strip() for w in stop_words]

    def reconfigure(self, config: BaseModel) -> None:
        """Update stop words list."""
        if isinstance(config, VoiceConfig):
            self.stop_words = [w.lower().strip() for w in config.stop_words]

    def detect(self, text: str) -> bool:
        """
        Returns True if the text ends with any of the stop words.
        Handles basic punctuation at the end of the text.
        """
        if not text:
            return False

        # Normalize text: lower case and remove trailing punctuation
        text_clean = text.lower().strip()
        while text_clean and text_clean[-1] in ".,!?;:":
            text_clean = text_clean[:-1].strip()

        for stop_phrase in self.stop_words:
            # Check if the text ends exactly with the stop phrase
            # We want to match whole words/phrases at the end
            if text_clean == stop_phrase:
                return True
            if text_clean.endswith(" " + stop_phrase):
                return True

        return False


class StandardPipeline(Pipeline):
    """
    Streamlined pipeline for high-performance STT.
    Handles intermediate 'ghost' updates and final commitments.
    """

    def __init__(self, vad, engine, display):
        super().__init__()
        self.vad = vad
        self.engine = engine
        self.display = display

        self.active_buffer = []
        self.last_speech_time = 0
        self.is_speaking = False
        self.silence_threshold_ms = 400
        self.update_interval_ms = 100
        self.last_update_time = 0

        # Performance Profile (Self-Calibration)
        self.perf = PerformanceProfile()
        self.dynamic_throttle_ms = 100
        self.inference_history = []

    def reconfigure(self, config: BaseModel) -> None:
        if isinstance(config, PipelineConfig):
            self.silence_threshold_ms = config.silence_threshold_ms
            self.update_interval_ms = config.update_interval_ms
            self.perf = config.performance
            self.dynamic_throttle_ms = self.perf.ghost_throttle_ms

    def _apply_dynamic_backoff(self, inference_ms: float):
        """Adjusts the ghost update throttle based on real-time inference latency."""
        self.inference_history.append(inference_ms)
        if len(self.inference_history) > 5:
            self.inference_history.pop(0)

        avg_latency = sum(self.inference_history) / len(self.inference_history)

        # If inference is taking more than 80% of our throttle budget, back off
        target_throttle = max(self.perf.ghost_throttle_ms, int(avg_latency * 1.25))

        # Smoothly adjust throttle
        if target_throttle > self.dynamic_throttle_ms:
            self.dynamic_throttle_ms = min(target_throttle, 1000)  # Max 1s lag
        elif target_throttle < self.dynamic_throttle_ms:
            self.dynamic_throttle_ms = max(target_throttle, self.perf.ghost_throttle_ms)

    def process_chunk(self, chunk: np.ndarray, now_ms: float) -> bool:
        if self.is_idle:
            return False

        is_speech = self.vad.is_speech(chunk)

        # Handle test mode: run VAD but don't accumulate audio or transcribe
        if self.test_mode:
            if is_speech:
                if not self.is_speaking:
                    self.is_speaking = True
                    self._notify_state_change(True)
                self.last_speech_time = now_ms
            else:
                # Silence detected in test mode
                if self.is_speaking:
                    if now_ms - self.last_speech_time > self.silence_threshold_ms:
                        self.is_speaking = False
                        self._notify_state_change(False)
            return False

        # Normal mode: accumulate audio and transcribe
        if is_speech:
            if not self.is_speaking:
                self.is_speaking = True
                self._notify_state_change(True)
                self.last_update_time = now_ms

            self.active_buffer.append(chunk)
            self.last_speech_time = now_ms

            # Intermediate 'Ghost' Update
            if now_ms - self.last_update_time >= self.dynamic_throttle_ms:
                full_audio = np.concatenate(self.active_buffer)

                # EFFICIENT FIRST PASS: Sliding window for ghost results (GPU ONLY)
                if self.engine.device_type != "cpu" and self.perf.ghost_window_s > 0:
                    window_samples = int(self.perf.ghost_window_s * 16000)
                    if len(full_audio) > window_samples:
                        full_audio = full_audio[-window_samples:]

                import time

                start = time.perf_counter()
                text = self.engine.transcribe(
                    full_audio, padding_s=self.perf.min_padding_s
                )
                self._apply_dynamic_backoff((time.perf_counter() - start) * 1000)

                if text:
                    self.display.update(ghost=text)  # Pass as ghost for real-time feel
                    if self.stop_detector and self.stop_detector.detect(text):
                        self._handle_stop()
                        return True
                self.last_update_time = now_ms
        else:
            # Silence detected
            if self.is_speaking:
                self.active_buffer.append(chunk)

                # If we've been silent long enough, finalize
                if now_ms - self.last_speech_time > self.silence_threshold_ms:
                    full_audio = np.concatenate(self.active_buffer)
                    # Use full context for finalization, no windowing
                    text = self.engine.transcribe(
                        full_audio, padding_s=self.perf.min_padding_s
                    )
                    if text:
                        self.display.finalize(text)
                        if self.stop_detector and self.stop_detector.detect(text):
                            self._handle_stop()
                            return True

                    self.reset_state()

        return False

    def _handle_stop(self):
        self.set_idle(True)

    def reset_state(self):
        # Reset for next sentence
        self.active_buffer = []
        self.last_update_time = 0
        if self.is_speaking:
            self.is_speaking = False
            self._notify_state_change(False)
        self.vad.reset_states()
