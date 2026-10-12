"""Tests for scripts/bootstrap.py (ADR 0006: babelfish owns its bootstrap).

The bootstrap is a self-contained script (it runs before the project venv
exists), so it is imported here directly from its path.
"""

import importlib.util
import asyncio
import json
import logging
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


def test_standalone_launch_has_no_server_flags(bootstrap, monkeypatch):
    monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, env = plan.build("nvidia_win", ["--type"])
    assert "--server" not in args
    assert "--port" not in args
    assert args[1:4] == ["run", "--no-sync", "babelfish"]
    assert args[4:] == ["--type"]
    assert env["PATH"] == "/fake"


def test_driven_launch_has_server_flags(bootstrap, monkeypatch):
    monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
    monkeypatch.setattr(bootstrap, "DRIVEN", True)
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


def test_gpu_mode_without_force_has_no_cpu_flag(bootstrap, monkeypatch):
    monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, _ = plan.build("nvidia_win")
    assert "--cpu" not in args


def test_fresh_config_gpu_launch_appends_cpu(bootstrap, monkeypatch):
    """ADR 0014: with no config file at all, the machine default device is
    cpu — the launch rides --cpu even when a GPU wheel happens to be synced
    (an existing config may have synced GPU flavors; the fresh default is
    still CPU, and the launch flag must agree with it)."""
    plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
    args, _ = plan.build("windows_gpu")
    assert "--cpu" in args


