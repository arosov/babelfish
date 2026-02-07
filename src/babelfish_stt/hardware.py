import torch
import sounddevice as sd
from typing import Dict, Optional, List

def is_cuda_available() -> bool:
    """Checks if CUDA acceleration is available."""
    return torch.cuda.is_available()

def get_gpu_info() -> Dict:
    """Returns basic information about the GPU if available."""
    if not is_cuda_available():
        return {
            "cuda_available": False,
            "name": None,
            "vram_gb": 0.0
        }
    
    try:
        device_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory
        vram_gb = total_memory / (1024**3)
        
        return {
            "cuda_available": True,
            "name": device_name,
            "vram_gb": vram_gb
        }
    except Exception:
        return {
            "cuda_available": True,
            "name": "Unknown GPU",
            "vram_gb": 0.0
        }

def list_microphones() -> List[Dict]:
    """Lists all available audio input devices."""
    devices = sd.query_devices()
    input_devices = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_devices.append({
                "index": i,
                "name": dev['name'],
                "channels": dev['max_input_channels'],
                "sample_rate": dev['default_samplerate']
            })
    return input_devices
