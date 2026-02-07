import os
import json
import logging
import tempfile
from pathlib import Path
from babelfish_stt.config import BabelfishConfig

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self.load()

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
