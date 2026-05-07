# Goals and non-goals

The objectives plushie-python optimizes for, and the explicit
non-objectives it declines work against. The lists are
deliberately short; they earn their place by being recurring
decision criteria, not by enumerating every aspiration.

## Goals

Testable shipping criteria. Findings that improve any of these
are real work.

- **Wire protocol fidelity on the host side.** Messages encode
  and decode identically against every other SDK and the
  renderer; the codec stays in lockstep with the renderer's
  spec (authority lives in plushie-rust); values round-trip
  through MessagePack and JSONL without coercion drift.
- **Cross-SDK concept parity.** Concepts (event shapes, widget
  props, command structures, subscription types) converge with
  the other host SDKs at the semantic level. plushie-elixir is
  the shape tiebreaker; see `posture.md`.
- **Elm-architecture purity.** `init/update/view` is the user's
  contract. Return shapes are validated; commands are pure data;
  effects push to the edges; `view` is a pure function of model.
  No `async`/`await` in user code. The runtime preserves these
  invariants. See `elm-invariants.md`.
- **Lightweight runtime.** Idle apps do no measurable work. No
  polling, no per-frame walking when nothing changed, no
  spinning subscription threads, no asyncio overhead in the hot
  path. See `performance-bar.md`.
- **Fault tolerance across the wire.** Renderer crash is detected
  by the reader thread, the runtime reconnects with exponential
  backoff, replays settings, and re-syncs the tree from a fresh
  full snapshot. App exception in `init/update/view` reverts to
  the last good state and surfaces the error. Neither side takes
  the other down. See `resilience.md`.
- **Type checker support is real.** Public APIs carry precise
  types. `App[Model]` is generic on the model type; event
  dataclasses give `match` precise patterns; `@overload` makes
  multi-signature builders type-check at the call site.
  pyright on `src` is part of preflight.

## Non-goals

Explicit non-objectives. Findings or proposals that push the
project toward them get declined; they are not candidates that
lost a priority contest.

- **Backwards compatibility before 1.0.** The right design wins;
  the rename happens. PyPI consumers expect breaking changes in
  pre-1.0 minor bumps; the CHANGELOG names them.
- **Per-Python API ergonomics that diverge from cross-SDK
  shape.** See `posture.md`. "More Pythonic" alone is not
  sufficient; the shape question routes through the parity
  workflow. Unavoidable Python-specific deviations (e.g.
  `Command.task` instead of `async`) are noted at the
  relevant invariants.
- **API stability hardening before 1.0.** Deprecation warnings,
  sealed callback lists, documented compatibility windows,
  `Final` annotations on public constants, `@override` audits.
  These happen in a single planned sweep at the 1.0 cut, not
  piecemeal during normal development.
- **Coverage targets as a metric.** Test discipline is "exercise
  real surfaces through the renderer," not "hit a percentage."
  See `test-discipline.md`.
- **Mocking the renderer for speed.** mock-mode in the real
  binary is already fast (microseconds to milliseconds per
  test); a pure-Python mock is faster only at the cost of the
  exact bug class the integration spine catches.
- **asyncio in user code.** The Elm loop is synchronous on a
  single runtime thread. Async work is expressed as
  `Command.task(...)` and runs in a `ThreadPoolExecutor`;
  results arrive as `AsyncResult` events. Adding an async
  variant of `update`, an async `view`, or an asyncio-native
  event loop is out of scope. Hosting plushie inside an
  asyncio app is fine; the SDK runs its own thread.
- **Micro-optimization at the cost of readability.** Clever
  encoding, lookup, or layout schemes in hot paths need to
  earn the obscurity with measurement. Optimizations that look
  clean and do not damage readability are welcome; see
  `performance-bar.md`.
- **Refactoring without a forcing function.** Module size or
  file length alone is not a reason to refactor. The trigger
  is a real change that the existing structure cannot
  accommodate cleanly.
- **DSL extensions for hypothetical future widgets.** A new
  `ui.*` builder, a new event dataclass, a new command factory
  earns its place when at least two real users would benefit.
  "We might want this someday" is a reason not to extend the
  surface.
- **Defending against speculative deployment shapes.** Untrusted
  multi-tenant runtimes, browser-as-arbitrary-host, sandboxed
  user apps inside other Python runtimes. None of these are
  current goals. Defenses against them are out of scope unless
  and until the shape is taken up.
