import time
import numpy as np
import sys
import sounddevice as sd
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.vad import SileroVAD
from babelfish_stt.hardware import find_best_microphone

def test_vad_diagnostics(device_index=None):
    print("\n" + "="*50)
    print("🔍 VAD & AUDIO DIAGNOSTIC (15 SECONDS)")
    print("="*50)
    
    try:
        # 1. Initialize VAD
        vad = SileroVAD(threshold=0.3) # More sensitive for diagnostics
        
        # 2. Select Device
        if device_index is None:
            print("Auto-detecting best microphone...")
            device_index = find_best_microphone()
            
        # 3. Initialize Streamer (Native capturing + soxr resampling)
        streamer = AudioStreamer(device_index=device_index)
        
        print(f"\nSELECTED MICROPHONE:")
        print(f"  Index: {streamer.device_index}")
        print(f"  Name:  {streamer.mic_name}")
        print(f"  Native Hardware Rate: {streamer.native_rate}Hz")
        print(f"  Target Processing Rate: {streamer.target_rate}Hz")
        if streamer.needs_resampling:
            print(f"  Resampling: ACTIVE (soxr)")
        else:
            print(f"  Resampling: INACTIVE (native match)")
        
        print("\n🔴 LISTENING START - Please speak clearly now...")
        print("-" * 50)
        
        start_time = time.time()
        duration = 15
        speech_chunks = 0
        total_chunks = 0
        max_rms = 0
        
        # We use chunk_size=512 in the TARGET (16kHz) domain
        for chunk in streamer.stream(chunk_size=512):
            total_chunks += 1
            
            # 1. Check Signal Level (RMS)
            rms = np.sqrt(np.mean(chunk**2))
            max_rms = max(max_rms, rms)
            
            # 2. Check VAD
            is_speech = vad.is_speech(chunk)
            
            # 3. Visual Feedback
            level_val = int(rms * 100)
            level_bar = "█" * min(level_val, 20)
            status = "🔥 VOICE" if is_speech else "... silence"
            
            sys.stdout.write(f"\r[{status}] RMS: {rms:.4f} | Peak: {max_rms:.4f} | Level: {level_bar:<20} ")
            sys.stdout.flush()
            
            if is_speech:
                speech_chunks += 1
                
            if time.time() - start_time > duration:
                break
                
        print("\n" + "-"*50)
        print("🏁 DIAGNOSTIC COMPLETE")
        print(f"  Total 32ms Chunks: {total_chunks}")
        print(f"  Speech Chunks:     {speech_chunks}")
        print(f"  Highest Peak RMS:  {max_rms:.4f}")
        
        if max_rms < 0.0005:
            print("\n❌ CRITICAL: Microphone signal is too weak or silent.")
            print("Action: Check physical connection, system gain, or hardware mute.")
        elif speech_chunks == 0:
            print("\n⚠️  WARNING: Audio detected but VAD did not trigger.")
            print("Action: Try lowering threshold or check for high background noise.")
        else:
            print(f"\n✅ SUCCESS: Captured voice activity!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'streamer' in locals():
            streamer.stop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=None)
    args = parser.parse_args()
    test_vad_diagnostics(device_index=args.device)