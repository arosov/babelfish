import unittest
from unittest.mock import patch, MagicMock
import sys
from babelfish_stt.main import run_babelfish

class TestMainArgs(unittest.TestCase):
    @patch('babelfish_stt.main.run_babelfish')
    @patch('sys.argv', ['babelfish', '--double-pass'])
    def test_main_double_pass_flag(self, mock_run):
        from babelfish_stt.main import main
        main()
        mock_run.assert_called_with(double_pass=True)

    @patch('babelfish_stt.main.run_babelfish')
    @patch('sys.argv', ['babelfish'])
    def test_main_no_flag(self, mock_run):
        from babelfish_stt.main import main
        main()
        mock_run.assert_called_with(double_pass=False)

if __name__ == '__main__':
    unittest.main()
