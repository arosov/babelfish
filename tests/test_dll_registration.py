import os
import sys
from pathlib import Path

import pytest

from babelfish_stt import hardware


@pytest.fixture(autouse=True)
def reset_registration_flag():
    """Keeps the module-global idempotence flag from leaking between tests."""
    hardware._dll_dirs_registered = False
    yield
    hardware._dll_dirs_registered = False


@pytest.fixture
def fake_site(tmp_path):
    """A fake site-packages carrying an ORT capi dir and pip NVIDIA DLL dirs."""
    sp = tmp_path / "site-packages"
    (sp / "onnxruntime" / "capi").mkdir(parents=True)
    (sp / "nvidia" / "cublas" / "bin").mkdir(parents=True)
    (sp / "nvidia" / "cudnn" / "bin").mkdir(parents=True)
    (sp / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll").touch()
    (sp / "nvidia" / "cublas" / "bin" / "cublas64_12.dll").touch()
    (sp / "nvidia" / "cudnn" / "bin" / "cudnn64_9.dll").touch()
    # A stray non-bin dir must be picked up too (mirrors the bootstrap's
    # rglob over every *.dll parent), and nested DLL parents deduped.
    nested = sp / "nvidia" / "cublas" / "bin" / "nested"
    nested.mkdir(parents=True)
    (nested / "extra.dll").touch()
    return sp


def test_collect_ort_dll_dirs(fake_site):
    dirs = hardware._collect_ort_dll_dirs([fake_site])

    assert dirs[0] == str(fake_site / "onnxruntime" / "capi")
    assert str(fake_site / "nvidia" / "cublas" / "bin") in dirs
    assert str(fake_site / "nvidia" / "cudnn" / "bin") in dirs
    assert str(fake_site / "nvidia" / "cublas" / "bin" / "nested") in dirs
    # No duplicates
    assert len(dirs) == len(set(dirs))
    # capi comes first (ORT bridge resolution)
    assert dirs.index(str(fake_site / "onnxruntime" / "capi")) == 0


def test_collect_ort_dll_dirs_dedupes_shared_roots(tmp_path):
    sp = tmp_path / "site-packages"
    (sp / "onnxruntime" / "capi").mkdir(parents=True)
    (sp / "onnxruntime" / "capi" / "onnxruntime.dll").touch()
    (sp / "nvidia" / "cublas" / "bin").mkdir(parents=True)
    (sp / "nvidia" / "cublas" / "bin" / "cublas.dll").touch()
    (sp / "nvidia" / "cublas2" / "bin").mkdir(parents=True)
    (sp / "nvidia" / "cublas2" / "bin" / "cublas.dll").touch()

    dirs = hardware._collect_ort_dll_dirs([sp, sp])  # same root twice
    assert len(dirs) == 3


def test_register_skips_when_no_dirs(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(hardware, "_candidate_site_packages", lambda: [empty])

    assert hardware.register_nvidia_dll_dirs() == []


def test_register_prepends_env_var(fake_site, monkeypatch):
    monkeypatch.setattr(hardware, "_candidate_site_packages", lambda: [fake_site])
    if sys.platform == "win32":
        env_var = "PATH"
        separator = ";"
    else:
        env_var = "LD_LIBRARY_PATH"
        separator = ":"

    monkeypatch.setenv(env_var, "original_entry")
    registered = hardware.register_nvidia_dll_dirs()

    assert registered, "expected dirs to be registered"
    value = os.environ[env_var]
    for d in registered:
        assert d in value
    assert value.endswith(separator + "original_entry")


def test_register_is_idempotent(fake_site, monkeypatch):
    monkeypatch.setattr(hardware, "_candidate_site_packages", lambda: [fake_site])
    first = hardware.register_nvidia_dll_dirs()
    second = hardware.register_nvidia_dll_dirs()
    assert first
    assert second == []
