"""
Ghost text behavior tests using real audio files.

These tests verify the InputSimulator's ghost text handling
with realistic ASR output patterns from actual audio.
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

        time.sleep(0.06)  # Wait slightly more than half the throttle
        throttled_simulator.update_ghost("hello w")
        call_count_2 = mock_keyboard.type.call_count

        time.sleep(0.06)  # Wait again
        throttled_simulator.update_ghost("hello wo")
        call_count_3 = mock_keyboard.type.call_count

        assert call_count_1 == 1
        # First throttle waits since it's within 100ms
        assert call_count_2 == call_count_1
        # Second throttle - cumulative time ~120ms may or may not throttle
        # The key is that throttling IS happening (not all 3 produce output)

    def test_ghost_incremental_backspacing(self, simulator, mock_keyboard):
        """Should only backspace changed suffix, not entire text."""
        simulator.update_ghost("hello world")
        mock_keyboard.reset_mock()

        simulator.update_ghost("hello there")

        backspace_calls = mock_keyboard.press.call_count
        type_call = mock_keyboard.type.call_args[0][0]

        # "hello world" vs "hello there" share 6 graphemes prefix ('h','e','l','l','o',' ')
        # So only 5 need to be removed: 'w','o','r','l','d'
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

        # "ghost" has 5 graphemes: g,h,o,s,t
        assert mock_keyboard.press.call_count == 5
        mock_keyboard.type.assert_called_with("final")


class TestAudioIntegration:
    """Integration tests with real audio files."""

    @pytest.fixture
    def audio_pipeline(self):
        from tests.audio_fixtures import AudioPipelineFixture

        return AudioPipelineFixture()

    @pytest.mark.slow
    def test_audio_files_exist(self):
        """Verify all expected audio fixture files exist."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "audio"

        expected_files = [
            "multiple_words.wav",
            "unicode_speech.wav",
            "fast_speech.wav",
            "hello_hello.wav",
            "joke.wav",
        ]

        for filename in expected_files:
            filepath = fixtures_dir / filename
            assert filepath.exists(), f"Missing audio fixture: {filename}"

    @pytest.mark.slow
    def test_audio_format_16khz(self, audio_pipeline):
        """Verify all audio files are 16kHz."""
        import soundfile as sf

        fixtures_dir = Path(__file__).parent / "fixtures" / "audio"
        for f in fixtures_dir.glob("*.wav"):
            info = sf.info(f)
            assert info.samplerate == 16000, f"{f.name} is not 16kHz: {info.samplerate}"
            assert info.channels == 1, f"{f.name} is not mono: {info.channels}"


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
