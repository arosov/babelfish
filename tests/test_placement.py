import unittest

from babelfish_stt.placement import GpuDevice, HardwareFacts, onnx_providers, resolve_device


class TestOnnxProviders(unittest.TestCase):
    def test_a_rocm_device_id_selects_that_hip_device(self):
        self.assertEqual(
            onnx_providers("rocm:1"),
            [("ROCMExecutionProvider", {"device_id": 1}), "CPUExecutionProvider"],
        )

    def test_an_openvino_device_id_selects_that_openvino_device_type(self):
        self.assertEqual(
            onnx_providers("openvino:GPU.1"),
            [("OpenVINOExecutionProvider", {"device_type": "GPU.1"}), "CPUExecutionProvider"],
        )

    def test_existing_device_ids_keep_their_providers(self):
        cpu = "CPUExecutionProvider"
        cases = (
            ("cpu", [cpu]),
            ("cuda", [("CUDAExecutionProvider", {"device_id": 0}), cpu]),
            ("cuda:1", [("CUDAExecutionProvider", {"device_id": 1}), cpu]),
            ("dml", [("DmlExecutionProvider", {"device_id": 0}), cpu]),
            ("dml:2", [("DmlExecutionProvider", {"device_id": 2}), cpu]),
            ("rocm", ["ROCMExecutionProvider", cpu]),
            ("openvino", ["OpenVINOExecutionProvider", cpu]),
            ("coreml", ["CoreMLExecutionProvider", cpu]),
            ("cuda:oops", [("CUDAExecutionProvider", {"device_id": 0}), cpu]),
        )
        for device, expected in cases:
            with self.subTest(device=device):
                self.assertEqual(onnx_providers(device), expected)


