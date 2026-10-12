"""Calibration math and probe assets (ADR 0013): bench once per
acceleration backend, canary-checked every launch.

The pure functions here own the measurable decisions of the probe matrix
so they can be tested without a model: onset-aligned fixture slicing,
per-window cohort medians with the outlier rule, window selection from
the measured cost curve, the throttle-anchored tier boundaries with
hysteresis, the fingerprint that keys the persisted cache, and the
canary's tolerance check. `engine.benchmark()` orchestrates the actual
inferences over these functions; `main.calibrate()` owns the
miss/hit/canary flow and persistence.

Supersedes the silence-probe posture of ADR 0011 (silence is not a
Ghost-shaped probe: it demoted a CUDA card that measures 30-39 ms on
speech purely on probe workload, and one scalar cannot serve both
passes — the Ghost/Final rank order flips across backends).
"""

import hashlib
import importlib.metadata
import logging
import statistics
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Tuple

import numpy as np

from babelfish_stt.config import CALIBRATION_SCHEMA_VERSION

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000

# --- Probe protocol (pinned by the Oct 2026 measurement pass; ADR 0013) ---

# The five bundled real-speech fixtures: very short, normal, repeated,
# long-conversational, and long-dense-French. 16 kHz mono, no clipping,
# natively at realistic mic level (RMS 0.011-0.024) — probe bytes are fed
# raw, with NO RMS normalization (measured ~8% effect, and not
# workload-neutral in principle).
FIXTURES = (
    "unicode_speech",
    "multiple_words",
    "hello_hello",
    "joke",
    "dictation_fr",
)

# Candidate Ghost windows. 2.0 must stay in the set: DML's cost cliff
# has been observed between 2.0 and 2.3 s windows (~57 ms below it,
# ~260 ms above — 4.5x, the Oct-5-morning regime) AND between 1.0 and
# 1.5 s windows (later sessions, ~50 ms below / ~225 ms above) — the
# cliff position itself is cross-session state, so the set needs
# candidates on both sides of wherever it currently sits. The curve
# rule lands the window below the cliff either way.
CANDIDATE_WINDOWS_S = (1.0, 1.5, 2.0, 2.5, 3.0)

# Per cell: one discarded warm-up + this many timed probes, per-cell
# median. The warm-up is per cell because the first recognize() on a
# new input length pays session/kernel init (ADR 0011's cold-start
# finding, applied to every cell rather than once).
PROBES_PER_CELL = 3

# Fixtures long enough to measure a Final-shaped pass (a whole
# utterance, meaningfully longer than any candidate Ghost window).
FINAL_FIXTURE_MIN_S = 2.6

# The canary replays this fixture's cell at the stored operating window.
# The normal-length pangram: representative of the Ghost regime and long
# enough to cover every candidate window after onset alignment.
CANARY_FIXTURE = "multiple_words"

# --- Window selection from the measured curve ---

# The Ghost window comes from the curve, not a tier lookup: the largest
# candidate window whose column cohort stays within this budget, or
# within CURVE_HEADROOM x the best column's cohort (whichever is
# larger). The budget keeps a flat-cost backend (CPU) on the max window;
# the headroom multiple lets a uniformly slower backend still spread to
# larger windows when nothing got relatively worse.
GHOST_BUDGET_MS = 200.0
CURVE_HEADROOM = 1.5

# --- Tier boundaries and throttle floors ---

# The floors are UX cadence anchors (the max Ghost update interval a
# user tolerates) and stay as they were; pacing is max(cost, throttle),
# so each tier's boundary is the operating cost below which that tier's
# throttle still paces submissions with ~2x headroom — anchored to the
# cadence each tier promises, not to hardware classes. Boundaries are
# exclusive upper bounds ("<50 ultra, <100 high, <200 medium, else
# low_power").
TIER_BOUNDARIES_MS = (50.0, 100.0, 200.0)
TIER_THROTTLES = {"ultra": 100, "high": 150, "medium": 250, "low_power": 400}

