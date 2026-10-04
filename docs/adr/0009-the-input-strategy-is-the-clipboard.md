# The input strategy is the clipboard — one strategy, no alternatives

Injection had four selectable strategies: Direct (pynput keystroke emulation),
Clipboard (`pyperclip` + paste chord), Native (OS CLI tools), and Hybrid
(ASCII → Direct, else Clipboard), chosen by `system_input.strategy`. Decision:
**clipboard is the strategy** — Direct, Native, and Hybrid are removed as
selectable strategies. What remains of Direct is its backspace loop, kept as the
one backspace mechanism (pynput `Key.backspace` press/release), which Clipboard
already delegated to. `system_input.strategy` is removed from config; every
config that named `direct`, `native`, or `hybrid` now pastes like `clipboard`.

**Clipboard is the only mode whose failure modes are environmental, not
content-corrupting.** It is unicode-proof (no layout, no dead keys, no modifier
state involved), atomic (one synthetic keystroke regardless of utterance
length), and fast regardless of length. The keystroke strategies fail in the
opposite direction: Direct fires hundreds of key events that apps under load
drop or reorder, races with modifiers the user is holding, and misbehaves on
non-ASCII in X11 layouts; Native is strictly worse than Direct on Windows —
a `powershell.exe` spawn (~100–500 ms) per injection, SendKeys escaping that
doubles `(`/`[`/`[`/`]` (only `{ } + ^ % ~` are special), and a single-quote
parse error that fails on every apostrophe before falling back. Hybrid looked
like a compromise but inherited both families' weaknesses — it never earned its
branch.

**The defaults already voted for this.** `ClipboardStrategy` was the shipped
default (`config.py:89`), the Ghost path was hard-coded to clipboard re-typing
(`input_manager.py:149`), Direct already fell back to Clipboard on any exception
(`input_strategies.py:35`), and Clipboard's backspace already delegated to
Direct (`input_strategies.py:70`). The four-way branch existed on paper; in
practice two of its edges were already one-way doors pointing back at clipboard.

## Consequences

**Backspace is the surviving Direct behavior, deliberately.** A paste cannot
delete, so backspacing (Ghost clearing in `update_ghost`/`finalize`) still goes
through pynput's backspace loop. The `InputStrategy` abc is retired with the
strategies: the clipboard paste and the backspace loop are plain functions, not
a strategy object hierarchy. No strategy survives with a `type` that nothing
uses.

**Removing `strategy` from config is a breaking change on purpose.** An existing
`babelfish.config.json` carrying `"strategy": "native"` or `"hybrid"` no longer
has anything to name. The field is dropped from `SystemInputConfig` and from the
generated schema (`babelfish_schema.json`); unknown keys are tolerated by
pydantic's default parse, so stale files keep loading and their setting is
silently ignored. `readme.md`'s `system_input` block drops the field. The
in-memory `--type` override (`main.py:224-226`) never touched it.

**Ghost and Final now share one paste path.** With one strategy, the
Ghost/Final asymmetry (Ghost hard-coded clipboard, Final configured) collapses
to a single implementation: both are clipboard paste + pynput backspace. The
`strategy` argument threading (`display.py:328`, `finalize`, `_send_backspaces`,
`type_text`) is removed with it.

**Linux terminal paste is a chord decision, not a strategy decision.**
[ADR 0008](0008-linux-terminal-detection-is-window-class-x11-only.md) decides
`Ctrl+Shift+V` vs `Ctrl+V` inside the one clipboard path. With the strategy
branch gone there is exactly one place for that logic to live.

**Windows clipboard users on admins/elevated targets keep hitting UIPI** —
pynput-synthesized chords from a non-elevated process are dropped in elevated
windows. That is a platform constraint on the surviving path, unchanged by this
simplification, and the reason clipboard save/restore and a terminal-aware
chord (ADR 0008) remain the future work here, not more strategies.

**Rejected alternatives:** keep Direct as a selectable strategy (no clipboard
clobber, but content-corrupting failure modes and a Wayland-dead code path for
a mode nobody sets — the default was clipboard); fix Native's escaping and
latency instead of removing it (fixing a mode whose only distinct value was
"works where paste is remapped" is effort spent preserving a liability);
keep Hybrid (its `is_safe()` gate protects against a unicode problem Direct
does not reliably have on Windows/macOS, while adding a branch and two test
suites); config-tolerant aliasing of removed values to clipboard (validates
settings that no longer mean anything — silent ignores keep the config surface
honest and the schema clean).
