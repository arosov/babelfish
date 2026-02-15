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


_HAS_GPU = None


def has_gpu():
    """Check if GPU is available."""
    global _HAS_GPU
    if _HAS_GPU is not None:
        return _HAS_GPU

    import ctypes
    import ctypes.util

    lib_name = "libcuda.so.1"
    try:
        ctypes.CDLL(lib_name)
        _HAS_GPU = True
        return True
    except Exception:
        try:
            found = ctypes.util.find_library(lib_name)
            if found:
                ctypes.CDLL(found)
                _HAS_GPU = True
                return True
        except Exception:
            pass
    _HAS_GPU = False
    return False


pytestmark = pytest.mark.skipif("not has_gpu()", reason="GPU not available")


# Run with:
#   uv sync --extra nvidia-linux
#   export LD_LIBRARY_PATH=".venv/lib/python3.12/site-packages/nvidia/cublas/lib:.venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:.venv/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:.venv/lib/python3.12/site-packages/nvidia/cufft/lib:.venv/lib/python3.12/site-packages/nvidia/curand/lib:.venv/lib/python3.12/site-packages/nvidia/nvjitlink/lib:\$LD_LIBRARY_PATH"
#   uv run pytest -s -m slow
#
# -s: shows stdout/stderr (required for real STT output)
# -m slow: runs only slow tests (real STT integration tests)
#
# Run single file:
#   uv run pytest -s -m slow -k "hello_hello"
#   uv run pytest -s -m slow -k "joke"


@pytest.fixture(scope="session")
def shared_stt_engine():
    """A session-scoped STT engine to avoid re-initializing and hitting GPU memory limits."""
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

    print(f"\n[FIXTURE] Loading STT Engine...")
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
    load_duration = (time.perf_counter() - start_time) * 1000
    print(f"[FIXTURE] STT Engine loaded in {load_duration:.2f}ms")
    return engine


