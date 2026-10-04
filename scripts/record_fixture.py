"""Record a dictation fixture WAV for the replay harness (Phase 0 of the
Ghost fixing plan).

Records the default (or named) microphone from the moment the script starts
until you press ENTER, at the Babelfish capture rate (16 kHz mono), using the
same sounddevice + soxr resampling path as AudioStreamer so the fixture is
faithful to real capture.

Usage:
    python scripts/record_fixture.py                     # default mic, writes tests/fixtures/dictation_fr.wav
    python scripts/record_fixture.py -o my_take.wav      # different output file
    python scripts/record_fixture.py --list-devices      # show input devices and exit
    python scripts/record_fixture.py -m "SteelSeries"    # mic by (partial) name
    python scripts/record_fixture.py --seconds 40        # fixed duration instead of ENTER

Speak the target paragraph (the French mediatheque text) at your natural
pace, with the same pauses as the failing ./scripts/run.bat --type run.
"""

import argparse
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

try:
    import soxr
except ImportError:
    soxr = None

TARGET_RATE = 16000
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "tests" / "fixtures" / "dictation_fr.wav"


def list_input_devices() -> None:
    print("Input devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']}  (default rate {d['default_samplerate']})")
    print(f"\nDefault input: {sd.default.device[0]}")


def find_device(name_substring: str):
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and name_substring.lower() in d["name"].lower():
            return i
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="output WAV path")
    ap.add_argument(
        "-m", "--mic", default=None, help="input device by (partial) name"
    )
    ap.add_argument(
        "--seconds", type=float, default=None,
        help="record a fixed duration instead of waiting for ENTER",
    )
    ap.add_argument(
        "--list-devices", action="store_true", help="list input devices and exit"
    )
    args = ap.parse_args()

    if args.list_devices:
        list_input_devices()
        return 0

    device = sd.default.device[0]
    if args.mic:
        found = find_device(args.mic)
        if found is None:
            print(f"ERROR: no input device matching {args.mic!r}", file=sys.stderr)
            list_input_devices()
            return 2
        device = found

    info = sd.query_devices(device, "input")
    native_rate = int(info["default_samplerate"])
    needs_resample = native_rate != TARGET_RATE and soxr is not None

    chunks: list[np.ndarray] = []

    def callback(indata, frames, time_info, status):
        if status:
            print(f"(callback status: {status})")
        chunks.append(indata.copy().flatten())

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Device: [{device}] {info['name']}")
    print(f"Recording at {native_rate} Hz"
          + (f" -> resample to {TARGET_RATE} Hz" if needs_resample else " (native match)"))
    print("Speak now. Press ENTER to stop"
          + ("" if args.seconds is None else f" (auto-stop after {args.seconds:.0f}s)"))
    print()

    with sd.InputStream(
        samplerate=native_rate,
        channels=1,
        dtype="float32",
        device=device,
        callback=callback,
        blocksize=int(native_rate * 0.032),  # ~32 ms blocks, like the app's chunks
    ):
        import threading
        import time

        stop_flag = threading.Event()
        if args.seconds is None:
            threading.Thread(
                target=lambda: (input(), stop_flag.set()), daemon=True
            ).start()
            while not stop_flag.is_set():
                time.sleep(0.1)
        else:
            deadline = time.time() + args.seconds
            while time.time() < deadline:
                time.sleep(0.1)

    audio = np.concatenate(chunks).flatten()
    if needs_resample:
        audio = soxr.resample(audio, native_rate, TARGET_RATE)
    audio = np.clip(audio, -1.0, 1.0)

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    duration = audio.size / TARGET_RATE
    print()
    print(f"Recorded {duration:.1f}s, peak level {peak:.2f}")
    if peak < 0.02:
        print("WARNING: peak is near silence - mic may be muted or wrong device.")
        print("Recording NOT saved; re-run with --list-devices to pick the mic.")
        return 3

    pcm16 = (audio * 32767.0).astype("<i2")
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_RATE)
        wf.writeframes(pcm16.tobytes())
    print(f"Wrote {out_path} ({pcm16.nbytes / 1024:.0f} KiB, {TARGET_RATE} Hz mono)")
    print("Hand this path to the replay harness / next session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
