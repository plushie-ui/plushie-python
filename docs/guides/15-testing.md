# Testing

The pad is a fair pile of behaviour at this point: a sidebar, an editor, a save button, a keyboard shortcut, a compile pipeline, autosave. Each of those has an obvious way to break, and the interesting breaks live at the seam between the Python SDK and the renderer. Tests that mock the renderer miss those. Tests that drive the real renderer catch them.

Plushie leans hard on the second approach. The renderer binary ships a `--mock` mode that runs the full wire protocol without any GPU work, and the SDK ships a pytest fixture that talks to it. Every test in this chapter sends real messages, receives real events, and asserts against the real model.

The full helper catalog lives in the [Testing reference](../reference/testing.md). This chapter walks through writing tests for the pad.

## No widget mocks

There is no Python-side simulation of widget behaviour. No fake tree builders, no stubbed events, no hand-rolled DOM. `AppFixture` sends an `interact` message to the renderer, the renderer decides what events the widget produces, the fixture feeds those events through `app.update`, diffs the new view, and sends a patch back. The whole cycle runs per interaction.

That means a test can fail because the renderer changed how `text_input` emits submit events, because the wire format shifted a field name, or because a widget prop started rejecting a value it used to accept. Those are exactly the failures worth catching.

The tradeoff is a running binary. `python -m plushie download` fetches a prebuilt renderer; once it is on the path, tests run without further ceremony.

## The pytest plugin

`plushie.testing.plugin` is registered as a `pytest11` entry point. Installing `plushie` is enough for pytest to pick it up; no conftest wiring required for the common case. The plugin starts one `SessionPool` at `pytest_configure` and stops it at `pytest_unconfigure`. The pool owns a single `plushie --mock --max-sessions N` subprocess and hands out session IDs to tests.

The `plushie_pool` fixture is session-scoped and yields the running pool. If the plugin cannot start the pool (for example, the renderer binary is missing), the fixture calls `pytest.skip`, so unit tests that never ask for the pool keep running.

When the entry point is not auto-discovered (src layouts without an installed package are the usual culprit), enable it explicitly:

```toml
[tool.pytest.ini_options]
addopts = "-p plushie.testing.plugin"
```

Pool size is controlled by `PLUSHIE_TEST_MAX_SESSIONS` (default eight). For heavy parallelism (`pytest -n 16`) crank it up.

## The fixture pattern

`AppFixture` is a context manager that allocates a session from the pool, runs `app.init`, sends the initial snapshot, and exposes the helper API. On exit it resets the session and releases it back to the pool. Each test gets a clean slate.

```python
import pytest

from plushie.testing import AppFixture

from plushie_pad.app import Pad


@pytest.fixture
def app(plushie_pool):
    with AppFixture(Pad, plushie_pool) as fixture:
        yield fixture
```

The fixture is per-test. The pool is per-session. One renderer subprocess serves every test in the suite.

## Writing a test

Three interactions cover most of the pad. Type into the editor, click save, assert the model cleared its dirty flag:

```python
def test_save_clears_dirty(app):
    app.type_text("pad#editor", "\n# added\n")
    assert app.model.dirty is True
    app.click("pad#save")
    assert app.model.dirty is False
```

`type_text` sends a `type_text` interact. The renderer emits an `Input` event. The fixture routes it through `Pad.update`, which sets `dirty=True`. `click` sends a `click` interact; the renderer emits a `Click`; update runs `_save` which clears `dirty`.

The common interaction helpers mirror the widget vocabulary:

| Helper | Widget |
|---|---|
| `click(selector)` | `button` |
| `type_text(selector, text)` | `text_input`, `text_editor` |
| `submit(selector)` | `text_input` |
| `toggle(selector)` | `checkbox`, `toggler` |
| `select(selector, value)` | `pick_list`, `combo_box`, `radio` |
| `slide(selector, value)` | `slider` |

`click`, `type_text`, `submit`, and `toggle` validate the widget type against the local tree and raise `TypeError` with a suggestion if it does not match. Calling `click` on a checkbox, for instance, raises with a note to use `toggle`.

Assertions run against the live model and the renderer's view of the tree:

```python
def test_default_experiment_loads(app):
    app.assert_exists("pad#editor")
    assert app.model.selected == "hello"
    assert "Hello, Plushie!" in app.model.editor_source
```

`app.model` is the current model object (a frozen dataclass for the pad). `app.text(selector)` extracts display text from a node. `app.assert_exists(selector)` raises with the available IDs listed if the selector is wrong, which makes typos obvious.

The pad's event log is another angle: every save pushes an entry onto `model.event_log`, so a save test can assert both the dirty flag and the log grew by one entry:

```python
def test_save_appends_to_event_log(app):
    before = len(app.model.event_log)
    app.click("pad#save")
    after = app.model.event_log
    assert len(after) == before + 1
    assert after[0].kind == "saved"
```

