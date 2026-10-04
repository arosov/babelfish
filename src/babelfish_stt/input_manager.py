import logging
import threading
import time
import unicodedata
from collections import deque
from typing import Optional

import grapheme
from pynput.keyboard import Controller

from babelfish_stt.ghost_composer import GhostComposer
from babelfish_stt.input_strategies import paste_text, send_backspaces
from babelfish_stt.config import SeparatorPolicy

logger = logging.getLogger(__name__)

# Worker queue item kinds. Ghost frames coalesce (latest wins); a Final
# supersedes any pending ghost frame; CLEAR drops pending typing state
# without backspacing.
_GHOST = "ghost"
_FINAL = "final"
_CLEAR = "clear"


class InputSimulator:
    """
    Types Ghost and Final text into the focused application.

    Ghost composition is span-based and shared with the terminal display
    (ADR 0010): the GhostComposer folds each sliding-window transcription
    into one growing line. Typing is append-diff (the rework of ADR 0010):
    the simulator keeps mirrors of what is actually on screen
    (`typed_committed` / `typed_live`), and each applied frame erases only
    the live tail and pastes only the committed delta + live — the
    keystroke cost per update is bounded by the window, never the line.
    Full erase + repaste happens only when the composer's dedup reached
    into previously typed committed words (rare, bounded by the audio
    bound).

    The ADR 0009 primitives (clipboard paste + pynput backspaces) are
    unchanged — only the erase-all pattern is retired.
    """

    def __init__(self, keyboard_controller=None, throttle_s: float = 0.05):
        # Allow injecting a mock controller for testing
        self.keyboard = keyboard_controller or Controller()
        self.throttle_s = throttle_s
        self.last_ghost_time = 0.0
        self.last_final_char = ""

        # The one ghost-composition state: span-based, shared with the
        # terminal display (ADR 0010). Owned by the calling (audio)
        # thread: enqueue_* composes here; the typing worker never
        # touches the composer.
        self.composer = GhostComposer()

        # Mirrors of what is actually on screen — the single backspace-
        # counting source of truth. Owned by the typing worker.
        self.typed_committed = ""  # committed prefix typed on screen
        self.typed_live = ""  # live tail typed on screen
        self._mirror_trusted = True  # a failed paste/backspace untrusts it

        self._last_applied = None
        self._after_finalize = False
        # Typing worker: the audio thread enqueues frames and returns
        # immediately; this single worker applies them paced by the
        # throttle, so the audio loop never blocks on keystrokes.
        self._queue: deque = deque()
        self._cond = threading.Condition()
        self._busy = False
        self._stop = False
        self._next_apply_time = 0.0
        self._worker = threading.Thread(
            target=self._typing_worker, name="babelfish-typing", daemon=True
        )
        self._worker.start()

    # ------------------------------------------------------------------
    # Mirror accessors

    @property
    def displayed_graphemes(self):
        """The graphemes currently on screen (derived from the mirrors)."""
        text = self._mirror_text()
        return list(grapheme.graphemes(text)) if text else []

    @property
    def last_ghost_length(self) -> int:
        return len(self.displayed_graphemes)

    @property
    def accumulated_text(self) -> str:
        """Returns the text from all ghost updates applied to the screen."""
        return self._mirror_text()

    def _mirror_text(self) -> str:
        parts = [p for p in (self.typed_committed, self.typed_live) if p]
        return " ".join(parts)

    def _set_mirrors(self, committed_words, live_words):
        self.typed_committed = " ".join(committed_words)
        self.typed_live = " ".join(live_words)

    def _clear_mirrors(self):
        self.typed_committed = ""
        self.typed_live = ""

    @staticmethod
    def _grapheme_len(text: str) -> int:
        return len(list(grapheme.graphemes(text))) if text else 0

    # ------------------------------------------------------------------
    # Sync API (composition + immediate typing on the calling thread)

    def type_text(self, text: str):
        """Injects the given text via the clipboard paste (ADR 0009)."""
        if not text:
            return
        try:
            paste_text(text, self.keyboard)
        except Exception as e:
            logger.error(f"Failed to paste text: {e}")
            self._mirror_trusted = False

    def update_ghost(self, ghost_text: Optional[str], window=None):
        """
        Composes the new Ghost through the shared span-based composer and
        applies it to the screen synchronously (append-diff typing).

        `window` is the Ghost's audio coverage as
        (window_start_sample, buffer_end_sample), provided by the pipeline
        through InputDisplay. The async path (enqueue_ghost) composes the
        same way and hands the snapshot to the typing worker.
        """
        # If we're starting fresh after finalize, silently clear any stale state
        # without sending backspaces. The user may have edited/moved the cursor
        # after the last utterance ended.
        if self._after_finalize and self.displayed_graphemes:
            self._clear_mirrors()
            self.composer.reset()
            self._after_finalize = False

        if not ghost_text:
            self._clear_previous()
            self.composer.reset()
            self._last_applied = None
            self.last_ghost_time = 0.0
            return

        # Early exit: redundant frame. The key is (text, window) so an
        # identical re-transcription over a slid window still composes; and
        # the key is recorded only after a frame is actually applied, so a
        # throttle-dropped frame can never poison it (ADR 0010).
        if (ghost_text, window) == self._last_applied:
            return

        # Compose BEFORE the throttle gate: the composer state must
        # advance on every frame (mirroring the terminal display), and any
        # throttle-skipped frame's typing is superseded by the next applied
        # one.
        composed = self.composer.update(ghost_text, window)
        if not composed:
            return

        now = time.time()

        # Throttling: only gate the keystrokes, never the composition.
        if (self.typed_committed or self.typed_live) and (
            now - self.last_ghost_time < self.throttle_s
        ):
            return

        self._apply_ghost_frame(
            ((ghost_text, window), (tuple(self.composer.committed), tuple(self.composer.live)))
        )
        self.last_ghost_time = now

    def finalize(
        self,
        text: str,
        separator: SeparatorPolicy = SeparatorPolicy.TRAILING,
    ):
        """Finalizes the transcription by clearing any ghost text and
        typing the Final (synchronous; the async path is enqueue_finalize).
        """
        # The composer belongs to the composing thread; the worker path
        # resets it at enqueue time instead.
        self.composer.reset()
        self._last_applied = None
        self._type_final(text, separator)
        # Mark that finalize completed - next ghost update should start fresh
        # without backspacing, since user may have edited/moved cursor
        self._after_finalize = True

    def reset(self):
        """Resets the state without backspacing."""
        self.composer.reset()
        self._last_applied = None
        self._clear_mirrors()
        self._mirror_trusted = True
        self.pre_finalize_text = ""
        self._after_finalize = False
        self.last_ghost_time = 0.0
        # Drop a trailing pending ghost frame; a pending Final still
        # belongs on screen, so a CLEAR is queued behind it.
        with self._cond:
            while self._queue and self._queue[-1][0] == _GHOST:
                self._queue.pop()
            self._queue.append((_CLEAR, None))
            self._cond.notify()

    # ------------------------------------------------------------------
    # Async API (compose on the calling thread; the worker types)

    def enqueue_ghost(self, ghost_text: Optional[str], window=None):
        """
        Composes the frame now — the composer must advance on every frame,
        mirroring the terminal display — and hands the composed snapshot
        to the typing worker. Returns immediately.
        """
        if not ghost_text:
            # Defensive: an empty Ghost clears the utterance's typed state.
            self.composer.reset()
            self._last_applied = None
            self.last_ghost_time = 0.0
            self._enqueue(_CLEAR, None)
            return
        self.composer.update(ghost_text, window)
        snapshot = (tuple(self.composer.committed), tuple(self.composer.live))
        self._enqueue(_GHOST, ((ghost_text, window), snapshot))

    def enqueue_finalize(
        self,
        text: str,
        separator: SeparatorPolicy = SeparatorPolicy.TRAILING,
    ):
        """
        Enqueues the Final. Supersedes any pending ghost frame (ordering
        guarantee): the Final erases whatever ghost state is on screen and
        replaces it. Returns immediately.
        """
        # The composer belongs to the calling (audio) thread: reset it
        # here, at the moment the Final supersedes the Ghost pass.
        self.composer.reset()
        self._last_applied = None
        self._enqueue(_FINAL, (text, separator))

    def flush(self, timeout: float = 10.0) -> bool:
        """Blocks until every enqueued frame has been applied (tests)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._cond:
                if not self._queue and not self._busy:
                    return True
            time.sleep(0.002)
        return False

    def stop(self):
        """Stops the typing worker (the process exits anyway; daemon)."""
        with self._cond:
            self._stop = True
            self._cond.notify()

    def _enqueue(self, kind: str, payload):
        with self._cond:
            if kind == _GHOST:
                # Latest-wins coalescing: a pending ghost frame is
                # superseded by the newer one.
                if self._queue and self._queue[-1][0] == _GHOST:
                    self._queue[-1] = (kind, payload)
                else:
                    self._queue.append((kind, payload))
            elif kind == _FINAL:
                # The Final supersedes any pending ghost frame.
                while self._queue and self._queue[-1][0] == _GHOST:
                    self._queue.pop()
                self._queue.append((kind, payload))
            else:  # _CLEAR
                if self._queue and self._queue[-1][0] == _GHOST:
                    self._queue[-1] = (kind, payload)
                else:
                    self._queue.append((kind, payload))
            self._cond.notify()

    def _typing_worker(self):
        """Applies enqueued frames, paced by the throttle. Ghost frames
        wait for their spacing (a newer frame may replace the pending one
        meanwhile); Final/CLEAR apply immediately."""
        while True:
            with self._cond:
                while not self._queue and not self._stop:
                    self._cond.wait(timeout=0.2)
                if self._stop:
                    return
                kind, payload = self._queue.popleft()
                self._busy = True
            try:
                if kind == _FINAL:
                    self._apply_final(payload)
                elif kind == _CLEAR:
                    self._apply_clear()
                else:
                    # Throttle pacing lives here: ghost keystroke bursts
                    # are spaced at least throttle_s apart.
                    delay = self._next_apply_time - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    self._apply_ghost_frame(payload)
                    self._next_apply_time = time.monotonic() + self.throttle_s
            except Exception:
                logger.exception("Typing worker failed to apply a frame")
                self._mirror_trusted = False
            finally:
                with self._cond:
                    self._busy = False

    def _apply_ghost_frame(self, item):
        """Applies one composed snapshot to the screen (worker thread)."""
        key, (committed_words, live_words) = item
        committed_words = list(committed_words)
        live_words = list(live_words)

        # Stale state after a Final the user may have edited/moved the
        # cursor past: start fresh without backspaces.
        if self._after_finalize and (self.typed_committed or self.typed_live):
            self._clear_mirrors()
            self._after_finalize = False
            self._mirror_trusted = True

        # Apply-time dedup: an identical re-transcription over an
        # identical window is skipped; the key records only after a frame
        # is actually applied (ADR 0010).
        if key == self._last_applied:
            return

        typed_c = self.typed_committed.split() if self.typed_committed else []
        typed_l = self.typed_live.split() if self.typed_live else []
        target_words = committed_words + live_words

        if typed_c + typed_l == target_words:
            # The word sequence is already on screen (only the
            # committed/live split moved): refresh the mirrors, no
            # keystrokes.
            self._set_mirrors(committed_words, live_words)
            self._last_applied = key
            return

        if committed_words[: len(typed_c)] == typed_c:
            # Normal case: the committed prefix only grew. Erase the live
            # tail, paste the committed delta + live. The per-update cost
            # is bounded by the window, never the line.
            self._send_backspaces(self._grapheme_len(self.typed_live))
            text = " ".join(committed_words[len(typed_c):] + live_words)
            if text:
                self._paste(text)
        else:
            # Rare case: the composer's dedup trim reached into previously
            # typed committed words — full erase + repaste for this frame
            # only.
            self._send_backspaces(self._grapheme_len(self._mirror_text()))
            self._paste(" ".join(target_words))

        self._set_mirrors(committed_words, live_words)
        self.last_ghost_time = time.time()
        self._last_applied = key

    def _apply_final(self, payload):
        text, separator = payload
        self._type_final(text, separator)
        self._after_finalize = True

    def _apply_clear(self):
        if self.displayed_graphemes:
            self._send_backspaces(self._grapheme_len(self._mirror_text()))
        self._clear_mirrors()
        self._last_applied = None
        self.last_ghost_time = 0.0

    # ------------------------------------------------------------------
    # Typing primitives (mirrors + ADR 0009 mechanics)

    def _paste(self, text: str):
        """Pastes text and advances the mirror trust state."""
        if not text:
            return
        try:
            paste_text(text, self.keyboard)
        except Exception as e:
            logger.error(f"Failed to paste text: {e}")
            self._mirror_trusted = False

    def _type_final(self, text: str, separator: SeparatorPolicy):
        """Erases the ghost mirrors and types the Final (worker-safe:
        touches mirrors and keystrokes only)."""
        # Capture what was on screen before clearing (for verification)
        self.pre_finalize_text = self._mirror_text()

        total = self._grapheme_len(self._mirror_text())
        if total:
            if not self._mirror_trusted:
                # A paste/backspace failed earlier: the mirrors no longer
                # describe the screen. Safer to leave ghost text than to
                # erase the user's content.
                logger.warning(
                    f"Untrusted mirror state in finalize: skipping "
                    f"{total} backspaces to prevent over-erasure. "
                    f"Will type final text without clearing."
                )
            else:
                self._send_backspaces(total)

        self._clear_mirrors()
        self._mirror_trusted = True

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

            self._paste(text)
            self.last_final_char = text[-1]

    def _clear_previous(self):
        """Sends backspaces for the length of the displayed ghost."""
        if self.displayed_graphemes:
            self._send_backspaces(self._grapheme_len(self._mirror_text()))
            self._clear_mirrors()

    def _send_backspaces(self, count: int):
        """Sends N backspaces via the pynput backspace loop."""
        if count <= 0:
            return
        try:
            send_backspaces(count, self.keyboard)
        except Exception as e:
            logger.error(f"Failed to send backspaces: {e}")
            self._mirror_trusted = False
