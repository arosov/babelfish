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

# Configure logging
logging.basicConfig(level=logging.ERROR)

def run_babelfish(double_pass: bool = False):
    """
    Main VAD-driven segmented loop for Babelfish STT.
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
    
    # 6. Stateful Loop Variables
    active_buffer = []
    last_speech_time = 0
    is_speaking = False
    silence_threshold_ms = 700 # Time to wait before finalizing
    update_interval_samples = 3200 # Update display every 200ms of speech
    last_update_size = 0
    
    print("🎤 Listening... (Press Ctrl+C to stop)\n")
    
    try:
        # Loop over 32ms chunks (512 samples)
        for chunk in streamer.stream(chunk_size=512):
            now = time.time() * 1000 # ms
            
            if vad.is_speech(chunk):
                if not is_speaking:
                    is_speaking = True
                    # Optional: pre-pend some context?
                
                active_buffer.append(chunk)
                last_speech_time = now
                
                # Update display periodically while speaking
                current_size = sum(len(c) for c in active_buffer)
                if current_size - last_update_size >= update_interval_samples:
                    full_audio = np.concatenate(active_buffer)
                    text = engine.transcribe(full_audio)
                    if text:
                        display.update(text)
                    last_update_size = current_size
            else:
                # Silence detected
                if is_speaking:
                    active_buffer.append(chunk) # Add some silence context
                    
                    # If we've been silent long enough, finalize
                    if now - last_speech_time > silence_threshold_ms:
                        full_audio = np.concatenate(active_buffer)
                        text = engine.transcribe(full_audio)
                        if text:
                            display.finalize(text)
                        
                        # Reset for next sentence
                        active_buffer = []
                        last_update_size = 0
                        is_speaking = False
                        vad.reset_states()
                        
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