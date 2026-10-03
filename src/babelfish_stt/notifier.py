import logging
import platform
import shutil
import subprocess

from notifypy import Notify
from pydantic import BaseModel

from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.config import UIConfig

logger = logging.getLogger(__name__)

# Event names that produce a desktop toast, mapped to their message text.
EVENT_MESSAGES = {
    "wakeword_detected": "Wake word detected, listening",
    "stop_word_detected": "Stop word detected, idle",
}


class DesktopNotifier(Reconfigurable):
    """
    Sends cross-platform desktop notifications for pipeline events.

    Owned by the pipeline so both standalone and service (`--server`) modes
    get wake/stop-word toasts. Gated by `ui.notifications` (hot-reloadable).
    """

    config_key = "ui"

    def __init__(self):
        self.enabled = True

    def reconfigure(self, config: BaseModel) -> None:
        if isinstance(config, UIConfig):
            self.enabled = config.notifications

    def notify_event(self, event_name: str) -> None:
        """Send a toast for a pipeline event, if one maps to it and toasts are enabled."""
        if not self.enabled:
            return

        message = EVENT_MESSAGES.get(event_name)
        if message is None:
            return

        self.send("Babelfish", message)

    def send(self, title: str, message: str, timeout_sec: int = 4):
        """Sends a cross-platform desktop notification with best-effort timeout support."""
        if platform.system().lower() == "linux":
            # On Linux, notify-send is the most reliable way to respect the timeout
            notify_send = shutil.which("notify-send")
            if notify_send:
                try:
                    subprocess.Popen(
                        [
                            notify_send,
                            "-t",
                            str(timeout_sec * 1000),
                            "-a",
                            "Babelfish",
                            title,
                            message,
                        ]
                    )
                    return
                except Exception as e:
                    logger.error(f"notify-send failed: {e}")

        # Fallback for Windows/macOS or if notify-send is missing
        try:
            self._send_notifypy(title, message)
        except Exception as e:
            logger.error(f"notifypy failed: {e}")

    def _send_notifypy(self, title: str, message: str):
        notification = Notify()
        notification.application_name = "Babelfish"
        notification.title = title
        notification.message = message
        # notifypy doesn't support timeout directly, but we keep the parameter
        # so the notify-send path and this one share the same signature.
        notification.send(block=False)
