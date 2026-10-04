import logging
import sys
import time

import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

# Backspace pacing: pynput press/release pairs fire faster than some
# editors process synthesized keystrokes; a dropped backspace desyncs the
# display mirror and every later erase eats content BEFORE the utterance
# start. The pacing below is what the `graphemes` count assumes actually
# happened.
BACKSPACE_INTERVAL_S = 0.004

# Gap between an erase burst and the next paste chord: the paste must be
# processed strictly after the erase finished, or the paste text gets
# inserted before some backspaces were applied.
ERASE_PASTE_GAP_S = 0.01


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
    """Erases `count` graphemes with pynput backspace press/release pairs,
    paced so editors process every keystroke.

    A paste cannot delete, so this is the one backspace mechanism — the
    surviving behavior of the retired Direct strategy (ADR 0009). The
    pacing is load-bearing: a backspace dropped by the editor desyncs the
    typed-path mirror and the next erase eats real content to the left of
    the utterance start.
    """
    if count <= 0:
        return
    try:
        for i in range(count):
            if i:
                time.sleep(BACKSPACE_INTERVAL_S)
            keyboard.press(Key.backspace)
            keyboard.release(Key.backspace)
        time.sleep(ERASE_PASTE_GAP_S)
    except Exception as e:
        logger.error(f"Backspace failed: {e}")
