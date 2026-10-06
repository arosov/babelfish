import unittest
from unittest.mock import patch, MagicMock
import io
import time

import babelfish_stt.display as display_module
from babelfish_stt.display import TerminalDisplay, MultiDisplay

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


class _CharmapStdout(io.StringIO):
    """A stdoutStub that encodes like a Windows cp1252 pipe: any character
    outside cp1252 raises UnicodeEncodeError, mirroring the loop-killer."""
    encoding = "cp1252"

    def write(self, s):
        try:
            s.encode("cp1252")
        except UnicodeEncodeError as e:
            raise UnicodeEncodeError(
                "charmap", s, e.start, e.end, e.reason
            )
        return super().write(s)


class TestTerminalDisplayUnicodeSafety(unittest.TestCase):
    """Regression: a Ghost containing characters outside the stream codec
    must degrade that console draw, never raise UnicodeEncodeError into
    the STT loop (main.py's 'Error in STT loop' harakiri)."""

    def _display(self):
        stdout = _CharmapStdout()
        with patch("babelfish_stt.display.sys") as mock_sys:
            mock_sys.stdout = stdout
            display = TerminalDisplay()
            display.update(refined="café", ghost="\U0001f9d4 run")
            # ASCII prefix flushes fine; the poisoned draw must degrade, not raise
        return stdout, display

    def test_degraded_draw_does_not_raise(self):
        stdout, _ = self._display()
        # \U0001f9d4 is outside cp1252 -> became replacement chars
        self.assertIn("?", stdout.getvalue())
        self.assertNotIn("\U0001f9d4", stdout.getvalue())

    def test_degrade_warns_once_then_stays_silent(self):
        with patch.object(display_module, "logger") as mock_logger:
            with patch("babelfish_stt.display.sys") as mock_sys:
                mock_sys.stdout = _CharmapStdout()
                display = TerminalDisplay()
                display.update(ghost="\U0001f9d4 one")
                time.sleep(TerminalDisplay.REDRAW_MIN_INTERVAL_S + 0.05)
                display.update(ghost="\U0001f9d4 two")
            self.assertEqual(mock_logger.warning.call_count, 1)


class _RaisingDisplay:
    def __init__(self):
        self.calls = []

    def update(self, *args, **kwargs):
        self.calls.append(("update", args, kwargs))
        raise RuntimeError("boom")

    def finalize(self, *args, **kwargs):
        self.calls.append(("finalize", args, kwargs))
        raise RuntimeError("boom")

    def reset(self):
        self.calls.append(("reset",))
        raise RuntimeError("boom")


class _RecordingDisplay:
    def __init__(self):
        self.calls = []

    def update(self, *args, **kwargs):
        self.calls.append(("update", args, kwargs))

    def finalize(self, *args, **kwargs):
        self.calls.append(("finalize", args, kwargs))

    def reset(self):
        self.calls.append(("reset",))


class TestMultiDisplayContainment(unittest.TestCase):
    """A failing backend must be bypassed, not take down the caller
    (the STT loop); the remaining backends still receive every frame."""

    def _make(self):
        raising, recording = _RaisingDisplay(), _RecordingDisplay()
        return MultiDisplay(raising, recording), raising, recording

    def test_failing_backend_does_not_propagate(self):
        multi, _, _ = self._make()
        multi.update(text="hello")
        multi.finalize(text="bye")
        multi.reset()

    def test_remaining_backends_receive_frames(self):
        multi, raising, recording = self._make()
        multi.update(text="hello")
        multi.finalize(text="bye")
        multi.reset()
        self.assertEqual(len(raising.calls), 3)  # it was attempted each time
        self.assertEqual(
            [c[0] for c in recording.calls], ["update", "finalize", "reset"]
        )

    def test_failures_reported_once_then_summarized(self):
        multi, _, _ = self._make()
        with self.assertLogs("babelfish_stt.display", level="ERROR") as logs:
            for _ in range(5):
                multi.update(text="x")
            self.assertEqual(len(logs.output), 1)  # only the first failure


if __name__ == '__main__':
    unittest.main()