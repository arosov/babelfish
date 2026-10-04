import pytest
from unittest.mock import MagicMock, patch
from pynput.keyboard import Key

from babelfish_stt.input_strategies import paste_text, send_backspaces


@pytest.fixture
def mock_keyboard():
    return MagicMock()


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


def test_send_backspaces_zero_noop(mock_keyboard):
    send_backspaces(0, mock_keyboard)
    mock_keyboard.press.assert_not_called()
