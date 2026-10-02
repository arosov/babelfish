# Each stage owns its own model

Babelfish had one model (Parakeet TDT) serving two roles: continuous provisional text
during an utterance, and a single committed transcript at the end. Rather than give the
roles different models through a registry of named roles each binding to a configurable
model id, we split the work into two stages, each owning the model it uses.

A stage is written against its own model and is not parameterised by it. The Ghost Stage
consumes audio continuously with a stateful, incremental decoder; the Final Stage
transcribes a completed utterance once with a whole-utterance model. There are no model
ids in configuration and no role registry.

## Considered Options

**One model, two passes** (status quo). Rejected: Parakeet was being constrained to serve
both roles, and no single model is simultaneously a low-latency incremental decoder and a
high-accuracy whole-utterance transcoder.

**Role registry, model configurable per role.** The obvious design, and the one a future
reader is most likely to propose. Rejected as speculative generality. Nobody asked to
choose their models, babelfish has one author, and a common abstraction across roles caps
each stage at the weakest common denominator of every model that might bind to it.
Tailoring each stage to its model is what makes a stateful Ghost Stage possible at all.

**Shared base class for the two stages.** Rejected: they share only utterance lifecycle,
which is an object they both reference rather than a behaviour they both inherit.

## Consequences

**Self-calibration is gone.** The startup benchmark, the throttle and sliding-window
fields on `PerformanceProfile`, and the Ultra/High/Medium/Low tiers were all derived from
measuring one model's latency against the ghost cadence. The Ghost model's own streaming
cadence governs now. `AGENTS.md` claimed self-calibration as a headline capability and was
wrong.

**Silently wrong padding.** `min_padding_s` right-pads a buffer with zeros and was a
workaround for TDT on incomplete audio. It still feeds the Final Stage
(`pipeline.py:469`) and its derivation needs revisiting or removal independently.

**Spelling assumptions are gone.** Nothing downstream can assume one model's output
formatting, because two models now produce the two kinds of text. Anything that aligned
transcripts by string similarity across the two stages needs re-checking.