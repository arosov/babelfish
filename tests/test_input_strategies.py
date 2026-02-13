import pytest
from unittest.mock import MagicMock, patch
from babelfish_stt.input_strategies import (
    DirectStrategy,
    ClipboardStrategy,
    HybridStrategy,
)


@pytest.fixture
def mock_keyboard():
    return MagicMock()


def test_direct_strategy(mock_keyboard):
    strategy = DirectStrategy()
    strategy.type("hello", mock_keyboard)
    mock_keyboard.type.assert_called_once_with("hello")


@patch("pyperclip.copy")
def test_clipboard_strategy(mock_copy, mock_keyboard):
    strategy = ClipboardStrategy()
    # Mock platform to non-mac
    with patch("sys.platform", "linux"):
        strategy.type("hello", mock_keyboard)
        mock_copy.assert_called_once_with("hello")
        # Check if Ctrl+V was simulated (simplified check)
        assert mock_keyboard.pressed.called


def test_hybrid_strategy_safe(mock_keyboard):
    strategy = HybridStrategy()
    with patch.object(DirectStrategy, "type") as mock_direct:
        strategy.type("safe text", mock_keyboard)
        mock_direct.assert_called_once_with("safe text", mock_keyboard)


@patch("pyperclip.copy")
def test_hybrid_strategy_unsafe(mock_copy, mock_keyboard):
    strategy = HybridStrategy()
    # Unsafe text (accents)
    strategy.type("café", mock_keyboard)
    mock_copy.assert_called_once_with("café")
