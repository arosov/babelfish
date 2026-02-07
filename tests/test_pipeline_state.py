import unittest
from unittest.mock import MagicMock
import numpy as np
from babelfish_stt.pipeline import SinglePassPipeline, DoublePassPipeline, StopWordDetector

class TestPipelineState(unittest.TestCase):
    def setUp(self):
        self.mock_vad = MagicMock()
        self.mock_engine = MagicMock()
        self.mock_display = MagicMock()
        
    def test_pipeline_idle_state(self):
        pipeline = SinglePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        pipeline.set_idle(True)
        self.assertTrue(pipeline.is_idle)
        
        chunk = np.zeros(512, dtype=np.float32)
        # In idle state, it should return False (no transition) and not call engine
        result = pipeline.process_chunk(chunk, now_ms=1000)
        self.assertFalse(result)
        self.mock_engine.transcribe.assert_not_called()

    def test_pipeline_stop_word_trigger(self):
        # Setup detector
        detector = StopWordDetector(stop_words=["stop"])
        pipeline = SinglePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        pipeline.stop_detector = detector
        
        self.assertFalse(pipeline.is_idle)
        
        # Simulate speech
        self.mock_vad.is_speech.return_value = True
        self.mock_engine.transcribe.return_value = "please stop"
        
        chunk = np.zeros(3200, dtype=np.float32) # Enough to trigger update
        result = pipeline.process_chunk(chunk, now_ms=1000)
        
        # Should detect stop word, set idle to True, and return True
        self.assertTrue(result)
        self.assertTrue(pipeline.is_idle)
        self.mock_display.update.assert_called()

    def test_double_pass_stop_word_trigger_anchor(self):
        detector = StopWordDetector(stop_words=["stop"])
        pipeline = DoublePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        pipeline.stop_detector = detector
        
        # Simulate speech that triggers anchor pass
        self.mock_vad.is_speech.return_value = True
        self.mock_engine.transcribe.return_value = "okay stop"
        
        # Manually trigger anchor pass
        result = pipeline._run_anchor_pass(now_ms=1000)
        
        self.assertTrue(result)
        self.assertTrue(pipeline.is_idle)
        self.mock_display.update.assert_called()

    def test_double_pass_stop_word_trigger_ghost(self):
        detector = StopWordDetector(stop_words=["stop"])
        pipeline = DoublePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        pipeline.stop_detector = detector
        
        # Setup ghost pass context
        pipeline.active_ghost_buffer = [np.zeros(1600)]
        self.mock_engine.transcribe.return_value = "stop"
        
        # Manually trigger ghost pass
        result = pipeline._run_ghost_pass()
        
        self.assertTrue(result)
        self.assertTrue(pipeline.is_idle)
        self.mock_display.update.assert_called()

    def test_double_pass_integrated_stop(self):
        detector = StopWordDetector(stop_words=["stop"])
        pipeline = DoublePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)
        pipeline.stop_detector = detector
        
        # Simulate speech that triggers a ghost pass in process_chunk
        self.mock_vad.is_speech.return_value = True
        self.mock_engine.transcribe.return_value = "stop"
        
        chunk = np.zeros(512)
        result = pipeline.process_chunk(chunk, now_ms=1000)
        
        self.assertTrue(result)
        self.assertTrue(pipeline.is_idle)

if __name__ == '__main__':
    unittest.main()
