import pytest
from unittest.mock import MagicMock, patch
from babelfish_stt.input_manager import InputSimulator
from babelfish_stt.config import SeparatorPolicy
from pynput.keyboard import Key


@pytest.fixture
def mock_keyboard():
    return MagicMock()


@pytest.fixture
def simulator(mock_keyboard):
    return InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)


@pytest.fixture
def mock_pyperclip():
    """Ghost and Final text are injected via the clipboard; keep tests hermetic."""
    with patch("babelfish_stt.input_strategies.pyperclip") as m:
        yield m


def _backspace_calls(mock_keyboard):
    """Press calls that are actual backspace keystrokes."""
    return [
        c for c in mock_keyboard.press.call_args_list
        if c.args and c.args[0] == Key.backspace
    ]


def test_type_text(simulator, mock_keyboard, mock_pyperclip):
    simulator.type_text("hello")
    mock_pyperclip.copy.assert_called_once_with("hello")
    mock_keyboard.pressed.assert_called_once_with(Key.ctrl)


def test_update_ghost(simulator, mock_keyboard, mock_pyperclip):
    # First ghost is pasted via clipboard in full
    simulator.update_ghost("test")
    mock_pyperclip.copy.assert_called_once_with("test")
    assert simulator.last_ghost_length == 4

    # Even pure extensions re-paste the full ghost via clipboard
    mock_keyboard.reset_mock()
    mock_pyperclip.reset_mock()
    simulator.update_ghost("testing")
    mock_pyperclip.copy.assert_called_once_with("testing")
    assert simulator.last_ghost_length == 7


def test_finalize(simulator, mock_keyboard, mock_pyperclip):
    simulator.update_ghost("ghost")
    mock_keyboard.reset_mock()
    mock_pyperclip.reset_mock()

    simulator.finalize("final result")
    # Should backspace 5 times, then paste the Final via the clipboard
    assert len(_backspace_calls(mock_keyboard)) == 5
    mock_pyperclip.copy.assert_called_once_with("final result ")
    assert simulator.last_ghost_length == 0


def test_clear_previous_empty(simulator, mock_keyboard):
    simulator._clear_previous()
    mock_keyboard.press.assert_not_called()


def test_type_text_exception_handling(simulator, mock_keyboard, mock_pyperclip):
    mock_pyperclip.copy.side_effect = Exception("Clipboard error")
    # Should not raise exception
    simulator.type_text("hello")
    mock_pyperclip.copy.assert_called_once()


def test_finalize_adds_trailing_space_by_default(simulator, mock_keyboard, mock_pyperclip):
    # The separator rides with the utterance: every Final ends with a space.
    simulator.finalize("hello")
    mock_pyperclip.copy.assert_called_with("hello ")

    # The next Final is typed verbatim — no leading space (the post-Enter
    # case, solved structurally).
    mock_pyperclip.reset_mock()
    simulator.finalize("world")
    mock_pyperclip.copy.assert_called_with("world ")

    # Ends-with-whitespace guard: text already ending in whitespace is
    # passed through unchanged.
    mock_pyperclip.reset_mock()
    simulator.finalize("test\n")
    mock_pyperclip.copy.assert_called_with("test\n")


def test_finalize_leading_policy_is_legacy(simulator, mock_keyboard, mock_pyperclip):
    simulator.finalize("hello", separator=SeparatorPolicy.LEADING)
    mock_pyperclip.copy.assert_called_with("hello")


def test_grapheme_backspacing(simulator, mock_keyboard, mock_pyperclip):
    # Emoji
    simulator.update_ghost("🏢")
    assert simulator.last_ghost_length == 1  # grapheme length, not len() which is 2

    mock_keyboard.reset_mock()
    simulator.update_ghost("updated")
    # The single displayed emoji grapheme is backspaced, then re-pasted
    assert len(_backspace_calls(mock_keyboard)) == 1

    # Combined characters (NFC-aware grapheme counting)
    # 'e' + combining accent (NFD)
    decomposed = "e\u0301"
    mock_keyboard.reset_mock()
    simulator.update_ghost(decomposed)
    # grapheme length should be 1
    assert simulator.last_ghost_length == 1

    mock_keyboard.reset_mock()
    simulator.finalize("done")
    # Should only backspace once for the accented 'e'
    assert len(_backspace_calls(mock_keyboard)) == 1


def test_finalize_pastes_via_clipboard_chord(simulator, mock_keyboard, mock_pyperclip):
    """Final injection is a clipboard paste, not keystroke emulation."""
    simulator.finalize("done")
    mock_pyperclip.copy.assert_called_once_with("done ")
    mock_keyboard.pressed.assert_called_once_with(Key.ctrl)