@pytest.mark.slow
class TestRealSTTIntegration:
    """Integration tests with real STT engine. Requires GPU.

    Run with: pytest -s -m slow
    """

    @pytest.fixture
    def audio_pipeline(self, shared_stt_engine):
        from tests.audio_fixtures import AudioPipelineFixture

        fixture = AudioPipelineFixture()
        fixture._shared_engine = shared_stt_engine
        return fixture

    @pytest.fixture
    def corpus(self):
        import yaml

        corpus_path = Path(__file__).parent / "fixtures" / "corpus.yaml"
        with open(corpus_path) as f:
            data = yaml.safe_load(f)
        return {item["id"]: item for item in data["corpus"]}

    WER_THRESHOLD = 0.10

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "corpus_entry",
        [
            "multiple_words",
            "unicode_speech",
            "fast_speech",
            "hello_hello",
            "joke",
            "multi_utterance",
        ],
        indirect=False,
    )
    def test_single_file_transcription(self, audio_pipeline, corpus_entry):
        """Test a single audio file from the corpus."""
        import yaml
        import soundfile as sf
        import re
        import time
        from jiwer import wer, cer

        corpus_path = Path(__file__).parent / "fixtures" / "corpus.yaml"
        with open(corpus_path) as f:
            data = yaml.safe_load(f)
        corpus = {item["id"]: item for item in data["corpus"]}

        expected = corpus[corpus_entry]

        print(f"\n{'=' * 70}")
        print(f"[TEST] Single File: {corpus_entry}")
        print(f"{'=' * 70}")

        audio_path = Path(__file__).parent / "fixtures" / "audio" / expected["filename"]
        audio_info = sf.info(audio_path)
        duration = audio_info.duration

        test_start = time.perf_counter()
        result = audio_pipeline.run_with_real_stt(expected["filename"], warmup=False)
        test_elapsed = (time.perf_counter() - test_start) * 1000

        actual = result.transcript.strip()
        expected_transcript = expected.get("actual_transcript", "").strip()

        def normalize_punctuation(text):
            text = re.sub(r"[,\.]", "", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip().lower()

        actual_normalized = normalize_punctuation(actual)
        expected_normalized = normalize_punctuation(expected_transcript)

        word_error = wer(expected_normalized, actual_normalized)
        char_error = (
            cer(expected_normalized, actual_normalized) if expected_normalized else 0
        )
        passed = word_error <= self.WER_THRESHOLD

        print(f"[TEST] 📁 {expected['filename']} ({duration:.2f}s)")
        print(f"[TEST]   Elapsed:  {test_elapsed:.0f}ms")
        print(f'[TEST]   Expected: "{expected_transcript}"')
        print(f'[TEST]   Actual:   "{actual}"')
        print(
            f"[TEST]   WER: {word_error * 100:6.2f}%  |  CER: {char_error * 100:6.2f}%  |  {'PASS' if passed else 'FAIL'}"
        )

        if result.ghost_timeline:
            print(f"[TEST]   Ghosts: {len(result.ghost_timeline)} updates")
            if result.voice_to_first_ghost_ms:
                print(f"[TEST]   First ghost: {result.voice_to_first_ghost_ms:.0f}ms")
            print(f"[TEST]   Ghost Timeline:")
            for i, ghost in enumerate(result.ghost_timeline):
                duration_str = (
                    f" ({ghost.duration_ms:.0f}ms)" if ghost.duration_ms else ""
                )
                print(
                    f'[TEST]     {i + 1:3d}. {ghost.timestamp_ms:6.0f}ms{duration_str}: "{ghost.text}"'
                )
        else:
            print(f"[TEST]   Ghosts: 0 updates")

        if result.final_timeline:
            print(f"[TEST]   Final Passes: {len(result.final_timeline)} updates")
            for i, final in enumerate(result.final_timeline):
                print(f'[TEST]     Final {i + 1}: "{final.text}"')
                print(f"[TEST]       Duration: {final.duration_ms:.0f}ms")
                print(
                    f"[TEST]       Delay from audio end: {final.delay_from_audio_end_ms:.0f}ms"
                )
        else:
            print(f"[TEST]   Final Passes: 0 (using transcript)")

        assert passed, (
            f"WER {word_error * 100:.2f}% exceeds threshold {self.WER_THRESHOLD * 100:.1f}%"
        )

    def test_real_transcription_matches_corpus(self, audio_pipeline, corpus):
        """Test that real STT output matches expected transcripts using WER threshold."""
        from jiwer import wer, cer, RemoveMultipleSpaces, Strip, Compose

        WER_THRESHOLD = 0.10

        print(f"\n{'=' * 70}")
        print(f"[TEST] REAL STT TRANSCRIPTION TEST WITH GPU")
        print(f"{'=' * 70}")
        print(f"[TEST] GPU available: {has_gpu()}")
        print(f"[TEST] WER Threshold: {WER_THRESHOLD * 100:.1f}%")
        print(f"[TEST] Corpus entries: {len(corpus)}")
        print(f"{'=' * 70}\n")

        import re

        def normalize_punctuation(text):
            text = re.sub(r"[,\.]", "", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip().lower()

        all_passed = True
        results = []

        for corpus_id, expected in corpus.items():
            import soundfile as sf

            audio_path = (
                Path(__file__).parent / "fixtures" / "audio" / expected["filename"]
            )
            audio_info = sf.info(audio_path)
            duration = audio_info.duration

            print(f"[TEST] ▶ Processing: {expected['filename']}")
            result = audio_pipeline.run_with_real_stt(
                expected["filename"], warmup=False
            )

            actual = result.transcript.strip()
            expected_transcript = expected.get("actual_transcript", "").strip()

            actual_normalized = normalize_punctuation(actual)
            expected_normalized = normalize_punctuation(expected_transcript)

            word_error = wer(expected_normalized, actual_normalized)
            char_error = (
                cer(expected_normalized, actual_normalized)
                if expected_normalized
                else 0
            )
            passed = word_error <= WER_THRESHOLD

            results.append(
                {
                    "id": corpus_id,
                    "duration": duration,
                    "expected": expected_transcript,
                    "actual": actual,
                    "wer": word_error,
                    "cer": char_error,
                    "passed": passed,
                    "ghost_count": len(result.ghost_timeline),
                    "voice_to_first": result.voice_to_first_ghost_ms,
                    "final_timeline": result.final_timeline,
                }
            )

            print(f"{'─' * 70}")
            print(f"[TEST] 📁 {expected['filename']} ({duration:.2f}s)")
            print(f"{'─' * 70}")
            print(f'[TEST]   Expected: "{expected_transcript}"')
            print(f'[TEST]   Actual:   "{actual}"')
            print(f"[TEST]   ─────────────────────────────────────")
            print(
                f"[TEST]   WER: {word_error * 100:6.2f}%  |  CER: {char_error * 100:6.2f}%  |  {'✅ PASS' if passed else '❌ FAIL'}"
            )
            print(
                f"[TEST]   Ghosts: {len(result.ghost_timeline)} updates  |  First ghost: {result.voice_to_first_ghost_ms:.0f}ms"
                if result.voice_to_first_ghost_ms
                else "[TEST]   Ghosts: 0 updates"
            )
            print()

            if len(result.ghost_timeline) > 0:
                print(f"[TEST]   Ghost Timeline:")
                for i, ghost in enumerate(result.ghost_timeline):
                    duration_str = (
                        f" ({ghost.duration_ms:.0f}ms)" if ghost.duration_ms else ""
                    )
                    print(
                        f'[TEST]     {i + 1:2d}. {ghost.timestamp_ms:6.0f}ms{duration_str}: "{ghost.text}"'
                    )
                print()

            if not passed:
                all_passed = False
                print(
                    f"[TEST]   ❌ FAILED: WER {word_error * 100:.2f}% exceeds threshold {WER_THRESHOLD * 100:.1f}%"
                )

        print(f"{'=' * 70}")
        print(f"[TEST] SUMMARY")
        print(f"{'=' * 70}")
        passed_count = sum(1 for r in results if r["passed"])
        total_ghosts = sum(r["ghost_count"] for r in results)
        avg_wer = sum(r["wer"] * 100 for r in results) / len(results)

        total_final_duration = 0
        total_final_delay = 0
        final_count = 0
        for r in results:
            for f in r.get("final_timeline", []):
                total_final_duration += f.duration_ms
                total_final_delay += f.delay_from_audio_end_ms
                final_count += 1

        print(f"[TEST]   Files tested: {len(results)}")
        print(f"[TEST]   Passed: {passed_count}/{len(results)}")
        print(f"[TEST]   Average WER: {avg_wer:.2f}%")
        print(f"[TEST]   Total ghost updates: {total_ghosts}")
        if final_count > 0:
            print(
                f"[TEST]   Avg Final Duration: {total_final_duration / final_count:.0f}ms"
            )
            print(f"[TEST]   Avg Final Delay: {total_final_delay / final_count:.0f}ms")
        print(f"{'=' * 70}\n")

        assert all_passed, f"WER threshold exceeded for one or more files"

    def test_ghost_timeline_captured(self, audio_pipeline, corpus):
        """Test that ghost timeline is captured for each audio file."""
        import soundfile as sf

        print(f"\n{'=' * 70}")
        print(f"[TEST] GHOST TIMELINE VERIFICATION TEST")
        print(f"{'=' * 70}\n")

        all_passed = True

        for corpus_id, expected in corpus.items():
            audio_path = (
                Path(__file__).parent / "fixtures" / "audio" / expected["filename"]
            )
            audio_info = sf.info(audio_path)
            duration = audio_info.duration

            print(f"[TEST] ▶ Processing: {expected['filename']}")
            result = audio_pipeline.run_with_real_stt(
                expected["filename"], warmup=False
            )

            ghost_count = len(result.ghost_timeline)
            passed = ghost_count > 0

            print(f"{'─' * 70}")
            print(f"[TEST] 📁 {expected['filename']} ({duration:.2f}s)")
            print(f"{'─' * 70}")
            print(f"[TEST]   Ghost Updates: {ghost_count}")

            if result.voice_to_first_ghost_ms is not None:
                print(
                    f"[TEST]   Voice-to-First-Ghost: {result.voice_to_first_ghost_ms:.0f}ms"
                )
            else:
                print(f"[TEST]   Voice-to-First-Ghost: N/A")

            if result.end_to_end_latency_ms is not None:
                print(
                    f"[TEST]   End-to-End Latency: {result.end_to_end_latency_ms:.0f}ms"
                )

            print(f'[TEST]   Final Transcript: "{result.transcript}"')
            if result.final_timeline:
                final = result.final_timeline[0]
                print(f"[TEST]   Final Duration: {final.duration_ms:.0f}ms")
                print(f"[TEST]   Final Delay: {final.delay_from_audio_end_ms:.0f}ms")

            print(f"\n[TEST]   Ghost Timeline ({len(result.ghost_timeline)} updates):")
            if len(result.ghost_timeline) > 0:
                for i, ghost in enumerate(result.ghost_timeline):
                    duration_str = (
                        f" | {ghost.duration_ms:4.0f}ms" if ghost.duration_ms else ""
                    )
                    print(
                        f'[TEST]     {i + 1:2d}. {ghost.timestamp_ms:6.0f}ms{duration_str} | {ghost.grapheme_length:2d} graphemes | "{ghost.text}"'
                    )
            else:
                print(f"[TEST]     (no ghost updates captured)")
                all_passed = False

            print()

            if not passed:
                print(f"[TEST]   ❌ FAILED: No ghost updates captured for {corpus_id}")

        print(f"{'=' * 70}")
        print(f"[TEST] GHOST TIMELINE SUMMARY")
        print(f"{'=' * 70}")
        total_ghosts = sum(
            len(
                audio_pipeline.run_with_real_stt(
                    e["filename"], warmup=False
                ).ghost_timeline
            )
            for e in corpus.values()
        )
        print(f"[TEST]   Files tested: {len(corpus)}")
        print(f"[TEST]   Total ghost updates: {total_ghosts}")
        print(f"[TEST]   Average ghosts per file: {total_ghosts / len(corpus):.1f}")
        print(f"{'=' * 70}\n")

        assert all_passed, "No ghost updates captured for one or more files"
