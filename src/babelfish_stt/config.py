from typing import List, Optional
from pydantic import BaseModel, Field


class HardwareConfig(BaseModel):
    device: str = "auto"
    vram_limit_gb: Optional[float] = None
    microphone_index: Optional[int] = None


class PipelineConfig(BaseModel):
    double_pass: bool = False
    preset: str = "balanced"
    ghost_preset: str = "fast"
    anchor_preset: str = "solid"
    anchor_trigger_interval_ms: int = 2000
    silence_threshold_ms: int = 700


class ShortcutsConfig(BaseModel):
    toggle_listening: str = "Ctrl+Shift+S"
    force_listen: str = "Ctrl+Shift+L"


class ActivationDetectionConfig(BaseModel):
    icon_only: bool = False
    overlay_mode: bool = False


class VoiceConfig(BaseModel):
    wakeword: Optional[str] = None
    wakeword_sensitivity: float = 0.5
    stop_words: List[str] = Field(default_factory=list)


class UIConfig(BaseModel):
    verbose: bool = False
    show_timestamps: bool = True
    shortcuts: ShortcutsConfig = Field(default_factory=ShortcutsConfig)
    activation_detection: ActivationDetectionConfig = Field(
        default_factory=ActivationDetectionConfig
    )


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8123


class CacheConfig(BaseModel):
    cache_dir: Optional[str] = None


class BabelfishConfig(BaseModel):
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
