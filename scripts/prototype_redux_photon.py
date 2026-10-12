"""Track A prototype: Moondream Parakeet Redux via the Photon runtime (CPU).

Throwaway experiment (plan: ~/.opencode/plan/parakeet-redux-prototypes.md),
NOT the production integration. One new file, zero changes to existing files.

Design — reuse the inherited engine surface instead of re-implementing
anything: PhotonRecognizeWrapper mimics the onnx-asr model surface
(``recognize(audio, sample_rate) -> str``), and PhotonEngine subclasses
babelfish's own STTEngine overriding ONLY the model-load path. Everything
else (the transcribe padding protocol, _measure_latency_ms, canary_probe,
benchmark, engine lock) is inherited UNCHANGED — so telemetry lines
(⚡ First Ghost / Inference RTF) and pipeline behavior match the
baseline/Track-B runs exactly.

Wire-up mirrors run_babelfish()'s heavy_init() and STANDALONE behavior:
**default is live microphone** (idle until hotkey/hotkey-gated, Ghost
updates on the terminal, `--type` types into the focused app) with wake
word gating skipped via ww_engine=None (rawest latency picture; wake word
is engine-agnostic and orthogonal). `--replay` switches to the fixture
harness (real-time paced, capture JSON) so numbers are directly
comparable with the baseline and Track-B runs.

Run (torch never pollutes the project venv — uv overlay):

    uv run --with moondream python scripts/prototype_redux_photon.py \
        --log-level DEBUG

Optional extras:
    --type                         type Ghost/Final into the focused app
    --replay dictation_fr          replay a bundled fixture instead of mic
    REDUX_FORCE_ISA=avx2  <env>    force a kestrel ISA path before load
                                   (test hook for future kestrel builds
                                   where the kernel ships but the probe
                                   misreports; today it loads but the
                                   first matmul raises "no 'avx2'
                                   matrix-multiply path on this machine")
"""

import os
import sys

# --- Environment, BEFORE torch/kestrel load -------------------------------
# OMP_WAIT_POLICY must be set before torch loads on CPU (plan research fact).
os.environ.setdefault("OMP_WAIT_POLICY", "passive")
# Match main.py's thread caps so the numbers aren't confounded by
# oversubscription on the i9-9900K (16t) for tiny real-time inferences.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
# Keep moondream's HF downloads out of the HF default cache: prefer
# VOGON_APP_CACHE_DIR (VogonPoet's shared cache), else a repo-local .cache.
_hf_home = os.environ.get("VOGON_APP_CACHE_DIR")
if not _hf_home:
    _hf_home = str(os.path.join(os.path.dirname(__file__), "..", ".cache"))
os.environ.setdefault("HF_HOME", os.path.abspath(_hf_home))

# Console UTF-8 (mirrors main.py so model output can't kill the loop on
# Windows charmap codecs).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import argparse  # noqa: E402
import asyncio  # noqa: E402
import functools  # noqa: E402
import logging  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402

import babelfish_stt.engine  # noqa: E402,F401  (registers DLL dirs etc.)
from babelfish_stt.engine import STTEngine  # noqa: E402
from babelfish_stt.main import calibrate, run_stt_loop  # noqa: E402
from babelfish_stt.replay import WavStreamer, CaptureDisplay  # noqa: E402
from babelfish_stt.display import TerminalDisplay, MultiDisplay  # noqa: E402
from babelfish_stt.vad import SileroVAD  # noqa: E402
from babelfish_stt.pipeline import StandardPipeline  # noqa: E402
from babelfish_stt.config_manager import ConfigManager  # noqa: E402
from babelfish_stt.notifier import DesktopNotifier  # noqa: E402

logger = logging.getLogger(__name__)


class PhotonRecognizeWrapper:
    """Mimics the onnx-asr model surface: recognize(audio, sample_rate) -> str."""

    def __init__(self, photon_client: Any):
        self._client = photon_client

    def recognize(self, input_audio: np.ndarray, sample_rate: int = 16000) -> str:
        result = self._client.transcribe(audio=input_audio, sample_rate=sample_rate)
        if isinstance(result, dict):
            return (result.get("text") or "").strip()
        return str(result).strip()


