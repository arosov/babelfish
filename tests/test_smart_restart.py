import unittest
from unittest.mock import MagicMock
from babelfish_stt.server import BabelfishServer
from babelfish_stt.config import BabelfishConfig, HardwareConfig, ServerConfig


class TestSmartRestart(unittest.TestCase):
    def test_reconfigure_no_restart_same_device(self):
        config_manager = MagicMock()
        config_manager.config = BabelfishConfig(
            hardware=HardwareConfig(device="cuda:0")
        )
        server = BabelfishServer(config_manager)

        server.initial_config.hardware.active_device = "cuda:0"

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

        new_config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        server.reconfigure(new_config)

        self.assertTrue(server.restart_required)

    def test_reconfigure_restart_on_server_change(self):
        config_manager = MagicMock()
        config_manager.config = BabelfishConfig(
            hardware=HardwareConfig(device="cpu"),
            server=ServerConfig(host="127.0.0.1", port=8123),
        )
        server = BabelfishServer(config_manager)
        server.initial_config.hardware.active_device = "cpu"

        new_config = BabelfishConfig(
            hardware=HardwareConfig(device="cpu"),
            server=ServerConfig(host="0.0.0.0", port=8123),
        )
        server.reconfigure(new_config)

        self.assertTrue(server.restart_required)


if __name__ == "__main__":
    unittest.main()