`app.model` returns the same object type the app does. Frozen dataclasses with slots compare by value, which is exactly what you want here.

## Selectors

Selectors look like the IDs you already assigned in `view`.

| Form | Matches |
|---|---|
| `"#id"` | Local widget ID, any window |
| `"#scope/path/id"` | Exact scoped path |
| `"window_id#id"` | Widget in a specific window |
| `"window_id#scope/path/id"` | Scoped path in a specific window |

The pad wraps everything in `ui.window("pad", ...)`, so every widget lives under the `pad` scope. `"pad#editor"` and `"pad#save"` are the common forms. An unscoped `"#save"` works too when it is unambiguous, but the window-qualified form is clearer in a multi-window app. An unscoped ID that exists in more than one window raises `ValueError`, so the ambiguity surfaces as soon as a second window lands in the tree.

Partial scoped paths work: `"#sidebar/select-hello"` matches any node whose scoped ID ends with that suffix.

## The three backends

Every test in this chapter runs against the mock backend, but the same test code runs against two others too. Backend selection is an environment variable:

```bash
pytest                                        # mock (default)
PLUSHIE_TEST_BACKEND=headless pytest          # real rendering, no display
PLUSHIE_TEST_BACKEND=windowed pytest          # real windows
```

| Backend | Speed | Rendering | Display | Use case |
|---|---|---|---|---|
| `mock` | fastest | protocol only | none | default in CI and local dev |
| `headless` | slower | software (tiny-skia) | none | screenshot tests in CI |
| `windowed` | slowest | GPU (iced) | required | manual verification |

Mock is the default because it is the fastest thing that still exercises the real wire protocol. Headless adds pixel-accurate software rendering with no display requirement, which is what you want for pixel regression tests. Windowed opens real windows on a real compositor, which is what you want when you are debugging a visual glitch by hand.

The test source is identical across all three. The only thing that changes is what the renderer does with the messages. Interactions that depend on layout (`interact_step` round trips for scroll-into-view, hit testing at precise coordinates) go silently through the fixture, which handles them transparently with an `on_step` callback that re-renders and replies.

## Screenshot diffs

On headless and windowed backends, `app.assert_screenshot("name")` captures a PNG, hashes it, and compares against a golden file under `test/screenshots/<name>.screenshot_hash`. First run creates the baseline. Subsequent runs compare.

```python
def test_pad_initial_screenshot(app):
    app.assert_screenshot("pad-initial")
```

To regenerate baselines after an intentional UI change:

```bash
PLUSHIE_UPDATE_SCREENSHOTS=1 PLUSHIE_TEST_BACKEND=headless pytest
```

`app.save_screenshot("pad-initial")` writes the full PNG under `test/screenshots/` for eyeballing in an image viewer. It raises on the mock backend since there are no pixels to save.

For structural regression without going pixel-accurate, `app.assert_tree_hash("name")` hashes the normalized tree. Tree hashes work on every backend, and the golden files live alongside screenshots under `test/snapshots/`. The update variable is separate (`PLUSHIE_UPDATE_SNAPSHOTS=1`) so a structural change does not silently overwrite screenshot baselines.

## Effect stubs

When a test triggers a command that opens a file dialog, writes to the clipboard, or shows a native notification, you do not want real OS dialogs popping up in CI. The renderer ships an effect-stub mechanism: register a canned response for an effect kind, and the renderer replies with that value instead of dispatching the real platform call.

Stubs register by kind (the operation type string, `file_open`, `clipboard_write`, and so on), not by tag. The stub applies to every effect of that kind regardless of the tag used to trigger it. Stubs are scoped to the test session and get cleared when the fixture closes.

```python
def test_import_loads_experiment(app, tmp_path):
    path = tmp_path / "hello.py"
    path.write_text(VALID_SOURCE)
    app._pool.send(
        app._session_id,
        {
            "type": "register_effect_stub",
            "kind": "file_open",
            "response": {"path": str(path)},
        },
    )
    app.click("pad#import")
    assert path.name in app.model.editor_source
```

The pad does not currently wire up import, so this snippet is aspirational. The point stands: the pattern is "stub the platform response, fire the command, assert the resulting model". No real dialog, no user action, no waiting.

## The pad's save shortcut

Pad's `update` handles a keyboard shortcut: `Cmd+S` (or `Ctrl+S` on platforms where `modifiers.command` maps to `ctrl`) calls `_save`. Tests exercise that through `press` and friends, which take a `"<modifier>+<modifier>+<key>"` string:

```python
def test_save_shortcut_clears_dirty(app):
    app.type_text("pad#editor", "\n# added\n")
    assert app.model.dirty is True
    app.press("command+s")
    assert app.model.dirty is False
```

