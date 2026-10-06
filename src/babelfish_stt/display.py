import sys
import asyncio
import json
import logging
import time
from babelfish_stt.input_manager import InputSimulator
from babelfish_stt.ghost_composer import GhostComposer

logger = logging.getLogger(__name__)


class TerminalDisplay:
    """
    Handles real-time terminal-based streaming updates for transcription.

    Ghost text is composed incrementally by the shared span-based
    GhostComposer (ADR 0010): each Ghost update folds into the accumulated
    line — words whose audio has left the window are committed (never
    rewritten), the live window tail is replaced by each new Ghost — so
    text appends instead of overwriting.

    When the Final arrives, the accumulated Ghost line stays visible and the
    Final transcript is written on the next line (bold).
    """

    # ~100ms minimum between console redraws. Protects the audio-loop thread
    # from slow Windows console I/O when low Ghost spacing values flood
    # updates; suppressed text is kept so the next redraw shows the latest.
    REDRAW_MIN_INTERVAL_S = 0.1

    def __init__(self):
        self.last_text = ""
        self.max_line_length = 0
        self._last_write_time = 0.0
        self._pending_update = None  # (text, refined, ghost) held while rate-limited
        self._composer = GhostComposer()
        self._line_len = 0  # visible chars on the current terminal line
        self._line_open = False  # current line has content
        self._degrade_warned = False  # first degraded draw already reported?

    def _safe_write(self, text: str) -> None:
        """Unicode-safe console write that can never raise.

        The stream encoding is forced to UTF-8 at startup (main.py) and
        PYTHONUTF8=1 is pinned by the bootstrap, so this normally just
        delegates. Last-resort net: if the stream still rejects a character
        (legacy console before reconfigure, exotic redirect), the draw is
        degraded with replacement characters for the offending span instead
        of raising UnicodeEncodeError into the STT loop and killing it.
        The underlying transcript text is never mutated — only this draw.
        """
        try:
            sys.stdout.write(text)
        except UnicodeEncodeError:
            if not self._degrade_warned:
                self._degrade_warned = True
                logger.warning(
                    f"Terminal stream rejected non-representable characters "
                    f"({text[:40]!r} ...); degrading console-only draws with "
                    f"replacement characters"
                )
            enc = getattr(sys.stdout, "encoding", None) or "ascii"
            sys.stdout.write(text.encode(enc, "replace").decode(enc))

    def update(
        self,
        text: str = "",
        refined: str = "",
        ghost: str = "",
        window=None,
        **kwargs,
    ):
        """
        Updates the current line with streaming text.
        Supports ANSI styles: Refined is Bold, Ghost is Dimmed.

        `window` is the Ghost's audio coverage as
        (window_start_sample, buffer_end_sample), provided by the pipeline.
        Extra pipeline telemetry kwargs (e.g. duration_ms) are intentionally
        not consumed here.
        """
        # Compose BEFORE the rate-limit check: the accumulation state must
        # advance even when the redraw itself is deferred.
        if ghost:
            ghost = self._composer.update(ghost, window)

        now = time.monotonic()
        if now - self._last_write_time < self.REDRAW_MIN_INTERVAL_S:
            # Rate-limited: keep the latest (already composed) text for the
            # next redraw; the Final lands on its own line regardless.
            self._pending_update = (text, refined, ghost)
            return
        self._last_write_time = now
        self._write(text, refined, ghost)

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
        self._safe_write(f"\r{display_text}{padding}")
        sys.stdout.flush()

        self._line_len = len(plain_text)
        self._line_open = True
        self.last_text = plain_text
        self.max_line_length = max(self.max_line_length, len(plain_text))

    def finalize(self, text: str = "", **kwargs):
        """
        Keeps the accumulated Ghost line visible and writes the Final on the
        next line (bold).

        Extra telemetry kwargs (e.g. final_pass_ms) are intentionally not
        consumed here — MultiDisplay forwards them to every display, so
        each finalize must accept and ignore what it does not use.
        """
        # Flush any rate-limited Ghost update so the line shows the latest
        # composition before the Final lands.
        if self._pending_update is not None:
            pending = self._pending_update
            self._pending_update = None
            self._write(*pending)

        # Terminate the Ghost accumulation line so it stays visible
        if self._line_open:
            self._safe_write("\n")
            sys.stdout.flush()

        # ANSI escape codes: 1=Bold, 0=Reset
        if text:
            self._safe_write(f"\033[1m{text}\033[0m\n")
        sys.stdout.flush()

        self.reset()

    def reset(self):
        """Resets the line state."""
        self.last_text = ""
        self.max_line_length = 0
        self._pending_update = None
        self._composer.reset()
        self._line_len = 0
        self._line_open = False


