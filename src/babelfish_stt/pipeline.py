import numpy as np
import time
from typing import List, Optional
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import VoiceConfig, UIConfig, PipelineConfig


class Pipeline(Reconfigurable):
    def __init__(self):
        self.is_idle = False
        self.stop_detector: Optional[StopWordDetector] = None
        self.on_state_change = None  # Callback(is_speaking: bool)
        self.test_mode = False  # When True, run VAD only and drop audio

    def set_idle(self, idle: bool):
        self.is_idle = idle

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

    def reconfigure(self, config: PipelineConfig) -> None:
        """Pipeline base reconfiguration (e.g., logic shifts if needed)"""
        pass


class StopWordDetector(Reconfigurable):
    """
    Detects stop phrases in transcript strings.
    """

    def __init__(self, stop_words: List[str]):
        self.stop_words = [w.lower().strip() for w in stop_words]

    def reconfigure(self, config: VoiceConfig) -> None:
        """Update stop words list."""
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

    def reconfigure(self, config: PipelineConfig) -> None:
        self.silence_threshold_ms = config.silence_threshold_ms
        self.update_interval_ms = config.update_interval_ms

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
            if now_ms - self.last_update_time >= self.update_interval_ms:
                full_audio = np.concatenate(self.active_buffer)
                text = self.engine.transcribe(full_audio)
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
                    text = self.engine.transcribe(full_audio)
                    if text:
                        self.display.finalize(text)
                        if self.stop_detector and self.stop_detector.detect(text):
                            self._handle_stop()
                            return True

                    self._reset_utterance()

        return False

    def _handle_stop(self):
        self.set_idle(True)
        self._reset_utterance()

    def _reset_utterance(self):
        # Reset for next sentence
        self.active_buffer = []
        self.last_update_time = 0
        if self.is_speaking:
            self.is_speaking = False
            self._notify_state_change(False)
        self.vad.reset_states()
