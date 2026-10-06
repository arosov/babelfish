# /// script
# dependencies = [
#   "websockets",
#   "huggingface-hub",
# ]
# ///

"""Babelfish environment bootstrap.

Owned by babelfish — see docs/adr/0006-babelfish-owns-its-bootstrap.md.
The bootstrap is the single owner of environment provisioning: hardware
detection, `uv sync` with the right ORT extra, model provisioning, and
DLL-path setup for the ONNX Runtime execution provider.

Two modes of the same logic, selected by environment:

- **Driven mode** (`VOGON_APP_DATA_DIR` set, as set by VogonPoet): stay a
  status WebSocket on port 8123, write the PID file, and finally launch
  `babelfish --server --port 8123`, emitting the stdout markers the Kotlin
  backend scrapes (`BOOTSTRAP SERVER STARTED`, `Launching Babelfish`, and
  downstream `SERVER: WebSockets running on`) and the status shapes
  `{"type":"status","message":…,"vad_state":"bootstrapping"}`.
- **Standalone mode** (those variables absent): detect hardware → sync the
  right ORT extra → provision the Parakeet model if not cached → build the
  DLL env → foreground `uv run --no-sync babelfish <passthrough args>`, all
  logging to stdout/stderr. No server, no WebSocket bootstrap phase.

Both modes share: `HardwareDetector.get_best_mode()`, the `.last_hw_mode`
marker plus `uv sync --extra <extra> --reinstall-package <ort-flavor>`
self-heal (this heals mixed ORT wheel installs), `verify_ort_flavor` — a
live check that the installed onnxruntime actually exposes the mode's
execution provider, which triggers the sync even on a matching marker
(H1) and only records the marker once the intended provider imports (H2)
—, model provisioning from `istupakov/parakeet-tdt-0.6b-v3-onnx`, and the
DLL injection. The launcher scripts only resolve uv, seed the shared
cache variables, and delegate.
"""

import asyncio
import logging
import sys
import os
import subprocess
import shutil
import json
import ctypes
import ctypes.util
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import websockets

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# --- Configuration ---
PORT = 8123

# Log UV cache for debugging
uv_cache = os.environ.get("UV_CACHE_DIR", "System Default")
uv_python = os.environ.get("UV_PYTHON_INSTALL_DIR", "System Default")
logger.info(f"Active UV Cache: {uv_cache}")
logger.info(f"Active UV Python Install Dir: {uv_python}")

# Multilingual Parakeet-TDT v3 (25 languages)
MODEL_REPO = "istupakov/parakeet-tdt-0.6b-v3-onnx"
MODEL_DIR_NAME = "nemo-parakeet-tdt-0.6b-v3"

# This script lives in the babelfish checkout: its parent is the project root.
BUNDLE_DIR = Path(__file__).resolve().parent.parent

# ORT flavor per hardware mode: (package, provider that must be available).
# Every flavor wheel installs the same top-level `onnxruntime/` package, so a
# stale wheel can shadow the intended one and silently degrade to CPU. The
# marker alone can't catch that (out-of-band venv mutations persist), so
# `verify_ort_flavor` re-checks the live interpreter on every launch.
# Providers are listed statically in the pyd — no DLL injection needed.
ORT_FLAVOR: Dict[str, tuple] = {
    "cpu": ("onnxruntime", None),
    "nvidia_win": ("onnxruntime-gpu", "CUDAExecutionProvider"),
    "nvidia_linux": ("onnxruntime-gpu", "CUDAExecutionProvider"),
    "intel_linux": ("onnxruntime-openvino", "OpenVINOExecutionProvider"),
    "windows_gpu": ("onnxruntime-directml", "DmlExecutionProvider"),
    "metal": ("onnxruntime", None),
}

UV_CMD = os.environ.get("UV_CMD", "uv")


