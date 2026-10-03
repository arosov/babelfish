import sys
import asyncio
import json
import logging
import time
from typing import Optional
from babelfish_stt.input_manager import InputSimulator

logger = logging.getLogger(__name__)


class TerminalDisplay:
    """
    Handles real-time terminal-based streaming updates for transcription.

    Ghost text is composed incrementally. Each Ghost update re-transcribes a
    sliding window of the utterance audio, so consecutive updates overlap
    heavily and may revise words inside that window. The displayed Ghost line
    therefore accumulates: words whose audio has slid out of the Ghost window
    are committed (never rewritten), while the live window tail is replaced by
    each new Ghost, keeping the matched overlap aligned so text appends
    instead of overwriting.

    When the Final arrives, the accumulated Ghost line stays visible and the
    Final transcript is written on the next line (bold).
    """

    # ~100ms minimum between console redraws. Protects the audio-loop thread
    # from slow Windows console I/O when low Ghost spacing values flood
    # updates; suppressed text is kept so the next redraw shows the latest.
    REDRAW_MIN_INTERVAL_S = 0.1

    # Characters stripped when comparing words across Ghost updates
    _WORD_STRIP = ".,!?;:\"'`—–-…()[]"

    def __init__(self):
        self.last_text = ""
        self.max_line_length = 0
        self._last_write_time = 0.0
        self._pending_update = None  # (text, refined, ghost) held while rate-limited
        # Ghost composition state (reset per utterance)
        self._ghost_committed = []  # words whose audio has left the Ghost window
        self._ghost_live = []  # words of the latest Ghost (current window)
        self._ghost_line = ""  # composed Ghost line currently displayed
        self._ghost_window = (0, 0)  # (start, end) samples of the latest Ghost's window
        self._line_len = 0  # visible chars on the current terminal line
        self._line_open = False  # current line has content

    def update(self, text: str = "", refined: str = "", ghost: str = "", window=None):
        """
        Updates the current line with streaming text.
        Supports ANSI styles: Refined is Bold, Ghost is Dimmed.

        `window` is the Ghost's audio coverage as
        (window_start_sample, buffer_end_sample), provided by the pipeline.
        """
        # Compose BEFORE the rate-limit check: the accumulation state must
        # advance even when the redraw itself is deferred.
        if ghost:
            ghost = self._compose_ghost(ghost, window)

        now = time.monotonic()
        if now - self._last_write_time < self.REDRAW_MIN_INTERVAL_S:
            # Rate-limited: keep the latest (already composed) text for the
            # next redraw; the Final lands on its own line regardless.
            self._pending_update = (text, refined, ghost)
            return
        self._last_write_time = now
        self._write(text, refined, ghost)

    def _compose_ghost(self, ghost: str, window=None) -> str:
        """
        Fold a new Ghost (one window transcription) into the accumulated
        Ghost line: commit words whose audio left the window, keep the rest
        revisable by later updates.
        """
        ghost = ghost.strip()
        if not ghost:
            return self._ghost_line

        new_words = ghost.split()
        if self._ghost_live:
            commit = self._commit_count(self._ghost_live, new_words, window)
            self._ghost_committed.extend(self._ghost_live[:commit])
            # If the new Ghost re-covers committed tail words (boundary
            # errors from rough proportional commits), drop the duplicates:
            # the live tail shows them, so nothing is lost.
            dupe = self._text_overlap_words(self._ghost_committed, new_words)
            if dupe:
                del self._ghost_committed[-dupe:]
        if window is not None:
            self._ghost_window = window
        self._ghost_live = new_words
        self._ghost_line = " ".join(self._ghost_committed + new_words)
        return self._ghost_line

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
        j = self._text_overlap_words(prev_words, new_words)
        if j is not None and j > 0:
            return len(prev_words) - j

        if window is not None:
            start, end = self._ghost_window
            window_dur = end - start
            new_start = window[0]
            if window_dur > 0 and new_start > start:
                count = round(len(prev_words) * (new_start - start) / window_dur)
                return max(0, min(count, len(prev_words)))
        return 0

    @classmethod
    def _text_overlap_words(cls, prev_words, new_words) -> Optional[int]:
        """
        Largest j where the last j words of the previous Ghost match the
        first j words of the new Ghost (case/punctuation-insensitive), or
        None when no solid alignment exists (the model re-worded the shared
        region). Solid means at least half the aligned words match.
        """
        a = [cls._norm_word(w) for w in prev_words]
        b = [cls._norm_word(w) for w in new_words]
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

    @classmethod
    def _norm_word(cls, word: str) -> str:
        return word.lower().strip(cls._WORD_STRIP)

    def _write(self, text: str = "", refined: str = "", ghost: str = ""):
        if refined or ghost:
            # ANSI escape codes: 1=Bold, 2=Dim, 0=Reset
            display_text = ""
            if refined:
                display_text += f"\033[1m{refined}\033[0m"
            if ghost:
                separator = " " if refined else ""
                display_text += f"{separator}\033[2m{ghost}\033[0m"

            # For length tracking, we need to ignore ANSI codes
            plain_text = (refined + (" " if refined and ghost else "") + ghost).strip()
        else:
            display_text = text
            plain_text = text

        if not plain_text:
            return

        # Identical content on an open line: nothing to draw
        if self._line_open and plain_text == self.last_text:
            return

        # Clear previous line if new text is shorter
        padding = " " * max(0, self._line_len - len(plain_text))
        sys.stdout.write(f"\r{display_text}{padding}")
        sys.stdout.flush()

        self._line_len = len(plain_text)
        self._line_open = True
        self.last_text = plain_text
        self.max_line_length = max(self.max_line_length, len(plain_text))

    def finalize(self, text: str = ""):
        """
        Keeps the accumulated Ghost line visible and writes the Final on the
        next line (bold).
        """
        # Flush any rate-limited Ghost update so the line shows the latest
        # composition before the Final lands.
        if self._pending_update is not None:
            pending = self._pending_update
            self._pending_update = None
            self._write(*pending)

        # Terminate the Ghost accumulation line so it stays visible
        if self._line_open:
            sys.stdout.write("\n")

        # ANSI escape codes: 1=Bold, 0=Reset
        if text:
            sys.stdout.write(f"\033[1m{text}\033[0m\n")
        sys.stdout.flush()

        self.reset()

    def reset(self):
        """Resets the line state."""
        self.last_text = ""
        self.max_line_length = 0
        self._pending_update = None
        self._ghost_committed = []
        self._ghost_live = []
        self._ghost_line = ""
        self._ghost_window = (0, 0)
        self._line_len = 0
        self._line_open = False


