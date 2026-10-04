"""Slow replay pipeline test (GPU, ~20s): replays the committed French
dictation fixture through the REAL engine and pipeline, in real time,
and regenerates the committed capture JSON that the fast replay test
(tests/test_ghost_composer_replay.py) asserts against.

The replay mirrors the `babelfish --replay` CLI path exactly: same
WavStreamer pacing, same calibration, same pipeline; only the terminal
display is omitted (the capture is the point).

Run: .venv/Scripts/python.exe -m pytest -m slow -s tests/test_replay_pipeline.py
"""

import threading
from pathlib import Path

import pytest

from babelfish_stt.config import (
    BabelfishConfig,
    CacheConfig,
    HardwareConfig,
    PerformanceProfile,
    PipelineConfig,
)
from babelfish_stt.display import MultiDisplay
from babelfish_stt.engine import STTEngine
from babelfish_stt.main import run_stt_loop
from babelfish_stt.pipeline import StandardPipeline
from babelfish_stt.replay import CaptureDisplay, WavStreamer
from babelfish_stt.vad import SileroVAD

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dictation_fr.wav"
CAPTURE_PATH = Path(__file__).parent / "fixtures" / "dictation_fr_capture.json"

SAMPLE_RATE = 16000
# Raw-ghost sanity budget: fast French dictation does not exceed ~8 words
# per second of window audio; a TDT loop seam (the year emitted twice in
# a row, ~30 words per ~3s window) blows far past it.
GHOST_WORDS_PER_SECOND = 8
GHOST_WORD_MARGIN = 2


def _pick_device() -> str:
    """First available GPU backend in this venv (cuda > dml > cpu)."""
    import onnxruntime

    providers = set(onnxruntime.get_available_providers())
    if "CUDAExecutionProvider" in providers:
        return "cuda"
    if "DmlExecutionProvider" in providers:
        return "dml"
    return "cpu"


@pytest.fixture(scope="session")
def replay_engine():
    config = BabelfishConfig(
        hardware=HardwareConfig(device=_pick_device()),
        cache=CacheConfig(),
    )
    engine = STTEngine(config)
    yield engine


@pytest.mark.slow
def test_replay_generates_sane_capture(replay_engine, tmp_path):
    assert FIXTURE_PATH.exists(), f"fixture {FIXTURE_PATH} is missing"

    engine = replay_engine

    # Calibrate exactly like startup does (ADR 0011: unconditional probe,
    # applied in memory only) so the replay runs at the live tier.
    profile = PerformanceProfile(**engine.benchmark())
    pipeline_config = PipelineConfig(performance=profile)

    capture = CaptureDisplay(
        tmp_path / "replay_capture.json",
        header={
            "fixture": FIXTURE_PATH.name,
            "tier": profile.tier,
            "ghost_window_s": profile.ghost_window_s,
            "ghost_throttle_ms": profile.ghost_throttle_ms,
            "ghost_padding_s": profile.ghost_padding_s,
            "min_padding_s": profile.min_padding_s,
            "device": engine.device_type,
        },
    )

    vad = SileroVAD()
    pipeline = StandardPipeline(vad, engine, MultiDisplay(capture))
    pipeline.reconfigure(pipeline_config)

    streamer = WavStreamer(FIXTURE_PATH)
    shutdown_event = threading.Event()

    # Real-time paced replay through the production loop, listening from
    # the first sample (the CLI's --replay path).
    run_stt_loop(
        streamer,
        pipeline,
        ww_engine=None,
        shutdown_event=shutdown_event,
        listen_immediately=True,
    )

    # Write FIRST, assert after: a red run still leaves the freshly
    # regenerated (red) capture on disk — the frozen signal to commit.
    capture.write()

    events = capture.events
    ghosts = [e for e in events if e["type"] == "ghost"]
    finals = [e for e in events if e["type"] == "final"]

    # --- capture-level properties ---
    assert ghosts, (
        "no ghost frames captured — Silero VAD missed the fixture speech? "
        "The fixture is deliberately quiet (peak 0.17, live-identical); "
        "do not gain-boost it — reassess instead."
    )
    assert finals, "no finalize events captured — utterances never closed"

    # Windows are monotone within an utterance: the buffer only grows and
    # the window only slides forward until the reset.
    prev_start, prev_end = 0, 0
    for e in events:
        if e["type"] == "reset":
            prev_start, prev_end = 0, 0
        elif e["type"] == "ghost":
            start, end = e["window"]
            assert end >= prev_end, f"buffer end went backwards: {e}"
            assert start >= prev_start, f"window start went backwards: {e}"
            assert 0 <= start < end, f"malformed window {e['window']}"
            prev_start, prev_end = start, end

    # --- raw-ghost sanity: no TDT looping ---
    for e in ghosts:
        start, end = e["window"]
        dur_s = (end - start) / SAMPLE_RATE
        words = len(e["ghost"].split())
        budget = dur_s * GHOST_WORDS_PER_SECOND + GHOST_WORD_MARGIN
        assert words <= budget, (
            f"raw ghost holds {words} words in {dur_s:.2f}s of window "
            f"(budget {budget:.0f}) — degenerate TDT looping: {e['ghost']!r}"
        )

    # The capture written for the fast test is the one just regenerated:
    # refresh the committed file so the frozen signal matches this run.
    CAPTURE_PATH.write_text(
        (tmp_path / "replay_capture.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
