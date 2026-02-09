import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from babelfish_stt.hardware import find_best_microphone, list_microphones, HardwareManager

class TestStartupHardware(unittest.TestCase):
    @patch('sounddevice.query_devices')
    def test_list_microphones_empty(self, mock_query):
        # Mocking sounddevice to return only output devices or no devices
        mock_query.return_value = [
            {'name': 'Output Only', 'max_input_channels': 0, 'max_output_channels': 2, 'default_samplerate': 44100}
        ]
        mics = list_microphones()
        self.assertEqual(len(mics), 0)

    @patch('sounddevice.query_devices')
    def test_find_best_microphone_none_available(self, mock_query):
        # Mocking sounddevice to return no input devices
        mock_query.return_value = [
            {'name': 'Output Only', 'max_input_channels': 0, 'max_output_channels': 2, 'default_samplerate': 44100}
        ]
        idx = find_best_microphone()
        self.assertIsNone(idx)

    @patch('sounddevice.query_devices')
    @patch('babelfish_stt.hardware.get_gpu_info')
    def test_probe_exits_on_no_mic(self, mock_gpu, mock_query):
        mock_gpu.return_value = {'cuda_available': False, 'name': None, 'vram_gb': 0.0}
        mock_query.return_value = [
            {'name': 'Output Only', 'max_input_channels': 0, 'max_output_channels': 2, 'default_samplerate': 44100}
        ]
        
        hm = HardwareManager()
        with self.assertRaises(SystemExit) as cm:
            hm.probe()
        self.assertEqual(cm.exception.code, 1)

    @patch('sounddevice.query_devices')
    @patch('torch.cuda.is_available')
    @patch('torch.cuda.get_device_properties')
    @patch('torch.cuda.get_device_name')
    def test_hardware_manager_probe(self, mock_get_name, mock_get_props, mock_is_available, mock_query):
        mock_is_available.return_value = True
        mock_get_name.return_value = "RTX 4090"
        mock_props = MagicMock()
        mock_props.total_memory = 24 * 1024 * 1024 * 1024
        mock_get_props.return_value = mock_props
        
        devices = [
            {'name': 'Mic 1', 'max_input_channels': 1, 'max_output_channels': 0, 'default_samplerate': 16000},
            {'name': 'Speaker', 'max_input_channels': 0, 'max_output_channels': 2, 'default_samplerate': 48000}
        ]
        
        def query_devices_mock(index=None):
            if index is None:
                return devices
            return devices[index]
            
        mock_query.side_effect = query_devices_mock
        
        hm = HardwareManager()
        hm.probe()
        
        self.assertTrue(hm.gpu_info['cuda_available'])
        self.assertEqual(hm.gpu_info['vram_gb'], 24.0)
        self.assertEqual(len(hm.microphones), 1)
        self.assertEqual(hm.best_mic_index, 0)

if __name__ == '__main__':
    unittest.main()
