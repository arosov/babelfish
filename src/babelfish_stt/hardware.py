import sounddevice as sd
import numpy as np
import subprocess
import shutil
import sys
import os
import ctypes
import ctypes.util
from typing import Dict, Optional, List


def detect_nvidia() -> bool:
    """Detects NVIDIA GPU presence by checking for libcuda/nvcuda libraries."""
    lib_name = "nvcuda.dll" if sys.platform == "win32" else "libcuda.so.1"
    try:
        # 1. Try direct loading
        ctypes.CDLL(lib_name)
        return True
    except:
        pass
    # 2. Try finding via util
    found_path = ctypes.util.find_library(lib_name)
    if found_path:
        try:
            ctypes.CDLL(found_path)
            return True
        except:
            pass
    return False


def detect_amd_linux() -> bool:
    """Detects AMD GPU on Linux by checking for ROCm devices or libraries."""
    if sys.platform != "linux":
        return False
    if os.path.exists("/dev/kfd"):
        return True
    try:
        if ctypes.util.find_library("libhsa-runtime64.so.1"):
            return True
    except:
        pass
    return False


def detect_metal() -> bool:
    """Detects Apple Silicon / Metal support."""
    if sys.platform != "darwin":
        return False
    return os.path.exists("/System/Library/Frameworks/Metal.framework")


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


def get_device_name(device_type: str = "cpu") -> str:
    """
    Returns a human-readable name for the active device type.
    """
    if device_type == "cpu":
        return "CPU"

    if device_type.startswith("cuda"):
        device_id = 0
        if ":" in device_type:
            try:
                device_id = int(device_type.split(":")[1])
            except ValueError:
                pass

        # Try to get real name via nvidia-smi
        if shutil.which("nvidia-smi"):
            try:
                output = (
                    subprocess.check_output(
                        [
                            "nvidia-smi",
                            f"--id={device_id}",
                            "--query-gpu=name",
                            "--format=csv,noheader",
                        ],
                        stderr=subprocess.STDOUT,
                    )
                    .decode("utf-8")
                    .strip()
                )
                if output:
                    return output
            except Exception:
                pass
        return f"NVIDIA GPU (CUDA:{device_id})"

    if device_type == "rocm":
        # Try to get name via rocm-smi
        smi_path = shutil.which("rocm-smi") or "/opt/rocm/bin/rocm-smi"
        if os.path.exists(smi_path):
            try:
                output = subprocess.check_output(
                    [smi_path, "--showproductname", "--json"]
                ).decode("utf-8")
                import json

                data = json.loads(output)
                for card in data.values():
                    name = card.get("Card series", card.get("Product Name"))
                    if name:
                        return name
            except Exception:
                pass
        return "AMD GPU (ROCm)"

    if device_type.startswith("dml") and sys.platform == "win32":
        names = get_windows_gpu_names()
        device_id = 0
        if ":" in device_type:
            try:
                device_id = int(device_type.split(":")[1])
            except ValueError:
                pass

        if 0 <= device_id < len(names):
            return names[device_id]
        return names[0] if names else "DirectML GPU"

    if device_type == "metal" and sys.platform == "darwin":
        # For Mac, actual hardware name can be found via system_profiler or sysctl
        try:
            output = (
                subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"])
                .decode("utf-8")
                .strip()
            )
            if output:
                return output
        except Exception:
            pass
        return "Apple Silicon"

    return device_type.upper()


def get_memory_usage(device_type: str = "cpu") -> Dict[str, float]:
    """
    Generic dispatcher to get memory usage for the active device type.
    Supported: cuda, rocm, dml (Windows), metal (macOS).
    Returns {"total": 0.0, "used": 0.0} if not available.
    """
    if device_type.startswith("cuda"):
        device_id = 0
        if ":" in device_type:
            try:
                device_id = int(device_type.split(":")[1])
            except ValueError:
                pass
        return _get_nvidia_memory(device_id)

    if device_type == "rocm":
        return _get_rocm_memory()

    if device_type.startswith("dml") and sys.platform == "win32":
        device_id = 0
        if ":" in device_type:
            try:
                device_id = int(device_type.split(":")[1])
            except ValueError:
                pass
        return _get_windows_memory(device_id)

    if device_type == "metal" and sys.platform == "darwin":
        return _get_macos_memory()

    return {"total": 0.0, "used": 0.0}


