# Testing

Tests drive the real renderer binary through a pytest fixture. All
interactions go through the wire protocol. There are no Python-side
mocks of widget behaviour, no synthetic event objects, no
hand-written DOM. The renderer's `--mock` mode is the mock, and the
same `AppFixture` code runs against the headless renderer (real
rendering, no display) and the windowed renderer (real windows) too.

The testing package lives in `plushie.testing`. Its public surface is
the `AppFixture` context manager, the `SessionPool` that owns the
shared renderer process, the `Element` wrapper for query results, the
`TreeHash` and `Screenshot` golden-file helpers, and the `WidgetFixture`
harness for exercising custom widgets in isolation. The `plushie_pool`
pytest fixture is auto-registered by the pytest plugin entry point.

## Quick start

```python
import pytest

from plushie.testing import AppFixture

from myapp import Counter


@pytest.fixture
def app(plushie_pool):
    with AppFixture(Counter, plushie_pool) as f:
        yield f


def test_increment(app):
    assert app.model.count == 0
    app.click("#inc")
    assert app.model.count == 1
    assert app.text("#count") == "Count: 1"
```

`AppFixture` takes an `App` subclass (instantiated for you) or an
existing `App` / `AppBuilder` instance, and a running `SessionPool`.
The context manager allocates a fresh session on entry and releases
it on exit. Each session is isolated: the pool sends a `reset_session`
to the renderer when `close()` runs so the next test starts clean.

`AppFixture` processes commands synchronously inside the fixture
thread. Tasks, streams, batches, and dispatch commands run inline
through `app.update`. Widget and window ops, timers, effects, and
cancellations require a live runtime and are silently skipped.
Everything else (interactions, queries, assertions) is synchronous
too: each call sends a wire message and waits for the matching
response before returning.

## Backends

Backend selection is controlled by the `PLUSHIE_TEST_BACKEND`
environment variable. The pytest plugin reads it at session start
and passes the mode to `SessionPool`.

| Backend | Speed | Rendering | Display | Use case |
|---|---|---|---|---|
| `mock` | fastest | protocol only | none | default in CI and local dev |
| `headless` | slower | software rasterisation | none | screenshot tests in CI |
| `windowed` | slowest | GPU (iced) | required | manual verification |

```bash
pytest                                       # mock (default)
PLUSHIE_TEST_BACKEND=headless pytest         # real rendering, no display
PLUSHIE_TEST_BACKEND=windowed pytest         # real windows
```

The test code is identical across all three. Interactions that depend
on layout or pixel output (screenshot hashes, anything driven by
`interact_step`) only differ at the renderer. In headless mode the
renderer sends intermediate `interact_step` messages during a single
interaction; the fixture handles them transparently via an `on_step`
callback that re-renders and replies with the current tree.

Set `PLUSHIE_TEST_MAX_SESSIONS` to change the pool size (default 8).

## AppFixture reference

### Properties

| Property | Type | Description |
|---|---|---|
| `model` | `M` | Current application model |
| `tree` | `Node \| None` | Current normalized UI tree |

### Interactions

Each interaction sends an `interact` message to the renderer,
collects the events it produces, routes each through `app.update`,
processes any resulting commands, re-renders, and diffs the view
tree to send a patch (or snapshot on first render).

| Method | Widget types | Wire action |
|---|---|---|
| `click(selector)` | `button` | `click` |
| `type_text(selector, text)` | `text_input`, `text_editor` | `type_text` |
| `submit(selector)` | `text_input` | `submit` |
| `toggle(selector)` | `checkbox`, `toggler` | `toggle` |
| `select(selector, value)` | `pick_list`, `combo_box`, `radio` | `select` |
| `slide(selector, value)` | `slider`, `vertical_slider` | `slide` |
| `scroll(selector, delta_x, delta_y)` | `scrollable` | `scroll` |
| `paste(selector, text)` | `text_input`, `text_editor` | `paste` |
| `sort(selector, column)` | `table` | `sort` |
| `canvas_press(selector, x, y, button)` | `canvas` | `canvas_press` |
| `canvas_release(selector, x, y, button)` | `canvas` | `canvas_release` |
| `canvas_move(selector, x, y)` | `canvas` | `canvas_move` |
| `pane_focus_cycle(selector)` | `pane_grid` | `pane_focus_cycle` |
| `press(key)` | n/a | `press` |
| `release(key)` | n/a | `release` |
| `type_key(key)` | n/a | `type_key` |
| `move_to(x, y)` | n/a | `move_to` |

