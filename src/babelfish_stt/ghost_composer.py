"""Shared span-based Ghost line composition (ADR 0010).

Every Ghost is the transcription of a sliding window over the utterance
audio, so consecutive updates overlap and may revise words inside the
shared region. This composer folds them into one growing line.

The window span is ground truth: it says exactly how much audio left the
window, so it bounds how many words may commit per update. Text
alignment only refines the boundary within that bound — never beyond it
(words the new Ghost still re-covers must stay live and revisable).
Trusting text over the span is what mass-committed the live tail on
coincidental one-word runs and piled the line up as duplicates. When the
model re-words the shared region the alignment fails and the audio-time
proportion commits the aged-out head; when a Ghost claims far more words
than its window can hold it is a degenerate TDT loop and commits
nothing.

One algorithm serves two consumers — the terminal display and the typed
InputSimulator — so both Ghost renderings append while you speak and
agree by construction. The composed path deliberately does not
reintroduce the fuzzy word-stitching heuristics this replaces (and never
the GLOSSARY's avoided vocabulary for Ghost text).
"""

import math
from typing import Optional

# Characters stripped when comparing words across Ghost updates
WORD_STRIP = ".,!?;:\"'`—–-…()[]"

# How far past the audio-truth bound a commit may reach: boundary fuzz
# between word timing and sample-aligned window edges.
COMMIT_MARGIN = 1

# A text alignment shorter than this many shared words is coincidence —
# a single shared function word ("la") pins no boundary.
MIN_SOLID_J = 2

# A sliding window holds at most this many words per second of audio
# (fast French dictation). A Ghost claiming far more than its window's
# duration allows is a degenerate TDT loop (repetition seam).
MAX_WORDS_PER_SECOND = 8

SAMPLE_RATE = 16000


def _norm_word(word: str) -> str:
    return word.lower().strip(WORD_STRIP)


def _text_overlap_words(prev_words: list[str], new_words: list[str]) -> Optional[int]:
    """
    Largest j where the last j words of the previous Ghost match the
    first j words of the new Ghost (case/punctuation-insensitive), or
    None when no solid alignment exists (the model re-worded the shared
    region). Solidity scales with j: short overlaps must match almost
    perfectly, or they are coincidence.
    """
    a = [_norm_word(w) for w in prev_words]
    b = [_norm_word(w) for w in new_words]
    max_j = min(len(a), len(b))
    best_j, best_score = 0, -1
    for j in range(max_j + 1):
        score = sum(1 for i in range(j) if a[len(a) - j + i] == b[i])
        # Prefer more matches; on ties prefer the larger overlap (commit
        # less, leaving text revisable by later updates).
        if score > best_score or (score == best_score and j > best_j):
            best_j, best_score = j, score
    if best_j < MIN_SOLID_J or best_score < math.ceil(2 * best_j / 3):
        return None  # ambiguous: the model re-worded the shared region
    return best_j


