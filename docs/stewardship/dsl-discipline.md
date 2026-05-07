# DSL discipline

Python does not have hygienic macros, so plushie-python's
user-facing surface is built from plain idioms: builder
functions, dataclasses, ABCs, and the occasional decorator.
This doc describes the posture for adding to that surface,
deciding where compile-time-ish guarantees come from
(type hints, pyright), and keeping the user-facing API honest.

The Python equivalent of `plushie-elixir/macro-dsl.md`.

## What the user-facing surface is

A small handful of import points cover the full vocabulary:

- `plushie.ui` - builder functions for every widget. Returns
  plain dicts in the wire-format node shape. Users can freely
  mix `ui` calls with raw dicts.
- `plushie.canvas` - canvas shape and group builders for
  custom drawing.
- `plushie.events` - one frozen dataclass per event family
  (`Click`, `Input`, `Toggle`, `Slide`, `KeyEvent`,
  `WindowEvent`, etc.). `match` on class type is the dispatch
  mechanism.
- `plushie.commands` - `Command` dataclass with static factory
  methods. Pure data; the runtime executes them.
- `plushie.subscriptions` - `Subscription` dataclass with
  static factory methods.
- `plushie.types` - shared value types (`Length`, `Padding`,
  `Color`, `Font`, `Border`, `Shadow`, `StyleMap`, `A11y`).
- `plushie.App` and `plushie.create_app` - the two app entry
  shapes.

The shape is:

- Container builders take children as `*args`, options as
  keyword-only kwargs.
- Named containers take `id` as the first positional arg.
- Anonymous containers (`column`, `row`, `stack`) have no
  positional id; an optional `id=` kwarg does not create
  scope.
- Leaf widgets are id-first for interactive
  (`button("save", "Save")`); display widgets that rarely
  need explicit IDs have an auto-id sugar form
  (`text("Hello")` works; `text("count", "Count: 1")` works
  too).
- `@overload` decorators make multi-signature builders
  type-check at the call site. Positional-only markers (`/`)
  pin id and content args.

The surface is not a backdoor for arbitrary code generation.
Every builder is a thin function over a dict literal; what a
builder returns is what a user could have written by hand.

## When a new user-facing pattern earns its place

The surface is permissive about adding widgets (a new `ui.foo`
that returns a dict is local and obvious; no extension
question). It is conservative about adding new patterns (a new
decorator, a new ABC, a new dispatch mechanism, a new
event-shape convention).

A new pattern earns its place when:

- At least two existing or imminent users want the same
  shape.
- The pattern replaces a runtime construct that is harder to
  read or harder to type-check at the call site.
- A meaningful class of bugs becomes detectable by pyright
  that runtime checks would catch only on first use.
- The resulting code reads as cleanly as what the user would
  have written by hand.
- The cross-SDK question has been answered first; the new
  pattern matches plushie-elixir's shape (or a deliberate,
  documented Python deviation like `Command.task`).

A new pattern does not earn its place when:

- The argument is "we could check this at compile time"
  (i.e. with `Literal` types or generics). Type-checker
  reach has costs (slower checks, harder error attribution,
  IDE pain on incomplete code); the bug class has to be real
  and recurring.
- The argument is "this would let users write less code." If
  the existing form already reads cleanly, fewer characters
  is not the bar.
- The argument is "this would be more Pythonic." See
  `posture.md`. Cross-SDK shape is the constraint; Python
  idiom is downstream of that.

A new pattern is rejected when:

- It hides indirection that a reader of the call site would
  not expect (a decorator that mutates module state at
  import time, a metaclass that rewrites methods, a builder
  that returns different dict shapes based on argument
  identity).
- The resulting code reads worse than the equivalent
  hand-written form.
- The error messages it produces are vague or surface from
  the wrong layer of the stack.

## Type-checker-friendly by default

pyright runs on `src` in preflight. The user-facing surface
holds itself to a higher type-precision bar than internal
helpers because users feel pyright errors on their code:

- `App[M]` is generic on the model type. `init`, `update`,
  `view`, `subscribe`, `handle_renderer_exit`, and
  `window_config` all type-check end-to-end against `M` for
  the user's chosen model.
- `@overload` for builders with multiple call shapes (e.g.
  `text("Hello")` vs `text("count", "Count: 1")`).
  Positional-only markers (`/`) pin which argument is which.
- Event dataclasses are frozen with explicit field types
  (`Click.id: str`, `Input.value: str`, `Toggle.value: bool`,
  `Slide.value: float`). `match` on class type then gives
  pyright precise narrowing.
- `tuple[str, ...]` for immutable collections in dataclasses
  (event scope, model item lists in examples). `list[T]` is
  for genuinely mutable returns (the subscription list from
  `subscribe`).
- `Any` is a smell. When unavoidable (the user's model type
  in framework-internal code, opaque payload values), it is
  documented at the site.

A change that erodes type precision (broadening a parameter
to `Any`, removing an overload, dropping a `Generic` to
silence pyright) is suspect even when it compiles. The right
move is usually to fix the underlying type, not loosen the
signature.

## Runtime validation as a backstop

Some checks cannot be expressed in the type system and live in
the runtime instead:

- Return-shape validation in `unwrap_result` (TypeError on
  the wrong shape). See `elm-invariants.md`.
- `None` return detection from `update` (logged warning, keep
  previous model).
- Window-root validation: the renderer rejects a tree whose
  top level is not a window node, and the error surfaces back
  through the runtime.
- Tree normalization rejects placeholder shapes that escape
  composite widget rendering paths.

These are deliberate; the corresponding type-system reach
would either be impossible (the dynamic event match-fall-
through case) or would impose a large per-app type-annotation
burden (window-root tree shape) for negligible win.

## Errors point at the user's code

A traceback that surfaces from deep inside `plushie.runtime`
without any sign of the user's call site is a failure mode.
The runtime's `try`/`except` handlers log via
`logger.exception`, which preserves the full traceback
including user frames. Custom `TypeError` messages from
`unwrap_result` and similar say what is wrong in the user's
terms (the function name, the offending value), not in the
framework's internals' terms.

A useful error message:

- Names what is wrong in the user's terms (the callback name,
  the field name, the offending value).
- Names what was expected (the supported shapes, the required
  type, the valid alternatives).
- Surfaces near the user's code, not deep in the runtime.

Vague error messages from the framework are bug-class. They
cost users time and they cost us issue triage.

## What this looks like in practice

- A user proposes "let `update` be `async def`." Cross-SDK
  question answered first: no other SDK has this. Real
  problem? `Command.task` already covers async work. Outcome:
  decline; reference `goals-and-non-goals.md`.
- A user proposes "auto-derive an event dataclass from a
  schema." Real bug class? Field drift between similar event
  families is rare. Two real users? No. Outcome: decline;
  the explicit-dataclass shape is what makes `match` work.
- A user proposes "a context-manager DSL for nested
  containers." `with ui.column():` style. Real bug class?
  No (containers already nest fine via `*args`). Generated
  code reads cleaner? No (positional args read cleaner).
  Outcome: decline.
- A user proposes "make `Command.task` accept an `async def`
  too." Real bug class? Maybe (Python users reach for
  `async`). Two real users? Likely. Generated code reads
  cleanly? Yes if the bridge to the executor is clean.
  Outcome: consider; the shape question is whether `async
  def` user functions get scheduled on a private asyncio
  loop or on the existing executor with `asyncio.run`. Pick
  the simpler one and document.
