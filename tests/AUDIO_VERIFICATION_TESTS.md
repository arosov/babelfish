# Audio Verification Tests

## Overview

This document describes the audio-based verification system for testing the ghost text behavior in the Babelfish STT pipeline. The system enables automated verification of the input manager behavior using recorded audio files run through the real STT engine.

---

## Test Structure

### Test Files

| File | Description |
|------|-------------|
| `tests/test_ghost_text.py` | Main test file with ghost text behavior tests |
| `tests/audio_fixtures.py` | Test utility for running audio through the pipeline |
| `tests/fixtures/audio/` | Directory containing test audio files |
| `tests/fixtures/corpus.yaml` | Expected transcripts and metadata for each audio file |

### Test Classes

1. **`TestGhostTextBehavior`** - Unit tests for ghost text logic (no GPU required)
   - `test_ghost_timing_respects_throttle` - Verifies throttling prevents overwhelming the system
   - `test_ghost_incremental_backspacing` - Verifies O(1) diff logic (only backspace changed suffix)
   - `test_ghost_word_stitching` - Verifies incremental typing for word-by-word ASR updates
   - `test_ghost_handles_unicode_graphemes` - Verifies unicode/emoji handling as single graphemes
   - `test_ghost_empty_string_clears_state` - Verifies empty ghost text clears state

2. **`TestFinalizeBehavior`** - Unit tests for text finalization
   - `test_finalize_adds_spacing_between_utterances` - Verifies spacing between utterances
   - `test_finalize_preserves_existing_spacing` - Verifies no double-spacing
   - `test_finalize_clears_ghost_before_typing` - Verifies backspace before final typing

3. **`TestAudioIntegration`** - Basic audio file verification (marked `@pytest.mark.slow`)
   - `test_audio_files_exist` - Verifies all fixture files exist
   - `test_audio_format_16khz` - Verifies all audio is 16kHz mono

4. **`TestRealSTTIntegration`** - Integration tests with real STT engine (requires GPU)
   - `test_single_file_transcription` - Parametrized test for single audio file (see Per-File Execution below)
   - `test_real_transcription_matches_corpus` - Batch test running all files
   - `test_ghost_timeline_captured` - Verifies ghost timeline is captured

---

## Test Audio Files

Located in `tests/fixtures/audio/`:

| File | Duration | Purpose |
|------|----------|---------|
| `multiple_words.wav` | 3.86s | Classic pangram - tests full sentence transcription |
| `unicode_speech.wav` | 2.30s | French accents - tests grapheme handling |
| `fast_speech.wav` | 2.24s | Rapid sequential words - tests throttling |
| `hello_hello.wav` | 2.93s | Regression test for warm-up behavior |
| `joke.wav` | 18.57s | Long-form multi-sentence test |
| `multi_utterance.wav` | 7.84s | Multi-utterance joke test |

All files are:
- Format: WAV
- Sample rate: 16kHz
- Channels: Mono
- Encoding: 32-bit float

---

## Corpus Definition

The `tests/fixtures/corpus.yaml` file defines expected transcripts:

```yaml
corpus:
  - id: multiple_words
    filename: multiple_words.wav
    duration_s: 3.858625
    language: en
    transcript: the quick brown fox jumps over the lazy dog
    actual_transcript: The quick brown fox jumps over the lazy dog.
    ghost_count: 0
    notes: Classic pangram
```

Fields:
- `id`: Unique identifier for the test
- `filename`: Audio file name in `fixtures/audio/`
- `duration_s`: Audio duration in seconds
- `language`: Language code
- `transcript`: Base transcript
- `actual_transcript`: Expected STT output (for WER comparison)
- `ghost_count`: Number of ghost updates (captured during test run)
- `notes`: Description

---

## Running Tests

### Prerequisites

```bash
# Install with GPU support
uv sync --extra nvidia-linux

# Set CUDA library path (Linux)
export LD_LIBRARY_PATH=".venv/lib/python3.12/site-packages/nvidia/cublas/lib:.venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:.venv/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:.venv/lib/python3.12/site-packages/nvidia/cufft/lib:.venv/lib/python3.12/site-packages/nvidia/curand/lib:.venv/lib/python3.12/site-packages/nvidia/nvjitlink/lib:$LD_LIBRARY_PATH"

# Set CUDA library path (Windows PowerShell) - run as single line:
$env:PATH = ".venv\Lib\site-packages\nvidia\cublas\bin;.venv\Lib\site-packages\nvidia\cuda_nvrtc\bin;.venv\Lib\site-packages\nvidia\cuda_runtime\bin;.venv\Lib\site-packages\nvidia\cudnn\bin;.venv\Lib\site-packages\nvidia\cufft\bin;.venv\Lib\site-packages\nvidia\curand\bin;.venv\Lib\site-packages\nvidia\nvjitlink\bin;" + $env:PATH

# Enable UTF-8 for proper Unicode support (Windows PowerShell):
$env:PYTHONIOENCODING = "utf-8"

# Run tests:
uv run pytest -s -m slow -k "joke"

# Or run all slow tests:
uv run pytest -s -m slow

# Or via cmd.exe:
cmd /c "set PATH=.venv\Lib\site-packages\nvidia\cublas\bin;.venv\Lib\site-packages\nvidia\cuda_nvrtc\bin;.venv\Lib\site-packages\nvidia\cuda_runtime\bin;.venv\Lib\site-packages\nvidia\cudnn\bin;.venv\Lib\site-packages\nvidia\cufft\bin;.venv\Lib\site-packages\nvidia\curand\bin;.venv\Lib\site-packages\nvidia\nvjitlink\bin;%PATH% && set PYTHONIOENCODING=utf-8 && uv run pytest -s -m slow"
```

