import pytest
import numpy as np
from babelfish_stt.wakeword import WakeWordEngine

def test_wakeword_engine_init():
    """Test that the WakeWordEngine can be initialized with a model name."""
    # We'll use a standard model like 'hey_jarvis' which is usually included
    engine = WakeWordEngine(model_name="hey_jarvis")
    assert engine.model_name == "hey_jarvis"
    assert engine.oww_model is not None

def test_wakeword_engine_detection():
    """Test that the engine can process audio and (eventually) detect a keyword."""
    engine = WakeWordEngine(model_name="hey_jarvis")
    
    # Create a small buffer of silence
    # openWakeWord expects 16kHz audio, usually in chunks of 1280 samples
    chunk = np.zeros(1280, dtype=np.float32)
    
    # This should not raise an error
    result = engine.process_chunk(chunk)
    
    assert isinstance(result, dict)
    assert "hey_jarvis" in result
    assert isinstance(result["hey_jarvis"], float)