class TestHardwareDetectorModes:
    """Windows defaults to DirectML; CUDA is an explicit opt-in. On Linux the
    CUDA flavor is only synced when an NVIDIA GPU is actually detected."""

    def _detector(self, bootstrap, monkeypatch, platform="win32", nvidia=False, gpus=()):
        """Builds a HardwareDetector with faked platform + detection."""

        class _FakeSys:
            stderr = sys.stderr

            def __init__(self):
                self.platform = platform

        monkeypatch.setattr(bootstrap, "sys", _FakeSys())
        monkeypatch.setattr(
            bootstrap.HardwareDetector, "detect_nvidia", lambda *args: nvidia
        )
        monkeypatch.setattr(bootstrap.HardwareDetector, "detect_metal", lambda s: False)
        monkeypatch.setattr(bootstrap.HardwareDetector, "get_all_gpus", lambda s: list(gpus))
        return bootstrap.HardwareDetector()

    def test_fresh_config_defaults_to_cpu_even_with_nvidia(
        self, bootstrap, monkeypatch
    ):
        # No config file: 'auto' migrates to the platform default, which is
        # 'cpu' on every platform now (ADR 0014) — even an NVIDIA machine
        # starts on CPU with the redux card, GPUs are opt-in.
        detector = self._detector(bootstrap, monkeypatch, platform="win32", nvidia=True, gpus=["NVIDIA GPU"])
        hw = detector.get_best_mode()
        assert hw == {
            "hw_mode": "cpu",
            "extra": "cpu",
            "desc": "CPU",
        }

    def test_nvidia_windows_cuda_config_uses_nvidia_win(self, bootstrap, monkeypatch):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda:0")
        detector = self._detector(bootstrap, monkeypatch, platform="win32", nvidia=True, gpus=["NVIDIA GPU"])
        hw = detector.get_best_mode()
        assert hw == {
            "hw_mode": "nvidia_win",
            "extra": "nvidia-win",
            "desc": "NVIDIA GPU (CUDA)",
        }

    def test_nvidia_dml_config_uses_windows_gpu(self, bootstrap, monkeypatch):
        monkeypatch.setattr(
            bootstrap, "_read_config_device", lambda: "dml:0"
        )
        detector = self._detector(bootstrap, monkeypatch, platform="win32", nvidia=True, gpus=["NVIDIA GPU"])
        hw = detector.get_best_mode()
        assert hw["extra"] == "windows-gpu"
        assert "DirectML" in hw["desc"]

    def test_windows_cpu_config_gets_the_cpu_flavor(self, bootstrap, monkeypatch):
        # ADR 0014: the device decides the flavor (D1) — a cpu config syncs
        # the small plain onnxruntime wheel; no GPU env is spun up.
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cpu")
        detector = self._detector(bootstrap, monkeypatch, platform="win32", nvidia=False, gpus=[])
        hw = detector.get_best_mode()
        assert hw == {"hw_mode": "cpu", "extra": "cpu", "desc": "CPU"}

    def test_windows_cuda_config_without_nvidia_warns_but_honors_request(
        self, bootstrap, monkeypatch, caplog
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
        detector = self._detector(bootstrap, monkeypatch, platform="win32", nvidia=False, gpus=[])
        with caplog.at_level(logging.WARNING, logger="babelfish_bootstrap"):
            hw = detector.get_best_mode()
        assert hw["extra"] == "nvidia-win"
        assert any("no NVIDIA GPU was detected" in r.message for r in caplog.records)

    def test_windows_legacy_rocm_config_migrates_to_platform_default(
        self, bootstrap, monkeypatch, caplog
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "rocm:0")
        detector = self._detector(bootstrap, monkeypatch, platform="win32", nvidia=False, gpus=[])
        with caplog.at_level(logging.INFO, logger="babelfish_bootstrap"):
            hw = detector.get_best_mode()
        assert hw["extra"] == "cpu"
        assert any("Migrating legacy device 'rocm:0' → 'cpu'" in r.message for r in caplog.records)

    def test_linux_nvidia_defaults_to_cuda(self, bootstrap, monkeypatch):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
        detector = self._detector(bootstrap, monkeypatch, platform="linux", nvidia=True)
        hw = detector.get_best_mode()
        assert hw == {
            "hw_mode": "nvidia_linux",
            "extra": "nvidia-linux",
            "desc": "NVIDIA GPU",
        }

    def test_linux_without_nvidia_defaults_to_cpu(self, bootstrap, monkeypatch):
        detector = self._detector(bootstrap, monkeypatch, platform="linux", nvidia=False, gpus=["AMD GPU"])
        hw = detector.get_best_mode()
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"

    def test_linux_cuda_config_without_nvidia_syncs_cpu_flavor(
        self, bootstrap, monkeypatch, caplog
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda:0")
        detector = self._detector(bootstrap, monkeypatch, platform="linux", nvidia=False)
        with caplog.at_level(logging.WARNING, logger="babelfish_bootstrap"):
            hw = detector.get_best_mode()
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"
        assert any("will degrade to CPU" in r.message for r in caplog.records)

    def test_linux_dml_config_is_invalid_and_falls_back_to_cpu(
        self, bootstrap, monkeypatch, caplog
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "dml:1")
        detector = self._detector(bootstrap, monkeypatch, platform="linux", nvidia=True)
        with caplog.at_level(logging.WARNING, logger="babelfish_bootstrap"):
            hw = detector.get_best_mode()
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"
        assert any("invalid on Linux" in r.message for r in caplog.records)

    def test_no_gpu_falls_back_to_cpu(self, bootstrap, monkeypatch):
        # On Linux there is no DirectML fallback: without an NVIDIA driver
        # the CPU flavor is synced. (Windows always syncs windows-gpu — see
        # test_windows_cpu_config_still_syncs_windows_gpu.)
        detector = self._detector(bootstrap, monkeypatch, platform="linux", nvidia=False, gpus=())
        hw = detector.get_best_mode()
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"


def _detector_for(bootstrap, monkeypatch, platform="win32", nvidia=True, gpus=("NVIDIA GPU",)):
    """Builds a HardwareDetector with faked platform + detection."""
    class _FakeSys:
        stderr = sys.stderr

        def __init__(self):
            self.platform = platform

    monkeypatch.setattr(bootstrap, "sys", _FakeSys())
    monkeypatch.setattr(bootstrap.HardwareDetector, "detect_nvidia", lambda *args: nvidia)
    monkeypatch.setattr(bootstrap.HardwareDetector, "detect_metal", lambda *args: False)
    monkeypatch.setattr(bootstrap.HardwareDetector, "get_all_gpus", lambda s: list(gpus))
    return bootstrap.HardwareDetector()


class TestForcedCpuCoherence:
    """ADR 0014 Phase A: VOGON_FORCE_CPU / --cpu are honored by EVERY layer.

    A forced-CPU run must route detection to CPU mode — zero GPU flavor
    sync, zero GPU provisioning — even when the config still says cuda.
    This is the observed layering anomaly (GPU environment around a CPU
    inference), now closed."""

    def test_env_force_routes_cuda_config_to_cpu_mode(
        self, bootstrap, monkeypatch, caplog
    ):
        monkeypatch.setenv("VOGON_FORCE_CPU", "1")
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
        detector = _detector_for(bootstrap, monkeypatch, platform="win32")
        with caplog.at_level(logging.INFO, logger="babelfish_bootstrap"):
            hw = detector.get_best_mode()
        assert hw == {"hw_mode": "cpu", "extra": "cpu", "desc": "CPU"}
        assert any(
            "Effective device: cpu (config says cuda" in r.message
            for r in caplog.records
        )

    def test_cpu_cli_passthrough_routes_cuda_config_to_cpu_mode(
        self, bootstrap, monkeypatch
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
        detector = _detector_for(bootstrap, monkeypatch, platform="win32")
        hw = detector.get_best_mode(passthrough=["--cpu", "--type"])
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"

    def test_linux_cuda_config_with_env_force_skips_nvidia_linux(
        self, bootstrap, monkeypatch
    ):
        monkeypatch.setenv("VOGON_FORCE_CPU", "1")
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
        detector = _detector_for(bootstrap, monkeypatch, platform="linux", nvidia=True)
        hw = detector.get_best_mode()
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"

    def test_pure_cpu_config_gets_the_cpu_flavor(self, bootstrap, monkeypatch):
        """Phase-B refinement of the Phase-A gate: the device decides the
        flavor (D1), so a config that says "cpu" now syncs the plain CPU
        wheel — below the anomaly fix, this is the consistent endpoint."""
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cpu")
        detector = _detector_for(bootstrap, monkeypatch, platform="win32", nvidia=False, gpus=[])
        hw = detector.get_best_mode()
        assert hw == {"hw_mode": "cpu", "extra": "cpu", "desc": "CPU"}

    def test_launch_plan_cpu_passthrough_appends_cpu_once(
        self, bootstrap, monkeypatch
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
        plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
        args, _ = plan.build("nvidia_win", ["--cpu"])
        assert args.count("--cpu") == 1

    def test_launch_plan_cpu_passthrough_without_cpu_config(
        self, bootstrap, monkeypatch
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cuda")
        plan = bootstrap.HardwareLaunchPlan(FakeEnvManager())
        args, _ = plan.build("nvidia_win", ["--type"])
        assert "--cpu" not in args
        assert "--type" in args

    def test_gpu_cli_passthrough_selects_best_detected_backend(
        self, bootstrap, monkeypatch
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cpu")
        detector = _detector_for(bootstrap, monkeypatch, platform="win32", nvidia=True)
        hw = detector.get_best_mode(passthrough=["--gpu"])
        assert hw["hw_mode"] == "nvidia_win"

    def test_gpu_cli_passthrough_without_gpu_stays_cpu(
        self, bootstrap, monkeypatch
    ):
        monkeypatch.setattr(bootstrap, "_read_config_device", lambda: "cpu")
        detector = _detector_for(
            bootstrap, monkeypatch, platform="win32", nvidia=False, gpus=[]
        )
        hw = detector.get_best_mode(passthrough=["--gpu"])
        assert hw["hw_mode"] == "cpu"
        assert hw["extra"] == "cpu"


class TestWeightsCard:
    """ADR 0014: provisioning is device-keyed — cpu resolves the Redux int4
    card (pinned repo revision, exactly 4 files), GPU backends keep fp32 v3 —
    with config hardware.model as the explicit card override."""

    def test_cpu_card_is_redux(self, bootstrap):
        card = bootstrap._weights_card("cpu")
        assert card["card"] == "cpu"
        assert card["dir_name"] == "nemo-parakeet-tdt-0.6b-v3-redux"
        assert card["repo"] == "eschmidbauer/parakeet-redux-onnx"
        assert card["revision"] == bootstrap.MODEL_REPO_CPU_REVISION
        assert sorted(card["patterns"]) == [
            "config.json",
            "decoder_joint-model.onnx",
            "encoder-model.onnx",
            "vocab.txt",
        ]

    def test_gpu_card_is_fp32_v3(self, bootstrap):
        for device in ("cuda:0", "dml:0", "openvino:GPU.0"):
            card = bootstrap._weights_card(device)
            assert card["card"] == "gpu", device
            assert card["dir_name"] == "nemo-parakeet-tdt-0.6b-v3"
            assert card["repo"] == "istupakov/parakeet-tdt-0.6b-v3-onnx"
            assert card["revision"] is None
            assert card["patterns"] == [
                "encoder-model.onnx",
                "decoder_joint-model.onnx",
                "encoder-model.onnx.data",
                "config.json",
                "vocab.txt",
            ]

    def test_config_model_override_forces_the_card(
        self, bootstrap, monkeypatch, tmp_path
    ):
        (tmp_path / "babelfish.config.json").write_text(
            json.dumps({"hardware": {"device": "cpu", "model": "v3"}})
        )
        card = bootstrap._weights_card("cpu")
        assert card["card"] == "gpu"

        (tmp_path / "babelfish.config.json").write_text(
            json.dumps({"hardware": {"device": "cuda", "model": "redux"}})
        )
        card = bootstrap._weights_card("cuda")
        assert card["card"] == "cpu"

    def test_models_dir_resolution_follows_device(
        self, bootstrap, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("VOGON_APP_CACHE_DIR", str(tmp_path / "cache"))
        cpu_dir = bootstrap._resolve_models_dir(None, "cpu")
        assert cpu_dir == tmp_path / "cache" / "models" / "nemo-parakeet-tdt-0.6b-v3-redux"
        gpu_dir = bootstrap._resolve_models_dir(None, "cuda:0")
        assert gpu_dir == tmp_path / "cache" / "models" / "nemo-parakeet-tdt-0.6b-v3"
        explicit = bootstrap._resolve_models_dir("C:/vp_models", "gpu")
        assert explicit == Path("C:/vp_models") / "nemo-parakeet-tdt-0.6b-v3"

    def test_run_redux_launcher_compatibility_names(self, bootstrap):
        """scripts/run_redux.py keyed off the historical constants; both
        names keep their old values as GPU-card aliases."""
        assert bootstrap.MODEL_DIR_NAME == "nemo-parakeet-tdt-0.6b-v3"
        assert bootstrap.MODEL_REPO == "istupakov/parakeet-tdt-0.6b-v3-onnx"


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
