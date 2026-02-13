import sys
import asyncio
import json
import logging
from babelfish_stt.input_manager import InputSimulator

logger = logging.getLogger(__name__)


class TerminalDisplay:
    """
    Handles real-time terminal-based streaming updates for transcription.
    """

    def __init__(self):
        self.last_text = ""
        self.max_line_length = 0

    def update(self, text: str = "", refined: str = "", ghost: str = ""):
        """
        Updates the current line with streaming text.
        Supports ANSI styles: Refined is Bold, Ghost is Dimmed.
        """
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

        # Clear previous line if new text is shorter
        padding = " " * max(0, self.max_line_length - len(plain_text))
        sys.stdout.write(f"\r{display_text}{padding}")
        sys.stdout.flush()

        self.last_text = plain_text
        self.max_line_length = max(self.max_line_length, len(plain_text))

    def finalize(self, text: str = ""):
        """
        Finalizes the current line and moves to the next one (bold).
        """
        # ANSI escape codes: 1=Bold, 0=Reset
        display_text = f"\033[1m{text}\033[0m"

        padding = " " * max(0, self.max_line_length - len(text))
        sys.stdout.write(f"\r{display_text}{padding}\n")
        sys.stdout.flush()

        self.last_text = ""
        self.max_line_length = 0


class ServerDisplay:
    """
    Sends transcription updates to all connected WebSocket clients.
    """

    def __init__(self, server):
        self.server = server

    def update(self, text: str = "", refined: str = "", ghost: str = ""):
        if not text and not refined and not ghost:
            return

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

        msg = {"type": "transcription", "text": text, "final": True}
        asyncio.run_coroutine_threadsafe(
            self.server.broadcast_message(msg), self.server._loop
        )


class MultiDisplay:
    """
    Multiplexes transcription updates to multiple display backends.
    """

    def __init__(self, *displays):
        self.displays = displays

    def update(self, text: str = "", refined: str = "", ghost: str = ""):
        for d in self.displays:
            d.update(text, refined, ghost)

    def finalize(self, text: str = ""):
        for d in self.displays:
            d.finalize(text)


class InputDisplay:
    """
    Handles transcription updates by simulating keyboard input.
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.simulator = InputSimulator()

    def update(self, text: str = "", refined: str = "", ghost: str = ""):
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
            if self.simulator.last_ghost_length > 0:
                self.simulator.finalize("")
            return

        self.simulator.finalize(text, strategy=config.strategy)
