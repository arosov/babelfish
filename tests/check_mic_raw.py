import sounddevice as sd
import numpy as np
import argparse

def check_raw_data(device_index):
    print(f"Checking device {device_index}")
    duration = 5
    for fs in [16000, 44100, 48000]:
        try:
            print(f"Trying {fs}Hz...")
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, device=device_index)
            sd.wait()
            max_val = np.max(np.abs(recording))
            print(f"Max abs value at {fs}Hz: {max_val}")
            if max_val > 0:
                print(f"SUCCESS at {fs}Hz")
                return
        except Exception as e:
            print(f"Failed at {fs}Hz: {e}")
    print("RESULT: ALL SILENT OR FAILED")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=1)
    args = parser.parse_args()
    check_raw_data(args.device)
