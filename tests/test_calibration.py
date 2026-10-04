"""
Startup self-calibration tests (ADR 0011): the benchmark always runs in
auto tier mode, its measurement is median-based with a discarded warm-up,
the CPU branch runs zero probes, and its result is applied in memory
only — never persisted. A persisted concrete tier is a manual override
that skips calibration, and the one-time migration rewrites a latched
tier to auto.
"""

import asyncio
import json
import unittest
from unittest.mock import patch, MagicMock

from babelfish_stt.config import (
    BabelfishConfig,
    HardwareConfig,
    PerformanceProfile,
)
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.engine import STTEngine


class _EngineMixin(unittest.TestCase):
    def _gpu_engine(self) -> STTEngine:
        with patch("onnx_asr.load_model"), patch(
            "babelfish_stt.engine.get_memory_usage"
        ) as mock_mem:
            mock_mem.return_value = {"total": 8.0, "used": 1.0}
            return STTEngine(config=BabelfishConfig(hardware=HardwareConfig(device="cuda")))

    def _cpu_engine(self) -> STTEngine:
        with patch("onnx_asr.load_model"), patch(
            "babelfish_stt.engine.get_memory_usage"
        ):
            return STTEngine(
                config=BabelfishConfig(hardware=HardwareConfig(device="cpu"))
            )


class TestBenchmarkMeasurement(_EngineMixin):
    def test_cold_start_shaped_samples_do_not_demote_under_median(self):
        """One ~600ms cold sample plus four ~38ms warm samples: the mean
        (~150ms) lands low_power; the median (~38ms) lands ultra."""
        engine = self._gpu_engine()
        # warm-up first (discarded), then the five probes
        series = iter([600.0, 38.0, 39.0, 37.0, 40.0, 36.0])
        with patch.object(engine, "_measure_latency_ms", lambda a: next(series)):
            profile = engine.benchmark()

        self.assertEqual(profile["tier"], "ultra")
        self.assertEqual(profile["ghost_throttle_ms"], 100)
        self.assertEqual(profile["ghost_window_s"], 3.0)
        self.assertEqual(profile["min_padding_s"], 2.0)
        self.assertEqual(profile["ghost_padding_s"], 1.0)

    def test_spiked_series_does_not_demote_under_median(self):
        engine = self._gpu_engine()
        series = iter([38.0, 38.0, 38.0, 38.0, 38.0, 600.0])
        with patch.object(engine, "_measure_latency_ms", lambda a: next(series)):
            profile = engine.benchmark()

        self.assertEqual(profile["tier"], "ultra")

    def test_real_median_crosses_tier_boundaries(self):
        engine = self._gpu_engine()
        series = iter([55.0, 60.0, 55.0, 58.0, 59.0, 61.0])
        with patch.object(engine, "_measure_latency_ms", lambda a: next(series)):
            profile = engine.benchmark()
        self.assertEqual(profile["tier"], "high")
        self.assertEqual(profile["ghost_throttle_ms"], 150)

    def test_cpu_branch_runs_zero_probes(self):
        engine = self._cpu_engine()

        def _no_probe(*args, **kwargs):
            raise AssertionError("CPU calibration must not run probes")

        with patch.object(engine, "_measure_latency_ms", _no_probe):
            with patch.object(engine, "transcribe", _no_probe):
                profile = engine.benchmark()

        self.assertEqual(profile["tier"], "cpu")
        self.assertEqual(profile["ghost_window_s"], 1.0)
        self.assertEqual(profile["ghost_padding_s"], 0.0)


class TestCalibrateInMemory:
    """The benchmark result is applied to the shared config in memory
    only; no calibration path writes pipeline.performance to the file."""

    @staticmethod
    async def _async_ok(message: str):
        return None

    def _config_manager(self, tmp_path, performance: dict):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "hardware": {"device": "cpu"},
                    "pipeline": {"performance": performance},
                }
            )
        )
        return ConfigManager(config_path=str(config_file))

    def test_auto_tier_calibrates_and_applies_in_memory(self, tmp_path):
        config_manager = self._config_manager(tmp_path, {"tier": "auto"})
        engine = MagicMock()
        engine.benchmark.return_value = {
            "tier": "high",
            "ghost_throttle_ms": 150,
            "ghost_window_s": 2.5,
            "ghost_padding_s": 1.0,
            "min_padding_s": 2.0,
        }

        with patch.object(ConfigManager, "save") as mock_save:
            from babelfish_stt.main import calibrate

            asyncio.run(
                calibrate(config_manager, engine, status=self._async_ok)
            )

        engine.benchmark.assert_called_once()
        applied = config_manager.config.pipeline.performance
        assert applied.tier == "high"
        assert applied.ghost_throttle_ms == 150
        # The file was never written with calibration output
        mock_save.assert_not_called()
        data = json.loads(config_manager.config_path.read_text())
        assert data["pipeline"]["performance"]["tier"] == "auto"

    def test_concrete_persisted_tier_skips_calibration(self, tmp_path):
        """A concrete tier on a migrated file is a deliberate manual
        override: calibration is skipped, benchmark never runs."""
        config_manager = self._config_manager(
            tmp_path, {"tier": "high", "latch_migrated": True}
        )
        engine = MagicMock()

        from babelfish_stt.main import calibrate

        asyncio.run(calibrate(config_manager, engine, status=self._async_ok))

        engine.benchmark.assert_not_called()
        assert config_manager.config.pipeline.performance.tier == "high"

    def test_raising_benchmark_falls_back_to_defaults(self, tmp_path):
        config_manager = self._config_manager(tmp_path, {"tier": "auto"})
        engine = MagicMock()
        engine.benchmark.side_effect = RuntimeError("probe exploded")

        from babelfish_stt.main import calibrate

        asyncio.run(
            calibrate(config_manager, engine, status=self._async_ok)
        )

        # Startup proceeds on the default profile rather than aborting
        defaults = PerformanceProfile()
        applied = config_manager.config.pipeline.performance
        assert applied.tier == defaults.tier
        assert applied.ghost_throttle_ms == defaults.ghost_throttle_ms


if __name__ == "__main__":
    unittest.main()
