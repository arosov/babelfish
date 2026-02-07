import unittest
from babelfish_stt.pipeline import HybridTrigger, AlignmentManager

class TestPipelineComponents(unittest.TestCase):
    def test_hybrid_trigger(self):
        trigger = HybridTrigger(interval_ms=1000)
        self.assertFalse(trigger.should_trigger(500, True))
        
        trigger.start_speech(100)
        self.assertTrue(trigger.is_speaking)
        
        # Test interval trigger
        self.assertTrue(trigger.should_trigger(1200, True))
        
        # Test VAD pause trigger
        trigger.reset(1000)
        self.assertTrue(trigger.should_trigger(1100, False))
        
        trigger.stop_speech()
        self.assertFalse(trigger.is_speaking)
        self.assertFalse(trigger.should_trigger(2000, True))

    def test_alignment_manager(self):
        am = AlignmentManager(context_words=2)
        self.assertEqual(am.get_prefix_context("hello world"), "hello world")
        self.assertEqual(am.get_prefix_context("this is a test"), "a test")
        self.assertEqual(am.get_prefix_context(""), "")
        self.assertEqual(am.get_prefix_context("one"), "one")

if __name__ == '__main__':
    unittest.main()