### Run All Tests

```bash
# Run all slow (GPU) tests
uv run pytest -s -m slow

# Run all non-slow tests (unit tests, no GPU)
uv run pytest -m "not slow"
```

### Per-File Execution

Run a single audio file test:

```bash
# Run specific file
uv run pytest -s -m slow -k "hello_hello"
uv run pytest -s -m slow -k "joke"
uv run pytest -s -m slow -k "multiple_words"
uv run pytest -s -m slow -k "unicode_speech"
uv run pytest -s -m slow -k "fast_speech"
```

Available test identifiers:
- `test_single_file_transcription[multiple_words]`
- `test_single_file_transcription[unicode_speech]`
- `test_single_file_transcription[fast_speech]`
- `test_single_file_transcription[hello_hello]`
- `test_single_file_transcription[joke]`
- `test_single_file_transcription[multi_utterance]`

---

## Metrics and Logging

### WER (Word Error Rate)

The primary metric for transcription accuracy:

```
WER = (Substitutions + Deletions + Insertions) / Total Words
```

- Threshold: 10% (configurable via `WER_THRESHOLD`)
- WER of 0% = perfect transcription

### CER (Character Error Rate)

Secondary metric for character-level accuracy:

```
CER = (Substitutions + Deletions + Insertions) / Total Characters
```

### Timing Metrics

| Metric | Description |
|--------|-------------|
| `voice_to_first_ghost_ms` | Time from audio start to first ghost text update |
| `timestamp_ms` | Timestamp of each ghost update relative to audio start |
| `end_to_end_latency_ms` | Total time from audio start to final transcript |

### Example Output

```
======================================================================
[TEST] Single File: joke
======================================================================
[FIXTURE] STT Engine device: cuda
[TEST] 📁 joke.wav (18.57s)
[TEST]   Expected: "A woman gets on a bus with her baby..."
[TEST]   Actual:   "A woman gets on a bus with her baby..."
[TEST]   WER:   3.03%  |  CER:   2.36%  |  PASS
[TEST]   Ghosts: 123 updates
[TEST]   First ghost: 855ms
[TEST]   Ghost Timeline:
[TEST]       1.    855ms: "Okay."
[TEST]       2.   1102ms: "A woman gets on a bus with a"
[TEST]       3.   1155ms: "A woman gets on a bus with her baby."
...
```

---

## Test Utilities

### AudioPipelineFixture

Located in `tests/audio_fixtures.py`, provides:

```python
from tests.audio_fixtures import AudioPipelineFixture

pipeline = AudioPipelineFixture()
result = pipeline.run_with_real_stt("hello_hello.wav", warmup=False)

# Result fields:
result.transcript              # Final transcribed text
result.ghost_timeline         # List of GhostUpdate objects
result.voice_to_first_ghost_ms  # Time to first ghost
result.end_to_end_latency_ms  # Total processing time
```

### GhostUpdate Dataclass

```python
@dataclass
class GhostUpdate:
    timestamp_ms: float      # Time since audio start (ms)
    text: str               # Ghost text content
    grapheme_length: int    # Number of graphemes
```

---

## Adding New Test Audio

1. **Create audio file** in `tests/fixtures/audio/`
   - Format: WAV, 16kHz, mono, 32-bit float
   - Duration: 1-30 seconds recommended

2. **Add entry to `corpus.yaml`**:
   ```yaml
   - id: my_new_test
     filename: my_new_test.wav
     duration_s: 3.0
     language: en
     transcript: my test phrase
     actual_transcript: My test phrase.
     notes: Description of what this tests
   ```

3. **Run test to capture baseline**:
   ```bash
   uv run pytest -s -m slow -k "my_new_test"
   ```

4. **Update `actual_transcript`** in corpus.yaml with the captured output

---

## Troubleshooting

### "GPU not available" error

Ensure:
1. CUDA libraries are installed
2. `LD_LIBRARY_PATH` is set correctly
3. NVIDIA GPU is available: `nvidia-smi`

### Tests timing out

- Increase pytest timeout: `uv run pytest -s -m slow --timeout=300`
- Check model loading: first run is slower due to model initialization

### WER threshold exceeded

- Check audio quality
- Verify `corpus.yaml` `actual_transcript` matches current model output
- Consider adjusting `WER_THRESHOLD` in test code

---

## Future Enhancements

- [ ] Add timing benchmarks for performance tracking
- [ ] Support multiple languages
- [ ] Add more edge case audio (background noise, multiple speakers)
- [ ] CI integration for automated testing
- [ ] Performance regression tracking

---

## Related Files

- `src/babelfish_stt/input_manager.py` - InputSimulator implementation
- `src/babelfish_stt/pipeline.py` - STT pipeline
- `src/babelfish_stt/engine.py` - STT engine (ONNX Parakeet)
- `src/babelfish_stt/config.py` - Configuration models
