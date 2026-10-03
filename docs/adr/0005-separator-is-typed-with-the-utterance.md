# The separator is typed with the utterance

The space between two consecutive Finals is typed **with** the earlier Final — as its
trailing space — and the next Final is typed verbatim. This replaces the old rule,
which deferred the decision to the **next** Final.

**The separator is typed at the moment of maximal knowledge, never guessed at the
moment of maximal ignorance.** The old rule (`input_manager.py:268-278`) peeked at a
one-character memory, `last_final_char`, and prepended a space to the *next* Final
whenever the previous one had not ended in whitespace. But by the time that next Final
arrives, the user may have pressed Enter, moved the cursor, or switched applications —
the typing layer knows less then than it did right after it typed. That is why the
first Final after any re-arm arrived with a leading space: `reset()` never clears
`last_final_char`, and no LOCK/activation boundary does either, so the stale character
survived every boundary and armed the guess at precisely the wrong moment.

**The residue moves from the start of a line to its end.** With trailing separators,
pressing Enter between utterances leaves the final text starting at column 0; the only
trace of the separator is a trailing space before the newline — a linter shrug, not an
editor indentation change. The old leading rule instead glued a stray space onto the
next line's first word.

The behavior is controlled by `system_input.separator`: `trailing` (the new default),
`leading` (the legacy rule, verbatim, for those who prefer the old feel), and `never`
(pure passthrough). The setting hot-reloads like the rest of `system_input`; existing
config files get the new behavior without edits — that is intended.

## Consequences

**`last_final_char` survives only to serve `leading`.** Under `trailing` no memory is
consulted, but it is still updated after every typed Final in all modes. This is what
makes a mid-flight hot-reload safe: switching `trailing → leading` cannot double-space,
because the legacy guard sees a whitespace character and suppresses its prepend.

**Empty Finals type nothing under any policy.** `finalize("")` — the ghost-clear path —
neither types nor appends a separator.

**Rejected alternatives:** key-context observation (requires watching keyboard state —
invasive, and risks reacting to our own emission); gap-timing memory (a threshold
tuned against user behavior, unfalsifiable when it misfires); blind backspace eating
("remove the stale space at the next Final") — this sends backspaces across an
utterance boundary blind, and eats the user's newline when they pressed Enter instead
of leaving the trailing space. The existing doctrine stands: no blind backspaces
across a Final boundary, and no "eat the stale space" cleanup, ever, in any mode.

**The transcript stays pure.** The separator belongs to the typing layer only: the
Final text, the WebSocket message, and the terminal display are unchanged. VogonPoet
keeps making its own insertion choice.
