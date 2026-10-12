import onnx_asr
import onnxruntime
import numpy as np
import logging
import os
import threading
import sys
import time
from pathlib import Path
from typing import Any, Optional, List, Dict
from babelfish_stt.reconfigurable import Reconfigurable
from babelfish_stt.calibration import (
    CANDIDATE_WINDOWS_S,
    CANARY_FIXTURE,
    FINAL_FIXTURE_MIN_S,
    MIN_PADDING_S,
    PROBES_PER_CELL,
    SAMPLE_RATE,
    column_cohort,
    entry_payload,
    final_rtfx as final_rtfx_of,
    fingerprint,
    load_calibration_fixtures,
    load_fixture_audio,
    onnx_asr_version,
    ort_version,
    select_window,
    slice_window,
    table_tier_for_cost,
    tier_for_cost,
    throttle_for_cost,
    weights_identity,
)
from babelfish_stt.config import (
    CALIBRATION_SCHEMA_VERSION,
    PipelineConfig,
    BabelfishConfig,
)
from babelfish_stt.hardware import get_memory_usage, get_device_name
from babelfish_stt.placement import onnx_providers, resolve_device
from pydantic import BaseModel

# nvidia-smi reports GPUs in PCI bus order, so pin CUDA ordinals to bus ids
# before any ONNX Runtime session is created in this process.
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

logger = logging.getLogger(__name__)

# Generous cap around the first CUDA session creation (DLL load + context
# build + encoder-weights read). The healthy path is ~3s; if this cap trips,
# the load is wedged (driver contention, AV scan) and we fail loudly into the
# existing CPU fallback instead of hanging startup forever. Applies only when
# a local model dir resolved: with no local copy, load_model auto-downloads
# from the HF cache inside the same call, and a first-run download can
# legitimately take longer than this cap.
MODEL_LOAD_TIMEOUT_S = 60.0

# GPU backend -> (required provider, ORT flavor package), used by
# _degraded_device_fix to print the exact remediation when ORT lacks the
# provider a resolved device needs. The uv extra is derived below (cuda
# is platform-dependent). Mirrors ORT_FLAVOR in scripts/bootstrap.py —
# the engine-side loud fallback of the bootstrap's verify-and-self-heal.
_DEGRADED_FIX: Dict[str, tuple] = {
    "cuda": ("CUDAExecutionProvider", "onnxruntime-gpu"),
    "dml": ("DmlExecutionProvider", "onnxruntime-directml"),
    "openvino": ("OpenVINOExecutionProvider", "onnxruntime-openvino"),
    "coreml": ("CoreMLExecutionProvider", "onnxruntime"),
}
_BACKEND_EXTRA = {
    "dml": "windows-gpu",
    "openvino": "intel-linux",
    "coreml": "cpu",
}


def _degraded_device_fix(device: str) -> Optional[str]:
    """Remediation text when ORT lacks the provider `device` needs, else None.

    A resolved GPU device whose provider is missing from
    `get_available_providers()` usually means another ORT flavor wheel
    (plain / gpu / directml / openvino all ship the same top-level
    `onnxruntime/` package) currently owns the pyd — a shadowed install.
    """
    backend = device.partition(":")[0]
    if backend == "cuda":
        extra = "nvidia-win" if sys.platform == "win32" else "nvidia-linux"
    else:
        extra = _BACKEND_EXTRA.get(backend)
    entry = _DEGRADED_FIX.get(backend)
    if not extra or not entry:
        return None
    required, package = entry
    available = list(onnxruntime.get_available_providers())
    if required in available:
        return None
    return (
        f"Device {device} requested but {required} is not available "
        f"(providers: {available}). Likely a shadowed ORT install. "
        f"Fix: uv sync --extra {extra} --reinstall-package {package}"
    )


# --- Weights ladder (ADR 0014) ---
#
# MODEL_NAME stays the onnx-asr registry key; it is NOT the file layout —
# whatever weights sit in the resolved directory get loaded (the load-bearing
# property the Track-B prototype exercised with zero code changes). The fp32
# v3 directory keeps that name; the Redux int4 card lives beside it with a
# -redux suffix. cpu devices land on the redux card, GPU devices keep fp32
# v3 (GPU int4 MatMulNBits is deliberately out of scope for now); a config
# hardware.model ("v3"/"redux") forces one card regardless of device.

