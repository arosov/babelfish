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

import logging
import numpy as np
import time
import argparse
import threading
import asyncio
import openwakeword
from typing import Optional, List, Any
from babelfish_stt.hardware import HardwareManager
from babelfish_stt.engine import STTEngine
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.display import (
    TerminalDisplay,
    ServerDisplay,
    MultiDisplay,
    InputDisplay,
)
from babelfish_stt.vad import SileroVAD
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.server import BabelfishServer
from babelfish_stt.wakeword import WakeWordEngine
from babelfish_stt.pipeline import StandardPipeline, StopWordDetector
from babelfish_stt.hotkey_manager import HotkeyManager

logger = logging.getLogger(__name__)


def run_stt_loop(streamer, pipeline, ww_engine, shutdown_event, server=None):
    """Main blocking loop for audio capture and processing."""
    try:
        logger.info("🎤 STT Loop Started")
        logger.info("-" * 50)

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

        # Optimization: Process audio in 96ms chunks (1536 samples @ 16kHz)
        # This is exactly 3 blocks of 512 samples, which Silero VAD requires.
        # This reduces inference frequency by ~66% compared to 32ms chunks.
        for chunk in streamer.stream(chunk_size=1536):
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
                    continue

                # Only run WakeWord detection if VAD detected speech
                if is_speech and ww_engine and ww_engine.detect(chunk):
                    logger.info(f"✨ WAKEWORD '{active_ww}' DETECTED!")
                    pipeline.request_mode(
                        is_idle=False, force=False, source_event="wakeword_detected"
                    )
                    # Clear any old audio from streamer to start fresh
                    streamer.drain()
                    # Ignore stop word for 4s to avoid immediate re-triggering with same audio
                    stop_cooldown_until = now + 4.0
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
):
    logger.info("=" * 50)
    logger.info("🚀 BABELFISH STT INITIALIZING")

    # 2. Config Load & Validation
    config_manager = ConfigManager()
    if not config_manager.is_valid(hw):
        logger.warning(
            "⚠️ Configuration is invalid or missing. Generating optimal defaults..."
        )
        config_manager.generate_optimal_defaults(hw)
    else:
        logger.info("✅ Configuration validated against hardware.")

    # Override config with CLI flags if provided
    if force_cpu:
        config_manager.config.hardware.device = "cpu"
        config_manager.config.hardware.auto_detect = False
        logger.info("   MODE: Force CPU Execution (CLI Override)")

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

    # 3. Start Server Early (Async)
    server = BabelfishServer(config_manager)
    config_manager.register(server)

    await server.start()
    logger.info(
        f"   SERVER: WebSockets running on ws://{config_manager.config.server.host}:{config_manager.config.server.port}/config"
    )

    await asyncio.sleep(0.5)
    logger.info("=" * 50)

    # 4. Initialize Audio Pipeline (Heavy/Blocking)
    async def heavy_init():
        device = config_manager.config.hardware.device

        await server.broadcast_bootstrap_status("Loading Silero VAD...")
        vad = await asyncio.to_thread(SileroVAD)

        await server.broadcast_bootstrap_status(f"Loading STT Engine ({device})...")
        engine = await asyncio.to_thread(STTEngine, config=config_manager.config)

        # 5. Hardware Self-Calibration
        if config_manager.config.pipeline.performance.tier == "auto":
            await server.broadcast_bootstrap_status("Calibrating Performance...")
            perf_data = await asyncio.to_thread(engine.benchmark)
            config_manager.update({"pipeline": {"performance": perf_data}})
            logger.info(f"✅ Performance calibrated: {perf_data['tier'].upper()}")

        await server.broadcast_bootstrap_status(
            f"Loading WakeWord ({config_manager.config.voice.wakeword or 'None'})..."
        )
        ww_engine = await asyncio.to_thread(
            WakeWordEngine,
            start_word=config_manager.config.voice.wakeword,
            stop_word=config_manager.config.voice.stop_wakeword,
            sensitivity=config_manager.config.voice.wakeword_sensitivity,
            stop_sensitivity=config_manager.config.voice.stop_wakeword_sensitivity,
        )

        await server.broadcast_bootstrap_status("Initializing Audio Stream...")
        streamer = await asyncio.to_thread(
            AudioStreamer,
            microphone_name=config_manager.config.hardware.microphone_name,
        )

        display = MultiDisplay(
            TerminalDisplay(),
            ServerDisplay(server),
            InputDisplay(config_manager),
        )
        pipeline = StandardPipeline(vad, engine, display)

        if pipeline.stop_detector:
            config_manager.register(pipeline.stop_detector)

        return vad, engine, ww_engine, streamer, display, pipeline

    logger.info("⏳ Loading engines and models (this may take a few seconds)...")
    vad, engine, ww_engine, streamer, display, pipeline = await heavy_init()

    # Link pipeline to server and register remaining components for hot-reloading
    server.set_pipeline(pipeline)
    pipeline.server = server

    # Initialize and start global hotkeys
    hotkey_manager = HotkeyManager(pipeline, server)
    hotkey_manager.start(config_manager.config)
    config_manager.register(hotkey_manager)

    # Update server's internal initial_config to include runtime stats (active_device, VRAM)
    # This prevents unnecessary restarts when switching from 'auto' to the detected device.
    server.initial_config = config_manager.config.model_copy(deep=True)

    # Broadcast updated config (with VRAM stats and active device) to clients
    await server.send_initial_state(None)

    config_manager.register(vad)
    config_manager.register(engine)
    config_manager.register(pipeline)
    config_manager.register(streamer)
    config_manager.register(ww_engine)
    if pipeline.stop_detector:
        config_manager.register(pipeline.stop_detector)

    await server.broadcast_bootstrap_status("Engine Ready!")
    logger.info("✅ Initialization complete.")

    # 3. Start STT Loop in Background Thread
    shutdown_event = threading.Event()
    loop = asyncio.get_running_loop()

    stt_task = loop.run_in_executor(
        None,
        run_stt_loop,
        streamer,
        pipeline,
        ww_engine,
        shutdown_event,
        server,
    )

    try:
        await asyncio.Future()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("🛑 Stopping Babelfish...")
    finally:
        shutdown_event.set()
        streamer.stop()
        hotkey_manager.stop()
        await stt_task
        logger.info("✅ Shutdown complete.")


def main():
    # Configure logging early to ensure probe() output is visible
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s", force=True
    )

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

    args = parser.parse_args()

    if args.wakeword == "LIST_OPTIONS":
        logger.info("Available Wake-words:")
        for ww in available_ww:
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
        )
    )


if __name__ == "__main__":
    main()