def verify_ort_flavor(hw_mode: str) -> Tuple[bool, List[str]]:
    """Check the live venv's ORT against the flavor the hardware mode needs.

    Runs `uv run --no-sync python` and prints the installed onnxruntime
    version plus `get_available_providers()`. Only spawns `uv run
    --no-sync`, which does not touch installed packages — safe even while
    an old babelfish instance still holds `babelfish.exe`.
    Returns (ok, providers); ok means the required provider (if any) is
    present. A missing provider means some other flavor wheel currently
    owns the shared `onnxruntime/` package (shadow install).
    """
    package, required_provider = ORT_FLAVOR.get(hw_mode, ("onnxruntime", None))
    try:
        result = subprocess.run(
            [
                UV_CMD,
                "run",
                "--no-sync",
                "python",
                "-c",
                "import onnxruntime; "
                "print(onnxruntime.__version__); "
                "print('|'.join(onnxruntime.get_available_providers()))",
            ],
            cwd=BUNDLE_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as e:
        logger.warning(f"ORT flavor verification could not run: {e}")
        return False, []

    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        reason = stderr[-1] if stderr else f"exit code {result.returncode}"
        logger.warning(f"ORT flavor verification failed to import: {reason}")
        return False, []

    lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()]
    version = lines[0] if lines else "unknown"
    providers = lines[1].split("|") if len(lines) > 1 else []
    if required_provider and required_provider not in providers:
        logger.warning(
            f"ORT flavor mismatch for {hw_mode}: {package} needs "
            f"{required_provider}, but available providers are {providers} "
            f"(installed onnxruntime {version}). Likely a shadowed install."
        )
        return False, providers
    return True, providers

# Driven mode is signaled by the same env contract the Kotlin side uses for
# config/data locations. Setting VOGON_APP_DATA_DIR opts into the
# status-WebSocket + server launch flow described above.
DRIVEN = bool(os.environ.get("VOGON_APP_DATA_DIR"))

# --- Windows DXGI Structures for in-process GPU detection ---
if sys.platform == "win32":

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_uint8 * 8),
        ]

        def __init__(self, guid_str):
            import uuid

            g = uuid.UUID(guid_str)
            self.Data1 = g.time_low
            self.Data2 = g.time_mid
            self.Data3 = g.time_hi_version
            self.Data4 = (ctypes.c_uint8 * 8)(*g.bytes[8:])

    class DXGI_ADAPTER_DESC1(ctypes.Structure):
        _fields_ = [
            ("Description", ctypes.c_wchar * 128),
            ("VendorId", ctypes.c_uint32),
            ("DeviceId", ctypes.c_uint32),
            ("SubSysId", ctypes.c_uint32),
            ("Revision", ctypes.c_uint32),
            ("DedicatedVideoMemory", ctypes.c_size_t),
            ("DedicatedSystemMemory", ctypes.c_size_t),
            ("SharedSystemMemory", ctypes.c_size_t),
            ("AdapterLuidLow", ctypes.c_uint32),
            ("AdapterLuidHigh", ctypes.c_int32),
            ("Flags", ctypes.c_uint32),
        ]


def _read_config_device() -> str:
    """Reads `hardware.device` from the babelfish config, if one exists.

    In driven mode only `<VOGON_APP_DATA_DIR>/babelfish.config.json` is
    considered (matching ConfigManager); standalone also checks the project
    root, where ConfigManager looks by default.
    """
    candidates: List[Path] = []
    app_data_dir = os.environ.get("VOGON_APP_DATA_DIR")
    if app_data_dir:
        candidates.append(Path(app_data_dir) / "babelfish.config.json")
    if not app_data_dir:
        candidates.append(BUNDLE_DIR / "babelfish.config.json")

    for config_path in candidates:
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                device = data.get("hardware", {}).get("device", "auto")
                if device:
                    return str(device)
            except Exception:
                pass
    return "auto"


def _platform_default_device() -> str:
    """The concrete backend a fresh/legacy config starts on (ADR 0007).

    Windows defaults to DirectML; Linux defaults to CUDA when an NVIDIA
    driver is present, else CPU. Decided at config creation — never "auto".
    """
    if sys.platform == "win32":
        return "dml"
    if sys.platform == "linux":
        return "cuda" if HardwareDetector.detect_nvidia() else "cpu"
    return "cpu"


