import unittest
from unittest.mock import patch, MagicMock, AsyncMock, call
import asyncio
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from babelfish_stt.main import run_babelfish
from babelfish_stt.hardware import HardwareManager

class TestStartupIntegration(unittest.IsolatedAsyncioTestCase):
    @patch('babelfish_stt.main.BabelfishServer')
    @patch('babelfish_stt.main.ConfigManager')
    @patch('babelfish_stt.main.STTEngine')
    @patch('babelfish_stt.main.AudioStreamer')
    @patch('babelfish_stt.main.SileroVAD')
    @patch('babelfish_stt.main.WakeWordEngine')
    @patch('babelfish_stt.main.SinglePassPipeline')
    @patch('babelfish_stt.main.DoublePassPipeline')
    @patch('babelfish_stt.main.TerminalDisplay')
    @patch('babelfish_stt.main.threading.Event')
    @patch('babelfish_stt.main.asyncio.to_thread')
    @patch('babelfish_stt.main.asyncio.get_running_loop')
    async def test_run_babelfish_sequence(self, mock_loop, mock_to_thread, mock_event, mock_display, 
                                         mock_double_pipe, mock_single_pipe, mock_ww, mock_vad, 
                                         mock_streamer, mock_engine, mock_config_mgr, mock_server):
        # Setup mocks
        hw = MagicMock(spec=HardwareManager)
        hw.gpu_info = {'cuda_available': True, 'vram_gb': 8.0}
        hw.best_mic_index = 1
        
        cm = mock_config_mgr.return_value
        cm.is_valid.return_value = True
        cm.config.server.host = "127.0.0.1"
        cm.config.server.port = 8123
        cm.config.hardware.device = "cuda"
        cm.config.hardware.microphone_index = 1
        cm.config.pipeline.double_pass = False
        cm.config.voice.wakeword = None
        cm.config.voice.stop_words = []
        
        srv = mock_server.return_value
        srv.start = AsyncMock()
        
        # We need to make heavy_init return something
        pipeline_mock = MagicMock()
        pipeline_mock.stop_detector = None
        mock_to_thread.return_value = (MagicMock(), MagicMock(), None, MagicMock(), MagicMock(), pipeline_mock)
        
        # Mock asyncio.Future to return immediately
        f = asyncio.Future()
        f.set_result(None)
        
        # Mock stt_task
        stt_task = asyncio.Future()
        stt_task.set_result(None)
        mock_loop.return_value.run_in_executor.return_value = stt_task
        
        with patch('babelfish_stt.main.asyncio.Future', return_value=f):
            await run_babelfish(hw)
        
        # Verify sequence
        # 1. Config initialized
        mock_config_mgr.assert_called_once()
        # 2. Config validated against hw
        cm.is_valid.assert_called_with(hw)
        # 3. Server created with config
        mock_server.assert_called_with(cm)
        # 4. Server started before heavy_init
        srv.start.assert_called_once()
        # 5. heavy_init called (via to_thread)
        mock_to_thread.assert_called_once()

    @patch('babelfish_stt.main.ConfigManager')
    @patch('babelfish_stt.main.BabelfishServer')
    @patch('babelfish_stt.main.asyncio.get_running_loop')
    async def test_run_babelfish_generates_defaults_if_invalid(self, mock_loop, mock_server, mock_config_mgr):
        hw = MagicMock(spec=HardwareManager)
        cm = mock_config_mgr.return_value
        cm.is_valid.return_value = False # INVALID
        cm.config.server.host = "127.0.0.1"
        cm.config.server.port = 8123
        cm.config.voice.stop_words = []
        
        srv = mock_server.return_value
        srv.start = AsyncMock()

        # Mock stt_task
        stt_task = asyncio.Future()
        stt_task.set_result(None)
        mock_loop.return_value.run_in_executor.return_value = stt_task
        
        # Minimal mock for the rest
        pipeline_mock = MagicMock()
        pipeline_mock.stop_detector = None
        with patch('babelfish_stt.main.asyncio.to_thread', return_value=(MagicMock(),)*5 + (pipeline_mock,)):
            with patch('babelfish_stt.main.asyncio.Future', side_effect=asyncio.CancelledError):
                try:
                    await run_babelfish(hw)
                except asyncio.CancelledError:
                    pass
        
        cm.generate_optimal_defaults.assert_called_with(hw)

if __name__ == '__main__':
    unittest.main()
