import unittest
from babelfish_stt.pipeline import HybridTrigger

class TestHybridTrigger(unittest.TestCase):
    def test_trigger_on_timer(self):
        # Trigger every 2000ms
        trigger = HybridTrigger(interval_ms=2000)
        
        # 1000ms passed, not speaking -> no trigger
        self.assertFalse(trigger.should_trigger(now_ms=1000, is_speaking=False))
        
        # Start speaking at 1000ms
        trigger.start_speech(1000)
        
        # 2500ms passed (1500ms of speech) -> no trigger
        self.assertFalse(trigger.should_trigger(now_ms=2500, is_speaking=True))
        
        # 3500ms passed (2500ms of speech) -> TRIGGER
        self.assertTrue(trigger.should_trigger(now_ms=3500, is_speaking=True))

    def test_trigger_on_pause(self):
        trigger = HybridTrigger(interval_ms=2000)
        trigger.start_speech(1000)
        
        # 1500ms passed, still speaking
        self.assertFalse(trigger.should_trigger(now_ms=1500, is_speaking=True))
        
        # 1600ms passed, speaking stopped (VAD pause) -> TRIGGER
        self.assertTrue(trigger.should_trigger(now_ms=1600, is_speaking=False))

    def test_reset_after_trigger(self):
        trigger = HybridTrigger(interval_ms=2000)
        trigger.start_speech(1000)
        
        self.assertTrue(trigger.should_trigger(now_ms=3500, is_speaking=True))
        
        # Reset
        trigger.reset(3500)
        
        # Should not trigger immediately again
        self.assertFalse(trigger.should_trigger(now_ms=4000, is_speaking=True))
        
        # Should trigger after another 2000ms
        self.assertTrue(trigger.should_trigger(now_ms=6000, is_speaking=True))

if __name__ == '__main__':
    unittest.main()
