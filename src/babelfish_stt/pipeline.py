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


class HybridTrigger:
    """
    Triggers a refinement pass based on a timer or a VAD pause.
    """

    def __init__(self, interval_ms: int = 2000):
        self.interval_ms = interval_ms
        self.last_trigger_time = 0
        self.is_speaking = False
        self.speech_start_time = 0

    def start_speech(self, now_ms: float):
        if not self.is_speaking:
            self.is_speaking = True
            self.speech_start_time = now_ms
            self.last_trigger_time = now_ms

    def should_trigger(self, now_ms: float, is_speaking: bool) -> bool:
        if not self.is_speaking:
            return False

        # Trigger on VAD pause
        if not is_speaking:
            return True

        # Trigger on interval
        if now_ms - self.last_trigger_time >= self.interval_ms:
            return True

        return False

    def reset(self, now_ms: float):
        self.last_trigger_time = now_ms
        # We don't reset is_speaking here, as the caller handles that state

    def stop_speech(self):
        self.is_speaking = False


class AlignmentManager:
    """
    Manages text alignment and prefix context extraction.
    """

    def __init__(self, context_words: int = 4):
        self.context_words = context_words

    def get_prefix_context(self, text: str) -> str:
        """Extracts the last N words as prefix context."""
        words = text.split()
        if not words:
            return ""
        return " ".join(words[-self.context_words :])


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


class SinglePassPipeline(Pipeline):
    def __init__(self, vad, engine, display):
        super().__init__()
        self.vad = vad
        self.engine = engine
        self.display = display

        self.active_buffer = []
        self.last_speech_time = 0
        self.is_speaking = False
        self.silence_threshold_ms = 400
        self.update_interval_samples = 1600  # 100ms @ 16kHz
        self.last_update_size = 0

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

            self.active_buffer.append(chunk)
            self.last_speech_time = now_ms

            # Update display periodically while speaking
            current_size = sum(len(c) for c in self.active_buffer)
            if current_size - self.last_update_size >= self.update_interval_samples:
                full_audio = np.concatenate(self.active_buffer)
                text = self.engine.transcribe(full_audio)
                if text:
                    self.display.update(text)
                    if self.stop_detector and self.stop_detector.detect(text):
                        self._handle_stop()
                        return True
                self.last_update_size = current_size
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
        self.last_update_size = 0
        if self.is_speaking:
            self.is_speaking = False
            self._notify_state_change(False)
        self.vad.reset_states()


class DoublePassPipeline(Pipeline):
    def __init__(self, vad, engine, display):
        from babelfish_stt.audio import HistoryBuffer

        super().__init__()
        self.vad = vad
        self.engine = engine
        self.display = display

        self.history = HistoryBuffer(maxlen_samples=64000)  # 4s @ 16kHz
        self.trigger = HybridTrigger(interval_ms=2000)
        self.alignment = AlignmentManager(context_words=4)

        self.active_ghost_buffer = []
        self.refined_text = ""
        self.is_speaking = False
        self.last_speech_time = 0
        self.silence_threshold_ms = 400
        self.last_ghost_time = 0
        self.ghost_throttle_ms = 100
        # self.min_ghost_audio_ms removed, handled by STTEngine padding

    def reconfigure(self, config: PipelineConfig) -> None:
        """Apply pipeline settings."""
        self.trigger.interval_ms = config.anchor_trigger_interval_ms

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
        self.history.append(chunk)

        if is_speech:
            if not self.is_speaking:
                self.is_speaking = True
                self._notify_state_change(True)
                self.trigger.start_speech(now_ms)
                self.active_ghost_buffer = []

            self.active_ghost_buffer.append(chunk)
            self.last_speech_time = now_ms

            if self.trigger.should_trigger(now_ms, is_speaking=True):
                if self._run_anchor_pass(now_ms):
                    return True
            else:
                if now_ms - self.last_ghost_time >= self.ghost_throttle_ms:
                    if self._run_ghost_pass():
                        return True
                    self.last_ghost_time = now_ms
        else:
            if self.is_speaking:
                self.active_ghost_buffer.append(chunk)

                # Check for finalized sentence (long silence)
                if now_ms - self.last_speech_time > self.silence_threshold_ms:
                    if self._run_anchor_pass(now_ms, finalize=True):
                        return True
                    self._reset_utterance()
                # Check for minor pause trigger
                elif self.trigger.should_trigger(now_ms, is_speaking=False):
                    if self._run_anchor_pass(now_ms):
                        return True

        return False

    def _run_anchor_pass(self, now_ms: float, finalize: bool = False) -> bool:
        """High-accuracy refinement pass. Returns True if stop word detected."""
        self.engine.set_quality("balanced")

        audio = self.history.get_all()
        new_refined = self.engine.transcribe(audio)

        stop_detected = False
        if new_refined:
            self.refined_text = new_refined
            if finalize:
                self.display.finalize(self.refined_text)
            else:
                # Prepare for next ghost pass by clearing its buffer
                # The anchor pass has covered all history
                self.active_ghost_buffer = []
                self.display.update(refined=self.refined_text)

            if self.stop_detector and self.stop_detector.detect(self.refined_text):
                self._handle_stop()
                stop_detected = True

        self.trigger.reset(now_ms)
        self.engine.set_quality("realtime")
        return stop_detected

    def _run_ghost_pass(self) -> bool:
        """Fast low-latency update. Returns True if stop word detected."""
        if not self.active_ghost_buffer:
            return False

        audio = np.concatenate(self.active_ghost_buffer)

        # Provide audio context if we have refined text to stay aligned
        if self.refined_text:
            history_audio = self.history.get_all()
            # Use up to 2 seconds of previous audio as context
            context_samples = 32000

            # We want the audio BEFORE the active_ghost_buffer
            ghost_len = len(audio)
            available_history = history_audio[:-ghost_len]
            context_audio = (
                available_history[-context_samples:]
                if len(available_history) > context_samples
                else available_history
            )

            full_audio = np.concatenate([context_audio, audio])
            context_secs = len(context_audio) / 16000.0
            ghost_text = self.engine.transcribe(
                full_audio, left_context_secs=context_secs
            )
        else:
            ghost_text = self.engine.transcribe(audio)

        if ghost_text:
            # For now, we rely on the display to handle the merge with styles
            self.display.update(refined=self.refined_text, ghost=ghost_text)

            # Check for stop words in the combined text if available, or just ghost text
            # Display update already shows the combination.
            # Stop detector should ideally see the "full" text.
            combined_text = (self.refined_text + " " + ghost_text).strip()
            if self.stop_detector and self.stop_detector.detect(combined_text):
                self._handle_stop()
                return True

        return False

    def _handle_stop(self):
        self.set_idle(True)
        self._reset_utterance()

    def _reset_utterance(self):
        if self.is_speaking:
            self.is_speaking = False
            self._notify_state_change(False)
        self.trigger.stop_speech()
        self.refined_text = ""
        self.active_ghost_buffer = []
        self.vad.reset_states()
        self.history.clear()
