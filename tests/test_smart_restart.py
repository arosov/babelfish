import unittest
from unittest.mock import MagicMock
from babelfish_stt.server import BabelfishServer
from babelfish_stt.config import BabelfishConfig, HardwareConfig


class TestSmartRestart(unittest.TestCase):
    def test_reconfigure_no_restart_same_device(self):
        config_manager = MagicMock()
        config_manager.config = BabelfishConfig(
            hardware=HardwareConfig(device="cuda:0")
        )
        server = BabelfishServer(config_manager)

        # Simulate active device being cuda:0 (detected during engine init)
        server.initial_config.hardware.active_device = "cuda:0"

        # New config with same explicit device
        new_config = BabelfishConfig(hardware=HardwareConfig(device="cuda:0"))
        server.reconfigure(new_config)

        self.assertFalse(server.restart_required)

    def test_reconfigure_no_restart_auto_to_active(self):
        config_manager = MagicMock()
        config_manager.config = BabelfishConfig(hardware=HardwareConfig(device="auto"))
        server = BabelfishServer(config_manager)

        # Simulate engine resolved 'auto' to 'cuda:0'
        server.initial_config.hardware.active_device = "cuda:0"

        # User switches from 'auto' to explicit 'cuda:0'
        new_config = BabelfishConfig(hardware=HardwareConfig(device="cuda:0"))
        server.reconfigure(new_config)

        self.assertFalse(server.restart_required)

    def test_reconfigure_restart_on_actual_change(self):
        config_manager = MagicMock()
        config_manager.config = BabelfishConfig(
            hardware=HardwareConfig(device="cuda:0")
        )
        server = BabelfishServer(config_manager)
        server.initial_config.hardware.active_device = "cuda:0"

        # Change to cpu
        new_config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        server.reconfigure(new_config)

        self.assertTrue(server.restart_required)


if __name__ == "__main__":
    unittest.main()
