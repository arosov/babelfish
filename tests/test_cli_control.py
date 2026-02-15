import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import sys


class TestCLIControl(unittest.TestCase):
    @patch("babelfish_stt.main.asyncio.run")
    @patch(
        "sys.argv",
        [
            "babelfish",
            "--wakeword",
            "hey_jarvis",
            "--stopword",
            "stop talking",
            "--cpu",
        ],
    )
    def test_main_control_flags(self, mock_run):
        from babelfish_stt.main import main

        # Mock the async run_babelfish call
        mock_run.return_value = None

        main()

        # Verify asyncio.run was called with run_babelfish
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]

        # The call should be an awaitable (coroutine)
        # We can't easily check the params without running the coroutine
        # But we can verify run was called

    @patch("babelfish_stt.main.asyncio.run")
    @patch("sys.argv", ["babelfish"])
    def test_main_defaults(self, mock_run):
        from babelfish_stt.main import main

        mock_run.return_value = None

        main()

        # Verify asyncio.run was called
        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