class PhotonEngine(STTEngine):
    """STTEngine with ONLY the model-load path swapped for Photon.

    Inherited unchanged: the transcribe padding protocol (end-padding to
    padding_s * 16000 under the engine lock), all calibration plumbing
    (_measure_latency_ms / canary_probe / benchmark / fingerprint), and the
    device-resolution / VRAM-status machinery (harmless: reports host RAM
    path for cpu).

    Calibration fingerprint caveat (recorded, not fixed): the fingerprint
    uses MODEL_NAME ("nemo-parakeet-tdt-0.6b-v3") and the onnxruntime /
    onnx-asr module versions even though the runtime behind transcribe is
    Photon/kestrel — a Photon-profile entry could therefore collide with a
    same-device onnx-asr entry keyed identically. Expected outcome on this
    machine: a CPU-fingerprint entry may already exist (from the Track-B
    run); the Photon bench then OVERWRITES that shared entry. That is fine
    for the prototype (the last bench wins; cap 4) but means the two
    runtimes cannot share persisted profiles. It is another reason the
    config copy lives in .scratch_logs/cfg (never the real config file).
    """

    # Keep MODEL_NAME (calibration fixtures + fingerprint key off it);
    # document that its registry role is unused here.

    def __init__(self, config):
        # Reuse the parent constructor for device/lock/status plumbing, but
        # bypass its onnx-asr load: monkeypatch-free approach — call the
        # parent __init__, which builds self.model via _load_model_bounded;
        # we override that hook to build the Photon client instead.
        super().__init__(config)

    def _load_model_bounded(self, *args: Any, log_label: str, **kwargs: Any) -> Any:
        """Replace onnx_asr.load_model with the Photon client load."""
        import moondream as md

        isa = os.environ.get("REDUX_FORCE_ISA")
        if isa:
            from kestrel_kernels import ternary as ternary_kernels

            try:
                ternary_kernels.set_gemm_isa(isa)
                logger.warning(
                    f"⚠️ REDUX_FORCE_ISA={isa}: ISA probe overridden (set before "
                    "load; the first matmul will still fail unless the kestrel "
                    "payload actually ships this path)"
                )
            except Exception as e:
                logger.warning(f"⚠️ REDUX_FORCE_ISA={isa} rejected: {e}")

        start = time.perf_counter()
        logger.info(f"🧠 Loading Photon model (moondream/parakeet-redux, cpu)...")
        client = md.photon("moondream/parakeet-redux", device="cpu")
        elapsed = time.perf_counter() - start
        logger.info(f"⏱️ {log_label}: {elapsed:.2f}s")
        return PhotonRecognizeWrapper(client)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track A prototype: Parakeet Redux via Photon "
        "(moondream) on the real babelfish pipeline. Live mic by default; "
        "--replay runs the bundled fixtures instead."
    )
    parser.add_argument(
        "--replay",
        dest="fixture",
        type=str,
        default=None,
        metavar="NAME",
        help="Bare calibration fixture name to replay instead of the mic "
        "(e.g. dictation_fr). Omitted name replays all five fixtures.",
    )
    parser.add_argument(
        "--type",
        dest="type_into_apps",
        action="store_true",
        help="Type Ghost/Final text into the focused app (mic mode; in-memory "
        "override mirroring babelfish CLI --type).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Config file path (default: CWD-relative babelfish.config.json, "
        "same resolution as the babelfish CLI).",
    )
    parser.add_argument(
        "--capture-out",
        dest="capture_out",
        type=str,
        default=None,
        help="Capture JSON output path (relative to CWD). Default: none in "
        "mic mode; 'photon_capture.json' in replay mode.",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        type=str.lower,
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Root log level (default: info).",
    )
    return parser


