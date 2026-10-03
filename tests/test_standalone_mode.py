import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import numpy as np

from babelfish_stt.config import BabelfishConfig, UIConfig
from babelfish_stt.notifier import DesktopNotifier, EVENT_MESSAGES
from babelfish_stt.pipeline import StandardPipeline


class TestArgParsing(unittest.TestCase):
    def test_defaults_are_standalone(self):
        from babelfish_stt.main import parse_args

        args = parse_args([])

        self.assertFalse(args.server)
        self.assertFalse(args.type_into_apps)
        self.assertIsNone(args.port)

    def test_server_flag(self):
        from babelfish_stt.main import parse_args

        args = parse_args(["--server"])

        self.assertTrue(args.server)

    def test_type_flag(self):
        from babelfish_stt.main import parse_args

        args = parse_args(["--type"])

        self.assertTrue(args.type_into_apps)

    def test_flags_compose(self):
        from babelfish_stt.main import parse_args

        args = parse_args(["--server", "--type", "--port", "9999"])

        self.assertTrue(args.server)
        self.assertTrue(args.type_into_apps)
        self.assertEqual(args.port, 9999)

    def test_port_without_server_fails(self):
        from babelfish_stt.main import parse_args

        with self.assertRaises(SystemExit) as ctx, \
               patch("sys.stderr", new=MagicMock()):
            parse_args(["--port", "8124"])

        self.assertEqual(ctx.exception.code, 2)

    def test_port_with_server_ok(self):
        from babelfish_stt.main import parse_args

        args = parse_args(["--server", "--port", "8124"])

        self.assertEqual(args.port, 8124)

    def test_main_passes_serve_and_type_to_run_babelfish(self):
        from babelfish_stt.main import main

        argv = ["babelfish", "--server", "--type"]
        with patch("sys.argv", argv), \
               patch("babelfish_stt.main.HardwareManager") as mock_hw, \
               patch("babelfish_stt.main.asyncio.run") as mock_run:
            main()

        coro = mock_run.call_args[0][0]
        self.assertEqual(
            coro.cr_frame.f_locals["serve"], True
        )
        self.assertEqual(
            coro.cr_frame.f_locals["type_into_apps"], True
        )
        mock_hw.assert_called_once()


class TestStandalonePipelineNoServer(unittest.TestCase):
    """The key regression guard: the pipeline must not touch a server in standalone mode."""

    def _make_pipeline(self):
        vad = MagicMock()
        vad.is_speech.return_value = False
        engine = MagicMock()
        engine.device_type = "cpu"
        display = MagicMock()
        pipeline = StandardPipeline(vad, engine, display)
        pipeline.server = None  # standalone: no server
        pipeline.stop_detector = None
        return pipeline, display

    def test_stt_loop_style_usage_with_server_none(self):
        """Simulates the standalone orchestration: request_mode/process_chunk with
        pipeline.server=None and no notifier must not raise."""
        pipeline, display = self._make_pipeline()

        pipeline.request_mode(is_idle=False, source_event=None)
        self.assertFalse(pipeline.is_idle)

        chunk = np.zeros(512, dtype=np.float32)
        now_ms = 0.0
        pipeline.process_chunk(chunk, now_ms, is_speech=False)
        pipeline.request_mode(is_idle=True, force=True)

        self.assertTrue(pipeline.is_idle)
        display.reset.assert_called()

    def test_request_mode_with_source_event_and_no_server(self):
        """Wake/stop-word triggered transitions used to call
        server.trigger_event; they must degrade gracefully when server=None."""
        pipeline, _ = self._make_pipeline()

        pipeline.request_mode(is_idle=False, source_event="wakeword_detected")
        pipeline.request_mode(is_idle=True, force=True, source_event="stop_word_detected")

        self.assertTrue(pipeline.is_idle)

    def test_source_event_notifies_without_server(self):
        pipeline, _ = self._make_pipeline()
        notifier = MagicMock()
        pipeline.notifier = notifier

        pipeline.request_mode(is_idle=False, source_event="wakeword_detected")

        notifier.notify_event.assert_called_once_with("wakeword_detected")

    def test_manual_mode_change_skips_notifier(self):
        pipeline, _ = self._make_pipeline()
        notifier = MagicMock()
        pipeline.notifier = notifier

        pipeline.request_mode(is_idle=True, force=True)

        notifier.notify_event.assert_not_called()


