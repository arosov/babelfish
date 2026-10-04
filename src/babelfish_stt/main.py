import sys
import os

# PERFORMANCE OPTIMIZATION:
# Strictly limit threading for numerical libraries BEFORE they initialize.
# This prevents high-core CPUs (like i9 9900) from over-subscribing threads
# for tiny real-time inferences, which is a major source of high CPU usage.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
# nvidia-smi lists GPUs in PCI bus order: pin CUDA ordinals to bus ids so the
# device selected by highest-VRAM probing is the device ONNX Runtime uses.
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

# Register the ONNX Runtime / NVIDIA DLL directories before any module below
# imports onnxruntime (directly, or via onnx_asr / openwakeword). Without this
# a CUDA provider whose dependencies cannot be resolved fails silently into
# the engine's CPU fallback. Safety net for paths that skip the bootstrap —
# see scripts/bootstrap.py and ADR 0006.
from babelfish_stt.hardware import register_nvidia_dll_dirs  # noqa: E402

register_nvidia_dll_dirs()

import logging
import numpy as np
import time
import argparse
import functools
import threading
import asyncio
import openwakeword
from pathlib import Path
from typing import Optional, List, Any
from babelfish_stt.hardware import HardwareManager
from babelfish_stt.engine import STTEngine
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.replay import (
    WavStreamer,
    CaptureDisplay,
    DEFAULT_CAPTURE_OUT,
)
from babelfish_stt.display import (
    TerminalDisplay,
    ServerDisplay,
    MultiDisplay,
    InputDisplay,
)
from babelfish_stt.vad import SileroVAD
from babelfish_stt.config import PerformanceProfile
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.server import BabelfishServer
from babelfish_stt.notifier import DesktopNotifier
from babelfish_stt.wakeword import WakeWordEngine
from babelfish_stt.pipeline import StandardPipeline, StopWordDetector
from babelfish_stt.hotkey_manager import HotkeyManager

logger = logging.getLogger(__name__)


async def calibrate(engine, status) -> PerformanceProfile:
    """Startup self-calibration (ADR 0011).

    Runs unconditionally on every launch — there is no tier override to
    skip it and nothing is ever persisted. The computed profile is passed
    to the pipeline in memory only; pacing is never user-facing
    configuration.

    Survivable failure: on any exception, fall back to the
    PerformanceProfile() defaults instead of aborting startup — the same
    fallback posture engine init has for device-load failure.
    """
    await status("Calibrating Performance...")
    try:
        perf_data = await asyncio.to_thread(engine.benchmark)
    except Exception as e:
        logger.warning(
            f"⚠️ Calibration failed ({e}); keeping default profile."
        )
        return PerformanceProfile()

    profile = PerformanceProfile(**perf_data)
    logger.info(f"✅ Performance calibrated: {profile.tier.upper()}")
    return profile


