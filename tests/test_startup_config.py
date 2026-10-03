import unittest
from unittest.mock import patch, MagicMock
import os
import json
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.config import platform_default_device
from babelfish_stt.hardware import HardwareManager


class TestStartupConfig(unittest.TestCase):
    def setUp(self):
        self.test_config_path = "test_config.json"
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)

    def tearDown(self):
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)

    def test_malformed_json_triggers_defaults(self):
        with open(self.test_config_path, "w") as f:
            f.write("{ invalid json: ")

        cm = ConfigManager(config_path=self.test_config_path)
        self.assertEqual(cm.config.hardware.device, platform_default_device())

    @patch("sounddevice.query_devices")
    @patch("onnxruntime.get_available_providers")
    @patch("babelfish_stt.hardware.get_gpu_info")
    @patch("babelfish_stt.hardware.find_best_microphone")
    @patch("babelfish_stt.config_manager.platform_default_device", lambda: "dml")
    def test_generate_optimal_defaults_write_the_platform_default(
        self, mock_mic, mock_gpu, mock_providers, mock_sd_query
    ):
        mock_providers.return_value = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        mock_gpu.return_value = {
            "cuda_available": True,
            "name": "RTX 3080",
            "vram_gb": 10.0,
        }
        mock_mic.return_value = 0

        def sd_query(*args, **kwargs):
            if args:  # query_devices(index, "input") -> single device
                return {"name": "Mic 1", "max_input_channels": 1, "default_samplerate": 48000.0}
            return [{"name": "Mic 1", "max_input_channels": 1, "default_samplerate": 48000.0}]

        mock_sd_query.side_effect = sd_query

        hm = HardwareManager().probe()
        cm = ConfigManager(config_path=self.test_config_path)

        cm.generate_optimal_defaults(hm)

        # Device selection is delegated to placement.resolve_device at engine
        # startup; optimal defaults save the concrete platform default (never
        # "auto") regardless of GPU.
        self.assertEqual(cm.config.hardware.device, "dml")
        self.assertEqual(cm.config.hardware.microphone_name, "Mic 1")

        self.assertTrue(os.path.exists(self.test_config_path))
        with open(self.test_config_path, "r") as f:
            data = json.load(f)
            self.assertEqual(data["hardware"]["device"], "dml")
            self.assertEqual(data["hardware"]["microphone_name"], "Mic 1")

    @patch("sounddevice.query_devices")
    @patch("onnxruntime.get_available_providers")
    @patch("babelfish_stt.hardware.get_gpu_info")
    @patch("babelfish_stt.hardware.find_best_microphone")
    @patch("babelfish_stt.config_manager.platform_default_device", lambda: "cuda")
    def test_generate_optimal_defaults_linux_cuda_with_nvidia(
        self, mock_mic, mock_gpu, mock_providers, mock_sd_query
    ):
        mock_providers.return_value = ["CPUExecutionProvider"]
        mock_gpu.return_value = {
            "cuda_available": False,
            "name": None,
            "vram_gb": 0.0,
        }
        mock_mic.return_value = 0

        def sd_query(*args, **kwargs):
            if args:
                return {"name": "Mic 1", "max_input_channels": 1, "default_samplerate": 48000.0}
            return [{"name": "Mic 1", "max_input_channels": 1, "default_samplerate": 48000.0}]

        mock_sd_query.side_effect = sd_query

        hm = HardwareManager().probe()
        cm = ConfigManager(config_path=self.test_config_path)

        cm.generate_optimal_defaults(hm)

        self.assertEqual(cm.config.hardware.device, "cuda")

    @patch("babelfish_stt.hardware.get_gpu_info")
    @patch("babelfish_stt.hardware.find_best_microphone")
    @patch("babelfish_stt.hardware.list_microphones")
    def test_is_valid_hardware_check(self, mock_list, mock_find, mock_gpu):
        mock_gpu.return_value = {
            "cuda_available": True,
            "name": "RTX 3080",
            "vram_gb": 10.0,
        }
        mock_list.return_value = [{"index": 0, "name": "Mic 1"}]
        mock_find.return_value = 0

        hm = HardwareManager().probe()

        with open(self.test_config_path, "w") as f:
            json.dump(
                {
                    "hardware": {
                        "device": "cuda",
                        "microphone_name": "Mic 1",
                        "auto_detect": False,
                    }
                },
                f,
            )

        cm = ConfigManager(config_path=self.test_config_path)
        self.assertTrue(cm.is_valid(hm))

        with open(self.test_config_path, "w") as f:
            json.dump(
                {
                    "hardware": {
                        "device": "cuda",
                        "microphone_name": "Non-existent Mic",
                        "auto_detect": False,
                    }
                },
                f,
            )

        cm = ConfigManager(config_path=self.test_config_path)
        self.assertFalse(cm.is_valid(hm))

        mock_gpu.return_value = {"cuda_available": False, "name": None, "vram_gb": 0.0}
        hm.probe()
        with open(self.test_config_path, "w") as f:
            json.dump({"hardware": {"device": "cuda", "auto_detect": False}}, f)

        cm = ConfigManager(config_path=self.test_config_path)
        self.assertTrue(cm.is_valid(hm))


if __name__ == "__main__":
    unittest.main()
