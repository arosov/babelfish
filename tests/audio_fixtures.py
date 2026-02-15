"""
Audio fixture utilities for testing the STT pipeline with real audio files.

Usage:
    @pytest.fixture
    def audio_pipeline():
        return AudioPipelineFixture()

    def test_ghost_updates(audio_pipeline):
        result = audio_pipeline.run(
            "fixtures/audio/hello_hello.wav",
            config=PipelineConfig(
                ghost_throttle_ms=50,
                type_ghost=True,
            )
        )

        assert "hello" in result.transcript.lower()
        assert len(result.ghost_timeline) > 0
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Any
from unittest.mock import patch, MagicMock

from babelfish_stt.config import (
    BabelfishConfig,
    PipelineConfig,
    SystemInputConfig,
    InputStrategy,
    HardwareConfig,
    PerformanceProfile,
)


@dataclass
class GhostUpdate:
    """Represents a ghost text update event."""

    timestamp_ms: float
    text: str
    grapheme_length: int
    duration_ms: Optional[float] = None


@dataclass
class FinalUpdate:
    """Represents a final text commitment event."""

    text: str
    timestamp_ms: float
    duration_ms: float
    delay_from_audio_end_ms: float


@dataclass
class PipelineResult:
    """Results from running audio through the pipeline."""

    transcript: str
    ghost_timeline: List[GhostUpdate] = field(default_factory=list)
    final_timeline: List[FinalUpdate] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    voice_to_first_ghost_ms: Optional[float] = None
    end_to_end_latency_ms: Optional[float] = None
    ghost_update_count: int = 0


class AudioPipelineFixture:
    """
    Test utility that runs audio files through the STT pipeline
    while capturing ghost and final text events.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.fixtures_dir = Path(__file__).parent / "fixtures" / "audio"
        self._captured_ghosts: List[GhostUpdate] = []
        self._captured_finals: List[FinalUpdate] = []
        self._start_time: Optional[float] = None
        self._first_ghost_time: Optional[float] = None
        self._audio_finished_time: Optional[float] = None
        self._last_transcription_duration_ms: float = 0
        self._shared_engine: Optional[Any] = None

    def run(
        self,
        audio_filename: str,
        config: Optional[BabelfishConfig] = None,
    ) -> PipelineResult:
        """
        Run an audio file through the pipeline with ghost tracking.

        Args:
            audio_filename: Name of file in fixtures/audio/
            config: Optional pipeline configuration

        Returns:
            PipelineResult with transcript and ghost timeline
        """
        audio_path = self.fixtures_dir / audio_filename
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio_data, sample_rate = sf.read(audio_path, dtype="float32")

        if sample_rate != 16000:
            raise ValueError(
                f"Audio must be 16kHz, got {sample_rate}. Please convert first."
            )

        self._captured_ghosts = []
        self._captured_finals = []
        self._start_time = None
        self._first_ghost_time = None
        self._audio_finished_time = None
        self._last_transcription_duration_ms = 0

        test_config = config or self._default_config()

        result = self._run_pipeline(audio_data, sample_rate, test_config)

        voice_to_first = None
        if self._first_ghost_time and self._start_time:
            voice_to_first = (self._first_ghost_time - self._start_time) * 1000

        return PipelineResult(
            transcript=result.get("text", ""),
            ghost_timeline=self._captured_ghosts,
            final_timeline=self._captured_finals,
            voice_to_first_ghost_ms=voice_to_first,
            ghost_update_count=len(self._captured_ghosts),
        )

    def run_with_real_stt(
        self,
        audio_filename: str,
        config: Optional[BabelfishConfig] = None,
        warmup: bool = True,
    ) -> PipelineResult:
        """
        Run an audio file through the pipeline with real STT engine.

        Args:
            audio_filename: Name of file in fixtures/audio/
            config: Optional pipeline configuration
            warmup: If True, run a silent audio chunk first to warm up the model

        Returns:
            PipelineResult with transcript and ghost timeline
        """
        audio_path = self.fixtures_dir / audio_filename
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio_data, sample_rate = sf.read(audio_path, dtype="float32")

        if sample_rate != 16000:
            raise ValueError(
                f"Audio must be 16kHz, got {sample_rate}. Please convert first."
            )

        self._captured_ghosts = []
        self._captured_finals = []
        self._start_time = None
        self._first_ghost_time = None
        self._audio_finished_time = None
        self._last_transcription_duration_ms = 0

        test_config = config or self._default_config()

        result = self._run_pipeline_with_real_stt(
            audio_data, sample_rate, test_config, warmup
        )

        voice_to_first = None
        if self._first_ghost_time and self._start_time:
            voice_to_first = (self._first_ghost_time - self._start_time) * 1000

        return PipelineResult(
            transcript=result.get("text", ""),
            ghost_timeline=self._captured_ghosts,
            final_timeline=self._captured_finals,
            voice_to_first_ghost_ms=voice_to_first,
            ghost_update_count=len(self._captured_ghosts),
        )

    def _run_pipeline_with_real_stt(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        config: BabelfishConfig,
        warmup: bool = True,
    ) -> dict:
        """
        Execute the pipeline with real STT engine.
        """
        import logging
        import time

        logging.basicConfig(level=logging.INFO)

        from babelfish_stt.engine import STTEngine
        from babelfish_stt.pipeline import StandardPipeline
        from babelfish_stt.vad import SileroVAD
        from babelfish_stt.display import TerminalDisplay

        chunk_size = 512
        hop_size = 512

        if self._shared_engine:
            stt_engine = self._shared_engine
        else:
            print(f"[FIXTURE] Initializing STT Engine...")
            stt_engine = STTEngine(config)

        # Wrap transcribe to capture duration
        if not hasattr(stt_engine, "_wrapped_for_test"):
            original_transcribe = stt_engine.transcribe

            def wrapped_transcribe(*args, **kwargs):
                t_start = time.perf_counter()
                res = original_transcribe(*args, **kwargs)
                stt_engine._last_duration_ms = (time.perf_counter() - t_start) * 1000
                return res

            stt_engine.transcribe = wrapped_transcribe
            stt_engine._last_duration_ms = 0
            stt_engine._wrapped_for_test = True

        print(f"[FIXTURE] STT Engine device: {stt_engine.device_type}")

        if warmup:
            warmup_audio = np.zeros(int(16000 * 1.0), dtype=np.float32)
            stt_engine.transcribe(warmup_audio, padding_s=1.0)

        mock_vad = MagicMock(spec=SileroVAD)

        class MockVAD:
            def __init__(self, audio_data, hop_size, silence_threshold=0.01):
                self.audio_data = audio_data
                self.hop_size = hop_size
                self.silence_threshold = silence_threshold
                self.chunk_count = 0

            def is_speech(self, chunk):
                self.chunk_count += 1
                chunk_start = (self.chunk_count - 1) * self.hop_size
                if chunk_start >= len(self.audio_data):
                    return False
                chunk_audio = self.audio_data[chunk_start : chunk_start + len(chunk)]
                rms = np.sqrt(np.mean(chunk_audio**2))
                return rms > self.silence_threshold

            def reset_states(self):
                self.chunk_count = 0

        mock_vad = MockVAD(audio_data, hop_size)
        mock_display = MagicMock(spec=TerminalDisplay)
        mock_display.update = self._create_ghost_callback(stt_engine)
        mock_display.finalize = self._create_finalize_callback(stt_engine)
        mock_display.reset = MagicMock()

        pipeline = StandardPipeline(mock_vad, stt_engine, mock_display)
        pipeline.set_test_mode(False)
        pipeline.reconfigure(config.pipeline)
        pipeline.request_mode(is_idle=False, force=True)

        self._start_time = time.perf_counter()

        num_chunks = len(audio_data) // hop_size
        for i in range(num_chunks):
            start_idx = i * hop_size
            end_idx = start_idx + chunk_size
            if end_idx > len(audio_data):
                break

            chunk = audio_data[start_idx:end_idx]
            now_ms = (start_idx / sample_rate) * 1000

            pipeline.process_chunk(chunk, now_ms)

            if (
                pipeline._transcription_future
                and not pipeline._transcription_future.done()
            ):
                try:
                    pipeline._transcription_future.result(timeout=0.1)
                except Exception:
                    pass

        # Capture when the audio file actually finished being fed
        self._audio_finished_time = time.perf_counter()

        silence_duration_ms = 500
        silence_chunks = int(silence_duration_ms / (hop_size / sample_rate * 1000))
        for i in range(silence_chunks):
            now_ms = (num_chunks * hop_size / sample_rate * 1000) + (
                i * (hop_size / sample_rate * 1000)
            )
            silence_chunk = np.zeros(hop_size, dtype=np.float32)
            pipeline.process_chunk(silence_chunk, now_ms)

        for _ in range(50):
            if (
                pipeline._transcription_future is None
                or pipeline._transcription_future.done()
            ):
                break
            time.sleep(0.01)

        full_text = (
            " ".join(f.text for f in self._captured_finals)
            if self._captured_finals
            else ""
        )
        return {"text": full_text}

    def _default_config(self) -> BabelfishConfig:
        """Create default test configuration matching production GPU (ultra tier)."""
        return BabelfishConfig(
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

    def _run_pipeline(
        self, audio_data: np.ndarray, sample_rate: int, config: BabelfishConfig
    ) -> dict:
        """
        Execute the pipeline with mocked audio input.

        This simulates the audio loop by feeding chunks to the pipeline
        and capturing callbacks.
        """
        import time
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.pipeline import StandardPipeline
        from babelfish_stt.vad import SileroVAD
        from babelfish_stt.display import TerminalDisplay

        chunk_size = 512
        hop_size = 512

        mock_engine = MagicMock(spec=STTEngine)
        mock_engine.device_type = "cpu"
        mock_engine.transcribe = self._create_transcribe_mock(audio_data, sample_rate)

        # Wrap transcribe to capture duration
        original_transcribe = mock_engine.transcribe

        def wrapped_transcribe(*args, **kwargs):
            t_start = time.perf_counter()
            res = original_transcribe(*args, **kwargs)
            self._last_transcription_duration_ms = (
                time.perf_counter() - t_start
            ) * 1000
            return res

        mock_engine.transcribe = wrapped_transcribe

        mock_vad = MagicMock(spec=SileroVAD)
        mock_vad.is_speech = lambda chunk: True
        mock_vad.reset_states = MagicMock()

        mock_display = MagicMock(spec=TerminalDisplay)
        mock_display.update = self._create_ghost_callback(mock_engine)
        mock_display.finalize = self._create_finalize_callback(mock_engine)
        mock_display.reset = MagicMock()

        pipeline = StandardPipeline(mock_vad, mock_engine, mock_display)
        pipeline.set_test_mode(False)

        self._start_time = time.perf_counter()

        num_chunks = len(audio_data) // hop_size
        for i in range(num_chunks):
            start_idx = i * hop_size
            end_idx = start_idx + chunk_size
            if end_idx > len(audio_data):
                break

            chunk = audio_data[start_idx:end_idx]
            now_ms = (start_idx / sample_rate) * 1000

            pipeline.process_chunk(chunk, now_ms)

        self._audio_finished_time = time.perf_counter()

        return {"text": self._captured_finals[-1].text if self._captured_finals else ""}

    def _create_transcribe_mock(self, audio_data: np.ndarray, sample_rate: int):
        """Create a mock transcribe function that returns text from the audio."""
        from babelfish_stt.engine import STTEngine

        def mock_transcribe(audio_buffer: np.ndarray, **kwargs) -> str:
            if len(audio_buffer) < 1600:
                return ""

            words = ["hello", "world", "test", "words"]
            duration_s = len(audio_buffer) / sample_rate

            if duration_s < 1.0:
                return "hello"
            elif duration_s < 2.0:
                return "hello world"
            elif duration_s < 3.0:
                return "hello world test"
            else:
                return "hello world test words"

        return mock_transcribe

    def _create_ghost_callback(self, stt_engine: Any):
        """Create callback for ghost text updates."""

        def ghost_callback(
            ghost: Optional[str] = None, text: Optional[str] = None, **kwargs
        ):
            text = text or ghost
            if text is None:
                return

            import time

            now = time.perf_counter()
            if self._first_ghost_time is None:
                self._first_ghost_time = now

            try:
                import grapheme

                grapheme_count = len(list(grapheme.graphemes(text)))
            except ImportError:
                grapheme_count = len(text)

            self._captured_ghosts.append(
                GhostUpdate(
                    timestamp_ms=(now - self._start_time) * 1000
                    if self._start_time
                    else 0,
                    text=text,
                    grapheme_length=grapheme_count,
                    duration_ms=getattr(stt_engine, "_last_duration_ms", 0),
                )
            )

        return ghost_callback

    def _create_finalize_callback(self, stt_engine: Any):
        """Create callback for final text."""

        def finalize_callback(text: Optional[str] = None, **kwargs):
            if text:
                import time

                now = time.perf_counter()
                delay = (
                    (now - self._audio_finished_time) * 1000
                    if self._audio_finished_time
                    else 0
                )

                self._captured_finals.append(
                    FinalUpdate(
                        text=text,
                        timestamp_ms=(now - self._start_time) * 1000
                        if self._start_time
                        else 0,
                        duration_ms=getattr(stt_engine, "_last_duration_ms", 0),
                        delay_from_audio_end_ms=delay,
                    )
                )

        return finalize_callback