class TestHighestVramSelection(unittest.TestCase):
    def test_auto_picks_the_nvidia_gpu_with_the_most_vram(self):
        facts = HardwareFacts(
            providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("cuda:0", "NVIDIA GeForce GTX 1050", 4.0),
                GpuDevice("cuda:1", "NVIDIA GeForce RTX 2080 SUPER", 8.0),
            ),
        )

        self.assertEqual(resolve_device("auto", facts), "cuda:1")

    def test_auto_picks_the_directml_adapter_with_the_most_vram(self):
        facts = HardwareFacts(
            providers=("DmlExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("dml:0", "Intel(R) UHD Graphics 630", 0.5),
                GpuDevice("dml:1", "AMD Radeon RX 6600", 8.0),
                GpuDevice("dml:2", "AMD Radeon RX 6800 XT", 16.0),
                GpuDevice("dml:3", "NVIDIA GeForce GTX 1660", 6.0),
            ),
        )

        self.assertEqual(resolve_device("auto", facts), "dml:2")

    def test_auto_picks_the_rocm_card_with_the_most_vram(self):
        facts = HardwareFacts(
            providers=("ROCMExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("rocm:0", "AMD Radeon RX 6600", 8.0),
                GpuDevice("rocm:1", "AMD Radeon RX 7900 XTX", 24.0),
            ),
        )

        self.assertEqual(resolve_device("auto", facts), "rocm:1")

    def test_auto_prefers_a_discrete_openvino_gpu_over_an_integrated_one_with_more_reported_memory(
        self,
    ):
        facts = HardwareFacts(
            providers=("OpenVINOExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("openvino:GPU.0", "Intel(R) UHD Graphics 770", 16.0, integrated=True),
                GpuDevice("openvino:GPU.1", "Intel(R) Arc(TM) A770", 8.0),
            ),
        )

        self.assertEqual(resolve_device("auto", facts), "openvino:GPU.1")

    def test_an_explicitly_pinned_device_is_kept_even_if_another_has_more_vram(self):
        facts = HardwareFacts(
            providers=("DmlExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("dml:0", "AMD Radeon RX 6600", 8.0),
                GpuDevice("dml:1", "AMD Radeon RX 6800 XT", 16.0),
            ),
        )

        self.assertEqual(resolve_device("dml:0", facts), "dml:0")

    def test_a_bare_backend_name_picks_the_device_with_the_most_vram_on_that_backend(self):
        cases = (
            ("rocm", "ROCMExecutionProvider", ("rocm:0", 8.0), ("rocm:1", 24.0), "rocm:1"),
            ("dml", "DmlExecutionProvider", ("dml:0", 6.0), ("dml:1", 12.0), "dml:1"),
            (
                "openvino",
                "OpenVINOExecutionProvider",
                ("openvino:GPU.0", 4.0),
                ("openvino:GPU.1", 16.0),
                "openvino:GPU.1",
            ),
        )
        for requested, provider, (id_a, gb_a), (id_b, gb_b), expected in cases:
            with self.subTest(requested=requested):
                facts = HardwareFacts(
                    providers=(provider, "CPUExecutionProvider"),
                    gpus=(GpuDevice(id_a, "GPU A", gb_a), GpuDevice(id_b, "GPU B", gb_b)),
                )

                self.assertEqual(resolve_device(requested, facts), expected)

    def test_a_gpu_provider_with_no_enumerated_device_falls_back_to_device_zero(self):
        cases = (
            ("CUDAExecutionProvider", "cuda:0"),
            ("ROCMExecutionProvider", "rocm:0"),
            ("DmlExecutionProvider", "dml:0"),
        )
        for provider, expected in cases:
            with self.subTest(provider=provider):
                facts = HardwareFacts(providers=(provider, "CPUExecutionProvider"))

                self.assertEqual(resolve_device("auto", facts), expected)

    def test_a_cuda_request_without_the_cuda_provider_falls_back_to_the_best_directml_adapter(
        self,
    ):
        facts = HardwareFacts(
            providers=("DmlExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("dml:0", "NVIDIA GeForce GTX 1660", 6.0),
                GpuDevice("dml:1", "NVIDIA GeForce RTX 3080", 10.0),
            ),
        )

        self.assertEqual(resolve_device("cuda:0", facts), "dml:1")

    def test_auto_on_apple_silicon_resolves_to_coreml(self):
        facts = HardwareFacts(
            providers=("CoreMLExecutionProvider", "CPUExecutionProvider"),
            platform="darwin",
            machine="arm64",
        )

        self.assertEqual(resolve_device("auto", facts), "coreml")

    def test_auto_without_any_gpu_provider_is_cpu(self):
        facts = HardwareFacts(providers=("CPUExecutionProvider",))

        self.assertEqual(resolve_device("auto", facts), "cpu")

    def test_auto_does_not_pick_openvino_when_no_gpu_was_enumerated(self):
        facts = HardwareFacts(providers=("OpenVINOExecutionProvider", "CPUExecutionProvider"))

        self.assertEqual(resolve_device("auto", facts), "cpu")

    def test_an_explicit_cpu_request_stays_cpu_even_when_a_gpu_is_available(self):
        facts = HardwareFacts(
            providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
            gpus=(GpuDevice("cuda:0", "NVIDIA GeForce RTX 2080 SUPER", 8.0),),
        )

        self.assertEqual(resolve_device("cpu", facts), "cpu")

    def test_gpus_with_equal_vram_resolve_to_the_lowest_index(self):
        facts = HardwareFacts(
            providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("cuda:0", "NVIDIA GeForce RTX 3060", 12.0),
                GpuDevice("cuda:1", "NVIDIA GeForce RTX 3060", 12.0),
            ),
        )

        self.assertEqual(resolve_device("auto", facts), "cuda:0")

    def test_auto_on_an_intel_mac_stays_on_cpu(self):
        facts = HardwareFacts(
            providers=("CoreMLExecutionProvider", "CPUExecutionProvider"),
            platform="darwin",
            machine="x86_64",
        )

        self.assertEqual(resolve_device("auto", facts), "cpu")


if __name__ == "__main__":
    unittest.main()
