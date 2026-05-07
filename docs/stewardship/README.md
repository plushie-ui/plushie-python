# Stewardship

Working notes on the project's direction, trust posture, goals,
and deliberate non-goals. The intent is to make plushie-python's
posture explicit so that any proposed work, whether a feature, a
refactor, a library upgrade, an API change, a breaking-change
call, or an observation surfaced during a review, can be evaluated
against a stable reference instead of restated intuition.

These docs are about long-lived guiding principles, not about any
particular review or report. They name the axes the project takes
seriously, the disciplines that hold them up, and the directions
that are explicitly out of scope. They should outlive any
particular finding, proposal, or working pass.

The files below are the authority on each axis when an axis is
in play.

## Layout

- `posture.md` describes what plushie-python is, who it is for,
  the cross-SDK relationship (plushie-elixir is the API-shape
  reference), the project's stage, and the recurring disciplines.
- `goals-and-non-goals.md` lists the testable shipping criteria
  the project optimizes for, and the explicit non-objectives it
  declines work against.
- `trust-model.md` describes plushie-python's role in the wider
  Plushie trust model, what the host SDK implements on its own
  side, and how those choices shape design and triage decisions.
  Authoritative trust-model lives in plushie-rust.
- `resilience.md` describes how plushie-python behaves when
  things go wrong (app exception revert, view-error tracking,
  reconnect with state re-sync, thread-pool isolation), and
  where fail-fast is the right answer.
- `performance-bar.md` lists the working principle for keeping
  the runtime lightweight, the readability-as-bound rule for
  optimizations, and numeric direction for the realistic
  application profile.
- `test-discipline.md` describes the integration-spine rule
  (tests exercise the real renderer binary), the three test
  modes shared across SDKs, when stubs are acceptable, and the
  pytest patterns the test fixture commits to.
- `simplicity.md` describes the clarity bar code in plushie-python
  has to clear, the discipline around when an abstraction earns
  its place, the preference for local complexity over global,
  and the codebase's functional flavor inside Python idioms.
- `elm-invariants.md` describes the contract between user apps
  and the runtime: `init/update/view` shapes, return-shape
  validation, commands as pure data, subscription diffing,
  widget event flow, scoped IDs.
- `dsl-discipline.md` describes the user-facing UI vocabulary
  (`ui.*` builder functions, the App ABC, dataclass-based
  events, decorator factory). When new patterns earn their
  place, type-checker friendliness, and the bar for error
  messages.
- `concurrency-shape.md` describes the runtime thread, reader
  thread, ThreadPoolExecutor, timer threads, the queue-based
  event injection model, and what is deliberately not used
  (asyncio in user code, multiprocessing).
- `triage.md` consolidates the routing logic from the other docs
  into a single first-match-wins flow for evaluating proposed
  work. The underlying docs remain the authority on each axis.
- `roadmap/` holds direction items that are stated goals or
  considered directions but not currently scheduled work.
  Observations that relate to a future direction get captured
  against the relevant roadmap item rather than as standalone
  work, regardless of source.

More files appear here as topics get carved out (specific named
invariants, breaking-change posture, animation-system posture,
etc.).

## How to use these docs

When a piece of proposed work shows up (a feature idea, a
refactor proposal, a library upgrade, an observation from a
review pass, a "this code feels off" instinct), the question is
not "is the proposer wrong" but "does this map to something the
project has committed to or explicitly declined." `triage.md` is
the routing tool; the other docs are the authority on each axis.

Common shapes:

- Work aligned with a stated goal: just do it.
- Work that lands on a stated non-goal: decline; the close note
  references the relevant doc so the next person sees why.
- Work tied to a roadmap item: append to that roadmap file's
  "Observations" section as context for when the direction is
  taken up. Do not open it as standalone work on the strength
  of a roadmap-only relevance.
- Work that does not map to anything here: either it is plain
  maintenance (just do it) or it is a stewardship-level
  question the docs have not yet taken a position on. In the
  latter case, the conversation happens here, before the work,
  not in a ticket queue or a refactor PR.

## Cross-SDK posture

plushie-python is one of six host SDKs sharing the renderer.
plushie-elixir is the canonical reference SDK for API shape;
when a concept's name, structure, or parameter ordering is
contested across SDKs, what plushie-elixir does is the answer.
plushie-rust is the protocol authority; wire-format questions
route there. The parity workflow lives in the sibling
`plushie-sdk-parity/` repo.

## What this directory is not

Not a marketing surface. Not a public security policy. Not an
exhaustive design document. Audience is maintainers and agents
working on the codebase. If a doc grows past one screen, it
probably wants to be split.
