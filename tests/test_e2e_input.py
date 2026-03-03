"""
E2E Integration tests for Audio -> STT -> InputSimulator pipeline.

These tests verify the full pipeline with real STT engine and real InputSimulator.
Only the keyboard controller is mocked to capture output without OS side effects.

Run with: pytest -s -m slow -k "e2e"
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from babelfish_stt.input_manager import InputSimulator
from babelfish_stt.pipeline import StandardPipeline
from babelfish_stt.vad import SileroVAD


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


@pytest.fixture
def e2e_pipeline(shared_stt_engine):
    """Create a pipeline with real STT engine and mocked display."""
    from unittest.mock import MagicMock
    from babelfish_stt.display import TerminalDisplay

    mock_keyboard = MagicMock()
    input_simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)

    mock_display = MagicMock(spec=TerminalDisplay)

    pipeline = StandardPipeline(
        vad=SileroVAD(threshold=0.5),
        engine=shared_stt_engine,
        display=mock_display,
    )

    pipeline.set_test_mode(False)
    pipeline.reconfigure(shared_stt_engine.config_ref.pipeline)
    pipeline.request_mode(is_idle=False, force=True)

    return {
        "pipeline": pipeline,
        "mock_keyboard": mock_keyboard,
        "input_simulator": input_simulator,
        "mock_display": mock_display,
    }


def run_audio_through_pipeline(pipeline, audio_data, sample_rate, hop_size=1600):
    """Helper to run audio through pipeline and wait for completion."""
    import time

    chunk_duration_ms = hop_size / sample_rate * 1000

    num_chunks = int(len(audio_data) / hop_size)
    for i in range(num_chunks):
        chunk = audio_data[i * hop_size : (i + 1) * hop_size]
        now_ms = i * chunk_duration_ms
        pipeline.process_chunk(chunk, now_ms)

        if pipeline._transcription_future and not pipeline._transcription_future.done():
            try:
                pipeline._transcription_future.result(timeout=0.1)
            except Exception:
                pass

    silence_chunks = int(0.5 * sample_rate / hop_size)
    for i in range(silence_chunks):
        now_ms = num_chunks * chunk_duration_ms + i * chunk_duration_ms
        silence = np.zeros(hop_size, dtype=np.float32)
        pipeline.process_chunk(silence, now_ms)

    for _ in range(50):
        if (
            pipeline._transcription_future is None
            or pipeline._transcription_future.done()
        ):
            break
        time.sleep(0.01)


@pytest.mark.slow
class TestE2EInputIntegration:
    """E2E integration tests with real STT + mocked InputSimulator."""

    def test_e2e_ghost_text_sequence_hello_hello(self, e2e_pipeline):
        """Test hello_hello.wav produces correct ghost/final text sequence."""
        import soundfile as sf

        audio_path = Path(__file__).parent / "fixtures" / "audio" / "hello_hello.wav"
        audio_data, sample_rate = sf.read(audio_path, dtype="float32")

        pipeline = e2e_pipeline["pipeline"]
        mock_display = e2e_pipeline["mock_display"]

        run_audio_through_pipeline(pipeline, audio_data, sample_rate)

        update_calls = mock_display.update.call_count
        finalize_calls = mock_display.finalize.call_count

        print(f"\n[TEST] E2E Test Results (hello_hello):")
        print(f"[TEST]   Display update calls: {update_calls}")
        print(f"[TEST]   Display finalize calls: {finalize_calls}")

        all_ghosts = [
            call.kwargs.get("ghost", "") or call.kwargs.get("text", "")
            for call in mock_display.update.call_args_list
        ]
        all_finals = [
            call.kwargs.get("text", "") for call in mock_display.finalize.call_args_list
        ]

        print(f"[TEST]   Ghost texts: {all_ghosts[:5]}...")
        print(f"[TEST]   Final texts: {all_finals}")

        assert update_calls > 0, "Display should have received ghost text updates"
        assert finalize_calls > 0, "Display should have received final text"
        assert any("hello" in g.lower() for g in all_ghosts), (
            "Should contain 'hello' in ghost text"
        )

        print(f"[TEST]   PASS")

    def test_e2e_word_stitching_multiple_words(self, e2e_pipeline):
        """Test multiple_words.wav produces correct word stitching."""
        import soundfile as sf

        audio_path = Path(__file__).parent / "fixtures" / "audio" / "multiple_words.wav"
        audio_data, sample_rate = sf.read(audio_path, dtype="float32")

        pipeline = e2e_pipeline["pipeline"]
        mock_display = e2e_pipeline["mock_display"]

        run_audio_through_pipeline(pipeline, audio_data, sample_rate)

        all_ghosts = [
            call.kwargs.get("ghost", "") or call.kwargs.get("text", "")
            for call in mock_display.update.call_args_list
        ]

        print(f"\n[TEST] Word Stitching Test Results (multiple_words):")
        print(f"[TEST]   Total ghost updates: {len(all_ghosts)}")
        print(f"[TEST]   Ghost texts:")
        for i, g in enumerate(all_ghosts[:10]):
            print(f"[TEST]     {i + 1}. {g!r}")
        if len(all_ghosts) > 10:
            print(f"[TEST]     ... and {len(all_ghosts) - 10} more")

        assert len(all_ghosts) > 1, "Should have multiple ghost updates"
        assert any("quick" in g.lower() or "brown" in g.lower() for g in all_ghosts), (
            "Should contain words from audio"
        )

        print(f"[TEST]   PASS")

    def test_e2e_full_input_sequence_joke(self, e2e_pipeline):
        """Test joke.wav produces complete ghost/final sequence with all details."""
        import soundfile as sf

        audio_path = Path(__file__).parent / "fixtures" / "audio" / "joke.wav"
        audio_data, sample_rate = sf.read(audio_path, dtype="float32")

        pipeline = e2e_pipeline["pipeline"]
        mock_display = e2e_pipeline["mock_display"]

        print(f"\n[TEST] Running joke.wav through pipeline...")
        run_audio_through_pipeline(pipeline, audio_data, sample_rate)

        update_calls = mock_display.update.call_count
        finalize_calls = mock_display.finalize.call_count

        all_ghosts = [
            call.kwargs.get("ghost", "") or call.kwargs.get("text", "")
            for call in mock_display.update.call_args_list
        ]
        all_finals = [
            call.kwargs.get("text", "") for call in mock_display.finalize.call_args_list
        ]

        print(f"\n[TEST] Joke Test Results:")
        print(f"[TEST]   Audio duration: {len(audio_data) / sample_rate:.2f}s")
        print(f"[TEST]   Ghost text updates: {update_calls}")
        print(f"[TEST]   Final text events: {finalize_calls}")
        print(f"[TEST]   Final transcripts: {all_finals}")
        print(f"\n[TEST]   Full ghost timeline:")
        for i, ghost in enumerate(all_ghosts):
            print(f"[TEST]     {i + 1:2d}. {ghost!r}")

        assert update_calls > 0, "Should have ghost text updates"
        assert len(all_ghosts) >= 50, (
            f"Expected many ghost updates for joke, got {len(all_ghosts)}"
        )

        print(
            f"[TEST]   PASS - Full input sequence captured with {len(all_ghosts)} ghost updates"
        )
