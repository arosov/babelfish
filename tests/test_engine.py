import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from babelfish_stt.engine import STTEngine

class TestEngine(unittest.TestCase):
    @patch('babelfish_stt.engine.Parakeet')
    def test_engine_initialization(self, mock_parakeet):
        engine = STTEngine(device="cpu")
        
        # Verify Parakeet initialized with correct parameters
        mock_parakeet.assert_called_once_with(
            model_name="nvidia/parakeet-tdt-0.6b-v3",
            device="cpu",
            config='realtime'
        )
        self.assertEqual(engine.pk, mock_parakeet.return_value)

    @patch('babelfish_stt.engine.Parakeet')
    def test_transcribe(self, mock_parakeet):
        engine = STTEngine(device="cpu")
        mock_audio = np.zeros(16000, dtype=np.float32)
        
        # Mock parakeet result
        mock_result = MagicMock()
        mock_result.text = "Hello world"
        mock_parakeet.return_value.transcribe.return_value = mock_result
        
        text = engine.transcribe(mock_audio)
        
        self.assertEqual(text, "Hello world")
        mock_parakeet.return_value.transcribe.assert_called_once_with(mock_audio, _quiet=True)

    @patch('babelfish_stt.engine.Parakeet')
    def test_transcribe_empty(self, mock_parakeet):
        engine = STTEngine(device="cpu")
        text = engine.transcribe(np.array([]))
        self.assertEqual(text, "")
        mock_parakeet.return_value.transcribe.assert_not_called()

if __name__ == '__main__':
    unittest.main()