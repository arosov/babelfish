import pytest
from pydantic import ValidationError
from babelfish_stt.config import (
    HardwareConfig, 
    PipelineConfig, 
    VoiceConfig, 
    UIConfig, 
    BabelfishConfig
)

def test_hardware_config_defaults():
    config = HardwareConfig()
    assert config.device == "auto"
    assert config.vram_limit_gb is None
    assert config.microphone_index is None

def test_hardware_config_validation():
    with pytest.raises(ValidationError):
        HardwareConfig(vram_limit_gb="a lot")

def test_pipeline_config_defaults():
    config = PipelineConfig()
    assert config.double_pass is False
    assert config.ghost_preset == "fast"
    assert config.anchor_preset == "solid"

def test_voice_config_defaults():
    config = VoiceConfig()
    assert config.wakeword is None
    assert config.wakeword_sensitivity == 0.5
    assert config.stop_words == []

def test_ui_config_defaults():
    config = UIConfig()
    assert config.verbose is False
    assert config.show_timestamps is True

def test_babelfish_config_nesting():
    config = BabelfishConfig()
    assert isinstance(config.hardware, HardwareConfig)
    assert isinstance(config.pipeline, PipelineConfig)
    assert isinstance(config.voice, VoiceConfig)
    assert isinstance(config.ui, UIConfig)

def test_babelfish_config_serialization():
    config = BabelfishConfig()
    json_data = config.model_dump_json()
    assert "hardware" in json_data
    
    new_config = BabelfishConfig.model_validate_json(json_data)
    assert new_config.hardware.device == config.hardware.device
