import logging
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)


class InputSimulator:
    """
    Simulates keyboard input for system-wide transcription injection.
    Tracks ghost text length to correctly 'replace' it with updated or final text.
    """

    def __init__(self, keyboard_controller=None):
        # Allow injecting a mock controller for testing
        self.keyboard = keyboard_controller or Controller()
        self.last_ghost_length = 0

    def type_text(self, text: str):
        """Types the given text using the keyboard controller."""
        if not text:
            return
        try:
            self.keyboard.type(text)
        except Exception as e:
            logger.error(f"Failed to type text: {e}")

    def update_ghost(self, ghost_text: str):
        """
        Updates the ghost text by backspacing the previous one
        and typing the new one.
        """
        self._clear_previous()
        if ghost_text:
            self.type_text(ghost_text)
            self.last_ghost_length = len(ghost_text)
        else:
            self.last_ghost_length = 0

    def finalize(self, text: str):
        """
        Finalizes the transcription by clearing any ghost text
        and typing the final result.
        """
        self._clear_previous()
        if text:
            self.type_text(text)
        # Reset tracking
        self.last_ghost_length = 0

    def _clear_previous(self):
        """Sends backspaces for the length of the last typed ghost."""
        if self.last_ghost_length > 0:
            try:
                for _ in range(self.last_ghost_length):
                    self.keyboard.press(Key.backspace)
                    self.keyboard.release(Key.backspace)
            except Exception as e:
                logger.error(f"Failed to send backspaces: {e}")
            self.last_ghost_length = 0
