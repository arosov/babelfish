import logging
import sys

import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)


def paste_text(text: str, keyboard: Controller):
    """Injects text via the clipboard: copy, then synthesize the paste chord.

    The one input strategy (ADR 0009). Unicode-proof, atomic, and fast
    regardless of utterance length. Linux terminal chord selection
    (Ctrl+Shift+V vs Ctrl+V) is ADR 0008 intent, not yet implemented.
    """
    if not text:
        return

    # Save current clipboard? (Restoration is tricky and racy, skipping for now)
    pyperclip.copy(text)

    # Simulate Paste
    if sys.platform == "darwin":
        with keyboard.pressed(Key.cmd):
            keyboard.press("v")
            keyboard.release("v")
    else:
        with keyboard.pressed(Key.ctrl):
            keyboard.press("v")
            keyboard.release("v")


def send_backspaces(count: int, keyboard: Controller):
    """Erases `count` graphemes with pynput backspace press/release pairs.

    A paste cannot delete, so this is the one backspace mechanism — the
    surviving behavior of the retired Direct strategy (ADR 0009). Bursts
    are not paced here: the typing worker paces the applies themselves
    (see InputSimulator.TYPING_THROTTLE_S), which bounded the whole
    keystroke regime in the proven-good live era.
    """
    if count <= 0:
        return
    try:
        for _ in range(count):
            keyboard.press(Key.backspace)
            keyboard.release(Key.backspace)
    except Exception as e:
        logger.error(f"Backspace failed: {e}")
