import logging
from pynput.keyboard import Controller

logger = logging.getLogger("babelfish.typer")

class TyperManager:
    def __init__(self):
        self.keyboard = Controller()
        
    def type_text(self, text: str):
        """Types the provided text followed by a space."""
        if not text:
            return
        
        logger.debug(f"Typing text: '{text}'")
        self.keyboard.type(text)
        self.keyboard.type(" ")