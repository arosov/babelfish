import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from babelfish_stt.engine import STTEngine
from babelfish_stt.config import BabelfishConfig, HardwareConfig


class TestEngine(unittest.TestCase):
    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_engine_initialization(self, mock_mem, mock_load):
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        engine = STTEngine(config=config)

        # Verify onnx_asr initialized
        mock_load.assert_called_once()
        self.assertEqual(engine.model, mock_load.return_value)

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_transcribe(self, mock_mem, mock_load):
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        engine = STTEngine(config=config)
        mock_audio = np.zeros(16000, dtype=np.float32)

        # Mock model result
        mock_load.return_value.recognize.return_value = "Hello world"

        text = engine.transcribe(mock_audio)

        self.assertEqual(text, "Hello world")
        # recognizer called with padded audio (2s default padding)
        # min_samples = 2.0 * 16000 = 32000
        # original 16000 + 16000 zeros
        args, kwargs = mock_load.return_value.recognize.call_args
        self.assertEqual(len(args[0]), 32000)

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_transcribe_empty(self, mock_mem, mock_load):
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        engine = STTEngine(config=config)
        text = engine.transcribe(np.array([]))
        self.assertEqual(text, "")
        mock_load.return_value.recognize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
