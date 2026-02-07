import torch
from typing import Dict, Optional

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
