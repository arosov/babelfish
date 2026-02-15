# Audio Verification System for Ghost Text Testing

## Overview

This document outlines a plan to create an audio-based verification system for testing the ghost text behavior in the Babelfish STT pipeline. The goal is to enable automated verification of input manager behavior using recorded audio files instead of requiring live microphone input.

---

## Current State

### Test Infrastructure

- **Framework**: pytest with unittest-style tests
- **Babelfish tests**: Located in `../babelfish/tests/`
- **VogonPoet tests**: Standard Kotest/Kotlin tests in `composeApp/src/*Test/`
- **Dependency**: Heavy use of mocks - no real audio hardware needed for unit tests

### Existing Input Tests

| File | Coverage |
|------|----------|
| `test_input_simulator.py` | Unit tests with mocked keyboard - ghost text logic, backspacing, grapheme handling |
| `test_input_strategies.py` | Strategy pattern tests - Direct, Clipboard, Hybrid |
| `test_e2e_voice_control.py` | Full pipeline mocked end-to-end |
| `test_display_input.py` | InputDisplay integration |

### Gap Identified

No way to run real audio files through the pipeline to verify actual ghost text behavior. Current tests use mocks that don't capture real ASR characteristics like:
- Timing variations in transcription
- Partial/evolving transcripts
- Audio quality effects on output

---

## Proposed Solution

### 1. Test Audio Assets

Create a directory for test audio fixtures:

```
babelfish/tests/fixtures/
babelfish/tests/fixtures/audio/
babelfish/tests/fixtures/audio/hello_world.wav
babelfish/tests/fixtures/audio/multiple_words.wav
babelfish/tests/fixtures/audio/unicode_speech.wav
babixtures/audio/felfish/tests/fast_speech.wav
babelfish/tests/fixtures/audio/two_sentences.wav
babelfish/tests/fixtures/corpus.yaml
```

#### Audio File Specifications

| File | Duration | Purpose |
|------|----------|---------|
| `hello_world.wav` | ~2s | Basic test - simple phrase |
| `multiple_words.wav` | ~5s | Word stitching with multiple updates |
| `unicode_speech.wav` | ~3s | Special characters, accents |
| `fast_speech.wav` | ~4s | Rapid updates, throttling test |
| `two_sentences.wav` | ~6s | Multiple utterances, spacing |

#### Corpus Definition Format

Create `babelfish/tests/fixtures/corpus.yaml`:

```yaml
---
version: 1

corpus:
  - id: hello_world
    filename: hello_world.wav
    language: en
    transcript: "hello world"
    expected_ghosts:
      - timestamp_ms: 500
        text: "hello"
      - timestamp_ms: 1200
        text: "hello world"

  - id: multiple_words
    filename: multiple_words.wav
    language: en
    transcript: "the quick brown fox jumps over the lazy dog"
    expected_ghosts:
      - timestamp_ms: 300
        text: "the"
      - timestamp_ms: 600
        text: "the quick"
      - timestamp_ms: 1000
        text: "the quick brown"
      # ... more updates

  - id: unicode_speech
    filename: unicode_speech.wav
    language: fr
    transcript: "café résumé naïve"
    expected_ghosts:
      - timestamp_ms: 500
        text: "café"
      - timestamp_ms: 1200
        text: "café résumé"

  - id: fast_speech
    filename: fast_speech.wav
    language: en
    transcript: "testing one two three four five"
    expected_ghosts:
      - timestamp_ms: 200
        text: "testing"
      - timestamp_ms: 350
        text: "testing one"
      - timestamp_ms: 500
        text: "testing one two"

  - id: two_sentences
    filename: two_sentences.wav
    language: en
    transcript: "first sentence. second sentence"
    expected_ghosts:
      - timestamp_ms: 1000
        text: "first sentence"
      - timestamp_ms: 2500
        text: "first sentence."
      - timestamp_ms: 3500
        text: "first sentence. second"
```

### 2. Audio Pipeline Test Utility

Create `babelfish/tests/audio_fixtures.py`:

```python
"""
Audio fixture utilities for testing the STT pipeline with real audio files.

Usage:
    @pytest.fixture
    def audio_pipeline():
        return AudioPipelineFixture()

    def test_ghost_updates(audio_pipeline):
        result = audio_pipeline.run(
            "fixtures/audio/hello_world.wav",
            config=PipelineConfig(
                ghost_throttle_ms=50,
                type_ghost=True,
            )
        )
        
        assert result.transcript == "hello world"
        assert result.ghost_timeline[0].text == "hello"
        assert len(result.ghost_timeline) > 1
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import patch, MagicMock

from babelfish_stt.pipeline import SinglePassPipeline
from babelfish_stt.config import BabelfishConfig


@dataclass
class GhostUpdate:
    """Represents a ghost text update event."""
    timestamp_ms: float
    text: str
    grapheme_length: int


@dataclass
class PipelineResult:
    """Results from running audio through the pipeline."""
    transcript: str
    ghost_timeline: list[GhostUpdate] = field(default_factory=list)
    final_timeline: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AudioPipelineFixture:
    """
    Test utility that runs audio files through the STT pipeline
    while capturing ghost and final text events.
    """
    
    def __init__(self, model_dir: Optional[str] = None):
        self.fixtures_dir = Path(__file__).parent / "fixtures" / "audio"
        self._captured_ghosts: list[GhostUpdate] = []
        self._captured_finals: list[str] = []
        self._start_time: Optional[float] = None
    
    def run(
        self,
        audio_filename: str,
        config: Optional[BabelfishConfig] = None,
    ) -> PipelineResult:
        """
        Run an audio file through the pipeline with ghost tracking.
        
        Args:
            audio_filename: Name of file in fixtures/audio/
            config: Optional pipeline configuration
            
        Returns:
            PipelineResult with transcript and ghost timeline
        """
        audio_path = self.fixtures_dir / audio_filename
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Load audio
        audio_data, sample_rate = sf.read(audio_path, dtype="float32")
        
        # Capture callbacks
        self._captured_ghosts = []
        self._captured_finals = []
        
        # Run pipeline with mocked audio input
        with self._patch_audio_streamer(audio_data, sample_rate):
            # Run actual pipeline
            result = self._run_pipeline(config or self._default_config())
        
        return PipelineResult(
            transcript=result.get("text", ""),
            ghost_timeline=self._captured_ghosts,
            final_timeline=self._captured_finals,
        )
    
    def _default_config(self) -> BabelfishConfig:
        """Create default test configuration."""
        return BabelfishConfig(
            pipeline=PipelineConfig(
                silence_threshold_ms=400,
                update_interval_ms=100,
            ),
            system_input=SystemInputConfig(
                enabled=True,
                type_ghost=True,
                strategy=InputStrategy.DIRECT,
            ),
        )
    
    def _patch_audio_streamer(self, audio_data: np.ndarray, sample_rate: int):
        """Patch AudioStreamer to yield from file instead of mic."""
        # Implementation details...
        pass
    
    def _run_pipeline(self, config: BabelfishConfig):
        """Execute the actual pipeline."""
        # Implementation details...
        pass
```

### 3. Ghost Text Verification Tests

Create `babelfish/tests/test_ghost_text.py`:

```python
"""
Ghost text behavior tests using real audio files.

These tests verify the InputSimulator's ghost text handling
with realistic ASR output patterns from actual audio.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, call
from pathlib import Path

from babelfish_stt.input_manager import InputSimulator
from tests.audio_fixtures import AudioPipelineFixture, GhostUpdate


@pytest.fixture
def audio_pipeline():
    """Fixture providing audio pipeline test utility."""
    return AudioPipelineFixture()


@pytest.fixture
def mock_keyboard():
    return MagicMock()


class TestGhostTextBehavior:
    """Tests for ghost text update and backspacing behavior."""
    
    def test_ghost_timing_respects_throttle(self, mock_keyboard):
        """Ghost updates should be throttled to prevent overwhelming the system."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.1)
        
        # Rapid updates
        simulator.update_ghost("hello")
        simulator.update_ghost("hello w")
        simulator.update_ghost("hello wo")
        simulator.update_ghost("hello wor")
        simulator.update_ghost("hello worl")
        
        # Should only output once due to throttle
        # (timing-dependent, but verifies throttle logic)
    
    def test_ghost_incremental_backspacing(self, mock_keyboard):
        """Should only backspace changed suffix, not entire text."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        # Initial ghost
        simulator.update_ghost("hello world")
        mock_keyboard.reset_mock()
        
        # Update to "hello there"
        simulator.update_ghost("hello there")
        
        # Should backspace only "world" and type "there"
        # Not: backspace all 11 chars and retype
        # (verifies O(1) diff logic)
    
    def test_ghost_word_stitching(self, mock_keyboard):
        """Word stitching should handle incremental ASR updates correctly."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        # Simulate ASR word-by-word updates
        simulator.update_ghost("the")
        mock_keyboard.reset_mock()
        simulator.update_ghost("the quick")
        mock_keyboard.reset_mock()
        simulator.update_ghost("the quick brown")
        
        # Verify incremental typing
        # Should type " quick" then " brown", not retype everything
    
    def test_ghost_handles_unicode_graphemes(self, mock_keyboard):
        """Unicode characters should be handled as single graphemes."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        # Emoji and accented characters
        simulator.update_ghost("café 🏢")
        
        # Should have correct grapheme count (not byte count)
        assert simulator.last_ghost_length == 5  # c, a, f, é, 🏢
        
        # Update should backspace only the changed part
        simulator.update_ghost("café 🏢 test")
        # Verify backspace count
    
    def test_ghost_empty_string_clears_state(self, mock_keyboard):
        """Empty ghost text should clear state without errors."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        simulator.update_ghost("some text")
        assert simulator.last_ghost_length > 0
        
        simulator.update_ghost("")
        assert simulator.last_ghost_length == 0


class TestFinalizeBehavior:
    """Tests for text finalization and injection."""
    
    def test_finalize_adds_spacing_between_utterances(self, mock_keyboard):
        """Should add space between consecutive finalizations."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        simulator.finalize("hello")
        mock_keyboard.type.assert_called_with("hello")
        
        mock_keyboard.reset_mock()
        simulator.finalize("world")
        # Should add space: " world"
        mock_keyboard.type.assert_called_with(" world")
    
    def test_finalize_preserves_existing_spacing(self, mock_keyboard):
        """Should not add extra space if already present."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        simulator.finalize("hello")
        
        mock_keyboard.reset_mock()
        simulator.finalize(" world")  # Already has leading space
        mock_keyboard.type.assert_called_with(" world")
    
    def test_finalize_clears_ghost_before_typing(self, mock_keyboard):
        """Should backspace ghost text before typing final."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        simulator.update_ghost("ghost")
        mock_keyboard.reset_mock()
        
        simulator.finalize("final")
        
        # Should have backspaced ghost
        assert mock_keyboard.press.call_count == 5
        # Then typed final
        mock_keyboard.type.assert_called_with("final")


class TestAudioIntegration:
    """Integration tests with real audio files."""
    
    @pytest.mark.slow
    def test_hello_world_audio_ghost_timeline(self, audio_pipeline):
        """Test ghost timeline from actual audio file."""
        result = audio_pipeline.run("hello_world.wav")
        
        # Basic transcript check
        assert "hello" in result.transcript.lower()
        assert "world" in result.transcript.lower()
        
        # Ghost timeline should have multiple updates
        assert len(result.ghost_timeline) >= 2
        
        # First ghost should be partial
        assert result.ghost_timeline[0].text != result.transcript
    
    @pytest.mark.slow
    @pytest.mark.skipif(
        not Path("tests/fixtures/audio/unicode_speech.wav").exists(),
        reason="Audio fixture not available"
    )
    def test_unicode_audio_grapheme_handling(self, audio_pipeline):
        """Test handling of accented characters from real audio."""
        result = audio_pipeline.run("unicode_speech.wav")
        
        # Verify ghosts captured unicode correctly
        for ghost in result.ghost_timeline:
            # Should not have byte-level corruption
            assert ghost.grapheme_length == len(list(ghost.text))


class TestEdgeCases:
    """Edge case tests for ghost text handling."""
    
    def test_rapid_concurrent_updates(self, mock_keyboard):
        """Handle rapid successive updates without state corruption."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        # Simulate concurrent-like updates
        updates = ["a", "ab", "abc", "abcd", "abcde"]
        for text in updates:
            simulator.update_ghost(text)
        
        # Final state should be consistent
        assert simulator.words == ["abcde"]
        assert simulator.last_ghost_length == 5
    
    def test_drift_recovery(self, mock_keyboard):
        """Should recover gracefully when word stitching drifts."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        # Build some history
        simulator.update_ghost("the quick brown fox")
        
        # Drastic change (ASR restart or new sentence)
        mock_keyboard.reset_mock()
        simulator.update_ghost("completely different text here")
        
        # Should handle gracefully, not crash
        assert simulator.last_ghost_length > 0
    
    def test_redundant_frame_handling(self, mock_keyboard):
        """Should skip duplicate ghost frames efficiently."""
        simulator = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
        
        simulator.update_ghost("test")
        mock_keyboard.reset_mock()
        
        # Same text again
        simulator.update_ghost("test")
        
        # Should skip entirely - no keyboard activity
        mock_keyboard.type.assert_not_called()
        mock_keyboard.press.assert_not_called()


# Mark slow tests for optional execution
pytestmark = pytest.mark.slow
```

