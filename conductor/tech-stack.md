# Tech Stack - Babelfish

## Core Backend
- **Language:** Python 3.12 (Pinned to 3.12.*)
- **Package Management & Distribution:** `uv`
- **Communication Protocol:** WebTransport

## Pipeline Engines
- **Speech-to-Text (Primary):** [parakeet-stream](https://github.com/maximerivest/parakeet-stream)
  - **NeMo Toolkit:** >=2.6.2 (Required for `StreamingBatchedAudioBuffer`)
  - **PyTorch:** >=2.6.0
  - **CUDA Python:** >=12.3 (For optimized decoding speed)
- **Speech-to-Text (Orchestration):** Custom two-pass system using Parakeet's instant preset switching.
  - **Presets:** 'realtime' for Ghost pass, 'balanced' for Anchor pass.
- **Wake-Word Detection:** [openWakeWord](https://github.com/dscripka/openWakeWord) (ONNX-based).
- **Stop-Word Detection:** Custom text-based strict matching logic.
- **Voice Activity Detection (VAD):** Integrated via `parakeet-stream`'s native loop.
- **Audio Input:** `sounddevice` for real-time microphone capture.
- **Large Language Model (LLM):** *TBD* (Phase 3 integration).

## Known Compatibility Fixes
- **PyArrow:** Pinned to `<19.0.0` to ensure compatibility with `datasets` 2.14.4.

## Hardware & OS Targets
- **Platforms:** Windows (Windows Services), Linux (Systemd).
- **Acceleration:** NVIDIA CUDA (Primary target).

## Distribution & Orchestration
- **Launcher:** Custom Python scripts invoked via `uv run`.
  - **CLI Flags:** `--double-pass`, `--wakeword`, `--stopword`, `--cpu`.
- **Service Management:** Designed for integration with Kotlin-based frontend controller.