`click`, `type_text`, `submit`, and `toggle` check the target widget
type against the local tree and raise `TypeError` with a suggested
method name when it does not match (for example, calling `click` on
a checkbox raises with a suggestion to use `toggle` instead). `submit`
reads the current value from the local tree and sends it in the
payload. `toggle` reads the current checked / is_toggled state and
sends the inverted value.

Key strings follow the `press`/`release`/`type_key` convention
`"<modifier>+<modifier>+<key>"`. Modifiers are `ctrl`, `shift`,
`alt`, `logo`, `command`. Single-character keys are lowercased;
multi-character keys are resolved case-insensitively against
`plushie.keys`:

```python
app.press("ctrl+s")
app.type_key("Enter")
app.type_key("ArrowRight")
app.release("shift+a")
```

Unknown named keys raise `ValueError`.

### Queries

Queries hit the renderer directly (not the local tree), so they
observe the state after the last interaction settled.

| Method | Returns | Description |
|---|---|---|
| `find(selector)` | `Element` | Raise `ElementNotFoundError` if missing |
| `query(selector)` | `Element \| None` | Return `None` if missing |
| `text(selector)` | `str \| None` | Extract display text (local tree first, then renderer) |
| `exists(selector)` | `bool` | Local tree first, then renderer fallback |
| `find_by_role(role)` | `Element \| None` | By accessible role |
| `find_by_label(label)` | `Element \| None` | By accessible label |
| `find_focused()` | `Element \| None` | Currently focused element |
| `resolved_a11y(selector)` | `dict[str, Any]` | Merged a11y map with widget-level inference |

### Assertions

| Method | Description |
|---|---|
| `assert_text(selector, expected)` | Display text matches |
| `assert_exists(selector)` | Element is in the tree |
| `assert_not_exists(selector)` | Element is not in the tree |
| `assert_model(expected)` | Current model equals expected value |
| `assert_a11y(selector, expected)` | Resolved a11y dict contains expected keys |
| `assert_role(selector, role)` | Inferred accessibility role matches |
| `assert_no_diagnostics()` | No validation diagnostics were collected |
| `assert_tree_hash(name)` | Structural tree hash matches golden file |
| `assert_screenshot(name)` | Screenshot hash matches golden file |

`assert_text`, `assert_exists`, and `assert_not_exists` include the
set of available widget IDs in their failure messages, which makes
typos obvious.

### Lifecycle

| Method | Description |
|---|---|
| `reset()` | Re-run `init`, process commands, send a fresh snapshot |
| `close()` | Release the session back to the pool (called by `__exit__`) |
| `await_async()` | No-op; commands already processed synchronously |
| `advance_frame(timestamp)` | Drive renderer animation clock to a timestamp in ms |
| `skip_transitions()` | Advance 10 s forward to complete any in-flight transition |
| `save_screenshot(name)` | Write the PNG to `test/screenshots/<name>.png` |
| `get_diagnostics()` | Drain and return collected diagnostic events |

### Internal state

`fixture._session_id` and `fixture._pool` are accessible for tests
that need to send raw wire messages or swap the session on the
underlying `Connection`. The fixture temporarily sets `conn.session`
to its own session ID for the duration of each interaction or
query, then restores the previous value, so concurrent sessions on
the same pool do not cross wires.

## Selectors

Selectors are the same strings the widget tree uses. The fixture
resolves them against the local tree first and falls back to the
renderer's `find_by_id` semantics when the local resolution is
ambiguous or when the selector targets a query-only pseudo-selector.

| Form | Matches |
|---|---|
| `"#id"` | Local widget ID, unscoped |
| `"#scope/path/id"` | Exact scoped path |
| `"window_id#id"` | Widget in a specific window |
| `"window_id#scope/path/id"` | Scoped path in a specific window |
| `"text content"` | Widget with matching text prop (fallback) |
| `"[role=button]"` | Attribute selector, passes through to renderer |
| `"[text=Save]"` | Attribute selector, passes through to renderer |
| `":focused"` | Currently focused widget, passes through to renderer |

