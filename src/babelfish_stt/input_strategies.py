import logging
import sys
import time

import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

# Chunked-erase envelope (fast-speech live evidence, 2026-10-04 session):
# backspace bursts ≤ ~82 keystrokes were delivered reliably by Notepad++
# in every live run (normal-speed committed frames maxed at 82); bursts
# ≥ 100 dropped events and scarred the run (drifted mirrors, mid-word
# cuts, stale fragments). The boundary is unmeasured somewhere in
# 82–100. Bursts within the proven envelope fire exactly as before; only
# larger bursts are split, with a short gap so the editor processes
# every event. Mechanism-agnostic by design: whatever drops events at
# high burst intensity, lower per-chunk intensity helps.
ERASE_CHUNK = 60          # keystrokes per chunk (60 keys = 120 injected events)
ERASE_CHUNK_GAP_S = 0.015 # gap between chunks (unmeasured; tune 10 → 15 → 25ms)
ERASE_SETTLE_S = 0.010    # settle before returning, chunked bursts only


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
    within the proven-deliverable envelope (≤ ERASE_CHUNK) fire exactly
    as before, unpaced: the typing worker paces the applies themselves
    (see InputSimulator.TYPING_THROTTLE_S). Larger bursts are chunked —
    ERASE_CHUNK press/release pairs, a short ERASE_CHUNK_GAP_S gap, then
    the remainder — so the editor processes every event instead of
    dropping keystrokes at high burst intensity (the fast-speech
    failure mode), followed by one ERASE_SETTLE_S so a caller's paste
    chord lands strictly after the erase completed.
    """
    if count <= 0:
        return
    try:
        if count <= ERASE_CHUNK:
            for _ in range(count):
                keyboard.press(Key.backspace)
                keyboard.release(Key.backspace)
            return
        remaining = count
        while remaining > 0:
            chunk = min(ERASE_CHUNK, remaining)
            for _ in range(chunk):
                keyboard.press(Key.backspace)
                keyboard.release(Key.backspace)
            remaining -= chunk
            if remaining > 0:
                time.sleep(ERASE_CHUNK_GAP_S)
        # Called from paced applies, but a chunked burst can be followed
        # immediately by the caller's paste chord; give the editor a
        # moment so the paste cannot swallow the erase tail.
        time.sleep(ERASE_SETTLE_S)
    except Exception as e:
        logger.error(f"Backspace failed: {e}")
        # Re-raise so the caller's mirror-trust handling sees the
        # failure: InputSimulator._send_backspaces (and the worker's
        # catch-all) untrust the mirrors and log on the raised
        # exception. Swallowing here would leave the mirror claiming
        # screen state the burst never established.
        raise