async def run(
    fixture: str, type_into_apps: bool, config_manager: ConfigManager, capture_out: str
) -> None:
    status_msgs: list = []

    async def status(message: str):
        status_msgs.append(message)
        logger.info(f"… {message}")

    replay_mode = fixture is not None
    logger.info("=" * 50)
    logger.info(
        "🧪 TRACK A: Redux via Photon "
        + ("(replay harness)" if replay_mode else "(live microphone)")
    )
    logger.info("=" * 50)

    config = config_manager.config
    # Photon is a CPU prototype: force the device in memory (never saved)
    # so the parent STTEngine constructor resolves cpu (providers,
    # quantization=None, calibration fingerprint backend "cpu").
    configured_device = config.hardware.device
    config.hardware.device = "cpu"
    logger.info(
        f"   DEVICE: cpu forced in memory for Photon (config file says "
        f"{configured_device!r}; override is in-memory only, never saved)"
    )

    if type_into_apps:
        config.system_input.enabled = True
        config.system_input.type_ghost = True
        logger.info("   MODE: Typing Ghost/Final text into the focused app")

    # 1. VAD
    await status("Loading Silero VAD...")
    vad = await asyncio.to_thread(SileroVAD)

    # 2. Photon engine (overrides only the load path)
    await status("Loading STT Engine (Photon cpu)...")
    engine = await asyncio.to_thread(PhotonEngine, config)

    # 3. Calibration — inherited, benches the 5-fixture matrix against the
    # Photon wrapper (first launch: no persisted entry for this fingerprint).
    profile = await calibrate(engine, config_manager, status)

    # 4. Displays: terminal (+ capture in replay/with --capture-out;
    # + InputDisplay when typing is on — same precedence as run_babelfish).
    displays: list = [TerminalDisplay()]
    if replay_mode or capture_out:
        fixture_name = fixture or "live"
        capture = CaptureDisplay(
            capture_out or "photon_capture.json",
            header={
                "fixture": fixture_name,
                "runtime": "photon",
                "tier": profile.tier,
                "ghost_window_s": profile.ghost_window_s,
                "ghost_throttle_ms": profile.ghost_throttle_ms,
                "ghost_padding_s": profile.ghost_padding_s,
                "min_padding_s": profile.min_padding_s,
                "device": engine.device_type,
            },
        )
        displays.append(capture)
    else:
        capture = None
    if config.system_input.enabled:
        from babelfish_stt.display import InputDisplay

        displays.append(InputDisplay(config_manager))
    display = MultiDisplay(*displays)

    # 5. Pipeline + streamer + loop
    pipeline = StandardPipeline(vad, engine, display, perf=profile)
    if replay_mode:
        # No wake-word gating; force-listen from the first sample; finals
        # captured per fixture. Rawest latency picture.
        fixtures = [fixture] if fixture else [
            "dictation_fr",
            "hello_hello",
            "joke",
            "multiple_words",
            "unicode_speech",
        ]
        for name in fixtures:
            if capture:
                capture.header["fixture"] = name
                capture.events.clear()
            logger.info("-")
            logger.info(f"📼 Replaying fixture: {name}")
            streamer = WavStreamer(
                str(
                    os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "src",
                        "babelfish_stt",
                        "calibration_assets",
                        f"{name}.wav",
                    )
                )
            )
            shutdown_event = threading.Event()
            await asyncio.to_thread(
                run_stt_loop,
                streamer,
                pipeline,
                None,  # ww_engine: skipped in replay
                shutdown_event,
                None,  # server
                True,  # listen_immediately
            )
            if capture:
                capture.write()
    else:
        # LIVE MIC — standalone semantics: idle until the hotkey
        # (config ui.shortcuts.toggle_listening, default Ctrl+Space),
        # Ghost updates on the terminal, Final replaces consumable text.
        from babelfish_stt.audio import AudioStreamer
        from babelfish_stt.hotkey_manager import HotkeyManager

        hotkey_manager = HotkeyManager(pipeline, None)
        hotkey_manager.start(config)
        logger.info(
            "🎤 Live mic ready. Press the toggle hotkey to start/stop "
            "listening (Ctrl+C to exit)."
        )
        shutdown_event = threading.Event()
        try:
            await asyncio.to_thread(
                run_stt_loop,
                AudioStreamer(
                    microphone_name=config.hardware.microphone_name
                ),
                pipeline,
                None,  # ww_engine: skipped — rawest latency picture
                shutdown_event,
                None,  # server
            )
        finally:
            hotkey_manager.stop()
            if capture:
                capture.write()

    await status("Engine Ready!")
    logger.info("✅ Track A complete.")


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )

    config_manager = ConfigManager(config_path=args.config)
    asyncio.run(run(args.fixture, args.type_into_apps, config_manager, args.capture_out))


if __name__ == "__main__":
    main()
