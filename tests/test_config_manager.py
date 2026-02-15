import os
import pytest
from babelfish_stt.config import BabelfishConfig
from babelfish_stt.config_manager import ConfigManager


def test_config_manager_load_default(tmp_path):
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))

    # Should load defaults if file doesn't exist
    assert manager.config.hardware.device == "auto"


def test_config_manager_save_load(tmp_path):
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))

    manager.config.pipeline.silence_threshold_ms = 500
    manager.save()

    assert config_file.exists()

    # New manager should load the saved config
    new_manager = ConfigManager(config_path=str(config_file))
    assert new_manager.config.pipeline.silence_threshold_ms == 500


def test_config_manager_atomic_save(tmp_path):
    # This is hard to test perfectly but we can verify it doesn't leave partial files on error if we mock it
    # For now we just verify basic save/load
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))
    manager.save()
    assert config_file.exists()


def test_config_manager_invalid_json(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("{invalid json}")

    # Should probably fall back to defaults or raise error
    # Let's say it falls back to defaults but logs a warning
    manager = ConfigManager(config_path=str(config_file))
    assert manager.config.hardware.device == "auto"


def test_config_manager_save_failure(tmp_path, monkeypatch):
    import os

    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))

    def mock_replace(src, dst):
        raise OSError("Disk full")

    monkeypatch.setattr(os, "replace", mock_replace)

    with pytest.raises(OSError, match="Disk full"):
        manager.save()

    assert not config_file.exists()
