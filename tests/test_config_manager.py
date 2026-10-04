import json
import os
import pytest
from babelfish_stt.config import BabelfishConfig, platform_default_device
from babelfish_stt.config_manager import ConfigManager


def test_config_manager_load_default(tmp_path):
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))

    # Should load defaults if file doesn't exist
    assert manager.config.hardware.device == platform_default_device()


def test_config_manager_migrates_legacy_auto_device(tmp_path, caplog):
    """An old config's 'auto' device is rewritten to the platform default."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"hardware": {"device": "auto"}}))

    with caplog.at_level("INFO"):
        manager = ConfigManager(config_path=str(config_file))

    assert manager.config.hardware.device == platform_default_device()
    assert any("Migrating legacy device 'auto'" in r.message for r in caplog.records)

    # Persisted so bootstrap / the UI see the same concrete device next launch
    data = json.loads(config_file.read_text())
    assert data["hardware"]["device"] == platform_default_device()


def test_config_manager_migrates_legacy_empty_device(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"hardware": {"device": ""}}))

    manager = ConfigManager(config_path=str(config_file))

    assert manager.config.hardware.device == platform_default_device()
    data = json.loads(config_file.read_text())
    assert data["hardware"]["device"] == platform_default_device()


def test_config_manager_migrates_legacy_rocm_device(tmp_path, monkeypatch):
    import babelfish_stt.config_manager as cm_module

    monkeypatch.setattr(cm_module, "platform_default_device", lambda: "dml")
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"hardware": {"device": "rocm:0"}}))

    manager = ConfigManager(config_path=str(config_file))

    assert manager.config.hardware.device == "dml"
    data = json.loads(config_file.read_text())
    assert data["hardware"]["device"] == "dml"


def test_config_manager_keeps_concrete_device(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"hardware": {"device": "dml:1"}}))

    manager = ConfigManager(config_path=str(config_file))

    assert manager.config.hardware.device == "dml:1"
    data = json.loads(config_file.read_text())
    assert data["hardware"]["device"] == "dml:1"


def test_config_manager_migrates_latched_tier_to_auto(tmp_path):
    """A tier persisted by the old latching benchmark is rewritten to
    'auto' once (ADR 0011)."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"pipeline": {"performance": {"tier": "low_power"}}})
    )

    manager = ConfigManager(config_path=str(config_file))

    assert manager.config.pipeline.performance.tier == "auto"
    data = json.loads(config_file.read_text())
    assert data["pipeline"]["performance"]["tier"] == "auto"
    assert data["pipeline"]["performance"]["latch_migrated"] is True


def test_config_manager_latch_migration_is_one_time(tmp_path):
    """After the migration, a concrete tier in the file is a deliberate
    manual override and must not be rewritten again (ADR 0011)."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "pipeline": {
                    "performance": {
                        "tier": "low_power",
                        "latch_migrated": True,
                    }
                }
            }
        )
    )

    manager = ConfigManager(config_path=str(config_file))

    assert manager.config.pipeline.performance.tier == "low_power"
    data = json.loads(config_file.read_text())
    assert data["pipeline"]["performance"]["tier"] == "low_power"


def test_config_manager_auto_tier_is_untouched(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"pipeline": {"performance": {"tier": "auto"}}})
    )

    manager = ConfigManager(config_path=str(config_file))

    assert manager.config.pipeline.performance.tier == "auto"
    assert manager.config.pipeline.performance.latch_migrated is False


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
    assert manager.config.hardware.device == platform_default_device()


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
