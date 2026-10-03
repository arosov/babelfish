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


class TestGhostComposition(unittest.TestCase):
    """Ghost updates compose incrementally in the terminal: window updates
    append instead of overwriting, and mid-window rewrites replace cleanly."""

    def _update(self, display: TerminalDisplay, ghost: str):
        """Update and wait out the redraw gate so the write lands."""
        display.update(ghost=ghost)
        time.sleep(TerminalDisplay.REDRAW_MIN_INTERVAL_S + 0.02)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_ghost_appends_across_window_slides(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "A woman gets on a")
        self._update(display, "A woman gets on a bus")  # pure append
        self._update(display, "gets on a bus with her")  # window slid past "A woman"
        self._update(display, "on a bus with her baby.")  # slid further
        self.assertEqual(display.last_text, "A woman gets on a bus with her baby.")
        self.assertIn("A woman gets on a bus with her baby.", mock_stdout.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_partial_rewrite_replaces_tail(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "A woman gets on a bus with her")
        # Model revises "a" -> "the" inside the window and appends
        self._update(display, "on the bus with her baby.")
        self.assertEqual(display.last_text, "A woman gets on the bus with her baby.")
        out = mock_stdout.getvalue()
        self.assertIn("A woman gets on the bus with her baby.", out)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_total_rewording_replaces_instead_of_duplicating(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "But then he said.")
        # Model re-words the whole window: nothing may be committed, the
        # new Ghost replaces the line (no "But But then indeed").
        self._update(display, "But then indeed")
        self.assertEqual(display.last_text, "But then indeed")
        self.assertEqual(display._ghost_committed, [])
        self.assertNotIn("But But", mock_stdout.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_weak_alignment_commits_nothing(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "I think I used to be a little bit")
        # New ghost shares almost nothing with the previous one: even though
        # it is shorter, no head words may be committed (they would be
        # re-covered by the new Ghost and duplicated).
        self._update(display, "Are you")
        self.assertEqual(display._ghost_committed, [])
        # The live tail is replaced wholesale by the new Ghost
        self.assertEqual(display.last_text, "Are you")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_committed_words_survive_rewrites(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "A woman gets on a")
        self._update(display, "gets on a bus with her")  # commits "A woman"
        self.assertEqual(display._ghost_committed, ["A", "woman"])
        # Even a fully different-looking update cannot rewrite committed text
        self._update(display, "with her monkey")
        self.assertEqual(display.last_text, "A woman gets on a bus with her monkey")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_finalize_keeps_ghost_line_with_final_below(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "A woman gets on a bus")
        display.finalize("A woman gets on a bus with her baby.")
        out = mock_stdout.getvalue()
        # Ghost line stays visible (dim), Final below it (bold)
        self.assertIn("\033[2mA woman gets on a bus\033[0m", out)
        self.assertIn("\033[1mA woman gets on a bus with her baby.\033[0m", out)
        self.assertLess(
            out.index("\033[2mA woman gets on a bus"),
            out.index("\033[1mA woman gets on a bus with her baby."),
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_finalize_resets_composition(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "first utterance ghost")
        display.finalize("first utterance final")
        self.assertEqual(display._ghost_committed, [])
        self.assertEqual(display._ghost_live, [])
        # Next utterance composes fresh
        self._update(display, "second")
        self.assertEqual(display.last_text, "second")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_composition_advances_while_rate_limited(self, mock_stdout):
        display = TerminalDisplay()
        display.update(ghost="one")  # written
        display.update(ghost="one two")  # rate-limited, but composed
        self.assertEqual(display._ghost_live, ["one", "two"])
        # The stashed pending update carries the composed text
        self.assertEqual(display._pending_update[2], "one two")


class TestWindowComposition(unittest.TestCase):
    """Window-aware commits: the pipeline reports each Ghost's audio
    coverage, so the boundary is pinned by audio time when the model
    re-words the shared region."""

    def _update(self, display: TerminalDisplay, ghost: str, window):
        display.update(ghost=ghost, window=window)
        time.sleep(TerminalDisplay.REDRAW_MIN_INTERVAL_S + 0.02)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_growing_window_commits_nothing(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "hello world", (0, 5120))
        # Window still starts at 0 (growing): everything stays live
        self._update(display, "hello world foo", (0, 16000))
        self.assertEqual(display._ghost_committed, [])
        self.assertEqual(display.last_text, "hello world foo")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_slide_commits_aged_out_head(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "hello world foo", (0, 16000))
        # Window start slid 5120 samples into a 16000-sample window:
        # ~1 of 3 words ages out.
        self._update(display, "world foo bar", (5120, 21120))
        self.assertEqual(display._ghost_committed, ["hello"])
        self.assertEqual(display.last_text, "hello world foo bar")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_reworded_slide_commits_by_audio_time(self, mock_stdout):
        """The model re-words the shared region completely: the text
        alignment fails, but audio time still commits the aged-out head
        (losing the utterance opening is worse than a rough guess)."""
        display = TerminalDisplay()
        self._update(display, "hello world foo", (0, 16000))
        self._update(display, "une crise qui s'aggrave", (5120, 21120))
        self.assertEqual(display._ghost_committed, ["hello"])
        self.assertEqual(display.last_text, "hello une crise qui s'aggrave")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_text_alignment_pins_boundary_over_proportional(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "one two three four five", (0, 16000))
        # Window slid a lot (2/3 of the window) but the text alignment says
        # only the first word aged out — the new Ghost re-covers the rest
        # (e.g. silence grew the buffer, not speech).
        self._update(display, "two three four five six", (10666, 26666))
        self.assertEqual(display._ghost_committed, ["one"])
        self.assertEqual(display.last_text, "one two three four five six")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_empty_ghost_does_not_advance_window(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "hello world", (0, 5120))
        # An empty Ghost result must not advance the window state, or the
        # next commit would age out words for audio that has no words yet.
        display.update(ghost="", window=(5120, 10240))
        self.assertEqual(display._ghost_live, ["hello", "world"])
        self.assertEqual(display._ghost_window, (0, 5120))

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_overcommit_is_deduped(self, mock_stdout):
        """A rough proportional commit that reaches into audio the new Ghost
        still re-covers is trimmed back: no duplicate phrases pile up, and
        the words are not lost (the live tail shows them)."""
        display = TerminalDisplay()
        self._update(display, "hello world foo", (0, 16000))
        # New ghost re-covers "world foo" (boundary over-committed "world"):
        self._update(display, "world foo bar", (10240, 26240))
        self.assertEqual(display._ghost_committed, ["hello"])
        self.assertEqual(display.last_text, "hello world foo bar")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_dedup_does_not_touch_clean_commits(self, mock_stdout):
        display = TerminalDisplay()
        self._update(display, "hello world", (0, 5120))
        # Clean slide: committed tail and new head are different audio
        self._update(display, "world goodbye", (2560, 13120))
        self.assertEqual(display._ghost_committed, ["hello"])
        self.assertEqual(display.last_text, "hello world goodbye")


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
