# Audio Verification System - Specification

## Overview

A comprehensive audio-based verification system for testing ghost text behavior in the Babelfish STT pipeline. Enables automated verification of input manager behavior using recorded audio files, providing measurable feedback on latency, transcription accuracy, and ghost update frequency.

## Functional Requirements

### Core Features

1. **Test Audio Fixtures**
   - Directory structure: `tests/fixtures/audio/`
   - Audio format: WAV (16kHz, mono, float32)
   - Support for 5 test cases: hello_world, multiple_words, unicode_speech, fast_speech, two_sentences

2. **Corpus Definition Format**
   - YAML file: `tests/fixtures/corpus.yaml`
   - Contains: id, filename, language, transcript, expected_ghosts[]
   - Ghost timeline includes: timestamp_ms, text

3. **Audio Pipeline Test Utility (`tests/audio_fixtures.py`)**
   - `AudioPipelineFixture` class
   - Methods: `run(audio_filename, config)` → `PipelineResult`
   - Captures: transcript, ghost_timeline, final_timeline, errors

4. **Metrics Captured**
   - Voice-to-first-ghost latency (A)
   - Ghost update frequency during speech (B)
   - Final transcription accuracy vs expected (C)
   - Backspacing/diff correctness (D)
   - End-to-end latency (E)

5. **Test Categories**
   - Unit tests: throttling, backspacing, word stitching, unicode/grapheme handling
   - Integration tests: real audio through pipeline
   - Edge cases: concurrent updates, drift recovery, redundant frames

### Test Execution

- Standalone test suite: `pytest tests/test_ghost_text.py -v`
- Optional: `pytest tests/test_ghost_text.py -v -m slow` for audio integration tests
- No CI integration (per user preference)

## Out of Scope

- CI automation
- TTS/synthetic audio generation
- Pre-commit hooks
- Real-time streaming verification