Modifiers are `ctrl`, `shift`, `alt`, `logo`, `command`. Single characters lowercase, multi-character names resolve case-insensitively against `plushie.keys`: `app.type_key("Enter")`, `app.type_key("ArrowRight")`. Unknown names raise `ValueError`.

`type_key` presses and releases in one call. `press` and `release` are separate calls when you need to test held modifiers or ordering.

## Autosave and the renderer clock

Autosave fires on a `Subscription.every(1500, "autosave")`. Tests should not wait 1.5 seconds of wall clock for a timer to fire; instead, the fixture exposes a virtual clock through `advance_frame(timestamp_ms)`. Advancing the clock past the timer's due time makes the timer fire immediately:

```python
def test_autosave_saves_dirty_buffer(app):
    app.click("pad#autosave")
    app.type_text("pad#editor", "\n# dirty edit\n")
    assert app.model.dirty is True
    app.advance_frame(2000)
    assert app.model.dirty is False
```

`advance_frame` also drives transitions and springs forward to the given timestamp. `skip_transitions` is a convenience that jumps ten seconds ahead, which completes any plausible in-flight animation in one call.

## Reset between tests

`AppFixture` allocates a fresh session per test and releases it on exit. Inside a single test, `app.reset()` reruns `init`, processes the initial commands, and sends a fresh snapshot. That is useful for tests that want to verify several independent starting states without paying the cost of spinning up a new session each time:

```python
def test_multiple_starts(app):
    assert app.model.selected == "hello"
    app.click("pad#save")
    app.reset()
    assert app.model.selected == "hello"
    assert app.model.dirty is False
```

`await_async()` exists on the fixture for parity with Elixir, but it is a no-op: `AppFixture` processes commands synchronously inside the fixture thread. Tasks, streams, batches, and dispatch commands run inline through `app.update`. Widget and window ops, timers, and pending effects still need a live runtime and are skipped silently; the virtual clock (`advance_frame`) drives what is otherwise driven by wall time.

## Running tests in CI

For most projects the answer is two lines in the CI config:

```bash
python -m plushie download
pytest
```

The first line drops the prebuilt renderer into the Python package's cache directory. The second runs the suite against the mock backend, which is the speed sweet spot.

For pixel regressions, run a second pass less often (a weekly scheduled job, or a nightly build) against headless:

```bash
PLUSHIE_TEST_BACKEND=headless pytest -k screenshot
```

Headless is slow enough that running every screenshot assertion on every PR is probably not the trade you want. Running them weekly catches drift without choking the main CI pipeline.

Pin the renderer version in CI so baselines stay stable. A renderer upgrade will usually shift a few pixels for reasons unrelated to your app; treat that as a separate PR that also updates screenshot baselines.

## Diagnostics and logging

The renderer emits validation diagnostics for unknown props, bad enum values, and structural problems. The fixture collects them as it runs.

```python
def test_no_prop_warnings(app):
    app.assert_no_diagnostics()
```

`assert_no_diagnostics` fails with the full list of diagnostics if any accumulated, so the message tells you exactly what the renderer complained about. `app.get_diagnostics()` returns the buffered list when you want to assert on specific entries.

Log output goes through the standard `plushie.testing` logger. Pytest's `caplog` fixture captures it:

```python
import logging


def test_save_logs(app, caplog):
    with caplog.at_level(logging.INFO, logger="plushie.testing"):
        app.click("pad#save")
```

## Try it

- Add a test that clicks a sidebar entry and asserts `app.model.selected` changed.
- Add a test that turns on autosave (`app.click("pad#autosave")`), advances frames until the timer fires, and asserts a save happened.
- Run the suite with `PLUSHIE_TEST_BACKEND=headless` and add an `assert_screenshot("pad-default")` check. Commit the baseline.
- Break the editor prop name in `view` and watch the failure message list the real IDs.

The pad already ships tests covering the default experiment load, the dirty flag on edit, and the dirty flag clearing on save. Layer in the shortcut test above and the assertion on `model.event_log` and you have a safety net that catches every bug this chapter would have let through.

## Automation scripts

For smoke tests that read more like a transcript than a unit test, the `.plushie` scripting format is a declarative alternative. A script names the app in its header, then lists interactions and expectations line by line:

```
app: plushie_pad.app:Pad
viewport: 1100x700
backend: mock
-----
click "pad#save"
expect exists "pad#editor"
```

Run scripts with `python -m plushie script tests/scripts/*.plushie` (mock backend) or `python -m plushie replay tests/scripts/saved.plushie` (real windows). The [CLI Commands reference](../reference/cli-commands.md) covers the full instruction set.

Scripts and pytest are not in competition. Pytest covers the "assert the model" side of testing; scripts cover the "record a scenario and replay it visually" side. Most projects use both.

Next: [Shared State](16-shared-state.md)
