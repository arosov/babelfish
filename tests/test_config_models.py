import pytest
from pydantic import ValidationError
from babelfish_stt.config import (
    HardwareConfig,
    PipelineConfig,
    VoiceConfig,
    UIConfig,
    SystemInputConfig,
    TranscriptionWindowConfig,
    BabelfishConfig,
)


def test_hardware_config_defaults():
    config = HardwareConfig()
    assert config.device == "auto"
    assert config.vram_total_gb == 0.0
    assert config.microphone_name is None


def test_hardware_config_validation():
    with pytest.raises(ValidationError):
        HardwareConfig(vram_total_gb="not a float")


def test_pipeline_config_defaults():
    config = PipelineConfig()
    assert config.silence_threshold_ms == 400
    assert config.performance.tier == "auto"


def test_voice_config_defaults():
    config = VoiceConfig()
    assert config.wakeword is None
    assert config.wakeword_sensitivity == 0.5
    assert config.stop_words == []


def test_system_input_config_defaults():
    config = SystemInputConfig()
    assert config.enabled is False
    assert config.type_ghost is False


def test_transcription_window_config_defaults():
    config = TranscriptionWindowConfig()
    assert config.always_on_top is True


def test_ui_config_defaults():
    config = UIConfig()
    assert config.notifications is True
    assert config.transcription_window.always_on_top is True


def test_babelfish_config_nesting():
    config = BabelfishConfig()
    assert isinstance(config.hardware, HardwareConfig)
    assert isinstance(config.pipeline, PipelineConfig)
    assert isinstance(config.voice, VoiceConfig)
    assert isinstance(config.ui, UIConfig)
    assert isinstance(config.system_input, SystemInputConfig)


def test_babelfish_config_serialization():
    config = BabelfishConfig()
    config.system_input.enabled = True
    json_data = config.model_dump_json()
    assert "system_input" in json_data
    assert '"enabled":true' in json_data

    new_config = BabelfishConfig.model_validate_json(json_data)
    assert new_config.system_input.enabled is True
    assert new_config.hardware.device == config.hardware.device


def test_babelfish_config_nested_validation():
    # Test that nested validation works
    with pytest.raises(ValidationError):
        BabelfishConfig(hardware={"vram_total_gb": "not a number"})


def test_babelfish_config_partial_update():
    # Test updating only one field via dict
    config = BabelfishConfig()
    updated_data = {"pipeline": {"silence_threshold_ms": 500}}

    # We can't directly update from dict in Pydantic easily without model_validate
    # but we can check if validation works on partial dicts if we were to use them
    validated = BabelfishConfig.model_validate({**config.model_dump(), **updated_data})
    assert validated.pipeline.silence_threshold_ms == 500
    assert validated.hardware.device == "auto"  # preserved