class HardwareDetector:
    @staticmethod
    def detect_nvidia() -> bool:
        """Detects NVIDIA GPU presence by checking for libcuda/nvcuda libraries."""
        lib_name = "nvcuda.dll" if sys.platform == "win32" else "libcuda.so.1"
        try:
            # 1. Try direct loading
            try:
                ctypes.CDLL(lib_name)
                return True
            except Exception:
                pass

            # 2. Try finding via util
            found_path = ctypes.util.find_library(lib_name)
            if found_path:
                try:
                    ctypes.CDLL(found_path)
                    return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    @staticmethod
    def detect_metal() -> bool:
        """Detects Apple Silicon / Metal support."""
        if sys.platform != "darwin":
            return False
        return os.path.exists("/System/Library/Frameworks/Metal.framework")

    @staticmethod
    def get_all_gpus() -> List[str]:
        """Retrieves a list of all detected GPU names using in-process DXGI or WMI fallback."""
        gpus = []
        try:
            if sys.platform == "win32":
                # 1. Prefer DXGI for consistency with the backend
                try:
                    dxgi = ctypes.windll.dxgi
                    factory_iid = GUID("{7b7166ec-21c7-44ae-b21a-c9ae321ae369}")
                    p_factory = ctypes.c_void_p()
                    if (
                        dxgi.CreateDXGIFactory1(
                            ctypes.byref(factory_iid), ctypes.byref(p_factory)
                        )
                        == 0
                    ):

                        def get_func(obj_ptr, index, argtypes):
                            vtable = ctypes.cast(
                                obj_ptr, ctypes.POINTER(ctypes.c_void_p)
                            )[0]
                            func_ptr = ctypes.cast(
                                vtable, ctypes.POINTER(ctypes.c_void_p)
                            )[index]
                            return ctypes.WINFUNCTYPE(
                                ctypes.c_long, ctypes.c_void_p, *argtypes
                            )(func_ptr)

                        for i in range(16):
                            p_adapter = ctypes.c_void_p()
                            # EnumAdapters1 index 12
                            if (
                                get_func(
                                    p_factory, 12, [ctypes.c_uint32, ctypes.c_void_p]
                                )(p_factory, i, ctypes.byref(p_adapter))
                                != 0
                            ):
                                break

                            desc = DXGI_ADAPTER_DESC1()
                            # GetDesc1 index 10
                            if (
                                get_func(p_adapter, 10, [ctypes.c_void_p])(
                                    p_adapter, ctypes.byref(desc)
                                )
                                == 0
                            ):
                                # Filter out software renderers (Microsoft Basic Render Driver)
                                # DXGI_ADAPTER_FLAG_SOFTWARE = 2
                                if not (desc.Flags & 2):
                                    name = desc.Description.strip()
                                    if name:
                                        gpus.append(name)

                            get_func(p_adapter, 2, [])(p_adapter)  # Release
                        get_func(p_factory, 2, [])(p_factory)  # Release
                except Exception:
                    pass

                if gpus:
                    return list(dict.fromkeys(gpus))

                # Fallback to powershell
                out = (
                    subprocess.check_output(
                        [
                            "powershell",
                            "-Command",
                            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
                        ],
                        stderr=subprocess.DEVNULL,
                    )
                    .decode()
                    .strip()
                    .split("\n")
                )
                for line in out:
                    name = line.strip()
                    if name:
                        gpus.append(name)
            elif sys.platform == "linux":
                if shutil.which("lspci"):
                    # Force English output for lspci
                    env = os.environ.copy()
                    env["LC_ALL"] = "C"
                    out = subprocess.check_output(["lspci"], env=env).decode().lower()
                    for line in out.split("\n"):
                        if "vga" in line or "3d controller" in line:
                            if "nvidia" in line:
                                gpus.append("NVIDIA GPU")
                            elif "amd" in line or "ati" in line:
                                gpus.append("AMD GPU")
                            elif "intel" in line:
                                gpus.append("Intel Graphics")
        except Exception:
            pass
        return list(dict.fromkeys(gpus))

    def get_best_mode(self) -> Dict[str, str]:
        detected_caps = []
        if self.detect_nvidia():
            detected_caps.append("NVIDIA")
        if self.detect_metal():
            detected_caps.append("Apple Metal")

        all_gpu_names = self.get_all_gpus()
        logger.info(f"Hardware Detection: Caps={detected_caps}, GPUs={all_gpu_names}")

        # `hardware.device` is the source of truth (ADR 0007); detection only
        # gates the Linux CUDA flavor. Legacy values ('', 'auto', rocm*) map
        # to the platform default — the config file itself is NOT rewritten
        # here (runtime config_manager migration owns that).
        config_device = _read_config_device()
        if config_device in ("", "auto") or config_device.startswith("rocm"):
            default = _platform_default_device()
            logger.info(f"Migrating legacy device '{config_device}' → '{default}'")
            config_device = default

        # NVIDIA presence: driver libraries, or a GPU name from enumeration.
        nvidia_present = "NVIDIA" in detected_caps or any(
            "nvidia" in g.lower() for g in all_gpu_names
        )

        # Smart Mac Detection (device-independent; macOS is low priority)
        if "Apple Metal" in detected_caps:
            import platform

            arch = platform.machine().lower()
            if "arm" in arch or "aarch64" in arch:
                if config_device == "cpu":
                    logger.info("Apple Silicon detected but device is 'cpu'. Using CPU.")
                    return {"hw_mode": "cpu", "extra": "cpu", "desc": "Apple Silicon (CPU mode)"}
                # Apple Silicon -> CoreML Capable
                return {
                    "hw_mode": "metal",
                    "extra": "cpu",
                    "desc": "Apple Silicon (CoreML capable)",
                }
            else:
                # Intel Mac -> Prefer CPU for stability unless forced
                return {
                    "hw_mode": "cpu",
                    "extra": "cpu",
                    "desc": "Intel Mac (CPU Mode)",
                }

        if sys.platform == "win32":
            # Windows is DirectML-first: the windows-gpu wheel is small and
            # works on every GPU vendor. CUDA is an explicit opt-in via
            # hardware.device ("cuda"/"cuda:N") and syncs nvidia-win on demand.
            if config_device.startswith("cuda"):
                if not nvidia_present:
                    logger.warning(
                        f"hardware.device '{config_device}' requests CUDA but no "
                        "NVIDIA GPU was detected; honoring the request anyway."
                    )
                logger.info(f"Device {config_device}: using nvidia-win extra.")
                return {
                    "hw_mode": "nvidia_win",
                    "extra": "nvidia-win",
                    "desc": "NVIDIA GPU (CUDA)",
                }
            return {
                "hw_mode": "windows_gpu",
                "extra": "windows-gpu",
                "desc": "DirectML",
            }

        if sys.platform == "linux":
            if config_device.startswith("cuda"):
                if not nvidia_present:
                    logger.warning(
                        f"hardware.device '{config_device}' requests CUDA but no "
                        "NVIDIA GPU was detected; syncing the CPU flavor — the "
                        "runtime will degrade to CPU."
                    )
                    return {
                        "hw_mode": "cpu",
                        "extra": "cpu",
                        "desc": "CPU (CUDA requested, no NVIDIA driver)",
                    }
                logger.info("NVIDIA GPU detected. Using nvidia-linux extra.")
                return {
                    "hw_mode": "nvidia_linux",
                    "extra": "nvidia-linux",
                    "desc": "NVIDIA GPU",
                }
            if config_device.startswith("dml"):
                logger.warning(
                    f"Device '{config_device}' (DirectML) is invalid on Linux; using CPU."
                )
                return {"hw_mode": "cpu", "extra": "cpu", "desc": "CPU"}
            # 'cpu' and anything else. intel-linux is a manual opt-in extra
            # and is never selected here.
            logger.info(f"Device {config_device}: using cpu extra.")
            return {"hw_mode": "cpu", "extra": "cpu", "desc": "CPU"}

        return {"hw_mode": "cpu", "extra": "cpu", "desc": "CPU"}


