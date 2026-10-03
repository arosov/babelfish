# Babelfish

Babelfish is a local speech-to-text server: it captures audio, decides when you are
speaking, transcribes it, and commits the result into whatever application has focus.

## Language

### Utterances

**Utterance**:
One continuous stretch of speech, from the moment speech is detected to the moment enough
silence follows to close it. All transcription state belongs to an utterance and is
discarded when it ends.
_Avoid_: session, segment, phrase

### Transcript text

**Ghost**:
Provisional transcript text shown while you are still speaking. It is iterated in place
as you dictate and then replaced wholesale by the Final when speech ends; it is never
committed anywhere. Named for the fact that it leaves no trace.
_Avoid_: interim, preview, partial, draft

**Final**:
The committed transcript for one utterance. Produced once, after speech ends, from the
full audio buffer. This is the only text that is injected or typed into the focused
application.
_Avoid_: corrected, committed, result

### Passes

**Ghost pass**:
The pass that turns in-progress audio into Ghost text, continuously, for as long as the
utterance runs. It re-transcribes a sliding window of the buffer on a throttle.
_Avoid_: first pass, live pass, fast path, streaming pass

**Final pass**:
The pass that turns a completed utterance's audio into the Final transcript, once.
_Avoid_: second pass, batch pass, accurate path

Both passes are served by the same Parakeet model on one device — see
[ADR 0004](docs/adr/0004-one-parakeet-model-on-one-device.md). There are no per-pass
models and no per-pass devices.
