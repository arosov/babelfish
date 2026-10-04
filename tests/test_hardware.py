import unittest
import subprocess
from unittest.mock import patch, MagicMock
from babelfish_stt.hardware import (
    get_gpu_info,
    get_device_name,
    get_best_gpu_index,
    is_cuda_available,
    _get_nvidia_memory,
    _get_nvidia_gpus,
    _list_nvidia_devices,
    NVIDIA_SMI_TIMEOUT_S,
)


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


class TestNvidiaSmiTimeout(unittest.TestCase):
    """Behavior on nvidia-smi timeout = behavior on error: fallback + warning."""

    def _wedge(self):
        return patch(
            "subprocess.check_output",
            side_effect=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=10.0),
        )

    @patch("shutil.which", return_value="/usr/bin/nvidia-smi")
    def test_nvidia_smi_output_bounds_the_probe(self, mock_which):
        """Every nvidia-smi call goes through the timeout constant."""
        with patch("subprocess.check_output", return_value=b"3080, 10240\n") as m:
            _get_nvidia_memory(0)
            _, kwargs = m.call_args
        self.assertEqual(kwargs["timeout"], NVIDIA_SMI_TIMEOUT_S)

    @patch("shutil.which", return_value="/usr/bin/nvidia-smi")
    def test_get_nvidia_memory_timeout_returns_fallback(self, mock_which):
        with self._wedge(), self.assertLogs(
            "babelfish_stt.hardware", level="WARNING"
        ) as logs:
            self.assertEqual(
                _get_nvidia_memory(0), {"total": 0.0, "used": 0.0}
            )
        self.assertTrue(
            any("timed out" in r.getMessage() for r in logs.records)
        )

    @patch("shutil.which", return_value="/usr/bin/nvidia-smi")
    def test_get_nvidia_gpus_timeout_returns_empty(self, mock_which):
        with self._wedge():
            self.assertEqual(_get_nvidia_gpus(), [])

    @patch("shutil.which", return_value="/usr/bin/nvidia-smi")
    def test_list_nvidia_devices_timeout_returns_empty(self, mock_which):
        with self._wedge():
            self.assertEqual(_list_nvidia_devices(), [])

    @patch("shutil.which", return_value="/usr/bin/nvidia-smi")
    def test_get_best_gpu_index_timeout_returns_zero(self, mock_which):
        with self._wedge():
            self.assertEqual(get_best_gpu_index(), 0)

    @patch("shutil.which", return_value="/usr/bin/nvidia-smi")
    def test_get_device_name_timeout_falls_to_static(self, mock_which):
        with self._wedge():
            self.assertEqual(get_device_name("cuda"), "NVIDIA GPU (CUDA)")

    @patch("babelfish_stt.hardware.is_cuda_available")
    @patch("shutil.which", return_value="/usr/bin/nvidia-smi")
    def test_get_gpu_info_timeout_degrades(self, mock_which, mock_is_cuda):
        """Same shape as today's error path, not a silent stall."""
        mock_is_cuda.return_value = True
        with self._wedge():
            info = get_gpu_info()
        self.assertTrue(info["cuda_available"])


if __name__ == "__main__":
    unittest.main()
