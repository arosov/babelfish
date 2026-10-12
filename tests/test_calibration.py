"""
Startup self-calibration tests (ADR 0013, reworked): a real-speech probe
matrix (onset-aligned fixture slices, per-cell median, outlier rule)
picks the Ghost window from the measured cost curve and the tier/throttle
at that operating point; the bench runs once per acceleration backend,
is cached in the config file's `calibration` section keyed by a
resolved-device fingerprint, and every later launch is canary-checked
(one inference at the stored operating point, +/-25%) before reuse.
"""

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np

from babelfish_stt import calibration as cal
from babelfish_stt.calibration import (
    CANDIDATE_WINDOWS_S,
    ONSET_THRESHOLD,
    PROBES_PER_CELL,
    SAMPLE_RATE,
)
from babelfish_stt.config import (
    BabelfishConfig,
    CALIBRATION_SCHEMA_VERSION,
    CalibrationProfileEntry,
    HardwareConfig,
    PerformanceProfile,
)
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.engine import STTEngine
from babelfish_stt.placement import GpuDevice, HardwareFacts

FP = cal.fingerprint(
    backend="cuda:0",
    device_name="Test GPU (CUDA)",
    quantization=None,
    model_name="nemo-parakeet-tdt-0.6b-v3",
    weights_id="d34db33fcafe",
    schema_version=CALIBRATION_SCHEMA_VERSION,
    ort_version="1.30.0",
    onnx_asr_version="0.12.0",
)


# ---------------------------------------------------------------------------
# Pure functions: onset-aligned slicing, cohorts/outliers, window
# selection, tier boundaries/hysteresis, fingerprint.
# ---------------------------------------------------------------------------


def _synth_fixture(seconds: float, amp: float = 0.1) -> np.ndarray:
    """Synthetic fixture: `seconds` of audio with `amp` speech after 0.5s
    of leading silence."""
    audio = np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)
    onset = int(0.5 * SAMPLE_RATE)
    audio[onset:] = amp
    return audio


class TestOnsetSlicing(unittest.TestCase):
    def test_slice_skips_leading_silence(self):
        """Every probe cell contains speech: slicing is onset-aligned, so
        leading silence is skipped (finding 7 — onset slices can
        transcribe "", measuring a cheaper workload than intended)."""
        audio = _synth_fixture(3.0, amp=0.1)
        sl = cal.slice_window(audio, 1.0)
        self.assertGreater(np.abs(sl).max(), ONSET_THRESHOLD)
        # 1.0 s of speech from the onset, not silence + onset
        self.assertEqual(len(sl), int(1.0 * SAMPLE_RATE))
        self.assertAlmostEqual(sl[0], 0.1, places=5)

    def test_slice_clips_at_fixture_end(self):
        """A window longer than the remaining audio measures what exists;
        the cohort median absorbs the shorter cell."""
        audio = _synth_fixture(2.0)  # 1.5 s of speech after onset
        sl = cal.slice_window(audio, 3.0)
        self.assertEqual(len(sl), int(1.5 * SAMPLE_RATE))
        self.assertGreater(np.abs(sl).max(), ONSET_THRESHOLD)

    def test_all_silent_fixture_yields_empty_slice(self):
        """Degenerate edge: onset == len(audio) -> empty slice, never a
        silently cheaper speech probe."""
        audio = np.zeros(int(2.0 * SAMPLE_RATE), dtype=np.float32)
        self.assertEqual(len(cal.slice_window(audio, 1.0)), 0)


class TestColumnCohort(unittest.TestCase):
    def test_cohort_is_the_median_without_outliers(self):
        cohort, dropped = cal.column_cohort(
            {"a": 35.0, "b": 36.0, "c": 34.0, "d": 35.0, "e": 35.0}
        )
        self.assertEqual(cohort, 35.0)
        self.assertEqual(dropped, ())

    def test_outlier_cell_dropped_and_cohort_recomputed(self):
        """Any cell median > 2x its column's cohort is dropped (and
        surfaced so the caller logs it)."""
        cohort, dropped = cal.column_cohort(
            {"a": 35.0, "b": 36.0, "c": 34.0, "d": 35.0, "e": 300.0}
        )
        self.assertEqual(dropped, ("e",))
        self.assertEqual(cohort, 35.0)

    def test_cheap_cell_is_not_dropped(self):
        """Only upward outliers are dropped: a cheap cell (short fixture
        clipped below the window) is a legitimate measurement."""
        cohort, dropped = cal.column_cohort(
            {"a": 30.0, "b": 36.0, "c": 34.0, "d": 35.0, "e": 35.0}
        )
        self.assertEqual(dropped, ())
        self.assertEqual(cohort, 35.0)


