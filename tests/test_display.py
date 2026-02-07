import unittest
from unittest.mock import patch, MagicMock
import io
from babelfish_stt.display import TerminalDisplay

class TestDisplay(unittest.TestCase):
    def test_display_initialization(self):
        display = TerminalDisplay()
        self.assertEqual(display.last_text, "")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_update_streaming(self, mock_stdout):
        display = TerminalDisplay()
        display.update("Hello")
        
        # Should contain the text and carriage return
        output = mock_stdout.getvalue()
        self.assertIn("Hello", output)
        self.assertIn("\r", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_finalize(self, mock_stdout):
        display = TerminalDisplay()
        display.finalize("Hello world")
        
        # Should contain the text and a newline
        output = mock_stdout.getvalue()
        self.assertIn("Hello world", output)
        self.assertIn("\n", output)
        self.assertEqual(display.last_text, "")

if __name__ == '__main__':
    unittest.main()