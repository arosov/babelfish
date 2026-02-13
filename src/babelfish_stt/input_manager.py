import logging
import unicodedata
import grapheme
import time
import re
import difflib
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
    Tracks ghost text state as a list of words and graphemes to achieve O(1)
    performance regardless of conversation length.
    """

    def __init__(self, keyboard_controller=None, throttle_s: float = 0.05):
        # Allow injecting a mock controller for testing
        self.keyboard = keyboard_controller or Controller()
        self.throttle_s = throttle_s
        self.last_ghost_time = 0.0
        self.last_final_char = ""

        # Internal state as lists for performance
        self.words = []  # List of strings
        self.graphemes = []  # List of individual graphemes

        self._strategies = {
            StrategyEnum.DIRECT: DirectStrategy(),
            StrategyEnum.CLIPBOARD: ClipboardStrategy(),
            StrategyEnum.NATIVE: NativeStrategy(),
            StrategyEnum.HYBRID: HybridStrategy(),
        }
        self._direct = DirectStrategy()
        self._last_raw_ghost = ""
        self._clean_regex = re.compile(r"[^a-zA-Z0-9]")

    @property
    def last_ghost_length(self) -> int:
        return len(self.graphemes)

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
        Updates the ghost text incrementally with O(1) complexity.
        """
        if not ghost_text:
            self._clear_previous()
            self.words = []
            self.graphemes = []
            self._last_raw_ghost = ""
            self.last_ghost_time = 0.0
            return

        # 1. Early exit: redundant websocket frame
        if ghost_text == self._last_raw_ghost:
            return
        self._last_raw_ghost = ghost_text

        now = time.time()

        # 2. Stitching (Word-level)
        # We only pass the tail of words to the stitcher
        ext_words = ghost_text.split()
        if not ext_words:
            return

        new_words = self._stitch_words(self.words, ext_words)

        # 3. Throttling
        # We only check timing for actual keystrokes
        if self.graphemes:
            if now - self.last_ghost_time < self.throttle_s:
                self.words = new_words
                return

        # 4. Content check
        if new_words == self.words and self.graphemes:
            return

        # 5. Incremental Grapheme Update
        # Convert the words back to a string for grapheme parsing,
        # but ONLY if the list changed.
        new_text = " ".join(new_words)
        new_graphemes = list(grapheme.graphemes(new_text))

        # 6. Diff & Type
        common_len = 0
        for g1, g2 in zip(self.graphemes, new_graphemes):
            if g1 == g2:
                common_len += 1
            else:
                break

        # Remove suffix
        to_remove = len(self.graphemes) - common_len
        if to_remove > 0:
            try:
                for _ in range(to_remove):
                    self.keyboard.press(Key.backspace)
                    self.keyboard.release(Key.backspace)
            except Exception as e:
                logger.error(f"Failed to send backspaces: {e}")

        # Type suffix
        to_add_list = new_graphemes[common_len:]
        if to_add_list:
            to_add = "".join([str(g) for g in to_add_list])
            self.type_text(to_add, StrategyEnum.DIRECT)

        # 7. Update State
        self.words = new_words
        self.graphemes = new_graphemes
        self.last_ghost_time = now

    def _stitch_words(self, base_words: list[str], ext_words: list[str]) -> list[str]:
        """
        Uses SequenceMatcher on the tail of the word list. O(1) performance.
        """
        if not base_words:
            return ext_words

        # Tail window for O(1) matching
        tail_size = 30
        base_tail = base_words[-tail_size:]

        # Clean versions for matching (lower case, alphanumeric only)
        # We MUST use lower() here to ensure case-insensitive alignment.
        def clean(w):
            return self._clean_regex.sub("", w).lower()

        base_clean = [clean(w) for w in base_tail]
        ext_clean = [clean(w) for w in ext_words]

        # Use SequenceMatcher to find the longest overlap
        matcher = difflib.SequenceMatcher(None, base_clean, ext_clean, autojunk=False)
        match = matcher.find_longest_match(0, len(base_clean), 0, len(ext_clean))

        if match.size > 0:
            # Overlap found. Join index in global word list:
            join_idx = (len(base_words) - len(base_tail)) + match.a

            # Reconstruction:
            # We take the ORIGINAL base words up to the match,
            # then ALL ext words from the match point.
            # This handles case changes (Comment -> comment) by preferring the latest version.
            return base_words[:join_idx] + ext_words[match.b :]

        # Fallback: if no overlap found in the tail, we might have a drift.
        # Instead of just returning base_words (which "squashes" the update),
        # we trust the new ghost text if it's substantial or if we have little history.
        if len(base_words) < 10 or (
            len(ext_words) >= 5 and not any(w in base_clean for w in ext_clean[:5])
        ):
            return ext_words

        return base_words

    def finalize(self, text: str, strategy: StrategyEnum = StrategyEnum.DIRECT):
        """Finalizes the transcription by clearing any ghost text."""
        self._clear_previous()

        # Safety delay to ensure the target application has processed backspaces
        # before we paste the final text. Prevents "Comment comment" repetitions.
        time.sleep(0.05)

        self.words = []
        self.graphemes = []

        if text:
            text = unicodedata.normalize("NFC", text)
            if (
                self.last_final_char
                and not self.last_final_char.isspace()
                and not text[0].isspace()
            ):
                text = " " + text

            self.type_text(text, strategy)
            self.last_final_char = text[-1]

    def reset(self):
        """Resets the state without backspacing."""
        self.words = []
        self.graphemes = []
        self._last_raw_ghost = ""

    def _clear_previous(self):
        """Sends backspaces for the length of the last typed ghost."""
        if self.graphemes:
            try:
                for _ in range(len(self.graphemes)):
                    self.keyboard.press(Key.backspace)
                    self.keyboard.release(Key.backspace)
            except Exception as e:
                logger.error(f"Failed to send backspaces: {e}")
            self.graphemes = []
