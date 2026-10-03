# Reactive Ghost Pass — before/after harness record

GPU harness (`uv run pytest -s -m slow -k test_single_file_transcription`),
RTX 2080 SUPER, ultra profile (spacing 100ms, window 3.0s).

## Before (gate + throttle display)

| file | first_ghost_ms | ghosts | ghost inference | final delays (ms) |
|---|---|---|---|---|
| multiple_words | 221 | 10 | ~214ms | 287 |
| unicode_speech | 172 | 8 | ~195ms | 224 |
| fast_speech | 177 | 7 | ~205ms | 231 |
| hello_hello | 157 | 7 | ~198ms | 0 / 213 |
| joke (18.6s) | 197 | 39 | ~240ms | 0 / 632 |
| multi_utterance | 166 | 10 | ~198ms | 0 / 0 |

## After (consume-on-done + submit-on-spacing, ghost_padding_s=0.0)

All WERs unchanged (0.0–3.0%). Telemetry: staleness ≈ inference on every Ghost
(display is immediate on completion; e.g. hello_hello ghost #1 `duration=135ms
staleness=135ms`).

| file | first_ghost_ms | ghosts | notes |
|---|---|---|---|
| multiple_words | — | — | (see run log; all PASS) |
| unicode_speech | — | — | PASS |
| fast_speech | — | — | PASS |
| hello_hello | 244 | 16 | first-window text "Hello." — real words, no garbage |
| joke (18.6s) | 296 | 100 | cadence ≈ inference-bound (~250ms/update vs ~480ms before) |
| multi_utterance | 145 | 24 | first-window text "Yeah." |

Observations:

- Ghost update count roughly 2.5× (joke 39 → 100, multi_utterance 10 → 24):
  cadence is now bounded by inference only, the spacing gate never delays
  display.
- Staleness == inference duration on every Ghost (≤32ms chunk granularity on
  top). Before, staleness was max(throttle, inference) with an extra gate wait.
- First-window Ghosts produce real words with `ghost_padding_s = 0.0` — no
  bump needed (the harness shows no empty/garbageless first windows).
- First-ghost wall time on this GPU is dominated by the first inference
  (~135–160ms for the ~0.33s unpadded onset window; the model has high
  per-call overhead on short clips) plus loop scheduling; single-run jitter
  is larger than the delta on some files.

## CPU (Phase 2 verification, device="cpu", window 1.0s)

`benchmark()` returns `{'tier': 'cpu', 'ghost_throttle_ms': 300,
'ghost_window_s': 1.0, 'ghost_padding_s': 0.0, 'min_padding_s': 0}` — the CPU
tier now gets a bounded sliding window (was `window = 0`, i.e. whole-buffer
re-transcription that grew with the utterance).

12s of joke.wav fed through the CPU pipeline: 113 Ghosts, inference durations
min=127ms / max=294ms / avg=213ms — flat across the whole utterance, updates
still arriving at the very end. Before this change CPU Ghosts re-transcribed
the entire growing buffer (~3–5s per Ghost at 10s utterance depth), and the
early ones paid 2s padding.

## Round 2 — live stand (user mic, French, fluent speech)

Two findings from the user's live log:

1. **First visible Ghost ~540ms** (inference 115ms, staleness 120ms → submit
   fired ~420ms after onset): the first ~4 Ghosts (every 100ms spacing)
   transcribed to **empty text** — the unpadded ~330ms onset windows have no
   model context. Exactly the case the plan reserved a `ghost_padding_s` bump
   for. Fix: default `ghost_padding_s = 1.0` (GPU tiers; CPU stays 0.0 — its
   1s window already bounds it).
2. **Finals much longer than the accumulated Ghost sum**: when the model
   re-worded the shared region, the ambiguity guard committed nothing, and
   the aged-out opening words were lost for good (window slides past them).
   Fluent/fast speech slides the window more per update → more loss.
   Fix: the pipeline now passes each Ghost's audio coverage
   `(window_start, buffer_end)` to the display; when no solid text alignment
   exists, the display commits the aged-out head words **by audio time**
   instead of dropping them.

Round 3: rough audio-time commits can reach into audio the next Ghost still
re-covers (doubled phrases: "The woman walks to The woman walks to…"). A
dedup pass trims committed-tail words that the new Ghost's head matches —
they stay visible in the live tail, so nothing is lost. Replay on joke.wav:
ghost sum went 452 → 342 chars with the doubling gone, utterance opening and
ending both intact.

## Harness encoding note

On Windows consoles set `PYTHONIOENCODING=utf-8` when running with `-s`, or
the emoji output crashes under cp1252 (independent of this change).
