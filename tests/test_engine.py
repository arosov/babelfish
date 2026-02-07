import unittest
from unittest.mock import patch, MagicMock
import torch
import numpy as np
from babelfish_stt.engine import STTEngine

class TestEngine(unittest.TestCase):
    @patch('babelfish_stt.engine.StreamingTranscriber')
    @patch('babelfish_stt.engine.TranscriberConfig')
    def test_engine_initialization(self, mock_config, mock_transcriber):
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        
        engine = STTEngine(device="cpu")
        
        # Verify config created with fast preset parameters
        mock_config.assert_called_once()
        args, kwargs = mock_config.call_args
        self.assertEqual(kwargs['chunk_secs'], 1.0)
        self.assertEqual(kwargs['device'], "cpu")
        
        # Verify transcriber created with config and device
        mock_transcriber.assert_called_once_with(
            model_name="nvidia/parakeet-tdt-0.6b-v3",
            device="cpu",
            config=mock_config_instance
        )
        self.assertEqual(engine.transcriber, mock_transcriber.return_value)

    @patch('babelfish_stt.engine.StreamingTranscriber')
    @patch('babelfish_stt.engine.TranscriberConfig')
    def test_transcribe_stream(self, mock_config, mock_transcriber):
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        engine = STTEngine(device="cpu")
        mock_audio = MagicMock()
        
        # Mock stream to return an iterator
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_transcriber.return_value.stream.return_value = [mock_segment]
        
        results = list(engine.transcribe_stream(mock_audio))
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].text, "Hello world")
        
        # The mock_audio should have been moved to the device from config
        mock_audio.to.assert_called_once_with(mock_config_instance.device)
        mock_transcriber.return_value.stream.assert_called_once_with(mock_audio.to.return_value)

if __name__ == '__main__':
    unittest.main()
