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
from babelfish_stt.pipeline import SinglePassPipeline, DoublePassPipeline

# Configure logging
logging.basicConfig(level=logging.ERROR)

def run_babelfish(double_pass: bool = False):
    """
    Main loop for Babelfish STT, delegating to pipeline handlers.
    """
    print("\n" + "="*50)
    print("🚀 BABELFISH STT INITIALIZING")
    if double_pass:
        print("   MODE: Double-Pass Refinement")
    else:
        print("   MODE: Single-Pass (Default)")
    print("="*50)
    
    # 1. Hardware Detection
    hw_info = get_gpu_info()
    device = "cuda" if hw_info['cuda_available'] else "cpu"
    best_mic_idx = find_best_microphone()
    
    # 2. Initialize VAD (Fast)
    vad = SileroVAD()
    
    # 3. Initialize STT Engine (Steady)
    engine = STTEngine(device=device)
    
    # 4. Initialize Audio & Display (Using detected best mic)
    streamer = AudioStreamer(device_index=best_mic_idx)
    display = TerminalDisplay()
    
    # 5. Report
    print("\n" + "-"*50)
    print("HARDWARE & CONFIGURATION REPORT")
    print(f"  Acceleration: {'GPU' if hw_info['cuda_available'] else 'CPU'} ({device})")
    print(f"  STT Engine:   {engine.model_name}")
    print(f"  Audio Input:  [{streamer.device_index}] {streamer.mic_name}")
    if streamer.needs_resampling:
        print(f"  Resampling:   {streamer.native_rate}Hz -> {streamer.target_rate}Hz (soxr)")
    print("-"*50 + "\n")
    
    # 6. Initialize Pipeline
    if double_pass:
        pipeline = DoublePassPipeline(vad, engine, display)
    else:
        pipeline = SinglePassPipeline(vad, engine, display)
    
    print("🎤 Listening... (Press Ctrl+C to stop)\n")
    
    try:
        # Loop over 32ms chunks (512 samples)
        for chunk in streamer.stream(chunk_size=512):
            now_ms = time.time() * 1000
            pipeline.process_chunk(chunk, now_ms)
                        
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping Babelfish...")
    finally:
        streamer.stop()
        print("✅ Shutdown complete.")

def main():
    parser = argparse.ArgumentParser(description="Babelfish STT - High-performance streaming transcription")
    parser.add_argument("--double-pass", action="store_true", help="Enable two-pass refinement system")
    args = parser.parse_args()
    
    run_babelfish(double_pass=args.double_pass)

if __name__ == "__main__":
    main()