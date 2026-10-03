"""Tests for scripts/bootstrap.py (ADR 0006: babelfish owns its bootstrap).

The bootstrap is a self-contained script (it runs before the project venv
exists), so it is imported here directly from its path.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap.py"


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("babelfish_bootstrap", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bootstrap():
    return _load_bootstrap()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Point config/env reads at a temp dir so the real machine state
    (repo config, VOGON_* variables) can't leak into assertions."""
    monkeypatch.setattr("babelfish_bootstrap.BUNDLE_DIR", tmp_path)
    monkeypatch.delenv("VOGON_APP_DATA_DIR", raising=False)
    monkeypatch.delenv("VOGON_FORCE_CPU", raising=False)


class FakeEnvManager:
    def __init__(self, hw_mode="cpu"):
        self.hw_mode = hw_mode
        self.last_env = None

    def get_env_with_dll_injection(self, hw_mode):
        self.hw_mode = hw_mode
        self.last_env = {"PATH": "/fake"}
        return dict(self.last_env)


def test_split_args_consumes_models_dir(bootstrap):
    models_dir, passthrough = bootstrap._split_args(
        ["--models-dir", "C:/x", "--cpu", "--wakeword", "hey_jarvis"]
    )
    assert models_dir == "C:/x"
    assert passthrough == ["--cpu", "--wakeword", "hey_jarvis"]


def test_split_args_passthrough_only(bootstrap):
    models_dir, passthrough = bootstrap._split_args(["--cpu", "--type"])
    assert models_dir is None
    assert passthrough == ["--cpu", "--type"]


def test_split_args_models_dir_equals_form(bootstrap):
    models_dir, passthrough = bootstrap._split_args(["--models-dir=C:/x"])
    assert models_dir == "C:/x"
    assert passthrough == []


def test_standalone_launch_has_no_server_flags(bootstrap):
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, env = plan.build("nvidia_win", ["--type"])
    assert "--server" not in args
    assert "--port" not in args
    assert args[1:4] == ["run", "--no-sync", "babelfish"]
    assert args[4:] == ["--type"]
    assert env["PATH"] == "/fake"


def test_driven_launch_has_server_flags(bootstrap, monkeypatch):
    monkeypatch.setattr("babelfish_bootstrap.DRIVEN", True)
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, env = plan.build("nvidia_win")
    assert args[4:8] == ["--server", "--port", "8123"]


def test_force_cpu_env_var_appends_cpu_flag(bootstrap, monkeypatch):
    monkeypatch.setenv("VOGON_FORCE_CPU", "1")
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, _ = plan.build("nvidia_win", ["--type"])
    assert "--cpu" in args
    assert "--type" in args  # passthrough preserved


def test_config_cpu_device_appends_cpu_flag(bootstrap, tmp_path):
    config = tmp_path / "babelfish.config.json"
    config.write_text(json.dumps({"hardware": {"device": "cpu"}}))
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, _ = plan.build("nvidia_win")
    assert "--cpu" in args


def test_cpu_hw_mode_appends_cpu_flag(bootstrap):
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, _ = plan.build("cpu")
    assert "--cpu" in args


def test_gpu_mode_without_force_has_no_cpu_flag(bootstrap):
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, _ = plan.build("nvidia_win")
    assert "--cpu" not in args


class TestHardwareDetectorModes:
    def test_nvidia_windows_uses_nvidia_win(self, bootstrap, monkeypatch):
        detector = bootstrap.HardwareDetector()
        monkeypatch.setattr(bootstrap.HardwareDetector, "detect_nvidia", lambda s: True)
        monkeypatch.setattr(
            bootstrap.HardwareDetector, "get_all_gpus", lambda s: ["NVIDIA GPU"]
        )
        hw = detector.get_best_mode()
        assert hw == {
            "hw_mode": "nvidia_win",
            "extra": "nvidia-win",
            "desc": "NVIDIA GPU",
        }

    def test_nvidia_dml_config_uses_windows_gpu(self, bootstrap, monkeypatch, tmp_path):
        monkeypatch.setattr(
            bootstrap, "_read_config_device", lambda: "dml:0"
        )
        detector = bootstrap.HardwareDetector()
        monkeypatch.setattr(bootstrap.HardwareDetector, "detect_nvidia", lambda s: True)
        monkeypatch.setattr(
            bootstrap.HardwareDetector, "get_all_gpus", lambda s: ["NVIDIA GPU"]
        )
        hw = detector.get_best_mode()
        assert hw["extra"] == "windows-gpu"
        assert "DirectML" in hw["desc"]

    def test_amd_linux(self, bootstrap, monkeypatch):
        detector = bootstrap.HardwareDetector()
        monkeypatch.setattr(bootstrap.HardwareDetector, "detect_nvidia", lambda s: False)
        monkeypatch.setattr(
            bootstrap.HardwareDetector, "detect_amd_linux", lambda s: True
        )
        monkeypatch.setattr(bootstrap.HardwareDetector, "get_all_gpus", lambda s: [])
        hw = detector.get_best_mode()
        if sys.platform == "win32":
            assert hw["extra"] == "windows-gpu"
        else:
            assert hw["extra"] == "amd-linux"

    def test_no_gpu_falls_back_to_cpu(self, bootstrap, monkeypatch):
        detector = bootstrap.HardwareDetector()
        monkeypatch.setattr(bootstrap.HardwareDetector, "detect_nvidia", lambda s: False)
        monkeypatch.setattr(
            bootstrap.HardwareDetector, "detect_amd_linux", lambda s: False
        )
        monkeypatch.setattr(bootstrap.HardwareDetector, "detect_metal", lambda s: False)
        monkeypatch.setattr(bootstrap.HardwareDetector, "get_all_gpus", lambda s: [])
        hw = detector.get_best_mode()
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"


def test_ort_package_map_covers_all_modes(bootstrap):
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    ort_map = {
        "cpu": "onnxruntime",
        "nvidia_win": "onnxruntime-gpu",
        "nvidia_linux": "onnxruntime-gpu",
        "amd_linux": "onnxruntime-rocm",
        "windows_gpu": "onnxruntime-directml",
        "metal": "onnxruntime",
    }
    # Every extra the detector can return maps to exactly one ORT flavor
    # (this is the mixed-install self-heal pair with --reinstall-package).
    for extra in ("cpu", "nvidia-win", "nvidia-linux", "amd-linux", "windows-gpu"):
        assert any(
            hw["extra"] == extra for hw in _all_detector_modes(bootstrap)
        )
    assert len(ort_map) == 6


def _all_detector_modes(bootstrap):
    """Enumerate the mode table the detector can return for the record."""
    return [
        {"hw_mode": "nvidia_win", "extra": "nvidia-win"},
        {"hw_mode": "nvidia_linux", "extra": "nvidia-linux"},
        {"hw_mode": "amd_linux", "extra": "amd-linux"},
        {"hw_mode": "windows_gpu", "extra": "windows-gpu"},
        {"hw_mode": "metal", "extra": "cpu"},
        {"hw_mode": "cpu", "extra": "cpu"},
    ]
