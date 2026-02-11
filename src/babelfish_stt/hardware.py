import sounddevice as sd
import numpy as np
import subprocess
import shutil
import sys
from typing import Dict, Optional, List


def is_cuda_available() -> bool:
    """Checks if CUDA acceleration is available via ONNX Runtime."""
    try:
        import onnxruntime as ort

        return "CUDAExecutionProvider" in ort.get_available_providers()
    except ImportError:
        return False


def get_gpu_info() -> Dict:
    """Returns basic information about the GPU if available."""
    if not is_cuda_available():
        return {"cuda_available": False, "name": None, "vram_gb": 0.0}

    # Since torch might be CPU-only, we use nvidia-smi as a fallback for metadata
    # or just return generic info if available.
    try:
        if shutil.which("nvidia-smi"):
            output = (
                subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=name,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    stderr=subprocess.STDOUT,
                )
                .decode("utf-8")
                .strip()
                .split("\n")[0]
            )
            name, vram = output.split(",")
            return {
                "cuda_available": True,
                "name": name.strip(),
                "vram_gb": float(vram.strip()) / 1024.0,
            }
    except Exception:
        pass

    return {
        "cuda_available": True,
        "name": "NVIDIA GPU",
        "vram_gb": 4.0,
    }  # Assume 4GB if detection fails


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
        self.available_providers = []
        self.microphones = []
        self.best_mic_index = None

    def probe(self):
        """
        Probes the system for available hardware (GPU and Microphones).
        Should be called early in the startup sequence.
        """
        import logging
        import onnxruntime as ort

        logging.info("Probing hardware...")

        self.available_providers = ort.get_available_providers()
        self.gpu_info = get_gpu_info()
        self.microphones = list_microphones()
        self.best_mic_index = find_best_microphone()

        if self.gpu_info["cuda_available"]:
            logging.info(
                f"GPU Detected: {self.gpu_info['name']} ({self.gpu_info['vram_gb']:.2f} GB VRAM)"
            )
        elif "ROCMExecutionProvider" in self.available_providers:
            logging.info("AMD GPU (ROCm) detected via ONNX Runtime.")
        elif "DmlExecutionProvider" in self.available_providers:
            logging.info("DirectML support detected via ONNX Runtime.")
        else:
            logging.info(
                "No supported GPU acceleration detected. Falling back to CPU mode."
            )

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


def get_windows_gpu_names() -> List[str]:
    """Retrieves GPU names on Windows using WMIC."""
    names = []
    if sys.platform != "win32":
        return names
    try:
        output = (
            subprocess.check_output(
                "wmic path win32_VideoController get name", shell=True
            )
            .decode()
            .strip()
            .split("\n")
        )
        # Skip header
        for line in output[1:]:
            name = line.strip()
            if name:
                names.append(name)
    except Exception:
        pass
    return names


def _get_nvidia_gpus() -> List[Dict]:
    """
    Returns a list of detected NVIDIA GPUs using nvidia-smi.
    Returns empty list if tool is missing or fails.
    """
    gpus = []
    if not shutil.which("nvidia-smi"):
        return gpus

    try:
        output = (
            subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.STDOUT,
            )
            .decode("utf-8")
            .strip()
            .split("\n")
        )

        for i, line in enumerate(output):
            parts = line.split(",")
            if len(parts) >= 2:
                name = parts[0].strip()
                vram_mb = parts[1].strip()
                try:
                    vram_gb = float(vram_mb) / 1024.0
                    display_name = f"{name} ({vram_gb:.1f} GB)"
                except ValueError:
                    display_name = name

                gpus.append({"id": f"cuda:{i}", "name": display_name})
    except Exception:
        pass

    return gpus


def list_hardware() -> List[Dict]:
    """Lists all supported hardware acceleration devices."""
    devices = [{"id": "cpu", "name": "CPU"}]

    try:
        import onnxruntime as ort

        available = ort.get_available_providers()

        if "CUDAExecutionProvider" in available:
            # Detect actual GPUs
            nvidia_gpus = _get_nvidia_gpus()
            if nvidia_gpus:
                devices.extend(nvidia_gpus)
            else:
                # Fallback generic if nvidia-smi failed but CUDA is available
                devices.append({"id": "cuda", "name": "NVIDIA GPU (Generic)"})

        if "ROCMExecutionProvider" in available:
            devices.append({"id": "rocm", "name": "AMD GPU (ROCm)"})

        if "DmlExecutionProvider" in available:
            # On Windows, DirectML is the unified provider.
            # We try to fetch the actual GPU name to be more user-friendly.
            name = "DirectML (Windows)"
            gpu_names = get_windows_gpu_names()
            if gpu_names:
                # Join multiple GPUs if present, or just take the first one
                # Usually users care about the primary one or just want to see their card name
                pretty_names = ", ".join(gpu_names)
                name = f"{pretty_names} (DirectML)"

            devices.append({"id": "dml", "name": name})

        if "OpenVINOExecutionProvider" in available:
            devices.append({"id": "openvino", "name": "Intel Graphics (OpenVINO)"})

    except Exception:
        pass

    return devices
