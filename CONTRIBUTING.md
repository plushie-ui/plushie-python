# Contributing to plushie-python

## Development setup

```bash
git clone <repo-url>
cd plushie-python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

You need Python 3.12 or later. The `.venv` directory is expected
by pyright for type resolution.

## Running checks

### Preflight (all checks)

```bash
./preflight
```

This mirrors CI and runs everything: format check, lint, type
check, and tests. Run this before committing.

### Individual tools

```bash
ruff format src tests examples          # auto-format
ruff format --check src tests examples  # check formatting (CI mode)
ruff check src tests examples           # lint
pyright src tests examples              # type check
pytest                                  # tests (mock backend)
```

### Test backends

Tests run against the real plushie renderer binary. Download it
first:

```bash
python -m plushie download
```

Three backends are available:

- **mock** (default) -- no rendering, synthetic events, fastest
  (~ms per test). No display server needed.
- **headless** -- real rendering via tiny-skia, no display server
  (~100ms per test).
- **windowed** -- real iced windows, needs a display server or Xvfb
  (~seconds per test).

Select with the `PLUSHIE_TEST_BACKEND` environment variable:

```bash
pytest                                       # mock (default)
PLUSHIE_TEST_BACKEND=headless pytest         # headless
PLUSHIE_TEST_BACKEND=windowed pytest         # windowed
```

Layer 0 tests (protocol, framing, events, tree, ui, types) are pure
Python and run without a binary. Layer 1+ tests (connection, runtime,
integration) require the binary.

### Coverage

```bash
coverage run -m pytest                # collect coverage
coverage report --show-missing        # terminal report
coverage html                         # HTML report in htmlcov/
```

Coverage is configured in `pyproject.toml` under `[tool.coverage.*]`.
Available for local use but not enforced in CI.

## Build verification

To verify the package builds correctly and passes PyPI checks:

```bash
python -m build
twine check dist/*
```

This is not part of `./preflight` (too slow for every run), but should
be checked before publishing a release.

## Documentation

Build the docs site locally:

```bash
mkdocs serve       # live preview at http://127.0.0.1:8000
mkdocs build       # build static site to site/
```

CI runs `mkdocs build --strict` on every push and deploys to GitHub
Pages on pushes to `main`.

## Code style

Formatting and linting are handled by ruff. No manual style rules
beyond what the tools enforce.

- `ruff format` for formatting (double quotes, 88 char line length)
- `ruff check` for linting (pycodestyle, pyflakes, isort,
  flake8-bugbear, pyupgrade, flake8-simplify, ruff-specific)

Run `ruff format src tests examples` before committing to
auto-fix formatting. The CI workflow checks formatting with
`--check` and will reject unformatted code.

## Type checking

Pyright in standard mode covers `src`, `tests`, and `examples`.
All new code should pass `pyright` cleanly.

Use `# type: ignore[rule-name]` sparingly and only when the type
checker genuinely cannot understand the code (e.g. mock objects,
dynamic protocol testing). Include the specific rule name so
future readers know what's being suppressed.

## Adding a new widget builder

Widget builders live in `src/plushie/ui.py`. Each function returns
a plain dict matching the wire protocol's node shape:

```python
{"id": ..., "type": ..., "props": {...}, "children": [...]}
```

Steps:

1. Add the builder function to `ui.py`. Follow the existing
   conventions: `id` as the first positional-only argument for
   interactive widgets, `@overload` for auto-id sugar on display
   widgets.
2. Add the function name to `__all__` in `ui.py`.
3. Add tests in `tests/test_ui.py` covering the builder's
   signatures, props encoding, and edge cases.
4. If the widget has a unique event type, add the event dataclass
   too (see below).

## Adding a new event type

Event dataclasses live in `src/plushie/events.py`. Each wire event
family gets its own frozen dataclass with precisely typed fields.

Steps:

1. Add the dataclass to `events.py`. Use `frozen=True, slots=True`.
   Widget events carry `id: str` and `scope: tuple[str, ...] = ()`.
   Subscription events are global (no scope).
2. Add the class name to `__all__` in `events.py`.
3. Add the decoding case to `decode_message()` in
   `src/plushie/protocol.py`.
4. Add the new type to the `decode_message` return type union.
5. Add tests in `tests/test_events.py` for construction and field
   access, and in `tests/test_protocol.py` for wire decoding.

## Documentation tests

The `tests/docs/` directory contains tests that mirror documentation
examples. Each test file corresponds to a docs page. Tests are
linked to their docs via HTML comment markers at the top of the
test file:

```python
"""Tests mirroring the getting started guide.

<!-- test: test_init_returns_model, test_update_increments
     -- keep the guide in sync with these tests -->
"""
```

When changing behavior covered by docs, update the corresponding
test in `tests/docs/` to confirm the docs stay accurate.

## PR process

1. Create a branch from `main`.
2. Make your changes. Run `./preflight` and fix any failures.
3. Push and open a PR against `main`.
4. PRs require all CI checks to pass (lint, type check, tests on
   mock and headless backends).
5. Keep PRs focused -- one logical change per PR.
