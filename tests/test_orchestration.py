import unittest
from unittest.mock import patch, MagicMock
import numpy as np

class TestOrchestration(unittest.TestCase):
    @patch('babelfish_stt.main.find_best_microphone')
    @patch('babelfish_stt.main.get_gpu_info')
    @patch('babelfish_stt.main.AudioStreamer')
    @patch('babelfish_stt.main.WakeWordEngine')
    @patch('babelfish_stt.main.STTEngine')
    @patch('babelfish_stt.main.SileroVAD')
    def test_orchestration_lifecycle(self, mock_vad, mock_stt, mock_ww, mock_streamer, mock_gpu, mock_mic):
        from babelfish_stt.main import run_babelfish
        
        # Setup mocks
        mock_gpu.return_value = {'cuda_available': False}
        mock_mic.return_value = 0
        
        streamer_inst = mock_streamer.return_value
        # Yield 3 chunks: 1. Silence, 2. WakeWord, 3. Speech
        chunk1 = np.zeros(512)
        chunk2 = np.ones(512) # Simulate wake word
        chunk3 = np.zeros(512) # Back to "listening" loop
        
        streamer_inst.stream.return_value = [chunk1, chunk2, chunk3]
        
        ww_inst = mock_ww.return_value
        # Prediction: first chunk 0, second chunk 1.0 (trigger), third chunk shouldn't be called for WW
        ww_inst.process_chunk.side_effect = [{"hey": 0.0}, {"hey": 1.0}]
        
        # Run orchestration with a wake word
        # We need to stop the loop after streamer is exhausted
        run_babelfish(wakeword="hey")
        
        # Verify WakeWordEngine was used for first two chunks
        self.assertEqual(ww_inst.process_chunk.call_count, 2)
        
        # Pipeline should NOT have been called for first two chunks (it was idle)
        # But should be called for the third chunk
        # Since run_babelfish initializes its own pipeline, we can't easily mock the instance, 
        # but we can verify STTEngine (used by pipeline) was called eventually
        # Actually, let's mock the pipeline classes in main.
        
    @patch('babelfish_stt.main.find_best_microphone')
    @patch('babelfish_stt.main.get_gpu_info')
    @patch('babelfish_stt.main.STTEngine')
    @patch('babelfish_stt.main.SinglePassPipeline')
    @patch('babelfish_stt.main.WakeWordEngine')
    @patch('babelfish_stt.main.AudioStreamer')
    def test_state_transition_call(self, mock_streamer, mock_ww, mock_pipeline, mock_stt, mock_gpu, mock_mic):
        from babelfish_stt.main import run_babelfish
        
        mock_gpu.return_value = {'cuda_available': False}
        mock_mic.return_value = 0
        
        streamer_inst = mock_streamer.return_value
        chunk1 = np.zeros(512)
        chunk2 = np.ones(512) # Wake word
        chunk3 = np.zeros(512) # Speech
        streamer_inst.stream.return_value = [chunk1, chunk2, chunk3]
        
        ww_inst = mock_ww.return_value
        ww_inst.process_chunk.side_effect = [{"hey": 0.0}, {"hey": 1.0}]
        
        pipe_inst = mock_pipeline.return_value
        pipe_inst.is_idle = True # Starts idle
        
        # We need to simulate the property change in the mock
        # When set_idle(False) is called, is_idle should become False
        def set_idle_mock(val):
            pipe_inst.is_idle = val
        pipe_inst.set_idle.side_effect = set_idle_mock
        
        run_babelfish(wakeword="hey")
        
        # pipe_inst.process_chunk should only be called once (for chunk3)
        self.assertEqual(pipe_inst.process_chunk.call_count, 1)
        # pipe_inst.set_idle(False) should have been called
        pipe_inst.set_idle.assert_called_with(False)

if __name__ == '__main__':
    unittest.main()