class TestSelectWindow(unittest.TestCase):
    def test_flat_curve_picks_the_max_window(self):
        """A flat cost curve (CPU-shaped: per-call overhead bound) buys
        the largest window — small windows buy nothing."""
        for flat in (35.0, 170.0):
            cohorts = {w: flat for w in CANDIDATE_WINDOWS_S}
            self.assertEqual(cal.select_window(cohorts), 3.0)

    def test_cliff_curve_stays_below_the_cliff(self):
        """DML-shaped cliff (~57 ms at <=2.0 s, ~260 ms at >=2.3 s): the
        window lands at 2.0 s, NOT the 2.5 s a tier lookup would pick —
        the old table's window landed exactly in the slow regime."""
        cohorts = {1.0: 57.0, 1.5: 57.0, 2.0: 57.0, 2.5: 260.0, 3.0: 260.0}
        self.assertEqual(cal.select_window(cohorts), 2.0)

    def test_budget_caps_the_window(self):
        """A rising curve is capped by the budget: the largest window
        whose cohort stays <= max(budget, 1.5 x best)."""
        cohorts = {1.0: 100.0, 1.5: 140.0, 2.0: 180.0, 2.5: 220.0, 3.0: 260.0}
        # best=100 -> limit = max(200, 150) = 200 -> largest <= 200 is 2.0
        self.assertEqual(cal.select_window(cohorts), 2.0)

    def test_headroom_lets_a_uniformly_slow_backend_spread(self):
        """A uniformly slow backend (all cells 300 ms) is not pinned to
        the smallest window: the 1.5x-of-best headroom raises the limit
        above the budget."""
        cohorts = {w: 300.0 for w in CANDIDATE_WINDOWS_S}
        self.assertEqual(cal.select_window(cohorts), 3.0)


class TestTierBoundaries(unittest.TestCase):
    def test_boundary_table(self):
        """Boundaries anchored to the cadence each tier's throttle
        promises (~2x headroom), not to hardware classes: <50 ultra,
        <100 high, <200 medium, else low_power."""
        cases = [
            (49.9, "ultra", 100),
            (50.0, "high", 150),
            (99.9, "high", 150),
            (100.0, "medium", 250),
            (199.9, "medium", 250),
            (200.0, "low_power", 400),
            (400.0, "low_power", 400),
        ]
        for cost, tier, throttle in cases:
            self.assertEqual(cal.tier_for_cost(cost), tier, cost)
            self.assertEqual(cal.throttle_for_cost(cost), throttle, cost)

    def test_hysteresis_keeps_previous_label_near_boundary(self):
        """A re-bench landing within +/-15% of a boundary keeps the
        previous tier label (CPU straddles 200 ms across sessions)."""
        self.assertEqual(cal.tier_for_cost(205.0, previous_tier="medium"), "medium")
        self.assertEqual(cal.tier_for_cost(205.0, previous_tier="low_power"), "low_power")
        self.assertEqual(cal.tier_for_cost(95.0, previous_tier="ultra"), "ultra")
        # 60 ms is outside every hysteresis band: the table decides
        self.assertEqual(cal.tier_for_cost(60.0, previous_tier="ultra"), "high")

    def test_hysteresis_requires_a_previous_label(self):
        self.assertEqual(cal.tier_for_cost(205.0), "low_power")

    def test_throttle_takes_the_measured_operating_point_regardless(self):
        """The label is nearly cosmetic, the operating point is the
        product: a kept label does not keep the old throttle — the
        throttle follows the table at the newly measured cost."""
        self.assertEqual(cal.throttle_for_cost(205.0), 400)
        self.assertEqual(cal.tier_for_cost(205.0, previous_tier="medium"), "medium")


class TestFingerprint(unittest.TestCase):
    def _fp(self, **overrides):
        parts = dict(
            backend="cuda:0",
            device_name="Test GPU (CUDA)",
            quantization=None,
            model_name="nemo-parakeet-tdt-0.6b-v3",
            weights_id="d34db33fcafe",
            schema_version=CALIBRATION_SCHEMA_VERSION,
            ort_version="1.30.0",
            onnx_asr_version="0.12.0",
        )
        parts.update(overrides)
        return cal.fingerprint(**parts)

    def test_identical_inputs_give_identical_fingerprints(self):
        self.assertEqual(self._fp(), self._fp())

    def test_fingerprint_is_keyed_by_every_component(self):
        base = self._fp()
        variants = [
            self._fp(backend="cpu"),
            self._fp(device_name="Other GPU (CUDA)"),
            self._fp(quantization="int8"),
            self._fp(model_name="some-other-model"),
            self._fp(weights_id="deadbeef1234"),
            self._fp(weights_id=""),
            self._fp(schema_version=CALIBRATION_SCHEMA_VERSION + 1),
            self._fp(ort_version="1.29.0"),
            self._fp(onnx_asr_version="0.13.0"),
        ]
        for variant in variants:
            self.assertNotEqual(variant, base)


