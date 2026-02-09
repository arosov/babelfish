import pytest
import numpy as np
from babelfish_stt.config import BabelfishConfig
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.vad import SileroVAD
from babelfish_stt.pipeline import StopWordDetector, DoublePassPipeline, SinglePassPipeline
from babelfish_stt.engine import STTEngine
from babelfish_stt.display import TerminalDisplay

def test_hot_reloading_propagation(tmp_path):
    config_file = tmp_path / "config.json"
    cm = ConfigManager(config_path=str(config_file))
    
    # 1. Setup components
    vad = SileroVAD(threshold=0.5)
    stop_detector = StopWordDetector(stop_words=["stop"])
    engine = STTEngine(device="cpu")
    display = TerminalDisplay()
    pipeline = DoublePassPipeline(vad, engine, display)
    
    # Pre-set cm values to match initial component state to pass the initial sync check
    cm.config.voice.wakeword_sensitivity = 0.5
    cm.config.voice.stop_words = ["stop"]
    cm.config.pipeline.anchor_trigger_interval_ms = 2000

    # 2. Register them
    cm.register(vad)
    cm.register(stop_detector)
    cm.register(engine)
    cm.register(pipeline)
    
    # Verify initial values (from defaults)
    assert vad.threshold == 0.5
    assert stop_detector.stop_words == ["stop"]
    assert pipeline.trigger.interval_ms == 2000
    
    # 3. Update config via ConfigManager
    cm.update({
        "voice": {
            "wakeword_sensitivity": 0.8,
            "stop_words": ["finish", "terminate"]
        },
        "pipeline": {
            "anchor_trigger_interval_ms": 500
        }
    })
    
    # 4. Verify propagation
    assert vad.threshold == 0.8
    assert stop_detector.stop_words == ["finish", "terminate"]
    assert pipeline.trigger.interval_ms == 500

def test_hot_reloading_registration_triggers_immediate_sync(tmp_path):
    config_file = tmp_path / "config.json"
    # Create config with non-default values
    config = BabelfishConfig()
    config.voice.wakeword_sensitivity = 0.9
    
    import json
    with open(config_file, "w") as f:
        json.dump(config.model_dump(), f)
        
    cm = ConfigManager(config_path=str(config_file))
    
    vad = SileroVAD(threshold=0.1) # Starts with 0.1
    cm.register(vad)
    
    # Should immediately be updated to 0.9 from cm.config
    assert vad.threshold == 0.9