An unscoped `"#id"` raises `ValueError` when the tree contains the
same local ID in multiple windows. Prefix the selector with the
window ID (`"settings#save"`) or use the full scoped path
(`"#settings/form/save"`) to disambiguate.

Partial scoped paths work too: `"#todo-1/done"` matches any node
whose full ID ends with `/todo-1/done` or `#todo-1/done`, which
mirrors the renderer's `find_by_id` lookup.

When `find` raises `ElementNotFoundError` or `assert_*` fails, the
error message lists the widget IDs present in the local tree to help
diagnose typos.

## Element

`Element` is a frozen dataclass wrapping the raw node dict returned
by a query. It exposes the node's structure through typed
properties and extracts display text in priority order.

```python
el = app.find("#greeting")
assert el.type == "text"
assert el.id == "greeting"
assert el.text() == "Hello, world!"
```

| Property / method | Returns | Description |
|---|---|---|
| `id` | `str` | Node ID, scoped if inside a named container |
| `type` | `str` | Widget type name |
| `props` | `dict[str, Any]` | Raw props dict |
| `children` | `list[Element]` | Child nodes, wrapped |
| `text()` | `str \| None` | First of `content`, `label`, `value`, `placeholder` |
| `a11y()` | `dict[str, Any]` | Explicit a11y props |
| `resolved_a11y()` | `dict[str, Any]` | a11y map with widget-level inference |
| `inferred_role()` | `str` | `a11y.role` if set, otherwise the widget `type` |

`resolved_a11y` layers inference on top of the explicit a11y prop so
tests see what assistive technology will see: `placeholder` seeds
`description` for `text_input`, `text_editor`, `combo_box`, and
`pick_list`; `alt` seeds `label` for `image`, `svg`, and `qr_code`.
Explicit values win over inferred ones.

## Tree hash and screenshot assertions

Golden files pin the UI at a known-good shape and catch unintended
changes. The helpers are separate because tree hashes compare
structure and screenshots compare pixels; the former works on all
backends, the latter only on `headless` and `windowed`.

```python
def test_initial_layout(app):
    app.assert_tree_hash("counter-initial")

def test_styled_render(app):
    app.assert_screenshot("counter-styled")
```

First run creates the golden file at `test/snapshots/<name>.tree_hash`
or `test/screenshots/<name>.screenshot_hash`. Subsequent runs
compare. When the UI intentionally changes, regenerate the golden
files:

```bash
PLUSHIE_UPDATE_SNAPSHOTS=1 pytest       # tree hashes
PLUSHIE_UPDATE_SCREENSHOTS=1 pytest     # pixel hashes
```

The two environment variables are independent so a structural change
does not silently overwrite screenshot baselines and vice versa.

`save_screenshot(name)` saves the full PNG under `test/screenshots/`
for visual inspection. It requires a backend that returns pixel data
(`headless` or `windowed`) and raises `RuntimeError` otherwise.

The `TreeHash` and `Screenshot` dataclasses are also usable directly
for custom assertions:

```python
from plushie.testing import TreeHash, Screenshot

th = TreeHash.from_tree("snapshot_name", tree)
th.assert_match("test/snapshots")

s = Screenshot.from_response(response_msg, backend="headless")
s.assert_match("test/screenshots")
```

A `backend` tag on either adds a suffix to the golden file path
(`snapshot_name.headless.sha256`) so mock and headless baselines can
coexist.

## SessionPool

`SessionPool` owns a single `plushie --mock --max-sessions N`
subprocess (or the equivalent for headless / windowed) and
multiplexes test sessions over it.

```python
from plushie.testing import SessionPool

pool = SessionPool(mode="mock", max_sessions=16)
pool.start()
try:
    session_id = pool.register()
    pool.send_snapshot(session_id, tree)
    pool.unregister(session_id)
finally:
    pool.stop()
```

| Method | Description |
|---|---|
| `start()` | Spawn the subprocess, send initial settings, wait for `hello` |
| `stop()` | Close the connection and clear the session table |
| `register()` | Allocate a unique session ID (raises when the pool is full) |
| `unregister(session_id)` | Reset the session on the renderer and release the slot |
| `send(session_id, msg)` | Fire-and-forget wire send with `session` injected |
| `send_settings(session_id, settings)` | Send a `settings` message |
| `send_snapshot(session_id, tree)` | Send a `snapshot` message |
| `send_patch(session_id, ops)` | Send a `patch` message |
| `interact(session_id, action, ...)` | Send an `interact` and collect events |
| `query_find(session_id, selector)` | Query for a single node |
| `query_tree(session_id)` | Query for the full tree |
| `tree_hash(session_id, name)` | Request a structural tree hash |
| `screenshot(session_id, name)` | Request a screenshot (PNG + hash) |
| `is_alive` | Property: whether the subprocess is running |