class TestWeightsIdentity(unittest.TestCase):
    """weights_identity gives the fingerprint its weights component
    (ADR 0014): the fp32 and redux cards can never share a cache key."""

    def setUp(self):
        import tempfile
        import shutil

        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def _card(self, name, files):
        d = Path(self._tmp) / name
        d.mkdir(parents=True)
        for fname, blob in files.items():
            (d / fname).write_bytes(blob)
        return d

    def test_missing_and_empty_dirs_yield_empty_identity(self):
        self.assertEqual(cal.weights_identity(None), "")
        self.assertEqual(cal.weights_identity(Path(self._tmp) / "nope"), "")
        empty = Path(self._tmp) / "empty"
        empty.mkdir()
        self.assertEqual(cal.weights_identity(empty), "")

    def test_identity_is_stable_for_identical_cards(self):
        files = {
            "config.json": b'{"x": 1}',
            "vocab.txt": b"abc",
            "encoder-model.onnx": b"\x00" * (16 * 1024 * 1024),
        }
        a = self._card("a", files)
        b = self._card("b", files)
        self.assertEqual(cal.weights_identity(a), cal.weights_identity(b))

    def test_big_file_size_change_rotates_the_identity(self):
        """The packed encoder (~344 MB redux / ~2.4 GB fp32) is identified
        by name + size: a different export has a different size, which is
        what separates the two cards. Files are created sparse via
        truncate() — only the name/size go into the digest, no GB reads."""
        def _card_with_size(name, size):
            d = Path(self._tmp) / name
            d.mkdir(parents=True)
            (d / "config.json").write_bytes(b'{"x": 1}')
            with open(d / "encoder-model.onnx", "wb") as f:
                f.truncate(size)
            return d

        a = _card_with_size("big_a", 344 * 1024 * 1024)
        b = _card_with_size("big_b", 2400 * 1024 * 1024)
        self.assertNotEqual(cal.weights_identity(a), cal.weights_identity(b))

    def test_small_file_content_change_rotates_the_identity(self):
        a = self._card(
            "a",
            {
                "config.json": b'{"x": 1}',
                "vocab.txt": b"abc",
                "encoder-model.onnx": b"\x00" * (16 * 1024 * 1024),
            },
        )
        b = self._card(
            "b",
            {
                "config.json": b'{"x": 2}',
                "vocab.txt": b"abc",
                "encoder-model.onnx": b"\x00" * (16 * 1024 * 1024),
            },
        )
        self.assertNotEqual(cal.weights_identity(a), cal.weights_identity(b))

    def test_fingerprint_collision_regression_fp32_vs_redux_cpu(self):
        """The measured prototype bug: an fp32 CPU bench and a redux CPU
        bench shared one weights-blind key, so the second silently
        overwrote the first. With the weights component the two
        fingerprints are distinct entries and both profiles survive a
        weights swap."""
        def _seed_card(name, files):
            d = Path(self._tmp) / name
            d.mkdir(parents=True)
            for fname, blob in files.items():
                (d / fname).write_bytes(blob)
            return d

        # fp32 v3: small files (hashable content) + big binaries (only
        # name+size enter the digest — no GB write/read in tests)
        fp32_card = _seed_card(
            "v3",
            {"config.json": b'{"name": "v3"}', "vocab.txt": b"abc"},
        )
        for fname, size in (
            ("encoder-model.onnx", 7 * 1024 * 1024),
            ("encoder-model.onnx.data", 2336 * 1024 * 1024),
            ("decoder_joint-model.onnx", 65 * 1024 * 1024),
        ):
            with open(fp32_card / fname, "wb") as f:
                f.truncate(size)

        redux_card = _seed_card(
            "redux",
            {"config.json": b'{"name": "redux"}', "vocab.txt": b"abc"},
        )
        for fname, size in (
            ("encoder-model.onnx", 344 * 1024 * 1024),
            ("decoder_joint-model.onnx", 73 * 1024 * 1024),
        ):
            with open(redux_card / fname, "wb") as f:
                f.truncate(size)

        common = dict(
            backend="cpu",
            device_name="CPU",
            quantization=None,
            model_name="nemo-parakeet-tdt-0.6b-v3",
            schema_version=CALIBRATION_SCHEMA_VERSION,
            ort_version="1.30.0",
            onnx_asr_version="0.12.0",
        )
        weights_fp32 = cal.weights_identity(fp32_card)
        weights_redux = cal.weights_identity(redux_card)
        fp32_fp = cal.fingerprint(weights_id=weights_fp32, **common)
        redux_fp = cal.fingerprint(weights_id=weights_redux, **common)

        self.assertNotEqual(weights_fp32, weights_redux)
        self.assertNotEqual(fp32_fp, redux_fp)
        # Both are cpu-keyed; the keys differ ONLY by the weights id
        self.assertEqual(
            fp32_fp.replace(weights_fp32, ""),
            redux_fp.replace(weights_redux, ""),
        )


