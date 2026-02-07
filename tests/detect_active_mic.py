import sounddevice as sd
import numpy as np
import time
import sys

def probe_all_microphones():
    print("
🔍 ACTIVE SIGNAL PROBE")
    print("Please speak or make noise during the probe...
")
    
    devices = sd.query_devices()
    input_devices = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
    
    results = []
    
    for idx in input_devices:
        name = devices[idx]['name']
        # Skip weird virtual devices with 128 channels unless necessary
        if devices[idx]['max_input_channels'] > 32:
            continue
            
        print(f"  Testing [{idx}] {name}...", end="", flush=True)
        
        try:
            # Record 2 seconds
            fs = 16000
            duration = 2.0
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, device=idx)
            sd.wait()
            
            peak = np.max(np.abs(recording))
            rms = np.sqrt(np.mean(recording**2))
            
            results.append({
                'index': idx,
                'name': name,
                'peak': peak,
                'rms': rms
            })
            print(f" Peak: {peak:.4f} | RMS: {rms:.4f}")
            
        except Exception as e:
            print(f" Error: {e}")

    print("
" + "="*50)
    print("🏆 PROBE RESULTS (Sorted by signal strength)")
    print("-" * 50)
    
    # Sort by RMS (volume)
    results.sort(key=lambda x: x['rms'], reverse=True)
    
    for r in results[:5]:
        status = "✅ ACTIVE" if r['rms'] > 0.001 else "🔈 SILENT"
        print(f"{status} | Index {r['index']:<2} | RMS: {r['rms']:.4f} | {r['name']}")
    
    if results and results[0]['rms'] > 0.001:
        print(f"
Recommended device index: {results[0]['index']}")
    else:
        print("
❌ No active signal detected on any device.")

if __name__ == "__main__":
    probe_all_microphones()