class EnvironmentManager:
    def __init__(self, babelfish_dir: Path):
        self.babelfish_dir = babelfish_dir
        # Use cache directory for runtime artifacts
        self.cache_dir = Path(
            os.environ.get("VOGON_APP_CACHE_DIR", str(babelfish_dir / ".cache"))
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.marker_file = self.cache_dir / ".last_hw_mode"
        self.d3d12info_dir = self.cache_dir / "d3d12info"

        # One-time cleanup of legacy d3d12info binary artifacts
        if self.d3d12info_dir.exists():
            try:
                shutil.rmtree(self.d3d12info_dir)
            except Exception:
                pass

    def check_marker(self, hw_mode: str) -> bool:
        if not (self.babelfish_dir / "uv.lock").exists():
            return False
        if self.marker_file.exists():
            return self.marker_file.read_text().strip() == hw_mode
        return False

    def write_marker(self, hw_mode: str):
        self.marker_file.write_text(hw_mode)

    async def provision_model(
        self,
        repo_id: str,
        dest_dir: Path,
        allow_patterns: List[str],
        status_callback=None,
    ):
        if dest_dir.exists() and any(dest_dir.glob("*.onnx")):
            return

        from huggingface_hub import snapshot_download

        if status_callback:
            message = f"Provisioning model from {repo_id}..."
            if asyncio.iscoroutinefunction(status_callback):
                await status_callback(message)
            else:
                status_callback(message)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: snapshot_download(
                repo_id=repo_id, local_dir=str(dest_dir), allow_patterns=allow_patterns
            ),
        )

    def get_env_with_dll_injection(self, hw_mode: str) -> Dict[str, str]:
        """Prepends the ONNX Runtime capi dir and the pip NVIDIA DLL dirs to
        the child's PATH (Windows) or LD_LIBRARY_PATH (Linux).

        Source of truth for the in-process safety net in
        `babelfish_stt.hardware.register_nvidia_dll_dirs`; keep the two in
        agreement.
        """
        env = os.environ.copy()
        # Clear VIRTUAL_ENV so uv uses the project .venv instead of bootstrap env
        env.pop("VIRTUAL_ENV", None)
        if hw_mode == "cpu":
            return env

        libs_paths = []
        # ORT CAPI
        if sys.platform == "win32":
            capi = list(
                self.babelfish_dir.glob(".venv/Lib/site-packages/onnxruntime/capi")
            )
        else:
            capi = list(
                self.babelfish_dir.glob(
                    ".venv/lib/python*/site-packages/onnxruntime/capi"
                )
            )

        if capi:
            libs_paths.append(str(capi[0].resolve()))

        # NVIDIA libraries
        nv_glob = (
            ".venv/Lib/site-packages/nvidia"
            if sys.platform == "win32"
            else ".venv/lib/python*/site-packages/nvidia"
        )
        nv_roots = list(self.babelfish_dir.glob(nv_glob))
        if nv_roots:
            ext = "*.dll" if sys.platform == "win32" else "*.so*"
            for path in nv_roots[0].rglob(ext):
                parent = str(path.parent.resolve())
                if parent not in libs_paths:
                    libs_paths.append(parent)

        if libs_paths:
            if sys.platform == "win32":
                current = env.get("PATH", "")
                env["PATH"] = ";".join(libs_paths) + ";" + current
            else:
                current = env.get("LD_LIBRARY_PATH", "")
                env["LD_LIBRARY_PATH"] = ":".join(libs_paths) + (
                    ":" + current if current else ""
                )

        return env


