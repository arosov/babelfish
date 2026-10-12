import os
import sys
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, model_validator


def platform_default_device() -> str:
    """The concrete backend a fresh config starts on (ADR 0007, ADR 0014).

    The default is CPU on every platform, served by the Parakeet Redux
    int4 weights (ADR 0014: a 418 MB first-run download instead of 2.4 GB,
    3.9x faster load, transcripts equivalent to fp32 v3 on the bundled
    fixtures). GPUs are an explicit opt-in — write `hardware.device` in
    the config or pass `babelfish --gpu` — and keep the fp32 v3 weights.
    Decided at config creation — never at runtime, and never "auto".
    """
    return "cpu"


class SeparatorPolicy(str, Enum):
    TRAILING = "trailing"
    LEADING = "leading"
    NEVER = "never"


class HardwareConfig(BaseModel):
    # A concrete backend id: "dml"/"dml:N", "cuda"/"cuda:N", "cpu", or a
    # specific id from `list_hardware` (never "auto" — ADR 0007).
    device: str = Field(default_factory=platform_default_device)
    # Weights-ladder card override (ADR 0014): "v3" forces the fp32 v3
    # card, "redux" forces the int4 card, regardless of device (A/B
    # testing on a GPU machine). None derives the card from the device:
    # cpu -> redux, any GPU backend -> fp32 v3.
    model: Optional[str] = None
    microphone_name: Optional[str] = None
    quantization: Optional[str] = (
        None  # None means full precision; an explicit "int8" is still honoured
    )

    @model_validator(mode="after")
    def _validate_model_card(self) -> "HardwareConfig":
        if self.model not in (None, "v3", "redux"):
            raise ValueError(
                f"hardware.model must be None, 'v3' or 'redux' "
                f"(got {self.model!r})"
            )
        return self


class HardwareStatus(BaseModel):
    active_device: Optional[str] = None
    active_device_name: Optional[str] = None
    vram_total_gb: float = 0.0
    vram_used_baseline_gb: float = 0.0
    vram_used_model_gb: float = 0.0


class PerformanceProfile(BaseModel):
    """Pacing and window fields for the Ghost pass — the calibration
    output type (ADR 0011, reworked by ADR 0013).

    Never user-facing configuration: the startup benchmark computes a
    profile, cached per acceleration backend in the config file's
    `calibration` section and canary-checked every launch, and it is
    applied to the pipeline in memory only. `tier` is the measured tier
    label (informational — logs and the replay capture header); it is
    not an input.
    """

    ghost_throttle_ms: int = 50
    ghost_window_s: float = 2.5
    # Padding for Ghost submits only. 1.0 keeps the first, short windows
    # text-capable: fully unpadded onset windows often transcribe to ""
    # (observed live: first visible Ghost delayed ~400ms by empty results).
    # Applied only while the window audio is short (see
    # pipeline.FIRST_WINDOW_MIN_S) — mature windows are unpadded.
    ghost_padding_s: float = 1.0
    min_padding_s: float = 2.0
    tier: str = "uncalibrated"


# Version of the persisted calibration record format (ADR 0013). Bump on
# any change to what a stored entry means (probe protocol, cell-table
# shape, boundary table): the store is ignored when stale and re-benched,
# and the version rides in the fingerprint so a bump rotates cache keys.
# Bumped to 2 by ADR 0014: fingerprints gained a weights-identity
# component, so stored v1 entries (weights-blind) are ignored once.
CALIBRATION_SCHEMA_VERSION = 2


class CalibrationProfileEntry(BaseModel):
    """One benched calibration profile, persisted under its fingerprint in
    the `calibration` section (ADR 0013).

    The profile fields are the operating point (window, throttle, padding,
    tier label); `operating_cost_ms` is the Ghost cohort cost measured at
    that window; `cells` is the full measured Ghost probe matrix (fixture →
    window → median ms) — kept for the canary's reference and for
    support/diagnostic value; `final_rtfx` is informational.
    """

    ghost_throttle_ms: int
    ghost_window_s: float
    ghost_padding_s: float = 1.0
    min_padding_s: float = 2.0
    tier: str
    operating_cost_ms: float
    final_rtfx: float = 0.0
    cells: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    benched_at: str = ""

    def to_profile(self) -> PerformanceProfile:
        """The in-memory profile this entry hands to the pipeline."""
        return PerformanceProfile(
            ghost_throttle_ms=self.ghost_throttle_ms,
            ghost_window_s=self.ghost_window_s,
            ghost_padding_s=self.ghost_padding_s,
            min_padding_s=self.min_padding_s,
            tier=self.tier,
        )


class CalibrationConfig(BaseModel):
    """The persisted calibration cache (ADR 0013): bench once per
    acceleration backend, keyed by fingerprint, canary-checked every
    launch.

    Deliberately NOT `pipeline.performance` — that key keeps its
    live strip-migration semantics from the ADR 0011 rework; calibration
    output lives in its own top-level section so stale pacing keys are
    still wiped while benched entries survive.
    """

    schema_version: int = CALIBRATION_SCHEMA_VERSION
    profiles: Dict[str, CalibrationProfileEntry] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    silence_threshold_ms: int = 400
    pre_roll_ms: int = 300


class ShortcutsConfig(BaseModel):
    toggle_listening: str = Field(default="Ctrl+Space", title="Toggle Listening")


class ActivationDetectionConfig(BaseModel):
    icon_only: bool = False
    overlay_mode: bool = False


class TranscriptionWindowConfig(BaseModel):
    always_on_top: bool = True


class SystemInputConfig(BaseModel):
    enabled: bool = False
    type_ghost: bool = False
    # Minimum spacing between typed keystrokes into the focused application
    # (milliseconds). 0 is deliberately not offered: unpaced ~50ms applies
    # flood editors and a lost modifier key-up turns backspaces into word
    # deletion (see input_manager.py). Hot-reloaded from the config file.
    typing_throttle_ms: int = 350
    # Injection is always clipboard paste + pynput backspace (ADR 0009); the
    # old "strategy" field is gone. Unknown keys from stale configs (e.g.
    # "strategy": "native", or the removed "force_listen" shortcut) are
    # silently ignored by pydantic's default parse.
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
    # Persisted calibration cache (ADR 0013) — bench output keyed by
    # fingerprint, never a user input.
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)
    system_input: SystemInputConfig = Field(default_factory=SystemInputConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
