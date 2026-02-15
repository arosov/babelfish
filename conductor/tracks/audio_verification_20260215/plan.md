# Plan: Audio Verification System

## Phase 1: Core Infrastructure

- [ ] Task: Add soundfile to test dependencies in pyproject.toml
- [ ] Task: Create tests/audio_fixtures.py utility module
  - [ ] Define GhostUpdate dataclass
  - [ ] Define PipelineResult dataclass
  - [ ] Implement AudioPipelineFixture class with run() method
  - [ ] Implement _default_config() method
  - [ ] Implement _patch_audio_streamer() method (mock AudioStreamer to yield from file)
  - [ ] Implement _run_pipeline() method
- [ ] Task: Create basic mock keyboard fixture in conftest.py

## Phase 2: Test Audio Fixtures

- [ ] Task: Create tests/fixtures/audio/ directory structure
- [ ] Task: Record/create hello_world.wav (~2s, "hello world")
- [ ] Task: Record/create multiple_words.wav (~5s, "the quick brown fox jumps over the lazy dog")
- [ ] Task: Record/create unicode_speech.wav (~3s, "café résumé naïve")
- [ ] Task: Record/create fast_speech.wav (~4s, rapid "testing one two three four five")
- [ ] Task: Record/create two_sentences.wav (~6s, "first sentence. second sentence")
- [ ] Task: Create tests/fixtures/corpus.yaml with transcript and expected_ghosts for each file

## Phase 3: Ghost Text Tests

- [ ] Task: Create tests/test_ghost_text.py
- [ ] Task: Write unit tests - throttling behavior (TestGhostTextBehavior)
- [ ] Task: Write unit tests - incremental backspacing
- [ ] Task: Write unit tests - word stitching
- [ ] Task: Write unit tests - unicode/grapheme handling
- [ ] Task: Write unit tests - empty string handling
- [ ] Task: Write unit tests - finalize spacing logic (TestFinalizeBehavior)
- [ ] Task: Write integration tests with real audio (TestAudioIntegration)
- [ ] Task: Write edge case tests (TestEdgeCases)

## Phase 4: Verification

- [ ] Task: Run full test suite and verify all tests pass
- [ ] Task: Verify coverage meets >80% requirement
- [ ] Task: Document usage in tests/README.md or in AGENTS.md
