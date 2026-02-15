import logging
import unicodedata
import grapheme
import time
import re
import sys
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

        # Track what's actually displayed on screen
        self.displayed_graphemes = []  # List of individual graphemes

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
            if self.displayed_graphemes:
                # If we have displayed text but 0 overlap, it's a replacement/correction
                # that failed to stitch. We MUST clear the old text first.
                total_to_clear = len(self.displayed_graphemes)
                self._send_backspaces(
                    total_to_clear,
                    strategy=StrategyEnum.DIRECT,
                    update_accumulated=True,
                )

            # No overlap - APPEND without backspacing
            if new_graphemes:
                to_add = "".join([str(g) for g in new_graphemes])
                self.type_text(to_add, StrategyEnum.DIRECT)
                # Track accumulated text
                self._accumulated_text += to_add
        else:
            # Has overlap - but we need to be careful not to destroy content we appended earlier
            # Only backspace the EXACT suffix that differs
            # Compute what's currently displayed
            # Find where new ghost diverges from displayed
            to_remove = len(self.displayed_graphemes) - common_len
            if to_remove > 0:
                # We always use DIRECT strategy for intermediate ghost backspacing
                # to maintain the highest responsiveness and avoid clipboard interference
                self._send_backspaces(
                    to_remove, strategy=StrategyEnum.DIRECT, update_accumulated=True
                )

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

        # Pre-process ext_words to collapse consecutive duplicate words
        # This prevents STT repetitions from causing stitching issues
        ext_words_deduped = []
        prev_word = None
        for w in ext_words:
            clean_w = self._clean_regex.sub("", w).lower()
            prev_clean = (
                self._clean_regex.sub("", prev_word).lower() if prev_word else None
            )
            if clean_w and clean_w == prev_clean:
                continue
            ext_words_deduped.append(w)
            prev_word = w

        ext_words = ext_words_deduped
        if not ext_words:
            return base_words

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
        self.pre_finalize_text = "".join([str(g) for g in self.displayed_graphemes])

        # State verification: check if displayed_graphemes matches accumulated text
        # If they don't match, we may have state drift and should use full clear
        expected_accumulated = "".join([str(g) for g in self.displayed_graphemes])
        state_mismatch = self._accumulated_text != expected_accumulated

        # Clear whatever is currently displayed on screen
        total_to_clear = len(self.displayed_graphemes)
        if total_to_clear:
            # If state mismatch detected, log warning
            # This indicates ghost updates may have drifted from actual screen
            if state_mismatch:
                logger.warning(
                    f"State mismatch in finalize: accumulated='{self._accumulated_text[:50]}...' "
                    f"vs displayed={len(self.displayed_graphemes)} graphemes."
                )
            # We use the configured strategy for finalization backspacing
            # to be consistent with the configured injection method
            self._send_backspaces(total_to_clear, strategy=strategy)

        # Safety delay to ensure the target application has processed backspaces
        # before we paste the final text. Prevents "Comment comment" repetitions.
        # This is now also handled inside the strategy's backspace settle time,
        # but we keep a small extra buffer here just in case.
        time.sleep(0.01)

        self.words = []
        self.graphemes = []
        self.displayed_graphemes = []
        self._last_raw_ghost = ""
        self._accumulated_text = ""

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
        self._last_raw_ghost = ""
        self._accumulated_text = ""
        self.pre_finalize_text = ""

    def _clear_previous(self):
        """Sends backspaces for the length of the last typed ghost."""
        if self.displayed_graphemes:
            self._send_backspaces(len(self.displayed_graphemes))
            self.graphemes = []
            self.displayed_graphemes = []

    def _send_backspaces(
        self,
        count: int,
        strategy: StrategyEnum = StrategyEnum.DIRECT,
        update_accumulated: bool = False,
    ):
        """Sends N backspaces using the selected strategy."""
        if count <= 0:
            return
        try:
            impl = self._strategies.get(strategy, self._direct)
            impl.backspace(count, self.keyboard)

            # Update accumulated text tracking
            if update_accumulated and self._accumulated_text:
                # We remove the last 'count' graphemes
                # Note: this is a simple approximation as graphemes might be multiple chars
                # but in most cases backspace removes one 'visual' character.
                self._accumulated_text = (
                    self._accumulated_text[:-count]
                    if len(self._accumulated_text) >= count
                    else ""
                )
        except Exception as e:
            logger.error(f"Failed to send backspaces with strategy {strategy}: {e}")
