import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from babelfish_stt.audio import AudioStreamer

class TestAudio(unittest.TestCase):
    @patch('sounddevice.InputStream')
    @patch('sounddevice.query_devices')
    def test_audio_streamer_initialization(self, mock_query, mock_input_stream):
        # Mock default device
        mock_query.return_value = {'name': 'test mic', 'max_input_channels': 1, 'default_sample_rate': 16000}
        
        with patch('sounddevice.default.device', [0, 0]):
            streamer = AudioStreamer(sample_rate=16000)
            self.assertEqual(streamer.sample_rate, 16000)
            self.assertEqual(streamer.device_index, 0)

    @patch('sounddevice.InputStream')
    def test_audio_stream_generator(self, mock_input_stream):
        streamer = AudioStreamer(sample_rate=16000)
        
        # Add some data to the queue to simulate audio input
        test_chunk = np.array([0.1, 0.2], dtype='float32')
        streamer.audio_queue.put(test_chunk)
        
        # Get the generator
        gen = streamer.stream()
        
        # We need to be careful as streamer.stream() starts a while loop
        # We'll take one item and then stop it
        chunk = next(gen)
        np.testing.assert_array_equal(chunk, test_chunk)
        
        # Stop the streamer to break the while loop
        streamer.stop()
        
        # The next next() should raise StopIteration
        with self.assertRaises(StopIteration):
            next(gen)

    def test_audio_callback(self):
        streamer = AudioStreamer(sample_rate=16000)
        test_data = np.array([[0.1], [0.2]], dtype='float32')
        
        # Call the callback directly
        streamer._audio_callback(test_data, 2, None, None)
        
        # Verify data is in queue and flattened
        self.assertFalse(streamer.audio_queue.empty())
        chunk = streamer.audio_queue.get()
        np.testing.assert_array_equal(chunk, test_data.flatten())

if __name__ == '__main__':
    unittest.main()