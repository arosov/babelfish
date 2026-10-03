"""
Unit tests for the event-driven Ghost loop (Reactive Ghost Pass).

Ghost-pass behaviour against the real model lives in test_ghost_text.py
(GPU-gated, marked slow). These tests use a fake engine with deterministic,
controllable inference completion so submit/consume behaviour can be tested
without a GPU or model.
"""

import threading
import time
import numpy as np
import pytest
from unittest.mock import MagicMock

from babelfish_stt.config import PipelineConfig, PerformanceProfile
from babelfish_stt.engine import STTEngine
from babelfish_stt.pipeline import StandardPipeline
from babelfish_stt.vad import SileroVAD
from babelfish_stt.display import TerminalDisplay

CHUNK_SAMPLES = 512  # 32ms @ 16kHz
CHUNK_MS = 32.0


class FakeEngine:
    """Engine stub whose inference blocks until released.

    Records every transcribe() call as (audio_samples, padding_s).
    Two release modes:
    - instant (default): every inference completes immediately.
    - block_until_next_call(): the first inference hangs until a second
      transcribe() call arrives (deterministic way to keep a Ghost in
      flight while the Final starts).
    """

    def __init__(self, device_type: str = "cpu", text: str = "hello"):
        self.device_type = device_type
        self.text = text
        self.calls: list = []
        self._release = threading.Event()
        self._release.set()  # instant inference by default
        self._block_first_only = False

    def block(self):
        """Make the next (or in-flight) inference hang until release()."""
        self._release.clear()

    def block_until_next_call(self):
        """First inference hangs until the next transcribe() call arrives."""
        self._block_first_only = True
        self._release.clear()

    def release(self):
        self._release.set()

    def transcribe(self, audio, padding_s: float = 2.0) -> str:
        self.calls.append((len(audio), padding_s))
        if self._block_first_only and len(self.calls) > 1:
            # A later call (the Final) arrived: let the blocked first
            # inference finish.
            self._release.set()
        if not self._release.wait(timeout=10.0):
            raise TimeoutError("fake inference was never released")
        return self.text


def make_pipeline(
    throttle_ms: int = 100,
    ghost_window_s: float = 1.0,
    ghost_padding_s: float = 0.0,
    min_padding_s: float = 2.0,
    engine: FakeEngine = None,
    device_type: str = "cpu",
):
    engine = engine or FakeEngine(device_type=device_type)
    vad = MagicMock(spec=SileroVAD)
    vad.is_speech = lambda chunk: True
    vad.reset_states = MagicMock()
    display = MagicMock(spec=TerminalDisplay)
    pipeline = StandardPipeline(vad, engine, display)
    pipeline.set_test_mode(False)
    pipeline.request_mode(is_idle=False, force=True)  # start listening
    pipeline.reconfigure(
        PipelineConfig(
            performance=PerformanceProfile(
                ghost_throttle_ms=throttle_ms,
                ghost_window_s=ghost_window_s,
                ghost_padding_s=ghost_padding_s,
                min_padding_s=min_padding_s,
            )
        )
    )
    return pipeline, engine, display


def speech_chunk() -> np.ndarray:
    return np.ones(CHUNK_SAMPLES, dtype=np.float32)


def silence_chunk() -> np.ndarray:
    return np.zeros(CHUNK_SAMPLES, dtype=np.float32)


