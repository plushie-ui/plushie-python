# Project posture

What plushie-python is, who it is for, and the disciplines that
keep it that way.

## What plushie-python is

The Python host SDK for Plushie. An Elm-architecture app runtime
that drives a renderer subprocess (Rust binary, native windows via
iced) over a typed wire protocol on stdin/stdout. The SDK ships as
a PyPI package; user apps subclass `plushie.App[M]` (or use the
`create_app()` decorator factory), declare their UI with the
`plushie.ui` builder functions, and the runtime handles diffing,
command dispatch, subscriptions, and reconnect lifecycle.

This SDK is one of six host SDKs sharing the renderer (Elixir,
Rust, Gleam, Python, Ruby, TypeScript). The renderer binary is
shared; each SDK implements its own runtime against it.

## Audience

- App developers writing Plushie apps in Python. They see the
  `plushie.App` ABC, the `plushie.ui` builder vocabulary, the
  `Command` and `Subscription` factory APIs, the typed event
  dataclasses, and the `AppFixture` test driver.
- Widget authors writing pure-Python composite or canvas widgets
  via `WidgetDef`, or wiring Rust-backed widgets in through
  `NativeWidget` plus `python -m plushie build`.
- SDK maintainers. The connection layer, the runtime threads,
  the wire codec, the test session pool.

The PyPI package's public API is anything imported from
`plushie`, `plushie.ui`, `plushie.events`, `plushie.commands`,
`plushie.subscriptions`, `plushie.canvas`, `plushie.types`,
`plushie.testing`, `plushie.transport`, and the top-level
`plushie.run`/`plushie.start`. Names prefixed with `_` are
internal regardless of module. Submodules under `plushie.tree`
expose `Node`, `diff`, `normalize_view`, `find`, and similar
helpers; the rest of the tree internals are not part of the
stable surface.

## Cross-SDK relationship

plushie-elixir is the canonical reference SDK for API shape.
plushie-python follows it on contested questions.

- **API shape tiebreaker.** When a concept's name, structure, or
  parameter ordering is contested across SDKs, what plushie-elixir
  does is the answer. plushie-rust is the protocol authority
  (wire format, message variants, codec); plushie-elixir is the
  shape authority (what user-facing concepts look like).
- A rename here is a six-SDK change, not a refactor. The bar for
  renaming a widget prop, an event field, a command shape, or a
  subscription type is "is the new name actually better across
  every SDK," not "does it fit Python conventions better." If
  the cross-SDK answer is the new name, plushie-elixir leads,
  plushie-python follows.
- Cross-SDK parity is audited via the sibling
  `plushie-sdk-parity/` repo. Findings about parity drift route
  through that workflow rather than as standalone work here.
- Within-language idiom prevails on syntax. PEP 8 naming
  (snake_case for functions, PascalCase for classes), `match`
  statements over visitor patterns, `dataclass(frozen=True,
  slots=True)` for value types, `tuple` over `list` for
  immutable collections, type hints throughout. Concepts,
  names, parameter ordering, and behavior converge with the
  other SDKs.

"More Pythonic" alone is not justification for breaking parity.
"The current shape is wrong everywhere and we are choosing the
better shape" is, and the change ripples.

There are a handful of unavoidable Python-specific deviations.
`async` is a reserved word, so the async-work command is
`Command.task(...)`. Dataclasses are the value-type vocabulary
because Python has no native sum types. These are noted at the
relevant invariants and do not extend a license to drift on
other shape questions.

## Stage

Pre-1.0. There is no backwards-compatibility obligation today.
When the best design requires renaming a method, a field, or
restructuring a module, that is the right call. The CHANGELOG
notes breaking changes explicitly. Pin to an exact version.

The 1.0 boundary is when stability obligations begin. Until
then, the priority is getting the shape right, not preserving
the current shape. Pre-1.0 is the time to settle questions
about API shape, naming, and structure that will be expensive
to revisit.

API stability hardening (deprecation warnings, sealed callback
lists, `Final` annotations on public constants, `@override`
audits) lands in a single planned sweep at the 1.0 cut, not
piecemeal during normal development.

## Disciplines

Recurring decision rules. Not negotiable on a per-ticket basis.

- **Tests run through the real renderer.** The default test
  backend runs `plushie-renderer --mock`: real binary, real wire
  protocol, real codec, real Core engine, no GPU. A test that
  passes against a pure-Python mock and would fail against the
  binary is worse than no test. Stubs are reserved for failure
  modes the binary cannot exhibit. See `test-discipline.md`.
- **Cross-SDK claims are verified, not assumed.** When the
  question is "does plushie-elixir do this the same way," the
  answer comes from reading source on each side. "It looks
  like" is not a verification.
- **Type checker is part of the build.** pyright runs in
  preflight; type errors are bugs. Public APIs use precise
  types (`@overload` for multi-signature builders, `Generic[M]`
  for the App, `tuple[str, ...]` not `list[str]` where
  immutability matters). `Any` is a smell; if it is unavoidable,
  it is documented.
- **Design before code at boundaries.** Public PyPI API, the
  `ui` builder surface, the wire protocol on the Python side,
  the App ABC, the test fixture contract. Internal refactors
  can iterate fast; boundary changes pay the design tax up
  front.
- **Clarity is the bar.** Code reads clearly to someone new to
  the file; abstractions earn their place by use, not by
  hypothesis; complexity is a cost. See `simplicity.md`.
- **No half-built features.** A feature lands fully or not at
  all. Half-built features create drift in the parity surface
  and accumulate into "the docs say it does X but three SDKs
  do not actually."
- **Local cleanup, not scope creep.** Small, low-risk
  improvements to code under active modification are welcome.
  Larger or risky adjacent improvements get noted and advocated
  for as follow-on work, not silently rolled into the current
  change.
- **No legacy or compatibility shims.** Pre-1.0; remove dead
  paths cleanly rather than preserving old behavior.
