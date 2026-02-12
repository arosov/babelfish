import logging
import threading
from typing import Optional, Dict, Union
from pynput import keyboard
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import BabelfishConfig

logger = logging.getLogger(__name__)


class HotkeyManager(Reconfigurable):
    """
    Global hotkey manager for Babelfish.
    Supports both 'Hold to Talk' (PTT) and 'Toggle Listening' shortcuts.
    """

    def __init__(self, pipeline, server):
        self.pipeline = pipeline
        self.server = server
        self.listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()

        # Current state
        self.ptt_key: Optional[Union[keyboard.Key, keyboard.KeyCode]] = None
        self.toggle_hotkey: Optional[keyboard.HotKey] = None

        # Mapping from UI strings to pynput Key constants
        self._key_map = {
            "left ctrl": keyboard.Key.ctrl_l,
            "right ctrl": keyboard.Key.ctrl_r,
            "left shift": keyboard.Key.shift,
            "right shift": keyboard.Key.shift_r,
            "left alt": keyboard.Key.alt,
            "right alt": keyboard.Key.alt_r,
            "left meta": keyboard.Key.cmd,
            "right meta": keyboard.Key.cmd_r,
            "space": keyboard.Key.space,
            "enter": keyboard.Key.enter,
            "tab": keyboard.Key.tab,
            "escape": keyboard.Key.esc,
        }

    def _parse_key(
        self, key_str: str
    ) -> Optional[Union[keyboard.Key, keyboard.KeyCode]]:
        """Parses a single key string into a pynput key or char."""
        if not key_str:
            return None

        k = key_str.lower().strip()
        if k in self._key_map:
            return self._key_map[k]

        if len(k) == 1:
            return keyboard.KeyCode.from_char(k)

        if k.startswith("f") and len(k) > 1:
            try:
                f_num = int(k[1:])
                return getattr(keyboard.Key, f"f{f_num}")
            except (ValueError, AttributeError):
                pass

        return None

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

        # 1. Handle PTT (Hold to Talk)
        canonical_key = listener.canonical(key)
        if self.ptt_key and (key == self.ptt_key or canonical_key == self.ptt_key):
            if self.pipeline and self.pipeline.is_idle:
                self.pipeline.request_mode(is_idle=False, force=False)

        # 2. Handle Toggle (Pass to HotKey helper)
        if self.toggle_hotkey:
            self.toggle_hotkey.press(canonical_key)

    def _on_release(self, key):
        listener = self.listener
        if not listener:
            return

        # 1. Handle PTT (Hold to Talk)
        canonical_key = listener.canonical(key)
        if self.ptt_key and (key == self.ptt_key or canonical_key == self.ptt_key):
            if self.pipeline and not self.pipeline.is_idle:
                self.pipeline.request_mode(is_idle=True, force=False)

        # 2. Handle Toggle (Pass to HotKey helper)
        if self.toggle_hotkey:
            self.toggle_hotkey.release(canonical_key)

    def _on_toggle_triggered(self):
        if self.pipeline:
            new_state = not self.pipeline.is_idle
            self.pipeline.request_mode(is_idle=new_state, force=True)

        # 2. Handle Toggle (Pass to HotKey helper)
        if self.toggle_hotkey:
            self.toggle_hotkey.press(canonical_key)

    def _on_release(self, key):
        listener = self.listener
        if not listener:
            return

        # 1. Handle PTT (Hold to Talk)
        canonical_key = listener.canonical(key)
        if self.ptt_key and (key == self.ptt_key or canonical_key == self.ptt_key):
            if self.pipeline and not self.pipeline.is_idle:
                logger.info("[Hotkey] PTT Released -> Idle")
                self.pipeline.set_idle(True)
                self._broadcast_status()

        # 2. Handle Toggle (Pass to HotKey helper)
        if self.toggle_hotkey:
            self.toggle_hotkey.release(canonical_key)

    def _on_toggle_triggered(self):
        if self.pipeline:
            new_state = not self.pipeline.is_idle
            logger.info(
                f"[Hotkey] Toggle triggered -> {'Idle' if new_state else 'Listening'}"
            )
            self.pipeline.set_idle(new_state, force=True)
            self._broadcast_status()

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

            # Setup PTT
            ptt_str = config.ui.shortcuts.force_listen
            self.ptt_key = self._parse_key(ptt_str)

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

            logger.info(f"Starting HotkeyManager: PTT={ptt_str}, Toggle={toggle_str}")

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
        self.ptt_key = None
        self.toggle_hotkey = None

    def reconfigure(self, config: BaseModel) -> None:
        if isinstance(config, BabelfishConfig):
            self.start(config)
