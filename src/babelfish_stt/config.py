from typing import List, Optional
from pydantic import BaseModel, Field

class HardwareConfig(BaseModel):
    device: str = "auto"
    vram_limit_gb: Optional[float] = None
    microphone_index: Optional[int] = None

class PipelineConfig(BaseModel):
    double_pass: bool = False
    ghost_preset: str = "fast"
    anchor_preset: str = "solid"

class VoiceConfig(BaseModel):
    wakeword: Optional[str] = None
    wakeword_sensitivity: float = 0.5
    stop_words: List[str] = Field(default_factory=list)

class UIConfig(BaseModel):
    verbose: bool = False
    show_timestamps: bool = True

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8123
    cert_path: Optional[str] = None
    key_path: Optional[str] = None

class BabelfishConfig(BaseModel):
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
