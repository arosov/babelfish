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
Provisional transcript text shown while you are still speaking. It is iterated
in place as you dictate — in every display, window updates append incrementally
through one shared span-based composer (ADR 0010: the terminal line and the
typed line are composed identically) and the accumulated Ghost line stays
visible after the utterance ends — and then the Final succeeds it. It is never
committed anywhere; nothing is typed or stored from it.
_Avoid_: interim, preview, partial, draft

**Committed / Live**:
The two halves of one composed Ghost line (ADR 0010). Words whose audio has
slid out of the Ghost window are committed — appended once, never rewritten;
the live tail is the current window's transcription, replaced by each new
Ghost. The window span is ground truth: it bounds how many words may commit
(one word of boundary-fuzz margin), and the word-overlap alignment only
refines that boundary within it — the audio-time proportion commits the
aged-out head when the model re-words the shared region. Terms for the
boundary between them, not for kinds of transcript text.
_Avoid_: stitched, merged, fuzzy-matched

**Final**:
The committed transcript for one utterance. Produced once, after speech ends, from the
full audio buffer. This is the only text that is injected or typed into the focused
application.
_Avoid_: corrected, committed, result

**Separator**:
The space typed after each Final. It belongs to the typing layer, never the
transcript: it is typed with the Final it follows, and the next Final is
typed verbatim. Controlled by `system_input.separator`.
_Avoid_: spacing, gap

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

### Environment

**Bootstrap**:
The provisioning step babelfish runs before the engine starts: detect hardware, sync the
right ORT wheel extra for the machine, provision the Parakeet model if not cached, and
register the CUDA/cuDNN DLL directories. Lives in `scripts/bootstrap.py` and is owned by
babelfish, not VogonPoet — see
[ADR 0006](docs/adr/0006-babelfish-owns-its-bootstrap.md).
_Avoid_: installer, setup script, env setup

**Weights ladder**:
The per-device choice of Parakeet weights card (ADR 0014): a `cpu` device resolves the
**Redux card** (`nemo-parakeet-tdt-0.6b-v3-redux`, int4, ~418 MB) and any GPU device the
**fp32 card** (`nemo-parakeet-tdt-0.6b-v3`). The directory is what rotates — the
engine's `MODEL_NAME` is only the onnx-asr registry key. `hardware.model` ("v3" |
"redux") forces one card; the ladder is strict, with no cross-card fallback.
_Avoid_: model swap, weights swap (that's the run_redux prototype's mechanism),
quantization (that is `hardware.quantization`, a different axis)

