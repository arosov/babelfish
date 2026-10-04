import numpy as np
import time
import threading
import logging
import concurrent.futures
from collections import deque
from typing import List, Optional, Any
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.notifier import DesktopNotifier
from babelfish_stt.config import (
    VoiceConfig,
    UIConfig,
    PipelineConfig,
    PerformanceProfile,
)

logger = logging.getLogger(__name__)


class Pipeline(Reconfigurable):
    def __init__(self):
        self._lock = threading.RLock()
        self.is_idle = True
        self.is_speaking = False
        self.pending_idle = False
        self.stop_detector: Optional[StopWordDetector] = None
        self.on_state_change = None  # Callback(is_speaking: bool)
        self.on_mode_change = None  # Callback(is_idle: bool)
        self.test_mode = False  # When True, run VAD only and drop audio
        self.server: Any = None  # Will be set by main.py
        self.notifier: Optional[DesktopNotifier] = None  # Set by main.py

    def request_mode(
        self, is_idle: bool, force: bool = False, source_event: Optional[str] = None
    ):
        """
        Unified entry point for changing the engine mode.
        Handles deferral, resource cleanup, and server synchronization.
        """
        with self._lock:
            if not is_idle:
                # UNLOCKING (Listening) - Always immediate
                logger.info(f"🔓 UNLOCK requested (Event: {source_event or 'manual'})")
                self.pending_idle = False
                callback = None
                if self.is_idle:
                    self.is_idle = False
                    self.reset_state()
                    callback = self.on_mode_change

                if source_event:
                    if self.notifier:
                        self.notifier.notify_event(source_event)
                    if self.server:
                        self.server.trigger_event(source_event)

                if callback:
                    callback(False)
                return

            # LOCKING (Idle)
            if not force and self.is_speaking:
                # Defer locking until current speech ends
                if not self.pending_idle:
                    logger.info(
                        f"⏳ LOCK requested but speech in progress. Queuing... (Event: {source_event or 'manual'})"
                    )
                    self.pending_idle = True
                return

            # Execute immediate LOCK
            logger.info(f"🔒 LOCK executed (Event: {source_event or 'manual'})")
            self.is_idle = True
            self.pending_idle = False
            self.reset_state()
            callback = self.on_mode_change

            if source_event:
                if self.notifier:
                    self.notifier.notify_event(source_event)
                if self.server:
                    self.server.trigger_event(source_event)

            if callback:
                callback(True)

    def set_idle(self, idle: bool, force: bool = False):
        """Legacy wrapper, delegates to request_mode."""
        self.request_mode(idle, force=force)

    def reset_state(self):
        """Resets internal audio buffers and VAD states."""
        pass

    def set_test_mode(self, enabled: bool):
        """Enable/disable microphone test mode. When enabled, VAD runs but audio is dropped."""
        self.test_mode = enabled

    def _notify_state_change(self, is_speaking: bool):
        with self._lock:
            self.is_speaking = is_speaking
        if self.on_state_change:
            self.on_state_change(is_speaking)

    def process_chunk(self, chunk: np.ndarray, now_ms: float) -> bool:
        """
        Returns True if a state transition occurred (e.g., stop word detected).
        """
        raise NotImplementedError

    def reconfigure(self, config: BaseModel) -> None:
        """Pipeline base reconfiguration (e.g., logic shifts if needed)"""
        pass


class StopWordDetector(Reconfigurable):
    """
    Detects stop phrases in transcript strings.
    """

    config_key = "voice"

    def __init__(self, stop_words: List[str]):
        self.stop_words = [w.lower().strip() for w in stop_words]

    def reconfigure(self, config: BaseModel) -> None:
        """Update stop words list."""
        if isinstance(config, VoiceConfig):
            self.stop_words = [w.lower().strip() for w in config.stop_words]

    def detect(self, text: str) -> bool:
        """
        Returns True if the text ends with any of the stop words.
        Handles basic punctuation at the end of the text.
        """
        if not text:
            return False

        # Normalize text: lower case and remove trailing punctuation
        text_clean = text.lower().strip()
        while text_clean and text_clean[-1] in ".,!?;:":
            text_clean = text_clean[:-1].strip()

        for stop_phrase in self.stop_words:
            # Check if the text ends exactly with the stop phrase
            # We want to match whole words/phrases at the end
            if text_clean == stop_phrase:
                return True
            if text_clean.endswith(" " + stop_phrase):
                return True

        return False


