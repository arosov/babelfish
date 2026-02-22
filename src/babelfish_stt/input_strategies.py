import abc
import logging
import subprocess
import sys
import time
import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)


class InputStrategy(abc.ABC):
    @abc.abstractmethod
    def type(self, text: str, keyboard: Controller):
        pass

    @abc.abstractmethod
    def backspace(self, count: int, keyboard: Controller):
        pass


class DirectStrategy(InputStrategy):
    """Simulates individual keystrokes using pynput."""

    def type(self, text: str, keyboard: Controller):
        if not text:
            return
        try:
            keyboard.type(text)
        except Exception as e:
            logger.warning(
                f"DirectStrategy failed to type '{text}' ({e}). Fallback to Clipboard."
            )
            # Fallback to ClipboardStrategy
            ClipboardStrategy().type(text, keyboard)

    def backspace(self, count: int, keyboard: Controller):
        if count <= 0:
            return
        try:
            for _ in range(count):
                keyboard.press(Key.backspace)
                keyboard.release(Key.backspace)
        except Exception as e:
            logger.error(f"DirectStrategy backspace failed: {e}")


class ClipboardStrategy(InputStrategy):
    """Copies text to clipboard and simulates Paste command."""

    def type(self, text: str, keyboard: Controller):
        if not text:
            return

        # Save current clipboard? (Restoration is tricky and racy, skipping for now)
        pyperclip.copy(text)

        # Simulate Paste
        if sys.platform == "darwin":
            with keyboard.pressed(Key.cmd):
                keyboard.press("v")
                keyboard.release("v")
        else:
            with keyboard.pressed(Key.ctrl):
                keyboard.press("v")
                keyboard.release("v")

    def backspace(self, count: int, keyboard: Controller):
        # Clipboard cannot backspace, fallback to Direct
        DirectStrategy().backspace(count, keyboard)


class NativeStrategy(InputStrategy):
    """Uses platform-specific CLI tools to inject text."""

    def type(self, text: str, keyboard: Controller):
        if not text:
            return

        if sys.platform == "linux":
            try:
                # Try xdotool if available
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--", text],
                    check=True,
                    capture_output=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning(
                    "xdotool not found or failed, falling back to DirectStrategy"
                )
                DirectStrategy().type(text, keyboard)

        elif sys.platform == "win32":
            # PowerShell SendKeys
            # Escape special characters for SendKeys: { } [ ] ( ) + ^ % ~
            escaped = (
                text.replace("{", "{{")
                .replace("}", "}}")
                .replace("[", "[[")
                .replace("]", "]]")
                .replace("(", "((")
                .replace(")", "))")
                .replace("+", "{+}")
                .replace("^", "{^}")
                .replace("%", "{%}")
                .replace("~", "{~}")
            )
            cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{escaped}')"
            try:
                subprocess.run(["powershell", "-Command", cmd], check=True)
            except subprocess.CalledProcessError:
                logger.warning(
                    "PowerShell SendKeys failed, falling back to DirectStrategy"
                )
                DirectStrategy().type(text, keyboard)

        elif sys.platform == "darwin":
            # AppleScript
            escaped = text.replace('"', '\\"')
            cmd = f'tell application "System Events" to keystroke "{escaped}"'
            try:
                subprocess.run(["osascript", "-e", cmd], check=True)
            except subprocess.CalledProcessError:
                logger.warning("AppleScript failed, falling back to DirectStrategy")
                DirectStrategy().type(text, keyboard)
        else:
            DirectStrategy().type(text, keyboard)

    def backspace(self, count: int, keyboard: Controller):
        # Fallback to DirectStrategy for robust backspacing
        DirectStrategy().backspace(count, keyboard)


class HybridStrategy(InputStrategy):
    """Uses Direct Input for ASCII, Clipboard for others."""

    def __init__(self):
        self.direct = DirectStrategy()
        self.clipboard = ClipboardStrategy()

    def is_safe(self, text: str) -> bool:
        # Check if all characters are standard ASCII printable
        return all(32 <= ord(c) <= 126 or c in "\n\r\t" for c in text)

    def type(self, text: str, keyboard: Controller):
        if not text:
            return

        if self.is_safe(text):
            self.direct.type(text, keyboard)
        else:
            self.clipboard.type(text, keyboard)

    def backspace(self, count: int, keyboard: Controller):
        self.direct.backspace(count, keyboard)
