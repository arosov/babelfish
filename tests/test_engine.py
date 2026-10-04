import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import numpy as np
from babelfish_stt.engine import STTEngine
from babelfish_stt.config import BabelfishConfig, HardwareConfig


def _cuda_facts():
    from babelfish_stt.placement import GpuDevice, HardwareFacts

    return HardwareFacts(
        providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
        gpus=(GpuDevice("cuda:0", "NVIDIA GeForce RTX 2080 SUPER", 8.0),),
    )


class TestEngine(unittest.TestCase):
    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    @patch("babelfish_stt.hardware.probe_hardware_facts")
    def test_bare_cuda_resolves_to_the_gpu_with_the_most_vram(
        self, mock_probe, mock_mem, mock_load
    ):
        from babelfish_stt.placement import GpuDevice, HardwareFacts

        mock_probe.return_value = HardwareFacts(
            providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
            gpus=(
                GpuDevice("cuda:0", "NVIDIA GeForce GTX 1050", 4.0),
                GpuDevice("cuda:1", "NVIDIA GeForce RTX 2080 SUPER", 8.0),
            ),
        )
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        config = BabelfishConfig(hardware=HardwareConfig(device="cuda"))

        engine = STTEngine(config=config)

        self.assertEqual(engine.device_type, "cuda:1")
        _, kwargs = mock_load.call_args
        self.assertEqual(
            kwargs["providers"],
            [("CUDAExecutionProvider", {"device_id": 1}), "CPUExecutionProvider"],
        )

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_cpu_defaults_to_full_precision(self, mock_mem, mock_load):
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))

        STTEngine(config=config)

        _, kwargs = mock_load.call_args
        self.assertIsNone(kwargs["quantization"])

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    @patch("babelfish_stt.hardware.probe_hardware_facts")
    def test_gpu_load_failure_falls_back_to_cpu_full_precision(
        self, mock_probe, mock_mem, mock_load
    ):
        from babelfish_stt.placement import GpuDevice, HardwareFacts

        mock_probe.return_value = HardwareFacts(
            providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
            gpus=(GpuDevice("cuda:0", "NVIDIA GeForce RTX 2080 SUPER", 8.0),),
        )
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        mock_load.side_effect = [RuntimeError("CUDA OOM"), MagicMock()]
        config = BabelfishConfig(hardware=HardwareConfig(device="cuda"))

        engine = STTEngine(config=config)

        self.assertEqual(engine.device_type, "cpu")
        self.assertEqual(mock_load.call_count, 2)
        _, kwargs = mock_load.call_args
        self.assertEqual(kwargs["providers"], ["CPUExecutionProvider"])
        self.assertIsNone(kwargs["quantization"])

    @patch("babelfish_stt.engine.STTEngine._resolve_model_path", return_value=Path("m"))
    @patch(
        "babelfish_stt.engine.time.perf_counter",
        side_effect=[0.0, 0.08, 0.0, 0.08, 0.0, 0.08],
    )
    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_phase_timers_logged_in_order(self, mock_mem, mock_load, mock_pc, mock_rp):
        """The three ⏱️ lines appear around the load, in plan order."""
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))

        with self.assertLogs("babelfish_stt.engine", level="INFO") as logs:
            STTEngine(config=config)

        messages = [r.getMessage() for r in logs.records]
        init_idx = next(i for i, m in enumerate(messages) if "Initializing onnx-asr" in m)
        probe_indexes = [i for i, m in enumerate(messages) if "Memory probe" in m]
        load_idx = next(i for i, m in enumerate(messages) if "⏱️ Model load" in m)
        vram_idx = next(i for i, m in enumerate(messages) if "VRAM Status" in m)

        self.assertEqual(len(probe_indexes), 2)
        self.assertLess(init_idx, probe_indexes[0])
        self.assertLess(probe_indexes[0], load_idx)
        self.assertLess(load_idx, probe_indexes[1])
        self.assertLess(probe_indexes[1], vram_idx)

    @patch("babelfish_stt.engine.MODEL_LOAD_TIMEOUT_S", 0.1)
    @patch("babelfish_stt.engine.STTEngine._resolve_model_path", return_value=Path("m"))
    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    @patch("babelfish_stt.hardware.probe_hardware_facts")
    def test_model_load_timeout_falls_back_to_cpu(
        self, mock_probe, mock_mem, mock_load, mock_rp
    ):
        """A wedged GPU load trips the cap and routes into the CPU fallback."""
        import time as time_mod

        mock_probe.return_value = _cuda_facts()
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        cpu_model = MagicMock(name="cpu_model")

        def slow_gpu_load(*args, **kwargs):
            if kwargs.get("providers") != ["CPUExecutionProvider"]:
                time_mod.sleep(0.3)  # wedged past the patched 0.1s cap
                return MagicMock(name="gpu_model")
            return cpu_model

        mock_load.side_effect = slow_gpu_load
        config = BabelfishConfig(hardware=HardwareConfig(device="cuda"))

        with self.assertLogs("babelfish_stt.engine", level="WARNING") as logs:
            engine = STTEngine(config=config)

        self.assertTrue(
            any("exceeded" in r.getMessage() for r in logs.records),
            [r.getMessage() for r in logs.records],
        )
        # Same end state as today's failure path: CPU engine, healthy model.
        self.assertEqual(engine.device_type, "cpu")
        _, kwargs = mock_load.call_args
        self.assertEqual(kwargs["providers"], ["CPUExecutionProvider"])
        self.assertIs(engine.model, cpu_model)

    @patch("babelfish_stt.engine.MODEL_LOAD_TIMEOUT_S", 0.2)
    @patch("babelfish_stt.engine.STTEngine._resolve_model_path", return_value=None)
    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_model_load_without_local_path_skips_cap(self, mock_mem, mock_load, mock_rp):
        """No local model dir means first-run HF download: no cap applies."""
        import time as time_mod

        class _Sentinel(Exception):
            pass

        def slow_download(*args, **kwargs):
            time_mod.sleep(0.4)  # well past the patched 0.2s cap
            raise _Sentinel("download failed")

        mock_load.side_effect = slow_download
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))

        # The cap would raise TimeoutError; the sentinel proves the call ran
        # in-line (uncapped) and its exception propagated unchanged.
        with self.assertRaises(_Sentinel):
            STTEngine(config=config)

        mock_load.assert_called_once()

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_vram_status_includes_free(self, mock_mem, mock_load):
        """A successful probe surfaces Free VRAM in the status line."""
        mock_mem.return_value = {"total": 8.0, "used": 1.8}
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))

        with self.assertLogs("babelfish_stt.engine", level="INFO") as logs:
            STTEngine(config=config)

        vram_line = next(
            r.getMessage() for r in logs.records if "VRAM Status" in r.getMessage()
        )
        self.assertIn("Free=6.20GB", vram_line)
        self.assertIn("Total=8.00GB", vram_line)

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_vram_status_degraded_shape_without_free(self, mock_mem, mock_load):
        """A failed probe (zero total) keeps the legacy shape, no Free."""
        mock_mem.return_value = {"total": 0.0, "used": 0.0}
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))

        with self.assertLogs("babelfish_stt.engine", level="INFO") as logs:
            STTEngine(config=config)

        vram_line = next(
            r.getMessage() for r in logs.records if "VRAM Status" in r.getMessage()
        )
        self.assertNotIn("Free=", vram_line)

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_engine_initialization(self, mock_mem, mock_load):
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        engine = STTEngine(config=config)

        # Verify onnx_asr initialized
        mock_load.assert_called_once()
        self.assertEqual(engine.model, mock_load.return_value)

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_transcribe(self, mock_mem, mock_load):
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        engine = STTEngine(config=config)
        mock_audio = np.zeros(16000, dtype=np.float32)

        # Mock model result
        mock_load.return_value.recognize.return_value = "Hello world"

        text = engine.transcribe(mock_audio)

        self.assertEqual(text, "Hello world")
        # recognizer called with padded audio (2s default padding)
        # min_samples = 2.0 * 16000 = 32000
        # original 16000 + 16000 zeros
        args, kwargs = mock_load.return_value.recognize.call_args
        self.assertEqual(len(args[0]), 32000)

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_transcribe_empty(self, mock_mem, mock_load):
        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        engine = STTEngine(config=config)
        text = engine.transcribe(np.array([]))
        self.assertEqual(text, "")
        mock_load.return_value.recognize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
