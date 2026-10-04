import pytest
from unittest.mock import MagicMock, patch
from pynput.keyboard import Key

from babelfish_stt.input_strategies import paste_text, send_backspaces


class FakeClipboard:
    """pyperclip stand-in whose read-back can lag the write (the Windows
    clipboard-viewer race the paste verification exists for)."""

    def __init__(self, settle_after_reads=0):
        self.copies = []
        self._reads = 0
        self._settle_after_reads = settle_after_reads

    def copy(self, text):
        self.copies.append(text)

    def paste(self):
        self._reads += 1
        if self._reads <= self._settle_after_reads:
            return "stale previous frame"  # the race
        return self.copies[-1]


@pytest.fixture
def mock_keyboard():
    return MagicMock()


@patch("pyperclip.copy")
def test_paste_text(mock_copy, mock_keyboard):
    with patch("pyperclip.paste", return_value=None) as mock_paste:
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


def test_paste_waits_for_clipboard_settle(mock_keyboard):
    """The clipboard lags the copy (viewer/manager delay): the chord must
    not go out until the read-back holds the intended text."""
    clip = FakeClipboard(settle_after_reads=2)
    with patch("babelfish_stt.input_strategies.pyperclip", clip), patch(
        "babelfish_stt.input_strategies.time"
    ) as fake_time:
        paste_text("hello", mock_keyboard)

    # Two failed verifications slept before the third read held the text
    assert fake_time.sleep.call_count == 2
    # The chord still fired exactly once, after the clipboard settled
    assert mock_keyboard.press.call_count == 1


def test_paste_settled_clipboard_types_immediately(mock_keyboard):
    """The common case: the clipboard holds the text instantly — no
    sleeps, no pacing, the chord goes straight out."""
    clip = FakeClipboard(settle_after_reads=0)
    with patch("babelfish_stt.input_strategies.pyperclip", clip), patch(
        "babelfish_stt.input_strategies.time"
    ) as fake_time:
        paste_text("hello", mock_keyboard)

    assert fake_time.sleep.call_count == 0
    assert mock_keyboard.press.call_count == 1


def test_paste_unreadable_clipboard_is_not_a_blocker(mock_keyboard):
    """Verification is best-effort: a clipboard that never settles still
    sends the chord (after the bounded retries), with a warning."""
    clip = FakeClipboard(settle_after_reads=99)
    with patch("babelfish_stt.input_strategies.pyperclip", clip), patch(
        "babelfish_stt.input_strategies.time"
    ):
        paste_text("hello", mock_keyboard)

    assert mock_keyboard.press.call_count == 1


def test_send_backspaces(mock_keyboard):
    send_backspaces(3, mock_keyboard)
    assert mock_keyboard.press.call_count == 3
    assert mock_keyboard.release.call_count == 3
    assert mock_keyboard.press.call_args_list[0].args[0] == Key.backspace


def test_send_backspaces_zero_noop(mock_keyboard):
    send_backspaces(0, mock_keyboard)
    mock_keyboard.press.assert_not_called()
