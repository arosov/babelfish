"""Tests for scripts/bootstrap.py (ADR 0006: babelfish owns its bootstrap).

The bootstrap is a self-contained script (it runs before the project venv
exists), so it is imported here directly from its path.
"""

import importlib.util
import asyncio
import json
import os
import subprocess
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


def test_ort_flavor_map_covers_all_modes(bootstrap):
    """Every hw_mode the detector can return maps to exactly one ORT flavor
    package + required provider (ORT_FLAVOR feeds both the
    --reinstall-package choice and the live verify_ort_flavor check)."""
    detector_modes = {m["hw_mode"] for m in _all_detector_modes(bootstrap)}
    assert detector_modes <= set(bootstrap.ORT_FLAVOR)
    # intel-linux has no detector branch yet, but its flavor entry exists so
    # the extra gets the same self-heal treatment as every other mode.
    assert bootstrap.ORT_FLAVOR["intel_linux"] == (
        "onnxruntime-openvino",
        "OpenVINOExecutionProvider",
    )
    for mode, (package, provider) in bootstrap.ORT_FLAVOR.items():
        assert package.startswith("onnxruntime"), mode
        assert provider is None or provider.endswith("ExecutionProvider"), mode


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


class TestVerifyOrtFlavor:
    """verify_ort_flavor parses the live interpreter's provider list."""

    def _patch_ort(
        self, bootstrap, monkeypatch, stdout="", stderr="", returncode=0
    ):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(
                cmd, returncode, stdout=stdout, stderr=stderr
            )

        monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
        return calls

    def test_ok_when_required_provider_present(self, bootstrap, monkeypatch):
        self._patch_ort(
            bootstrap,
            monkeypatch,
            stdout="1.30.0\nCUDAExecutionProvider|CPUExecutionProvider\n",
        )
        ok, providers = bootstrap.verify_ort_flavor("nvidia_win")
        assert ok is True
        assert providers == ["CUDAExecutionProvider", "CPUExecutionProvider"]

    def test_failed_when_provider_missing(self, bootstrap, monkeypatch):
        self._patch_ort(
            bootstrap, monkeypatch, stdout="1.23.2\nCPUExecutionProvider\n"
        )
        ok, providers = bootstrap.verify_ort_flavor("windows_gpu")
        assert ok is False
        assert providers == ["CPUExecutionProvider"]

    def test_cpu_mode_needs_no_provider(self, bootstrap, monkeypatch):
        self._patch_ort(bootstrap, monkeypatch, stdout="1.30.0\nCPUExecutionProvider\n")
        ok, providers = bootstrap.verify_ort_flavor("cpu")
        assert ok is True
        assert providers == ["CPUExecutionProvider"]

    def test_import_failure_fails_closed(self, bootstrap, monkeypatch):
        self._patch_ort(
            bootstrap, monkeypatch, stderr="ModuleNotFoundError", returncode=1
        )
        ok, providers = bootstrap.verify_ort_flavor("nvidia_win")
        assert ok is False
        assert providers == []


class RecordingEnvManager:
    """Marker-matching EnvironmentManager stand-in recording writes."""

    def __init__(self, marker_matches: bool = False):
        self.marker_matches = marker_matches
        self.written: list = []

    def check_marker(self, hw_mode: str) -> bool:
        return self.marker_matches

    def write_marker(self, hw_mode: str):
        self.written.append(hw_mode)


async def _drive_ensure_ort_env(bootstrap, env_manager, hw_mode, extra, results):
    """Runs ensure_ort_env with recorded syncs and status messages."""
    sync_calls = []

    async def run_sync(cmd):
        sync_calls.append(cmd)
        return results.get("sync_ret", 0)

    statuses = []

    async def status(message):
        statuses.append(message)

    ok = await bootstrap.ensure_ort_env(
        env_manager, hw_mode, extra, run_sync, status
    )
    return ok, sync_calls, statuses


