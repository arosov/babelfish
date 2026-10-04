"""Shared span-based Ghost line composition (ADR 0010).

Every Ghost is the transcription of a sliding window over the utterance
audio, so consecutive updates overlap and may revise words inside the
shared region. This composer folds them into one growing line:

- words whose audio has left the window are committed (never rewritten);
- the live tail is replaced by each new Ghost, aligned against the
  previous Ghost's tail by word overlap, falling back to proportional
  audio-time commits from the pipeline-reported window span.

One algorithm serves two consumers — the terminal display and the typed
InputSimulator — so both Ghost renderings append while you speak and
agree by construction. The composed path deliberately does not
reintroduce the fuzzy word-stitching heuristics this replaces (and never
the GLOSSARY's avoided vocabulary for Ghost text).
"""

from typing import Optional

# Characters stripped when comparing words across Ghost updates
WORD_STRIP = ".,!?;:\"'`—–-…()[]"


def _norm_word(word: str) -> str:
    return word.lower().strip(WORD_STRIP)


def _text_overlap_words(prev_words: list[str], new_words: list[str]) -> Optional[int]:
    """
    Largest j where the last j words of the previous Ghost match the
    first j words of the new Ghost (case/punctuation-insensitive), or
    None when no solid alignment exists (the model re-worded the shared
    region). Solid means at least half the aligned words match.
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
    if best_score <= 0 or best_score * 2 < best_j:
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
        if self.live:
            commit = self._commit_count(self.live, new_words, window)
            self.committed.extend(self.live[:commit])
            # If the new Ghost re-covers committed tail words (boundary
            # errors from rough proportional commits), drop the duplicates:
            # the live tail shows them, so nothing is lost.
            dupe = self._text_overlap_trim(self.committed, new_words)
            if dupe:
                del self.committed[-dupe:]
        if window is not None:
            self.window = window
        self.live = new_words
        self.line = " ".join(self.committed + new_words)
        return self.line

    def _commit_count(self, prev_words, new_words, window) -> int:
        """
        How many head words of the previous Ghost have aged out of the
        Ghost window and should be committed.

        - A solid text alignment between the previous Ghost's tail and the
          new Ghost's head pins the boundary precisely.
        - Otherwise fall back to audio time: the pipeline-reported window
          coverage says how much audio left the window, so head words are
          committed even when the model re-worded them — losing the
          utterance opening is worse than a rough guess.
        - Without window info and without a text alignment, commit nothing
          (the new Ghost replaces the live tail).
        """
        j = _text_overlap_words(prev_words, new_words)
        if j is not None and j > 0:
            return len(prev_words) - j

        if window is not None:
            start, end = self.window
            window_dur = end - start
            new_start = window[0]
            if window_dur > 0 and new_start > start:
                count = round(len(prev_words) * (new_start - start) / window_dur)
                return max(0, min(count, len(prev_words)))
        return 0

    @classmethod
    def _text_overlap_trim(cls, committed: list[str], new_words: list[str]) -> Optional[int]:
        """
        Largest j where the last j committed words equal the first j words
        of the new Ghost (exact, cleaned), or None: the boundary grew over
        into audio the new Ghost still re-covers.
        """
        a = [_norm_word(w) for w in committed]
        b = [_norm_word(w) for w in new_words]
        max_j = min(len(a), len(b))
        for j in range(max_j, 0, -1):
            if a[len(a) - j:] == b[:j]:
                return j
        return None