class GhostComposer:
    """
    Folds successive sliding-window Ghost transcriptions into one
    append-only line (ADR 0010). One instance per consumer, reset per
    utterance.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.committed: list[str] = []  # words whose audio left the window
        self.live: list[str] = []  # words of the latest Ghost (current window)
        self.line: str = ""  # composed Ghost line
        self.window: tuple[int, int] = (0, 0)  # (start, end) samples of the latest Ghost's window
        self._prev_degenerate: bool = False  # the previous Ghost was a TDT loop

    def update(self, ghost: str, window=None) -> str:
        """
        Fold a new Ghost (one window transcription) into the accumulated
        Ghost line: commit words whose audio left the window, keep the
        rest revisable by later updates. Returns the composed line.
        """
        ghost = ghost.strip()
        if not ghost:
            return self.line

        new_words = ghost.split()
        degenerate = self._is_degenerate(new_words, window)
        if self.live:
            if degenerate:
                # Loop guard: this Ghost's text is a repetition seam — no
                # text alignment and no dedup may derive from it. The
                # audio truth still commits the aged-out head.
                self.committed.extend(self.live[: self._audio_commit(self.live, window)])
            else:
                commit = self._commit_count(self.live, new_words, window)
                self.committed.extend(self.live[:commit])
                # If the new Ghost re-covers committed tail words (boundary
                # errors from rough proportional commits), drop the duplicates:
                # the live tail shows them, so nothing is lost. The dedup may
                # not reach deeper than what the audio bound sanctioned.
                self._dedup_tail(new_words, max(commit, COMMIT_MARGIN + 1))
        if window is not None:
            self.window = window
        self.live = new_words
        self._prev_degenerate = degenerate
        self.line = " ".join(self.committed + new_words)
        return self.line

    def _is_degenerate(self, words: list[str], window) -> bool:
        """A Ghost whose word count exceeds its window's plausible word
        budget is a TDT loop; nothing may derive from its text."""
        if window is None:
            return False
        window_dur_s = (window[1] - window[0]) / SAMPLE_RATE
        if window_dur_s <= 0:
            return False
        return len(words) > window_dur_s * MAX_WORDS_PER_SECOND

    def _commit_count(self, prev_words, new_words, window) -> int:
        """
        How many head words of the previous Ghost have aged out of the
        Ghost window and should be committed.

        The span is ground truth: the previous window's coverage says how
        much audio left, so the commit is bounded by that proportion plus
        a one-word margin. Text alignment refines the boundary within
        that bound — a coincidental short run can never mass-commit the
        live tail. Without a usable span the text alignment decides
        alone; without either, nothing commits (the new Ghost replaces
        the live tail).
        """
        if window is not None:
            prev_start, prev_end = self.window
            window_dur = prev_end - prev_start
            if window_dur > 0:
                slide = max(0, window[0] - prev_start)
                # A degenerate previous Ghost's words are garbage: no
                # text alignment against them, and its word count must
                # not inflate the proportion (the plausible budget caps
                # it below).
                if self._prev_degenerate:
                    return self._audio_commit(prev_words, window)

                j = _text_overlap_words(prev_words, new_words)
                if j is not None and j > 0:
                    # Text refines the boundary — within the audio bound.
                    bound = self._audio_bound(prev_words, slide, window_dur)
                    return max(0, min(len(prev_words) - j, bound))
                return self._audio_commit(prev_words, window)

        # No usable span: the text alignment decides alone.
        j = _text_overlap_words(prev_words, new_words)
        if j is not None and j > 0:
            return len(prev_words) - j
        return 0

    def _plausible_words(self, prev_words, window_dur: int) -> int:
        """Word budget a window of `window_dur` samples can plausibly have
        held: a degenerate previous Ghost (TDT loop) must not inflate the
        audio proportion with its garbage word count."""
        return min(
            len(prev_words),
            max(1, round(window_dur / SAMPLE_RATE * MAX_WORDS_PER_SECOND)),
        )

    def _audio_bound(self, prev_words, slide: int, window_dur: int) -> int:
        """Words the audio truth allows committing: the proportion of the
        previous window that slid out, plus boundary-fuzz margin."""
        plausible = self._plausible_words(prev_words, window_dur)
        return min(
            math.ceil(plausible * slide / window_dur) + COMMIT_MARGIN,
            len(prev_words),
        )

    def _audio_commit(self, prev_words, window) -> int:
        """Audio-time proportional commit (no text alignment): the share
        of the previous window that slid out, in words."""
        prev_start, prev_end = self.window
        window_dur = prev_end - prev_start
        if window_dur <= 0:
            return 0
        slide = max(0, window[0] - prev_start)
        plausible = self._plausible_words(prev_words, window_dur)
        count = round(plausible * slide / window_dur)
        return max(0, min(count, len(prev_words)))

    def _dedup_tail(self, new_words: list[str], max_trim: int):
        """
        Loose normalized dedup, bounded: if the tail of the committed
        words matches the head of the new Ghost (at least half the words
        align), those committed words are duplicates the live tail
        re-shows — drop them, but never more than `max_trim`: the audio
        bound sanctioned committing at most that much, so the dedup may
        not reach deeper into words that genuinely aged out.
        """
        a = [_norm_word(w) for w in self.committed]
        b = [_norm_word(w) for w in new_words]
        max_j = min(len(a), len(b), max_trim)
        for j in range(max_j, 0, -1):
            matches = sum(1 for i in range(j) if a[len(a) - j + i] == b[i])
            if matches * 2 >= j:
                del self.committed[-j:]
                return
