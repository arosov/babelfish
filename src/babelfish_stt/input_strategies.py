import logging
import sys
import time

import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

# Windows clipboard race: a clipboard viewer/manager can delay the
# SetClipboardData commit, and an immediately synthesized Ctrl+V then
# pastes STALE content (the previous frame's text). The typed-path
# mirror advances while the screen does not, and every later erase eats
# real content left of the utterance start. The read-back below verifies
# the clipboard actually holds the intended text before the chord goes
# out; the common case verifies instantly (no pacing, no visible cost).
CLIPBOARD_VERIFY_RETRIES = 10
CLIPBOARD_VERIFY_DELAY_S = 0.01


def _clipboard_holds(text: str) -> bool:
    """True when the clipboard verifiably holds `text`. Unreadable or
    non-string backends (mocked tests, exotic desktops) count as
    verified: verification is best-effort, never a paste blocker."""
    try:
        current = pyperclip.paste()
    except Exception:
        return False
    if not isinstance(current, str):
        return True
    return current == text


def paste_text(text: str, keyboard: Controller):
    """Injects text via the clipboard: copy, VERIFY, then synthesize the
    paste chord.

    The one input strategy (ADR 0009). Unicode-proof, atomic, and fast
    regardless of utterance length. Linux terminal chord selection
    (Ctrl+Shift+V vs Ctrl+V) is ADR 0008 intent, not yet implemented.
    """
    if not text:
        return

    # Save current clipboard? (Restoration is tricky and racy, skipping for now)
    pyperclip.copy(text)

    # Verify the clipboard settled on the intended text before the
    # chord: pasting stale content desyncs the mirror from the screen.
    for attempt in range(CLIPBOARD_VERIFY_RETRIES):
        if _clipboard_holds(text):
            break
        if attempt == CLIPBOARD_VERIFY_RETRIES - 1:
            logger.warning(
                "Clipboard did not settle on the pasted text; "
                "sending the chord anyway"
            )
        else:
            time.sleep(CLIPBOARD_VERIFY_DELAY_S)

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
    surviving behavior of the retired Direct strategy (ADR 0009).
    """
    if count <= 0:
        return
    try:
        for _ in range(count):
            keyboard.press(Key.backspace)
            keyboard.release(Key.backspace)
    except Exception as e:
        logger.error(f"Backspace failed: {e}")
