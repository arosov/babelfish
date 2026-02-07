import json
import os
import logging
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("babelfish.config")

class ServerConfig(BaseModel):
    model: str
    device: str
    quantization: str  # e.g., "float16", "int8", "int8_float16"
    language: str = "" # Default to auto-detection
    wake_word: Optional[str] = None
    realtime_model_type: str = "tiny"
    auto_type: bool = False
    input_device_index: Optional[int] = None
    enable_realtime: bool = True
    use_main_model_for_realtime: bool = True

class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path

    def load_config(self) -> Optional[ServerConfig]:
        if not os.path.exists(self.config_path):
            return None
        
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                return ServerConfig(**data)
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            return None

    def save_config(self, config: ServerConfig):
        try:
            with open(self.config_path, "w") as f:
                json.dump(config.dict(), f, indent=4)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")
