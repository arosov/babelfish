import pytest
from unittest.mock import MagicMock, patch
from babelfish_stt.display import InputDisplay


@pytest.fixture
def mock_config_manager():
    manager = MagicMock()
    manager.config.system_input.enabled = True
    manager.config.system_input.type_ghost = True
    manager.config.system_input.typing_throttle_ms = 350
    return manager


def test_input_display_sets_typing_throttle_from_config(mock_config_manager):
    """The typing throttle rides the config: ms converted to seconds before
    each frame is enqueued (hot-reloadable, no restart)."""
    mock_config_manager.config.system_input.typing_throttle_ms = 250
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.update(ghost="hello")
        assert mock_sim.throttle_s == pytest.approx(0.25)


def test_input_display_typing_throttle_hot_reload(mock_config_manager):
    """A config change between frames takes effect on the next frame."""
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.update(ghost="first")
        assert mock_sim.throttle_s == pytest.approx(0.35)

        mock_config_manager.config.system_input.typing_throttle_ms = 600
        display.update(ghost="second")
        assert mock_sim.throttle_s == pytest.approx(0.6)


def test_input_display_update_enabled(mock_config_manager):
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.update(ghost="hello")
        mock_sim.enqueue_ghost.assert_called_once_with("hello", window=None)


def test_input_display_forwards_window_span(mock_config_manager):
    """The Ghost window span rides through to the simulator (ADR 0010)."""
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.update(ghost="hello", window=(5120, 21120))
        mock_sim.enqueue_ghost.assert_called_once_with(
            "hello", window=(5120, 21120)
        )


def test_input_display_update_disabled(mock_config_manager):
    mock_config_manager.config.system_input.enabled = False
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.update(ghost="hello")
        mock_sim.enqueue_ghost.assert_not_called()


def test_input_display_finalize(mock_config_manager):
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value

        display.finalize("final")
        # Only separator is passed from config; injection is always clipboard (ADR 0009)
        mock_sim.enqueue_finalize.assert_called_once_with(
            "final",
            separator=mock_config_manager.config.system_input.separator,
        )


def test_input_display_finalize_disabled_clears_ghost(mock_config_manager):
    """Typing disabled mid-flight: the Final still clears the ghost."""
    mock_config_manager.config.system_input.enabled = False
    with patch("babelfish_stt.display.InputSimulator") as MockSim:
        display = InputDisplay(mock_config_manager)
        mock_sim = MockSim.return_value
        mock_sim.displayed_graphemes = ["h", "i"]

        display.finalize("")
        mock_sim.enqueue_finalize.assert_called_once_with("")
