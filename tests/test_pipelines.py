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

if __name__ == '__main__':
    unittest.main()
