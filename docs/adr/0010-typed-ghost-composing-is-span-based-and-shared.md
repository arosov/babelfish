# Typed Ghost composing is span-based, shared with the terminal display

Status: Accepted

A typed Ghost must append while you speak. Today it sometimes rewrites itself:
the ghost collapses to the size of the last transcribed window instead of
growing, and the size gap only becomes visible when the Final replaces it. The
failure is speech-rate dependent. Decision: the typed Ghost stops beingcomposed
by fuzzy word-stitching heuristics and is composed by the same
audio-window-span algorithm the terminal display already uses, in one shared
composer. `InputSimulator._stitch_words` is removed.

## The bug, diagnosed

`InputDisplay.update` ignores the pipeline's Ghost window span
(`display.py:305-306` — "Extra pipeline metadata … is ignored") and feeds the
raw sliding-window transcription to `InputSimulator.update_ghost`
(`input_manager.py:63-130`). The simulator must therefore turn a sequence of
overlapping window transcriptions into one growing line, and does so with
`_stitch_words` heuristics (`input_manager.py:132-208`):

1. Exact overlap: a `difflib.SequenceMatcher` longest identical word block,
   requiring **more than 3 contiguous identical words** (`:172`).
2. Fuzzy overlap: `rapidfuzz.partial_ratio > 70` on concatenated cleaned words
   (`:197`).
3. Both fail → **replace-all**: the stitched line becomes exactly the last
   window's words (`:205`), discarding everything accumulated so far.
4. Otherwise ignore-new: the base words are kept and the Ghost visibly freezes
   (`:208`), until the sliding window moves far enough that the shared region
   vanishes and branch 3 fires anyway.

Every applied update re-types by erase-all-then-repaste-full
(`input_manager.py:112-124`), so a working stitch *looks* like appending and a
failed stitch *looks* like a rewrite. The reported bug — "ghosts rewrite
themselves instead of appending, depends on how fast I speak; the Final is
always correct but hugely larger than the ghost" — is branch 3, observed
through the erase/re-paste mechanics: with a fast speaker the shared region
between consecutive windows is short and heavily revised, so the exact block is
≤3 words (Parakeet TDT routinely revises words inside the shared region as
right-context grows), the fuzzy score falls below 70, and the line collapses to
one window. The Final, being stitch-independent, then replaces a one-window
ghost with a full-utterance transcript — the large size difference that makes
the bug easy to spot.

Two aggravators live in the same code:

- `_last_raw_ghost` is recorded *before* the throttle gate (`:87` vs `:101-105`),
  so a throttle-dropped frame poisons the dedup key: an identical
  re-transcription is later skipped even though the screen still shows older
  text. Dormant at a 400 ms cadence; a trap on faster tiers.
- The disabled-input cleanup in `InputDisplay.finalize` checks
  `simulator.graphemes` but erases `len(displayed_graphemes)`
  (`display.py:322-324`) — harmless only while the two lists mirror each other.

The calibration faults documented in
[ADR 0011](0011-calibration-always-runs-and-never-persists.md) made this fire
more often on this machine than it should have (a CUDA card throttled and
windowed as `low_power` shrinks the shared region), but the stitcher cliff is
the defect: *any* tier regime produces it given fast speech and a revising
model. Fixing the benchmark alone would hide the bug, not remove it.

## Decision

**One span-based composer, two consumers.** `TerminalDisplay._compose_ghost`,
`_commit_count`, and `_text_overlap_words` (`display.py:71-160`) are extracted
into a shared `GhostComposer` (`src/babelfish_stt/ghost_composer.py`). Its
model: words whose audio has left the window are **committed** (never
rewritten); the **live** tail is replaced by each new Ghost, aligned against
the previous Ghost's tail by word overlap, falling back to proportional
audio-time commits from the pipeline-reported window span. The typed path
consumes it identically:

- `InputDisplay.update` stops ignoring the `window=` span and passes it
  through.
- `InputSimulator.update_ghost(ghost, window)` composes via the shared class
  and then performs its existing erase-all + paste-the-full-line typing.
  The backspace count is derived from exactly the line the composer produced,
  so what is tracked and what is on screen can no longer diverge.
- `_stitch_words`, the `words`/`graphemes`/`displayed_graphemes` triple-track,
  and the fuzzy thresholds are deleted with the heuristic path.
- Dedup keys on `(ghost_text, window)` and is recorded only after a frame is
  actually applied — closing the `_last_raw_ghost` ordering trap.
- The wrong-list check in the disabled-input cleanup is fixed to read the list
  it erases.

**The typing mechanics are untouched.** The pynput backspace loop and the
clipboard paste remain exactly as decided in
[ADR 0009](0009-the-input-strategy-is-the-clipboard.md): erase-then-full-repaste
per update, clipboard as the only strategy. This is a composition decision, not
an injection decision. (If garbled text symptoms ever appear *without* the
line-shrink signature, dropped backspaces under load would be the next
suspect — but that is a different failure mode with no size-gap tell.)

## Considered Options

**Patch the heuristics** — bound the replace-all branch with the window span,
fix the dedup ordering, keep `_stitch_words`. Rejected: the fuzzy matching
still guesses where two windows join, its failure modes remain reachable (just
rarer), and the repo then carries two divergent composition algorithms for the
same Ghost stream — the terminal already appends while Notepad++ rewrote, for
the same input.

**Diff-paste instead of erase-all** — send only the trailing characters that
changed. Rejected for now: it multiplies the keystroke count per update and
restarts the dropped-keystroke exposure that ADR 0009 retired Direct to avoid.
The composite-line erase-all is atomic and its count is provably correct once
composition is. Keep it as the documented next step if clipboard paste churn
ever matters.

## Consequences

**Appending is structural, speed-independent.** The composed line can never
shrink mid-utterance: committed words are only ever appended to, and the live
tail is replaced wholesale against a pinned boundary. Speech rate changes how
often windows revise, not whether the line grows.

**Ghost and terminal agree by construction.** One algorithm serves both
displays; the vocabulary (`committed`/`live` for windows) may earn GLOSSARY.md
entries when this lands.

**The proportional fallback still exists on purpose.** When the model re-words
the shared region, text alignment cannot pin the boundary and the composer
falls back to audio-time proportional commits (`display.py:115-122`), which can
be roughly right and occasionally duplicate a boundary word. The terminal
composer already trims such duplicates (`display.py:88-90`); the typed path
inherits the same behaviour and tolerance.

**Tests.** A regression test replays a fast-speech ghost sequence (short
window, rapid span advance, revising transcriptions) and asserts the composed
line is append-only and every backspace count equals the length of the line
presently pasted; it should fail against the stitcher and pass against the
composer. The existing terminal composition tests move to the shared class.
The stitcher's own tests are deleted with it.

**Vocabulary guard.** The composed path must not reintroduce `interim`,
`preview`, `partial`, or `draft` — the GLOSSARY's Ghost/Final terms and their
avoid-list stand.

**Docs to correct on landing** (not now): the "Extra pipeline metadata … is
ignored" comment at `display.py:305-306` becomes wrong and must change, not
revert, per the ADR 0003 rule about comments that contradict decisions.
