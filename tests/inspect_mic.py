import sounddevice as sd
import argparse

def inspect_microphone(index=None):
    print("\nMICROPHONE INSPECTOR")
    
    try:
        print(f"System Default (In, Out): {sd.default.device}")
        
        if index is None:
            index = sd.default.device[0]
            print(f"No index provided, using default input: {index}")
            
        info = sd.query_devices(index)
        
        print("\nFULL DEVICE METADATA:")
        for key, value in info.items():
            print(f"  {key:<25}: {value}")
            
        try:
            sd.check_input_settings(device=index, samplerate=16000, channels=1)
            print("\n16kHz Mono Support: YES")
        except Exception as e:
            print(f"\n16kHz Mono Support: NO ({e})")

    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=None)
    args = parser.parse_args()
    inspect_microphone(args.device)