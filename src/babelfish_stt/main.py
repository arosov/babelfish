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
from babelfish_stt.hardware import get_gpu_info, list_microphones, find_best_microphone
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

def start_server_thread(config_manager):
    """Starts the WebTransport server in a separate thread/loop."""
    def run():
        async def _serve():
            server = BabelfishServer(config_manager)
            await server.start()
        
        # New loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_serve())
        except Exception as e:
            logging.error(f"Server thread failed: {e}")
        finally:
            loop.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t

def run_babelfish(double_pass: bool = False, wakeword: str = None, stopword: str = None, force_cpu: bool = False):
    """
    Main loop for Babelfish STT, delegating to pipeline handlers.
    """
    print("\n" + "="*50)
    print("🚀 BABELFISH STT INITIALIZING")
    
    # 0. Load Configuration & Start Server
    config_manager = ConfigManager()
    server_thread = start_server_thread(config_manager)
    print(f"   SERVER: WebTransport running on https://{config_manager.config.server.host}:{config_manager.config.server.port}/config")

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
    print("="*50)
    
    # 1. Hardware Detection
    hw_info = get_gpu_info()
    device = "cpu" if force_cpu else ("cuda" if hw_info['cuda_available'] else "cpu")
    best_mic_idx = find_best_microphone()
    
    # 2. Initialize VAD (Fast)
    vad = SileroVAD()
    
    # 3. Initialize STT Engine (Steady)
    engine = STTEngine(device=device)
    
    # 4. Initialize Wake-Word Engine if needed
    ww_engine = None
    if wakeword:
        ww_engine = WakeWordEngine(model_name=wakeword)
    
    # 5. Initialize Audio & Display (Using detected best mic)
    streamer = AudioStreamer(device_index=best_mic_idx)
    display = TerminalDisplay()
    
    # 6. Report
    print("\n" + "-"*50)
    print("HARDWARE & CONFIGURATION REPORT")
    print(f"  Acceleration: {'GPU' if hw_info['cuda_available'] and not force_cpu else 'CPU'} ({device})")
    print(f"  STT Engine:   {engine.model_name}")
    print(f"  STT Preset:   {engine.preset}")
    print(f"  Audio Input:  [{streamer.device_index}] {streamer.mic_name}")
    if streamer.needs_resampling:
        print(f"  Resampling:   {streamer.native_rate}Hz -> {streamer.target_rate}Hz (soxr)")
    print("-"*50 + "\n")
    
    # 7. Initialize Pipeline
    if double_pass:
        pipeline = DoublePassPipeline(vad, engine, display)
    else:
        pipeline = SinglePassPipeline(vad, engine, display)
    
    if stopword:
        pipeline.stop_detector = StopWordDetector(stop_words=[stopword])
    
    if ww_engine:
        pipeline.set_idle(True)
        print(f"💤 IDLE: Waiting for wake-word '{wakeword}'...")
        last_score_time = time.time()
        max_score_recent = 0.0
    else:
        print("🎤 Listening... (Press Ctrl+C to stop)\n")
    
    cooldown_until = 0
    
    try:
        # Loop over 32ms chunks (512 samples)
        for chunk in streamer.stream(chunk_size=512):
            now = time.time()
            now_ms = now * 1000
            
            if now < cooldown_until:
                # In cooldown, skip processing to avoid echo/loop triggers
                continue

            if pipeline.is_idle and ww_engine:
                # In IDLE mode, only run Wake-Word detection
                prediction = ww_engine.process_chunk(chunk)
                score = prediction.get(wakeword, 0)
                
                if score > max_score_recent:
                    max_score_recent = score

                # Every 1 second, print the max score seen to give feedback
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
                # In LISTENING mode, run STT pipeline
                transitioned = pipeline.process_chunk(chunk, now_ms)
                if transitioned and pipeline.is_idle:
                    logging.info(f"Stop-word '{stopword}' detected, transitioning to IDLE")
                    print(f"\n🛑 STOP-WORD DETECTED: '{stopword}'")
                    
                    if ww_engine:
                        ww_engine.reset()
                        # Draining the streamer helps clear any "stop word" audio 
                        # that might still be in the resampler/queue.
                        streamer.drain()
                        # Set a 1.5s cooldown to prevent immediate re-activation
                        cooldown_until = now + 1.5
                        print(f"💤 IDLE: Waiting for wake-word '{wakeword}'... (1.5s cooldown)")
                    else:
                        print("🛑 Stopped.")
                        
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping Babelfish...")
    finally:
        streamer.stop()
        print("✅ Shutdown complete.")

def main():
    import openwakeword
    # In 0.6.0, the dictionary is upper-case MODELS in the root module
    available_ww = list(openwakeword.MODELS.keys())
    
    parser = argparse.ArgumentParser(description="Babelfish STT - High-performance streaming transcription")
    parser.add_argument("--double-pass", action="store_true", help="Enable two-pass refinement system")
    parser.add_argument("--cpu", action="store_true", help="Force CPU execution even if GPU is available")
    parser.add_argument("--wakeword", type=str, nargs='?', const='LIST_OPTIONS', help=f"Enable wake-word activation. Available: {', '.join(available_ww)}")
    parser.add_argument("--stopword", type=str, help="Enable stop-word deactivation (e.g. 'stop talking')")
    args = parser.parse_args()
    
    if args.wakeword == 'LIST_OPTIONS' or (args.wakeword and args.wakeword not in available_ww):
        if args.wakeword != 'LIST_OPTIONS' and args.wakeword is not None:
            print(f"\n❌ Error: '{args.wakeword}' is not a valid wake-word.")
        print("\n📋 Available wake-words:")
        for ww in available_ww:
            print(f"  - {ww}")
        print("\nUsage example: uv run babelfish --wakeword hey_jarvis\n")
        sys.exit(0)
    
    run_babelfish(
        double_pass=args.double_pass,
        wakeword=args.wakeword,
        stopword=args.stopword,
        force_cpu=args.cpu
    )

if __name__ == "__main__":
    main()