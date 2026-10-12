import unittest
import subprocess
import sys
import logging
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

    def test_log_level_defaults_to_info(self):
        from babelfish_stt.main import parse_args

        args = parse_args([])

        self.assertEqual(args.log_level, "info")

    def test_log_level_accepts_debug_case_insensitively(self):
        from babelfish_stt.main import parse_args

        self.assertEqual(parse_args(["--log-level", "debug"]).log_level, "debug")
        self.assertEqual(parse_args(["--log-level", "DEBUG"]).log_level, "debug")

    def test_invalid_log_level_fails(self):
        from babelfish_stt.main import parse_args

        with self.assertRaises(SystemExit) as ctx, \
                patch("sys.stderr", new=MagicMock()):
            parse_args(["--log-level", "verbose"])

        self.assertEqual(ctx.exception.code, 2)

    def test_main_configures_log_level_from_flag(self):
        from babelfish_stt.main import main

        argv = ["babelfish", "--log-level", "debug"]
        with patch("sys.argv", argv), \
                patch("babelfish_stt.main.HardwareManager") as mock_hw, \
                patch("babelfish_stt.main.asyncio.run") as mock_run, \
                patch("babelfish_stt.main.logging.basicConfig") as mock_config:
            main()

        mock_config.assert_called_once()
        self.assertEqual(
            mock_config.call_args.kwargs["level"], logging.DEBUG
        )
        mock_hw.assert_called_once()

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
        (model_dir / "encoder-model.onnx").touch()  # a card holds an .onnx

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"), self.base_dir, self.MODEL_NAME
        )

        self.assertEqual(resolved, model_dir)

    def test_cache_dir_missing_model_falls_through(self):
        from babelfish_stt.engine import resolve_model_path

        # cache dir exists but has no card (no .onnx); repo-local dir also
        # missing — a GPU device falls through to None (HF auto-download)
        (Path(self._tmp) / "cache").mkdir()

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"), self.base_dir, self.MODEL_NAME
        )

        self.assertIsNone(resolved)

    def test_repo_local_used_when_no_cache_dir(self):
        from babelfish_stt.engine import resolve_model_path

        model_dir = self.base_dir / "models" / self.MODEL_NAME
        model_dir.mkdir(parents=True)
        (model_dir / "encoder-model.onnx").touch()

        resolved = resolve_model_path(None, self.base_dir, self.MODEL_NAME)

        self.assertEqual(resolved, model_dir)

    def test_cache_dir_takes_priority_over_repo_local(self):
        from babelfish_stt.engine import resolve_model_path

        cache_model = Path(self._tmp) / "cache" / "models" / self.MODEL_NAME
        cache_model.mkdir(parents=True)
        (cache_model / "encoder-model.onnx").touch()
        repo_model = self.base_dir / "models" / self.MODEL_NAME
        repo_model.mkdir(parents=True)
        (repo_model / "encoder-model.onnx").touch()

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"), self.base_dir, self.MODEL_NAME
        )

        self.assertEqual(resolved, cache_model)

    def test_nothing_found_returns_none(self):
        from babelfish_stt.engine import resolve_model_path

        resolved = resolve_model_path(None, self.base_dir, self.MODEL_NAME)

        self.assertIsNone(resolved)

    # --- The strict device-keyed weights ladder (ADR 0014) ---
    #
    # cpu implies redux and the engine MATERIALIZES the card when missing;
    # GPU devices never touch redux. Unit tests stub the provisioning
    # helper — no network here, ever.

    REDUX_CARD_DIR = "nemo-parakeet-tdt-0.6b-v3-redux"

    def _seed_redux(self, dest: Path) -> Path:
        from babelfish_stt.engine import REDUX_CARD_FILES

        dest.mkdir(parents=True, exist_ok=True)
        for fname in REDUX_CARD_FILES:
            (dest / fname).touch()
        return dest

    def test_cpu_device_resolves_the_redux_card(self):
        from babelfish_stt.engine import resolve_model_path

        redux = self._seed_redux(self.base_dir / "models" / self.REDUX_CARD_DIR)

        resolved = resolve_model_path(
            None, self.base_dir, self.MODEL_NAME, device="cpu"
        )

        self.assertEqual(resolved, redux)

    def test_cpu_ignores_the_fp32_card_and_provisions_redux(self):
        """Hard invariant: fp32 v3 is never served on cpu. With only the
        fp32 card sitting in the cache, a cpu device materializes the
        redux card instead (provisioning stubbed)."""
        from babelfish_stt.engine import resolve_model_path

        (self.base_dir / "models" / self.MODEL_NAME).mkdir(parents=True)
        (self.base_dir / "models" / self.MODEL_NAME / "encoder-model.onnx").touch()
        expected_dest = self.base_dir / "models" / self.REDUX_CARD_DIR

        with patch(
            "babelfish_stt.engine._ensure_redux_card",
            side_effect=lambda dest: dest and self._seed_redux(dest),
        ) as mock_ensure:
            resolved = resolve_model_path(
                None, self.base_dir, self.MODEL_NAME, device="cpu"
            )

        mock_ensure.assert_called_once_with(expected_dest)
        self.assertEqual(resolved, expected_dest)

    def test_cpu_partial_card_is_repaired_not_served(self):
        """A crash mid-download leaves a partial dir (e.g. no decoder):
        resolve must not hand a partial card to the loader — it calls the
        provisioning helper, which completes the dir in place."""
        from babelfish_stt.engine import resolve_model_path

        dest = self.base_dir / "models" / self.REDUX_CARD_DIR
        dest.mkdir(parents=True)
        (dest / "config.json").touch()
        (dest / "encoder-model.onnx").touch()

        with patch(
            "babelfish_stt.engine._ensure_redux_card",
            side_effect=lambda dest: self._seed_redux(dest),
        ):
            resolved = resolve_model_path(
                None, self.base_dir, self.MODEL_NAME, device="cpu"
            )

        self.assertEqual(resolved, dest)

    def test_cpu_card_auto_provision_uses_the_pinned_source(self):
        """The engine-side provisioning record (ADR 0014): the same pinned
        repo + revision + exactly the 4 loader files the bootstrap uses
        (mirrored constants — keep the two in agreement)."""
        from babelfish_stt import engine
        from babelfish_stt.engine import resolve_model_path

        expected_dest = self.base_dir / "models" / self.REDUX_CARD_DIR

        def fake_download(**kwargs):
            self._seed_redux(Path(kwargs["local_dir"]))
            return str(kwargs["local_dir"])

        with patch("huggingface_hub.snapshot_download", side_effect=fake_download) as mock_dl:
            resolved = resolve_model_path(
                None, self.base_dir, self.MODEL_NAME, device="cpu"
            )

        kwargs = mock_dl.call_args.kwargs
        self.assertEqual(kwargs["repo_id"], engine.REDUX_REPO)
        self.assertEqual(kwargs["revision"], engine.REDUX_REVISION)
        self.assertEqual(kwargs["allow_patterns"], list(engine.REDUX_CARD_FILES))
        self.assertEqual(Path(kwargs["local_dir"]), expected_dest)
        self.assertEqual(resolved, expected_dest)

    def test_offline_cpu_without_card_raises_actionable(self):
        """Missing card + no network = refuse to start, never an fp32
        fallback: the error names the remedy."""
        from babelfish_stt.engine import resolve_model_path

        with patch(
            "huggingface_hub.snapshot_download",
            side_effect=OSError("no network"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                resolve_model_path(None, self.base_dir, self.MODEL_NAME, device="cpu")

        self.assertIn("fp32 v3 is never used on cpu", str(ctx.exception))

    def test_cache_dir_takes_priority_within_a_card(self):
        from babelfish_stt.engine import resolve_model_path

        cache_model = self._seed_redux(
            Path(self._tmp) / "cache" / "models" / self.REDUX_CARD_DIR
        )
        repo_model = self._seed_redux(self.base_dir / "models" / self.REDUX_CARD_DIR)

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"),
            self.base_dir,
            self.MODEL_NAME,
            device="cpu",
        )

        self.assertEqual(resolved, cache_model)

    def test_gpu_never_loads_a_redux_dir(self):
        """Hard invariant: a -redux dir in the cache cannot leak into a
        GPU device — the GPU ladder resolves the fp32 card only, falling
        to None (onnx-asr's fp32 HF default) when that card is absent."""
        from babelfish_stt.engine import resolve_model_path

        self._seed_redux(Path(self._tmp) / "cache" / "models" / self.REDUX_CARD_DIR)

        resolved = resolve_model_path(
            str(Path(self._tmp) / "cache"), self.base_dir, self.MODEL_NAME,
            device="cuda:0",
        )

        self.assertIsNone(resolved)

    def test_engine_uses_cache_dir_path_in_load_call(self):
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.config import HardwareConfig

        # ADR 0014: device cpu resolves the REDUX card of the ladder: the
        # cache dir named nemo-parakeet-tdt-0.6b-v3-redux.
        cache_model = self._seed_redux(
            Path(self._tmp) / "cache" / "models" / self.REDUX_CARD_DIR
        )

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
        self.assertEqual(engine.weights_tag, "parakeet-redux int4 MatMulNBits")

    def test_engine_gpu_device_resolves_the_fp32_card(self):
        """ADR 0014: a GPU device keeps the fp32 v3 card by design — GPU
        int4 MatMulNBits is not in scope."""
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.config import HardwareConfig

        cache_model = Path(self._tmp) / "cache" / "models" / self.MODEL_NAME
        cache_model.mkdir(parents=True)
        (cache_model / "encoder-model.onnx").touch()

        config = BabelfishConfig(
            hardware=HardwareConfig(device="cuda"),
            cache={"cache_dir": str(Path(self._tmp) / "cache")},
        )

        with patch("onnx_asr.load_model"), \
               patch("babelfish_stt.engine.get_memory_usage", return_value={"total": 0, "used": 0}), \
               patch("babelfish_stt.engine.resolve_device", return_value="cuda:0"), \
               patch("babelfish_stt.engine.get_device_name", return_value="Test GPU (CUDA)"):
            engine = STTEngine(config=config)

        self.assertEqual(engine.model_path, cache_model)
        self.assertEqual(engine.weights_tag, "fp32 v3")

    def test_engine_legacy_model_key_is_device_derived(self):
        """An old config carrying hardware.model must not resurrect the A/B
        override (cpu implies redux; redux never on gpu): the key is
        ignored by pydantic (extra='ignore') and the ladder stays
        device-derived."""
        from babelfish_stt.engine import STTEngine

        cache_model = self._seed_redux(
            Path(self._tmp) / "cache" / "models" / self.REDUX_CARD_DIR
        )
        config = BabelfishConfig.model_validate(
            {
                "hardware": {"device": "cpu", "model": "v3"},
                "cache": {"cache_dir": str(Path(self._tmp) / "cache")},
            }
        )

        with patch("onnx_asr.load_model"), \
               patch("babelfish_stt.engine.get_memory_usage", return_value={"total": 0, "used": 0}), \
               patch("babelfish_stt.engine.resolve_device", return_value="cpu"), \
               patch("babelfish_stt.engine.get_device_name", return_value="CPU"):
            engine = STTEngine(config=config)

        self.assertEqual(engine.model_path, cache_model)

    def test_engine_gpu_without_local_card_passes_path_none(self):
        # GPU device with no local fp32 card: onnx-asr's HF auto-download
        # (the cpu variant now provisions instead of resolving to None).
        from babelfish_stt.engine import STTEngine
        from babelfish_stt.config import HardwareConfig

        config = BabelfishConfig(hardware=HardwareConfig(device="cuda"))
        config.cache.cache_dir = None

        with patch("onnx_asr.load_model") as mock_load, \
               patch("babelfish_stt.engine.get_memory_usage", return_value={"total": 0, "used": 0}), \
               patch("babelfish_stt.engine.resolve_device", return_value="cuda:0"), \
               patch("babelfish_stt.engine.get_device_name", return_value="Test GPU (CUDA)"):
            STTEngine(config=config)

        _, kwargs = mock_load.call_args
        self.assertIsNone(kwargs["path"])


if __name__ == "__main__":
    unittest.main()