def wait_for_done(pipeline, timeout: float = 10.0) -> bool:
    """Wait until the in-flight ghost future is done (or absent)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        future = pipeline._transcription_future
        if future is None or future.done():
            return True
        time.sleep(0.001)
    return False


class TestFirstGhostOnOnset:
    def test_first_ghost_submits_on_onset_chunk(self):
        """The first Ghost submit fires on the onset chunk itself, not a
        full throttle period later."""
        pipeline, engine, display = make_pipeline(throttle_ms=250)
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)

        assert engine.calls, "expected a Ghost submit on the onset chunk"
        # Ghost padding is applied to Ghost submits
        assert engine.calls[0][1] == pytest.approx(0.0)

        # Consume the result on the next chunk; submitted well within
        # the throttle window (throttle=250 > two chunk intervals).
        pipeline.process_chunk(speech_chunk(), CHUNK_MS, is_speech=True)
        pipeline.process_chunk(speech_chunk(), 2 * CHUNK_MS, is_speech=True)
        wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), 3 * CHUNK_MS, is_speech=True)
        display.update.assert_called()

    def test_spacing_gate_blocked_by_throttle_after_onset(self):
        """After the first submit, a second submit may not fire before the
        minimum spacing elapses."""
        pipeline, engine, display = make_pipeline(throttle_ms=250)
        # Onset chunk submits
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)
        # Consume on next chunk; spacing since submit (32ms) < 250ms, and
        # the worker is known-free => no second submit allowed.
        pipeline.process_chunk(speech_chunk(), CHUNK_MS, is_speech=True)
        wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), 2 * CHUNK_MS, is_speech=True)
        assert len(engine.calls) == 1

        # Once spacing elapses (>= 250ms), a new submit fires.
        pipeline.process_chunk(speech_chunk(), 300.0, is_speech=True)
        wait_for_done(pipeline)
        assert len(engine.calls) == 2


class TestConsumeOnDone:
    def test_consume_happens_independent_of_spacing(self):
        """A finished Ghost is displayed on any chunk (speech or silence
        within an utterance), even when the spacing gate hasn't reopened."""
        pipeline, engine, display = make_pipeline(throttle_ms=250)
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), CHUNK_MS, is_speech=True)
        assert display.update.call_count == 1
        assert display.update.call_args.kwargs.get("ghost") == "hello"

    def test_consume_on_silence_chunk_during_utterance(self):
        """Closing-pause silence chunks consume finished Ghosts too."""
        pipeline, engine, display = make_pipeline(throttle_ms=250)
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)
        # Silence before the finalize threshold (400ms default) but after
        # the last speech chunk triggers nothing final yet.
        pipeline.process_chunk(silence_chunk(), CHUNK_MS, is_speech=False)
        assert display.update.call_count == 1

    def test_no_duplicate_consume(self):
        """A consumed future is not consumed twice."""
        pipeline, engine, display = make_pipeline(throttle_ms=250)
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), CHUNK_MS, is_speech=True)
        pipeline.process_chunk(speech_chunk(), 2 * CHUNK_MS, is_speech=True)
        assert display.update.call_count == 1
        # The result was consumed exactly once and the slot is free again
        assert pipeline._transcription_future is None


class TestSubmitSpacing:
    def test_spacing_enforced_between_submits(self):
        """Submits wait at least ghost_throttle_ms apart, even while the
        worker stays free."""
        pipeline, engine, display = make_pipeline(throttle_ms=100)
        now = 0.0
        # Feed speech, waiting for each inference to finish so the only
        # limiter is the spacing gate (no worker contention).
        for _ in range(20):
            pipeline.process_chunk(speech_chunk(), now, is_speech=True)
            wait_for_done(pipeline)
            now += CHUNK_MS

        # Submits land on chunks where now_ms - last_submit >= 100:
        # 0, 128, 256, 384, 512 over 20 chunks of 32ms each.
        assert len(engine.calls) == 5

    def test_zero_spacing_submits_as_fast_as_model_goes(self):
        """throttle=0 means submit as soon as the worker is free again."""
        pipeline, engine, display = make_pipeline(throttle_ms=0)
        now = 0.0
        for _ in range(10):
            pipeline.process_chunk(speech_chunk(), now, is_speech=True)
            now += CHUNK_MS
            wait_for_done(pipeline)
            # The next chunk consumes and then immediately re-submits
            pipeline.process_chunk(speech_chunk(), now, is_speech=True)
            now += CHUNK_MS
            wait_for_done(pipeline)
        # Every consume is followed by a fresh submit on the same chunk
        assert len(engine.calls) >= 10


class TestPaddingSplit:
    def test_ghost_uses_ghost_padding_final_uses_min_padding(self):
        pipeline, engine, display = make_pipeline(
            throttle_ms=100, ghost_padding_s=0.5, min_padding_s=2.0
        )
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), CHUNK_MS, is_speech=True)
        ghost_paddings = [p for _, p in engine.calls]
        assert all(p == pytest.approx(0.5) for p in ghost_paddings)

        # Finalize with silence and verify the Final used min_padding_s
        start_silence = 2 * CHUNK_MS
        for i in range(16):  # > 400ms of silence
            pipeline.process_chunk(
                silence_chunk(), start_silence + i * CHUNK_MS, is_speech=False
            )
        # Final is blocking; the ghost result must have been released already
        engine.release()
        final_calls = engine.calls[1:]
        assert final_calls, "expected a Final transcribe call"
        # Ghost padding was strictly used on ghosts, Final padding on finals
        assert engine.calls[-1][1] == pytest.approx(2.0)