class ServerDisplay:
    """
    Sends transcription updates to all connected WebSocket clients.
    """

    def __init__(self, server):
        self.server = server
        self._last_ghost = ""
        self._last_final = ""

    def update(self, text: str = "", refined: str = "", ghost: str = "", **kwargs):
        # Extra pipeline metadata (e.g. the Ghost window span) is intentionally
        # not forwarded: the WebSocket payload shape stays stable.
        if not text and not refined and not ghost:
            return

        # Deduplication: skip if ghost text is identical to last sent
        if ghost == self._last_ghost and not refined:
            return
        self._last_ghost = ghost

        msg = {
            "type": "transcription",
            "text": text,
            "refined": refined,
            "ghost": ghost,
            "final": False,
        }
        asyncio.run_coroutine_threadsafe(
            self.server.broadcast_message(msg), self.server._loop
        )

    def finalize(self, text: str = ""):
        if not text:
            return

        # Deduplication: skip if final text is identical to last sent
        if text == self._last_final:
            return
        self._last_final = text

        msg = {"type": "transcription", "text": text, "final": True}
        asyncio.run_coroutine_threadsafe(
            self.server.broadcast_message(msg), self.server._loop
        )

    def reset(self):
        msg = {"type": "transcription_reset"}
        asyncio.run_coroutine_threadsafe(
            self.server.broadcast_message(msg), self.server._loop
        )
        self._last_ghost = ""
        self._last_final = ""


class MultiDisplay:
    """
    Multiplexes transcription updates to multiple display backends.
    """

    def __init__(self, *displays):
        self.displays = displays

    def update(self, text: str = "", refined: str = "", ghost: str = "", **kwargs):
        for d in self.displays:
            d.update(text, refined, ghost, **kwargs)

    def finalize(self, text: str = ""):
        for d in self.displays:
            d.finalize(text)

    def reset(self):
        for d in self.displays:
            d.reset()


class InputDisplay:
    """
    Handles transcription updates by simulating keyboard input.
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.simulator = InputSimulator()

    def update(self, text: str = "", refined: str = "", ghost: str = "", **kwargs):
        # Extra pipeline metadata (e.g. the Ghost window span) is ignored:
        # typed ghosts keep replacing the last typed window text.
        config = self.config_manager.config.system_input
        if not config.enabled or not config.type_ghost:
            # If ghost typing is disabled, we still need to make sure we don't
            # leave any stale ghost length in the simulator if it was previously enabled.
            # But the simulator resets on finalize.
            return

        # We only type ghost text if explicitly enabled
        if ghost:
            self.simulator.update_ghost(ghost)

    def finalize(self, text: str = ""):
        config = self.config_manager.config.system_input
        if not config.enabled:
            # Even if disabled now, if it was enabled during ghost pass,
            # we MUST clear the ghost text from the screen.
            if self.simulator.graphemes:
                self.simulator.finalize("")
            return

        self.simulator.finalize(
            text, strategy=config.strategy, separator=config.separator
        )

    def reset(self):
        self.simulator.reset()
