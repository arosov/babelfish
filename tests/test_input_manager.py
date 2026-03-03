"""
InputManager and InputSimulator unit tests.

These tests verify the InputSimulator's ghost text handling,
backspacing, word stitching, and finalization behavior.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from babelfish_stt.input_manager import InputSimulator


@pytest.fixture
def mock_keyboard():
    return MagicMock()


@pytest.fixture
def simulator(mock_keyboard):
    return InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)


@pytest.fixture
def throttled_simulator(mock_keyboard):
    return InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.1)


class TestGhostTextBehavior:
    """Tests for ghost text update and backspacing behavior."""

    def test_ghost_timing_respects_throttle(self, throttled_simulator, mock_keyboard):
        """Ghost updates should be throttled to prevent overwhelming the system."""
        import time

        throttled_simulator.update_ghost("hello")
        call_count_1 = mock_keyboard.type.call_count

        time.sleep(0.06)
        throttled_simulator.update_ghost("hello w")
        call_count_2 = mock_keyboard.type.call_count

        time.sleep(0.06)
        throttled_simulator.update_ghost("hello wo")
        call_count_3 = mock_keyboard.type.call_count

        assert call_count_1 == 1
        assert call_count_2 == call_count_1

    def test_ghost_incremental_backspacing(self, simulator, mock_keyboard):
        """Should only backspace changed suffix, not entire text."""
        simulator.update_ghost("hello world")
        mock_keyboard.reset_mock()

        simulator.update_ghost("hello there")

        backspace_calls = mock_keyboard.press.call_count
        type_call = mock_keyboard.type.call_args[0][0]

        assert backspace_calls == 5
        assert type_call == "there"

    def test_ghost_word_stitching(self, simulator, mock_keyboard):
        """Word stitching should handle incremental ASR updates correctly."""
        simulator.update_ghost("the")
        mock_keyboard.reset_mock()

        simulator.update_ghost("the quick")
        type_call_1 = mock_keyboard.type.call_args[0][0]

        mock_keyboard.reset_mock()
        simulator.update_ghost("the quick brown")
        type_call_2 = mock_keyboard.type.call_args[0][0]

        assert type_call_1 == " quick"
        assert type_call_2 == " brown"

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

    def test_finalize_adds_spacing_between_utterances(self, simulator, mock_keyboard):
        """Should add space between consecutive finalizations."""
        simulator.finalize("hello")
        mock_keyboard.type.assert_called_with("hello")

        mock_keyboard.reset_mock()
        simulator.finalize("world")
        mock_keyboard.type.assert_called_with(" world")

    def test_finalize_preserves_existing_spacing(self, simulator, mock_keyboard):
        """Should not add extra space if already present."""
        simulator.finalize("hello")

        mock_keyboard.reset_mock()
        simulator.finalize(" world")
        mock_keyboard.type.assert_called_with(" world")

    def test_finalize_clears_ghost_before_typing(self, simulator, mock_keyboard):
        """Should backspace ghost text before typing final."""
        simulator.update_ghost("ghost")
        mock_keyboard.reset_mock()

        simulator.finalize("final")

        assert mock_keyboard.press.call_count == 5
        mock_keyboard.type.assert_called_with("final")


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


class TestInputSimulatorCore:
    """Core InputSimulator functionality tests."""

    def test_type_text(self, simulator, mock_keyboard):
        simulator.type_text("hello")
        mock_keyboard.type.assert_called_once_with("hello")

    def test_update_ghost_first_call(self, simulator, mock_keyboard):
        """First ghost call should type the text directly."""
        simulator.update_ghost("test")
        mock_keyboard.type.assert_called_once_with("test")
        assert simulator.last_ghost_length == 4

    def test_update_ghost_incremental(self, simulator, mock_keyboard):
        """Update ghost should only type the delta."""
        simulator.update_ghost("test")
        mock_keyboard.reset_mock()

        simulator.update_ghost("testing")
        assert mock_keyboard.press.call_count == 0
        mock_keyboard.type.assert_called_once_with("ing")
        assert simulator.last_ghost_length == 7

    def test_finalize_basic(self, simulator, mock_keyboard):
        """Finalize should backspace and type new text."""
        simulator.update_ghost("ghost")
        mock_keyboard.reset_mock()

        simulator.finalize("final")
        assert mock_keyboard.press.call_count == 5
        mock_keyboard.type.assert_called_with("final")
        assert simulator.last_ghost_length == 0

    def test_clear_previous_empty(self, simulator, mock_keyboard):
        """Clearing empty previous should do nothing."""
        simulator._clear_previous()
        mock_keyboard.press.assert_not_called()

    def test_type_text_exception_handling(self, simulator, mock_keyboard):
        """Should handle keyboard exceptions gracefully."""
        mock_keyboard.type.side_effect = Exception("Keyboard error")
        simulator.type_text("hello")
        mock_keyboard.type.assert_called_once()

    def test_finalize_with_whitespace_handling(self, simulator, mock_keyboard):
        """Test finalize spacing between utterances."""
        simulator.finalize("hello")
        mock_keyboard.type.assert_called_with("hello")

        mock_keyboard.reset_mock()
        simulator.finalize("world")
        mock_keyboard.type.assert_called_with(" world")

        mock_keyboard.reset_mock()
        simulator.finalize("\tagain")
        mock_keyboard.type.assert_called_with("\tagain")

    def test_grapheme_backspacing_emoji(self, simulator, mock_keyboard):
        """Emoji should be handled as single grapheme."""
        simulator.update_ghost("🏢")
        assert simulator.last_ghost_length == 1

        mock_keyboard.reset_mock()
        simulator.update_ghost("updated")
        assert mock_keyboard.press.call_count == 1

    def test_grapheme_backspacing_combining(self, simulator, mock_keyboard):
        """Combining characters should be handled correctly."""
        decomposed = "e\u0301"
        simulator.update_ghost(decomposed)
        assert simulator.last_ghost_length == 1

        mock_keyboard.reset_mock()
        simulator.finalize("done")
        assert mock_keyboard.press.call_count == 1


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
            InputStrategy,
        )
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.pipeline import StandardPipeline
        from babelfish_stt.vad import SileroVAD
        from unittest.mock import MagicMock
        from babelfish_stt.display import TerminalDisplay

        print(f"\n[FIXTURE] Loading STT Engine for keyboard sequence test...")
        start_time = time.perf_counter()
        config = BabelfishConfig(
            hardware=HardwareConfig(device="auto"),
            pipeline=PipelineConfig(
                silence_threshold_ms=400,
                update_interval_ms=100,
                performance=PerformanceProfile(
                    ghost_throttle_ms=0,
                    ghost_window_s=3.0,
                    min_padding_s=2.0,
                    tier="ultra",
                ),
            ),
            system_input=SystemInputConfig(
                enabled=True,
                type_ghost=True,
                strategy=InputStrategy.DIRECT,
            ),
        )
        engine = STTEngine(config)
        load_duration = (time.perf_counter() - start_time) * 1000
        print(f"[FIXTURE] STT Engine loaded in {load_duration:.2f}ms")

        mock_display = MagicMock(spec=TerminalDisplay)
        ghost_captures = []

        def capture_ghost(text="", refined="", ghost=""):
            ghost_captures.append(ghost)

        mock_display.update = capture_ghost
        mock_display.finalize = MagicMock()
        mock_display.reset = MagicMock()

        pipeline = StandardPipeline(
            vad=SileroVAD(threshold=0.5),
            engine=engine,
            display=mock_display,
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
            InputStrategy,
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
            hardware=HardwareConfig(device="auto"),
            pipeline=PipelineConfig(
                silence_threshold_ms=400,
                update_interval_ms=100,
                performance=PerformanceProfile(
                    ghost_throttle_ms=100,
                    ghost_window_s=3.0,
                    min_padding_s=2.0,
                    tier="ultra",
                ),
            ),
            system_input=SystemInputConfig(
                enabled=True,
                type_ghost=True,
                strategy=InputStrategy.DIRECT,
            ),
        )
        engine = STTEngine(config)

        ghost_data = []

        def capture_ghost(text="", refined="", ghost=""):
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