class ServerDisplay:
    """
    Sends transcription updates to all connected WebSocket clients.

    Ghost text is composed by the shared span-based GhostComposer
    (ADR 0010) — the third consumer of the algorithm, alongside
    TerminalDisplay and InputSimulator. The broadcast carries both the
    raw Ghost and the composed split (committed / live words) so
    WebSocket clients can render the revisable frontier, plus the
    pipeline telemetry a transcript panel needs: the Ghost's audio
    window span, the ghost-pass inference time, the speech-onset →
    first-Ghost delay (first Ghost only) and the final-pass duration.
    """

    def __init__(self, server):
        self.server = server
        self._last_ghost = ""
        self._last_final = ""
        self._composer = GhostComposer()

    def update(
        self,
        text: str = "",
        refined: str = "",
        ghost: str = "",
        window=None,
        **kwargs,
    ):
        # Compose BEFORE the dedup check: the composer state must advance
        # exactly like TerminalDisplay's, even when the redraw itself is
        # skipped below.
        composed = self._composer.update(ghost, window) if ghost else self._composer.line

        # The payload keeps every field the client may consume; displays
        # that read `duration_ms` see it re-exported as `inference_ms`.
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
            "composed": composed,
            "committed": " ".join(self._composer.committed),
            "live": " ".join(self._composer.live),
            "window": list(window) if window is not None else None,
            "inference_ms": kwargs.get("duration_ms"),
            "onset_ms": kwargs.get("onset_ms"),
            "final": False,
        }
        asyncio.run_coroutine_threadsafe(
            self.server.broadcast_message(msg), self.server._loop
        )

    def finalize(self, text: str = "", **kwargs):
        if not text:
            return

        # Deduplication: skip if final text is identical to last sent
        if text == self._last_final:
            return
        self._last_final = text

        msg = {
            "type": "transcription",
            "text": text,
            "final": True,
            "final_pass_ms": kwargs.get("final_pass_ms"),
        }
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
        self._composer.reset()


class MultiDisplay:
    """
    Multiplexes transcription updates to multiple display backends.

    Containment contract: one backend failing must never take down the STT
    loop. Every call is wrapped — a backend that raises is logged (first
    occurrence in full, then summarized so a flood of Ghost redraws can't
    spam the log) and the remaining backends still receive the frame.
    """

    LOG_EVERY_N = 50

    def __init__(self, *displays):
        self.displays = displays
        self._error_counts = {}  # (backend class, method) -> failure count

    def _call(self, method: str, *args, **kwargs):
        for d in self.displays:
            try:
                getattr(d, method)(*args, **kwargs)
            except Exception as e:
                key = (type(d).__name__, method)
                count = self._error_counts.get(key, 0) + 1
                self._error_counts[key] = count
                if count == 1:
                    logger.error(
                        f"Display {type(d).__name__}.{method} failed "
                        f"(its backend is now bypassed, others kept): {e}"
                    )
                elif count % self.LOG_EVERY_N == 0:
                    logger.debug(
                        f"Display {type(d).__name__}.{method}: "
                        f"{count} failures so far"
                    )

    def update(self, text: str = "", refined: str = "", ghost: str = "", **kwargs):
        self._call("update", text, refined, ghost, **kwargs)

    def finalize(self, text: str = "", **kwargs):
        self._call("finalize", text, **kwargs)

    def reset(self):
        self._call("reset")


class InputDisplay:
    """
    Handles transcription updates by simulating keyboard input.

    Frames are enqueued to the simulator's typing worker and this call
    returns immediately — the audio thread never blocks on keystrokes
    (the typing worker applies them paced by the throttle, ghost frames
    coalescing latest-wins, a Final superseding any pending ghost frame).
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.simulator = InputSimulator()

    def update(self, text: str = "", refined: str = "", ghost: str = "", window=None, **kwargs):
        # The Ghost window span rides along (ADR 0010): the typed Ghost is
        # composed by the same span-based composer the terminal display
        # uses, and its audio-time commits need the pipeline's window.
        config = self.config_manager.config.system_input
        if not config.enabled or not config.type_ghost:
            # If ghost typing is disabled, we still need to make sure we don't
            # leave any stale ghost length in the simulator if it was previously enabled.
            # But the simulator resets on finalize.
            return

        # The typing throttle is hot-reloadable: it is re-read from the
        # config on every frame, so a changed `typing_throttle_ms` takes
        # effect on the next keystroke without a restart.
        self.simulator.throttle_s = config.typing_throttle_ms / 1000.0

        # We only type ghost text if explicitly enabled
        if ghost:
            self.simulator.enqueue_ghost(ghost, window=window)

    def finalize(self, text: str = "", **kwargs):
        config = self.config_manager.config.system_input
        if not config.enabled:
            # Even if disabled now, if it was enabled during ghost pass,
            # we MUST clear the ghost text from the screen.
            # Read the list we erase (ADR 0010): displayed_graphemes is the
            # single source of truth for what is on screen.
            if self.simulator.displayed_graphemes:
                self.simulator.enqueue_finalize("")
            return

        self.simulator.enqueue_finalize(text, separator=config.separator)

    def reset(self):
        self.simulator.reset()
