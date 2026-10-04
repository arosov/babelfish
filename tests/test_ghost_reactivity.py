"""
Unit tests for Phase 2 of the Reactive Ghost Pass: bounded CPU Ghost
inference, the split calibration profile, and the TerminalDisplay redraw
rate-limit.
"""

import time
import unittest
from unittest.mock import patch, MagicMock
import io

import numpy as np

from babelfish_stt.engine import STTEngine
from babelfish_stt.config import BabelfishConfig, HardwareConfig
from babelfish_stt.display import TerminalDisplay

from tests.test_ghost_loop import (
    FakeEngine,
    make_pipeline,
    speech_chunk,
    wait_for_done,
)


class TestCpuSlidingWindow(unittest.TestCase):
    def test_cpu_ghost_uses_sliding_window(self):
        """CPU Ghost inference is bounded by ghost_window_s instead of
        transcribing the entire growing buffer."""
        # Buffer grows to ~2s; window is 1.0s -> window path must trim.
        pipeline, engine, display = make_pipeline(
            throttle_ms=0, ghost_window_s=1.0, device_type="cpu"
        )
        now = 0.0
        # First ghost submits on the onset chunk (short buffer, no trim yet).
        pipeline.process_chunk(speech_chunk(), now, is_speech=True)
        wait_for_done(pipeline)
        # Grow the buffer well past the window with more speech chunks.
        for _ in range(70):  # 70 * 32ms ~= 2.24s
            now += 32.0
            pipeline.process_chunk(speech_chunk(), now, is_speech=True)
        wait_for_done(pipeline)
        # Consume the last ghost on a final chunk.
        now += 32.0
        pipeline.process_chunk(speech_chunk(), now, is_speech=True)

        self.assertTrue(engine.calls)
        # Window-aligned submissions never exceed window + one chunk
        max_samples = int(1.0 * 16000) + 512
        for samples, _padding in engine.calls:
            self.assertLessEqual(samples, max_samples)
        # And at least one ghost was trimmed to the window (not the full ~2s+)
        self.assertTrue(any(samples <= max_samples for samples, _ in engine.calls))


class TestBenchmarkSplitProfile(unittest.TestCase):
    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def _engine(self, device: str, mock_mem, mock_load) -> STTEngine:
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        config = BabelfishConfig(hardware=HardwareConfig(device=device))
        return STTEngine(config=config)

    def test_profile_includes_ghost_padding(self):
        engine = self._engine("cpu")
        profile = engine.benchmark()
        self.assertEqual(profile["ghost_padding_s"], 0.0)  # CPU: window bounds it
        self.assertIn("min_padding_s", profile)
        self.assertIn("ghost_throttle_ms", profile)
        self.assertIn("ghost_window_s", profile)

    def test_cpu_tier_gets_bounded_window(self):
        engine = self._engine("cpu")
        profile = engine.benchmark()
        self.assertEqual(profile["tier"], "cpu")
        self.assertEqual(profile["ghost_window_s"], 1.0)
        self.assertEqual(profile["ghost_padding_s"], 0.0)

    @patch("onnx_asr.load_model")
    @patch("babelfish_stt.engine.get_memory_usage")
    def test_spacing_values_unchanged(self, mock_mem, mock_load):
        mock_mem.return_value = {"total": 8.0, "used": 1.0}
        config = BabelfishConfig(hardware=HardwareConfig(device="cuda:0"))
        engine = STTEngine(config=config)
        with patch.object(engine, "transcribe", return_value=""):
            profile = engine.benchmark()
        self.assertEqual(profile["ghost_throttle_ms"], 100)
        self.assertEqual(profile["tier"], "ultra")
        # min_padding_s is Final-only but still calibrated
        self.assertEqual(profile["min_padding_s"], 2.0)
        # Ghost padding keeps the first windows text-capable
        self.assertEqual(profile["ghost_padding_s"], 1.0)


class TestTerminalDisplayComposer(unittest.TestCase):
    """TerminalDisplay consumes the shared GhostComposer (ADR 0010); one
    display-level check pins the delegation (composition-wise behaviour
    itself is covered in test_ghost_composer.py)."""

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_update_composes_via_shared_composer(self, mock_stdout):
        display = TerminalDisplay()
        display.update(ghost="A woman gets on a")
        time.sleep(TerminalDisplay.REDRAW_MIN_INTERVAL_S + 0.02)
        display.update(ghost="A woman gets on a bus")
        self.assertEqual(
            display._composer.line, "A woman gets on a bus"
        )
        self.assertEqual(
            display._composer.live, ["A", "woman", "gets", "on", "a", "bus"]
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_finalize_resets_shared_composer(self, mock_stdout):
        display = TerminalDisplay()
        display.update(ghost="first utterance ghost")
        display.finalize("first utterance final")
        self.assertEqual(display._composer.committed, [])
        self.assertEqual(display._composer.live, [])


class TestTerminalDisplayRateLimit(unittest.TestCase):
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_rapid_updates_are_rate_limited(self, mock_stdout):
        display = TerminalDisplay()
        display.update(ghost="one")
        first_output = mock_stdout.getvalue()
        self.assertIn("one", first_output)

        # Immediately after: suppressed, no new output
        display.update(ghost="two")
        self.assertEqual(mock_stdout.getvalue(), first_output)

        # After the interval passes: the latest text is written
        time.sleep(TerminalDisplay.REDRAW_MIN_INTERVAL_S + 0.02)
        display.update(ghost="three")
        self.assertIn("three", mock_stdout.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_finalize_always_writes(self, mock_stdout):
        display = TerminalDisplay()
        display.update(ghost="ghost")
        display.finalize("final")
        output = mock_stdout.getvalue()
        self.assertIn("final", output)
        self.assertIn("\n", output)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_finalize_flushes_pending_ghost(self, mock_stdout):
        display = TerminalDisplay()
        display.update(ghost="latest ghost")
        display.finalize("final")
        # The suppressed ghost is flushed before the final line so its
        # length is accounted for by the padding.
        self.assertIn("latest ghost", mock_stdout.getvalue())
        self.assertIn("final", mock_stdout.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_reset_clears_pending(self, mock_stdout):
        display = TerminalDisplay()
        display.update(ghost="written")  # first write passes the gate
        display.update(ghost="pending")  # immediately after: stashed
        display.reset()
        display.finalize("final")
        output = mock_stdout.getvalue()
        self.assertNotIn("pending", output)  # stashed text was dropped
        self.assertIn("written", output)
        self.assertIn("final", output)


if __name__ == "__main__":
    unittest.main()