WEIGHTS_TAG_FP32 = "fp32 v3"
WEIGHTS_TAG_REDUX = "parakeet-redux int4 MatMulNBits"
_REDUX_SUFFIX = "-redux"


def weights_card_dir(model_name: str, device: str, model_override: Optional[str]) -> str:
    """The ladder card a device resolves to: the directory name under
    models/ that holds the intended weights."""
    if model_override == "redux":
        return model_name + _REDUX_SUFFIX
    if model_override == "v3":
        return model_name
    return (
        model_name + _REDUX_SUFFIX if device == "cpu" else model_name
    )


def weights_tag_for(path: Optional[Path]) -> str:
    """The human-readable weights tag for a resolved model directory
    (the 📦 Model source log line: exactly which card loaded)."""
    if path is not None and path.name.endswith(_REDUX_SUFFIX):
        return WEIGHTS_TAG_REDUX
    return WEIGHTS_TAG_FP32


def resolve_model_path(
    cache_dir: Optional[str],
    base_dir: Path,
    model_name: str,
    device: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Optional[Path]:
    """
    Model resolution order (the per-device weights ladder, ADR 0014):
    1. Shared cache dir (config `cache.cache_dir`, auto-populated from
       VOGON_APP_CACHE_DIR) — e.g. VogonPoet's provisioned cache.
    2. Repo-local models/ directory.
    3. None -> onnx-asr default path (HF cache; auto-downloads on first use).

    The card (directory name) is device-derived — cpu -> the redux card,
    any GPU backend -> the fp32 v3 card — unless `model_override`
    (hardware.model) forces one card. The legacy 3-arg call form resolves
    the fp32 v3 card (device=None).
    """
    card_dir = weights_card_dir(model_name, device, model_override)
    tag = weights_tag_for(Path(card_dir))
    candidates = []

    if cache_dir:
        candidates.append(("shared-cache", Path(cache_dir) / "models" / card_dir))

    candidates.append(("repo", base_dir / "models" / card_dir))

    for source, candidate in candidates:
        if candidate.exists():
            logger.info(f"📦 Model source ({source}): {candidate} ({tag})")
            return candidate

    logger.info(
        "📦 No local model found; onnx-asr will use its default HF cache "
        "(auto-download on first use)."
    )
    if device == "cpu" and model_override is None:
        logger.warning(
            "📦 No local %s card for device cpu (expected the Redux card, "
            "provisioned by the bootstrap); the fallback downloads the fp32 "
            "v3 weights from HF." % card_dir
        )
    return None


class STTEngine(Reconfigurable):
    """
    Unified STT engine using onnx-asr for hardware-accelerated inference
    on AMD, Intel, and NVIDIA GPUs across Windows and Linux.
    """

    MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"

    config_key = "pipeline"

    def __init__(self, config: BabelfishConfig):
        self._lock = threading.Lock()
        # Resolve target device
        target_device = config.hardware.device
        self.device_type = self._resolve_device(target_device)
        self.config_ref = config  # Keep reference to update status

        # Model resolution order (the per-device weights ladder, ADR 0014):
        # 1. Shared cache dir (config `cache.cache_dir`, auto-populated from
        #    VOGON_APP_CACHE_DIR) — e.g. VogonPoet's provisioned cache.
        # 2. Repo-local models/ directory (used when running from a checkout
        #    with a local model copy).
        # 3. onnx-asr default path (HF cache; auto-downloads on first use).
        # The card is device-derived (cpu -> redux int4, gpu -> fp32 v3)
        # unless hardware.model forces one; self.model_path is kept for the
        # calibration fingerprint's weights identity (D5/ADR 0014) and
        # self.weights_tag for the startup diagnostics.
        model_path = self._resolve_model_path(config)
        self.model_path = model_path
        self.weights_tag = weights_tag_for(model_path)

        # Quantization Policy: full precision everywhere by default.
        # An explicit hardware.quantization setting is still honoured.
        if self.device_type != "cpu":
            quantization = None
            logger.info("🚀 GPU mode: Forcing highest precision quantization.")
        else:
            quantization = config.hardware.quantization
            logger.info(f"🐌 CPU mode: Using quantization={quantization}")
        # Recorded for the calibration fingerprint (ADR 0013): the bench
        # is keyed by what actually ran, not what was requested.
        self.quantization = quantization

        # Map Babelfish device to ONNX Runtime providers
        providers = self._get_providers(self.device_type)

        # A GPU device resolved while its provider is missing from the
        # installed onnxruntime means a shadowed/flavor-mismatched install:
        # say so loudly instead of silently degrading to CPU.
        degraded_fix = _degraded_device_fix(self.device_type)
        if degraded_fix:
            logger.warning(f"⚠️ {degraded_fix}")

        logger.info(f"🚀 Initializing onnx-asr (Providers: {providers})...")

        # Measure Baseline Memory (Before loading model)
        probe_start = time.perf_counter()
        mem_before = get_memory_usage(self.device_type)
        logger.info(f"⏱️ Memory probe: {time.perf_counter() - probe_start:.2f}s")

        try:
            self.model = self._load_model_bounded(
                self.MODEL_NAME,
                path=str(model_path) if model_path else None,
                quantization=quantization,
                providers=providers,
                log_label=f"Model load ({self.device_type})",
            )
        except Exception as e:
            logger.error(f"Failed to load onnx-asr model: {e}")
            # Fallback to CPU if GPU fails
            if self.device_type != "cpu":
                # If the GPU load failed because its provider is missing
                # (shadowed ORT install), say so loudly with the exact fix.
                fallback_fix = _degraded_device_fix(self.device_type)
                if fallback_fix:
                    logger.warning(f"⚠️ {fallback_fix}")
                logger.warning("Retrying with CPU provider...")
                self.device_type = "cpu"  # Update device type to cpu
                self.quantization = None  # the fallback forces full precision
                self.model = self._load_model_bounded(
                    self.MODEL_NAME,
                    path=str(model_path) if model_path else None,
                    quantization=None,
                    providers=["CPUExecutionProvider"],
                    log_label="Model load (cpu, fallback)",
                )
            else:
                raise

        # Measure Memory After loading and update config
        probe_start = time.perf_counter()
        mem_after = get_memory_usage(self.device_type)
        logger.info(f"⏱️ Memory probe: {time.perf_counter() - probe_start:.2f}s")

        try:
            self.config_ref.status.active_device = self.device_type
            self.config_ref.status.active_device_name = get_device_name(
                self.device_type
            )
            self.config_ref.status.vram_total_gb = float(mem_after["total"])
            self.config_ref.status.vram_used_baseline_gb = float(mem_before["used"])
            self.config_ref.status.vram_used_model_gb = float(mem_after["used"])

            vram_status = (
                f"Total={self.config_ref.status.vram_total_gb:.2f}GB, "
                f"Baseline={self.config_ref.status.vram_used_baseline_gb:.2f}GB, "
                f"ModelLoaded={self.config_ref.status.vram_used_model_gb:.2f}GB "
                f"(Delta: {self.config_ref.status.vram_used_model_gb - self.config_ref.status.vram_used_baseline_gb:.2f}GB)"
            )
            # Free VRAM at baseline distinguishes a repeat stall: driver
            # contention (probe itself slow/timed out), VRAM exhaustion
            # (used ≈ total before load), or AV scanning (time concentrated
            # in the model-load timer above).
            if self.config_ref.status.vram_total_gb > 0:
                free_gb = (
                    self.config_ref.status.vram_total_gb
                    - self.config_ref.status.vram_used_baseline_gb
                )
                vram_status = f"Free={free_gb:.2f}GB, " + vram_status
            logger.info(f"📊 VRAM Status: {vram_status}")
        except (TypeError, ValueError, AttributeError):
            # Handle mocks in tests or missing data
            logger.info(
                f"📊 VRAM Status: Total={mem_after['total']}GB, Baseline={mem_before['used']}GB, ModelLoaded={mem_after['used']}GB"
            )

    def _load_model_bounded(self, *args, log_label: str, **kwargs) -> Any:
        """onnx_asr.load_model with a generous wall-clock cap.

        Runs the load in a worker thread and waits up to
        MODEL_LOAD_TIMEOUT_S. On timeout the load cannot be abandoned
        safely in-thread (an interrupted ORT session creation has no
        termination guarantee), so the worker is left to finish as a
        daemon whose result is discarded — no half-initialized model is
        ever kept — and the timeout re-raises so the caller routes into
        its existing CPU-fallback path. Skipped entirely when no local
        model resolved (first-run HF auto-download inside load_model can
        legitimately outlast the cap).
        """
        if kwargs.get("path") is None:
            return onnx_asr.load_model(*args, **kwargs)

        start = time.perf_counter()
        # A plain daemon thread, not a ThreadPoolExecutor: the executor
        # registers an atexit hook that joins its workers, so a wedged load
        # would block interpreter shutdown even after shutdown(wait=False).
        # A daemon thread with a captured result is why the timeout can
        # abandon the attempt safely — see MODEL_LOAD_TIMEOUT_S.
        outcome: Dict[str, Any] = {}

        def _load() -> None:
            try:
                outcome["model"] = onnx_asr.load_model(*args, **kwargs)
            except BaseException as e:  # noqa: BLE001 - captured, not raised here
                outcome["error"] = e

        worker = threading.Thread(
            target=_load, name="model-load", daemon=True
        )
        worker.start()
        worker.join(timeout=MODEL_LOAD_TIMEOUT_S)
        elapsed = time.perf_counter() - start

        if worker.is_alive():
            # Wedged load (driver contention, AV scan?). The worker is left
            # to finish as a daemon; its result is never read, so a
            # half-initialized model is never kept. Surface a loud,
            # actionable timeout and route into the CPU fallback.
            logger.warning(
                f"⏱️ {log_label} exceeded {MODEL_LOAD_TIMEOUT_S:.0f}s — "
                "wedged load (driver contention, AV scan?); abandoning the "
                "GPU attempt (worker left to finish, result discarded) and "
                "falling back to CPU."
            )
            raise TimeoutError(f"{log_label} exceeded {MODEL_LOAD_TIMEOUT_S:.0f}s")

        if "error" in outcome:
            raise outcome["error"]

        logger.info(f"⏱️ {log_label}: {elapsed:.2f}s")
        return outcome["model"]

    def _resolve_model_path(self, config: BabelfishConfig) -> Optional[Path]:
        """
        Returns the first existing local model directory, or None to let
        onnx-asr use its default HF cache (auto-download on first use).
        """
        cache_dir = config.cache.cache_dir

        # Repo checkout layout: src/babelfish_stt/engine.py -> repo root
        base_dir = Path(__file__).resolve().parent.parent.parent
        return resolve_model_path(
            cache_dir,
            base_dir,
            self.MODEL_NAME,
            device=self.device_type,
            model_override=getattr(config.hardware, "model", None),
        )

    def _resolve_device(self, device: str) -> str:
        from babelfish_stt.hardware import probe_hardware_facts

        return resolve_device(device, probe_hardware_facts())

    def _get_providers(self, device: str) -> List[Any]:
        return onnx_providers(device)

    def reconfigure(self, config: BaseModel) -> None:
        """STTEngine reconfigure (called by ConfigManager)."""
        # Currently STTEngine doesn't have much to hot-reload from PipelineConfig
        # as most hardware settings require a restart which is handled by BabelfishServer.
        pass

    def transcribe(
        self,
        audio_buffer: np.ndarray,
        padding_s: float = 2.0,
    ) -> str:
        if len(audio_buffer) == 0:
            return ""

        # Performance Optimization:
        # The model has high overhead for short clips but is very fast for long ones.
        # Force a minimum duration of audio by padding with silence if needed.
        min_samples = int(padding_s * 16000)
        if len(audio_buffer) < min_samples:
            padding = np.zeros(min_samples - len(audio_buffer), dtype=np.float32)
            # Add padding to the END to preserve audio onset at the beginning
            # This is critical for accurate transcription of the first words
            input_audio = np.concatenate([audio_buffer, padding])
        else:
            input_audio = audio_buffer

        import time

        start_t = time.perf_counter()

        with self._lock:
            # onnx-asr handles the stream/context internally or we can just pass the buffer
            result = self.model.recognize(input_audio, sample_rate=16000)

        end_t = time.perf_counter()
        duration_ms = (end_t - start_t) * 1000
        audio_duration_s = len(input_audio) / 16000.0

        logger.debug(
            f"Inference: {duration_ms:.2f}ms for {audio_duration_s:.2f}s audio (RTF: {duration_ms / (audio_duration_s * 1000):.3f})"
        )

        return result.strip() if result else ""

    def _measure_latency_ms(
        self, test_audio: np.ndarray, padding_s: float = 0.0
    ) -> float:
        """One calibration probe: inference latency in ms for the given
        audio at the given padding protocol."""
        import time

        start = time.perf_counter()
        self.transcribe(test_audio, padding_s=padding_s)
        return (time.perf_counter() - start) * 1000

    def calibration_fingerprint(self) -> str:
        """Cache key for a benched profile (ADR 0013): resolved backend +
        device name + quantization + model + bench schema + onnxruntime
        and onnx-asr versions.

        Uses the RESOLVED device (self.device_type, reassigned in place
        by the GPU->CPU fallbacks above) so a driver-broken launch
        can't poison a GPU-keyed entry with CPU measurements, and the
        resolved card's weights identity (ADR 0014) so the fp32 and
        redux profiles can never collide under one key — the measured
        prototype bug (a Redux bench silently overwrote the fp32 CPU
        profile under the same weights-blind key).
        """
        return fingerprint(
            backend=self.device_type,
            device_name=get_device_name(self.device_type),
            quantization=self.quantization,
            model_name=self.MODEL_NAME,
            weights_id=weights_identity(self.model_path),
            schema_version=CALIBRATION_SCHEMA_VERSION,
            ort_version=ort_version(),
            onnx_asr_version=onnx_asr_version(),
        )

    def canary_probe(self, window_s: float) -> float:
        """One canary inference at the stored operating point (ADR 0013).

        Replays the canary fixture's cell at the stored window. The
        warm-up is discarded because on a cache hit this is the
        session's FIRST inference — its cold session/kernel init would
        otherwise read as deviation and defeat the cache.
        """
        audio = load_fixture_audio(CANARY_FIXTURE)
        probe_audio = slice_window(audio, window_s)
        self.transcribe(probe_audio, padding_s=0.0)  # discarded warm-up
        canary_ms = self._measure_latency_ms(probe_audio, padding_s=0.0)
        logger.debug(
            f"⏱️ Calibration canary: {canary_ms:.1f}ms at window "
            f"{window_s:.1f}s ({CANARY_FIXTURE}, onset-aligned)"
        )
        return canary_ms

    def benchmark(self, previous_tier: Optional[str] = None) -> dict:
        """Runs the real-speech probe matrix (ADR 0013) and returns the
        benched entry payload: profile fields (tier/throttle/window/
        paddings) plus the persistence extras (operating_cost_ms,
        final_rtfx, and the measured cell table).

        The single-scalar silence probe is gone (superseded): silence is
        not a Ghost-shaped probe and one scalar cannot serve both
        passes — the Ghost/Final rank order flips across backends.
        Instead:

        - Ghost cells: 5 bundled fixtures x candidate windows, sliced
          onset-aligned so every cell contains speech, each probed with
          1 discarded warm-up + 3 timed inferences, per-cell median.
        - Cohorts: per-window-column median of the 5 fixture cells; any
          cell median >2x its column's cohort is dropped and logged.
        - ghost_window_s comes from the measured curve (the largest
          candidate window whose cohort stays within budget/headroom),
          NOT from a tier lookup — DML's cliff (2.0->2.3 s in its
          morning regime; 1.0->1.5 s later) would put a tier-lookup
          window of 2.5 s exactly in the slow regime.
        - Tier + throttle come from the cost AT that window (the
          operating point). `previous_tier` enables the hysteresis that
          keeps a boundary-straddling backend's label stable.
        - min_padding_s is constant 2.0 (quality-driven, un-bundled from
          the tier); ghost_padding_s stays 1.0.
        - Final cells: per long fixture, one discarded warm-up + one
          full-length pass -> informational Final RTFx (each full length
          is a new input shape; cold-shape cost must not pollute it).
        """
        logger.info(
            "⏱️ Starting hardware self-calibration "
            f"(real-speech probe matrix, {self.device_type})..."
        )

        import statistics

        fixtures = load_calibration_fixtures()
        cells: Dict[str, Dict[str, float]] = {}
        cohorts: Dict[float, float] = {}

        for window in CANDIDATE_WINDOWS_S:
            column: Dict[str, float] = {}
            for name, audio in fixtures.items():
                probe_audio = slice_window(audio, window)
                # Per-cell warm-up, discarded: the first recognize() on
                # a new input length pays session/kernel init (ADR 0011's
                # cold-start finding, applied to every cell).
                self.transcribe(probe_audio, padding_s=0.0)
                probes = [
                    self._measure_latency_ms(probe_audio, padding_s=0.0)
                    for _ in range(PROBES_PER_CELL)
                ]
                column[name] = float(statistics.median(probes))
                cells.setdefault(name, {})[window] = column[name]

            cohort, dropped = column_cohort(column)
            for name in dropped:
                logger.warning(
                    f"⏱️ Calibration outlier dropped: {name} @ {window:.1f}s "
                    f"({column[name]:.1f}ms; column cohort {cohort:.1f}ms "
                    "after the >2x drop)"
                )
            cohorts[window] = cohort
            cell_summary = ", ".join(
                f"{name}={column[name]:.1f}" for name in fixtures
            )
            logger.info(
                f"⏱️ Calibration: window {window:.1f}s cohort "
                f"{cohort:.1f}ms ({cell_summary})"
            )

        window = select_window(cohorts)
        operating_cost = cohorts[window]
        tier = tier_for_cost(operating_cost, previous_tier)
        throttle = throttle_for_cost(operating_cost)
        if tier != table_tier_for_cost(operating_cost):
            logger.info(
                f"⏱️ Calibration: tier label kept as {tier} by hysteresis "
                f"(measured {operating_cost:.1f}ms, table says "
                f"{table_tier_for_cost(operating_cost)})"
            )

        # Final cells: one full-length pass per long fixture ->
        # informational Final RTFx (the whole utterance, like the Final
        # pass transcribes it). Each full-length audio is a NEW input
        # shape the matrix never saw (slices cap at the largest
        # candidate window), and the first inference at a new shape pays
        # a large one-time cost (measured: 157 ms vs ~37 ms warmed) —
        # so each Final cell gets the same discarded warm-up the Ghost
        # cells do, or the RTFx under-reports steady state by 2-4x.
        rtfx_values = []
        for name, audio in fixtures.items():
            if len(audio) / SAMPLE_RATE <= FINAL_FIXTURE_MIN_S:
                continue
            self.transcribe(audio, padding_s=MIN_PADDING_S)  # discarded warm-up
            cost_ms = self._measure_latency_ms(
                audio, padding_s=MIN_PADDING_S
            )
            rtfx_values.append(final_rtfx_of(len(audio) / SAMPLE_RATE, cost_ms))
            logger.info(
                f"⏱️ Calibration Final pass: {name} "
                f"{len(audio) / SAMPLE_RATE:.1f}s in {cost_ms:.1f}ms "
                f"(RTFx {rtfx_values[-1]:.0f}x)"
            )
        final_rtfx = (
            float(statistics.median(rtfx_values)) if rtfx_values else 0.0
        )

        logger.info(
            f"⏱️ Calibration complete: Window={window}s, "
            f"Tier={tier.upper()}, Throttle={throttle}ms, "
            f"OperatingCost={operating_cost:.1f}ms, "
            f"FinalRTFx={final_rtfx:.0f}x"
        )

        return entry_payload(
            tier=tier,
            ghost_throttle_ms=throttle,
            ghost_window_s=window,
            operating_cost_ms=operating_cost,
            cells=cells,
            final_rtfx=final_rtfx,
        )