def run_stt_loop(
    streamer, pipeline, ww_engine, shutdown_event, server=None, listen_immediately=False
):
    """Main blocking loop for audio capture and processing.

    `listen_immediately` (replay harness): skip idle/wake-word gating and
    treat the whole stream as one forced-listen session — the fixture is
    one utterance sequence from the first sample, with no hotkey to
    unlock it.
    """
    try:
        logger.info("🎤 STT Loop Started")
        logger.info("-" * 50)

        if listen_immediately:
            pipeline.request_mode(is_idle=False, force=True)
            logger.info("🎤 REPLAY: listening from the first sample (Ctrl+C to stop)")
        else:
            # Start in idle state (waiting for trigger)
            pipeline.request_mode(is_idle=True, force=True)

            if pipeline.is_idle:
                if ww_engine and ww_engine.active_start_word:
                    logger.info(
                        f"💤 IDLE: Waiting for wake-word '{ww_engine.active_start_word}'..."
                    )
                else:
                    logger.info("💤 IDLE: Waiting for trigger (Hotkey/PTT)...")
            else:
                # This branch shouldn't be hit on startup now, but kept for logic consistency
                logger.info("🎤 Listening... (Press Ctrl+C to stop)")

        cooldown_until = 0
        stop_cooldown_until = 0
        last_configured_ww = ww_engine.active_start_word if ww_engine else None
        last_configured_stop_ww = ww_engine.active_stop_word if ww_engine else None

        # Process audio in 32ms chunks (512 samples @ 16kHz)
        # This provides low-latency detection for VAD and ghost updates.
        for chunk in streamer.stream(chunk_size=512):
            if shutdown_event.is_set():
                break

            now = time.time()
            now_ms = now * 1000

            # 1. VAD Gating (Cheapest Check)
            # If the chunk is silent, we skip WakeWord and Pipeline logic entirely.
            is_speech = pipeline.vad.is_speech(chunk)

            # Dynamically check for wakeword updates
            active_ww = ww_engine.active_start_word if ww_engine else None
            stop_ww = ww_engine.active_stop_word if ww_engine else None

            # Handle dynamic transitions when configuration changes
            if active_ww != last_configured_ww or stop_ww != last_configured_stop_ww:
                # ... (rest of config update logic remains same)
                if active_ww != last_configured_ww:
                    if active_ww is None:
                        pipeline.request_mode(is_idle=False, force=True)
                        logger.info("🔄 CONFIG: Wake-word disabled. Listening...")
                    else:
                        pipeline.request_mode(is_idle=True, force=True)
                        logger.info(
                            f"🔄 CONFIG: Wake-word '{active_ww}' enabled. Waiting..."
                        )
                    last_configured_ww = active_ww

                if stop_ww != last_configured_stop_ww:
                    logger.info(
                        f"🔄 CONFIG: Stop-word changed to '{stop_ww or 'None'}'"
                    )
                    last_configured_stop_ww = stop_ww

            with pipeline._lock:
                is_idle = pipeline.is_idle

            if is_idle:
                if now < cooldown_until:
                    # Update pre-roll even during cooldown
                    pipeline.process_chunk(chunk, now_ms, is_speech=is_speech)
                    continue

                # Only run WakeWord detection if VAD detected speech
                if is_speech and ww_engine and ww_engine.detect(chunk):
                    logger.info(f"✨ WAKEWORD '{active_ww}' DETECTED!")
                    pipeline.request_mode(
                        is_idle=False, force=False, source_event="wakeword_detected"
                    )

                    # PROCESS THE TRIGGER CHUNK IMMEDIATELY
                    # This ensures the audio that contained the wake word is part of the sentence
                    pipeline.process_chunk(chunk, now_ms, is_speech=True)

                    # Ignore stop word for 4s to avoid immediate re-triggering with same audio
                    stop_cooldown_until = now + 4.0
                    continue  # Skip normal idle processing to prevent duplicate chunk handling
                else:
                    # Update pre-roll while idle
                    pipeline.process_chunk(chunk, now_ms, is_speech=is_speech)
            else:
                # Active mode
                stop_detected = False

                # Only check for Stop-WakeWord if VAD detected speech
                if is_speech and ww_engine and stop_ww:
                    # Always process chunk to keep model state consistent, but ignore result during cooldown
                    is_detected = ww_engine.detect(chunk, word=stop_ww)
                    if now >= stop_cooldown_until:
                        stop_detected = is_detected

                if stop_detected:
                    logger.info(f"🛑 STOP WAKEWORD '{stop_ww}' DETECTED!")
                    pipeline.request_mode(
                        is_idle=True, force=True, source_event="stop_word_detected"
                    )
                    state_changed = True
                else:
                    # In active mode, process chunk through pipeline if not stopping
                    # Pass the pre-computed is_speech to avoid redundant VAD check
                    state_changed = pipeline.process_chunk(
                        chunk, now_ms, is_speech=is_speech
                    )

                if state_changed:
                    # Pipeline reported a transition (e.g., transcript stop word detected)
                    # Re-check if we should go to idle based on current config
                    if active_ww:
                        # Already transitioned by pipeline or we transition here if it was just a regular utterance
                        with pipeline._lock:
                            currently_idle = pipeline.is_idle

                        if not currently_idle:
                            pipeline.request_mode(is_idle=True, force=False)

                        streamer.drain()
                        if ww_engine:
                            ww_engine.reset()
                        cooldown_until = now + 4.0
                        logger.info(
                            f"💤 IDLE: Waiting for wake-word '{active_ww}'... (4.0s cooldown)"
                        )
                    else:
                        logger.info("🛑 Stopped.")

    except Exception as e:
        logger.error(f"Error in STT loop: {e}")
    finally:
        logger.info("✅ STT Loop Shutdown.")


