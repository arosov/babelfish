import unittest
from unittest.mock import patch, MagicMock
from babelfish_stt.hardware import get_gpu_info, is_cuda_available

class TestHardware(unittest.TestCase):
    @patch('torch.cuda.is_available')
    def test_is_cuda_available(self, mock_is_available):
        mock_is_available.return_value = True
        self.assertTrue(is_cuda_available())
        
        mock_is_available.return_value = False
        self.assertFalse(is_cuda_available())

    @patch('torch.cuda.is_available')
    @patch('torch.cuda.get_device_name')
    @patch('torch.cuda.get_device_properties')
    def test_get_gpu_info_cuda(self, mock_get_props, mock_get_name, mock_is_available):
        mock_is_available.return_value = True
        mock_get_name.return_value = "NVIDIA GeForce RTX 3080"
        
        mock_props = MagicMock()
        mock_props.total_memory = 10 * 1024 * 1024 * 1024 # 10GB
        mock_get_props.return_value = mock_props
        
        info = get_gpu_info()
        self.assertEqual(info['name'], "NVIDIA GeForce RTX 3080")
        self.assertAlmostEqual(info['vram_gb'], 10.0)
        self.assertTrue(info['cuda_available'])

    @patch('torch.cuda.is_available')
    def test_get_gpu_info_no_cuda(self, mock_is_available):
        mock_is_available.return_value = False
        
        info = get_gpu_info()
        self.assertIsNone(info['name'])
        self.assertEqual(info['vram_gb'], 0.0)
        self.assertFalse(info['cuda_available'])

if __name__ == '__main__':
    unittest.main()
