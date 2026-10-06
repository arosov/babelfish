"""ServerDisplay telemetry extension tests (transcript panel payload).

ServerDisplay composes the Ghost with the shared ADR 0010 GhostComposer
and broadcasts the composed split (committed / live) alongside the raw
Ghost and pipeline telemetry — while keeping the dedup behavior
unchanged from the client's point of view.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from babelfish_stt.display import ServerDisplay


class _ImmediateScheduler:
    """Stands in for asyncio.run_coroutine_threadsafe: runs the broadcast
    coroutine synchronously so tests can assert on the sent messages."""

    def run_coroutine_threadsafe(self, coro, loop):
        asyncio.run(coro)
        return None


def _make_display(monkeypatch, sent):
    server = MagicMock()
    server.broadcast_message = AsyncMock(side_effect=sent.append)
    server._loop = MagicMock()
    monkeypatch.setattr("babelfish_stt.display.asyncio", _ImmediateScheduler())
    return ServerDisplay(server)


def test_update_broadcasts_composed_split(monkeypatch):
    sent = []
    display = _make_display(monkeypatch, sent)

    display.update(ghost="hello wor", window=(0, 16000), duration_ms=210.0, onset_ms=230.0)
    display.update(ghost="hello word this", window=(16000, 32000), duration_ms=180.0)
    display.update(ghost="word this is a", window=(32000, 48000), duration_ms=150.0)

    # Raw ghost is kept unchanged; the composed split matches the composer
    # output (committed words vs the revisable live tail).
    assert sent[0]["type"] == "transcription"
    assert sent[0]["final"] is False
    assert sent[0]["ghost"] == "hello wor"
    assert sent[0]["composed"] == "hello wor"
    assert sent[0]["committed"] == ""
    assert sent[0]["live"] == "hello wor"
    assert sent[0]["window"] == [0, 16000]
    assert sent[0]["inference_ms"] == 210.0
    assert sent[0]["onset_ms"] == 230.0  # first ghost only

    assert sent[1]["ghost"] == "hello word this"
    assert sent[1]["composed"] == "hello word this"
    assert sent[1]["onset_ms"] is None

    # Third ghost: the shared region re-covers "hello", so it stays
    # live/committed per the composer's audio-bound rules.
    assert sent[2]["composed"] == "hello word this is a"
    assert sent[2]["live"] == "word this is a"
    assert sent[2]["committed"] == "hello"


def test_update_dedup_unchanged(monkeypatch):
    sent = []
    display = _make_display(monkeypatch, sent)

    display.update(ghost="hello wor", window=(0, 16000), duration_ms=210.0)
    display.update(ghost="hello wor", window=(0, 16000), duration_ms=210.0)
    display.update(ghost="hello word", window=(0, 16000), duration_ms=220.0)

    # Identical ghost → still exactly one broadcast (client sees the same
    # dedup behavior as before the telemetry extension).
    assert len(sent) == 2


def test_update_composer_advances_even_when_deduped(monkeypatch):
    sent = []
    display = _make_display(monkeypatch, sent)

    display.update(ghost="hello wor", window=(0, 16000), duration_ms=210.0)
    display.update(ghost="hello wor", window=(16000, 32000), duration_ms=180.0)
    display.update(ghost="word this is a", window=(32000, 48000), duration_ms=150.0)

    # The deduped second update fed the composer (its words commit later),
    # exactly like TerminalDisplay.
    assert sent[-1]["committed"] == "hello wor"
    assert sent[-1]["live"] == "word this is a"


def test_finalize_broadcasts_final_pass_ms(monkeypatch):
    sent = []
    display = _make_display(monkeypatch, sent)

    display.finalize("Hello word, this is a test.", final_pass_ms=480.0)

    assert sent == [
        {
            "type": "transcription",
            "text": "Hello word, this is a test.",
            "final": True,
            "final_pass_ms": 480.0,
        }
    ]


def test_finalize_dedup_unchanged(monkeypatch):
    sent = []
    display = _make_display(monkeypatch, sent)

    display.finalize("Same text", final_pass_ms=480.0)
    display.finalize("Same text", final_pass_ms=100.0)
    display.finalize("Other text", final_pass_ms=200.0)

    assert len(sent) == 2
    assert sent[1]["text"] == "Other text"


def test_reset_resets_composer(monkeypatch):
    sent = []
    display = _make_display(monkeypatch, sent)

    display.update(ghost="hello wor", window=(0, 16000), duration_ms=210.0)
    display.reset()
    display.update(ghost="next utterance", window=(0, 16000), duration_ms=120.0)

    assert sent[-2] == {"type": "transcription_reset"}
    # After the reset the composer starts from an empty line again.
    assert sent[-1]["composed"] == "next utterance"
    assert sent[-1]["committed"] == ""
    assert sent[-1]["live"] == "next utterance"
