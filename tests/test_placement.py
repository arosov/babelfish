import logging
import unittest

from babelfish_stt.placement import GpuDevice, HardwareFacts, onnx_providers, resolve_device


class TestOnnxProviders(unittest.TestCase):
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
            ("openvino", ["OpenVINOExecutionProvider", cpu]),
            ("coreml", ["CoreMLExecutionProvider", cpu]),
            ("cuda:oops", [("CUDAExecutionProvider", {"device_id": 0}), cpu]),
        )
        for device, expected in cases:
            with self.subTest(device=device):
                self.assertEqual(onnx_providers(device), expected)


class TestConcreteBackendResolution(unittest.TestCase):
    """hardware.device is always a concrete backend — no "auto" (ADR 0007)."""

    def test_a_bare_backend_name_picks_the_device_with_the_most_vram_on_that_backend(self):
        cases = (
            ("cuda", "CUDAExecutionProvider", ("cuda:0", 4.0), ("cuda:1", 8.0), "cuda:1"),
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

    def test_cuda_prefers_a_discrete_gpu_over_an_integrated_one_with_more_reported_memory(self):
        facts = HardwareFacts(
            providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("cuda:0", "NVIDIA GeForce GTX 1050", 4.0),
                GpuDevice("cuda:1", "NVIDIA GeForce RTX 2080 SUPER", 8.0),
            ),
        )

        self.assertEqual(resolve_device("cuda", facts), "cuda:1")

    def test_dml_prefers_a_discrete_adapter_over_an_integrated_one(self):
        facts = HardwareFacts(
            providers=("DmlExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("dml:0", "Intel(R) UHD Graphics 630", 0.5, integrated=True),
                GpuDevice("dml:1", "AMD Radeon RX 6600", 8.0),
                GpuDevice("dml:2", "AMD Radeon RX 6800 XT", 16.0),
                GpuDevice("dml:3", "NVIDIA GeForce GTX 1660", 6.0),
            ),
        )

        self.assertEqual(resolve_device("dml", facts), "dml:2")

    def test_an_explicitly_pinned_device_is_kept_even_if_another_has_more_vram(self):
        facts = HardwareFacts(
            providers=("DmlExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("dml:0", "AMD Radeon RX 6600", 8.0),
                GpuDevice("dml:1", "AMD Radeon RX 6800 XT", 16.0),
            ),
        )

        self.assertEqual(resolve_device("dml:0", facts), "dml:0")

    def test_a_gpu_provider_with_no_enumerated_device_falls_back_to_device_zero(self):
        cases = (
            ("cuda", "CUDAExecutionProvider", "cuda:0"),
            ("dml", "DmlExecutionProvider", "dml:0"),
        )
        for requested, provider, expected in cases:
            with self.subTest(requested=requested):
                facts = HardwareFacts(providers=(provider, "CPUExecutionProvider"))

                self.assertEqual(resolve_device(requested, facts), expected)

    def test_a_request_without_its_provider_degrades_to_cpu_with_a_warning(self):
        cases = (
            ("cuda", ("DmlExecutionProvider", "CPUExecutionProvider")),
            ("cuda:0", ("DmlExecutionProvider", "CPUExecutionProvider")),
            ("dml", ("CUDAExecutionProvider", "CPUExecutionProvider")),
            ("dml:2", ("CPUExecutionProvider",)),
        )
        for requested, providers in cases:
            with self.subTest(requested=requested):
                facts = HardwareFacts(providers=providers)

                with self.assertLogs("babelfish_stt.placement", level=logging.WARNING):
                    resolved = resolve_device(requested, facts)

                self.assertEqual(resolved, "cpu")

    def test_an_unknown_device_degrades_to_cpu_with_a_warning(self):
        facts = HardwareFacts(providers=("CUDAExecutionProvider", "CPUExecutionProvider"))

        with self.assertLogs("babelfish_stt.placement", level=logging.WARNING):
            resolved = resolve_device("some_stale_value", facts)

        self.assertEqual(resolved, "cpu")

    def test_a_legacy_rocm_value_degrades_to_cpu_like_any_unknown_device(self):
        facts = HardwareFacts(providers=("CPUExecutionProvider",))

        with self.assertLogs("babelfish_stt.placement", level=logging.WARNING):
            resolved = resolve_device("rocm:0", facts)

        self.assertEqual(resolved, "cpu")

    def test_openvino_without_its_provider_degrades_to_cpu(self):
        facts = HardwareFacts(providers=("CPUExecutionProvider",))

        with self.assertLogs("babelfish_stt.placement", level=logging.WARNING):
            resolved = resolve_device("openvino", facts)

        self.assertEqual(resolved, "cpu")

    def test_coreml_is_passed_through_on_apple_silicon(self):
        facts = HardwareFacts(
            providers=("CoreMLExecutionProvider", "CPUExecutionProvider"),
            platform="darwin",
            machine="arm64",
        )

        self.assertEqual(resolve_device("coreml", facts), "coreml")

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

        self.assertEqual(resolve_device("cuda", facts), "cuda:0")


if __name__ == "__main__":
    unittest.main()