class StandardPipeline(Pipeline):
    """
    Streamlined pipeline for high-performance STT.
    Handles intermediate 'ghost' updates and final commitments.
    """

    config_key = "pipeline"

    def __init__(self, vad, engine, display):
        super().__init__()
        self.vad = vad
        self.engine = engine
        self.display = display

        self.active_buffer = []
        self._buffer_size = 0
        self.pre_roll_ms = 300
        self.pre_roll_buffer = deque()
        self.last_speech_time = 0
        self.silence_threshold_ms = 400

        # Throttle clock: last Ghost *submit* time. None = never submitted
        # (spacing considered already elapsed, so the first Ghost can fire on
        # the onset chunk itself).
        self.last_submit_ms: Optional[float] = None

        # Performance Profile (Self-Calibration)
        self.perf = PerformanceProfile()

        # Thread pool for offloading transcription
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._transcription_future = None

        # Generation counter to detect stale ghost results
        self._generation = 0
        self._future_generation = 0  # Generation of the currently running future

        # Ghost telemetry (window-capture -> submit -> done -> display)
        self._utterance_start_ms = 0.0
        self._first_ghost_shown = False
        self._ghost_window_s = 0.0
        self._ghost_capture_ms = 0.0
        self._ghost_submit_wall_ms = 0.0
        self._last_ghost_staleness_ms = 0.0  # read by the test harness
        # Audio coverage of the latest Ghost's window, in buffer samples:
        # (window_start, buffer_end). Lets the display commit aged-out words
        # by audio time even when the model re-worded the shared region.
        self._ghost_window_span = (0, 0)

    def reconfigure(self, config: BaseModel) -> None:
        if isinstance(config, PipelineConfig):
            self.silence_threshold_ms = config.silence_threshold_ms
            self.pre_roll_ms = config.pre_roll_ms
            self.perf = config.performance

    def process_chunk(
        self, chunk: np.ndarray, now_ms: float, is_speech: Optional[bool] = None
    ) -> bool:
        # Use pre-computed VAD result if provided, otherwise run it
        if is_speech is None:
            is_speech = self.vad.is_speech(chunk)

        with self._lock:
            if self.is_idle:
                # While idle, maintain pre-roll buffer
                self.pre_roll_buffer.append(chunk)
                max_chunks = max(
                    1, int((self.pre_roll_ms / 1000.0) * 16000 / len(chunk))
                )
                while len(self.pre_roll_buffer) > max_chunks:
                    self.pre_roll_buffer.popleft()
                return False

        # GHOST CONSUME: a finished Ghost inference is consumed immediately,
        # on every chunk — speech AND silence-during-utterance. Display no
        # longer waits for the spacing gate; staleness drops to inference
        # time (plus <=32ms chunk granularity).
        if self._consume_ghost_result(now_ms):
            return True  # Stop word detected in the Ghost text

        # GHOST TIMEOUT: Adaptive timeout based on buffer size
        # Calculate expected processing time to avoid false timeouts on long utterances
        if self.is_speaking:
            # Base timeout: 5 seconds minimum
            adaptive_timeout_ms = 5000

            # Add time based on buffer size (assuming RTF of 0.3 for worst-case CPU)
            # and the current throttle setting (minimum spacing)
            with self._lock:
                audio_duration_s = self._buffer_size / 16000.0
                # Conservative estimate: 0.5 RTF + current spacing
                expected_processing_ms = (
                    audio_duration_s * 0.5 * 1000
                ) + self.perf.ghost_throttle_ms
                # Add 3x safety margin for ghost inferences
                adaptive_timeout_ms = max(5000, expected_processing_ms * 3)

            if now_ms - self.last_speech_time > adaptive_timeout_ms:
                logger.warning(
                    f"🕒 Ghost timeout ({adaptive_timeout_ms / 1000:.1f}s) reached. "
                    f"Buffer: {audio_duration_s:.1f}s. Resetting state."
                )
                self.reset_state()
                return False

        # Handle test mode: run VAD but don't accumulate audio or transcribe
        if self.test_mode:
            with self._lock:
                if is_speech:
                    if not self.is_speaking:
                        self.is_speaking = True
                        self._notify_state_change(True)
                    self.last_speech_time = now_ms
                else:
                    # Silence detected in test mode
                    if self.is_speaking:
                        if now_ms - self.last_speech_time > self.silence_threshold_ms:
                            self.is_speaking = False
                            self._notify_state_change(False)
            return False

        # Normal mode: accumulate audio and transcribe
        if is_speech:
            with self._lock:
                if not self.is_speaking:
                    self._notify_state_change(True)
                    # Prime the throttle clock to "already elapsed": the
                    # first Ghost submits on this onset chunk, transcribing
                    # pre-roll + onset.
                    self.last_submit_ms = None
                    self._first_ghost_shown = False
                    self._utterance_start_ms = now_ms

                    # Prepend pre-roll buffer if it exists
                    if self.pre_roll_buffer:
                        while self.pre_roll_buffer:
                            rolled_chunk = self.pre_roll_buffer.popleft()
                            self.active_buffer.append(rolled_chunk)
                            self._buffer_size += len(rolled_chunk)

                self.active_buffer.append(chunk)
                self._buffer_size += len(chunk)
                self.last_speech_time = now_ms

                # SAFETY: Force finalize if buffer gets too large (> 60s) to prevent OOM
                # 60s * 16000 samples = 960,000 samples
                if self._buffer_size > 960000:
                    logger.warning(
                        "⚠️ Buffer limit (60s) reached. Forcing finalization."
                    )

                    self._drop_pending_ghost()
                    # Manual Finalization
                    full_audio = np.concatenate(self.active_buffer)
                    # Run transcribe in main thread (blocking but safe here for safety)
                    text = self.engine.transcribe(
                        full_audio, padding_s=self.perf.min_padding_s
                    )
                    if text:
                        self.display.finalize(text)
                    self.reset_state()
                    # Continue listening with empty buffer
                    return False

            # Ghost submit: only on speech chunks, only when the previous
            # result was consumed AND the minimum spacing between submits has
            # elapsed. The single worker already guarantees spacing
            # >= inference time (can't submit while busy).
            self._maybe_submit_ghost(now_ms)
        else:
            # Silence detected
            with self._lock:
                was_speaking = self.is_speaking

            if was_speaking:
                with self._lock:
                    self.active_buffer.append(chunk)
                    self._buffer_size += len(chunk)
                    is_silent_long_enough = (
                        now_ms - self.last_speech_time > self.silence_threshold_ms
                    )
            else:
                # Silence while not speaking: maintain pre-roll buffer
                with self._lock:
                    self.pre_roll_buffer.append(chunk)

                    # Limit pre-roll buffer size
                    # Assuming 16kHz, chunk size is usually 512 samples (~32ms)
                    # 300ms / 32ms ~= 10 chunks
                    max_chunks = max(
                        1, int((self.pre_roll_ms / 1000.0) * 16000 / len(chunk))
                    )
                    while len(self.pre_roll_buffer) > max_chunks:
                        self.pre_roll_buffer.popleft()

                is_silent_long_enough = False

            # If we've been silent long enough, finalize
            if was_speaking and is_silent_long_enough:
                # Drop the pending Ghost: the Final is starting. The
                # in-flight inference still holds engine._lock until it
                # finishes (ORT can't be preempted) but its result is
                # discarded via the generation bump.
                self._drop_pending_ghost()

                with self._lock:
                    full_audio = np.concatenate(self.active_buffer)

                # Final pass: blocking for consistency
                # Since STTEngine now has a lock, it won't run concurrently with ghost pass
                text = self.engine.transcribe(
                    full_audio, padding_s=self.perf.min_padding_s
                )
                if text:
                    self.display.finalize(text)
                    if self.stop_detector and self.stop_detector.detect(text):
                        self._handle_stop()
                        return True

                self.reset_state()

                # Completion of deferred LOCK
                with self._lock:
                    if self.pending_idle:
                        self.request_mode(is_idle=True, force=True)

        return False

    def _consume_ghost_result(self, now_ms: float) -> bool:
        """
        Consume a finished Ghost inference, if any: telemetry, generation
        check, display, stop-word detection. Called on every chunk so
        display follows inference completion directly instead of waiting
        for the spacing gate.

        Returns True if a stop word was detected (state transition).
        """
        if self._transcription_future is None or not self._transcription_future.done():
            return False

        with self._lock:
            future = self._transcription_future
            self._transcription_future = None

        try:
            text, duration_ms = future.result()
        except Exception as e:
            logger.error(f"Ghost transcription error: {e}")
            return False

        with self._lock:
            if self._generation != self._future_generation:
                logger.debug("Stale ghost result ignored")
                return False
            submit_wall_ms = self._ghost_submit_wall_ms
            window_s = self._ghost_window_s
            capture_ms = self._ghost_capture_ms

        if not text:
            logger.debug(
                f"[GHOST] Empty result ({duration_ms:.1f}ms, window={window_s:.2f}s)"
            )
            return False

        now_wall_ms = time.perf_counter() * 1000
        staleness_ms = now_wall_ms - submit_wall_ms
        self._last_ghost_staleness_ms = staleness_ms

        span = self._ghost_window_span
        logger.debug(
            f"[GHOST] Displayed {text!r}: capture={capture_ms:.1f}ms, "
            f"inference={duration_ms:.1f}ms, staleness={staleness_ms:.1f}ms "
            f"(window={window_s:.2f}s, span=({span[0]}, {span[1]}))"
        )

        if not self._first_ghost_shown:
            self._first_ghost_shown = True
            logger.info(
                f"⚡ First Ghost: {now_ms - self._utterance_start_ms:.0f}ms after "
                f"speech onset (inference {duration_ms:.0f}ms, "
                f"staleness {staleness_ms:.0f}ms)"
            )

        # duration_ms rides along as pipeline telemetry (the replay capture
        # display records it; displays that don't care ignore it).
        self.display.update(
            ghost=text, window=self._ghost_window_span, duration_ms=duration_ms
        )
        if self.stop_detector and self.stop_detector.detect(text):
            self._handle_stop()
            return True

        return False

    def _maybe_submit_ghost(self, now_ms: float):
        """
        Submit a Ghost transcription if the worker is free AND at least
        `ghost_throttle_ms` has passed since the last submit (minimum
        spacing between submits, not a display gate). A spacing of 0 means
        "submit as soon as the worker is free".
        """
        with self._lock:
            spacing_ok = self.last_submit_ms is None or (
                now_ms - self.last_submit_ms >= self.perf.ghost_throttle_ms
            )
            worker_free = (
                self._transcription_future is None
                or self._transcription_future.done()
            )
        if not (spacing_ok and worker_free):
            return

        capture_start = time.perf_counter()

        # EFFICIENT FIRST PASS: Sliding window for ghost results (all
        # devices). Bounded inference instead of transcribing the growing
        # whole buffer.
        full_audio = None
        if self.perf.ghost_window_s > 0:
            window_samples = int(self.perf.ghost_window_s * 16000)

            with self._lock:
                if self._buffer_size > window_samples:
                    # Detect chunk size from active_buffer for alignment
                    chunk_size = 512
                    if self.active_buffer:
                        chunk_size = len(self.active_buffer[0])

                    # Align window to chunk boundary (round UP to always send >= target)
                    window_samples_aligned = (
                        (window_samples + chunk_size - 1) // chunk_size
                    ) * chunk_size
                    if window_samples_aligned == 0:
                        window_samples_aligned = chunk_size

                    logger.debug(
                        f"[GHOST] Window: {window_samples} -> {window_samples_aligned} samples "
                        f"(chunk_size={chunk_size}, buffer_size={self._buffer_size})"
                    )

                    # Collect just enough chunks from the end
                    chunks = []
                    collected = 0
                    for buf_chunk in reversed(self.active_buffer):
                        chunks.append(buf_chunk)
                        collected += len(buf_chunk)
                        if collected >= window_samples_aligned:
                            break
                    # Concatenate in correct order (chunks were reversed)
                    full_audio = np.concatenate(chunks[::-1])

        if full_audio is None:
            # Fallback: Capture everything (buffer shorter than window)
            with self._lock:
                full_audio = np.concatenate(self.active_buffer)

        window_audio_s = len(full_audio) / 16000.0
        capture_done = time.perf_counter()

        # Audio coverage of this Ghost's window: the window holds the LAST
        # len(full_audio) samples of the buffer.
        window_start = self._buffer_size - len(full_audio)
        if window_start < 0:
            window_start = 0

        logger.debug(
            f"[GHOST] Sending {len(full_audio)} samples to STT "
            f"({window_audio_s:.2f}s, window={self.perf.ghost_window_s}s, "
            f"ghost_padding={self.perf.ghost_padding_s}s)"
        )

        # Capture current generation to detect stale results
        with self._lock:
            self._future_generation = self._generation

        def _run_transcribe(audio):
            t_start = time.perf_counter()
            res = self.engine.transcribe(audio, padding_s=self.perf.ghost_padding_s)
            return res, (time.perf_counter() - t_start) * 1000

        self._transcription_future = self.executor.submit(_run_transcribe, full_audio)
        with self._lock:
            self.last_submit_ms = now_ms
            self._ghost_window_s = window_audio_s
            self._ghost_window_span = (window_start, self._buffer_size)
            self._ghost_capture_ms = (capture_done - capture_start) * 1000
            self._ghost_submit_wall_ms = time.perf_counter() * 1000

    def _drop_pending_ghost(self):
        """
        Invalidate an outstanding Ghost submit: bump the generation (its
        result will be judged stale) and clear the future slot so nothing
        consumes it against the Final.
        """
        with self._lock:
            self._transcription_future = None
            self._generation += 1

    def _handle_stop(self):
        # Cancel any pending ghost transcription and increment generation to invalidate stale results
        with self._lock:
            self._transcription_future = None
            self._generation += 1
        self.request_mode(is_idle=True, force=True, source_event="stop_word_detected")

    def reset_state(self):
        # Reset for next sentence
        with self._lock:
            self.active_buffer = []
            self._buffer_size = 0
            self.pre_roll_buffer.clear()
            self.last_submit_ms = None
            self._transcription_future = None
            self._generation += 1  # Invalidate any pending ghost transcriptions
            self._last_ghost_staleness_ms = 0.0
            self._ghost_window_span = (0, 0)
            if self.is_speaking:
                self.is_speaking = False
                callback = self.on_state_change
            else:
                callback = None

            self.vad.reset_states()

        # Reset display state (e.g. clear ghost tracking)
        self.display.reset()

        if callback:
            callback(False)