async def run_babelfish(
    hw: HardwareManager,
    wakeword: Optional[str] = None,
    stopword: Optional[str] = None,
    force_cpu: bool = False,
    port: Optional[int] = None,
    serve: bool = False,
    type_into_apps: bool = False,
    replay_path: Optional[str] = None,
    capture_out: Optional[str] = None,
):
    logger.info("=" * 50)
    logger.info("🚀 BABELFISH STT INITIALIZING")

    mode = "SERVICE (--server, WebSocket API enabled)" if serve else "STANDALONE"
    logger.info(f"   MODE: {mode}")

    # 2. Config Load & Validation
    config_manager = ConfigManager()
    if not config_manager.is_valid(hw):
        logger.warning(
            "⚠️ Configuration is invalid or missing. Generating optimal defaults..."
        )
        config_manager.generate_optimal_defaults(hw)
    else:
        logger.info("✅ Configuration validated against hardware.")

    # Override config with CLI flags if provided (in-memory only, never saved)
    if force_cpu:
        config_manager.config.hardware.device = "cpu"
        logger.info("   MODE: Force CPU Execution (CLI Override)")

    if type_into_apps:
        config_manager.config.system_input.enabled = True
        config_manager.config.system_input.type_ghost = True
        logger.info("   MODE: Typing Ghost/Final text into the focused app (CLI Override)")

    # Replay harness: the pipeline replays a fixture WAV instead of the
    # microphone, and every Ghost frame is captured to JSON. System-input
    # typing is FORBIDDEN in replay mode — the harness must never type
    # into whatever application happens to have focus.
    capture = None
    if replay_path:
        if config_manager.config.system_input.enabled:
            raise RuntimeError(
                "Replay mode forbids system-input typing "
                "(system_input.enabled is true; remove it or the --type flag)"
            )
        logger.info(f"   REPLAY: {replay_path}")
        if capture_out:
            logger.info(f"   CAPTURE: {capture_out}")

    if port is not None:
        config_manager.config.server.port = port
        logger.info(f"   PORT: {port} (CLI Override)")

    if wakeword:
        config_manager.config.voice.wakeword = wakeword
    if stopword:
        # Check if it's meant to be an openwakeword stopword or a transcript stopword
        # For now, if we have a stopword flag and it matches an openwakeword model,
        # we'll use it as stop_wakeword. Otherwise, we keep it in stop_words.

        available_ww = list(openwakeword.MODELS.keys())
        if stopword in available_ww:
            config_manager.config.voice.stop_wakeword = stopword
            logger.info(f"   STOP-WAKE-WORD: {stopword}")
        else:
            if stopword not in config_manager.config.voice.stop_words:
                config_manager.config.voice.stop_words.append(stopword)
            logger.info(
                f"   STOP-WORDS: {', '.join(config_manager.config.voice.stop_words)}"
            )

    logger.info(f"   DEVICE: {config_manager.config.hardware.device.upper()}")

    if config_manager.config.voice.wakeword:
        logger.info(f"   WAKE-WORD: {config_manager.config.voice.wakeword}")

    # 3. Start Server (Service mode only; standalone runs fully offline)
    server = None
    if serve:
        server = BabelfishServer(config_manager)
        config_manager.register(server)

        await server.start()
        logger.info(
            f"   SERVER: WebSockets running on ws://{config_manager.config.server.host}:{config_manager.config.server.port}/config"
        )

        await asyncio.sleep(0.5)

    logger.info("=" * 50)

    # 4. Initialize Audio Pipeline (Heavy/Blocking)
    async def status(message: str):
        """Forward bootstrap progress to WebSocket clients when in service mode."""
        if server:
            await server.broadcast_bootstrap_status(message)

    async def heavy_init():
        device = config_manager.config.hardware.device
        capture = None  # the replay capture display; non-replay launches have none

        await status("Loading Silero VAD...")
        vad = await asyncio.to_thread(SileroVAD)

        await status(f"Loading STT Engine ({device})...")
        engine = await asyncio.to_thread(STTEngine, config=config_manager.config)

        # 5. Hardware Self-Calibration (ADR 0011: unconditional, in-memory
        # only) — runs before the pipeline is built so the profile can be
        # passed in.
        profile = await calibrate(engine, status)

        await status(
            f"Loading WakeWord ({config_manager.config.voice.wakeword or 'None'})..."
        )
        app_data_dir = os.environ.get("VOGON_APP_DATA_DIR")
        ww_engine = await asyncio.to_thread(
            WakeWordEngine,
            start_word=config_manager.config.voice.wakeword,
            stop_word=config_manager.config.voice.stop_wakeword,
            sensitivity=config_manager.config.voice.wakeword_sensitivity,
            stop_sensitivity=config_manager.config.voice.stop_wakeword_sensitivity,
            app_data_dir=app_data_dir,
        )

        await status("Initializing Audio Stream...")
        if replay_path:
            # Replay harness: the fixture replaces the microphone, paced
            # in real time (see babelfish_stt.replay).
            streamer = await asyncio.to_thread(WavStreamer, replay_path)
        else:
            streamer = await asyncio.to_thread(
                AudioStreamer,
                microphone_name=config_manager.config.hardware.microphone_name,
            )

        displays: List[Any] = [TerminalDisplay()]
        if server:
            displays.append(ServerDisplay(server))
        if capture_out:
            # Capture display: records every raw Ghost frame (text, window
            # span, wall ts, inference duration) to JSON — the evidence for
            # diagnosing Ghost behavior. Works alongside typing: with
            # `--type --capture-out PATH`, a live run records what the
            # pipeline actually emitted while the user watches the typed
            # result.
            fixture_name = Path(replay_path).name if replay_path else "live"
            capture = CaptureDisplay(
                capture_out,
                header={
                    "fixture": fixture_name,
                    "tier": profile.tier,
                    "ghost_window_s": profile.ghost_window_s,
                    "ghost_throttle_ms": profile.ghost_throttle_ms,
                    "ghost_padding_s": profile.ghost_padding_s,
                    "min_padding_s": profile.min_padding_s,
                    "device": engine.device_type,
                },
            )
            displays.append(capture)
        if replay_path:
            # The capture display replaces InputDisplay in replay mode:
            # typing into the focused app is forbidden while replaying.
            capture = capture or CaptureDisplay(
                capture_out or str(DEFAULT_CAPTURE_OUT),
                header={
                    "fixture": Path(replay_path).name,
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
            # Replaced only in replay mode: the capture display rides
            # ALONGSIDE typing in live diagnostic runs (see capture_out
            # above), it never replaces it.
            displays.append(InputDisplay(config_manager))
        display = MultiDisplay(*displays)
        pipeline = StandardPipeline(vad, engine, display, perf=profile)

        if pipeline.stop_detector:
            config_manager.register(pipeline.stop_detector)

        return vad, engine, ww_engine, streamer, display, pipeline, capture

    logger.info("⏳ Loading engines and models (this may take a few seconds)...")
    vad, engine, ww_engine, streamer, display, pipeline, capture = await heavy_init()

    # Initialize the notifier (both modes get wake/stop-word desktop toasts)
    notifier = DesktopNotifier()
    config_manager.register(notifier)
    pipeline.notifier = notifier

    # In service mode, link pipeline to server and register remaining
    # components for hot-reloading
    if server:
        server.set_pipeline(pipeline)
        pipeline.server = server

        # Update server's internal initial_config to include runtime stats
        # (active_device, VRAM) so a no-op config update doesn't look like a
        # device change and trigger a restart.
        server.initial_config = config_manager.config.model_copy(deep=True)
        await server.send_initial_state(None)

    # Initialize and start global hotkeys
    hotkey_manager = HotkeyManager(pipeline, server)
    hotkey_manager.start(config_manager.config)
    config_manager.register(hotkey_manager)

    config_manager.register(vad)
    config_manager.register(engine)
    config_manager.register(pipeline)
    config_manager.register(streamer)
    config_manager.register(ww_engine)
    if pipeline.stop_detector:
        config_manager.register(pipeline.stop_detector)

    await status("Engine Ready!")
    logger.info("✅ Initialization complete.")

    # 3. Start STT Loop in Background Thread
    shutdown_event = threading.Event()
    loop = asyncio.get_running_loop()

    stt_task = loop.run_in_executor(
        None,
        functools.partial(
            run_stt_loop,
            streamer,
            pipeline,
            ww_engine,
            shutdown_event,
            server,
            listen_immediately=bool(replay_path),
        ),
    )

    try:
        if replay_path:
            # A replay is finite: run to the end of the fixture and exit
            # cleanly (the WavStreamer ends after its trailing silence,
            # by which point the Final pass has fired).
            await stt_task
        else:
            await asyncio.Future()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("🛑 Stopping Babelfish...")
    finally:
        shutdown_event.set()
        streamer.stop()
        hotkey_manager.stop()
        await stt_task
        if capture is not None:
            capture.write()
        logger.info("✅ Shutdown complete.")


def build_parser() -> argparse.ArgumentParser:
    available_ww = list(openwakeword.MODELS.keys())

    parser = argparse.ArgumentParser(
        description="Babelfish STT - High-performance streaming transcription"
    )

    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU execution even if GPU is available",
    )

    parser.add_argument(
        "--server",
        action="store_true",
        help="Run in service mode: expose the WebSocket API (for VogonPoet). "
        "Default is standalone mode (no network listener).",
    )

    parser.add_argument(
        "--type",
        dest="type_into_apps",
        action="store_true",
        help="Type transcripts into the focused application (Ghost live, "
        "replaced by Final when the turn ends). In-memory override, not saved.",
    )

    parser.add_argument(
        "--replay",
        dest="replay_path",
        type=str,
        default=None,
        metavar="PATH",
        help="Replay harness: stream a fixture WAV through the real pipeline "
        "instead of the microphone (real-time paced) and capture every Ghost "
        "frame to JSON. Typing into applications is forbidden in this mode.",
    )

    parser.add_argument(
        "--capture-out",
        dest="capture_out",
        type=str,
        default=None,
        metavar="PATH",
        help="Capture JSON path: record every raw Ghost frame (text, window "
        "span, wall ts, inference duration) to JSON for diagnosing Ghost "
        "behavior. With --replay (default: "
        f"{DEFAULT_CAPTURE_OUT.as_posix()}); without --replay, works "
        "alongside a live run (e.g. with --type). Typing into applications "
        "is forbidden only in replay mode.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="WebSocket port in --server mode (default: from config or 8123)",
    )

    parser.add_argument(
        "--wakeword",
        type=str,
        nargs="?",
        const="LIST_OPTIONS",
        help=f"Enable wake-word activation. Available: {', '.join(available_ww)}",
    )

    parser.add_argument(
        "--stopword",
        type=str,
        help="Specific word that stops transcription",
    )

    return parser


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.port is not None and not args.server:
        parser.error("--port requires --server")

    if args.replay_path and args.type_into_apps:
        parser.error(
            "--replay forbids --type: the replay harness must never type "
            "into the focused application"
        )

    if args.replay_path and args.server:
        parser.error("--replay is standalone-only (no --server)")

    return args


def main():
    # Configure logging early to ensure probe() output is visible
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s", force=True
    )

    args = parse_args()

    if args.wakeword == "LIST_OPTIONS":
        logger.info("Available Wake-words:")
        for ww in list(openwakeword.MODELS.keys()):
            logger.info(f"  - {ww}")
        sys.exit(0)

    # 1. Hardware Probe
    hw = HardwareManager().probe()

    asyncio.run(
        run_babelfish(
            hw=hw,
            wakeword=args.wakeword,
            stopword=args.stopword,
            force_cpu=args.cpu,
            port=args.port,
            serve=args.server,
            type_into_apps=args.type_into_apps,
            replay_path=args.replay_path,
            capture_out=args.capture_out,
        )
    )


if __name__ == "__main__":
    main()
