import torch
import sounddevice as sd
import numpy as np
from typing import Dict, Optional, List


def is_cuda_available() -> bool:
    """Checks if CUDA acceleration is available."""
    return torch.cuda.is_available()


def get_gpu_info() -> Dict:
    """Returns basic information about the GPU if available."""
    if not is_cuda_available():
        return {"cuda_available": False, "name": None, "vram_gb": 0.0}

    try:
        device_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory
        vram_gb = total_memory / (1024**3)

        return {"cuda_available": True, "name": device_name, "vram_gb": vram_gb}
    except Exception:
        return {"cuda_available": True, "name": "Unknown GPU", "vram_gb": 0.0}


def list_microphones() -> List[Dict]:
    """Lists all available audio input devices."""
    devices = sd.query_devices()
    input_devices = []
    best_mic_index = find_best_microphone()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            input_devices.append(
                {
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": dev["default_samplerate"],
                    "is_default": (i == best_mic_index),
                }
            )
    return input_devices


def find_best_microphone() -> Optional[int]:
    """
    Heuristically finds the most likely active microphone based on system priority.
    Prioritizes Audio Servers (PipeWire/Pulse) and system abstractions over raw hardware.
    Returns None if no input device is found.
    """
    devices = sd.query_devices()

    # Priority list (keywords ordered by preference)
    priority_keywords = [
        "pipewire",
        "pulse",
        "default",
        "sysdefault",
        "usb",
        "headset",
        "siberia",
    ]

    # Find the first device that matches the highest priority keyword
    for keyword in priority_keywords:
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0 and keyword in dev["name"].lower():
                return i

    # Fallback: First input device
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            return i

    return None


import sys


class HardwareManager:
    """
    Manages hardware discovery and validation.
    Acts as the 'brain' for hardware resource awareness.
    """

    def __init__(self):
        self.gpu_info = {"cuda_available": False, "name": None, "vram_gb": 0.0}
        self.microphones = []
        self.best_mic_index = None

    def probe(self):
        """
        Probes the system for available hardware (GPU and Microphones).
        Should be called early in the startup sequence.
        """
        import logging

        logging.info("Probing hardware...")

        self.gpu_info = get_gpu_info()
        self.microphones = list_microphones()
        self.best_mic_index = find_best_microphone()

        if self.gpu_info["cuda_available"]:
            logging.info(
                f"GPU Detected: {self.gpu_info['name']} ({self.gpu_info['vram_gb']:.2f} GB VRAM)"
            )
        else:
            logging.info("No CUDA GPU detected. Falling back to CPU mode.")

        logging.info(f"Found {len(self.microphones)} input device(s).")
        if self.best_mic_index is not None:
            mic_name = sd.query_devices(self.best_mic_index)["name"]
            logging.info(
                f"Selected best microphone: {mic_name} (index {self.best_mic_index})"
            )
        else:
            logging.error("CRITICAL: No microphone detected on this system!")
            print(
                "\n❌ ERROR: No microphone detected. Babelfish requires an input device to start."
            )
            sys.exit(1)

        return self


def list_hardware() -> List[Dict]:
    """Lists all supported hardware acceleration devices."""
    devices = [{"id": "cpu", "name": "CPU"}]
    if is_cuda_available():
        gpu = get_gpu_info()
        devices.append({"id": "cuda", "name": gpu["name"] or "NVIDIA GPU"})
    return devices
