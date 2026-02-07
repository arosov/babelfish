import unittest
import numpy as np
from babelfish_stt.audio import HistoryBuffer

class TestHistoryBuffer(unittest.TestCase):
    def test_buffer_append_and_get(self):
        # 16000 Hz, 4 seconds = 64000 samples
        hb = HistoryBuffer(maxlen_samples=64000)
        
        chunk1 = np.ones(16000, dtype=np.float32)
        hb.append(chunk1)
        
        full = hb.get_all()
        self.assertEqual(len(full), 16000)
        np.testing.assert_array_equal(full, chunk1)

    def test_buffer_sliding_window(self):
        # Max length 10 samples
        hb = HistoryBuffer(maxlen_samples=10)
        
        hb.append(np.arange(6, dtype=np.float32)) # 0,1,2,3,4,5
        hb.append(np.arange(6, 12, dtype=np.float32)) # 6,7,8,9,10,11
        
        full = hb.get_all()
        # Should only keep last 10: [2,3,4,5,6,7,8,9,10,11]
        self.assertEqual(len(full), 10)
        self.assertEqual(full[0], 2)
        self.assertEqual(full[-1], 11)

    def test_buffer_clear(self):
        hb = HistoryBuffer(maxlen_samples=100)
        hb.append(np.ones(50))
        hb.clear()
        self.assertEqual(len(hb.get_all()), 0)

if __name__ == '__main__':
    unittest.main()
