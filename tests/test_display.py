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
    def test_update_with_styles(self, mock_stdout):
        display = TerminalDisplay()
        # Refined = Bold (\033[1m), Ghost = Dim (\033[2m)
        display.update(refined="Fixed", ghost="maybe")
        
        output = mock_stdout.getvalue()
        self.assertIn("\033[1mFixed", output)
        self.assertIn("\033[2mmaybe", output)
        self.assertIn("\033[0m", output) # Reset code

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