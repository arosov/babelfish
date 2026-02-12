import os
import json
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Any, TYPE_CHECKING, Optional
from babelfish_stt.config import (
    BabelfishConfig,
    HardwareConfig,
    PipelineConfig,
    VoiceConfig,
    UIConfig,
    ServerConfig,
)
from babelfish_stt.reconfigurable import Reconfigurable

if TYPE_CHECKING:
    from babelfish_stt.hardware import HardwareManager

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Check for Vogon app data dir environment variable
            app_data_dir = os.environ.get("VOGON_APP_DATA_DIR")
            if app_data_dir:
                config_path = os.path.join(app_data_dir, "babelfish.config.json")
            else:
                config_path = "babelfish.config.json"

        self.config_path = Path(config_path)
        self.config = self.load()
        self._components: List[Reconfigurable] = []

    def register(self, component: Reconfigurable):
        """Register a component to receive configuration updates."""
        if component not in self._components:
            self._components.append(component)
            # Immediately trigger a reconfigure with current config
            self._propagate_to_component(component)

    def _propagate_to_component(self, component: Reconfigurable):
        """Propagate relevant sub-config to a specific component."""
        try:
            # We determine which sub-config to send based on common patterns
            # or we could let components specify. For now, we try to match.
            # Most components care about a specific section.

            # This is a bit heuristic, but effective for our current scale
            # We could also use type hints of the reconfigure method if needed.

            # Map of component types/instances to sections
            from babelfish_stt.vad import SileroVAD
            from babelfish_stt.pipeline import Pipeline, StopWordDetector
            from babelfish_stt.engine import STTEngine
            from babelfish_stt.server import BabelfishServer

            if isinstance(component, SileroVAD):
                component.reconfigure(self.config.voice)
            elif isinstance(component, StopWordDetector):
                component.reconfigure(self.config.voice)
            elif isinstance(component, Pipeline):
                component.reconfigure(self.config.pipeline)
            elif isinstance(component, STTEngine):
                component.reconfigure(self.config.pipeline)
            elif isinstance(component, BabelfishServer):
                component.reconfigure(self.config)
            else:
                # Fallback: send full config if we don't know the specifics
                component.reconfigure(self.config)
        except Exception as e:
            logger.error(f"Failed to propagate config to {component}: {e}")

    def _propagate_all(self):
        """Propagate current config to all registered components."""
        for component in self._components:
            self._propagate_to_component(component)

    def load(self) -> BabelfishConfig:
        if not self.config_path.exists():
            logger.info(f"Config file {self.config_path} not found. Using defaults.")
            return BabelfishConfig()

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)

            # --- Migration: microphone_index -> microphone_name ---
            hardware = data.get("hardware", {})
            if "microphone_index" in hardware and "microphone_name" not in hardware:
                index = hardware.pop("microphone_index")
                try:
                    import sounddevice as sd

                    devices = sd.query_devices()
                    if index is not None and 0 <= index < len(devices):
                        hardware["microphone_name"] = devices[index]["name"]
                        logger.info(
                            f"Migrated microphone index {index} to name '{hardware['microphone_name']}'"
                        )
                except Exception as e:
                    logger.warning(f"Failed to migrate microphone index to name: {e}")

            config = BabelfishConfig.model_validate(data)

            # Ensure consistency: if auto_detect is enabled, device should be "auto"
            if config.hardware.auto_detect:
                config.hardware.device = "auto"

            return config
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                f"Failed to load config from {self.config_path}: {e}. Using defaults."
            )
            return BabelfishConfig()

    def is_valid(self, hw: Optional["HardwareManager"] = None) -> bool:
        """
        Validates the current configuration.
        If HardwareManager is provided, also validates hardware availability.
        """
        if not self.config_path.exists():
            return False

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
            config = BabelfishConfig.model_validate(data)

            # Auto-detect mode is always valid as long as we have hardware manager
            # to perform the detection during engine init.
            if config.hardware.auto_detect:
                return True

            if hw:
                # Validate microphone name
                if config.hardware.microphone_name is not None:
                    valid_names = [m["name"] for m in hw.microphones]
                    if config.hardware.microphone_name not in valid_names:
                        logger.warning(
                            f"Configured microphone '{config.hardware.microphone_name}' not found."
                        )
                        return False

                # Validate GPU availability if set to cuda
                if (
                    config.hardware.device == "cuda"
                    and not hw.gpu_info["cuda_available"]
                ):
                    logger.warning(
                        "Configured for CUDA but no GPU detected. STT Engine will fall back to CPU for this session."
                    )
                    # We return True here to prevent overwriting the user's preferred config.
                    # The STTEngine handles the runtime fallback.
                    return True

            return True
        except Exception as e:
            logger.warning(f"Configuration validation failed: {e}")
            return False

    def generate_optimal_defaults(self, hw: "HardwareManager"):
        """
        Generates and saves optimal defaults based on detected hardware.
        """
        logger.info("Generating optimal default configuration...")

        # Determine device based on priority and VRAM
        device = "cpu"

        if "CUDAExecutionProvider" in hw.available_providers:
            device = "cuda"
            logger.info(
                f"CUDA provider detected. Selecting CUDA mode (VRAM: {hw.gpu_info['vram_gb']:.2f}GB)."
            )
        elif "ROCMExecutionProvider" in hw.available_providers:
            device = "rocm"
            logger.info("ROCm provider detected. Selecting ROCm mode.")
        elif "DmlExecutionProvider" in hw.available_providers:
            device = "dml"
            logger.info("DirectML provider detected. Selecting DML mode.")
        elif "OpenVINOExecutionProvider" in hw.available_providers:
            device = "openvino"
            logger.info("OpenVINO provider detected. Selecting OpenVINO mode.")

        # Find name for best microphone
        best_mic_name = None
        if hw.best_mic_index is not None:
            try:
                import sounddevice as sd

                best_mic_name = sd.query_devices(hw.best_mic_index, "input")["name"]
            except Exception:
                pass

        self.config = BabelfishConfig(
            hardware=HardwareConfig(device=device, microphone_name=best_mic_name),
            pipeline=PipelineConfig(),
        )
        self.save()
        logger.info(f"Optimal defaults saved to {self.config_path}.")

    def save(self):
        """
        Atomic save using a temporary file.
        """
        data = self.config.model_dump()

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic save: write to temp file then rename
        fd, temp_path = tempfile.mkstemp(
            dir=self.config_path.parent, prefix=self.config_path.name + ".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=4)
            os.replace(temp_path, self.config_path)
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def update(self, changes: dict):
        """
        Updates the configuration with the provided changes.
        Performs a deep merge and validates the result.
        """
        current_data = self.config.model_dump()
        merged_data = self._deep_merge(current_data, changes)

        # Protective logic: if auto_detect is enabled, ensure device is 'auto'
        # This prevents UI race conditions where a draft 'cpu' device might be saved
        # alongside an 'auto_detect: true' flag.
        if merged_data.get("hardware", {}).get("auto_detect"):
            merged_data["hardware"]["device"] = "auto"

        # Validate by creating a new model instance
        new_config = BabelfishConfig.model_validate(merged_data)

        # If successful, apply and save
        self.config = new_config
        self.save()
        self._propagate_all()
        logger.info("Configuration updated and saved.")

    @staticmethod
    def _deep_merge(base: dict, update: dict) -> dict:
        """
        Recursively merges update dict into base dict.
        """
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
