import pytest
from unittest.mock import MagicMock, call
from babelfish_stt.input_manager import InputSimulator
from pynput.keyboard import Key


@pytest.fixture
def mock_keyboard():
    return MagicMock()


@pytest.fixture
def simulator(mock_keyboard):
    return InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)


def test_type_text(simulator, mock_keyboard):
    simulator.type_text("hello")
    mock_keyboard.type.assert_called_once_with("hello")


def test_update_ghost(simulator, mock_keyboard):
    # First ghost
    simulator.update_ghost("test")
    mock_keyboard.type.assert_called_once_with("test")
    assert simulator.last_ghost_length == 4

    # Update ghost
    mock_keyboard.reset_mock()
    simulator.update_ghost("testing")
    # Should not backspace since "test" is a prefix of "testing"
    assert mock_keyboard.press.call_count == 0
    mock_keyboard.type.assert_called_once_with("ing")
    assert simulator.last_ghost_length == 7


def test_finalize(simulator, mock_keyboard):
    simulator.update_ghost("ghost")
    mock_keyboard.reset_mock()

    simulator.finalize("final result")
    # Should backspace 5 times
    assert mock_keyboard.press.call_count == 5
    mock_keyboard.type.assert_called_once_with("final result")
    assert simulator.last_ghost_length == 0


def test_clear_previous_empty(simulator, mock_keyboard):
    simulator._clear_previous()
    mock_keyboard.press.assert_not_called()


def test_type_text_exception_handling(simulator, mock_keyboard):
    mock_keyboard.type.side_effect = Exception("Keyboard error")
    # Should not raise exception
    simulator.type_text("hello")
    mock_keyboard.type.assert_called_once()


def test_finalize_adds_space(simulator, mock_keyboard):
    # First call
    simulator.finalize("hello")
    mock_keyboard.type.assert_called_with("hello")

    # Second call, should prepend space
    mock_keyboard.reset_mock()
    simulator.finalize("world")
    mock_keyboard.type.assert_called_with(" world")

    # Third call, already has a tab (whitespace)
    mock_keyboard.reset_mock()
    simulator.finalize("\tagain")
    mock_keyboard.type.assert_called_with("\tagain")

    # Fourth call, previous ended with newline (whitespace)
    mock_keyboard.reset_mock()
    simulator.finalize("test\n")
    mock_keyboard.reset_mock()
    simulator.finalize("me")
    mock_keyboard.type.assert_called_with("me")


def test_grapheme_backspacing(simulator, mock_keyboard):
    # Emoji
    simulator.update_ghost("🏢")
    assert simulator.last_ghost_length == 1  # grapheme length, not len() which is 2

    mock_keyboard.reset_mock()
    simulator.update_ghost("updated")
    # Should only backspace once
    assert mock_keyboard.press.call_count == 1

    # Combined characters (NFC normalization)
    # 'e' + combining accent (NFD)
    decomposed = "e\u0301"
    mock_keyboard.reset_mock()
    simulator.update_ghost(decomposed)
    # grapheme length should be 1
    assert simulator.last_ghost_length == 1

    mock_keyboard.reset_mock()
    simulator.finalize("done")
    # Should only backspace once for the accented 'e'
    assert mock_keyboard.press.call_count == 1