class TestEnsureOrtEnv:
    """Marker + live verification gate around uv sync (self-heal logic)."""

    def _noop_verify(self, bootstrap, monkeypatch, sequence):
        calls = []

        def fake_verify(hw_mode):
            calls.append(hw_mode)
            state = sequence.pop(0) if len(sequence) > 1 else sequence[0]
            return state

        monkeypatch.setattr(bootstrap, "verify_ort_flavor", fake_verify)
        return calls

    def test_marker_ok_and_verify_ok_skips_sync(self, bootstrap, monkeypatch):
        self._noop_verify(bootstrap, monkeypatch, [(True, ["CPUExecutionProvider"])])
        env = RecordingEnvManager(marker_matches=True)
        ok, sync_calls, statuses = asyncio.run(
            _drive_ensure_ort_env(
                bootstrap, env, "windows_gpu", "windows-gpu", {}
            )
        )
        assert ok is True
        assert sync_calls == []
        assert env.written == []
        assert any("skipping sync" in s for s in statuses)

    def test_matching_marker_but_verify_fail_triggers_sync(self, bootstrap, monkeypatch):
        """H1 self-heal: out-of-band venv mutation persists past the marker."""
        self._noop_verify(
            bootstrap, monkeypatch, [(False, ["CPUExecutionProvider"])]
        )
        env = RecordingEnvManager(marker_matches=True)
        ok, sync_calls, statuses = asyncio.run(
            _drive_ensure_ort_env(
                bootstrap, env, "windows_gpu", "windows-gpu", {}
            )
        )
        assert ok is False  # verification keeps failing after both syncs
        assert len(sync_calls) == 2
        assert sync_calls[0] == [
            bootstrap.UV_CMD,
            "sync",
            "--extra",
            "windows-gpu",
            "--reinstall-package",
            "onnxruntime-directml",
        ]
        assert env.written == []  # never verified good -> no marker
        assert any("re-syncing to self-heal" in s for s in statuses)
        assert any("ORT flavor verification failed" in s for s in statuses)

    def test_sync_success_with_verify_ok_writes_marker(self, bootstrap, monkeypatch):
        self._noop_verify(
            bootstrap,
            monkeypatch,
            [(True, ["DmlExecutionProvider", "CPUExecutionProvider"])],
        )
        env = RecordingEnvManager(marker_matches=False)
        ok, sync_calls, statuses = asyncio.run(
            _drive_ensure_ort_env(
                bootstrap, env, "windows_gpu", "windows-gpu", {}
            )
        )
        assert ok is True
        assert len(sync_calls) == 1
        assert sync_calls[0] == [
            bootstrap.UV_CMD,
            "sync",
            "--extra",
            "windows-gpu",
            "--reinstall-package",
            "onnxruntime-directml",
        ]
        assert env.written == ["windows_gpu"]

    def test_marker_match_then_sync_self_heals_and_writes_marker(
        self, bootstrap, monkeypatch
    ):
        """H1 full path: stale shadow exists despite matching marker, the
        re-sync restores the intended provider, marker re-recorded."""
        self._noop_verify(
            bootstrap,
            monkeypatch,
            [
                (False, ["CPUExecutionProvider"]),
                (True, ["DmlExecutionProvider", "CPUExecutionProvider"]),
            ],
        )
        env = RecordingEnvManager(marker_matches=True)
        ok, sync_calls, statuses = asyncio.run(
            _drive_ensure_ort_env(
                bootstrap, env, "windows_gpu", "windows-gpu", {}
            )
        )
        assert ok is True
        assert len(sync_calls) == 1  # one re-sync restores the intended flavor
        assert env.written == ["windows_gpu"]

    def test_sync_success_but_verify_fail_retries_without_marker(self, bootstrap, monkeypatch):
        """H2: same-sync ordering race -> verification fail is never marked 'success'."""
        self._noop_verify(
            bootstrap, monkeypatch, [(False, ["CPUExecutionProvider"])]
        )
        env = RecordingEnvManager(marker_matches=False)
        ok, sync_calls, statuses = asyncio.run(
            _drive_ensure_ort_env(
                bootstrap, env, "nvidia_win", "nvidia-win", {}
            )
        )
        assert ok is False
        assert len(sync_calls) == 2  # retry happened
        assert sync_calls[0][-1] == "onnxruntime-gpu"
        assert env.written == []  # marker NOT written despite sync success
        assert any("Retrying dependency sync" in s for s in statuses)

    def test_sync_failure_aborts_immediately(self, bootstrap, monkeypatch):
        self._noop_verify(
            bootstrap, monkeypatch, [(False, [])] * 3
        )
        env = RecordingEnvManager(marker_matches=False)
        ok, sync_calls, statuses = asyncio.run(
            _drive_ensure_ort_env(
                bootstrap, env, "cpu", "cpu", {"sync_ret": 1}
            )
        )
        assert ok is False
        assert len(sync_calls) == 1
        assert env.written == []
        assert any("Sync failed!" in s for s in statuses)