# ---------------------------------------------------------------------------
# Engine benchmark: the probe matrix over mocked probe latency.
# ---------------------------------------------------------------------------


class _EngineMixin(unittest.TestCase):
    def _gpu_engine(self) -> STTEngine:
        with patch("onnx_asr.load_model"), patch(
            "babelfish_stt.engine.get_memory_usage"
        ) as mock_mem:
            mock_mem.return_value = {"total": 8.0, "used": 1.0}
            return STTEngine(
                config=BabelfishConfig(hardware=HardwareConfig(device="cuda"))
            )

    def _cpu_engine(self) -> STTEngine:
        with patch("onnx_asr.load_model"), patch(
            "babelfish_stt.engine.get_memory_usage"
        ):
            return STTEngine(
                config=BabelfishConfig(hardware=HardwareConfig(device="cpu"))
            )

    @staticmethod
    def _fake_measure(cost_for_duration):
        """_measure_latency_ms mock keyed on the audio the probe receives
        (its duration), so a fake shapes the whole window curve."""

        def measure(audio, padding_s=0.0):
            return float(cost_for_duration(len(audio) / SAMPLE_RATE))

        return measure


class TestBenchmarkMatrix(_EngineMixin):
    def test_cliff_curve_lands_below_the_cliff(self):
        """DML-shaped cost cliff: window 2.0 s / tier high — NOT the 2.5 s
        the old tier lookup picked straight into the slow regime."""
        engine = self._gpu_engine()
        with patch.object(
            engine, "_measure_latency_ms", self._fake_measure(
                lambda d: 57.0 if d <= 2.0 else 260.0
            )
        ), patch.object(engine, "transcribe", return_value=""):
            payload = engine.benchmark()

        self.assertEqual(payload["ghost_window_s"], 2.0)
        self.assertEqual(payload["tier"], "high")
        self.assertEqual(payload["ghost_throttle_ms"], 150)
        self.assertAlmostEqual(payload["operating_cost_ms"], 57.0)

    def test_flat_fast_curve_picks_max_window_ultra(self):
        """CUDA-shaped flat ~35 ms: max window, ultra, throttle 100."""
        engine = self._gpu_engine()
        with patch.object(
            engine, "_measure_latency_ms", self._fake_measure(lambda d: 35.0)
        ), patch.object(engine, "transcribe", return_value=""):
            payload = engine.benchmark()

        self.assertEqual(payload["ghost_window_s"], 3.0)
        self.assertEqual(payload["tier"], "ultra")
        self.assertEqual(payload["ghost_throttle_ms"], 100)
        self.assertEqual(payload["min_padding_s"], 2.0)
        self.assertEqual(payload["ghost_padding_s"], 1.0)

    def test_flat_cpu_curve_picks_max_window_medium(self):
        """CPU-shaped flat ~170 ms: the curve is flat, the window stays
        max; tier medium at the operating point."""
        engine = self._cpu_engine()
        with patch.object(
            engine, "_measure_latency_ms", self._fake_measure(lambda d: 170.0)
        ), patch.object(engine, "transcribe", return_value=""):
            payload = engine.benchmark()

        self.assertEqual(payload["ghost_window_s"], 3.0)
        self.assertEqual(payload["tier"], "medium")
        self.assertEqual(payload["ghost_throttle_ms"], 250)
        # min_padding is constant 2.0 (un-bundled from the tier: the old
        # table's low_power -> 1.0 was the ADR 0011-flagged bug)
        self.assertEqual(payload["min_padding_s"], 2.0)

    def test_flat_very_slow_curve_low_power(self):
        engine = self._cpu_engine()
        with patch.object(
            engine, "_measure_latency_ms", self._fake_measure(lambda d: 400.0)
        ), patch.object(engine, "transcribe", return_value=""):
            payload = engine.benchmark()

        self.assertEqual(payload["ghost_window_s"], 3.0)
        self.assertEqual(payload["tier"], "low_power")
        self.assertEqual(payload["ghost_throttle_ms"], 400)

    def test_probes_are_fixture_shaped_not_silence(self):
        """The silence probe is gone: every Ghost cell is an
        onset-aligned slice of a real-speech fixture, and the Final
        cells transcribe whole long fixtures."""
        engine = self._gpu_engine()
        probed = []

        def spy_measure(audio, padding_s=0.0):
            probed.append((len(audio), float(np.abs(audio).max()), padding_s))
            return 35.0

        with patch.object(engine, "_measure_latency_ms", spy_measure), \
                patch.object(engine, "transcribe", return_value=""):
            engine.benchmark()

        ghost_probes = [p for p in probed if p[2] == 0.0]
        final_probes = [p for p in probed if p[2] == 2.0]
        # Ghost cells: 5 fixtures x 5 windows x 3 probes, all with speech
        self.assertEqual(len(ghost_probes), 5 * len(CANDIDATE_WINDOWS_S) * PROBES_PER_CELL)
        for samples, peak, _ in ghost_probes:
            self.assertGreater(peak, ONSET_THRESHOLD)
            self.assertLessEqual(samples, int(3.0 * SAMPLE_RATE))
        # Final cells: the 4 fixtures longer than 2.6 s, full length,
        # at the Final-pass padding protocol
        self.assertEqual(len(final_probes), 4)
        for samples, peak, _ in final_probes:
            self.assertGreater(peak, ONSET_THRESHOLD)
        self.assertAlmostEqual(
            max(samples for samples, _, _ in final_probes) / SAMPLE_RATE, 18.57, places=1
        )

    def test_probe_protocol_counts_warmups_and_probes(self):
        """Per cell 1 discarded warm-up + 3 timed probes; 25 Ghost cells
        + 4 Final passes. The warm-up goes through transcribe (untimed)."""
        engine = self._gpu_engine()
        with patch.object(
            engine,
            "_measure_latency_ms",
            side_effect=self._fake_measure(lambda d: 35.0),
        ) as mock_measure, patch.object(
            engine, "transcribe", return_value=""
        ) as mock_transcribe:
            engine.benchmark()

        self.assertEqual(
            mock_measure.call_count,
            5 * len(CANDIDATE_WINDOWS_S) * PROBES_PER_CELL + 4,
        )
        # transcribe calls = the 25 discarded Ghost warm-ups + the 4
        # discarded Final warm-ups (the probes route through the mocked
        # _measure_latency_ms)
        self.assertEqual(mock_transcribe.call_count, 29)

    def test_spiky_probe_median_robust(self):
        """One 600 ms spike among a cell's 3 probes cannot demote the
        tier: the cell value is the median (ADR 0011's measurement
        robustness, kept)."""
        engine = self._gpu_engine()
        call = {"n": 0}

        def spiky_measure(audio, padding_s=0.0):
            call["n"] += 1
            # Spike every 3rd probe (the last probe of each cell)
            return 600.0 if call["n"] % PROBES_PER_CELL == 0 else 35.0

        with patch.object(engine, "_measure_latency_ms", spiky_measure), \
                patch.object(engine, "transcribe", return_value=""):
            payload = engine.benchmark()

        self.assertEqual(payload["tier"], "ultra")
        self.assertEqual(payload["ghost_throttle_ms"], 100)

    def test_outlier_fixture_dropped_and_logged(self):
        """A fixture measuring >2x its column's cohort is dropped and
        logged; the cohort (and the resulting operating point) is
        computed from the survivors."""
        engine = self._gpu_engine()
        # Synthetic fixtures distinguished by speech amplitude, so the
        # fake can slow exactly one of them
        fixtures = {
            name: _synth_fixture(seconds, amp=amp)
            for name, seconds, amp in [
                ("a", 3.0, 0.1),
                ("b", 3.2, 0.2),
                ("c", 3.4, 0.3),
                ("d", 3.6, 0.4),
                ("e", 3.8, 0.5),
            ]
        }

        def measure(audio, padding_s=0.0):
            amp = float(np.abs(audio).max())
            return 300.0 if abs(amp - 0.5) < 1e-6 else 35.0

        with patch(
            "babelfish_stt.engine.load_calibration_fixtures",
            return_value=fixtures,
        ), patch.object(engine, "_measure_latency_ms", measure), \
                patch.object(engine, "transcribe", return_value=""):
            import logging

            with self.assertLogs("babelfish_stt.engine", level="WARNING") as logs:
                payload = engine.benchmark()

        self.assertTrue(any("outlier dropped: e" in line for line in logs.output))
        # Cohort from survivors -> flat-35 curve shape: max window, ultra
        self.assertEqual(payload["ghost_window_s"], 3.0)
        self.assertEqual(payload["tier"], "ultra")
        self.assertAlmostEqual(payload["operating_cost_ms"], 35.0)

    def test_hysteresis_applied_through_benchmark(self):
        """benchmark(previous_tier=...) keeps a boundary-straddling
        label; the throttle still takes the measured operating point."""
        engine = self._cpu_engine()
        with patch.object(
            engine, "_measure_latency_ms", self._fake_measure(lambda d: 210.0)
        ), patch.object(engine, "transcribe", return_value=""):
            kept = engine.benchmark(previous_tier="medium")
            fresh = engine.benchmark()

        self.assertEqual(kept["tier"], "medium")  # 210 within +/-15% of 200
        self.assertEqual(kept["ghost_throttle_ms"], 400)  # table at 210
        self.assertEqual(fresh["tier"], "low_power")
        self.assertEqual(fresh["ghost_throttle_ms"], 400)

    def test_raising_probe_surfaces_from_benchmark(self):
        """A probe failure propagates out of benchmark(); the calibrate()
        wrapper converts it to PerformanceProfile() defaults and
        persists nothing."""
        engine = self._cpu_engine()

        def _raising_probe(*args, **kwargs):
            raise RuntimeError("probe exploded")

        with patch.object(engine, "_measure_latency_ms", _raising_probe):
            with self.assertRaises(RuntimeError):
                engine.benchmark()

    def test_broken_dml_request_lands_on_cpu_fingerprint(self):
        """Request dml with the DML provider missing: the resolved
        device is cpu, and the fingerprint is keyed by what actually
        runs — a driver-broken launch can't poison a dml entry."""
        with patch(
            "babelfish_stt.hardware.probe_hardware_facts",
            return_value=HardwareFacts(
                providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
                gpus=(GpuDevice("cuda:0", "Test GPU", 8.0),),
            ),
        ), patch("onnx_asr.load_model"), patch(
            "babelfish_stt.engine.get_memory_usage"
        ):
            engine = STTEngine(
                config=BabelfishConfig(hardware=HardwareConfig(device="dml"))
            )

        self.assertEqual(engine.device_type, "cpu")
        self.assertTrue(engine.calibration_fingerprint().startswith("cpu|"))

    def test_resolved_dml_device_fingerprints_as_dml(self):
        with patch(
            "babelfish_stt.hardware.probe_hardware_facts",
            return_value=HardwareFacts(
                providers=("DmlExecutionProvider", "CPUExecutionProvider"),
                gpus=(GpuDevice("dml:0", "Test DML GPU", 8.0),),
            ),
        ), patch("onnx_asr.load_model"), patch(
            "babelfish_stt.engine.get_memory_usage"
        ):
            engine = STTEngine(
                config=BabelfishConfig(hardware=HardwareConfig(device="dml"))
            )

        self.assertEqual(engine.device_type, "dml:0")
        self.assertTrue(engine.calibration_fingerprint().startswith("dml:0|"))

    def test_canary_probe_warms_up_then_measures_once(self):
        """The canary is the session's first inference on a cache hit:
        one discarded warm-up, then one timed probe at the stored
        window."""
        engine = self._gpu_engine()
        with patch.object(
            engine, "_measure_latency_ms", return_value=57.0
        ) as mock_measure, patch.object(
            engine, "transcribe", return_value=""
        ) as mock_transcribe:
            canary_ms = engine.canary_probe(2.0)

        self.assertEqual(canary_ms, 57.0)
        mock_measure.assert_called_once()
        # The discarded warm-up went through transcribe
        self.assertEqual(mock_transcribe.call_count, 1)
        probed_audio = mock_measure.call_args[0][0]
        self.assertGreater(float(np.abs(probed_audio).max()), ONSET_THRESHOLD)
        self.assertLessEqual(len(probed_audio), int(2.0 * SAMPLE_RATE))


