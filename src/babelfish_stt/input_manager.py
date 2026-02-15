import logging
import unicodedata
import grapheme
import time
import re
import difflib
from rapidfuzz import fuzz
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
        self.words = []  # List of strings (ghost state for stitching)
        self.graphemes = []  # List of individual graphemes (ghost state)

        # Track what's actually displayed on screen (for accumulation)
        self.displayed_graphemes = []  # List of individual graphemes

        # Track "committed" text - content from non-overlapping windows that should persist
        self.committed_grapheme_count = 0

        # Track accumulated text continuously (for testing/verification)
        self._accumulated_text = ""
        self.pre_finalize_text = ""

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

    @property
    def accumulated_text(self) -> str:
        """Returns the accumulated text from all ghost updates."""
        return self._accumulated_text

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

        # 6. Accumulate logic
        # Find grapheme-level common prefix
        common_len = 0
        for g1, g2 in zip(self.displayed_graphemes, new_graphemes):
            if g1 == g2:
                common_len += 1
            else:
                break

        # If there's NO overlap (common_len == 0), we just APPEND without backspacing
        # This handles STT sliding window case
        if common_len == 0:
            # No overlap - APPEND without backspacing
            if new_graphemes:
                to_add = "".join([str(g) for g in new_graphemes])
                self.type_text(to_add, StrategyEnum.DIRECT)
                # Track accumulated text
                self._accumulated_text += to_add
                # Track these graphemes as committed (they came from a non-overlapping window)
                self.committed_grapheme_count = len(new_graphemes)
        else:
            # Has overlap - but we need to be careful not to destroy content we appended earlier
            # Only backspace the EXACT suffix that differs
            # Compute what's currently displayed
            current_displayed = "".join(self.displayed_graphemes)

            # Find where new ghost diverges from displayed
            # We only want to backspace the part that the new ghost doesn't have
            new_text_str = "".join(new_graphemes)

            # Find the longest suffix of displayed that matches a prefix of new
            # but don't backspace more than the length difference would suggest
            to_remove = len(self.displayed_graphemes) - common_len
            if to_remove > 0:
                self._send_backspaces(to_remove, update_accumulated=True)

            # Type only the NEW suffix (beyond the common prefix)
            to_add_list = new_graphemes[common_len:]
            if to_add_list:
                to_add = "".join([str(g) for g in to_add_list])
                self.type_text(to_add, StrategyEnum.DIRECT)
                # Track accumulated text
                self._accumulated_text += to_add

        # 7. Update State
        self.words = new_words
        self.graphemes = new_graphemes
        self.displayed_graphemes = new_graphemes
        self.last_ghost_time = now

    def _stitch_words(self, base_words: list[str], ext_words: list[str]) -> list[str]:
        """
        Uses fuzzy matching on the tail of the word list to find overlaps.
        Handles both overlapping (STT returning similar segments) and
        non-overlapping (sliding window) cases.
        """
        if not base_words:
            return ext_words

        tail_size = 30
        base_tail = base_words[-tail_size:]

        def clean(w):
            return self._clean_regex.sub("", w).lower()

        base_clean = [clean(w) for w in base_tail]
        ext_clean = [clean(w) for w in ext_words]

        # Try exact match first (fast path)
        matcher = difflib.SequenceMatcher(None, base_clean, ext_clean, autojunk=False)
        match = matcher.find_longest_match(0, len(base_clean), 0, len(ext_clean))

        if match.size > 3:  # Require at least 3 word overlap for exact match
            join_idx = (len(base_words) - len(base_tail)) + match.a
            return base_words[:join_idx] + ext_words[match.b :]

        # Try fuzzy matching with rapidfuzz
        # Compare suffix of base with prefix of ext to find fuzzy overlap
        best_score = 0
        best_k = 0  # Number of words to overlap

        # Check overlaps of different lengths
        for k in range(min(len(base_clean), len(ext_clean)), 0, -1):
            base_suffix = "".join(base_clean[-k:])
            ext_prefix = "".join(ext_clean[:k])

            if len(base_suffix) < 3:
                continue

            # Use partial_ratio for substring matching
            score = fuzz.partial_ratio(base_suffix, ext_prefix)

            if score > best_score:
                best_score = score
                best_k = k

        # If fuzzy match is good enough (>70%), use it
        if best_score > 70 and best_k > 0:
            join_idx = len(base_words) - best_k
            return base_words[:join_idx] + ext_words

        # No overlap found - check if it's a new segment vs replacement
        if len(base_words) < 10 or (
            len(ext_words) >= 5 and not any(w in base_clean for w in ext_clean[:5])
        ):
            return ext_words

        # Fallback: return base_words (keep existing state)
        return base_words

    def finalize(self, text: str, strategy: StrategyEnum = StrategyEnum.DIRECT):
        """Finalizes the transcription by clearing any ghost text."""
        # Capture accumulated text before clearing (for testing/verification)
        self.pre_finalize_text = "".join(self.displayed_graphemes)

        # Clear both committed and current ghost text
        total_to_clear = self.committed_grapheme_count + len(self.graphemes)
        if total_to_clear:
            self._send_backspaces(total_to_clear)

        # Safety delay to ensure the target application has processed backspaces
        # before we paste the final text. Prevents "Comment comment" repetitions.
        time.sleep(0.05)

        self.words = []
        self.graphemes = []
        self.committed_grapheme_count = 0

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
        self.displayed_graphemes = []
        self.committed_grapheme_count = 0
        self._last_raw_ghost = ""
        self._accumulated_text = ""
        self.pre_finalize_text = ""

    def _clear_previous(self):
        """Sends backspaces for the length of the last typed ghost."""
        if self.graphemes:
            self._send_backspaces(len(self.graphemes))
            self.graphemes = []

    def _send_backspaces(self, count: int, update_accumulated: bool = False):
        """Sends N backspaces with a small delay between them."""
        if count <= 0:
            return
        try:
            for _ in range(count):
                self.keyboard.press(Key.backspace)
                self.keyboard.release(Key.backspace)
                # Track accumulated text if requested
                if update_accumulated and self._accumulated_text:
                    self._accumulated_text = self._accumulated_text[:-1]
                # Small delay to let the target application process the key event
                time.sleep(0.002)
        except Exception as e:
            logger.error(f"Failed to send backspaces: {e}")