async def ensure_ort_env(
    env_manager: EnvironmentManager,
    hw_mode: str,
    extra: str,
    run_sync,
    status,
) -> bool:
    """Marker + live-verification gate around `uv sync` (closes H1 + H2).

    - Marker matches but the live ORT flavor check fails (out-of-band venv
      mutation left a stale shadow wheel) -> run the sync anyway, self-heal.
    - After a successful sync, verify again and only write the marker when
      the intended provider is actually importable — so a same-sync
      ordering race (uv's install order deciding the pyd owner) can't
      record a broken environment as good.

    `run_sync(cmd)` executes one `uv sync` and returns its exit code;
    `status(message)` reports progress (WebSocket in driven mode, stderr in
    standalone). Returns True when the environment is verified good.
    """
    package, required_provider = ORT_FLAVOR.get(hw_mode, ("onnxruntime", None))

    if env_manager.check_marker(hw_mode):
        ok, _providers = verify_ort_flavor(hw_mode)
        if ok:
            await status("Environment matches hardware, skipping sync.")
            return True
        await status(
            "Environment marker matches, but ORT flavor verification "
            f"failed; re-syncing to self-heal ({package})..."
        )

    for attempt in (1, 2):
        cmd = [UV_CMD, "sync", "--extra", extra, "--reinstall-package", package]
        if attempt == 2:
            await status(f"Retrying dependency sync for {hw_mode}...")
        ret = await run_sync(cmd)
        if ret != 0:
            await status("Sync failed!")
            return False
        ok, providers = verify_ort_flavor(hw_mode)
        if ok:
            env_manager.write_marker(hw_mode)
            return True
        await status(
            f"ORT flavor verification failed after sync (providers: "
            f"{providers or 'import failed'})..."
        )

    await status(
        f"ORT flavor verification failed: {hw_mode} needs "
        f"{required_provider or 'a working onnxruntime import'}; two sync "
        "attempts did not restore it. Not launching."
    )
    return False