# ---------------------------------------------------------------------------
# The calibrate() flow: bench once per backend, canary every launch.
# ---------------------------------------------------------------------------


def _payload(tier="high", throttle=150, window=2.0, cost=57.3, rtfx=45.0):
    return {
        "tier": tier,
        "ghost_throttle_ms": throttle,
        "ghost_window_s": window,
        "ghost_padding_s": 1.0,
        "min_padding_s": 2.0,
        "operating_cost_ms": cost,
        "final_rtfx": rtfx,
        "cells": {"multiple_words": {"1.0": 57.8, "2.0": 58.4, "3.0": 57.9}},
    }


def _seed_entry(tier="high", throttle=150, window=2.0, cost=57.3, benched_at="2026-10-05T00:00:00+00:00"):
    return {
        "tier": tier,
        "ghost_throttle_ms": throttle,
        "ghost_window_s": window,
        "ghost_padding_s": 1.0,
        "min_padding_s": 2.0,
        "operating_cost_ms": cost,
        "final_rtfx": 45.0,
        "cells": {"multiple_words": {"1.0": 57.8, "2.0": 58.4, "3.0": 57.9}},
        "benched_at": benched_at,
    }


class TestCalibrateCache:
    """Miss -> bench -> persist; hit + canary-pass -> zero matrix probes;
    hit + canary-deviation -> re-bench + overwrite; stale schema -> miss;
    prune at cap; raising probe -> defaults, nothing persisted."""

    @staticmethod
    async def _async_ok(message: str):
        return None

    def _config_manager(self, tmp_path, calibration=None):
        config_file = tmp_path / "config.json"
        data = {"hardware": {"device": "cpu"}}
        if calibration is not None:
            data["calibration"] = calibration
        config_file.write_text(json.dumps(data))
        return ConfigManager(config_path=str(config_file))

    def _engine(self, fingerprint=FP, payload=None, canary_ms=None):
        engine = MagicMock()
        engine.calibration_fingerprint.return_value = fingerprint
        engine.benchmark.return_value = payload or _payload()
        if canary_ms is not None:
            engine.canary_probe.return_value = canary_ms
        return engine

    def _calibrate(self, engine, config_manager):
        from babelfish_stt.main import calibrate

        return asyncio.run(calibrate(engine, config_manager, status=self._async_ok))

    def _stored(self, config_manager):
        return config_manager.config.calibration.profiles

    def test_miss_benches_persists_and_returns_profile(self, tmp_path):
        config_manager = self._config_manager(tmp_path)
        engine = self._engine()

        profile = self._calibrate(engine, config_manager)

        engine.benchmark.assert_called_once_with(previous_tier=None)
        engine.canary_probe.assert_not_called()
        stored = self._stored(config_manager)[FP]
        assert stored.tier == "high"
        assert stored.ghost_window_s == 2.0
        assert stored.operating_cost_ms == 57.3
        assert stored.final_rtfx == 45.0
        assert stored.cells["multiple_words"]["2.0"] == 58.4
        assert stored.benched_at
        # The persisted file carries the entry under `calibration`
        data = json.loads(config_manager.config_path.read_text())
        assert FP in data["calibration"]["profiles"]
        assert data["calibration"]["schema_version"] == CALIBRATION_SCHEMA_VERSION
        # And the profile is the entry's operating point
        assert profile.tier == "high"
        assert profile.ghost_throttle_ms == 150
        assert profile.ghost_window_s == 2.0

    def test_hit_with_canary_within_tolerance_returns_stored(self, tmp_path):
        """Cache hit: one canary inference at the stored operating point
        (the canary fixture's own cell), zero matrix probes."""
        config_manager = self._config_manager(
            tmp_path,
            calibration={
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "profiles": {FP: _seed_entry()},
            },
        )
        # multiple_words @2.0 cell is 58.4; within 25% either way passes
        engine = self._engine(canary_ms=50.0)

        profile = self._calibrate(engine, config_manager)

        engine.canary_probe.assert_called_once_with(2.0)
        engine.benchmark.assert_not_called()
        assert profile.tier == "high"
        assert profile.ghost_throttle_ms == 150
        # Nothing changed on disk (no re-bench, no rewrite)
        data = json.loads(config_manager.config_path.read_text())
        assert data["calibration"]["profiles"][FP]["benched_at"] == (
            "2026-10-05T00:00:00+00:00"
        )

    def test_hit_with_canary_deviation_rebenches_and_overwrites(self, tmp_path):
        """Canary beyond tolerance (symmetric — a much-faster session is
        also a regime flip): full re-bench that launch, entry
        overwritten."""
        config_manager = self._config_manager(
            tmp_path,
            calibration={
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "profiles": {FP: _seed_entry()},
            },
        )
        engine = self._engine(
            payload=_payload(tier="ultra", throttle=100, window=3.0, cost=35.0),
            canary_ms=260.0,  # 4.4x the stored cell — way outside 25%
        )

        profile = self._calibrate(engine, config_manager)

        engine.benchmark.assert_called_once_with(previous_tier="high")
        stored = self._stored(config_manager)[FP]
        assert stored.tier == "ultra"
        assert stored.ghost_window_s == 3.0
        assert profile.tier == "ultra"

    def test_rebench_passes_previous_tier_for_hysteresis(self, tmp_path):
        """The flow hands the stored label to benchmark so a
        boundary-straddling backend keeps its tier label (the engine
        side of the hysteresis is covered in TestBenchmarkMatrix)."""
        config_manager = self._config_manager(
            tmp_path,
            calibration={
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "profiles": {FP: _seed_entry(tier="medium", window=3.0)},
            },
        )
        engine = self._engine(canary_ms=999.0)  # deviates

        self._calibrate(engine, config_manager)

        engine.benchmark.assert_called_once_with(previous_tier="medium")

    def test_stale_store_schema_version_misses(self, tmp_path):
        """A store written by an older bench schema is ignored entirely:
        the fingerprint may match, the matrix still runs."""
        config_manager = self._config_manager(
            tmp_path,
            calibration={
                "schema_version": 0,
                "profiles": {FP: _seed_entry()},
            },
        )
        engine = self._engine(canary_ms=57.0)

        profile = self._calibrate(engine, config_manager)

        engine.benchmark.assert_called_once_with(previous_tier=None)
        assert profile.tier == "high"

    def test_prune_at_cap_oldest_first(self, tmp_path):
        """The store is capped at 4 entries (one per acceleration
        backend), pruned oldest-first by benched_at."""
        from babelfish_stt.calibration import CALIBRATION_PROFILES_CAP

        seeded = {
            f"cpu{i}|old": _seed_entry(
                benched_at=f"2026-10-0{i + 1}T00:00:00+00:00"
            )
            for i in range(CALIBRATION_PROFILES_CAP)
        }
        config_manager = self._config_manager(
            tmp_path,
            calibration={"schema_version": CALIBRATION_SCHEMA_VERSION, "profiles": seeded},
        )
        engine = self._engine()  # a distinct fingerprint

        self._calibrate(engine, config_manager)

        stored = self._stored(config_manager)
        assert len(stored) == CALIBRATION_PROFILES_CAP
        assert "cpu0|old" not in stored  # oldest pruned
        assert FP in stored  # the new bench kept

    def test_raising_benchmark_defaults_and_persists_nothing(self, tmp_path):
        config_manager = self._config_manager(tmp_path)
        engine = self._engine()
        engine.benchmark.side_effect = RuntimeError("probe exploded")

        profile = self._calibrate(engine, config_manager)

        defaults = PerformanceProfile()
        assert profile.ghost_throttle_ms == defaults.ghost_throttle_ms
        assert profile.ghost_window_s == defaults.ghost_window_s
        assert profile.tier == defaults.tier
        assert self._stored(config_manager) == {}
        # No file was written with calibration output
        data = json.loads(config_manager.config_path.read_text())
        assert "calibration" not in data

    def test_raising_canary_defaults_and_persists_nothing(self, tmp_path):
        config_manager = self._config_manager(
            tmp_path,
            calibration={"schema_version": CALIBRATION_SCHEMA_VERSION, "profiles": {FP: _seed_entry()}},
        )
        engine = self._engine()
        engine.canary_probe.side_effect = RuntimeError("canary exploded")

        profile = self._calibrate(engine, config_manager)

        assert profile.tier == PerformanceProfile().tier
        assert self._stored(config_manager)[FP].tier == "high"  # untouched

    def test_broken_dml_request_persists_only_cpu_entry(self, tmp_path):
        """Acceptance: request dml with DML missing -> the fingerprint
        lands on cpu; no dml-keyed entry is ever written."""
        with patch(
            "babelfish_stt.hardware.probe_hardware_facts",
            return_value=HardwareFacts(
                providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
                gpus=(GpuDevice("cuda:0", "Test GPU", 8.0),),
            ),
        ), patch("onnx_asr.load_model"), patch(
            "babelfish_stt.engine.get_memory_usage"
        ):
            engine = STTEngine(
                config=BabelfishConfig(hardware=HardwareConfig(device="dml"))
            )

        config_manager = self._config_manager(tmp_path)
        with patch.object(engine, "benchmark", return_value=_payload()) as mock_bench:
            self._calibrate(engine, config_manager)

        mock_bench.assert_called_once()
        stored = self._stored(config_manager)
        assert len(stored) == 1
        fingerprint = next(iter(stored))
        assert fingerprint.startswith("cpu|"), fingerprint


if __name__ == "__main__":
    unittest.main()