Session IDs are strings of the form `pool_<n>`. The pool holds a
session-swap lock around every renderer call that needs to switch
the `Connection.session` field so concurrent tests on the same pool
do not interleave each other's messages.

## pytest plugin

The `plushie.testing.plugin` module is registered as a `pytest11`
entry point, so pytest discovers it automatically once `plushie` is
installed. It starts one `SessionPool` at `pytest_configure` and
stops it at `pytest_unconfigure`.

The `plushie_pool` fixture is session-scoped and yields the running
pool. If the pool failed to start (for example, the plushie binary
is missing), the fixture calls `pytest.skip` so integration tests
are skipped rather than errored.

Enable the plugin explicitly in `pyproject.toml` if the entry point
is not picked up (for example in src layouts without an installed
package):

```toml
[tool.pytest.ini_options]
addopts = "-p plushie.testing.plugin"
```

`conftest.py` can wrap `plushie_pool` in a per-test fixture that
hands out an `AppFixture`:

```python
# tests/conftest.py
import pytest

from plushie.testing import AppFixture

from myapp import Counter


@pytest.fixture
def counter(plushie_pool):
    with AppFixture(Counter, plushie_pool) as f:
        yield f
```

## Diagnostics and logging

Prop validation diagnostics emitted by the renderer are collected
into `fixture._diagnostics` as `Diagnostic` or `DiagnosticMessage`
events. `assert_no_diagnostics()` raises with the full list on
failure, including level, code, and message for each entry.
`get_diagnostics()` drains the buffer and returns the accumulated
events; use it when asserting on specific diagnostics rather than
"none at all".

Plushie logs to the `plushie.testing` logger at `INFO` and `DEBUG`.
Use pytest's built-in `caplog` fixture to capture and assert on log
output:

```python
import logging

def test_logs(app, caplog):
    with caplog.at_level(logging.WARNING, logger="plushie.testing"):
        app.click("#risky")
    assert "something fishy" in caplog.text
```

## WidgetFixture

`WidgetFixture` hosts a single custom widget in a parameterized
harness app (window > column > widget) and exposes the emitted
events. It inherits every `AppFixture` method and adds:

| Property | Description |
|---|---|
| `last_event` | Most recent event emitted by the widget, or `None` |
| `events` | Tuple of all emitted events, oldest first |
| `last_value` | `value` attribute of the most recent event, or `None` |

```python
from plushie.testing import WidgetFixture

from myapp.widgets.star_rating import StarRating


def test_star_rating(plushie_pool):
    with WidgetFixture(StarRating, "rating", plushie_pool) as w:
        w.canvas_press("#rating", 200.0, 10.0)
        assert w.last_event is not None
        assert w.last_value == 3
```

See [Custom Widgets reference](custom-widgets.md) for more on
building widgets that work with this harness.

## Running tests in CI

CI pipelines should set `PLUSHIE_TEST_BACKEND=headless` when they
care about real rendering (screenshot tests, layout-sensitive
assertions) and leave it unset otherwise for the faster mock
backend.

```bash
pytest                                      # fast, no binary download
python -m plushie download                  # fetch prebuilt binary
PLUSHIE_TEST_BACKEND=headless pytest        # real rendering in CI
```

The renderer must be downloaded into the project with
`python -m plushie download` or configured explicitly with
`PLUSHIE_BINARY_PATH` before the pytest plugin can start the pool.
When the binary is missing, the plugin logs a warning and the
`plushie_pool` fixture skips every test that requests it, so unit
tests that do not touch the pool still run.

## See also

- [App Lifecycle reference](app-lifecycle.md) - the cycle the fixture drives
- [Events reference](events.md) - the event classes delivered to `update`
- [Commands reference](commands.md) - which commands the fixture processes synchronously
- [CLI Commands reference](cli-commands.md) - `python -m plushie script` and `replay`
- [Configuration reference](configuration.md) - environment variables and `pyproject.toml` keys