### 4. Optional: Compression Support

Add support for compressed audio formats by adding `soundfile` to dependencies:

```toml
# In pyproject.toml
[project.optional-dependencies]
test = [
    "soundfile>=0.12.0",  # For loading various audio formats
]
```

The `AudioPipelineFixture` can auto-detect format from extension and use `sf.read()` for WAV/OGG/FLAC, or use `torchaudio` for more formats.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audio format | WAV (primary) | Lossless, widely supported, easy to create/edit |
| Model loading | Real model | Tests actual ASR behavior |
| Audio input | Mocked AudioStreamer | No mic needed, reproducible |
| Test location | `babelfish/tests/` | Near existing tests |
| Verification approach | Capture callbacks | Directly tests the interface |
| Slow tests | Marked with `@pytest.mark.slow` | Can be skipped in CI |
| Corpus format | YAML | Human-readable, easy to edit |

---

## Implementation Roadmap

### Phase 1: Core Infrastructure
1. Add `soundfile` to test dependencies
2. Create `tests/audio_fixtures.py` utility
3. Create basic mock keyboard fixture

### Phase 2: Test Audio Creation
1. Record or generate test audio files
2. Create `tests/fixtures/corpus.yaml`
3. Document how to add new test audio

### Phase 3: Ghost Text Tests
1. Create `tests/test_ghost_text.py`
2. Add unit tests for edge cases
3. Add integration tests with audio

### Phase 4: CI Integration
1. Add pytest markers for slow tests
2. Create separate CI job for audio tests
3. Document test execution procedures

---

## Trade-offs

### Advantages
- **Realistic**: Tests actual ASR output patterns
- **Reproducible**: Same audio = same results
- **Verifiable**: Can check exact expected outputs
- **Timing tests**: Can measure latency

### Disadvantages
- **Slower**: Requires model loading (~5-10s setup per test)
- **Storage**: Audio files add to repo size
- **Maintenance**: Corpus needs updating if ASR behavior changes

---

## Testing Checklist

### Must Have
- [ ] Ghost text timing/throttling works
- [ ] Incremental backspacing is correct
- [ ] Word stitching handles overlap
- [ ] Unicode/grapheme handling
- [ ] Finalize spacing logic

### Should Have
- [ ] Multiple consecutive utterances
- [ ] Fast speech (rapid updates)
- [ ] Drift recovery

### Nice to Have
- [ ] Latency measurements
- [ ] Performance benchmarks
- [ ] Cross-language tests

---

## Questions for Implementation

1. **Audio files**: Should sample recordings be created, or provided by user?
2. **Model selection**: Use smallest available model for speed, or default?
3. **Corpus format**: YAML sufficient, or need JSON for more structure?
4. **CI strategy**: Run on every commit or as separate manual verification?
5. **Audio compression**: Is OGG/MP3 support needed, or WAV sufficient?
