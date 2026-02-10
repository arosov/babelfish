import sys
import os

import logging
import numpy as np
import time
import argparse
import threading
import asyncio
from babelfish_stt.hardware import HardwareManager
from babelfish_stt.engine import STTEngine
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.display import TerminalDisplay
from babelfish_stt.vad import SileroVAD
from babelfish_stt.pipeline import (
    SinglePassPipeline,
    DoublePassPipeline,
    StopWordDetector,
)
from babelfish_stt.wakeword import WakeWordEngine
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.server import BabelfishServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("babelfish_stt.server").setLevel(logging.DEBUG)


def run_stt_loop(streamer, pipeline, ww_engine, wakeword, stopword, shutdown_event):
    """
    Blocking STT loop to be run in a separate thread.
    """
    print("\n" + "-" * 50)
    print("HARDWARE & CONFIGURATION REPORT")
    # ... (Hardware report moved here or kept in main, passing necessary info)
    # We'll just print status here
    print("🎤 STT Loop Started")
    print("-" * 50 + "\n")

    if ww_engine:
        pipeline.set_idle(True)
        print(f"💤 IDLE: Waiting for wake-word '{wakeword}'...")
    else:
        print("🎤 Listening... (Press Ctrl+C to stop)\n")

    last_score_time = time.time()
    max_score_recent = 0.0
    cooldown_until = 0

    try:
        # Loop over 32ms chunks (512 samples)
        chunk_count = 0
        for chunk in streamer.stream(chunk_size=512):
            chunk_count += 1
            if chunk_count % 100 == 0:
                logging.debug(f"Processed {chunk_count} chunks")

            if shutdown_event.is_set():
                break

            now = time.time()
            now_ms = now * 1000

            if now < cooldown_until:
                continue

            if pipeline.is_idle and ww_engine:
                prediction = ww_engine.process_chunk(chunk)
                score = prediction.get(wakeword, 0)

                if score > max_score_recent:
                    max_score_recent = score

                if now - last_score_time > 1.0:
                    sys.stdout.write(
                        f"\r   [Max confidence in last 1s: {max_score_recent:.2f}]   "
                    )
                    sys.stdout.flush()
                    max_score_recent = 0.0
                    last_score_time = now

                if score > 0.5:
                    logging.info(
                        f"Wake-word '{wakeword}' detected with score {score:.2f}"
                    )
                    print(
                        f"\n\n✨ WAKE-WORD DETECTED: '{wakeword}' (score: {score:.2f})"
                    )
                    print("🎤 Listening... (Press Ctrl+C to stop)\n")
                    pipeline.set_idle(False)
            else:
                transitioned = pipeline.process_chunk(chunk, now_ms)
                if transitioned and pipeline.is_idle:
                    logging.info(
                        f"Stop-word '{stopword}' detected, transitioning to IDLE"
                    )
                    print(f"\n🛑 STOP-WORD DETECTED: '{stopword}'")

                    if ww_engine:
                        ww_engine.reset()
                        streamer.drain()
                        cooldown_until = now + 1.5
                        print(
                            f"💤 IDLE: Waiting for wake-word '{wakeword}'... (1.5s cooldown)"
                        )
                    else:
                        print("🛑 Stopped.")

    except Exception as e:
        logging.error(f"Error in STT loop: {e}")
    finally:
        print("✅ STT Loop Shutdown.")


