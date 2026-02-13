"""Tests for wakeword_discovery module."""

import os
import tempfile
from pathlib import Path

import pytest

from babelfish_stt.wakeword_discovery import (
    CUSTOM_MODEL_SUFFIX,
    _extract_model_name,
    _sanitize_model_name,
    get_model_path,
    is_custom_model,
    scan_custom_models,
    strip_custom_suffix,
    validate_model_file,
)


class TestScanCustomModels:
    """Tests for scan_custom_models function."""

    def test_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_custom_models(tmpdir, "start")
            assert result == {}

    def test_nonexistent_directory(self):
        """Test scanning a non-existent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = os.path.join(tmpdir, "does_not_exist")
            result = scan_custom_models(nonexistent, "start")
            assert result == {}

    def test_single_model_onnx(self):
        """Test scanning with a single .onnx model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create structure: openwakeword_models/start/en/alexa/model.onnx
            model_dir = Path(tmpdir) / "openwakeword_models" / "start" / "en" / "alexa"
            model_dir.mkdir(parents=True)
            model_file = model_dir / "model.onnx"
            model_file.write_bytes(b"fake onnx content")

            result = scan_custom_models(tmpdir, "start")

            assert f"alexa{CUSTOM_MODEL_SUFFIX}" in result
            assert result[f"alexa{CUSTOM_MODEL_SUFFIX}"] == str(model_file)

    def test_single_model_tflite(self):
        """Test scanning with a single .tflite model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = (
                Path(tmpdir) / "openwakeword_models" / "start" / "en" / "test_model"
            )
            model_dir.mkdir(parents=True)
            model_file = model_dir / "test.tflite"
            model_file.write_bytes(b"fake tflite content")

            result = scan_custom_models(tmpdir, "start")

            assert f"test_model{CUSTOM_MODEL_SUFFIX}" in result

    def test_multiple_models_different_languages(self):
        """Test scanning with models in different language subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # English model
            en_dir = Path(tmpdir) / "openwakeword_models" / "start" / "en" / "hello"
            en_dir.mkdir(parents=True)
            en_file = en_dir / "hello.onnx"
            en_file.write_bytes(b"english model")

            # French model
            fr_dir = Path(tmpdir) / "openwakeword_models" / "start" / "fr" / "bonjour"
            fr_dir.mkdir(parents=True)
            fr_file = fr_dir / "bonjour.onnx"
            fr_file.write_bytes(b"french model")

            result = scan_custom_models(tmpdir, "start")

            assert f"hello{CUSTOM_MODEL_SUFFIX}" in result
            assert f"bonjour{CUSTOM_MODEL_SUFFIX}" in result
            assert result[f"hello{CUSTOM_MODEL_SUFFIX}"] == str(en_file)
            assert result[f"bonjour{CUSTOM_MODEL_SUFFIX}"] == str(fr_file)

    def test_start_and_stop_separation(self):
        """Test that start and stop models are scanned separately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Start model
            start_dir = Path(tmpdir) / "openwakeword_models" / "start" / "en" / "begin"
            start_dir.mkdir(parents=True)
            (start_dir / "begin.onnx").write_bytes(b"start")

            # Stop model
            stop_dir = Path(tmpdir) / "openwakeword_models" / "stop" / "en" / "end"
            stop_dir.mkdir(parents=True)
            (stop_dir / "end.onnx").write_bytes(b"stop")

            start_result = scan_custom_models(tmpdir, "start")
            stop_result = scan_custom_models(tmpdir, "stop")

            assert f"begin{CUSTOM_MODEL_SUFFIX}" in start_result
            assert f"end{CUSTOM_MODEL_SUFFIX}" not in start_result
            assert f"end{CUSTOM_MODEL_SUFFIX}" in stop_result
            assert f"begin{CUSTOM_MODEL_SUFFIX}" not in stop_result

    def test_ignores_invalid_extensions(self):
        """Test that non-model files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "openwakeword_models" / "start" / "en" / "test"
            model_dir.mkdir(parents=True)
            (model_dir / "readme.txt").write_text("This is a readme")
            (model_dir / "model.txt").write_text("Not a model")

            result = scan_custom_models(tmpdir, "start")

            assert result == {}

    def test_ignores_empty_files(self):
        """Test that empty model files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "openwakeword_models" / "start" / "en" / "empty"
            model_dir.mkdir(parents=True)
            (model_dir / "empty.onnx").write_bytes(b"")  # Empty file

            result = scan_custom_models(tmpdir, "start")

            assert result == {}


class TestValidateModelFile:
    """Tests for validate_model_file function."""

    def test_valid_file(self):
        """Test validation of a valid model file."""
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            f.write(b"valid content")
            tmp_path = f.name

        try:
            assert validate_model_file(tmp_path) is True
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file(self):
        """Test validation of a non-existent file."""
        assert validate_model_file("/path/to/nonexistent.onnx") is False

    def test_empty_file(self):
        """Test validation of an empty file."""
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            f.write(b"")
            tmp_path = f.name

        try:
            assert validate_model_file(tmp_path) is False
        finally:
            os.unlink(tmp_path)


class TestExtractModelName:
    """Tests for _extract_model_name function."""

    def test_from_subdirectory(self):
        """Test extracting name from subdirectory structure."""
        base_dir = Path("/app/openwakeword_models/start")
        model_file = Path("/app/openwakeword_models/start/en/alexa/model.onnx")

        result = _extract_model_name(model_file, base_dir)

        assert result == "alexa"

    def test_deeply_nested(self):
        """Test extracting name from deeply nested structure."""
        base_dir = Path("/app/openwakeword_models/start")
        model_file = Path(
            "/app/openwakeword_models/start/en/us/california/hey_jarvis/model.onnx"
        )

        result = _extract_model_name(model_file, base_dir)

        # Should use the immediate parent directory name
        assert result == "hey_jarvis"

    def test_direct_in_base(self):
        """Test extracting name when file is directly in base directory."""
        base_dir = Path("/app/openwakeword_models/start")
        model_file = Path("/app/openwakeword_models/start/my_model.onnx")

        result = _extract_model_name(model_file, base_dir)

        assert result == "my_model"


class TestSanitizeModelName:
    """Tests for _sanitize_model_name function."""

    def test_removes_asterisk(self):
        """Test that asterisk suffix is removed."""
        assert _sanitize_model_name("model*") == "model"

    def test_replaces_spaces(self):
        """Test that spaces are replaced with underscores."""
        assert _sanitize_model_name("my model") == "my_model"

    def test_replaces_special_chars(self):
        """Test that special characters are replaced."""
        assert _sanitize_model_name("model@v1.0") == "model_v1_0"

    def test_keeps_valid_chars(self):
        """Test that valid characters are preserved."""
        assert _sanitize_model_name("my_model-123") == "my_model-123"

    def test_trims_underscores(self):
        """Test that leading/trailing underscores are trimmed."""
        assert _sanitize_model_name("_model_") == "model"


class TestModelPathHelpers:
    """Tests for helper functions."""

    def test_is_custom_model(self):
        """Test is_custom_model function."""
        assert is_custom_model("model*") is True
        assert is_custom_model("model") is False
        assert is_custom_model("*model") is False

    def test_strip_custom_suffix(self):
        """Test strip_custom_suffix function."""
        assert strip_custom_suffix("model*") == "model"
        assert strip_custom_suffix("model") == "model"
        assert strip_custom_suffix("model**") == "model"

    def test_get_model_path(self):
        """Test get_model_path function."""
        custom_models = {
            "model*": "/path/to/model.onnx",
            "other*": "/path/to/other.onnx",
        }

        assert get_model_path("model*", custom_models) == "/path/to/model.onnx"
        assert get_model_path("model", custom_models) == "/path/to/model.onnx"
        assert get_model_path("nonexistent", custom_models) is None


class TestExcludedWakeWords:
    """Tests for excluded wake words functionality."""

    def test_excluded_wakewords_constant(self):
        """Test that excluded wake words constant exists and contains expected values."""
        from babelfish_stt.wakeword_discovery import EXCLUDED_WAKEWORDS

        assert "timer" in EXCLUDED_WAKEWORDS
        assert "weather" in EXCLUDED_WAKEWORDS
