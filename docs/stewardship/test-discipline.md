# Test discipline

How tests are written, what they cost, and what they commit to.
The discipline below shows up in plushie-python's own test suite,
in widget integration tests, and in parallel form across every
host SDK. It is one of the project's load-bearing conventions.

## The integration spine

Tests exercise the real renderer. The default test backend
(`mock`) runs `plushie-renderer --mock`: real binary, real wire
protocol, real codec, real Core engine. The only thing the
default backend strips is the GPU rendering step. Tests dispatch
events, read model and tree state, and assert on observable
behavior through the same wire path user apps use.

A test that passes against a pure-Python mock and would fail
against the binary is worse than no test. It gives confidence on
the exact class of bugs the integration is meant to catch: wire
format drift between encoder and renderer, startup handshake
ordering, codec edge cases, lifecycle on reconnect, the small
protocol-level details that pure-language mocks have no
mechanism to diverge on.

This is not about coverage as a metric. It is about catching
the bugs that matter where they actually live, which is at
boundaries.

## Three test modes

The renderer offers three runtime modes; the test backends
follow them by name. The naming is a cross-SDK contract.

- **mock**: microseconds to milliseconds per test. Protocol-only.
  Real binary, real wire, real Core, no rendering. The default
  for most tests; fast enough that a full suite runs through the
  binary without flinching. `pytest` uses this.
- **headless**: tens to low hundreds of milliseconds per test.
  Real rendering via tiny-skia, no display server. Used when
  the test cares about pixels: screenshot golden files
  (`plushie.testing.screenshot`), tree-hash assertions,
  layout-affecting bugs. `PLUSHIE_TEST_BACKEND=headless pytest`.
- **windowed**: seconds per test. Full iced rendering with a
  real display (headless weston on Linux, native display
  elsewhere; Xvfb works for X11-only environments). Used when
  the test cares about full window lifecycle, focus events, or
  platform-specific behavior.
  `PLUSHIE_TEST_BACKEND=windowed pytest`.

The names mean the same thing in plushie-rust, plushie-elixir,
plushie-gleam, plushie-typescript, plushie-ruby. Findings about
naming or behavior drift between the three modes route through
the parity workflow.

## Pooled mock backend

`plushie.testing.SessionPool` starts a single `plushie-renderer
--mock --max-sessions N` process and multiplexes tests over it.
Each test gets isolated state via session IDs in every wire
message. This keeps mock-mode startup amortized across the suite
rather than paid per test.

The `pytest_plushie` plugin (registered via the package's pytest
entry point) provides the `plushie_pool` fixture with
session-scoped lifecycle: pool starts at the first test that
needs it, stops at session end. Windowed mode does not pool;
each test gets its own renderer.

Tests use `AppFixture(AppClass, plushie_pool)` as a context
manager. The fixture sets up a session, gives the test a
synchronous interaction API (`click`, `type_text`, `submit`,
`toggle`, `select`, `find`, `text`, `model`, `assert_exists`,
`assert_not_exists`, `assert_text`), and tears down at exit.
All interactions go through the wire path.

## Synchronous test API

`AppFixture` runs `update` and `view` synchronously on the test
thread. There are no event-loop barriers to wait on, no async
fixtures, no explicit syncs. The fixture's command processor
handles `task`, `stream`, `done`, and `batch` inline (skipping
side-effecting commands that need a live renderer like
`window_op`); the test sees the model converge before the next
assertion.

Reading state goes through public APIs:

- `app.model` returns the current model.
- `app.find(selector)` and `app.find_all(selector)` query the
  renderer's view of the tree.
- `app.text(selector)` extracts text content from a queried
  node.
- `app.assert_exists(selector)` /
  `app.assert_not_exists(selector)` /
  `app.assert_text(selector, value)` for declarative checks.

There is no peeking at runtime internals (private threads, the
event queue, the executor). Tests that need a hook into
internal state are tests of the wrong layer; the runtime's own
unit tests cover that layer.

## When stubs are acceptable

A pure-Python stub that does not go through the renderer is
acceptable only for failure modes the binary cannot exhibit
cleanly:

- Forced renderer crash simulation (the binary cannot be told
  "panic now" via the protocol).
- Malformed wire bytes the codec rejects before any typed
  delivery path runs.
- Direct `update` calls to test pure return-shape behavior
  where no runtime context is needed (return-shape validation,
  None-return detection).
- Test infrastructure that wraps the integration primitives
  themselves.

If a test can run against the binary, it does. The bar for
adding a non-binary stub is "what failure mode does this
expose that nothing else can," answered concretely.

## Tests as documentation

Tests should read as a story for the next person who opens the
file. A clear setup, an explicit action, an assertion that
names what is being verified. Behavior-driven shape: the test
framework is incidental; what is being verified should be
obvious from the test name and the body.

pytest conventions: descriptive `test_*` names, `assert`
statements directly on values, fixtures for shared setup. The
function name is the section header; comment-based section
headers above test functions are noise.

The corollary: tests are not allowed to be slow. If a test is
slow, the underlying code path is usually slow in production
too. Speed up the code; do not accept the slow test. mock-mode
exists to skip the GPU step, not to hide a slow code path
behind a faster harness.

## Failing test before fix

For a bug fix, write the failing test first when possible. A
test added alongside the fix that would have passed without
the fix proves nothing about the bug. The failing test is the
definition of done.

Exceptions: refactors with no behavior change (the existing
suite is the regression net), and new features where the test
and the implementation arrive together.

## Type checking and lints are tests too

`pyright` runs on `src` in preflight; type errors are bugs and
fail the build. `ruff check` lints `src`, `tests`, `examples`;
warnings are fixed at the source, not silenced. `interrogate`
enforces docstring coverage on `src/plushie/`. Skipping any of
these in CI is not on offer.

## Implications

- A feature has to be testable through the renderer. If a
  feature cannot be exercised through the integration spine,
  that is a design problem with the feature, not a problem
  with the test discipline.
- "Let's mock the renderer for speed" proposals are declined.
  Speed comes from mock-mode in the real binary, which is
  already fast; the cost of a pure-Python mock is the bug
  class it hides.
- Coverage as a percentage is a non-goal (see
  `goals-and-non-goals.md`). Coverage of real surfaces is
  what matters; the integration spine is what produces it.
- Tests that reach into private runtime state (thread internals,
  the event queue, executor state) are rewritten to use the
  public `AppFixture` API or moved to the runtime's own unit
  tests where that level of inspection belongs.
