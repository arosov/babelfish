import sys
import logging
from babelfish_stt.hardware import get_gpu_info
from babelfish_stt.engine import STTEngine
from babelfish_stt.audio import AudioStreamer
from babelfish_stt.display import TerminalDisplay

# Configure logging
logging.basicConfig(level=logging.ERROR)

def run_babelfish():
    """
    Main orchestration loop for Babelfish STT.
    """
    print("🚀 Babelfish STT Initializing...")
    
    # 1. Hardware Detection
    hw_info = get_gpu_info()
    device = "cuda" if hw_info['cuda_available'] else "cpu"
    print(f"💻 Hardware: {hw_info['name'] if hw_info['name'] else 'CPU'} (using {device})")
    
    # 2. Initialize STT Engine
    engine = STTEngine(device=device)
    
    # 3. Initialize Audio and Display
    streamer = AudioStreamer()
    display = TerminalDisplay()
    
    print("\n🎤 Listening... (Press Ctrl+C to stop)\n")
    
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