async def run_babelfish(
    hw: HardwareManager,
    double_pass: bool = False,
    wakeword: str = None,
    stopword: str = None,
    force_cpu: bool = False,
):
    print("\n" + "=" * 50)
    print("🚀 BABELFISH STT INITIALIZING")

    # 2. Config Load & Validation
    config_manager = ConfigManager()
    if not config_manager.is_valid(hw):
        print("⚠️ Configuration is invalid or missing. Generating optimal defaults...")
        config_manager.generate_optimal_defaults(hw)
    else:
        print("✅ Configuration validated against hardware.")

    # Override config with CLI flags if provided
    if force_cpu:
        config_manager.config.hardware.device = "cpu"
        print("   MODE: Force CPU Execution (CLI Override)")

    # We prioritize CLI flags for mode/wakeword/stopword if they are explicitly set
    if double_pass:
        config_manager.config.pipeline.double_pass = True

    if wakeword:
        config_manager.config.voice.wakeword = wakeword
    if stopword:
        if stopword not in config_manager.config.voice.stop_words:
            config_manager.config.voice.stop_words.append(stopword)

    print(
        f"   MODE: {'Double-Pass Refinement' if config_manager.config.pipeline.double_pass else 'Single-Pass'}"
    )
    print(f"   DEVICE: {config_manager.config.hardware.device.upper()}")

    if config_manager.config.voice.wakeword:
        print(f"   WAKE-WORD: {config_manager.config.voice.wakeword}")
    if config_manager.config.voice.stop_words:
        print(f"   STOP-WORDS: {', '.join(config_manager.config.voice.stop_words)}")

    # 3. Start Server Early (Async)
    # This allows the frontend to connect and see the initialization logs/state
    server = BabelfishServer(config_manager)
    config_manager.register(server)

    await server.start()
    print(
        f"   SERVER: WebTransport running on https://{config_manager.config.server.host}:{config_manager.config.server.port}/config"
    )

    # Give the client a moment to reconnect after the bootstrap handover
    # before we start the heavy initialization, so they see the first status messages.
    await asyncio.sleep(0.5)

    print("=" * 50)

    # 4. Initialize Audio Pipeline (Heavy/Blocking)
    async def heavy_init():
        device = config_manager.config.hardware.device
        best_mic_idx = config_manager.config.hardware.microphone_index

        await server.broadcast_bootstrap_status("Loading Silero VAD...")
        vad = await asyncio.to_thread(SileroVAD)

        await server.broadcast_bootstrap_status(f"Loading STT Engine ({device})...")
        engine = await asyncio.to_thread(STTEngine, config=config_manager.config)

        ww_engine = None

        if config_manager.config.voice.wakeword:
            await server.broadcast_bootstrap_status(
                f"Loading WakeWord ({config_manager.config.voice.wakeword})..."
            )
            ww_engine = await asyncio.to_thread(
                WakeWordEngine, model_name=config_manager.config.voice.wakeword
            )

        await server.broadcast_bootstrap_status("Initializing Audio Stream...")
        streamer = await asyncio.to_thread(AudioStreamer, device_index=best_mic_idx)

        from babelfish_stt.display import TerminalDisplay, ServerDisplay, MultiDisplay

        display = MultiDisplay(TerminalDisplay(), ServerDisplay(server))

        # Pipeline
        if config_manager.config.pipeline.double_pass:
            pipeline = DoublePassPipeline(vad, engine, display)
        else:
            pipeline = SinglePassPipeline(vad, engine, display)

        if config_manager.config.voice.stop_words:
            pipeline.stop_detector = StopWordDetector(
                stop_words=config_manager.config.voice.stop_words
            )

        return vad, engine, ww_engine, streamer, display, pipeline

    print("⏳ Loading engines and models (this may take a few seconds)...")
    vad, engine, ww_engine, streamer, display, pipeline = await heavy_init()

    # Link pipeline to server and register remaining components for hot-reloading
    server.set_pipeline(pipeline)
    config_manager.register(vad)
    config_manager.register(engine)
    config_manager.register(pipeline)
    config_manager.register(streamer)
    if pipeline.stop_detector:
        config_manager.register(pipeline.stop_detector)

    await server.broadcast_bootstrap_status("Engine Ready!")
    print("✅ Initialization complete.")

    # 3. Start STT Loop in Background Thread
    shutdown_event = threading.Event()
    loop = asyncio.get_running_loop()

    # We run the STT loop in a separate thread executor
    stt_task = loop.run_in_executor(
        None,
        run_stt_loop,
        streamer,
        pipeline,
        ww_engine,
        wakeword,
        stopword,
        shutdown_event,
    )

    try:
        # Keep the main task alive while the server and STT loop run
        # Since server.start() no longer blocks, we block here.
        await asyncio.Future()
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n\n🛑 Stopping Babelfish...")
    finally:
        shutdown_event.set()
        streamer.stop()
        # Wait for STT thread to finish
        await stt_task
        print("✅ Shutdown complete.")


def main():
    import openwakeword

    available_ww = list(openwakeword.MODELS.keys())

    parser = argparse.ArgumentParser(
        description="Babelfish STT - High-performance streaming transcription"
    )

    parser.add_argument(
        "--double-pass", action="store_true", help="Enable two-pass refinement system"
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
        help="Enable stop-word deactivation (e.g. 'stop talking')",
    )

    args = parser.parse_args()

    # 1. Hardware First Probe

    hw = HardwareManager().probe()

    if args.wakeword == "LIST_OPTIONS" or (
        args.wakeword and args.wakeword not in available_ww
    ):
        if args.wakeword != "LIST_OPTIONS" and args.wakeword is not None:
            print(f"\n❌ Error: '{args.wakeword}' is not a valid wake-word.")

        print("\n📋 Available wake-words:")

        for ww in available_ww:
            print(f"  - {ww}")

        print("\nUsage example: uv run babelfish --wakeword hey_jarvis\n")

        sys.exit(0)

    try:
        asyncio.run(
            run_babelfish(
                hw=hw,
                double_pass=args.double_pass,
                wakeword=args.wakeword,
                stopword=args.stopword,
                force_cpu=args.cpu,
            )
        )

    except KeyboardInterrupt:
        pass  # Handled in run_babelfish or implicit
