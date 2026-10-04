import pytest
from pydantic import ValidationError
from babelfish_stt.config import (
    HardwareConfig,
    HardwareStatus,
    PipelineConfig,
    VoiceConfig,
    UIConfig,
    SystemInputConfig,
    TranscriptionWindowConfig,
    BabelfishConfig,
    platform_default_device,
)


def test_hardware_config_defaults():
    config = HardwareConfig()
    # A concrete platform default, never "auto" (ADR 0007)
    assert config.device == platform_default_device()
    assert config.device != "auto"
    assert config.quantization is None
    assert config.microphone_name is None


def test_platform_default_device_is_concrete(monkeypatch):
    """win32 -> dml; Linux -> cuda only with an NVIDIA driver; darwin -> cpu."""
    from babelfish_stt import config as config_module

    monkeypatch.setattr(config_module.sys, "platform", "win32")
    assert config_module.platform_default_device() == "dml"

    monkeypatch.setattr(config_module.sys, "platform", "darwin")
    assert config_module.platform_default_device() == "cpu"

    monkeypatch.setattr(config_module.sys, "platform", "linux")

    import babelfish_stt.hardware as hardware_module

    monkeypatch.setattr(hardware_module, "detect_nvidia", lambda: True)
    assert config_module.platform_default_device() == "cuda"

    monkeypatch.setattr(hardware_module, "detect_nvidia", lambda: False)
    assert config_module.platform_default_device() == "cpu"


def test_hardware_status_validation():
    status = HardwareStatus()
    assert status.vram_total_gb == 0.0
    with pytest.raises(ValidationError):
        HardwareStatus(vram_total_gb="not a float")


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
    assert config.separator.value == "trailing"


def test_system_input_config_ignores_removed_strategy():
    """ADR 0009: `strategy` no longer exists; stale configs keep loading.

    Known-or-unknown values are silently ignored by pydantic's default parse —
    no aliasing that would validate a setting that no longer means anything.
    """
    for stale_value in ("direct", "clipboard", "native", "hybrid"):
        config = SystemInputConfig(strategy=stale_value)
        assert config.enabled is False
        assert config.separator.value == "trailing"


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
        BabelfishConfig(status={"vram_total_gb": "not a number"})


def test_babelfish_config_partial_update():
    # Test updating only one field via dict
    config = BabelfishConfig()
    updated_data = {"pipeline": {"silence_threshold_ms": 500}}

    # We can't directly update from dict in Pydantic easily without model_validate
    # but we can check if validation works on partial dicts if we were to use them
    validated = BabelfishConfig.model_validate({**config.model_dump(), **updated_data})
    assert validated.pipeline.silence_threshold_ms == 500
    assert validated.hardware.device == platform_default_device()  # preserved
