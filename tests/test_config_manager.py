import json
import os
import pytest
from unittest.mock import patch
from babelfish_stt.config import (
    BabelfishConfig,
    CALIBRATION_SCHEMA_VERSION,
    platform_default_device,
)
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


def test_config_manager_strips_stale_performance_keys(tmp_path):
    """pipeline.performance is no longer configuration (ADR 0011
    rework): stale pacing/tier keys are stripped from existing files on
    load and the stripped file is persisted."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "pipeline": {
                    "silence_threshold_ms": 400,
                    "performance": {
                        "ghost_throttle_ms": 400,
                        "ghost_window_s": 1.5,
                        "tier": "low_power",
                        "latch_migrated": True,
                    },
                }
            }
        )
    )

    manager = ConfigManager(config_path=str(config_file))

    assert not hasattr(manager.config.pipeline, "performance")
    assert manager.config.pipeline.silence_threshold_ms == 400
    data = json.loads(config_file.read_text())
    assert "performance" not in data["pipeline"]


def test_config_manager_strip_preserves_calibration(tmp_path):
    """The live strip-migration wipes `pipeline.performance` while
    PRESERVING the `calibration` section (ADR 0013): calibration output
    lives in its own top-level section precisely so the strip cannot
    touch it."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "pipeline": {
                    "performance": {"tier": "low_power"},
                },
                "calibration": {
                    "schema_version": 1,
                    "profiles": {
                        "cuda:0|GPU (CUDA)|None|m|1|1.30.0|0.12.0": {
                            "ghost_throttle_ms": 100,
                            "ghost_window_s": 3.0,
                            "tier": "ultra",
                            "operating_cost_ms": 35.0,
                            "cells": {"multiple_words": {"3.0": 34.0}},
                            "benched_at": "2026-10-05T00:00:00+00:00",
                        }
                    },
                },
            }
        )
    )

    manager = ConfigManager(config_path=str(config_file))

    data = json.loads(config_file.read_text())
    assert "performance" not in data["pipeline"]
    profiles = manager.config.calibration.profiles
    assert len(profiles) == 1
    entry = next(iter(profiles.values()))
    assert entry.tier == "ultra"
    assert entry.ghost_window_s == 3.0
    assert entry.cells["multiple_words"]["3.0"] == 34.0
    # The persisted file still carries the calibration section intact
    assert "calibration" in data
    assert entry in ConfigManager(config_path=str(config_file)).config.calibration.profiles.values()


def test_config_manager_save_roundtrips_calibration(tmp_path):
    """record_calibration persists a benched entry under its fingerprint
    and it survives a save/load cycle (schema_version, cells, tier)."""
    from babelfish_stt.config import CalibrationProfileEntry

    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))

    entry = CalibrationProfileEntry(
        tier="high",
        ghost_throttle_ms=150,
        ghost_window_s=2.0,
        operating_cost_ms=57.3,
        final_rtfx=45.0,
        cells={"multiple_words": {"2.0": 58.4}},
        benched_at="2026-10-05T00:00:00+00:00",
    )
    manager.record_calibration("dml:0|GPU (DirectML)|None|m|1|1.24.4|0.12.0", entry)

    data = json.loads(config_file.read_text())
    assert data["calibration"]["schema_version"] == CALIBRATION_SCHEMA_VERSION
    assert "dml:0|GPU (DirectML)|None|m|1|1.24.4|0.12.0" in data["calibration"]["profiles"]

    reloaded = ConfigManager(config_path=str(config_file))
    entry = reloaded.config.calibration.profiles["dml:0|GPU (DirectML)|None|m|1|1.24.4|0.12.0"]
    assert entry.tier == "high"
    assert entry.operating_cost_ms == 57.3
    assert entry.cells == {"multiple_words": {"2.0": 58.4}}
    assert entry.to_profile().ghost_throttle_ms == 150


def test_config_manager_record_calibration_prunes_at_cap(tmp_path):
    """The store is capped at 4 entries (one per acceleration backend
    fingerprint), pruned oldest-first by benched_at (ADR 0013)."""
    from babelfish_stt.calibration import CALIBRATION_PROFILES_CAP
    from babelfish_stt.config import CalibrationProfileEntry

    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))

    for i in range(CALIBRATION_PROFILES_CAP + 2):
        entry = CalibrationProfileEntry(
            tier="medium",
            ghost_throttle_ms=250,
            ghost_window_s=3.0,
            operating_cost_ms=170.0,
            benched_at=f"2026-10-0{i + 1}T00:00:00+00:00",
        )
        manager.record_calibration(f"backend{i}|dev|None|m|1|1.30.0|0.12.0", entry)

    reloaded = ConfigManager(config_path=str(config_file))
    profiles = reloaded.config.calibration.profiles
    assert len(profiles) == CALIBRATION_PROFILES_CAP
    # Oldest-first: backends 0 and 1 were pruned, the newest kept
    assert set(profiles) == {
        f"backend{i}|dev|None|m|1|1.30.0|0.12.0"
        for i in range(2, CALIBRATION_PROFILES_CAP + 2)
    }


def test_config_manager_performance_strip_is_idempotent(tmp_path):
    """A clean file loads untouched (no spurious saves)."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"pipeline": {"silence_threshold_ms": 500}}))

    with patch(
        "babelfish_stt.config_manager.ConfigManager.save"
    ) as mock_save:
        ConfigManager(config_path=str(config_file))
        mock_save.assert_not_called()


def test_config_manager_save_omits_performance(tmp_path):
    """The saved config never contains a performance section (the profile
    is calibration output, in memory only)."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=str(config_file))
    manager.save()
    data = json.loads(config_file.read_text())
    assert "performance" not in data.get("pipeline", {})


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
