import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np


class TestE2EVoiceControl(unittest.TestCase):
    @patch("babelfish_stt.main.ConfigManager")
    @patch("babelfish_stt.main.BabelfishServer")
    @patch("babelfish_stt.main.HardwareManager")
    @patch("babelfish_stt.main.StandardPipeline")
    @patch("babelfish_stt.main.WakeWordEngine")
    @patch("babelfish_stt.main.AudioStreamer")
    @patch("babelfish_stt.main.SileroVAD")
    @patch("babelfish_stt.main.TerminalDisplay")
    @patch("babelfish_stt.main.asyncio.to_thread")
    async def test_full_lifecycle_logging(
        self,
        mock_to_thread,
        mock_display,
        mock_vad,
        mock_streamer,
        mock_ww,
        mock_pipeline,
        mock_hw_mgr,
        mock_server,
    ):
        from babelfish_stt.main import run_babelfish

        # Setup hardware mock
        hw = MagicMock()
        hw.gpu_info = {"cuda_available": False}

        # Setup config mock
        config = MagicMock()
        config.server.host = "127.0.0.1"
        config.server.port = 8123
        config.hardware.device = "cpu"
        config.hardware.microphone_name = None
        config.voice.wakeword = "hey"
        config.voice.stop_words = []
        config.pipeline.silence_threshold_ms = 400
        config.pipeline.update_interval_ms = 100

        cm = MagicMock()
        cm.config = config
        cm.is_valid.return_value = True

        mock_hw_mgr.return_value = hw

        # Setup server mock
        srv = MagicMock()
        srv.start = AsyncMock()
        srv.broadcast_status = AsyncMock()
        mock_server.return_value = srv

        # Setup pipeline mock
        pipe_inst = MagicMock()
        pipe_inst.is_idle = True
        pipe_inst.vad = MagicMock()
        pipe_inst.vad.is_speech.return_value = True
        pipe_inst.request_mode = MagicMock()

        # Setup streamer mock
        stream_inst = MagicMock()
        chunk = np.zeros(512, dtype=np.float32)
        stream_inst.stream.return_value = iter([chunk])

        # Setup ww mock
        ww_inst = MagicMock()
        ww_inst.active_start_word = "hey"
        ww_inst.active_stop_word = None
        ww_inst.process_chunk.return_value = {"hey": 0.9}

        # Setup display mock
        disp_inst = MagicMock()

        # Make to_thread return our mocks
        async def fake_to_thread(*args):
            return (cm, srv, ww_inst, disp_inst, stream_inst, pipe_inst)

        mock_to_thread.side_effect = fake_to_thread

        # Run the function
        await run_babelfish(hw=hw, wakeword="hey")

        # Verify pipeline was used
        self.assertTrue(pipe_inst.request_mode.called)


if __name__ == "__main__":
    unittest.main()
