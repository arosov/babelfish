import pytest
from unittest.mock import MagicMock, call
from babelfish_stt.input_manager import InputSimulator
from pynput.keyboard import Key


@pytest.fixture
def mock_keyboard():
    return MagicMock()


@pytest.fixture
def simulator(mock_keyboard):
    return InputSimulator(keyboard_controller=mock_keyboard)


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
    # Should backspace 4 times
    assert mock_keyboard.press.call_count == 4
    assert mock_keyboard.release.call_count == 4
    # Verify they were backspaces
    mock_keyboard.press.assert_has_calls([call(Key.backspace)] * 4)
    mock_keyboard.type.assert_called_once_with("testing")
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
