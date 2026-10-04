"""Replay harness: run a fixture WAV through the real pipeline (the red
loop of the Ghost rework plan).

Two pieces:

- ``WavStreamer`` speaks the same generator contract as
  ``AudioStreamer.stream`` — fixed-size float32 chunks at the target rate —
  but sourced from a WAV file, paced in real time (sleeping to the file
  position). Real-time pacing is load-bearing: ``run_stt_loop`` derives
  ``now_ms`` from ``time.time()`` per chunk, so wall-clock pacing keeps
  throttle spacing, silence thresholds, and inference-overlap dynamics
  identical to a live run. A synthetic clock would let the loop outrun
  inference and change window contents at submit time.
- ``CaptureDisplay`` records every Ghost frame (raw text, window span,
  wall timestamp, inference duration) plus utterance boundaries and a
  performance header to JSON. The committed capture is the frozen
  red/green signal the fast replay test asserts against; the slow replay
  test regenerates it.
"""

import json
import logging
import time
import wave
from pathlib import Path
from typing import Any, Optional

import numpy as np

from babelfish_stt.reconfigurable import Reconfigurable

logger = logging.getLogger(__name__)

TARGET_RATE = 16000
# Appended after the fixture so the last utterance's silence threshold
# fires and the Final pass runs, like a real speaker stopping.
TRAILING_SILENCE_S = 1.0
# Default capture output for `--replay` (CWD-relative, matching the CLI's
# repo-root launch convention): the committed frozen red/green signal
# consumed by tests/test_ghost_composer_replay.py.
DEFAULT_CAPTURE_OUT = Path("tests/fixtures/dictation_fr_capture.json")


class WavStreamer(Reconfigurable):
    """Streams a fixture WAV through the AudioStreamer generator contract."""

    config_key = None  # The fixture is fixed audio; nothing to reconfigure

    def __init__(
        self,
        wav_path,
        sample_rate: int = TARGET_RATE,
        trailing_silence_s: float = TRAILING_SILENCE_S,
    ):
        self.path = Path(wav_path)
        self.target_rate = sample_rate

        with wave.open(str(self.path), "rb") as wf:
            file_rate = wf.getframerate()
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())

        if sampwidth != 2:
            raise ValueError(
                f"Replay fixture {self.path} must be 16-bit PCM (got {sampwidth * 8}-bit)"
            )
        audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)
        if file_rate != self.target_rate:
            import soxr

            audio = soxr.resample(audio, file_rate, self.target_rate)
            logger.info(
                f"🔄 Replay resample: {file_rate}Hz -> {self.target_rate}Hz"
            )

        if trailing_silence_s > 0:
            audio = np.concatenate(
                [
                    audio,
                    np.zeros(
                        int(trailing_silence_s * self.target_rate),
                        dtype=np.float32,
                    ),
                ]
            )

        self.audio = audio.astype(np.float32, copy=False)
        self.duration_s = len(self.audio) / self.target_rate
        self.is_running = False

        logger.info(
            f"📼 Replay streamer: {self.path.name} "
            f"({self.duration_s:.1f}s incl. {trailing_silence_s:.1f}s trailing silence)"
        )

    def stream(self, chunk_size: int = 512):
        """
        Yields fixed-size float32 chunks, real-time paced: a chunk is
        yielded only once its audio has elapsed on the wall clock, like a
        capture device delivering blocks.
        """
        self.is_running = True
        start = None
        pos = 0
        total = len(self.audio)
        while self.is_running and pos < total:
            if start is None:
                start = time.perf_counter()
            # Pace to the chunk's end position: a real device delivers a
            # block only after its audio has elapsed.
            target_s = (pos + chunk_size) / self.target_rate
            delay = target_s - (time.perf_counter() - start)
            if delay > 0:
                time.sleep(delay)
            chunk = self.audio[pos : pos + chunk_size]
            pos += chunk_size
            yield chunk.astype(np.float32, copy=True)

    def stop(self):
        """Stops the replay stream."""
        self.is_running = False

    def drain(self):
        """Nothing is buffered ahead of the yielded position."""

    def reconfigure(self, config) -> None:
        """The fixture is fixed audio; configuration cannot change it."""


class CaptureDisplay:
    """Records Ghost frames and utterance boundaries to JSON (replay only).

    A frame is recorded exactly as the pipeline emitted it — the raw
    sliding-window Ghost text, before any display composes it — together
    with the window span ``(window_start, buffer_end)`` in buffer samples,
    a wall timestamp, and the inference duration. ``finalize``/``reset``
    events mark utterance boundaries the same way the pipeline emits
    them, so a replay can reset the composer at the same points.
    """

    def __init__(self, out_path, header: Optional[dict] = None):
        self.out_path = Path(out_path)
        self.header: dict[str, Any] = dict(header or {})
        self.events: list[dict[str, Any]] = []

    def update(
        self,
        text: str = "",
        refined: str = "",
        ghost: str = "",
        window=None,
        duration_ms: Optional[float] = None,
        **kwargs,
    ):
        if not ghost:
            return
        self.events.append(
            {
                "type": "ghost",
                "ghost": ghost,
                "window": list(window) if window is not None else None,
                "ts": time.time(),
                "duration_ms": duration_ms,
            }
        )

    def finalize(self, text: str = ""):
        self.events.append({"type": "final", "text": text, "ts": time.time()})

    def reset(self):
        self.events.append({"type": "reset", "ts": time.time()})

    def write(self):
        """Writes the capture JSON (header + events), creating parents."""
        ghosts = sum(1 for e in self.events if e["type"] == "ghost")
        payload = {"header": self.header, "events": self.events}
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info(f"📝 Capture written: {self.out_path} ({ghosts} ghost frames)")