class BootstrapServer:
    """Driven-mode only: a short-lived WebSocket on `PORT` streaming
    provisioning status to the frontend, closed again before the server
    launches on the same port."""

    def __init__(self, models_dir: Optional[Path] = None):
        self.websocket = None
        # Default mirrors the standalone flow: explicit dir if VogonPoet
        # passed one, else the shared cache, else repo-local models/.
        self.models_dir = (
            models_dir or _resolve_models_dir().parent
        )
        self.detector = HardwareDetector()
        self.env_manager = EnvironmentManager(BUNDLE_DIR)
        self.completion_future = None

    def set_completion_future(self, future):
        self.completion_future = future

    async def handle_connection(self, websocket):
        if self.websocket:
            await websocket.close(1008, "Only one connection allowed")
            return
        self.websocket = websocket
        try:
            await self.run_bootstrap()
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}")
            await self.send_update(f"Error: {e}")
        finally:
            self.websocket = None

    async def send_update(self, message: str, vad_state: str = "bootstrapping"):
        if not self.websocket:
            return
        data = json.dumps(
            {"type": "status", "message": message, "vad_state": vad_state}
        )
        try:
            await self.websocket.send(data)
        except Exception:
            pass

    async def run_command(self, cmd, cwd=None, env=None):
        if env is None:
            env = os.environ.copy()
        # Remove VIRTUAL_ENV to ensure the child uv process targets the project .venv correctly
        env.pop("VIRTUAL_ENV", None)

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env
        )
        if process.stdout:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode().strip()
                if line_str:
                    logger.info(f"CMD: {line_str}")
                    await self.send_update(line_str)
        return await process.wait()

    async def _sync_dependencies(self, hw_mode: str, extra: str) -> bool:
        """Marker + verification gate (see ensure_ort_env), driven mode.

        Streams sync output to the status socket, returns False (without
        launching) when the environment cannot be verified good.
        """

        async def run_sync(cmd):
            return await self.run_command(cmd, cwd=BUNDLE_DIR)

        return await ensure_ort_env(
            self.env_manager, hw_mode, extra, run_sync, self.send_update
        )

    async def run_bootstrap(self):
        await self.send_update("Detecting Hardware...")
        hw = self.detector.get_best_mode()
        hw_mode = hw["hw_mode"]
        extra = hw["extra"]

        await self.send_update(f"Hardware: {hw['desc']}. Target mode: {hw_mode}")

        # Model Provisioning
        self.models_dir.mkdir(parents=True, exist_ok=True)
        model_dest = self.models_dir / MODEL_DIR_NAME
        patterns = ["*.onnx", "*.onnx.data", "config.json", "*.txt"]
        if hw_mode != "cpu":
            patterns = [
                "encoder-model.onnx",
                "decoder_joint-model.onnx",
                "encoder-model.onnx.data",
                "config.json",
                "vocab.txt",
            ]

        await self.env_manager.provision_model(
            MODEL_REPO, model_dest, patterns, self.send_update
        )

        # Dependency Sync
        if not await self._sync_dependencies(hw_mode, extra):
            return

        await self.send_update("Starting Babelfish...")
        launch_args, launch_env = HardwareLaunchPlan(self.env_manager).build(hw_mode)
        await asyncio.sleep(0.5)
        if self.websocket:
            await self.websocket.close()

        # Signal completion to the main loop
        if self.completion_future and not self.completion_future.done():
            self.completion_future.set_result((launch_args, launch_env))

