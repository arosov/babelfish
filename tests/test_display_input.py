import pytest
from unittest.mock import MagicMock, patch
from babelfish_stt.display import InputDisplay


@pytest.fixture
def mock_config_manager():
    manager = MagicMock()
    manager.config.system_input.enabled = True
    manager.config.system_input.type_ghost = True
    return manager


def test_input_display_update_enabled(mock_config_manager):
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.update(ghost="hello")
        mock_sim.update_ghost.assert_called_once_with("hello")


def test_input_display_update_disabled(mock_config_manager):
    mock_config_manager.config.system_input.enabled = False
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.update(ghost="hello")
        mock_sim.update_ghost.assert_not_called()


def test_input_display_finalize(mock_config_manager):
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.finalize("final")
        mock_sim.finalize.assert_called_once_with("final")
