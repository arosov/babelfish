import logging
from pynput.keyboard import Controller, Key
from babelfish_stt.input_strategies import (
    InputStrategy,
    DirectStrategy,
    ClipboardStrategy,
    NativeStrategy,
    HybridStrategy,
)
from babelfish_stt.config import InputStrategy as StrategyEnum

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
        self.last_final_char = ""
        self._strategies = {
            StrategyEnum.DIRECT: DirectStrategy(),
            StrategyEnum.CLIPBOARD: ClipboardStrategy(),
            StrategyEnum.NATIVE: NativeStrategy(),
            StrategyEnum.HYBRID: HybridStrategy(),
        }
        self._direct = DirectStrategy()

    def type_text(self, text: str, strategy: StrategyEnum = StrategyEnum.DIRECT):
        """Types the given text using the selected strategy."""
        if not text:
            return
        try:
            impl = self._strategies.get(strategy, self._direct)
            impl.type(text, self.keyboard)
        except Exception as e:
            logger.error(f"Failed to type text with strategy {strategy}: {e}")

    def update_ghost(self, ghost_text: str):
        """
        Updates the ghost text by backspacing the previous one
        and typing the new one. Ghost text ALWAYS uses direct input.
        """
        self._clear_previous()
        if ghost_text:
            self.type_text(ghost_text, StrategyEnum.DIRECT)
            self.last_ghost_length = len(ghost_text)
        else:
            self.last_ghost_length = 0

    def finalize(self, text: str, strategy: StrategyEnum = StrategyEnum.DIRECT):
        """
        Finalizes the transcription by clearing any ghost text
        and typing the final result using the selected strategy.
        """
        self._clear_previous()
        if text:
            # Prepend space if the previous finalization didn't end with whitespace
            # and the current text doesn't start with whitespace.
            if (
                self.last_final_char
                and not self.last_final_char.isspace()
                and not text[0].isspace()
            ):
                text = " " + text

            self.type_text(text, strategy)
            self.last_final_char = text[-1]

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
