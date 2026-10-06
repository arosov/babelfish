import logging
import threading
from typing import Optional
from pynput import keyboard
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import BabelfishConfig

logger = logging.getLogger(__name__)


class HotkeyManager(Reconfigurable):
    """
    Global hotkey manager for Babelfish.
    Supports the 'Toggle Listening' shortcut.
    """

    def __init__(self, pipeline, server):
        self.pipeline = pipeline
        self.server = server
        self.listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()

        # Current state
        self.toggle_hotkey: Optional[keyboard.HotKey] = None

    def _parse_hotkey_str(self, shortcut_str: str) -> Optional[str]:
        """Converts UI shortcut (Ctrl+Space) to pynput hotkey string (<ctrl>+<space>)."""
        if not shortcut_str:
            return None

        parts = shortcut_str.split("+")
        transformed = []
        for part in parts:
            p = part.strip().lower()
            if p == "ctrl":
                transformed.append("<ctrl>")
            elif p == "shift":
                transformed.append("<shift>")
            elif p == "alt":
                transformed.append("<alt>")
            elif p == "meta":
                transformed.append("<cmd>")
            elif p == "space":
                transformed.append("<space>")
            elif p == "enter":
                transformed.append("<enter>")
            elif p == "tab":
                transformed.append("<tab>")
            elif p == "escape":
                transformed.append("<esc>")
            elif len(p) == 1:
                transformed.append(p)
            elif p.startswith("f") and len(p) > 1:
                transformed.append(f"<{p}>")
            else:
                transformed.append(f"<{p}>")

        return "+".join(transformed)

    def _on_press(self, key):
        listener = self.listener
        if not listener:
            return

        # Handle Toggle (Pass to HotKey helper)
        if self.toggle_hotkey:
            self.toggle_hotkey.press(listener.canonical(key))

    def _on_release(self, key):
        listener = self.listener
        if not listener:
            return

        # Handle Toggle (Pass to HotKey helper)
        if self.toggle_hotkey:
            self.toggle_hotkey.release(listener.canonical(key))

    def _on_toggle_triggered(self):
        if self.pipeline:
            new_state = not self.pipeline.is_idle
            logger.info(
                f"[Hotkey] Toggle triggered -> {'Idle' if new_state else 'Listening'}"
            )
            self.pipeline.request_mode(is_idle=new_state, force=True)

    def _broadcast_status(self):
        if self.server:
            import asyncio

            if self.server._loop and self.server._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.server.broadcast_status(), self.server._loop
                )

    def start(self, config: BabelfishConfig):
        with self._lock:
            self.stop()

            # Setup Toggle
            toggle_str = config.ui.shortcuts.toggle_listening
            toggle_parsed = self._parse_hotkey_str(toggle_str)
            if toggle_parsed:
                try:
                    self.toggle_hotkey = keyboard.HotKey(
                        keyboard.HotKey.parse(toggle_parsed), self._on_toggle_triggered
                    )
                except Exception as e:
                    logger.error(f"Failed to parse toggle hotkey '{toggle_str}': {e}")

            logger.info(f"Starting HotkeyManager: Toggle={toggle_str}")

            try:
                self.listener = keyboard.Listener(
                    on_press=self._on_press, on_release=self._on_release
                )
                self.listener.start()
            except Exception as e:
                logger.error(f"Failed to start hotkey listener: {e}")

    def stop(self):
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
            self.listener = None
        self.toggle_hotkey = None

    def reconfigure(self, config: BaseModel) -> None:
        if isinstance(config, BabelfishConfig):
            self.start(config)
