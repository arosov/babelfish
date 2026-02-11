import unittest
from unittest.mock import patch, MagicMock
from babelfish_stt.hardware import get_gpu_info, is_cuda_available


class TestHardware(unittest.TestCase):
    @patch("onnxruntime.get_available_providers")
    def test_is_cuda_available(self, mock_providers):
        mock_providers.return_value = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.assertTrue(is_cuda_available())

        mock_providers.return_value = ["CPUExecutionProvider"]
        self.assertFalse(is_cuda_available())

    @patch("babelfish_stt.hardware.is_cuda_available")
    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_get_gpu_info_cuda(self, mock_output, mock_which, mock_is_cuda):
        mock_is_cuda.return_value = True
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_output.return_value = b"NVIDIA GeForce RTX 3080, 10240\n"

        info = get_gpu_info()
        self.assertEqual(info["name"], "NVIDIA GeForce RTX 3080")
        self.assertAlmostEqual(info["vram_gb"], 10.0)
        self.assertTrue(info["cuda_available"])

    @patch("babelfish_stt.hardware.is_cuda_available")
    def test_get_gpu_info_no_cuda(self, mock_is_cuda):
        mock_is_cuda.return_value = False

        info = get_gpu_info()
        self.assertIsNone(info["name"])
        self.assertEqual(info["vram_gb"], 0.0)
        self.assertFalse(info["cuda_available"])


if __name__ == "__main__":
    unittest.main()
