import unittest
from unittest.mock import patch, MagicMock
from babelfish_stt.main import run_babelfish

class TestBabelfish(unittest.TestCase):
    @patch('babelfish_stt.main.get_gpu_info')
    @patch('babelfish_stt.main.STTEngine')
    @patch('babelfish_stt.main.AudioStreamer')
    @patch('babelfish_stt.main.TerminalDisplay')
    def test_run_babelfish(self, mock_display, mock_audio, mock_engine, mock_hardware):
        mock_hardware.return_value = {'cuda_available': True, 'name': 'Test GPU'}
        
        # Mock engine behavior
        mock_engine_instance = mock_engine.return_value
        mock_segment = MagicMock()
        mock_segment.text = "Test transcription"
        mock_engine_instance.transcribe_stream.return_value = [mock_segment]
        
        # Mock audio behavior - yield one chunk then stop
        mock_audio_instance = mock_audio.return_value
        mock_audio_instance.stream.return_value = iter([MagicMock()])
        
        # Run babelfish but simulate a KeyboardInterrupt after one iteration
        # We can do this by making the audio stream raise KeyboardInterrupt after one yield
        def audio_side_effect():
            yield MagicMock()
            raise KeyboardInterrupt()
        
        mock_audio_instance.stream.side_effect = audio_side_effect
        
        run_babelfish()
        
        # Verify orchestration
        mock_hardware.assert_called_once()
        mock_engine.assert_called_once_with(device="cuda")
        mock_audio.assert_called_once()
        mock_display.assert_called_once()
        
        # Verify transcription update
        mock_display.return_value.update.assert_called()
        mock_audio_instance.stop.assert_called_once()

if __name__ == '__main__':
    unittest.main()
