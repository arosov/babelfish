import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from babelfish_stt.pipeline import DoublePassPipeline

class TestE2ELogic(unittest.TestCase):
    def setUp(self):
        self.mock_vad = MagicMock()
        self.mock_engine = MagicMock()
        self.mock_display = MagicMock()
        
        self.pipeline = DoublePassPipeline(self.mock_vad, self.mock_engine, self.mock_display)

    def test_double_pass_logic_flow(self):
        # 1. Start speaking
        self.mock_vad.is_speech.return_value = True
        self.mock_engine.transcribe.return_value = "hello"
        
        # First chunk triggers ghost pass
        self.pipeline.process_chunk(np.zeros(512), now_ms=1000)
        
        self.mock_display.update.assert_called_with(refined="", ghost="hello")
        
        # 2. Trigger refinement (move time 3s)
        self.mock_engine.transcribe.return_value = "Hello world"
        self.pipeline.process_chunk(np.zeros(512), now_ms=4000)
        
        # Should have run anchor pass
        self.mock_engine.set_quality.assert_any_call('balanced')
        self.mock_display.update.assert_called_with(refined="Hello world")
        
        # 3. Next ghost pass should integrate with refined text
        self.mock_engine.transcribe.return_value = "how are you"
        self.pipeline.process_chunk(np.zeros(512), now_ms=4100)
        
        self.mock_display.update.assert_called_with(refined="Hello world", ghost="how are you")

    def test_finalize_logic(self):
        self.mock_vad.is_speech.return_value = True
        self.pipeline.process_chunk(np.zeros(512), now_ms=1000)
        
        # Stop speaking
        self.mock_vad.is_speech.return_value = False
        self.mock_engine.transcribe.return_value = "Finalized sentence."
        
        # Silence for 1s
        self.pipeline.process_chunk(np.zeros(512), now_ms=2100)
        
        self.mock_display.finalize.assert_called_with("Finalized sentence.")
        self.assertEqual(self.pipeline.refined_text, "")
        self.assertEqual(len(self.pipeline.active_ghost_buffer), 0)

if __name__ == '__main__':
    unittest.main()
