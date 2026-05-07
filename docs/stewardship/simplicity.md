# Simplicity

The bar code in plushie-python has to clear, and the recurring
tradeoffs about structure and abstraction that decide what earns
its place. The other stewardship docs (`performance-bar.md`,
`resilience.md`, `test-discipline.md`, `dsl-discipline.md`) each
carry a flavor of this implicitly; this doc states it directly so
questions about "should we extract this" or "is this clear enough"
have an explicit reference.

This is not a style guide. Naming, formatting, lint rules, and
language-specific idioms live in `ruff`, `pyright`, and
`pyproject.toml`. This doc is about the posture above those: when
to add complexity, when to refuse it, what clarity costs, and
what readability buys.

## Clarity is a constraint, not an aspiration

Code in plushie-python has to read clearly to a Python engineer
who has not been in this codebase before. "It works" is the
floor; "it can be understood without context" is the bar.

Every reader pays the cost of obscure code. The author writes
it once; many readers will read it. Small clarity wins compound
across hundreds of files; small obscurity losses compound the
other way. Same compounding argument that drives the
lightweight-by-default stance in `performance-bar.md`, applied
to reader cost instead of CPU cost.

The bar is not negotiable. Optimizations, abstractions,
defensive layers, and refactors all have to clear it; the
readability test wins ties.

## Abstraction has to earn its place

Extracting a helper, a class, a Protocol, an ABC, a module: each
carries cost. A reader has to follow the indirection, hold the
abstraction's contract in their head, and decide whether what
the call site shows reflects what the abstraction does inside.
The benefit has to clearly outweigh that cost.

Working rules:

- **Three similar lines is better than a premature abstraction.**
  Two pieces of code that look similar today might diverge
  tomorrow; extracting them now locks them together for reasons
  that may not survive contact with future requirements.
- **By the third use of a similar pattern, the abstraction
  earns consideration.** Not commitment, consideration. The
  question is whether the three uses are the same concept or
  three coincidentally similar ones.
- **An abstraction with one user is a costume, not an
  abstraction.** Single-use indirection is overhead. A
  Protocol with one impl, an ABC with one subclass, a
  decorator that wraps one call site.
- **"We might need this someday" is a reason not to extract.**
  Generic code written for hypothetical future users is the
  recurring source of half-built abstractions that nobody
  fully understands later.
- **Generic where specific would do is harder to read.** A
  concrete dataclass beats a `Generic[T]` when the
  parameterization does not have at least two real uses.
  `Any` for a value that is always one of two known types is
  worse than a `Union` of those types.

These are working positions, not absolute rules. The burden is
on the proposed abstraction to push against them.

## Local complexity over global complexity

A 200-line function that does one thing clearly is preferable
to the same logic spread across five files in pursuit of
"smaller functions." Locality is a feature: a reader can hold
the whole thing in view. Following control flow across ten
indirections costs more than reading a longer linear sequence.

Module size on its own is not a problem. A large module is not
an invitation to split unless a real change is forced to bend
around its existing shape. Refactoring without a forcing
function is a non-goal (`goals-and-non-goals.md`); this is one
of the places that rule shows up most often. The runtime is
large because the runtime does a lot; that is fine.

Files split for the sake of "smaller files" frequently end up
with cross-file dependencies that obscure the same logic the
single file made obvious. Cohesion across a file beats brevity
of any one file.

## Functional flavor inside Python idioms

The codebase is functional-first within what Python supports
naturally. The Elm-architecture pattern (`init/update/view`) is
the SDK's structural backbone for a reason. The recurring
choices that follow:

- **Pure functions where possible.** Side effects push to the
  edges (Connection owns I/O, command execution wraps
  effectful calls, the rest of the runtime is functional).
  `update` is pure: it returns a new model and commands; the
  runtime performs the commands.
- **Frozen dataclasses with slots.** Value types are
  `@dataclass(frozen=True, slots=True)`. `dataclasses.replace`
  is the update form; in-place mutation is not how model
  state evolves. `tuple` over `list` for immutable
  collections so identity comparisons remain meaningful and
  the type system catches accidental mutation.
- **Pattern matching over branching.** `match`/`case` on event
  dataclass type is the Python-native dispatch mechanism for
  the Elm `update`. Multi-clause `match` beats nested
  `if`/`isinstance` chains where the shapes are stable. When
  the shapes are not stable, a single `if`/`elif` chain is
  clearer than pattern-matched dispatch the reader has to
  reconstruct.
- **One dataclass per event family.** Click has no value;
  Input.value is `str`; Toggle.value is `bool`; Slide.value
  is `float`. Separate classes give the type checker precise
  information; a single generic event with `Any` value loses
  that. See `elm-invariants.md`.
- **Errors as values where they fit.** Recoverable conditions
  return `(ok, value)` tuples or use sentinel return values
  (e.g., `find_window_node` returns `None` when not found).
  Exceptions for invariant violations and unrecoverable errors
  (`TypeError` on bad return shape, `PlushieNotFoundError` on
  missing binary). `try`/`except` at the runtime boundaries
  for graceful degradation, not throughout the call graph.
- **Composition over inheritance.** Subclassing is for the
  user-facing ABCs (`App`, `WidgetDef`); internally, plain
  modules and free functions compose. Mixins, deep
  inheritance hierarchies, and metaclass tricks do not have
  a place here.

PEP 8 prevails on syntax (snake_case, four-space indent,
docstrings on public functions). The concept-level patterns
above converge with the rest of the project ecosystem (see
`posture.md` on the cross-SDK story).

## Type hints are part of the API

Public functions have precise type hints. `Any` is a smell;
when it is genuinely correct (the model type, opaque user
payload), it is documented. `@overload` for multi-signature
builders so the type checker can pick the right overload at
the call site. `Generic[M]` on `App` so `model` typechecks
end-to-end. `tuple[str, ...]` on event scope fields; `list`
where the value is intentionally mutable (subscription
returns).

A change that erodes type precision (broadening a parameter
to `Any`, removing an overload, dropping a `Generic` to
silence pyright) is suspect even when it compiles. The right
move is usually to fix the underlying type issue, not loosen
the signature.

## Comments earn their place too

Code should explain itself. Comments answer questions the code
cannot:

- A non-obvious constraint or invariant the surrounding code
  holds.
- A surprising or subtle behavior a reader might trip on.
- A workaround for a specific external issue that the reader
  needs to understand to evaluate the code.

Comments are not for explaining what the next line does. If a
comment is needed to explain what, the code itself usually
wants to be clearer.

Docstrings are documentation, not comments; they have a
different purpose and a different bar. Public functions and
classes have docstrings that read as user-facing documentation
(`interrogate` enforces coverage on `src/plushie/`). Internal
helpers have a one-line docstring or none, depending on
whether the name and signature already carry the meaning.

## Implications

- Abstractions added without justifying use are declined,
  even when technically correct.
- Refactors that fragment a coherent module into smaller
  files without a forcing function are declined.
- Half-built abstractions (extracted but only partially
  applied, or extracted with planned consumers never
  arriving) are bug-class. Either complete the application or
  fold the abstraction back into the call sites.
- Reviewer comments of the form "I had to re-read this three
  times" are first-class and earn a rewrite, regardless of
  whether the code is correct as written.
- `# type: ignore` comments are signals the type is wrong, not
  tools for silencing pyright. Each one earns a follow-up
  unless the reason is documented and bounded.
