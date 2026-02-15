import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from babelfish_stt.hardware import (
    find_best_microphone,
    list_microphones,
    HardwareManager,
)


class TestStartupHardware(unittest.TestCase):
    @patch("sounddevice.query_devices")
    def test_list_microphones_empty(self, mock_query):
        mock_query.return_value = [
            {
                "name": "Output Only",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            }
        ]
        mics = list_microphones()
        self.assertEqual(len(mics), 0)

    @patch("sounddevice.query_devices")
    def test_find_best_microphone_none_available(self, mock_query):
        mock_query.return_value = [
            {
                "name": "Output Only",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            }
        ]
        idx = find_best_microphone()
        self.assertIsNone(idx)

    @patch("babelfish_stt.hardware.get_gpu_info")
    @patch("sounddevice.query_devices")
    def test_probe_exits_on_no_mic(self, mock_query, mock_gpu):
        mock_gpu.return_value = {"cuda_available": False, "name": None, "vram_gb": 0.0}
        mock_query.return_value = [
            {
                "name": "Output Only",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            }
        ]

        hm = HardwareManager()
        with self.assertRaises(SystemExit) as cm:
            hm.probe()
        self.assertEqual(cm.exception.code, 1)

    @patch("onnxruntime.get_available_providers")
    @patch("babelfish_stt.hardware.get_gpu_info")
    @patch("sounddevice.query_devices")
    def test_hardware_manager_probe(self, mock_query, mock_gpu, mock_providers):
        mock_providers.return_value = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        mock_gpu.return_value = {
            "cuda_available": True,
            "name": "RTX 4090",
            "vram_gb": 24.0,
        }

        devices = [
            {
                "name": "Mic 1",
                "max_input_channels": 1,
                "max_output_channels": 0,
                "default_samplerate": 16000,
            },
            {
                "name": "Speaker",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 48000,
            },
        ]

        def query_devices_mock(index=None):
            if index is None:
                return devices
            return devices[index]

        mock_query.side_effect = query_devices_mock

        hm = HardwareManager()
        hm.probe()

        self.assertTrue(hm.gpu_info["cuda_available"])
        self.assertEqual(hm.gpu_info["vram_gb"], 24.0)
        self.assertEqual(len(hm.microphones), 1)
        self.assertEqual(hm.best_mic_index, 0)


if __name__ == "__main__":
    unittest.main()
