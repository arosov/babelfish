import os
import json
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from babelfish_stt.config import BabelfishConfig, HardwareConfig, PipelineConfig, VoiceConfig, UIConfig, ServerConfig
from babelfish_stt.reconfigurable import Reconfigurable

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
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
                component.reconfigure(self.config.server)
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
            return BabelfishConfig.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to load config from {self.config_path}: {e}. Using defaults.")
            return BabelfishConfig()

    def save(self):
        """
        Atomic save using a temporary file.
        """
        data = self.config.model_dump()
        
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic save: write to temp file then rename
        fd, temp_path = tempfile.mkstemp(
            dir=self.config_path.parent, 
            prefix=self.config_path.name + ".tmp"
        )
        try:
            with os.fdopen(fd, 'w') as f:
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
