import sys
import os
import logging
import numpy as np
import time
import argparse
import threading
import asyncio
from typing import Optional, List, Any
from babelfish_stt.hardware import HardwareManager
from babelfish_stt.engine import STTEngine
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.display import TerminalDisplay, ServerDisplay, MultiDisplay
from babelfish_stt.vad import SileroVAD
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.server import BabelfishServer
from babelfish_stt.wakeword import WakeWordEngine
from babelfish_stt.pipeline import StandardPipeline, StopWordDetector


def run_stt_loop(streamer, pipeline, ww_engine, wakeword, shutdown_event):
    """Main blocking loop for audio capture and processing."""
    try:
        print("\n🎤 STT Loop Started")
        print("-" * 50)

        is_idle = wakeword is not None
        pipeline.set_idle(is_idle)

        if is_idle:
            print(f"💤 IDLE: Waiting for wake-word '{wakeword}'...")
        else:
            print("\n🎤 Listening... (Press Ctrl+C to stop)\n")

        cooldown_until = 0

        for chunk in streamer.stream():
            if shutdown_event.is_set():
                break

            now = time.time()
            now_ms = now * 1000

            if is_idle:
                # In idle mode, only run WakeWord engine
                if now < cooldown_until:
                    continue

                if ww_engine and ww_engine.detect(chunk):
                    print(f"✨ WAKEWORD '{wakeword}' DETECTED!")
                    is_idle = False
                    pipeline.set_idle(False)
                    # Clear any old audio from streamer to start fresh
                    streamer.drain()
            else:
                # In active mode, process chunk through pipeline
                state_changed = pipeline.process_chunk(chunk, now_ms)

                if state_changed:
                    # Pipeline reported a transition (e.g., stop word detected)
                    if wakeword:
                        is_idle = True
                        pipeline.set_idle(True)
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
    wakeword: Optional[str] = None,
    stopword: Optional[str] = None,
    force_cpu: bool = False,
):
    print("\n" + "=" * 50, flush=True)
    print("🚀 BABELFISH STT INITIALIZING", flush=True)

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

    if wakeword:
        config_manager.config.voice.wakeword = wakeword
    if stopword:
        if stopword not in config_manager.config.voice.stop_words:
            config_manager.config.voice.stop_words.append(stopword)

    print("   MODE: Standard Recital")
    print(f"   DEVICE: {config_manager.config.hardware.device.upper()}")

    if config_manager.config.voice.wakeword:
        print(f"   WAKE-WORD: {config_manager.config.voice.wakeword}")
    if config_manager.config.voice.stop_words:
        print(f"   STOP-WORDS: {', '.join(config_manager.config.voice.stop_words)}")

    # 3. Start Server Early (Async)
    server = BabelfishServer(config_manager)
    config_manager.register(server)

    await server.start()
    print(
        f"   SERVER: WebSockets running on ws://{config_manager.config.server.host}:{config_manager.config.server.port}/config"
    )

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

        # 5. Hardware Self-Calibration
        if config_manager.config.pipeline.performance.tier == "auto":
            await server.broadcast_bootstrap_status("Calibrating Performance...")
            perf_data = await asyncio.to_thread(engine.benchmark)
            config_manager.update({"pipeline": {"performance": perf_data}})
            print(f"✅ Performance calibrated: {perf_data['tier'].upper()}")

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

        display = MultiDisplay(TerminalDisplay(), ServerDisplay(server))
        pipeline = StandardPipeline(vad, engine, display)

        if config_manager.config.voice.stop_words:
            pipeline.stop_detector = StopWordDetector(
                stop_words=config_manager.config.voice.stop_words
            )

        return vad, engine, ww_engine, streamer, display, pipeline

    print("⏳ Loading engines and models (this may take a few seconds)...", flush=True)
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
    print("✅ Initialization complete.", flush=True)

    # 3. Start STT Loop in Background Thread
    shutdown_event = threading.Event()
    loop = asyncio.get_running_loop()

    stt_task = loop.run_in_executor(
        None,
        run_stt_loop,
        streamer,
        pipeline,
        ww_engine,
        config_manager.config.voice.wakeword,
        shutdown_event,
    )

    try:
        await asyncio.Future()
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n\n🛑 Stopping Babelfish...")
    finally:
        shutdown_event.set()
        streamer.stop()
        await stt_task
        print("✅ Shutdown complete.")


def main():
    import openwakeword

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
        print("\nAvailable Wake-words:")
        for ww in available_ww:
            print(f"  - {ww}")
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