class TestWindowSpanPassing:
    def test_display_receives_window_span(self):
        """The pipeline passes each Ghost's audio coverage to the display so
        composition can commit aged-out words by audio time."""
        pipeline, engine, display = make_pipeline(throttle_ms=0, ghost_window_s=1.0)
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), CHUNK_MS, is_speech=True)

        kwargs = display.update.call_args.kwargs
        # Buffer is one 512-sample chunk; the whole buffer is the window
        assert kwargs.get("window") == (0, 512)

    def test_window_span_advances_with_buffer(self):
        pipeline, engine, display = make_pipeline(throttle_ms=0, ghost_window_s=1.0)
        now = 0.0
        for _ in range(70):  # grow the buffer past the 1s window
            pipeline.process_chunk(speech_chunk(), now, is_speech=True)
            now += CHUNK_MS
            wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), now, is_speech=True)
        wait_for_done(pipeline)
        pipeline.process_chunk(speech_chunk(), now + CHUNK_MS, is_speech=True)

        start, end = display.update.call_args.kwargs.get("window")
        # Window start slid into the buffer; window is ~1s wide
        assert start > 0
        assert end - start <= int(1.0 * 16000) + 512


class TestStopWordOnGhost:
    def test_stop_word_in_ghost_text_triggers_stop(self):
        """A stop word detected in displayed Ghost text transitions state
        through the consume path."""
        pipeline, engine, display = make_pipeline(throttle_ms=0)
        from babelfish_stt.pipeline import StopWordDetector

        pipeline.stop_detector = StopWordDetector(["stop listening"])
        engine.text = "stop listening"

        # Onset chunk submits; next chunk consumes and detects the stop word
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        wait_for_done(pipeline)
        stop = pipeline.process_chunk(speech_chunk(), CHUNK_MS, is_speech=True)

        assert stop is True
        display.update.assert_called_once()
        # Pipeline went idle (stop word -> lock)
        assert pipeline.is_idle

    def test_stop_word_in_final_still_triggers_stop(self):
        """The Final's stop-word path is untouched."""
        pipeline, engine, display = make_pipeline(throttle_ms=0)
        from babelfish_stt.pipeline import StopWordDetector

        pipeline.stop_detector = StopWordDetector(["stop listening"])
        engine.text = "stop listening"
        # Keep the Ghost wedged so only the Final's text is evaluated
        engine.block_until_next_call()

        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)

        now = CHUNK_MS
        stop = False
        for i in range(20):
            stop = pipeline.process_chunk(silence_chunk(), now, is_speech=False)
            now += CHUNK_MS
            if stop:
                break

        assert stop is True
        assert pipeline.is_idle


class TestDropPendingGhostAtFinalize:
    def test_pending_ghost_dropped_when_final_starts(self):
        """An in-flight Ghost at silence-finalize is dropped: its result is
        never displayed and the Final goes out."""
        pipeline, engine, display = make_pipeline(throttle_ms=100)
        engine.block_until_next_call()
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        # Ghost inference is now wedged (blocked)
        assert pipeline._transcription_future is not None
        assert not pipeline._transcription_future.done()

        # Silence long enough to finalize; the Final's transcribe call
        # unblocks the wedged Ghost, but the Ghost was already dropped.
        for i in range(16):
            pipeline.process_chunk(
                silence_chunk(), CHUNK_MS + i * CHUNK_MS, is_speech=False
            )
        wait_for_done(pipeline)
        # Ghost result was discarded: generation bumped at finalize; no ghost
        # display ever happened despite the inference completing.
        display.update.assert_not_called()
        assert display.finalize.called  # Final went out

    def test_finalize_does_not_wait_for_useless_ghost(self):
        """Finalization discards the pending ghost: the final still produces
        text without the ghost inference completing first."""
        pipeline, engine, display = make_pipeline(throttle_ms=0)
        engine.block_until_next_call()
        pipeline.process_chunk(speech_chunk(), 0.0, is_speech=True)
        for i in range(16):
            pipeline.process_chunk(
                silence_chunk(), CHUNK_MS + i * CHUNK_MS, is_speech=False
            )
        assert display.finalize.called
