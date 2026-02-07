import sys
import logging
from babelfish_stt.hardware import get_gpu_info, list_microphones
from babelfish_stt.engine import STTEngine
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.display import TerminalDisplay

# Configure logging
logging.basicConfig(level=logging.ERROR)

def run_babelfish():
    """
    Main orchestration loop for Babelfish STT.
    """
    print("\n" + "="*50)
    print("🚀 BABELFISH STT INITIALIZING")
    print("="*50)
    
    # 1. Hardware & Environment Detection
    hw_info = get_gpu_info()
    device = "cuda" if hw_info['cuda_available'] else "cpu"
    mics = list_microphones()
    
    # 2. Initialize STT Engine (Loads model)
    engine = STTEngine(device=device)
    
    # 3. Initialize Audio (Auto-selects default)
    streamer = AudioStreamer()
    default_mic_name = next((m['name'] for m in mics if m['index'] == streamer.device_index), "Unknown")
    
    # 4. Final Configuration Report
    print("\n" + "-"*50)
    print("HARDWARE & CONFIGURATION REPORT")
    print(f"  Acceleration: {'GPU' if hw_info['cuda_available'] else 'CPU'} ({device})")
    if hw_info['cuda_available']:
        print(f"  GPU Device:   {hw_info['name']}")
        print(f"  Total VRAM:   {hw_info['vram_gb']:.2f} GB")
    
    print(f"  STT Engine:   {engine.model_name}")
    print(f"  Audio Input:  [{streamer.device_index}] {default_mic_name}")
    print("-"*50 + "\n")
    
    display = TerminalDisplay()
    print("🎤 Listening... (Press Ctrl+C to stop)\n")
    
    try:
        # 4. Orchestrate streaming
        for audio_chunk in streamer.stream():
            # Get segments from engine
            for segment in engine.transcribe_stream(audio_chunk):
                if segment.text.strip():
                    display.update(segment.text.strip())
                    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping Babelfish...")
    finally:
        streamer.stop()
        print("✅ Shutdown complete.")

if __name__ == "__main__":
    run_babelfish()
