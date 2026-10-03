import os
import sys
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, model_validator


def platform_default_device() -> str:
    """The concrete backend a fresh config starts on (ADR 0007).

    Windows defaults to DirectML (small wheel, works on every GPU vendor);
    Linux defaults to CUDA when an NVIDIA driver is present, else CPU.
    Decided at config creation — never at runtime, and never "auto".
    """
    if sys.platform == "win32":
        return "dml"
    if sys.platform == "linux":
        from babelfish_stt.hardware import detect_nvidia

        return "cuda" if detect_nvidia() else "cpu"
    return "cpu"


class InputStrategy(str, Enum):
    DIRECT = "direct"
    CLIPBOARD = "clipboard"
    NATIVE = "native"
    HYBRID = "hybrid"


class SeparatorPolicy(str, Enum):
    TRAILING = "trailing"
    LEADING = "leading"
    NEVER = "never"


class HardwareConfig(BaseModel):
    # A concrete backend id: "dml"/"dml:N", "cuda"/"cuda:N", "cpu", or a
    # specific id from `list_hardware` (never "auto" — ADR 0007).
    device: str = Field(default_factory=platform_default_device)
    microphone_name: Optional[str] = None
    quantization: Optional[str] = (
        None  # None means full precision; an explicit "int8" is still honoured
    )


class HardwareStatus(BaseModel):
    active_device: Optional[str] = None
    active_device_name: Optional[str] = None
    vram_total_gb: float = 0.0
    vram_used_baseline_gb: float = 0.0
    vram_used_model_gb: float = 0.0


class PerformanceProfile(BaseModel):
    ghost_throttle_ms: int = 50
    ghost_window_s: float = 2.5
    # Padding for Ghost submits only. 1.0 keeps the first, short windows
    # text-capable: fully unpadded onset windows often transcribe to ""
    # (observed live: first visible Ghost delayed ~400ms by empty results).
    ghost_padding_s: float = 1.0
    min_padding_s: float = 2.0
    tier: str = "auto"


class PipelineConfig(BaseModel):
    silence_threshold_ms: int = 400
    pre_roll_ms: int = 300
    performance: PerformanceProfile = Field(default_factory=PerformanceProfile)


class ShortcutsConfig(BaseModel):
    toggle_listening: str = Field(default="Ctrl+Space", title="Toggle Listening")
    force_listen: str = Field(default="Left Shift", title="Force Listen")


class ActivationDetectionConfig(BaseModel):
    icon_only: bool = False
    overlay_mode: bool = False


class TranscriptionWindowConfig(BaseModel):
    always_on_top: bool = True


class SystemInputConfig(BaseModel):
    enabled: bool = False
    type_ghost: bool = False
    strategy: InputStrategy = InputStrategy.CLIPBOARD
    separator: SeparatorPolicy = SeparatorPolicy.TRAILING


class VoiceConfig(BaseModel):
    wakeword: Optional[str] = None
    stop_wakeword: Optional[str] = None
    wakeword_sensitivity: float = 0.5
    stop_wakeword_sensitivity: float = 0.5
    stop_words: List[str] = Field(default_factory=list)


class UIConfig(BaseModel):
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

    @model_validator(mode="after")
    def populate_cache_dir(self) -> "CacheConfig":
        """Populate cache_dir from environment if not explicitly set."""
        if self.cache_dir is None:
            self.cache_dir = os.environ.get("VOGON_APP_CACHE_DIR")
        return self


class BabelfishConfig(BaseModel):
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    status: HardwareStatus = Field(default_factory=HardwareStatus)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    system_input: SystemInputConfig = Field(default_factory=SystemInputConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
