import logging
import unicodedata
import time
from typing import Optional

import grapheme
from pynput.keyboard import Controller

from babelfish_stt.ghost_composer import GhostComposer
from babelfish_stt.input_strategies import paste_text, send_backspaces
from babelfish_stt.config import SeparatorPolicy

logger = logging.getLogger(__name__)


class InputSimulator:
    """
    Types Ghost and Final text into the focused application.

    Ghost composition is span-based and shared with the terminal display
    (ADR 0010): the GhostComposer folds each sliding-window transcription
    into one growing line, and every applied update erases the displayed
    line and re-pastes the full composed line — the typing mechanics from
    ADR 0009 are untouched. The backspace count is derived from exactly the
    line the composer produced, so what is tracked and what is on screen
    can no longer diverge.
    """

    def __init__(self, keyboard_controller=None, throttle_s: float = 0.05):
        # Allow injecting a mock controller for testing
        self.keyboard = keyboard_controller or Controller()
        self.throttle_s = throttle_s
        self.last_ghost_time = 0.0
        self.last_final_char = ""

        # The one ghost-composition state: span-based, shared with the
        # terminal display (ADR 0010).
        self.composer = GhostComposer()

        # What is actually displayed on screen — the single backspace-counting
        # source of truth. What is tracked (the composed line) and what is
        # pasted always coincide: both derive from the composer's line.
        self.displayed_graphemes = []  # list of individual graphemes
        self._accumulated_text = ""

        self._last_applied = None
        self._after_finalize = False

    @property
    def last_ghost_length(self) -> int:
        return len(self.displayed_graphemes)

    @property
    def accumulated_text(self) -> str:
        """Returns the text from all ghost updates applied to the screen."""
        return self._accumulated_text

    def type_text(self, text: str):
        """Injects the given text via the clipboard paste (ADR 0009)."""
        if not text:
            return
        try:
            paste_text(text, self.keyboard)
        except Exception as e:
            logger.error(f"Failed to paste text: {e}")

    def update_ghost(self, ghost_text: Optional[str], window=None):
        """
        Composes the new Ghost through the shared span-based composer and
        then performs erase-all + paste-the-full-line typing.

        `window` is the Ghost's audio coverage as
        (window_start_sample, buffer_end_sample), provided by the pipeline
        through InputDisplay.
        """
        # If we're starting fresh after finalize, silently clear any stale state
        # without sending backspaces. The user may have edited/moved the cursor
        # after the last utterance ended.
        if self._after_finalize and self.displayed_graphemes:
            self.displayed_graphemes = []
            self._accumulated_text = ""
            self.composer.reset()
            self._after_finalize = False

        if not ghost_text:
            self._clear_previous()
            self.composer.reset()
            self._last_applied = None
            self.last_ghost_time = 0.0
            return

        # 1. Early exit: redundant frame. The key is (text, window) so an
        # identical re-transcription over a slid window still composes; and
        # the key is recorded only after a frame is actually applied, so a
        # throttle-dropped frame can never poison it (ADR 0010).
        if (ghost_text, window) == self._last_applied:
            return

        # 2. Compose BEFORE the throttle gate: the composer state must
        # advance on every frame (mirroring the terminal display), and any
        # throttle-skipped frame's typing is superseded by the next applied
        # one's full-line paste.
        composed = self.composer.update(ghost_text, window)
        if not composed:
            return

        now = time.time()

        # 3. Throttling: only gate the keystrokes, never the composition.
        if self.displayed_graphemes and now - self.last_ghost_time < self.throttle_s:
            return

        # 4. Content check: the composed line already matches what is on
        # screen — nothing to type; the dedup key records this frame.
        if composed == self._accumulated_text and self.displayed_graphemes:
            self._last_applied = (ghost_text, window)
            return

        # 5. Clear all displayed text and paste the full composed ghost.
        # The count derives from exactly the line we last pasted, so the
        # tracked and displayed states cannot drift apart.
        if self.displayed_graphemes:
            self._send_backspaces(len(self.displayed_graphemes))

        composed_graphemes = list(grapheme.graphemes(composed)) if composed else []
        if composed:
            self.type_text(composed)
            self._accumulated_text = composed

        self.displayed_graphemes = composed_graphemes
        self.last_ghost_time = now
        self._last_applied = (ghost_text, window)

    def finalize(
        self,
        text: str,
        separator: SeparatorPolicy = SeparatorPolicy.TRAILING,
    ):
        """Finalizes the transcription by clearing any ghost text."""
        # Capture accumulated text before clearing (for testing/verification)
        self.pre_finalize_text = "".join([str(g) for g in self.displayed_graphemes])

        # State verification: check if displayed_graphemes matches accumulated text
        # If they don't match, we may have state drift and should use full clear
        expected_accumulated = "".join([str(g) for g in self.displayed_graphemes])
        state_mismatch = self._accumulated_text != expected_accumulated

        # Clear whatever is currently displayed on screen
        total_to_clear = len(self.displayed_graphemes)
        if total_to_clear:
            # If state mismatch detected, SKIP backspacing entirely
            # Safer to have ghost text remain than to erase user's content
            if state_mismatch:
                logger.warning(
                    f"State mismatch in finalize: skipping {total_to_clear} backspaces "
                    f"to prevent over-erasure. accumulated='{self._accumulated_text[:50]}...' "
                    f"vs displayed={len(self.displayed_graphemes)} graphemes. "
                    f"Will type final text without clearing."
                )
            else:
                self._send_backspaces(total_to_clear)

        self.displayed_graphemes = []
        self.composer.reset()
        self._last_applied = None
        self._accumulated_text = ""

        if text:
            text = unicodedata.normalize("NFC", text)
            if separator == SeparatorPolicy.TRAILING:
                # The separator is typed with this utterance, at the moment of
                # maximal knowledge — never guessed at the next Final.
                if not text[-1].isspace():
                    text += " "
            elif separator == SeparatorPolicy.LEADING:
                # Legacy: guess the separator at the next Final (old rule verbatim).
                if (
                    self.last_final_char
                    and not self.last_final_char.isspace()
                    and not text[0].isspace()
                ):
                    text = " " + text

            self.type_text(text)
            self.last_final_char = text[-1]

        # Mark that finalize completed - next ghost update should start fresh
        # without backspacing, since user may have edited/moved cursor
        self._after_finalize = True

    def reset(self):
        """Resets the state without backspacing."""
        self.displayed_graphemes = []
        self.composer.reset()
        self._last_applied = None
        self._accumulated_text = ""
        self.pre_finalize_text = ""
        self._after_finalize = False

    def _clear_previous(self):
        """Sends backspaces for the length of the displayed ghost."""
        if self.displayed_graphemes:
            self._send_backspaces(len(self.displayed_graphemes))
            self.displayed_graphemes = []
            self._accumulated_text = ""

    def _send_backspaces(self, count: int):
        """Sends N backspaces via the pynput backspace loop."""
        if count <= 0:
            return
        try:
            send_backspaces(count, self.keyboard)
        except Exception as e:
            logger.error(f"Failed to send backspaces: {e}")
