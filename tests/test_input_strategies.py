import pytest
from unittest.mock import MagicMock, call, patch
from pynput.keyboard import Key

import babelfish_stt.input_strategies as input_strategies
from babelfish_stt.input_strategies import (
    ERASE_CHUNK,
    paste_text,
    send_backspaces,
)


@pytest.fixture
def mock_keyboard():
    return MagicMock()


@pytest.fixture
def mock_sleep():
    with patch.object(input_strategies.time, "sleep") as m:
        yield m


@patch("pyperclip.copy")
def test_paste_text(mock_copy, mock_keyboard):
    with patch("sys.platform", "linux"):
        paste_text("hello", mock_keyboard)
        mock_copy.assert_called_once_with("hello")
        # Simulated Ctrl+V chord
        mock_keyboard.pressed.assert_called_once_with(Key.ctrl)
    assert mock_keyboard.press.call_count == 1
    assert mock_keyboard.release.call_count == 1


@patch("pyperclip.copy")
def test_paste_text_empty_noop(mock_copy, mock_keyboard):
    paste_text("", mock_keyboard)
    mock_copy.assert_not_called()
    mock_keyboard.pressed.assert_not_called()


def test_send_backspaces(mock_keyboard):
    send_backspaces(3, mock_keyboard)
    assert mock_keyboard.press.call_count == 3
    assert mock_keyboard.release.call_count == 3
    assert mock_keyboard.press.call_args_list[0].args[0] == Key.backspace
    # No intra-burst pacing: the typing worker paces the applies, not
    # the keystrokes inside a burst (the proven-good live regime)
    mock_keyboard.tap.assert_not_called()


def test_send_backspaces_zero_noop(mock_keyboard):
    send_backspaces(0, mock_keyboard)
    mock_keyboard.press.assert_not_called()


# ---------------------------------------------------------------------------
# Chunked erases: bursts within the proven-deliverable envelope (≤
# ERASE_CHUNK, live-clean up to ~82 keys, failures from ≥100) fire
# exactly as before; larger bursts are split with a short inter-chunk
# gap so the editor processes every event (the fast-speech flakiness).

def test_small_burst_unchunked_no_sleeps(mock_keyboard, mock_sleep):
    """A burst at or under the chunk size fires unpaced, exactly as
    before: normal dictation never exceeds it, so the fix is a no-op
    for the verified-clean regime by construction."""
    send_backspaces(ERASE_CHUNK, mock_keyboard)

    assert mock_keyboard.press.call_count == ERASE_CHUNK
    assert mock_keyboard.release.call_count == ERASE_CHUNK
    mock_sleep.assert_not_called()


def test_chunked_burst_exact_keystrokes_and_sleep_structure(
    mock_keyboard, mock_sleep
):
    """A chunked burst sends exactly `count` backspace keystrokes
    (press+release pairs), separated by `ceil(count / ERASE_CHUNK) - 1`
    gaps plus one settle at the end."""
    count = ERASE_CHUNK * 2 + 13  # e.g. a ~200-key Final erase regime
    assert count > ERASE_CHUNK

    send_backspaces(count, mock_keyboard)

    backspaces = [c for c in mock_keyboard.press.call_args_list
                  if c == call(Key.backspace)]
    assert len(backspaces) == count
    assert mock_keyboard.press.call_count == count
    assert mock_keyboard.release.call_count == count

    gaps = 2  # ceil(133/60)=3 chunks -> 2 gaps
    expected_sleeps = [input_strategies.ERASE_CHUNK_GAP_S] * gaps + [
        input_strategies.ERASE_SETTLE_S
    ]
    assert mock_sleep.call_count == gaps + 1
    assert [c.args[0] for c in mock_sleep.call_args_list] == expected_sleeps
    # Every press is a backspace, pressed/released in strict pairs.
    assert all(c == call(Key.backspace) for c in mock_keyboard.press.call_args_list)


def test_boundary_exact_chunk_unchunked_plus_one_chunked(
    mock_keyboard, mock_sleep
):
    """The envelope boundary: count == ERASE_CHUNK stays unpaced,
    one keystroke more crosses into chunking (one gap + settle)."""
    send_backspaces(ERASE_CHUNK, mock_keyboard)
    mock_sleep.assert_not_called()
    assert mock_keyboard.press.call_count == ERASE_CHUNK

    mock_keyboard.reset_mock()
    mock_sleep.reset_mock()
    send_backspaces(ERASE_CHUNK + 1, mock_keyboard)
    assert mock_keyboard.press.call_count == ERASE_CHUNK + 1
    assert [c.args[0] for c in mock_sleep.call_args_list] == [
        input_strategies.ERASE_CHUNK_GAP_S,
        input_strategies.ERASE_SETTLE_S,
    ]


def test_failed_press_mid_burst_raises_for_caller_trust_handling(
    mock_keyboard, mock_sleep
):
    """A failing press mid-burst propagates so the caller can log and
    untrust its mirror state (InputSimulator._send_backspaces)."""
    failing = MagicMock()
    state = {"n": 0}

    def press_side_effect(key):
        state["n"] += 1
        if state["n"] > ERASE_CHUNK + 30:
            raise OSError("injected mid-burst failure")

    failing.press.side_effect = press_side_effect

    with pytest.raises(OSError):
        send_backspaces(ERASE_CHUNK * 3, failing)

    # The burst stopped at the injected failure (press #92 raised)...
    assert state["n"] == ERASE_CHUNK + 31
    # ...after the inter-chunk gap into the second chunk had fired; the
    # settle (only reached on success) did not.
    assert mock_sleep.call_count == 1
