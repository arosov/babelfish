import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from babelfish_stt.audio import AudioStreamer


class TestAudio(unittest.TestCase):
    @patch("sounddevice.InputStream")
    @patch("sounddevice.query_devices")
    def test_audio_streamer_initialization(self, mock_query, mock_input_stream):
        # Mock default device
        mock_query.return_value = {
            "name": "test mic",
            "max_input_channels": 1,
            "default_samplerate": 16000,
        }

        with patch("sounddevice.default.device", [0, 0]):
            streamer = AudioStreamer(sample_rate=16000)
            self.assertEqual(streamer.target_rate, 16000)
            self.assertEqual(streamer.device_index, 0)
            self.assertFalse(streamer.needs_resampling)

    @patch("sounddevice.InputStream")
    @patch("sounddevice.query_devices")
    def test_audio_stream_generator(self, mock_query, mock_input_stream):
        mock_query.return_value = {
            "name": "test mic",
            "max_input_channels": 1,
            "default_samplerate": 16000,
        }
        streamer = AudioStreamer(sample_rate=16000)

        # Add some data to the queue to simulate audio input
        # Size must be >= chunk_size (default 512)
        test_chunk = np.zeros(512, dtype="float32")
        test_chunk[0] = 0.1
        streamer.audio_queue.put(test_chunk)

        # Get the generator
        gen = streamer.stream(chunk_size=512)

        # Take one item
        chunk = next(gen)
        np.testing.assert_array_equal(chunk, test_chunk)

        # Stop the streamer
        streamer.stop()

        # The next next() should raise StopIteration
        with self.assertRaises(StopIteration):
            next(gen)

    @patch("sounddevice.query_devices")
    def test_audio_callback_no_resample(self, mock_query):
        mock_query.return_value = {
            "name": "test mic",
            "max_input_channels": 1,
            "default_samplerate": 16000,
        }
        streamer = AudioStreamer(sample_rate=16000)
        test_data = np.array([[0.1], [0.2]], dtype="float32")

        # Call the callback directly
        streamer._audio_callback(test_data, 2, None, None)

        # Verify data is in queue and flattened
        self.assertFalse(streamer.audio_queue.empty())
        chunk = streamer.audio_queue.get()
        np.testing.assert_array_equal(chunk, test_data.flatten())

    @patch("sounddevice.query_devices")
    def test_audio_callback_puts_raw_data(self, mock_query):
        """Verify callback only puts raw data, resampling is handled in stream loop."""
        mock_query.return_value = {
            "name": "test mic",
            "max_input_channels": 1,
            "default_samplerate": 44100,
        }
        streamer = AudioStreamer(sample_rate=16000)
        self.assertTrue(streamer.needs_resampling)

        test_data = np.array([[0.1], [0.2]], dtype="float32")
        streamer._audio_callback(test_data, 2, None, None)

        self.assertFalse(streamer.audio_queue.empty())
        chunk = streamer.audio_queue.get()
        # Verify it's the raw (unresampled) data
        np.testing.assert_array_equal(chunk, test_data.flatten())


if __name__ == "__main__":
    unittest.main()