def _get_nvidia_memory(device_index: int = 0) -> Dict[str, float]:
    """NVIDIA specific memory query."""
    if not shutil.which("nvidia-smi"):
        return {"total": 0.0, "used": 0.0}

    try:
        output = (
            subprocess.check_output(
                [
                    "nvidia-smi",
                    f"--id={device_index}",
                    "--query-gpu=memory.total,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.STDOUT,
            )
            .decode("utf-8")
            .strip()
            .split("\n")[0]
        )
        total_mb, used_mb = output.split(",")
        return {
            "total": float(total_mb.strip()) / 1024.0,
            "used": float(used_mb.strip()) / 1024.0,
        }
    except Exception:
        return {"total": 0.0, "used": 0.0}


def _get_rocm_memory() -> Dict[str, float]:
    """AMD ROCm (Linux) specific memory query."""
    # Try common locations if not in PATH
    smi_path = shutil.which("rocm-smi") or "/opt/rocm/bin/rocm-smi"
    if not os.path.exists(smi_path):
        return {"total": 0.0, "used": 0.0}

    try:
        # Get JSON output for easier parsing
        output = subprocess.check_output(
            [smi_path, "--showmeminfo", "vram", "--json"], stderr=subprocess.STDOUT
        ).decode("utf-8")
        import json

        data = json.loads(output)
        # rocm-smi JSON structure can vary, but usually it's keyed by 'cardX'
        for card in data.values():
            total = float(card.get("VRAM Total Memory (B)", 0)) / (1024**3)
            used = float(card.get("VRAM Total Used (B)", 0)) / (1024**3)
            if total > 0:
                return {"total": total, "used": used}
    except Exception:
        pass
    return {"total": 0.0, "used": 0.0}


def _get_macos_memory() -> Dict[str, float]:
    """Apple Silicon Unified Memory query."""
    try:
        # Total RAM
        total_bytes = int(
            subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip()
        )
        total_gb = total_bytes / (1024**3)

        # Used RAM (Heuristic using vm_stat)
        # Pages active + Pages wired is a good proxy for 'Used' in the context of AI models
        vm_output = subprocess.check_output(["vm_stat"]).decode("utf-8")
        lines = vm_output.split("\n")
        page_size = 4096  # Default
        active = 0
        wired = 0
        for line in lines:
            if "page size of" in line:
                page_size = int(line.split()[-2])
            elif "Pages active:" in line:
                active = int(line.split()[-1].strip("."))
            elif "Pages wired down:" in line:
                wired = int(line.split()[-1].strip("."))

        used_gb = ((active + wired) * page_size) / (1024**3)
        return {"total": total_gb, "used": used_gb}
    except Exception:
        return {"total": 0.0, "used": 0.0}


def _get_windows_memory(device_index: int = 0) -> Dict[str, float]:
    """Windows generic (DirectML/AMD/Intel) memory query via PowerShell."""
    try:
        # 1. Get Total VRAM via PowerShell for the specific adapter
        ps_total_cmd = f'powershell -Command "& {{ \\$gpus = @(Get-CimInstance Win32_VideoController); if (\\$gpus.Count -gt {device_index}) {{ \\$gpus[{device_index}].AdapterRam }} else {{ 0 }} }}"'
        total_bytes = int(
            subprocess.check_output(ps_total_cmd, shell=True).decode().strip()
        )
        total_gb = total_bytes / (1024**3)

        # 2. Get Used VRAM via PowerShell Performance Counters
        # We try to get the instance that corresponds to the device index, though performance counters
        # are sometimes ordered differently. We'll pick the nth instance.
        ps_used_cmd = (
            f"powershell -Command \"(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples "
            f'| Select-Object -Index {device_index} -ExpandProperty CookedValue"'
        )
        used_bytes = float(
            subprocess.check_output(ps_used_cmd, shell=True).decode().strip()
        )
        used_gb = used_bytes / (1024**3)

        if total_gb > 0:
            return {"total": total_gb, "used": used_gb}
    except Exception:
        pass
    return {"total": 0.0, "used": 0.0}


def find_microphone_index_by_name(name: str) -> Optional[int]:
    """Resolves a microphone name to its current PortAudio index."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and dev["name"] == name:
            return i
    return None


def list_microphones() -> List[Dict]:
    """
    Lists all available audio input devices, filtered to remove virtual/internal noise.
    """
    devices = sd.query_devices()
    input_devices = []
    best_mic_index = find_best_microphone()

    # Keywords that typically indicate internal/virtual devices we want to hide on Linux
    noise_keywords = [
        "monitor",
        "samplerate",
        "null",
        "dmix",
        "dsnoop",
        "softvol",
        "vdata",
        "equalizer",
        "output",
        "ladspa",
    ]

    for i, dev in enumerate(devices):
        name = dev["name"].lower()
        if dev["max_input_channels"] > 0:
            # Filter logic: if any noise keyword is in the name, skip it
            # UNLESS it's the current default or specifically prioritized (like USB)
            is_noise = any(kw in name for kw in noise_keywords)

            if not is_noise or i == best_mic_index:
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

    # Keywords that typically indicate internal/virtual devices we want to avoid
    noise_keywords = ["monitor", "samplerate", "null", "dmix", "dsnoop", "softvol"]

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

    # 1. Try to find a high-priority device that is NOT noise
    for keyword in priority_keywords:
        for i, dev in enumerate(devices):
            name = dev["name"].lower()
            if dev["max_input_channels"] > 0 and keyword in name:
                if not any(nk in name for nk in noise_keywords):
                    return i

    # 2. Fallback to first non-noise input device
    for i, dev in enumerate(devices):
        name = dev["name"].lower()
        if dev["max_input_channels"] > 0:
            if not any(nk in name for nk in noise_keywords):
                return i

    # 3. Last resort: First input device (even if it might be noise)
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            return i

    return None


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
            logging.error(
                "CRITICAL: No microphone detected. Babelfish requires an input device to start."
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


def get_best_gpu_index() -> int:
    """
    Returns the index of the NVIDIA GPU with the most VRAM.
    Defaults to 0 if detection fails.
    """
    if not shutil.which("nvidia-smi"):
        return 0

    try:
        # Get memory.total for all GPUs
        # Format: "4096, 8192"
        output = (
            subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.STDOUT,
            )
            .decode("utf-8")
            .strip()
            .split("\n")
        )

        best_index = 0
        max_vram = -1.0

        for i, line in enumerate(output):
            try:
                vram = float(line.strip())
                if vram > max_vram:
                    max_vram = vram
                    best_index = i
            except ValueError:
                continue

        return best_index

    except Exception:
        return 0


def list_hardware() -> List[Dict]:
    """Lists all supported hardware acceleration devices, including physically detected ones."""
    devices = [{"id": "cpu", "name": "CPU"}]

    # 1. NVIDIA (CUDA)
    # Check physical GPUs first via nvidia-smi regardless of current ORT provider status
    # This ensures users can select CUDA even if currently running in CPU/DML mode
    nvidia_physical = _get_nvidia_gpus()
    if nvidia_physical:
        devices.extend(nvidia_physical)
    elif detect_nvidia():
        # Fallback if nvidia-smi missing but driver components found
        devices.append({"id": "cuda", "name": "NVIDIA GPU"})

    # 2. AMD (ROCm)
    if detect_amd_linux():
        devices.append({"id": "rocm", "name": "AMD GPU (ROCm)"})

    # 3. Apple Metal
    if detect_metal():
        devices.append({"id": "metal", "name": "Apple Metal"})

    # 4. Windows DirectML / Intel OpenVINO
    if sys.platform == "win32":
        gpu_names = get_windows_gpu_names()
        for i, name in enumerate(gpu_names):
            devices.append({"id": f"dml:{i}", "name": f"{name} (DirectML)"})

    # Deduplicate by ID
    seen_ids = set()
    unique_devices = []
    for d in devices:
        if d["id"] not in seen_ids:
            unique_devices.append(d)
            seen_ids.add(d["id"])

    return unique_devices
