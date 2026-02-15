import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_keyboard():
    """Mock keyboard controller for testing InputSimulator."""
    return MagicMock()


@pytest.fixture
def mock_mouse():
    """Mock mouse controller (for completeness)."""
    return MagicMock()
