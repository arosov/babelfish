import torch
import logging
import pyaudio
from models_config import SUPPORTED_MODELS, HW_ACCEL_OPTIONS, ModelInfo, HWAccelInfo, SUPPORTED_WAKE_WORDS
from typing import Tuple, Optional, List, Dict

logger = logging.getLogger("babelfish.hardware")

class HardwareManager:
    def __init__(self):
        self.accel_type = self._detect_accel_type()
        self.total_vram_gb = self._get_total_vram()

    def _detect_accel_type(self) -> str:
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0).lower()
            if "nvidia" in device_name or "geforce" in device_name or "rtx" in device_name:
                return "nvidia"
            return "nvidia"
        
        if hasattr(torch.version, 'hip') and torch.version.hip is not None:
             return "amd"
             
        return "cpu"

    def _get_total_vram(self) -> float:
        if self.accel_type in ["nvidia", "amd"]:
            try:
                return torch.cuda.get_device_properties(0).total_memory / (1024**3)
            except:
                return 0.0
        return 0.0

    def get_recommended_model(self) -> str:
        """
        Recommends a model based on available VRAM.
        Leaves some overhead (20%) for the system.
        """
        available_vram = self.total_vram_gb * 0.8
        
        # Iterate from largest to smallest
        for model_id in reversed(list(SUPPORTED_MODELS.keys())):
            if SUPPORTED_MODELS[model_id].vram_usage_gb <= available_vram:
                return model_id
        # Fallback to the first available model if none fit recommendation
        return next(iter(SUPPORTED_MODELS.keys()))

    def list_audio_devices(self) -> List[Dict]:
        """Lists all available audio input devices."""
        audio = pyaudio.PyAudio()
        devices = []
        try:
            for i in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    devices.append({
                        "index": i,
                        "name": info.get('name'),
                        "channels": info.get('maxInputChannels'),
                        "sample_rate": int(info.get('defaultSampleRate'))
                    })
        finally:
            audio.terminate()
        return devices

    def log_system_info(self):
        accel = HW_ACCEL_OPTIONS[self.accel_type]
        logger.info("="*50)
        logger.info("HARDWARE CONFIGURATION REPORT")
        logger.info(f"Acceleration: {accel.name} ({accel.id})")
        logger.info(f"Description:  {accel.description}")
        logger.info(f"Required:     {', '.join(accel.required_packages)}")
        
        if self.accel_type != "cpu":
            logger.info(f"GPU Device:   {torch.cuda.get_device_name(0)}")
            logger.info(f"Total VRAM:   {self.total_vram_gb:.2f} GB")
        
        rec_model = self.get_recommended_model()
        logger.info(f"Recommended:  {rec_model} (requires {SUPPORTED_MODELS[rec_model].vram_usage_gb} GB)")
        
        logger.info("Audio Input Devices:")
        for dev in self.list_audio_devices():
            logger.info(f"  [{dev['index']}] {dev['name']} ({dev['channels']} ch)")
        logger.info("="*50)

    def get_config_for_frontend(self):
        """Returns the full definition of what we support to drive the UI."""
        return {
            "supported_models": {k: v.dict() for k, v in SUPPORTED_MODELS.items()},
            "supported_wake_words": SUPPORTED_WAKE_WORDS,
            "accel_options": {k: v.dict() for k, v in HW_ACCEL_OPTIONS.items()},
            "audio_devices": self.list_audio_devices(),
            "current_hardware": {
                "accel_type": self.accel_type,
                "total_vram_gb": self.total_vram_gb,
                "device_name": torch.cuda.get_device_name(0) if self.accel_type != "cpu" else "CPU"
            }
        }