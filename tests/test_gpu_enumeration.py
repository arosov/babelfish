import unittest
from unittest.mock import patch

from babelfish_stt.hardware import probe_hardware_facts
from babelfish_stt.placement import GpuDevice


class TestGpuEnumeration(unittest.TestCase):
    @patch("onnxruntime.get_available_providers")
    @patch("shutil.which")
    @patch("subprocess.check_output")
    def test_nvidia_gpus_are_enumerated_with_their_smi_index_and_total_vram(
        self, mock_output, mock_which, mock_providers
    ):
        mock_providers.return_value = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_output.return_value = (
            b"0, NVIDIA GeForce GTX 1050, 4096\n1, NVIDIA GeForce RTX 2080 SUPER, 8192\n"
        )

        facts = probe_hardware_facts()

        self.assertEqual(
            facts.gpus,
            (
                GpuDevice("cuda:0", "NVIDIA GeForce GTX 1050", 4.0),
                GpuDevice("cuda:1", "NVIDIA GeForce RTX 2080 SUPER", 8.0),
            ),
        )

    @patch("onnxruntime.get_available_providers")
    @patch("babelfish_stt.hardware._query_dxgi_adapters")
    def test_directml_adapters_are_enumerated_in_dxgi_order_with_vram(
        self, mock_adapters, mock_providers
    ):
        mock_providers.return_value = ["DmlExecutionProvider", "CPUExecutionProvider"]
        mock_adapters.return_value = [
            {"name": "Intel(R) UHD Graphics 630", "total_gb": 0.5, "integrated": True},
            {"name": "AMD Radeon RX 6800 XT", "total_gb": 16.0, "integrated": False},
        ]

        facts = probe_hardware_facts()

        self.assertEqual(
            facts.gpus,
            (
                GpuDevice("dml:0", "Intel(R) UHD Graphics 630", 0.5, integrated=True),
                GpuDevice("dml:1", "AMD Radeon RX 6800 XT", 16.0),
            ),
        )

    @patch("onnxruntime.get_available_providers")
    @patch("babelfish_stt.hardware._query_dxgi_adapters")
    def test_openvino_lists_intel_adapters_numbered_among_themselves(
        self, mock_adapters, mock_providers
    ):
        mock_providers.return_value = ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
        mock_adapters.return_value = [
            {"name": "Intel(R) UHD Graphics 770", "total_gb": 0.5, "integrated": True},
            {"name": "NVIDIA GeForce RTX 3060", "total_gb": 12.0, "integrated": False},
            {"name": "Intel(R) Arc(TM) A770", "total_gb": 16.0, "integrated": False},
        ]

        facts = probe_hardware_facts()

        self.assertEqual(
            facts.gpus,
            (
                GpuDevice("openvino:GPU.0", "Intel(R) UHD Graphics 770", 0.5, integrated=True),
                GpuDevice("openvino:GPU.1", "Intel(R) Arc(TM) A770", 16.0),
            ),
        )



if __name__ == "__main__":
    unittest.main()
