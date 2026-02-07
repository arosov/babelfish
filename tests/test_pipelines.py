import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from babelfish_stt.pipeline import SinglePassPipeline, DoublePassPipeline

class TestPipelines(unittest.TestCase):
    def setUp(self):
        self.mock_vad = MagicMock()
        self.mock_engine = MagicMock()
        self.mock_display = MagicMock()
        
    def test_single_pass_pipeline_init(self):
        pipeline = SinglePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        self.assertIsNotNone(pipeline)

    def test_double_pass_pipeline_init(self):
        pipeline = DoublePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        self.assertIsNotNone(pipeline)

    def test_single_pass_process_chunk_speech(self):
        pipeline = SinglePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        self.mock_vad.is_speech.return_value = True
        chunk = np.zeros(512, dtype=np.float32)
        
        # Should not raise
        pipeline.process_chunk(chunk, now_ms=1000)
        
    def test_double_pass_process_chunk_speech(self):
        pipeline = DoublePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        self.mock_vad.is_speech.return_value = True
        chunk = np.zeros(512, dtype=np.float32)
        
        # Should not raise
        pipeline.process_chunk(chunk, now_ms=1000)

    @patch('time.time')
    def test_double_pass_catch_up_simulation(self, mock_time):
        # This test ensures that if one process_chunk takes long, 
        # subsequent calls with accumulated chunks work.
        pipeline = DoublePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        self.mock_vad.is_speech.return_value = True
        self.mock_engine.transcribe.return_value = "Test"
        
        # 1. First chunk triggers a ghost pass
        pipeline.process_chunk(np.zeros(512), now_ms=1000)
        self.assertEqual(self.mock_engine.transcribe.call_count, 1)
        
        # 2. Simulate a long delay in the next processing (e.g. anchor pass)
        # We'll force a trigger by moving time forward by 3000ms
        pipeline.trigger.start_speech(1000)
        pipeline.process_chunk(np.zeros(512), now_ms=4000)
        
        # Verify it switched to balanced and transcribed
        self.mock_engine.set_quality.assert_any_call('balanced')
        self.mock_engine.set_quality.assert_any_call('realtime')
        
if __name__ == '__main__':
    unittest.main()
