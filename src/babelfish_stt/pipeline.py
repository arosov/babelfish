import numpy as np
import time
from typing import List

class Pipeline:
    def process_chunk(self, chunk: np.ndarray, now_ms: float):
        raise NotImplementedError

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
        return " ".join(words[-self.context_words:])

class SinglePassPipeline(Pipeline):
    def __init__(self, vad, engine, display):
        self.vad = vad
        self.engine = engine
        self.display = display
        
        self.active_buffer = []
        self.last_speech_time = 0
        self.is_speaking = False
        self.silence_threshold_ms = 700
        self.update_interval_samples = 3200
        self.last_update_size = 0

    def process_chunk(self, chunk: np.ndarray, now_ms: float):
        if self.vad.is_speech(chunk):
            if not self.is_speaking:
                self.is_speaking = True
            
            self.active_buffer.append(chunk)
            self.last_speech_time = now_ms
            
            # Update display periodically while speaking
            current_size = sum(len(c) for c in self.active_buffer)
            if current_size - self.last_update_size >= self.update_interval_samples:
                full_audio = np.concatenate(self.active_buffer)
                text = self.engine.transcribe(full_audio)
                if text:
                    self.display.update(text)
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
                    
                    # Reset for next sentence
                    self.active_buffer = []
                    self.last_update_size = 0
                    self.is_speaking = False
                    self.vad.reset_states()

class DoublePassPipeline(Pipeline):
    def __init__(self, vad, engine, display):
        from babelfish_stt.audio import HistoryBuffer
        self.vad = vad
        self.engine = engine
        self.display = display
        
        self.history = HistoryBuffer(maxlen_samples=64000) # 4s @ 16kHz
        self.trigger = HybridTrigger(interval_ms=2000)
        self.alignment = AlignmentManager(context_words=4)
        
        self.active_ghost_buffer = []
        self.refined_text = ""
        self.is_speaking = False
        self.last_speech_time = 0
        self.silence_threshold_ms = 700
        
    def process_chunk(self, chunk: np.ndarray, now_ms: float):
        is_speech = self.vad.is_speech(chunk)
        self.history.append(chunk)

        if is_speech:
            if not self.is_speaking:
                self.is_speaking = True
                self.trigger.start_speech(now_ms)
                self.active_ghost_buffer = []
            
            self.active_ghost_buffer.append(chunk)
            self.last_speech_time = now_ms

            if self.trigger.should_trigger(now_ms, is_speaking=True):
                self._run_anchor_pass(now_ms)
            else:
                self._run_ghost_pass()
        else:
            if self.is_speaking:
                self.active_ghost_buffer.append(chunk)
                
                # Check for finalized sentence (long silence)
                if now_ms - self.last_speech_time > self.silence_threshold_ms:
                    self._run_anchor_pass(now_ms, finalize=True)
                    self._reset_utterance()
                # Check for minor pause trigger
                elif self.trigger.should_trigger(now_ms, is_speaking=False):
                    self._run_anchor_pass(now_ms)

    def _run_anchor_pass(self, now_ms: float, finalize: bool = False):
        """High-accuracy refinement pass."""
        self.engine.set_quality('balanced')
        
        audio = self.history.get_all()
        new_refined = self.engine.transcribe(audio)
        
        if new_refined:
            self.refined_text = new_refined
            if finalize:
                self.display.finalize(self.refined_text)
            else:
                # Prepare for next ghost pass by clearing its buffer
                # The anchor pass has covered all history
                self.active_ghost_buffer = []
                self.display.update(refined=self.refined_text)
        
        self.trigger.reset(now_ms)
        self.engine.set_quality('realtime')

    def _run_ghost_pass(self):
        """Fast low-latency update."""
        if not self.active_ghost_buffer:
            return
            
        audio = np.concatenate(self.active_ghost_buffer)
        
        # Provide audio context if we have refined text to stay aligned
        if self.refined_text:
            history_audio = self.history.get_all()
            # Use up to 2 seconds of previous audio as context
            context_samples = 32000
            # Ensure we don't include the current ghost buffer twice if it's already in history
            # Actually history.append(chunk) is called at the start of process_chunk, 
            # so active_ghost_buffer is already at the end of history.
            
            # We want the audio BEFORE the active_ghost_buffer
            ghost_len = len(audio)
            available_history = history_audio[:-ghost_len]
            context_audio = available_history[-context_samples:] if len(available_history) > context_samples else available_history
            
            full_audio = np.concatenate([context_audio, audio])
            context_secs = len(context_audio) / 16000.0
            ghost_text = self.engine.transcribe(full_audio, left_context_secs=context_secs)
        else:
            ghost_text = self.engine.transcribe(audio)
        
        if ghost_text:
            # Contextual Merge: 
            # If ghost_text starts with words that are at the end of refined_text, 
            # we should avoid duplicating them.
            
            # For now, we rely on the display to handle the merge with styles
            self.display.update(refined=self.refined_text, ghost=ghost_text)

    def _reset_utterance(self):
        self.is_speaking = False
        self.trigger.stop_speech()
        self.refined_text = ""
        self.active_ghost_buffer = []
        self.vad.reset_states()
        self.history.clear()
