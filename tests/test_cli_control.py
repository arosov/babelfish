import unittest
from unittest.mock import patch, MagicMock
import sys

class TestCLIControl(unittest.TestCase):
    @patch('babelfish_stt.main.run_babelfish')
    @patch('sys.argv', ['babelfish', '--wakeword', 'hey_jarvis', '--stopword', 'stop talking'])
    def test_main_control_flags(self, mock_run):
        from babelfish_stt.main import main
        main()
        mock_run.assert_called_with(
            double_pass=False, 
            wakeword='hey_jarvis', 
            stopword='stop talking'
        )

if __name__ == '__main__':
    unittest.main()
