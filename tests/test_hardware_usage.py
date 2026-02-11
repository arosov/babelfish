import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
from babelfish_stt.hardware import get_memory_usage


class TestHardwareUsage(unittest.TestCase):
    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_get_nvidia_memory(self, mock_output, mock_which):
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_output.return_value = b"8192, 1024\n"

        usage = get_memory_usage("cuda:0")
        self.assertEqual(usage["total"], 8.0)
        self.assertEqual(usage["used"], 1.0)

    @patch("shutil.which")
    @patch("os.path.exists")
    @patch("subprocess.check_output")
    def test_get_rocm_memory(self, mock_output, mock_exists, mock_which):
        mock_which.return_value = "/usr/bin/rocm-smi"
        mock_exists.return_value = True
        mock_output.return_value = b'{"card0": {"VRAM Total Memory (B)": "8589934592", "VRAM Total Used (B)": "1073741824"}}'

        usage = get_memory_usage("rocm")
        self.assertEqual(usage["total"], 8.0)
        self.assertEqual(usage["used"], 1.0)

    @patch("sys.platform", "darwin")
    @patch("subprocess.check_output")
    def test_get_macos_memory(self, mock_output):
        def side_effect(cmd, **kwargs):
            if cmd[0] == "sysctl":
                return b"17179869184\n"  # 16GB
            if cmd[0] == "vm_stat":
                return b"Mach Virtual Memory Statistics: (page size of 4096 bytes)\nPages active: 1048576\nPages wired down: 524288\n"
            return b""

        mock_output.side_effect = side_effect

        usage = get_memory_usage("metal")
        # (1048576 + 524288) * 4096 / 1024^3 = 1572864 * 4096 / 1024^3 = 6.0 GB
        self.assertEqual(usage["total"], 16.0)
        self.assertEqual(usage["used"], 6.0)

    @patch("sys.platform", "win32")
    @patch("subprocess.check_output")
    def test_get_windows_memory(self, mock_output):
        def side_effect(cmd, **kwargs):
            if "Get-CimInstance" in cmd:
                return b"8589934592\n"  # 8GB
            if "Get-Counter" in cmd:
                return b"1073741824\n"  # 1GB
            return b""

        mock_output.side_effect = side_effect

        usage = get_memory_usage("dml")
        self.assertEqual(usage["total"], 8.0)
        self.assertEqual(usage["used"], 1.0)


if __name__ == "__main__":
    unittest.main()
