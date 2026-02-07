# Whisper Model VRAM Usage (faster-whisper)

The following estimates are for **faster-whisper** using **float16** or **int8** quantization on NVIDIA GPUs. Note that VRAM usage can increase based on batch size and audio duration.

| Model | Quantization | VRAM Usage (GB) | Recommended VRAM (Total) |
| :--- | :--- | :--- | :--- |
| **tiny** | int8 / float16 | ~0.4 - 0.5 | 2 GB |
| **base** | int8 / float16 | ~0.5 - 0.7 | 2 GB |
| **small** | int8 / float16 | ~1.0 - 1.5 | 4 GB |
| **medium** | int8 / float16 | ~2.5 - 3.0 | 6 GB |
| **large-v3-turbo** | float16 | ~3.5 - 4.5 | 8 GB |
| **large-v3** | float16 | ~5.0 - 6.0 | 10 GB+ |

### Quantization Notes:
- **float16**: Recommended for all NVIDIA GPUs (Pascal architecture and newer, e.g., GTX 10-series, RTX 20/30/40-series).
- **int8_float16**: Further reduces VRAM slightly and improves speed on some architectures with minimal accuracy loss.
- **int8**: Best for CPU-based inference or very low-memory environments.

### System Overhead:
Always leave at least **1.5 - 2.0 GB** of VRAM free for the operating system and background processes to avoid Out-of-Memory (OOM) errors.
