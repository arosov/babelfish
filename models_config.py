from typing import Dict, List, Optional
from pydantic import BaseModel

class ModelInfo(BaseModel):
    name: str
    vram_usage_gb: float
    description: str

class HWAccelInfo(BaseModel):
    id: str
    name: str
    required_packages: List[str]
    description: str

# Definition of supported Whisper models and their estimated VRAM usage in float16
SUPPORTED_MODELS: Dict[str, ModelInfo] = {
    "base": ModelInfo(name="base", vram_usage_gb=0.7, description="Base model, slightly better than tiny"),
    "small": ModelInfo(name="small", vram_usage_gb=1.5, description="Good balance of speed and accuracy"),
    "distil-small.en": ModelInfo(name="distil-small.en", vram_usage_gb=1.0, description="Extremely fast English-only distilled model"),
    "medium": ModelInfo(name="medium", vram_usage_gb=3.0, description="High accuracy, slower"),
    "large-v3-turbo": ModelInfo(name="large-v3-turbo", vram_usage_gb=4.0, description="Optimized large model, very fast with near large-v3 accuracy"),
    "large-v3": ModelInfo(name="large-v3", vram_usage_gb=5.5, description="State-of-the-art accuracy, requires ~5.5GB VRAM"),
    "parakeet-tdt-110m": ModelInfo(name="m-baccari/parakeet-tdt-110m-ct2", vram_usage_gb=0.4, description="NVIDIA Parakeet TDT (Ultra-low latency)"),
    "parakeet-rnnt-1.1b": ModelInfo(name="m-baccari/parakeet-rnnt-1.1b-ct2", vram_usage_gb=2.8, description="NVIDIA Parakeet RNN-T (High accuracy)"),
}

# Supported wake words (Porcupine defaults)
SUPPORTED_WAKE_WORDS: List[str] = [
    "alexa", "americano", "blueberry", "bumblebee", "computer", 
    "grapefruits", "grasshopper", "hey google", "hey siri", 
    "jarvis", "ok google", "picovoice", "porcupine", "terminator"
]

# Definition of hardware acceleration options
HW_ACCEL_OPTIONS: Dict[str, HWAccelInfo] = {
    "cpu": HWAccelInfo(
        id="cpu",
        name="CPU / None",
        required_packages=["torch"],
        description="Run on CPU. Slowest option."
    ),
    "nvidia": HWAccelInfo(
        id="nvidia",
        name="NVIDIA CUDA",
        required_packages=["torch", "nvidia-cudnn-cu12"],
        description="NVIDIA GPU acceleration using CUDA."
    ),
    "amd": HWAccelInfo(
        id="amd",
        name="AMD ROCm",
        required_packages=["torch-rocm"],
        description="AMD GPU acceleration using ROCm."
    )
}
