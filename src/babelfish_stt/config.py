from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class InputStrategy(str, Enum):
    DIRECT = "direct"
    CLIPBOARD = "clipboard"
    NATIVE = "native"
    HYBRID = "hybrid"


class HardwareConfig(BaseModel):
    device: str = "auto"
    auto_detect: bool = True
    microphone_name: Optional[str] = None
    onnx_model_dir: Optional[str] = None
    onnx_execution_provider: Optional[str] = None
    quantization: Optional[str] = (
        None  # None means auto/highest for GPU, default int8 for CPU in engine
    )

    # Runtime Status Fields (Populated by Engine)
    active_device: Optional[str] = None
    active_device_name: Optional[str] = None
    vram_total_gb: float = 0.0
    vram_used_baseline_gb: float = 0.0
    vram_used_model_gb: float = 0.0


class PerformanceProfile(BaseModel):
    ghost_throttle_ms: int = 100
    ghost_window_s: float = 2.5
    min_padding_s: float = 2.0
    tier: str = "auto"


class PipelineConfig(BaseModel):
    silence_threshold_ms: int = 400
    pre_roll_ms: int = 300
    update_interval_ms: int = 100
    performance: PerformanceProfile = Field(default_factory=PerformanceProfile)


class ShortcutsConfig(BaseModel):
    toggle_listening: str = Field(default="Ctrl+Space", title="Toggle Listening")
    force_listen: str = "Ctrl+Shift+L"


class ActivationDetectionConfig(BaseModel):
    icon_only: bool = False
    overlay_mode: bool = False


class TranscriptionWindowConfig(BaseModel):
    always_on_top: bool = True


class SystemInputConfig(BaseModel):
    enabled: bool = False
    type_ghost: bool = False
    strategy: InputStrategy = InputStrategy.CLIPBOARD


class VoiceConfig(BaseModel):
    wakeword: Optional[str] = None
    stop_wakeword: Optional[str] = None
    wakeword_sensitivity: float = 0.5
    stop_wakeword_sensitivity: float = 0.5
    stop_words: List[str] = Field(default_factory=list)


class UIConfig(BaseModel):
    verbose: bool = False
    show_timestamps: bool = True
    notifications: bool = True
    shortcuts: ShortcutsConfig = Field(default_factory=ShortcutsConfig)
    activation_detection: ActivationDetectionConfig = Field(
        default_factory=ActivationDetectionConfig
    )
    transcription_window: TranscriptionWindowConfig = Field(
        default_factory=TranscriptionWindowConfig
    )


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8123


class CacheConfig(BaseModel):
    cache_dir: Optional[str] = None


class BabelfishConfig(BaseModel):
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    system_input: SystemInputConfig = Field(default_factory=SystemInputConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
