# Control words are stripped from the audio, and the stop word is spoken alone

Two things are true about control words, and both contradict existing code.

**The wake word's audio is trimmed out of the transcription buffer.** It used to be
deliberately kept: `main.py:119-121` processes the trigger chunk immediately, with the
comment "This ensures the audio that contained the wake word is part of the sentence." That
was insurance against clipping the first syllable of what you actually said. We now trim
instead, because OpenWakeWord is a dedicated keyword-spotting model and it reports exactly
where the keyword was recognised — so the audio can be cut at a known position rather than
guessing at word boundaries in generated text. Trimming audio is also model-independent:
Parakeet and the Ghost model may spell "hey jarvis" differently and it makes no difference,
whereas matching the configured wake word against either model's output is a heuristic that
has to tolerate more variation the moment a second model exists. Stripping behaviour is
controlled by `--no-strip-control-words`, mostly so it can be turned off while debugging.

**The stop word is expected to be spoken as its own utterance.** Stop-word detection runs
on both Ghost and Final text, and a detection aborts the utterance without committing it.
That is only safe because the buffer being discarded contains nothing but the stop word.
If the stop word ever arrives mid-sentence, the sentence is lost silently.

## Consequences

**The comment at `main.py:119-121` is now wrong and must be changed, not reverted.** It
states the opposite of the current intent. A future reader will "fix" it.

**The wake-word boundary becomes a tunable.** `pre_roll_ms` previously did nothing on the
wake-word path. It now determines how much audio survives the trim, so if the first word
spoken after the wake word turns out to be clipped, that is the knob to raise.

**Ghost false positives now cost speech.** Stop-word detection on Ghost text
(`pipeline.py:339-343`) was already a silent-abort path, but the old Ghost output was
degraded TDT output on partial audio. A fluent decoder is more likely to produce a
plausible-looking trailing phrase that matches, and `StopWordDetector.detect` matches a
trailing `endswith`. Misfires should be logged — a detection against a buffer much longer
than the stop phrase indicates one — but detection behaviour is unchanged, because aborting
is the correct semantic when the word really is spoken alone.