# A re-bench landing within +/- this fraction of a boundary keeps the
# previous tier label: CPU straddles the 200 ms boundary across
# sessions/days, and the label must not flap with it. The fields
# (window/throttle) take the new measured values regardless — the label
# is nearly cosmetic, the operating point is the product.
TIER_HYSTERESIS = 0.15

# --- Canary ---

# One inference per launch at the stored operating point. Tolerance is
# symmetric: a session that got FASTER by more than this is also a
# regime flip (DML's session bimodality ran both ways) and re-benches.
CANARY_TOLERANCE = 0.25

# --- Onset alignment ---

# Skip each fixture's leading silence before slicing so every cell
# contains speech (onset slices can transcribe "" — a cell would then
# measure a cheaper workload than intended). Speech RMS is 0.011-0.024
# across the fixtures; 0.004 sits well below speech level and above the
# noise floor of the recorded leading silence.
ONSET_THRESHOLD = 0.004

# --- Fixed profile fields (quality-driven, un-bundled from the tier) ---

# min_padding_s is Final-only and constant 2.0 — the old tier table's
# low_power -> 1.0 mapping was the semantic bug ADR 0011 flagged.
# ghost_padding_s stays 1.0 (ADR 0010-era live finding: unpadded onset
# windows transcribe "", delaying the first visible Ghost).
MIN_PADDING_S = 2.0
GHOST_PADDING_S = 1.0

# Bundled fixtures, shipped as package data (~1.4 MB): offline-safe
# startup, no download machinery for a payload this size.
ASSETS_DIR = Path(__file__).resolve().parent / "calibration_assets"

# Cap on persisted entries (one per acceleration backend fingerprint:
# cuda/dml/openvino/cpu), pruned oldest-first by benched_at.
CALIBRATION_PROFILES_CAP = 4


# --- Asset loading ---


def load_fixture_audio(name: str) -> np.ndarray:
    """One bundled fixture as float32 mono audio at SAMPLE_RATE.

    Raises on a missing or malformed fixture (16-bit PCM only, like the
    replay harness) so a broken install surfaces as a calibration
    failure, not a silently cheaper probe.
    """
    path = ASSETS_DIR / f"{name}.wav"
    with wave.open(str(path), "rb") as wf:
        file_rate = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())

    if sampwidth != 2:
        raise ValueError(
            f"Calibration fixture {path} must be 16-bit PCM "
            f"(got {sampwidth * 8}-bit)"
        )
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if file_rate != SAMPLE_RATE:
        import soxr

        audio = soxr.resample(audio, file_rate, SAMPLE_RATE)

    return audio.astype(np.float32, copy=False)


def load_calibration_fixtures() -> dict:
    """All bundled fixtures, {name: audio}."""
    return {name: load_fixture_audio(name) for name in FIXTURES}


# --- Onset-aligned slicing ---


def onset_sample(audio: np.ndarray, threshold: float = ONSET_THRESHOLD) -> int:
    """Index of the first sample above `threshold` in magnitude.

    Returns len(audio) for an all-silent fixture (the slice is then
    empty — a degenerate probe, never silently cheaper speech).
    """
    above = np.nonzero(np.abs(audio) > threshold)[0]
    return int(above[0]) if len(above) else len(audio)


def slice_window(
    audio: np.ndarray,
    window_s: float,
    rate: int = SAMPLE_RATE,
    threshold: float = ONSET_THRESHOLD,
) -> np.ndarray:
    """The onset-aligned probe slice for a candidate window.

    Skips the fixture's leading silence, then takes `window_s` of audio
    (clipped at the fixture's end — a short fixture measures what it
    has; the cohort median absorbs that).
    """
    start = onset_sample(audio, threshold)
    return audio[start : start + int(window_s * rate)]


# --- Cohorts and the outlier rule ---


