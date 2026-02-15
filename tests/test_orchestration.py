import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np


class TestOrchestration(unittest.TestCase):
    @patch("babelfish_stt.main.ConfigManager")
    @patch("babelfish_stt.main.BabelfishServer")
    @patch("babelfish_stt.main.HardwareManager")
    @patch("babelfish_stt.main.StandardPipeline")
    @patch("babelfish_stt.main.WakeWordEngine")
    @patch("babelfish_stt.main.AudioStreamer")
    @patch("babelfish_stt.main.SileroVAD")
    @patch("babelfish_stt.main.TerminalDisplay")
    @patch("babelfish_stt.main.asyncio.to_thread")
    async def test_orchestration_lifecycle(
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

        hw = MagicMock()
        hw.gpu_info = {"cuda_available": False}

        config = MagicMock()
        config.server.host = "127.0.0.1"
        config.server.port = 8123
        config.hardware.device = "cpu"
        config.hardware.microphone_name = None
        config.voice.wakeword = "hey"
        config.voice.stop_words = []

        cm = MagicMock()
        cm.config = config
        cm.is_valid.return_value = True

        mock_hw_mgr.return_value = hw
        mock_server.return_value = MagicMock(start=AsyncMock())

        pipe_inst = MagicMock()
        pipe_inst.is_idle = True
        pipe_inst.vad = MagicMock()
        pipe_inst.vad.is_speech.return_value = False

        stream_inst = MagicMock()
        chunk = np.zeros(512, dtype=np.float32)
        stream_inst.stream.return_value = iter([chunk])

        ww_inst = MagicMock()
        ww_inst.active_start_word = "hey"
        ww_inst.process_chunk.return_value = {"hey": 0.0}

        async def fake_to_thread(*args):
            return (cm, MagicMock(), ww_inst, MagicMock(), stream_inst, pipe_inst)

        mock_to_thread.side_effect = fake_to_thread

        await run_babelfish(hw=hw, wakeword="hey")

        self.assertTrue(pipe_inst.request_mode.called)

    @patch("babelfish_stt.main.ConfigManager")
    @patch("babelfish_stt.main.BabelfishServer")
    @patch("babelfish_stt.main.HardwareManager")
    @patch("babelfish_stt.main.StandardPipeline")
    @patch("babelfish_stt.main.WakeWordEngine")
    @patch("babelfish_stt.main.AudioStreamer")
    @patch("babelfish_stt.main.SileroVAD")
    @patch("babelfish_stt.main.TerminalDisplay")
    @patch("babelfish_stt.main.asyncio.to_thread")
    async def test_state_transition_call(
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

        hw = MagicMock()
        hw.gpu_info = {"cuda_available": False}

        config = MagicMock()
        config.server.host = "127.0.0.1"
        config.server.port = 8123
        config.hardware.device = "cpu"
        config.hardware.microphone_name = None
        config.voice.wakeword = "hey"
        config.voice.stop_words = []

        cm = MagicMock()
        cm.config = config
        cm.is_valid.return_value = True

        mock_hw_mgr.return_value = hw
        mock_server.return_value = MagicMock(start=AsyncMock())

        pipe_inst = MagicMock()
        pipe_inst.is_idle = True

        def set_idle(val):
            pipe_inst.is_idle = val

        pipe_inst.request_mode = MagicMock(side_effect=set_idle)
        pipe_inst.vad = MagicMock()
        pipe_inst.vad.is_speech.return_value = True

        stream_inst = MagicMock()
        chunk = np.zeros(512, dtype=np.float32)
        stream_inst.stream.return_value = iter([chunk])

        ww_inst = MagicMock()
        ww_inst.active_start_word = "hey"
        ww_inst.process_chunk.return_value = {"hey": 1.0}

        async def fake_to_thread(*args):
            return (cm, MagicMock(), ww_inst, MagicMock(), stream_inst, pipe_inst)

        mock_to_thread.side_effect = fake_to_thread

        await run_babelfish(hw=hw, wakeword="hey")

        pipe_inst.request_mode.assert_called()


if __name__ == "__main__":
    unittest.main()