def _split_args(argv: List[str]):
    """Splits bootstrap args: consumes `--models-dir [X]` (VogonPoet's own
    models location) and returns the remainder as babelfish CLI passthrough
    args for standalone mode."""
    models_dir = None
    passthrough: List[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--models-dir" and i + 1 < len(argv):
            models_dir = argv[i + 1]
            i += 2
        elif arg.startswith("--models-dir="):
            models_dir = arg.split("=", 1)[1]
            i += 1
        else:
            passthrough.append(arg)
            i += 1
    return models_dir, passthrough


def _read_config_cache_dir() -> Optional[str]:
    """Reads `cache.cache_dir` from the babelfish config, mirroring
    ConfigManager's path resolution (driven: VOGON_APP_DATA_DIR; standalone:
    project root). Used to pick the same model directory the engine resolves."""
    candidates: List[Path] = []
    app_data_dir = os.environ.get("VOGON_APP_DATA_DIR")
    if app_data_dir:
        candidates.append(Path(app_data_dir) / "babelfish.config.json")
    if not app_data_dir:
        candidates.append(BUNDLE_DIR / "babelfish.config.json")

    for config_path in candidates:
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                cache_dir = data.get("cache", {}).get("cache_dir")
                if cache_dir:
                    return str(cache_dir)
            except Exception:
                pass
    return None


def _resolve_models_dir(explicit: Optional[str] = None) -> Path:
    """Model destination matching engine.resolve_model_path's search order:
    explicit --models-dir > config cache.cache_dir > VOGON_APP_CACHE_DIR >
    repo-local models/."""
    if explicit:
        return Path(explicit) / MODEL_DIR_NAME
    base = _read_config_cache_dir() or os.environ.get("VOGON_APP_CACHE_DIR") or BUNDLE_DIR
    return Path(base) / "models" / MODEL_DIR_NAME


class HardwareLaunchPlan:
    """Resolves the final `babelfish` launch command and environment.

    Shared by driven mode (invoked after the status socket closes, so the
    engine can rebind the port) and by standalone mode (invoked directly,
    with no WebSocket phase). The `--no-sync` + `--reinstall-package`
    pair above is where CPU↔GPU switching self-heals: the hw-mode marker
    in the shared cache decides when to re-sync, and the ORT-flavor
    reinstall pins out stale wheels from mixed installs.
    """

    def __init__(self, env_manager: EnvironmentManager):
        self.env_manager = env_manager

    def build(self, hw_mode: str, extra_args: Optional[List[str]] = None):
        env = self.env_manager.get_env_with_dll_injection(hw_mode)
        # UTF-8 stdio for the child regardless of pipe or console codepage:
        # locale codecs (cp1252 'charmap') crash on any non-cp1252 character
        # a transcript contains. main.py reconfigures its streams too; this
        # pins the mode for paths that print before that reconfigure runs.
        env["PYTHONUTF8"] = "1"
        args = [UV_CMD, "run", "--no-sync", "babelfish"]
        if DRIVEN:
            args += ["--server", "--port", str(PORT)]
        args += list(extra_args or [])

        # Force CPU mode at RUNTIME (not SYNC time)
        force_cpu = str(os.environ.get("VOGON_FORCE_CPU", "")).lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if not force_cpu and _read_config_device() == "cpu":
            force_cpu = True
        if force_cpu or hw_mode == "cpu":
            args.append("--cpu")

        return args, env


def run_standalone(argv: List[str]) -> None:
    """Provision the environment, then exec the babelfish CLI in the
    foreground with the same stdout/stderr — no WebSocket bootstrap phase."""
    models_dir_arg, passthrough_args = _split_args(argv)

    print("Bootstrap: detecting hardware...", file=sys.stderr)
    hw = HardwareDetector().get_best_mode()
    hw_mode = hw["hw_mode"]
    extra = hw["extra"]
    print(f"Bootstrap: hardware: {hw['desc']} (mode: {hw_mode})", file=sys.stderr)

    env_manager = EnvironmentManager(BUNDLE_DIR)

    # Model Provisioning
    model_dest = _resolve_models_dir(models_dir_arg)
    model_dest.parent.mkdir(parents=True, exist_ok=True)
    patterns = ["*.onnx", "*.onnx.data", "config.json", "*.txt"]
    if hw_mode != "cpu":
        patterns = [
            "encoder-model.onnx",
            "decoder_joint-model.onnx",
            "encoder-model.onnx.data",
            "config.json",
            "vocab.txt",
        ]

    if not (model_dest.exists() and any(model_dest.glob("*.onnx"))):
        print(f"Bootstrap: provisioning model from {MODEL_REPO}...", file=sys.stderr)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                env_manager.provision_model(MODEL_REPO, model_dest, patterns)
            )
        finally:
            loop.close()
    else:
        print(f"Bootstrap: model already provisioned at {model_dest}", file=sys.stderr)

    # Dependency Sync (self-heals mixed ORT installs via --reinstall-package,
    # gated on a live ORT flavor verification — see ensure_ort_env)
    async def _run_sync(cmd) -> int:
        return await asyncio.to_thread(subprocess.call, cmd, cwd=BUNDLE_DIR)

    async def _status(message: str) -> None:
        print(f"Bootstrap: {message}", file=sys.stderr)

    try:
        ok = asyncio.run(
            ensure_ort_env(env_manager, hw_mode, extra, _run_sync, _status)
        )
    except Exception as e:
        print(f"Bootstrap: dependency sync error: {e}", file=sys.stderr)
        ok = False
    if not ok:
        sys.exit(1)

    # Build the launch command (adds --cpu when forced or hw-locked to CPU,
    # and drops --server/--port: standalone is CLI passthrough)
    args, launch_env = HardwareLaunchPlan(env_manager).build(hw_mode, passthrough_args)

    print(f"Bootstrap: launching Babelfish ({' '.join(args[1:])})...", file=sys.stderr)
    os.chdir(BUNDLE_DIR)
    if sys.platform == "win32":
        # subprocess.call is blocking, so the script waits for Babelfish to exit
        ret = subprocess.call(args, env=launch_env)
        sys.exit(ret)
    else:
        # On Linux/Unix, replace the current process
        os.execvpe(args[0], args, launch_env)


