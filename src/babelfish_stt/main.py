import sys
import logging
import numpy as np
import time
import argparse
from babelfish_stt.hardware import get_gpu_info, list_microphones, find_best_microphone
from babelfish_stt.engine import STTEngine
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.display import TerminalDisplay
from babelfish_stt.vad import SileroVAD
from babelfish_stt.pipeline import SinglePassPipeline, DoublePassPipeline, StopWordDetector
from babelfish_stt.wakeword import WakeWordEngine

# Configure logging
logging.basicConfig(level=logging.ERROR)

def run_babelfish(double_pass: bool = False, wakeword: str = None, stopword: str = None):
    """
    Main loop for Babelfish STT, delegating to pipeline handlers.
    """
    print("\n" + "="*50)
    print("🚀 BABELFISH STT INITIALIZING")
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
    device = "cuda" if hw_info['cuda_available'] else "cpu"
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
    print(f"  Acceleration: {'GPU' if hw_info['cuda_available'] else 'CPU'} ({device})")
    print(f"  STT Engine:   {engine.model_name}")
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
    else:
        print("🎤 Listening... (Press Ctrl+C to stop)\n")
    
    try:
        # Loop over 32ms chunks (512 samples)
        for chunk in streamer.stream(chunk_size=512):
            now_ms = time.time() * 1000
            
            if pipeline.is_idle and ww_engine:
                # In IDLE mode, only run Wake-Word detection
                prediction = ww_engine.process_chunk(chunk)
                if prediction.get(wakeword, 0) > 0.5:
                    print(f"\n✨ WAKE-WORD DETECTED: '{wakeword}'")
                    print("🎤 Listening... (Press Ctrl+C to stop)\n")
                    pipeline.set_idle(False)
            else:
                # In LISTENING mode, run STT pipeline
                transitioned = pipeline.process_chunk(chunk, now_ms)
                if transitioned and pipeline.is_idle:
                    print(f"\n🛑 STOP-WORD DETECTED: '{stopword}'")
                    print(f"💤 IDLE: Waiting for wake-word '{wakeword}'..." if ww_engine else "🛑 Stopped.")
                    if not ww_engine:
                        # If no wake-word is configured but stop-word is hit, 
                        # maybe we should just exit or wait for user?
                        # For now, if no WW, it stays in IDLE (silent) until Ctrl+C.
                        pass
                        
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping Babelfish...")
    finally:
        streamer.stop()
        print("✅ Shutdown complete.")

def main():
    parser = argparse.ArgumentParser(description="Babelfish STT - High-performance streaming transcription")
    parser.add_argument("--double-pass", action="store_true", help="Enable two-pass refinement system")
    parser.add_argument("--wakeword", type=str, help="Enable wake-word activation (e.g. 'hey_jarvis')")
    parser.add_argument("--stopword", type=str, help="Enable stop-word deactivation (e.g. 'stop talking')")
    args = parser.parse_args()
    
    run_babelfish(
        double_pass=args.double_pass,
        wakeword=args.wakeword,
        stopword=args.stopword
    )

if __name__ == "__main__":
    main()