def column_cohort(
    cells: Mapping[str, float],
) -> Tuple[float, Tuple[str, ...]]:
    """Cohort median of one window column's fixture cells.

    Any cell median more than 2x the column's cohort median is dropped
    (and returned, so the caller logs it) and the cohort is recomputed
    from the survivors. The median itself already resists one outlier;
    the rule makes the drop explicit and observable.
    """
    cohort = float(statistics.median(cells.values()))
    dropped = tuple(
        name for name, value in cells.items() if value > 2.0 * cohort
    )
    if dropped:
        kept = {
            name: value
            for name, value in cells.items()
            if name not in dropped
        }
        if kept:
            cohort = float(statistics.median(kept.values()))
    return cohort, dropped


def select_window(
    cohorts: Mapping[float, float],
    budget_ms: float = GHOST_BUDGET_MS,
    headroom: float = CURVE_HEADROOM,
) -> float:
    """The Ghost window from the measured curve: the largest candidate
    window whose column cohort stays within max(budget, headroom x best
    cohort)."""
    best = min(cohorts.values())
    limit = max(budget_ms, headroom * best)
    return max(w for w, c in cohorts.items() if c <= limit)


# --- Tier at the operating point ---


def table_tier_for_cost(cost_ms: float) -> str:
    """The tier the boundary table assigns an operating cost."""
    for boundary, tier in zip(TIER_BOUNDARIES_MS, ("ultra", "high", "medium")):
        if cost_ms < boundary:
            return tier
    return "low_power"


def tier_for_cost(
    cost_ms: float, previous_tier: Optional[str] = None
) -> str:
    """Tier label for an operating cost, with hysteresis.

    Within +/- TIER_HYSTERESIS of a boundary the previous label is kept
    (when one exists) so a backend that straddles a boundary across
    sessions doesn't flap its label.
    """
    table = table_tier_for_cost(cost_ms)
    if previous_tier is None:
        return table
    for boundary in TIER_BOUNDARIES_MS:
        if abs(cost_ms - boundary) <= TIER_HYSTERESIS * boundary:
            return previous_tier
    return table


def throttle_for_cost(cost_ms: float) -> int:
    """The throttle floor for an operating cost — from the TABLE tier.

    Deliberately not from the hysteresis-kept label: the fields take the
    new measured values regardless of the kept label (the label is
    nearly cosmetic, the operating point is the product).
    """
    return TIER_THROTTLES[table_tier_for_cost(cost_ms)]


def final_rtfx(duration_s: float, cost_ms: float) -> float:
    """Final-pass real-time factor: audio seconds transcribed per
    second of inference. Informational only."""
    if cost_ms <= 0:
        return 0.0
    return duration_s / (cost_ms / 1000.0)


# --- Fingerprint ---


# Full-content hashing is bounded to small files; the big weights binaries
# (fp32 encoder ~2.4 GB with its .onnx.data, redux encoder ~344 MB) are
# identified by name + byte size. A re-export that kept every file size
# byte-identical would collide — vanishingly unlikely, and the price of
# full-content identity is hashing 2.4+ GB on every launch, a multi-second
# startup tax. The measured prototype bug (fp32 and redux profiles sharing
# one key) turns on the packed encoder's different size, which this
# catches exactly.
_WEIGHTS_FULL_HASH_LIMIT = 8 * 1024 * 1024


def weights_identity(model_dir) -> str:
    """Stable identity of the weights card a model directory holds.

    SHA-256 over each file's name and size, plus the full content of small
    files (config.json, vocab.txt) whose bytes pin the export. Raises
    nothing: a missing/unreadable/empty directory yields "" (no local
    card to identify — e.g. onnx-asr's HF auto-download path), so the
    fingerprint simply omits the weights component, as before ADR 0014.

    The measured prototype bug this closes: fingerprint
    `cpu|CPU|None|<MODEL_NAME>|1|1.30.0|0.12.0` was weights-blind — a
    Redux bench overwrote the fp32 profile under the same key and vice
    versa (the canary only catches it within ±25%).
    """
    if not model_dir:
        return ""
    try:
        files = sorted(
            p for p in Path(model_dir).iterdir() if p.is_file()
        )
    except OSError:
        return ""
    if not files:
        return ""

    digest = hashlib.sha256()
    try:
        for f in files:
            digest.update(f.name.encode("utf-8", "surrogateescape"))
            digest.update(str(f.stat().st_size).encode("ascii"))
            if f.stat().st_size <= _WEIGHTS_FULL_HASH_LIMIT:
                digest.update(f.read_bytes())
    except OSError:
        return ""
    return digest.hexdigest()[:12]


