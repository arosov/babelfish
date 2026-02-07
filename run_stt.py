import os
import sys
import signal
import logging
import torch
import time
from RealtimeSTT import AudioToTextRecorder
from hardware_manager import HardwareManager
from config_manager import ConfigManager, ServerConfig
from typer_manager import TyperManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("babelfish.main")

def main():
    print("\n--- Babelfish Server Launcher ---")
    
    # Initialize Managers
    hw = HardwareManager()
    cfg_manager = ConfigManager()
    typer = TyperManager()
    
    # Try to load config from file
    config = cfg_manager.load_config()
    
    if config:
        logger.info(f"Loaded configuration from file: {config.dict()}")
        selected_model = config.model
        device = config.device
        input_device_index = config.input_device_index
        wake_word = config.wake_word
        realtime_model_type = config.realtime_model_type
        language = config.language
        auto_type = config.auto_type
        # Use quantization from config as primary compute option
        compute_options = [config.quantization, "int8", "float32"]
    else:
        logger.info("No config file found. Falling back to hardware detection.")
        hw.log_system_info()
        selected_model = hw.get_recommended_model()
        device = "cuda" if hw.accel_type in ["nvidia", "amd"] else "cpu"
        input_device_index = None # Will use default
        wake_word = None
        realtime_model_type = "tiny"
        language = ""
        auto_type = False
        compute_options = ["float16", "int8_float16", "int8", "float32"]
        if device == "cpu":
            compute_options = ["int8", "float32"]
    
    recorder = None

    def text_detected(text):
        print(f"\rRealtime: {text}", end="", flush=True)

    def stabilized_text_detected(text):
        # Disabled realtime typing for now to ensure stability
        # if auto_type:
        #     typer.type_delta(text)
        pass

    def on_wakeword():
        print(f"\n[EVENT] Wake word '{wake_word}' detected! Recording...\n")

    for ctype in compute_options:
        try:
            logger.info(f"Attempting initialization: model={selected_model}, realtime_model_type={realtime_model_type}, device={device}, quantization={ctype}, input_device={input_device_index}, wake_word={wake_word}, language={language}, auto_type={auto_type}")
            
            recorder_args = {
                "model": selected_model,
                "realtime_model_type": realtime_model_type,
                "device": device,
                "input_device_index": input_device_index,
                "compute_type": ctype,
                "language": language,
                "enable_realtime_transcription": True,
                "use_main_model_for_realtime": False, # Explicitly use separate model for realtime if configured
                "on_realtime_transcription_update": text_detected,
                "on_realtime_transcription_stabilized": stabilized_text_detected,
                "on_wakeword_detected": on_wakeword,
                "spinner": False
            }

            if wake_word:
                recorder_args["wakeword_backend"] = "pvporcupine"
                recorder_args["wake_words"] = wake_word

            recorder = AudioToTextRecorder(**recorder_args)
            logger.info(f"Successfully initialized with {ctype}!")
            break
        except Exception as e:
            logger.error(f"Failed with {ctype}: {e}")
            continue

    if not recorder:
        logger.error("Could not initialize recorder with any compute type.")
        return

    # 3. Graceful Exit Handler
    def signal_handler(sig, frame):
        print("\n\nShutting down gracefully...")
        if recorder:
            try:
                recorder.shutdown()
            except:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    listen_msg = f"Model: {selected_model}"
    if wake_word:
        listen_msg += f" | Wake Word: {wake_word}"
    if auto_type:
        listen_msg += " | Auto-Type: ON"

    print(f"\n>>> LISTENING (Streaming Mode | {listen_msg}) <<<")
    print("Speak now. Finalized sentences will appear on new lines.\n")
    
    try:
        while True:
            # recorder.text() will wait for voice activation (or wake word if configured)
            # and then record until silence (or stop word if configured)
            text = recorder.text()
            if text:
                # If we have wake words, recorder.text() might be called multiple times
                # after a single wake word detection if we are in a loop.
                # In RealtimeSTT, recorder.text() handles the "listening" state.
                print(f"\nFinal: {text}\n", flush=True)
                if auto_type:
                    typer.type_text(text)
    except Exception as e:
        print(f"\nRuntime Error: {e}")
    finally:
        print("\nDiagnostic period finished.")
        if recorder:
            try:
                recorder.shutdown()
            except:
                pass

if __name__ == "__main__":
    main()