async def run_driven(argv: List[str]):
    models_dir_arg, remaining = _split_args(argv)
    if remaining:
        logger.warning(f"Ignoring unexpected args in driven mode: {remaining}")

    # Write PID file for robust cleanup
    app_data_dir = os.environ.get("VOGON_APP_DATA_DIR")
    if app_data_dir:
        pid_file = Path(app_data_dir) / "babelfish.pid"
        try:
            pid_file.write_text(str(os.getpid()))
        except Exception as e:
            logger.warning(f"Failed to write PID file: {e}")

    models_dir = Path(models_dir_arg) if models_dir_arg else None
    server = BootstrapServer(models_dir)

    # Create a Future to signal completion
    loop = asyncio.get_running_loop()
    completion_future = loop.create_future()
    server.set_completion_future(completion_future)

    async with websockets.serve(server.handle_connection, "127.0.0.1", PORT):
        logger.info(f"BOOTSTRAP SERVER STARTED port={PORT}")
        # Wait for the bootstrap to finish and return the launch command
        launch_args, launch_env = await completion_future

    # Server is now closed, port should be free
    logger.info(f"Bootstrap server stopped. Launching Babelfish on port {PORT}...")

    os.chdir(BUNDLE_DIR)
    if sys.platform == "win32":
        # subprocess.call is blocking, so the script waits for Babelfish to exit
        subprocess.call(launch_args, env=launch_env)
        sys.exit(0)
    else:
        # On Linux/Unix, replace the current process
        os.execvpe(launch_args[0], launch_args, launch_env)


def main():
    if DRIVEN:
        try:
            asyncio.run(run_driven(sys.argv[1:]))
        except KeyboardInterrupt:
            pass
    else:
        run_standalone(sys.argv[1:])


if __name__ == "__main__":
    main()
