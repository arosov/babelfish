import unittest
from babelfish_stt.pipeline import StopWordDetector

class TestStopWordDetector(unittest.TestCase):
    def test_basic_detection(self):
        detector = StopWordDetector(stop_words=["stop"])
        self.assertTrue(detector.detect("please stop"))
        self.assertTrue(detector.detect("stop"))
        self.assertFalse(detector.detect("don't stop yet"))

    def test_case_insensitivity(self):
        detector = StopWordDetector(stop_words=["Stop"])
        self.assertTrue(detector.detect("please stop"))
        self.assertTrue(detector.detect("STOP"))

    def test_punctuation_handling(self):
        detector = StopWordDetector(stop_words=["stop"])
        self.assertTrue(detector.detect("please stop."))
        self.assertTrue(detector.detect("stop!"))
        self.assertTrue(detector.detect("stop..."))

    def test_phrase_matching(self):
        detector = StopWordDetector(stop_words=["terminate session"])
        self.assertTrue(detector.detect("please terminate session"))
        self.assertFalse(detector.detect("terminate the session"))

    def test_multiple_stop_words(self):
        detector = StopWordDetector(stop_words=["stop", "quit", "exit"])
        self.assertTrue(detector.detect("please quit"))
        self.assertTrue(detector.detect("time to exit."))
        self.assertTrue(detector.detect("STOP!"))
        self.assertFalse(detector.detect("don't quit now"))

if __name__ == '__main__':
    unittest.main()
