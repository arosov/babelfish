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

### Stages and models

**Ghost Stage**:
The stage that turns in-progress audio into Ghost text, continuously, for as long as the
utterance runs.
_Avoid_: first pass, live pass, fast path, streaming pass

**Final Stage**:
The stage that turns a completed utterance's audio into the Final transcript, once.
_Avoid_: second pass, batch pass, accurate path

**Ghost model**:
The model owned by the Ghost Stage. Chosen for low latency on incomplete audio.
_Avoid_: fast model, live model, streaming model

**Final model**:
The model owned by the Final Stage. Chosen for whole-utterance accuracy rather than
latency.
_Avoid_: accurate model, slow model, batch model

### Hardware

**Placement mode**:
Which execution providers the two stages run on. `split` (the default) puts the Ghost
model on the GPU and the Final model on the CPU; `all-gpu` puts both on the GPU; `cpu`
puts both on the CPU. Decided once at process start and never changed while running.
_Avoid_: device mode, backend, performance tier
