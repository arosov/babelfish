"""
InputManager and InputSimulator unit tests.

These tests verify the InputSimulator's ghost text handling (span-based
composition via the shared GhostComposer, ADR 0010), backspacing, and
finalization behavior.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from babelfish_stt.input_manager import InputSimulator
from babelfish_stt.config import SeparatorPolicy
from pynput.keyboard import Key


@pytest.fixture
def mock_keyboard():
    return MagicMock()


@pytest.fixture
def simulator(mock_keyboard):
    return InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)


@pytest.fixture
def throttled_simulator(mock_keyboard):
    return InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.1)


@pytest.fixture
def mock_pyperclip():
    """Ghost and Final text are injected via the clipboard; keep tests hermetic."""
    with patch("babelfish_stt.input_strategies.pyperclip") as m:
        yield m


def _backspace_calls(mock_keyboard):
    """Press calls that are actual backspace keystrokes."""
    return [
        c for c in mock_keyboard.press.call_args_list
        if c.args and c.args[0] == Key.backspace
    ]


def test_typing_throttle_default_matches_the_proven_regime():
    """The worker's apply pacing defaults to the proven-good live regime
    (~400ms-apart typed updates), not the flood regime: unpaced 50ms
    applies at the calibrated submit cadence are where editors drop
    synthesized keystrokes."""
    from babelfish_stt.input_manager import TYPING_THROTTLE_S

    sim = InputSimulator(keyboard_controller=MagicMock())
    assert sim.throttle_s == TYPING_THROTTLE_S
    assert 0.2 <= TYPING_THROTTLE_S <= 0.45
    sim.stop()


class TestGhostTextBehavior:
    """Tests for ghost text update behavior (compose, throttle, re-paste)."""

    def test_ghost_timing_respects_throttle(
        self, throttled_simulator, mock_keyboard, mock_pyperclip
    ):
        """Ghost updates should be throttled to prevent overwhelming the system."""
        import time

        throttled_simulator.update_ghost("hello")
        pastes_1 = mock_pyperclip.copy.call_count

        time.sleep(0.06)  # Wait slightly more than half the throttle
        throttled_simulator.update_ghost("hello w")
        pastes_2 = mock_pyperclip.copy.call_count

        time.sleep(0.06)  # Cumulative ~120ms since the last paste
        throttled_simulator.update_ghost("hello wo")
        pastes_3 = mock_pyperclip.copy.call_count

        assert pastes_1 == 1
        # Within the 100ms throttle window -> suppressed
        assert pastes_2 == pastes_1
        # Past the throttle window -> re-pasted
        assert pastes_3 == pastes_2 + 1

    def test_ghost_replacement_clears_and_repastes(
        self, simulator, mock_keyboard, mock_pyperclip
    ):
        """A changed ghost erases only the changed suffix and re-pastes
        the delta + unchanged tail (append-diff typing)."""
        import grapheme

        simulator.update_ghost("hello world")
        mock_keyboard.reset_mock()
        mock_pyperclip.reset_mock()

        simulator.update_ghost("hello there")

        # "hello" is kept: the erase removes " world" (space + word,
        # from the old line) and " there" re-supplies the separator
        assert len(_backspace_calls(mock_keyboard)) == 6
        mock_pyperclip.copy.assert_called_once_with(" there")
        assert simulator.last_ghost_length == len(
            list(grapheme.graphemes("hello there"))
        )

    # The fuzzy word-stitching tests were deleted with the heuristic path
    # (ADR 0010); composition behaviour now lives in the shared
    # GhostComposer — see test_ghost_composer.py.

    def test_ghost_handles_unicode_graphemes(self, simulator, mock_keyboard):
        """Unicode characters should be handled as single graphemes."""
        simulator.update_ghost("café")

        assert simulator.last_ghost_length == 4

        mock_keyboard.reset_mock()
        simulator.update_ghost("café test")

        try:
            import grapheme

            expected = len(list(grapheme.graphemes("café test")))
        except ImportError:
            expected = len("café test")

        assert simulator.last_ghost_length == expected

    def test_ghost_empty_string_clears_state(self, simulator, mock_keyboard):
        """Empty ghost text should clear state without errors."""
        simulator.update_ghost("some text")
        assert simulator.last_ghost_length > 0

        simulator.update_ghost("")
        assert simulator.last_ghost_length == 0


class TestFinalizeBehavior:
    """Tests for text finalization and injection."""

    def test_finalize_adds_spacing_between_utterances(
        self, simulator, mock_keyboard, mock_pyperclip
    ):
        """Under the default trailing policy, each Final carries its own space."""
        simulator.finalize("hello")
        mock_pyperclip.copy.assert_called_with("hello ")

        mock_pyperclip.reset_mock()
        simulator.finalize("world")
        mock_pyperclip.copy.assert_called_with("world ")

    def test_finalize_policy_matrix(
        self, simulator, mock_keyboard, mock_pyperclip
    ):
        """Pin the spacing behavior of each separator policy."""
        from babelfish_stt.config import SeparatorPolicy

        # Default (no kwarg) is trailing.
        simulator.finalize("hello")
        mock_pyperclip.copy.assert_called_with("hello ")
        mock_pyperclip.reset_mock()

        # Trailing: appends unless text ends with whitespace; a second Final
        # never gets a leading space.
        simulator.finalize("world", separator=SeparatorPolicy.TRAILING)
        mock_pyperclip.copy.assert_called_with("world ")
        mock_pyperclip.reset_mock()
        simulator.finalize("test\n", separator=SeparatorPolicy.TRAILING)
        mock_pyperclip.copy.assert_called_with("test\n")
        mock_pyperclip.reset_mock()
        simulator.finalize("next", separator=SeparatorPolicy.TRAILING)
        mock_pyperclip.copy.assert_called_with("next ")
        mock_pyperclip.reset_mock()

        # Leading (legacy): the old rule verbatim. First call no space;
        # second gets a leading space; leading-whitespace text passes through.
        sim2 = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        sim2.finalize("hello", separator=SeparatorPolicy.LEADING)
        mock_pyperclip.copy.assert_called_with("hello")
        mock_pyperclip.reset_mock()
        sim2.finalize("world", separator=SeparatorPolicy.LEADING)
        mock_pyperclip.copy.assert_called_with(" world")
        mock_pyperclip.reset_mock()
        sim2.finalize("\tagain", separator=SeparatorPolicy.LEADING)
        mock_pyperclip.copy.assert_called_with("\tagain")
        mock_pyperclip.reset_mock()
        sim2.finalize("test\n", separator=SeparatorPolicy.LEADING)
        mock_pyperclip.reset_mock()
        sim2.finalize("me", separator=SeparatorPolicy.LEADING)
        mock_pyperclip.copy.assert_called_with("me")
        mock_pyperclip.reset_mock()
        sim2.finalize(" world", separator=SeparatorPolicy.LEADING)
        mock_pyperclip.copy.assert_called_with(" world")
        mock_pyperclip.reset_mock()

        # Never: pure passthrough.
        simulator.finalize("raw", separator=SeparatorPolicy.NEVER)
        mock_pyperclip.copy.assert_called_with("raw")
        mock_pyperclip.reset_mock()

        # Mode-switch safety: a trailing Final, then switch to leading —
        # no double space, because last_final_char is " ".
        simulator.finalize("switched", separator=SeparatorPolicy.TRAILING)
        mock_pyperclip.reset_mock()
        simulator.finalize("after", separator=SeparatorPolicy.LEADING)
        mock_pyperclip.copy.assert_called_with("after")
        mock_pyperclip.reset_mock()

        # Empty text: nothing typed, no separator.
        simulator.finalize("")
        mock_pyperclip.copy.assert_not_called()

    def test_finalize_clears_ghost_before_typing(
        self, simulator, mock_keyboard, mock_pyperclip
    ):
        """Should backspace ghost text before typing final."""
        simulator.update_ghost("ghost")
        mock_keyboard.reset_mock()

        simulator.finalize("final")

        assert len(_backspace_calls(mock_keyboard)) == 5
        mock_pyperclip.copy.assert_called_with("final ")


class TestEdgeCases:
    """Edge case tests for ghost text handling."""

    def test_rapid_concurrent_updates(self, simulator, mock_keyboard):
        """Handle rapid successive updates without state corruption."""
        updates = ["a", "ab", "abc", "abcd", "abcde"]
        for text in updates:
            simulator.update_ghost(text)

        assert simulator.last_ghost_length == 5

    def test_drift_recovery(self, simulator, mock_keyboard):
        """Should recover gracefully when word stitching drifts."""
        simulator.update_ghost("the quick brown fox")

        mock_keyboard.reset_mock()
        simulator.update_ghost("completely different text here")

        assert simulator.last_ghost_length > 0

    def test_redundant_frame_handling(self, simulator, mock_keyboard):
        """Should skip duplicate ghost frames efficiently."""
        simulator.update_ghost("test")
        mock_keyboard.reset_mock()

        simulator.update_ghost("test")

        mock_keyboard.type.assert_not_called()
        mock_keyboard.press.assert_not_called()

    def test_ghost_none_handling(self, simulator, mock_keyboard):
        """Should handle None gracefully."""
        simulator.update_ghost(None)
        mock_keyboard.assert_not_called()

    def test_finalize_empty_string(self, simulator, mock_keyboard):
        """Should handle empty finalize gracefully."""
        simulator.finalize("")
        mock_keyboard.assert_not_called()


class TestAppendDiffTyping:
    """Append-diff typing properties (the rework of ADR 0010's typing):
    per-update keystroke cost is bounded by the live tail (the window),
    never the composed line."""

    def test_pasted_text_is_changed_tail_never_full_line(self, simulator, mock_keyboard, mock_pyperclip):
        """In a clean sequence, each frame's paste is the changed tail
        from the first differing word — never a full-line repaste, and
        each applied update keeps the previously correct prefix."""
        sim = simulator
        sim.update_ghost("alpha beta gamma delta", (0, 16000))
        first_paste = mock_pyperclip.copy.call_args_list[0].args[0]
        assert first_paste == "alpha beta gamma delta"

        mock_pyperclip.reset_mock()
        for ghost, window in [
            ("beta gamma delta epsilon", (4000, 20000)),
            ("gamma delta epsilon zeta", (8000, 24000)),
        ]:
            sim.update_ghost(ghost, window=window)
            pasted = [c.args[0] for c in mock_pyperclip.copy.call_args_list]
            mock_pyperclip.reset_mock()
            # One paste per applied frame; it never repeats the whole
            # previously correct line (the word-prefix is kept)
            assert len(pasted) == 1
            assert pasted[0].strip() not in ("alpha", "beta")

        sim.update_ghost("zeta eta theta", (12000, 28000))
        final_paste = mock_pyperclip.copy.call_args_list[-1].args[0]
        # The unchanged head is never repasted
        assert "alpha" not in final_paste
        sim.stop()

    def test_full_repaste_sized_by_word_diff(self, simulator, mock_keyboard, mock_pyperclip):
        """When the composer's dedup trim reaches into previously typed
        committed words, the apply rewrites from the first differing
        WORD — erase and paste are exact and minimal, no separate
        full-repaste special case."""
        sim = simulator
        sim.update_ghost("alpha beta gamma", (0, 16000))
        # Commit all three, then the trim pulls "gamma" back out: the
        # typed committed prefix ("alpha beta") shrinks to ("alpha")
        sim.update_ghost("gamma delta", (16000, 32000))
        assert sim.typed_committed == "alpha beta"

        mock_keyboard.reset_mock()
        mock_pyperclip.reset_mock()
        sim.update_ghost("beta delta echo", (24000, 40000))
        # committed shrank to ["alpha"]
        assert sim.composer.committed == ["alpha"]
        # Old screen: "alpha beta gamma delta". New target:
        # [alpha, beta, delta, echo]. First difference at word 3
        # (gamma -> delta), matching on words 1-2.
        old_line = "alpha beta gamma delta"
        kept = "alpha beta"
        erased = len(old_line) - len(kept)
        assert len(_backspace_calls(mock_keyboard)) == erased
        # One paste: the changed tail, with the separator re-supplied
        pasted = [c.args[0] for c in mock_pyperclip.copy.call_args_list]
        assert pasted == [" delta echo"]
        assert sim.accumulated_text == "alpha beta delta echo"


class TestFinalizeResetsOrdering:
    """The audio thread's real ordering: display.finalize() enqueues the
    Final, then pipeline.reset_state() calls display.reset() immediately.
    The Final's erase must be computed from the mirrors as they stood
    when the Final was enqueued — not after the reset wiped them — or
    the ghost line stays on screen with the Final pasted after it."""

    def test_final_after_reset_still_erases_the_ghost(self, mock_pyperclip):
        mock_keyboard = MagicMock()
        sim = InputSimulator(
            keyboard_controller=mock_keyboard, throttle_s=0.0
        )
        sim.enqueue_ghost("ghost line on screen", None)
        assert sim.flush()
        assert sim.accumulated_text == "ghost line on screen"

        # The audio thread's real ordering: enqueue the Final, then
        # reset() — before the worker ever runs the Final's erase.
        sim.enqueue_finalize("FINAL", separator=SeparatorPolicy.TRAILING)
        sim.reset()

        assert sim.flush(0.5), "worker did not drain after reset"

        backspace_count = len(_backspace_calls(mock_keyboard))
        total_graphemes = len("ghost line on screen")
        assert backspace_count == total_graphemes, (
            f"Final erased {backspace_count} graphemes, "
            f"expected {total_graphemes} (the ghost must be erased when "
            f"the Final lands, not skipped)"
        )
        pasted = [c.args[0] for c in mock_pyperclip.copy.call_args_list]
        assert pasted[-1] == "FINAL "
        # No post-Final garbage: the ghost text appears exactly once as
        # a paste, the Final exactly once
        assert pasted.count("ghost line on screen") == 1
        assert pasted.count("FINAL ") == 1
        sim.stop()

    def test_reset_without_final_drops_pending_ghost(self, mock_pyperclip):
        """Stop-word path: reset() with no Final — a pending ghost frame
        must not apply after the cleanup."""
        mock_keyboard = MagicMock()
        sim = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        sim.enqueue_ghost("hello", None)
        assert sim.flush()

        sim.enqueue_ghost("hello world", None)  # pending, not yet applied
        sim.reset()
        assert sim.flush(0.5)

        pasted = [c.args[0] for c in mock_pyperclip.copy.call_args_list]
        assert pasted == ["hello"], (
            f"a pending ghost frame applied after reset: {pasted}"
        )
        sim.stop()


class TestTypingWorker:
    """The typing worker: the audio thread enqueues and returns
    immediately; frames apply paced, ghost frames coalescing latest-wins,
    a Final superseding any pending ghost frame."""

    def _blocking_keyboard(self):
        """A keyboard whose backspace presses log an observable trace and
        whose bursts can be paused: press() records and returns without
        blocking (pynput's real path), while a test controlling
        `release`... unused — kept for the queue-state helpers."""
        import threading

        from pynput.keyboard import Key

        release = threading.Event()
        started = threading.Event()
        mock_keyboard = MagicMock()

        def slow_press(key):
            if key == Key.backspace:
                started.set()

        mock_keyboard.press.side_effect = slow_press
        return mock_keyboard, started, release

    def test_finalize_supersedes_pending_ghost(self, mock_pyperclip):
        """The Final supersedes the pending ghost frame: superseded text
        is never typed; the Final erases the screen and lands last."""
        mock_keyboard, started, _ = self._blocking_keyboard()
        sim = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)

        sim.enqueue_ghost("hello world", None)
        assert sim.flush()
        assert sim.accumulated_text == "hello world"

        # Change the live tail (enqueue re-composes; the coalescing slot
        # holds only the latest frame), then supersede it with the Final.
        sim.enqueue_ghost("hello world AGAIN", None)
        sim.enqueue_finalize("FINAL", separator=SeparatorPolicy.TRAILING)
        assert sim.flush(), "worker did not drain"

        pasted = [c.args[0] for c in mock_pyperclip.copy.call_args_list]
        assert "hello world" in pasted  # the first applied frame
        # The superseded ghost frame was never typed
        assert not any("AGAIN" in p for p in pasted), (
            f"a superseded ghost frame typed: {pasted}"
        )
        assert pasted[-1] == "FINAL "  # the Final, with its trailing space
        assert sim.accumulated_text == ""
        sim.stop()

    def test_coalescing_keeps_only_the_latest_ghost(self, mock_pyperclip):
        mock_keyboard, started, _ = self._blocking_keyboard()
        sim = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)

        sim.enqueue_ghost("hello world", None)
        assert sim.flush()

        # A burst of ghost frames: all but the latest are superseded in
        # the coalescing slot (the worker applies only the newest)
        sim.enqueue_ghost("hello world from", None)
        sim.enqueue_ghost("hello world from the", None)
        sim.enqueue_ghost("hello world from the worker", None)
        assert sim.flush()

        pasted = [c.args[0] for c in mock_pyperclip.copy.call_args_list]
        assert sim.accumulated_text == "hello world from the worker"
        # Latest-wins: the burst applied as ONE frame — the last paste is
        # the full changed suffix against the previous screen state
        assert pasted[-1] == " from the worker"
        sim.stop()

    def test_enqueue_returns_immediately_under_slow_typing(self, mock_pyperclip):
        """The audio thread's contract: enqueue never blocks on
        keystrokes, even while the worker is mid-keystroke-burst."""
        import threading
        import time as time_module

        mock_keyboard = MagicMock()
        gate = threading.Event()
        calls = {"n": 0}

        def slow_press(key):
            calls["n"] += 1
            if calls["n"] == 1:
                assert gate.wait(timeout=5)

        mock_keyboard.press.side_effect = slow_press
        sim = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)

        sim.enqueue_ghost("hello world", None)
        # Wait until the worker is inside the backspace burst
        deadline = time_module.monotonic() + 5
        while calls["n"] < 1 and time_module.monotonic() < deadline:
            time_module.sleep(0.002)
        t0 = time_module.monotonic()
        sim.enqueue_ghost("hello world again", None)
        sim.enqueue_finalize("FINAL")
        assert time_module.monotonic() - t0 < 0.05, "enqueue blocked on typing"
        gate.set()
        assert sim.flush()
        sim.stop()

    def test_flush_reports_drained_state(self, mock_pyperclip):
        sim = InputSimulator(keyboard_controller=MagicMock(), throttle_s=0.0)
        sim.enqueue_ghost("hello", None)
        assert sim.flush()
        assert sim.accumulated_text == "hello"
        sim.enqueue_finalize("FINAL")
        assert sim.flush()
        assert sim.accumulated_text == ""
        sim.stop()


class TestInputSimulatorCore:
    """Core InputSimulator functionality tests."""

    def test_type_text(self, simulator, mock_keyboard, mock_pyperclip):
        simulator.type_text("hello")
        mock_pyperclip.copy.assert_called_once_with("hello")

    def test_update_ghost_first_call(self, simulator, mock_keyboard, mock_pyperclip):
        """First ghost call pastes the text via clipboard."""
        simulator.update_ghost("test")
        mock_pyperclip.copy.assert_called_once_with("test")
        assert simulator.last_ghost_length == 4

    def test_update_ghost_incremental(self, simulator, mock_keyboard, mock_pyperclip):
        """Even pure extensions re-paste the full ghost via clipboard."""
        simulator.update_ghost("test")
        mock_pyperclip.reset_mock()
        mock_keyboard.reset_mock()

        simulator.update_ghost("testing")
        mock_pyperclip.copy.assert_called_once_with("testing")
        assert simulator.last_ghost_length == 7

    def test_finalize_basic(self, simulator, mock_keyboard, mock_pyperclip):
        """Finalize should backspace and paste new text."""
        simulator.update_ghost("ghost")
        mock_keyboard.reset_mock()

        simulator.finalize("final")
        assert len(_backspace_calls(mock_keyboard)) == 5
        mock_pyperclip.copy.assert_called_with("final ")
        assert simulator.last_ghost_length == 0

    def test_clear_previous_empty(self, simulator, mock_keyboard):
        """Clearing empty previous should do nothing."""
        simulator._clear_previous()
        mock_keyboard.press.assert_not_called()

    def test_type_text_exception_handling(self, simulator, mock_keyboard, mock_pyperclip):
        """Should handle clipboard exceptions gracefully."""
        mock_pyperclip.copy.side_effect = Exception("Clipboard error")
        simulator.type_text("hello")
        mock_pyperclip.copy.assert_called_once()

    def test_finalize_with_whitespace_handling(
        self, simulator, mock_keyboard, mock_pyperclip
    ):
        """Trailing policy: whitespace-ending Final is unchanged; next is verbatim."""
        simulator.finalize("hello")
        mock_pyperclip.copy.assert_called_with("hello ")

        mock_pyperclip.reset_mock()
        simulator.finalize("world")
        mock_pyperclip.copy.assert_called_with("world ")

        mock_pyperclip.reset_mock()
        simulator.finalize("test\n")
        mock_pyperclip.copy.assert_called_with("test\n")

        mock_pyperclip.reset_mock()
        simulator.finalize("me")
        mock_pyperclip.copy.assert_called_with("me ")

    def test_grapheme_backspacing_emoji(self, simulator, mock_keyboard):
        """Emoji should be handled as single grapheme."""
        simulator.update_ghost("🏢")
        assert simulator.last_ghost_length == 1

        mock_keyboard.reset_mock()
        simulator.update_ghost("updated")
        assert len(_backspace_calls(mock_keyboard)) == 1

    def test_grapheme_backspacing_combining(self, simulator, mock_keyboard):
        """Combining characters should be handled correctly."""
        decomposed = "e\u0301"
        simulator.update_ghost(decomposed)
        assert simulator.last_ghost_length == 1

        mock_keyboard.reset_mock()
        simulator.finalize("done")
        # Should only backspace once for the accented 'e'
        assert len(_backspace_calls(mock_keyboard)) == 1


@pytest.mark.slow
class TestGhostUpdateKeyboardSequence:
    """Debug test to verify backspace vs type calls for ghost updates.

    This test helps debug Windows-specific issues with keyboard input.
    Shows the relationship between ghost text changes and keyboard operations.
    """

    @pytest.fixture(scope="class")
    def shared_stt_engine(self):
        """Session-scoped STT engine."""
        import time
        from babelfish_stt.config import (
            BabelfishConfig,
            HardwareConfig,
            PipelineConfig,
            PerformanceProfile,
            SystemInputConfig,
        )
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.pipeline import StandardPipeline
        from babelfish_stt.vad import SileroVAD
        from unittest.mock import MagicMock
        from babelfish_stt.display import TerminalDisplay

        print(f"\n[FIXTURE] Loading STT Engine for keyboard sequence test...")
        start_time = time.perf_counter()
        config = BabelfishConfig(
            hardware=HardwareConfig(device="cpu"),
            pipeline=PipelineConfig(silence_threshold_ms=400),
            system_input=SystemInputConfig(
                enabled=True,
                type_ghost=True,
            ),
        )
        engine = STTEngine(config)
        load_duration = (time.perf_counter() - start_time) * 1000
        print(f"[FIXTURE] STT Engine loaded in {load_duration:.2f}ms")

        mock_display = MagicMock(spec=TerminalDisplay)
        ghost_captures = []

        def capture_ghost(text="", refined="", ghost="", **kwargs):
            ghost_captures.append(ghost)

        mock_display.update = capture_ghost
        mock_display.finalize = MagicMock()
        mock_display.reset = MagicMock()

        pipeline = StandardPipeline(
            vad=SileroVAD(threshold=0.5),
            engine=engine,
            display=mock_display,
            perf=PerformanceProfile(
                ghost_throttle_ms=0,
                ghost_window_s=3.0,
                min_padding_s=2.0,
                tier="ultra",
            ),
        )
        pipeline.set_test_mode(False)
        pipeline.reconfigure(engine.config_ref.pipeline)
        pipeline.request_mode(is_idle=False, force=True)

        return {
            "engine": engine,
            "pipeline": pipeline,
            "ghost_captures": ghost_captures,
        }

    @pytest.fixture(scope="class")
    def ghost_sequence_with_timestamps(self):
        """Capture ghost sequence with timestamps for real-time replay."""
        import soundfile as sf
        from babelfish_stt.config import (
            BabelfishConfig,
            HardwareConfig,
            PipelineConfig,
            PerformanceProfile,
            SystemInputConfig,
        )
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.pipeline import StandardPipeline
        from babelfish_stt.vad import SileroVAD
        from unittest.mock import MagicMock
        from babelfish_stt.display import TerminalDisplay
        import time

        print(f"\n[FIXTURE] Capturing ghost timestamps from joke.wav...")
        start_time = time.perf_counter()

        config = BabelfishConfig(
            hardware=HardwareConfig(device="cpu"),
            pipeline=PipelineConfig(silence_threshold_ms=400),
            system_input=SystemInputConfig(
                enabled=True,
                type_ghost=True,
            ),
        )
        engine = STTEngine(config)

        ghost_data = []

        def capture_ghost(text="", refined="", ghost="", **kwargs):
            if ghost:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                ghost_data.append({"text": ghost, "timestamp_ms": elapsed_ms})

        mock_display = MagicMock(spec=TerminalDisplay)
        mock_display.update = capture_ghost
        mock_display.finalize = MagicMock()
        mock_display.reset = MagicMock()

        pipeline = StandardPipeline(
            vad=SileroVAD(threshold=0.5),
            engine=engine,
            display=mock_display,
            perf=PerformanceProfile(
                ghost_throttle_ms=100,
                ghost_window_s=3.0,
                min_padding_s=2.0,
                tier="ultra",
            ),
        )
        pipeline.set_test_mode(False)
        pipeline.reconfigure(engine.config_ref.pipeline)
        pipeline.request_mode(is_idle=False, force=True)

        audio_path = Path(__file__).parent / "fixtures" / "audio" / "joke.wav"
        audio_data, sample_rate = sf.read(audio_path, dtype="float32")

        hop_size = 1600
        chunk_duration_ms = hop_size / sample_rate * 1000
        num_chunks = int(len(audio_data) / hop_size)

        for i in range(num_chunks):
            chunk = audio_data[i * hop_size : (i + 1) * hop_size]
            now_ms = i * chunk_duration_ms
            pipeline.process_chunk(chunk, now_ms)

            if (
                pipeline._transcription_future
                and not pipeline._transcription_future.done()
            ):
                try:
                    pipeline._transcription_future.result(timeout=0.1)
                except Exception:
                    pass

        silence_chunks = int(0.5 * sample_rate / hop_size)
        for i in range(silence_chunks):
            now_ms = num_chunks * chunk_duration_ms + i * chunk_duration_ms
            silence = np.zeros(hop_size, dtype=np.float32)
            pipeline.process_chunk(silence, now_ms)

        for _ in range(100):
            if (
                pipeline._transcription_future is None
                or pipeline._transcription_future.done()
            ):
                break
            time.sleep(0.01)

        print(f"[FIXTURE] Captured {len(ghost_data)} ghosts with timestamps")
        return ghost_data

    def test_ghost_keyboard_sequence_joke(self, shared_stt_engine):
        """Show backspace vs type calls for each ghost update from joke.wav."""
        import soundfile as sf
        from babelfish_stt.input_manager import InputSimulator

        audio_path = Path(__file__).parent / "fixtures" / "audio" / "joke.wav"
        audio_data, sample_rate = sf.read(audio_path, dtype="float32")

        pipeline = shared_stt_engine["pipeline"]
        ghost_captures = shared_stt_engine["ghost_captures"]

        hop_size = 1600
        chunk_duration_ms = hop_size / sample_rate * 1000

        num_chunks = int(len(audio_data) / hop_size)
        print(f"\n[TEST] Processing joke.wav ({len(audio_data) / sample_rate:.2f}s)...")
        print(f"[TEST] Total chunks: {num_chunks}")

        for i in range(num_chunks):
            chunk = audio_data[i * hop_size : (i + 1) * hop_size]
            now_ms = i * chunk_duration_ms
            pipeline.process_chunk(chunk, now_ms)

            if (
                pipeline._transcription_future
                and not pipeline._transcription_future.done()
            ):
                try:
                    pipeline._transcription_future.result(timeout=0.1)
                except Exception:
                    pass

        silence_chunks = int(0.5 * sample_rate / hop_size)
        for i in range(silence_chunks):
            now_ms = num_chunks * chunk_duration_ms + i * chunk_duration_ms
            silence = np.zeros(hop_size, dtype=np.float32)
            pipeline.process_chunk(silence, now_ms)

        import time

        for _ in range(100):
            if (
                pipeline._transcription_future is None
                or pipeline._transcription_future.done()
            ):
                break
            time.sleep(0.01)

        ghost_sequence = [g for g in ghost_captures if g]
        print(f"[TEST] Captured {len(ghost_sequence)} ghost updates")

        print(f"\n[TEST] Replaying ghost sequence through InputSimulator...")
        print(f"{'=' * 100}")
        print(
            f"{'Ghost#':<8} | {'Ghost Text':<40} | {'Backspaces':<12} | {'Types':<8} | {'Type Text'}"
        )
        print(f"{'=' * 100}")

        mock_keyboard = MagicMock()
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)

        total_backspaces = 0
        total_types = 0
        prev_ghost = ""

        for i, ghost_text in enumerate(ghost_sequence):
            bs_before = mock_keyboard.press.call_count
            type_before = mock_keyboard.type.call_count

            simulator.update_ghost(ghost_text)

            bs_after = mock_keyboard.press.call_count
            type_after = mock_keyboard.type.call_count

            bs_delta = bs_after - bs_before
            type_delta = type_after - type_before

            type_text = ""
            if type_delta > 0 and mock_keyboard.type.call_args_list:
                type_text = mock_keyboard.type.call_args_list[-1][0][0]

            total_backspaces += bs_delta
            total_types += type_delta

            display_ghost = (
                ghost_text[:38] + ".." if len(ghost_text) > 40 else ghost_text
            )
            display_type = type_text[:20] + ".." if len(type_text) > 22 else type_text

            print(
                f"{i + 1:<8} | {display_ghost:<40} | {bs_delta:<12} | {type_delta:<8} | {display_type}"
            )

            prev_ghost = ghost_text

        print(f"{'=' * 100}")
        print(f"[TEST] TOTALS: {total_backspaces} backspaces, {total_types} type calls")
        print(
            f"[TEST] Ratio: {total_backspaces / max(1, total_types):.2f} backspaces per type call"
        )

        final_text = simulator.accumulated_text
        print(f"\n[TEST] FINAL TYPED TEXT:")
        print(f"{'=' * 100}")
        print(final_text)
        print(f"{'=' * 100}")
        print(f"[TEST] Final text length: {len(final_text)} characters")

    def test_ghost_keyboard_sequence_realtime_joke(
        self, ghost_sequence_with_timestamps
    ):
        """Replay ghosts with real-time delays to test throttle/timing behavior.

        This test captures ghost updates with timestamps during audio processing,
        then replays them with the same timing delays to simulate real-time behavior.
        Tests throttle logic and timing race conditions.
        """
        import time
        from babelfish_stt.input_manager import InputSimulator
        from unittest.mock import MagicMock

        ghost_data = ghost_sequence_with_timestamps

        print(f"\n[TEST] REAL-TIME REPLAY TEST")
        print(f"[TEST] Ghost updates: {len(ghost_data)}")

        if not ghost_data:
            print("[TEST] No ghost data captured!")
            return

        first_timestamp = ghost_data[0]["timestamp_ms"]
        total_duration = ghost_data[-1]["timestamp_ms"] - first_timestamp
        print(
            f"[TEST] Total audio duration: {total_duration:.0f}ms ({total_duration / 1000:.2f}s)"
        )

        mock_keyboard = MagicMock()

        throttle_ms = 100
        simulator = InputSimulator(
            keyboard_controller=mock_keyboard, throttle_s=throttle_ms / 1000.0
        )

        print(f"[TEST] Using throttle: {throttle_ms}ms")
        print(f"[TEST] Replaying with real-time delays...")

        print(f"\n{'=' * 120}")
        print(
            f"{'Ghost#':<8} | {'Elapsed':<10} | {'Delta':<8} | {'Ghost Text':<35} | {'BS':<6} | {'Type':<6} | {'Throttled?':<10} | {'Type Text'}"
        )
        print(f"{'=' * 120}")

        total_backspaces = 0
        total_types = 0
        throttled_count = 0
        last_process_time = 0
        real_start = time.perf_counter()

        for i, ghost in enumerate(ghost_data):
            ghost_text = ghost["text"]
            timestamp_ms = ghost["timestamp_ms"]

            if i == 0:
                elapsed_since_start = 0
            else:
                elapsed_since_start = (time.perf_counter() - real_start) * 1000

            target_delay_ms = timestamp_ms - ghost_data[i - 1]["timestamp_ms"]
            actual_delay_ms = (
                time.perf_counter() - real_start
            ) * 1000 - elapsed_since_start

            if target_delay_ms > actual_delay_ms:
                sleep_ms = (target_delay_ms - actual_delay_ms) / 1000.0
                if sleep_ms > 0:
                    time.sleep(sleep_ms)

            bs_before = mock_keyboard.press.call_count
            type_before = mock_keyboard.type.call_count

            simulator.update_ghost(ghost_text)

            bs_after = mock_keyboard.press.call_count
            type_after = mock_keyboard.type.call_count

            bs_delta = bs_after - bs_before
            type_delta = type_after - type_before

            was_throttled = type_delta == 0 and i > 0
            if was_throttled:
                throttled_count += 1

            total_backspaces += bs_delta
            total_types += type_delta

            if i % 10 == 0 or was_throttled or bs_delta > 10:
                display_ghost = (
                    ghost_text[:33] + ".." if len(ghost_text) > 35 else ghost_text
                )
                display_type = (
                    mock_keyboard.type.call_args_list[-1][0][0][:15] + ".."
                    if mock_keyboard.type.call_args_list
                    and len(mock_keyboard.type.call_args_list[-1][0][0]) > 17
                    else (
                        mock_keyboard.type.call_args_list[-1][0][0]
                        if mock_keyboard.type.call_args_list
                        else ""
                    )
                )

                print(
                    f"{i + 1:<8} | {timestamp_ms - first_timestamp:<10.0f} | {target_delay_ms:<8.0f} | {display_ghost:<35} | {bs_delta:<6} | {type_delta:<6} | {'YES' if was_throttled else '-':<10} | {display_type}"
                )

            last_process_time = timestamp_ms

        real_duration = (time.perf_counter() - real_start) * 1000

        print(f"{'=' * 120}")
        print(f"[TEST] REAL-TIME REPLAY TOTALS:")
        print(f"[TEST]   Ghost updates: {len(ghost_data)}")
        print(f"[TEST]   Throttled updates: {throttled_count}")
        print(f"[TEST]   Throttle rate: {throttled_count / len(ghost_data) * 100:.1f}%")
        print(f"[TEST]   Total backspaces: {total_backspaces}")
        print(f"[TEST]   Total type calls: {total_types}")
        print(
            f"[TEST]   Ratio: {total_backspaces / max(1, total_types):.2f} backspaces/type"
        )
        print(
            f"[TEST]   Real duration: {real_duration:.0f}ms ({real_duration / 1000:.2f}s)"
        )

        final_text = simulator.accumulated_text
        print(f"\n[TEST] FINAL TYPED TEXT (real-time):")
        print(f"{'=' * 100}")
        print(final_text)
        print(f"{'=' * 100}")
        print(f"[TEST] Final text length: {len(final_text)} characters")
