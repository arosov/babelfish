import sys
import os

# --- HOTFIX: Force NeMo/Parakeet extraction to disk ---
# The default /tmp (tmpfs) is too small (16GB) for unpacking large .nemo models.
# We redirect temporary files to a local 'tmp_extraction' folder on the physical disk.
_project_root = os.getcwd()
_tmp_dir = os.path.join(_project_root, "tmp_extraction")
os.makedirs(_tmp_dir, exist_ok=True)
os.environ["TMPDIR"] = _tmp_dir
# ------------------------------------------------------

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
from babelfish_stt.pipeline import SinglePassPipeline, DoublePassPipeline, StopWordDetector
from babelfish_stt.wakeword import WakeWordEngine
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.server import BabelfishServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logging.getLogger("babelfish_stt.server").setLevel(logging.DEBUG)
def run_stt_loop(streamer, pipeline, ww_engine, wakeword, stopword, shutdown_event):
    """
    Blocking STT loop to be run in a separate thread.
    """
    print("\n" + "-"*50)
    print("HARDWARE & CONFIGURATION REPORT")
    # ... (Hardware report moved here or kept in main, passing necessary info)
    # We'll just print status here
    print("🎤 STT Loop Started")
    print("-"*50 + "\n")
    
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
        for chunk in streamer.stream(chunk_size=512):
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
                    sys.stdout.write(f"\r   [Max confidence in last 1s: {max_score_recent:.2f}]   ")
                    sys.stdout.flush()
                    max_score_recent = 0.0
                    last_score_time = now

                if score > 0.5:
                    logging.info(f"Wake-word '{wakeword}' detected with score {score:.2f}")
                    print(f"\n\n✨ WAKE-WORD DETECTED: '{wakeword}' (score: {score:.2f})")
                    print("🎤 Listening... (Press Ctrl+C to stop)\n")
                    pipeline.set_idle(False)
            else:
                transitioned = pipeline.process_chunk(chunk, now_ms)
                if transitioned and pipeline.is_idle:
                    logging.info(f"Stop-word '{stopword}' detected, transitioning to IDLE")
                    print(f"\n🛑 STOP-WORD DETECTED: '{stopword}'")
                    
                    if ww_engine:
                        ww_engine.reset()
                        streamer.drain()
                        cooldown_until = now + 1.5
                        print(f"💤 IDLE: Waiting for wake-word '{wakeword}'... (1.5s cooldown)")
                    else:
                        print("🛑 Stopped.")
                        
    except Exception as e:
        logging.error(f"Error in STT loop: {e}")
    finally:
        print("✅ STT Loop Shutdown.")

async def run_babelfish(hw: HardwareManager, double_pass: bool = False, wakeword: str = None, stopword: str = None, force_cpu: bool = False):
    print("\n" + "="*50)
    print("🚀 BABELFISH STT INITIALIZING")
    
    # 0. Load Configuration
    config_manager = ConfigManager()
    
    if force_cpu:
        print("   MODE: Force CPU Execution")
    if double_pass:
        print("   MODE: Double-Pass Refinement")
    else:
        print("   MODE: Single-Pass (Default)")
    
    if wakeword:
        print(f"   WAKE-WORD: {wakeword}")
    if stopword:
        print(f"   STOP-WORD: {stopword}")
    
    # 1. Start Server Early (Async)
    server = BabelfishServer(config_manager)
    config_manager.register(server)
    
    await server.start()
    print(f"   SERVER: WebTransport running on https://{config_manager.config.server.host}:{config_manager.config.server.port}/config")
    print("="*50)
    
    # 2. Hardware & Engine Init (Heavy/Blocking)
    def heavy_init():
        device = "cpu" if force_cpu else ("cuda" if hw.gpu_info['cuda_available'] else "cpu")
        best_mic_idx = hw.best_mic_index
        
        vad = SileroVAD()
        engine = STTEngine(device=device)
        
        ww_engine = None
        if wakeword:
            ww_engine = WakeWordEngine(model_name=wakeword)
        
        streamer = AudioStreamer(device_index=best_mic_idx)
        display = TerminalDisplay()
        
        # Pipeline
        if double_pass:
            pipeline = DoublePassPipeline(vad, engine, display)
        else:
            pipeline = SinglePassPipeline(vad, engine, display)
        
        if stopword:
            pipeline.stop_detector = StopWordDetector(stop_words=[stopword])
            
        return vad, engine, ww_engine, streamer, display, pipeline

    print("⏳ Loading engines and models (this may take a few seconds)...")
    vad, engine, ww_engine, streamer, display, pipeline = await asyncio.to_thread(heavy_init)

    # Link pipeline to server and register remaining components for hot-reloading
    server.pipeline = pipeline
    config_manager.register(vad)
    config_manager.register(engine)
    config_manager.register(pipeline)
    if pipeline.stop_detector:
        config_manager.register(pipeline.stop_detector)

    print("✅ Initialization complete.")

    # 3. Start STT Loop in Background Thread
    shutdown_event = threading.Event()
    loop = asyncio.get_running_loop()
    
    # We run the STT loop in a separate thread executor
    stt_task = loop.run_in_executor(
        None, 
        run_stt_loop, 
        streamer, pipeline, ww_engine, wakeword, stopword, shutdown_event
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

    

    parser = argparse.ArgumentParser(description="Babelfish STT - High-performance streaming transcription")

    parser.add_argument("--double-pass", action="store_true", help="Enable two-pass refinement system")

    parser.add_argument("--cpu", action="store_true", help="Force CPU execution even if GPU is available")

    parser.add_argument("--wakeword", type=str, nargs='?', const='LIST_OPTIONS', help=f"Enable wake-word activation. Available: {', '.join(available_ww)}")

    parser.add_argument("--stopword", type=str, help="Enable stop-word deactivation (e.g. 'stop talking')")

    args = parser.parse_args()

    

    # 1. Hardware First Probe

    hw = HardwareManager().probe()



    if args.wakeword == 'LIST_OPTIONS' or (args.wakeword and args.wakeword not in available_ww):

        if args.wakeword != 'LIST_OPTIONS' and args.wakeword is not None:

            print(f"\n❌ Error: '{args.wakeword}' is not a valid wake-word.")

        print("\n📋 Available wake-words:")

        for ww in available_ww:

            print(f"  - {ww}")

        print("\nUsage example: uv run babelfish --wakeword hey_jarvis\n")

        sys.exit(0)

    

    try:

        asyncio.run(run_babelfish(

            hw=hw,

            double_pass=args.double_pass,

            wakeword=args.wakeword,

            stopword=args.stopword,

            force_cpu=args.cpu

        ))

    except KeyboardInterrupt:

        pass # Handled in run_babelfish or implicit