class TestDesktopNotifier(unittest.TestCase):
    def _notifier(self, enabled=True):
        notifier = DesktopNotifier()
        notifier.reconfigure(UIConfig(notifications=enabled))
        return notifier

    @patch("babelfish_stt.notifier.subprocess.Popen")
    def test_notify_event_sends_toast(self, mock_popen, *mocks):
        notifier = self._notifier()
        with patch("babelfish_stt.notifier.shutil.which", return_value=None), \
               patch("babelfish_stt.notifier.Notify") as mock_notify_cls:
            notifier.notify_event("wakeword_detected")

        mock_notify_cls.assert_called_once()
        notification = mock_notify_cls.return_value
        self.assertEqual(notification.title, "Babelfish")
        self.assertEqual(
            notification.message, EVENT_MESSAGES["wakeword_detected"]
        )
        notification.send.assert_called_once_with(block=False)
        mock_popen.assert_not_called()

    @patch("babelfish_stt.notifier.shutil.which", return_value=None)
    @patch("babelfish_stt.notifier.Notify")
    def test_disabled_notifications_send_nothing(self, mock_notify_cls, mock_which):
        notifier = self._notifier(enabled=False)

        notifier.notify_event("wakeword_detected")
        notifier.notify_event("stop_word_detected")

        mock_notify_cls.assert_not_called()

    @patch("babelfish_stt.notifier.shutil.which", return_value=None)
    @patch("babelfish_stt.notifier.Notify")
    def test_unknown_event_sends_nothing(self, mock_notify_cls, mock_which):
        notifier = self._notifier()

        notifier.notify_event("some_other_event")

        mock_notify_cls.assert_not_called()

    @patch("babelfish_stt.notifier.subprocess.Popen")
    def test_linux_uses_notify_send(self, mock_popen):
        notifier = self._notifier()
        with patch("babelfish_stt.notifier.platform.system", return_value="Linux"), \
               patch("babelfish_stt.notifier.shutil.which", return_value="/usr/bin/notify-send"), \
               patch("babelfish_stt.notifier.Notify") as mock_notify_cls:
            notifier.send("Test", "Hello")

        mock_popen.assert_called_once_with(
            ["/usr/bin/notify-send", "-t", "4000", "-a", "Babelfish", "Test", "Hello"]
        )
        mock_notify_cls.assert_not_called()


class TestEngineModelResolution(unittest.TestCase):
    MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"

    def setUp(self):
        import tempfile
        import shutil

        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.base_dir = Path(self._tmp) / "repo"

    def test_cache_dir_model_found(self):
        from babelfish_stt.engine import resolve_model_path

        model_dir = Path(self._tmp) / "cache" / "models" / self.MODEL_NAME
        model_dir.mkdir(parents=True)

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"), self.base_dir, self.MODEL_NAME
        )

        self.assertEqual(resolved, model_dir)

    def test_cache_dir_missing_model_falls_through(self):
        from babelfish_stt.engine import resolve_model_path

        # cache dir exists but has no model; repo/local dir also missing
        (Path(self._tmp) / "cache").mkdir()

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"), self.base_dir, self.MODEL_NAME
        )

        self.assertIsNone(resolved)

    def test_repo_local_used_when_no_cache_dir(self):
        from babelfish_stt.engine import resolve_model_path

        model_dir = self.base_dir / "models" / self.MODEL_NAME
        model_dir.mkdir(parents=True)

        resolved = resolve_model_path(None, self.base_dir, self.MODEL_NAME)

        self.assertEqual(resolved, model_dir)

    def test_cache_dir_takes_priority_over_repo_local(self):
        from babelfish_stt.engine import resolve_model_path

        cache_model = Path(self._tmp) / "cache" / "models" / self.MODEL_NAME
        cache_model.mkdir(parents=True)
        repo_model = self.base_dir / "models" / self.MODEL_NAME
        repo_model.mkdir(parents=True)

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"), self.base_dir, self.MODEL_NAME
        )

        self.assertEqual(resolved, cache_model)

    def test_nothing_found_returns_none(self):
        from babelfish_stt.engine import resolve_model_path

        resolved = resolve_model_path(None, self.base_dir, self.MODEL_NAME)

        self.assertIsNone(resolved)

    def test_engine_uses_cache_dir_path_in_load_call(self):
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.config import HardwareConfig

        cache_model = Path(self._tmp) / "cache" / "models" / self.MODEL_NAME
        cache_model.mkdir(parents=True)

        config = BabelfishConfig(
            hardware=HardwareConfig(device="cpu"),
            cache={"cache_dir": str(Path(self._tmp) / "cache")},
        )

        with patch("onnx_asr.load_model") as mock_load, \
               patch("babelfish_stt.engine.get_memory_usage", return_value={"total": 0, "used": 0}), \
               patch("babelfish_stt.engine.resolve_device", return_value="cpu"), \
               patch("babelfish_stt.engine.get_device_name", return_value="CPU"):
            engine = STTEngine(config=config)

        _, kwargs = mock_load.call_args
        self.assertEqual(kwargs["path"], str(cache_model))

    def test_engine_without_local_model_passes_path_none(self):
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.config import HardwareConfig

        config = BabelfishConfig(hardware=HardwareConfig(device="cpu"))
        config.cache.cache_dir = None

        with patch("onnx_asr.load_model") as mock_load, \
               patch("babelfish_stt.engine.get_memory_usage", return_value={"total": 0, "used": 0}), \
               patch("babelfish_stt.engine.resolve_device", return_value="cpu"), \
               patch("babelfish_stt.engine.get_device_name", return_value="CPU"):
            STTEngine(config=config)

        _, kwargs = mock_load.call_args
        self.assertIsNone(kwargs["path"])


if __name__ == "__main__":
    unittest.main()
