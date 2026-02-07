import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import logging

class TestE2EVoiceControl(unittest.TestCase):
    @patch('babelfish_stt.main.find_best_microphone')
    @patch('babelfish_stt.main.get_gpu_info')
    @patch('babelfish_stt.main.AudioStreamer')
    @patch('babelfish_stt.main.WakeWordEngine')
    @patch('babelfish_stt.main.STTEngine')
    @patch('babelfish_stt.main.TerminalDisplay')
    @patch('babelfish_stt.main.SileroVAD')
    def test_full_lifecycle_logging(self, mock_vad, mock_display, mock_stt, mock_ww, mock_streamer, mock_gpu, mock_mic):
        from babelfish_stt.main import run_babelfish
        
        # Setup hardware mocks
        mock_gpu.return_value = {'cuda_available': False}
        mock_mic.return_value = 0
        
        # 1. Setup Streamer to yield a sequence of chunks
        streamer_inst = mock_streamer.return_value
        # SinglePassPipeline update_interval_samples = 3200
        # We need to yield enough samples in chunk 2 to trigger an engine.transcribe call
        chunk_idle = np.zeros(512)
        chunk_wake = np.zeros(512)
        chunk_speech = np.zeros(4000) # > 3200 to trigger update
        chunk_final = np.zeros(512)
        
        streamer_inst.stream.return_value = [chunk_idle, chunk_wake, chunk_speech, chunk_final]
        
        # 2. Setup WakeWordEngine
        ww_inst = mock_ww.return_value
        ww_inst.process_chunk.side_effect = [
            {"hey": 0.1}, 
            {"hey": 0.9},
            {"hey": 0.1},
            {"hey": 0.1}
        ]
        
        # 3. Setup STT Engine
        stt_inst = mock_stt.return_value
        stt_inst.transcribe.return_value = "please stop"
        
        # 4. Mock VAD to always return true for speech so it triggers the update logic
        mock_vad.return_value.is_speech.return_value = True
        with self.assertLogs(level='INFO') as cm:
            run_babelfish(wakeword="hey", stopword="stop")
            
            # Verify logs contain expected transitions
            log_output = "\n".join(cm.output)
            self.assertIn("Wake-word 'hey' detected with score 0.90", log_output)
            self.assertIn("Stop-word 'stop' detected, transitioning to IDLE", log_output)

if __name__ == '__main__':
    unittest.main()