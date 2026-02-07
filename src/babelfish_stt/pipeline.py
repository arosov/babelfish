import numpy as np
import time
from typing import List

class Pipeline:
    def process_chunk(self, chunk: np.ndarray, now_ms: float):
        raise NotImplementedError

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
        self.vad = vad
        self.engine = engine
        self.display = display
        # Implementation will come in later tasks
        
    def process_chunk(self, chunk: np.ndarray, now_ms: float):
        # Placeholder for now
        pass