def fingerprint(
    backend: str,
    device_name: str,
    quantization: Optional[str],
    model_name: str,
    weights_id: str = "",
    schema_version: int = CALIBRATION_SCHEMA_VERSION,
    ort_version: str = "",
    onnx_asr_version: str = "",
) -> str:
    """Cache key for a benched profile: resolved backend + device name +
    quantization + model + WEIGHTS IDENTITY + bench schema +
    onnxruntime/onnx-asr versions.

    The caller passes the RESOLVED backend (post GPU->CPU fallback) so a
    driver-broken launch can't poison a GPU-keyed entry with CPU
    measurements, and the weights identity of the resolved model
    directory (weights_identity) so an fp32 bench and a redux bench can
    never share a key — the fp32 CPU and redux CPU profiles are distinct
    entries (ADR 0014; the measured collision from the prototype).
    """
    return "|".join(
        (
            backend,
            device_name,
            str(quantization),
            model_name,
            weights_id,
            str(schema_version),
            ort_version,
            onnx_asr_version,
        )
    )


def ort_version() -> str:
    import onnxruntime

    return onnxruntime.__version__


def onnx_asr_version() -> str:
    import onnx_asr

    version = getattr(onnx_asr, "__version__", None)
    if version:
        return str(version)
    return importlib.metadata.version("onnx-asr")


def utc_now_iso() -> str:
    """UTC timestamp for benched_at; same-format ISO strings sort
    chronologically, which the prune-oldest-first cap relies on."""
    return datetime.now(timezone.utc).isoformat()


# --- Canary ---


def window_key(window_s) -> str:
    """Cell-table key for a candidate window ("2.0" for 2.0). Accepts the
    float (benchmark-internal) or the string (loaded from JSON) form."""
    return f"{float(window_s):.1f}"


def canary_reference(entry) -> float:
    """The stored cost the canary is compared against: the canary
    fixture's own cell at the stored window (the canary replays exactly
    that cell), falling back to the operating cost for entries without
    a cell table."""
    cells = getattr(entry, "cells", None) or {}
    fixture_cells = cells.get(CANARY_FIXTURE) or {}
    reference = fixture_cells.get(window_key(float(entry.ghost_window_s)))
    if reference is not None:
        return float(reference)
    return float(entry.operating_cost_ms)


def canary_within_tolerance(
    canary_ms: float,
    reference_ms: float,
    tolerance: float = CANARY_TOLERANCE,
) -> bool:
    """True when the canary matches its stored reference within
    tolerance (symmetric: a much-faster session is also a regime flip)."""
    if reference_ms <= 0:
        return False
    return abs(canary_ms - reference_ms) <= tolerance * reference_ms


def entry_payload(
    tier: str,
    ghost_throttle_ms: int,
    ghost_window_s: float,
    operating_cost_ms: float,
    cells: Mapping[str, Mapping[str, float]],
    final_rtfx: float,
) -> dict:
    """The benchmark() result payload: profile fields + the persistence
    extras, ready for CalibrationProfileEntry(**payload, benched_at=...)."""
    return {
        "tier": tier,
        "ghost_throttle_ms": ghost_throttle_ms,
        "ghost_window_s": ghost_window_s,
        "ghost_padding_s": GHOST_PADDING_S,
        "min_padding_s": MIN_PADDING_S,
        "operating_cost_ms": round(float(operating_cost_ms), 1),
        "final_rtfx": round(float(final_rtfx), 1),
        "cells": {
            name: {window_key(w): round(float(v), 1) for w, v in windows.items()}
            for name, windows in cells.items()
        },
    }
