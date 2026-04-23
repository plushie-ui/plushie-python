# Testing

## Philosophy

Progressive fidelity: test your app's logic with fast, pure-Python mock tests;
promote to headless or windowed backends when you need wire-protocol verification
or pixel-accurate screenshots.


## Unit testing

`update()` is pure, `view()` returns dicts. Plain pytest, no framework
needed.

### Testing `update()`

<!-- test: test_adding_a_todo_appends_and_clears_input -- keep this code block in sync with the test -->
```python
from plushie.events import Click

def test_adding_a_todo_appends_and_clears_input():
    app = MyApp()
    model = app.init()
    model = dataclasses.replace(model, todos=[], input="Buy milk")
    model = app.update(model, Click(id="add_todo"))

    assert model.todos == [{"text": "Buy milk", "done": False}]
    assert model.input == ""
```

### Testing commands from `update()`

Commands are plain `Command` dataclasses. Inspect `type` and `payload`
to verify what `update()` asked the runtime to do, without executing
anything.

<!-- test: test_submitting_todo_returns_focus_command, test_save_triggers_async_task -- keep this code block in sync with the test -->
```python
from plushie.events import Submit, Click

def test_submitting_todo_returns_focus_command():
    app = MyApp()
    model = dataclasses.replace(app.init(), todos=[], input="Buy milk")
    model, cmd = app.update(model, Submit(id="todo_input", value="Buy milk"))

    assert model.todos == [{"text": "Buy milk"}]
    assert cmd.type == "focus"
    assert cmd.payload["target"] == "todo_input"

def test_save_triggers_async_task():
    app = MyApp()
    model = dataclasses.replace(app.init(), data="unsaved")
    _model, cmd = app.update(model, Click(id="save"))

    assert cmd.type == "task"
    assert cmd.payload["tag"] == "save_result"
```

### Testing `view()`

<!-- test: test_view_shows_todo_count -- keep this code block in sync with the test -->
```python
from plushie.tree import normalize, find, text_of

def test_view_shows_todo_count():
    app = MyApp()
    model = dataclasses.replace(
        app.init(),
        todos=[{"id": 1, "text": "Buy milk", "done": False}],
        input="",
    )
    tree = normalize(app.view(model))

    counter = find(tree, "todo_count")
    assert counter is not None
    assert "1" in text_of(counter)
```

### Testing `init()`

<!-- test: test_init_returns_valid_initial_state -- keep this code block in sync with the test -->
```python
def test_init_returns_valid_initial_state():
    app = MyApp()
    model = app.init()

    assert isinstance(model.todos, list)
    assert model.input == ""
```

### Tree query helpers

`plushie.tree` provides helpers for querying view trees directly:

<!-- test: test_find_by_id, test_exists, test_ids, test_find_all_by_predicate -- keep this code block in sync with the test -->
```python
from plushie.tree import find, ids, find_all, exists

find(tree, "my_button")                         # find node by ID
exists(tree, "my_button")                       # check existence
ids(tree)                                       # all IDs (depth-first)
find_all(tree, lambda node: node["type"] == "button")  # find by predicate
```

These work on the raw node dicts returned by `view()`. No test session or
backend required.

### JSON tree snapshots

For complex views, snapshot the entire tree as JSON to catch unintended
structural changes:

```python
import json
from pathlib import Path
from plushie.tree import normalize

def test_initial_view_snapshot():
    app = MyApp()
    tree = normalize(app.view(app.init()))
    golden = Path("tests/snapshots/initial_view.json")

    if not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(json.dumps(tree, indent=2, sort_keys=True))
    else:
        expected = json.loads(golden.read_text())
        assert tree == expected
```

First run writes the file. Subsequent runs compare and fail with a diff on
mismatch. Update after intentional changes:

```bash
PLUSHIE_UPDATE_SNAPSHOTS=1 pytest
```

This is a pure JSON comparison, distinct from the framework's
`assert_tree_hash()` (which uses SHA-256 hashes of the tree via a backend
session) and `assert_screenshot()` (which compares pixel data).


## The test framework

Unit tests cover logic. But they cannot click a button, verify a widget
appears after an interaction, or catch a rendering regression when you bump
iced. That is what the test framework is for.

```python
from plushie.testing import AppFixture

def test_clicking_increment_updates_counter(plushie_pool):
    with AppFixture(Counter, plushie_pool) as app:
        app.click("#increment")
        app.assert_text("#count", "1")
```

`AppFixture` starts a session, processes commands synchronously, and
tears down on exit. The default backend is `mock`, the plushie binary in
`--mock` mode with lightweight rendering and no display. Sessions are pooled for
performance via the `plushie_pool` pytest fixture.


## Selectors, interactions, and assertions

### Where do widget IDs come from?

Every widget in plushie gets an ID from the first argument to its builder.
For example, `ui.button("save_btn", "Save")` creates a button with ID
`"save_btn"`.

When using selectors in tests, prefix the ID with `#`:

```python
app.click("#save_btn")
app.find("#save_btn")
app.assert_text("#save_btn", "Save")
```

### Selectors

Two selector forms:

- **`"#id"`** - find by widget ID. The `#` prefix is required.
- **`"text content"`** - find by text content (checks `content`, `label`,
  `value`, `placeholder` props in that order, depth-first).

```python
app.click("#my_button")         # by ID
app.find("Click me")           # by text content
app.assert_exists("#sidebar")  # by ID
```

### Element handles

`query()` returns `None` if not found. `find()` raises
`ElementNotFoundError` with a clear message. Both return an `Element`
instance:

```python
element = app.find("#my-button")
element.id        # => "my-button"
element.type      # => "button"
element.props     # => {"label": "Click me", ...}
element.children  # => [...]
```

Use `text()` to extract display text from an element:

```python
assert app.find("#count").text() == "42"
```

`Element.text()` checks props in order: `content`, `label`, `value`,
`placeholder`. Returns `None` if no text prop is found.

### Interaction methods

All interaction methods accept a selector string. They are available on
the `AppFixture` instance.

| Method | Widget types | Event produced |
|---|---|---|
| `click(selector)` | `button` | `Click(id=id)` |
| `type_text(selector, text)` | `text_input`, `text_editor` | `Input(id=id, value=text)` |
| `submit(selector)` | `text_input` | `Submit(id=id, value=val)` |
| `toggle(selector)` | `checkbox`, `toggler` | `Toggle(id=id, value=!current)` |
| `select(selector, value)` | `pick_list`, `combo_box`, `radio` | `Select(id=id, value=val)` |
| `slide(selector, value)` | `slider`, `vertical_slider` | `Slide(id=id, value=val)` |

Interacting with the wrong widget type raises with an actionable hint:

```
TypeError: cannot click a checkbox widget, use toggle() instead
```

### Additional interactions

| Method | Description |
|---|---|
| `press(key)` | Press a key (key down). Supports modifiers: `"ctrl+s"` |
| `release(key)` | Release a key (key up). Supports modifiers: `"ctrl+s"` |
| `type_key(key)` | Type a key (press + release). Supports modifiers: `"enter"` |
| `move_to(x, y)` | Move the cursor to absolute coordinates |
| `scroll(selector, delta_x, delta_y)` | Scroll a widget |
| `paste(selector, text)` | Paste text into a widget |
| `sort(selector, column)` | Sort a table column |
| `canvas_press(selector, x, y, button)` | Press on a canvas |
| `canvas_release(selector, x, y, button)` | Release on a canvas |
| `canvas_move(selector, x, y)` | Move on a canvas |
| `pane_focus_cycle(selector)` | Cycle focus in a pane grid |

### Assertions

```python
# Text content
app.assert_text("#count", "42")

# Existence
app.assert_exists("#my-button")
app.assert_not_exists("#admin-panel")

# Full model equality
app.assert_model(MyModel(count=5, name="test"))

# Direct model inspection
assert app.model.count == 5

# Direct element access when you need more control
element = app.find("#count")
assert element.text() == "42"
assert element.type == "text"
```


## API reference

All of the following are available on an `AppFixture` instance:

| Method / Property | Description |
|---|---|
| `find(selector)` | Find element by selector, raises `ElementNotFoundError` if not found |
| `query(selector)` | Find element by selector, returns `None` if not found |
| `click(selector)` | Click a button widget |
| `type_text(selector, text)` | Type text into a text_input or text_editor |
| `submit(selector)` | Submit a text_input (simulates pressing enter) |
| `toggle(selector)` | Toggle a checkbox or toggler |
| `select(selector, value)` | Select a value from pick_list, combo_box, or radio |
| `slide(selector, value)` | Slide a slider to a numeric value |
| `press(key)` | Press a key (key down). Supports modifiers: `"ctrl+s"` |
| `release(key)` | Release a key (key up). Supports modifiers |
| `type_key(key)` | Type a key (press + release). Supports modifiers |
| `move_to(x, y)` | Move the cursor to absolute coordinates |
| `scroll(selector, delta_x, delta_y)` | Scroll a widget |
| `paste(selector, text)` | Paste text into a widget |
| `sort(selector, column)` | Sort a table column |
| `canvas_press(selector, x, y, button)` | Press on a canvas |
| `canvas_release(selector, x, y, button)` | Release on a canvas |
| `canvas_move(selector, x, y)` | Move on a canvas |
| `pane_focus_cycle(selector)` | Cycle focus in a pane grid |
| `model` | Returns the current app model (property) |
| `tree` | Returns the current normalized UI tree (property) |
| `text(selector)` | Extract text content from a widget |
| `exists(selector)` | Check whether an element exists in the tree |
| `find_by_role(role)` | Find an element by its accessible role |
| `find_by_label(label)` | Find an element by its accessible label |
| `find_focused()` | Find the currently focused element |
| `assert_text(selector, expected)` | Assert widget contains expected text |
| `assert_exists(selector)` | Assert widget exists in the tree |
| `assert_not_exists(selector)` | Assert widget does NOT exist in the tree |
| `assert_model(expected)` | Assert model equals expected (strict equality) |
| `assert_tree_hash(name)` | Capture tree hash and assert it matches golden file |
| `assert_screenshot(name)` | Capture screenshot and assert it matches golden file |
| `save_screenshot(name)` | Capture screenshot and save as PNG to `test/screenshots/` |
| `await_async()` | No-op in synchronous test mode (work already done) |
| `reset()` | Reset session to initial state |
| `close()` | Release the session back to the pool |


## Backends

All tests work on all backends. Write tests once, swap backends without
changing assertions.

### Backend modes

| | `mock` | `headless` | `windowed` |
|---|---|---|---|
| **Speed** | ~ms | ~100ms | ~seconds |
| **Renderer** | Yes (`--mock`) | Yes (`--headless`) | Yes |
| **Display server** | No | No | Yes (Xvfb in CI) |
| **Protocol round-trip** | Yes | Yes | Yes |
| **Structural tree hashes** | Yes | Yes | Yes |
| **Pixel screenshots** | No | Yes (software) | Yes |
| **Effects** | Cancelled | Cancelled | Executed |
| **Subscriptions** | Tracked, not fired | Tracked, not fired | Active |
| **Real rendering** | No | Yes (tiny-skia) | Yes (GPU) |
| **Real windows** | No | No | Yes |

- **`mock`** - shared `plushie --mock` process with session
  multiplexing. Tests app logic, tree structure, and wire protocol.
  No rendering, no display, sub-millisecond. The right default for
  90% of tests.

- **`headless`** - `plushie --headless` with software rendering via
  tiny-skia (no display server). Pixel screenshots for visual
  regression. Catches rendering bugs that mock mode cannot.

- **`windowed`** - `plushie` with real iced windows and GPU rendering.
  Effects execute, subscriptions fire, screenshots capture exactly
  what a user sees. Needs a display server (Xvfb or headless Weston).

### Backend selection

You never choose a backend in your test code. Backend selection is an
infrastructure decision made via environment variable.

| Priority | Source | Example |
|---|---|---|
| 1 | Environment variable | `PLUSHIE_TEST_BACKEND=headless pytest` |
| 2 | Default | `mock` |

The `plushie_pool` pytest fixture (provided by `plushie.testing.plugin`)
reads `PLUSHIE_TEST_BACKEND` at session startup and configures the
`SessionPool` accordingly.


## Snapshots and screenshots

Plushie has three distinct regression testing mechanisms. Understanding the
difference is important.

### Structural tree hashes (`assert_tree_hash`)

`assert_tree_hash()` captures a SHA-256 hash of the serialized UI tree and
compares it against a golden file. It works on all backend modes because
every mode can produce a tree.

```python
def test_counter_initial_state(plushie_pool):
    with AppFixture(Counter, plushie_pool) as app:
        app.assert_tree_hash("counter-initial")

def test_counter_after_increment(plushie_pool):
    with AppFixture(Counter, plushie_pool) as app:
        app.click("#increment")
        app.assert_tree_hash("counter-at-1")
```

Golden files are stored in `test/snapshots/` as `.tree_hash` files. On first
run, the golden file is created automatically. On subsequent runs, the hash
is compared and the test fails on mismatch.

To update golden files after intentional changes:

```bash
PLUSHIE_UPDATE_SNAPSHOTS=1 pytest
```

### Pixel screenshots (`assert_screenshot`)

`assert_screenshot()` captures real RGBA pixel data and compares it against
a golden file. It produces meaningful data on the `headless` backend
(software rendering via tiny-skia) and the `windowed` backend (GPU rendering
via wgpu). On `mock`, it silently succeeds as a no-op (returns an empty
hash, which is accepted without creating or checking a golden file).

Note that headless screenshots use software rendering, so pixels will not
match GPU output exactly. Maintain separate golden files per backend, or
use headless screenshots for layout regression testing only.

```python
def test_counter_renders_correctly(plushie_pool):
    with AppFixture(Counter, plushie_pool) as app:
        app.click("#increment")
        app.assert_screenshot("counter-at-1")
```

Golden files are stored in `test/screenshots/` as `.screenshot_hash` files.
The workflow is the same as structural snapshots but uses a separate env var:

```bash
PLUSHIE_UPDATE_SCREENSHOTS=1 pytest
```

Because screenshots silently no-op on mock, you can include
`assert_screenshot` calls in any test without conditional logic. They will
produce assertions when run on the headless or windowed backends.

### Saving screenshots to disk

`save_screenshot()` writes the actual PNG pixel data to
`test/screenshots/<name>.png`. Useful for debugging visual issues.

```python
def test_save_counter_screenshot(plushie_pool):
    with AppFixture(Counter, plushie_pool) as app:
        app.click("#increment")
        path = app.save_screenshot("counter-debug")
        assert path.exists()
```

### JSON tree snapshots

Pure JSON comparison at the unit test level, no backend or session needed.
See the [Unit testing](#json-tree-snapshots) section above.

### When to use each

- **`assert_tree_hash`** - always appropriate. Catches structural regressions
  (widgets appearing/disappearing, prop changes, nesting changes). Works on
  every backend. Use liberally.

- **`assert_screenshot`** - after bumping iced, changing the renderer,
  modifying themes, or any change that affects visual output. Produces
  meaningful assertions on the headless and windowed backends (no-op on
  mock). Include alongside `assert_tree_hash` for critical views.

- **JSON tree snapshots** - for unit tests of `view()` output. No framework
  overhead. Good for documenting what a view produces for a given model state.


## Script-based testing

`.plushie` scripts provide a declarative format for describing interaction
sequences. The format is a superset of iced's `.ice` test scripts. The
core instructions (`click`, `type`, `expect`, `snapshot`) use the same
syntax. Plushie adds `assert_text`, `assert_model`, `screenshot`, `wait`, and
a header section for app configuration.

### The `.plushie` format

A `.plushie` file has a header and an instruction section separated by
`-----`:

```
app: my_app:MyApp.Counter
viewport: 800x600
theme: dark
backend: mock
-----
click "#increment"
click "#increment"
expect "Count: 2"
tree_hash "counter-at-2"
screenshot "counter-pixels"
assert_text "#count" "2"
wait 500
```

#### Header fields

| Field | Required | Default | Description |
|---|---|---|---|
| `app` | Yes | -- | Module path implementing `plushie.App` |
| `viewport` | No | `800x600` | Viewport size as `WxH` |
| `theme` | No | `dark` | Theme name |
| `backend` | No | `mock` | Backend: `mock`, `headless`, or `windowed` |

Lines starting with `#` are comments (in both header and body sections).

#### Instructions

| Instruction | Syntax | Mock support | Description |
|---|---|---|---|
| `click` | `click "selector"` | Yes | Click a widget |
| `type` | `type "selector" "text"` | Yes | Type text into a widget |
| `type` (key) | `type enter` | Yes | Send a special key (press + release). Supports modifiers: `type ctrl+s` |
| `expect` | `expect "text"` | Yes | Assert text appears somewhere in the tree |
| `tree_hash` | `tree_hash "name"` | Yes | Capture and assert a structural tree hash |
| `screenshot` | `screenshot "name"` | No-op on mock | Capture and assert a pixel screenshot |
| `assert_text` | `assert_text "selector" "text"` | Yes | Assert widget has specific text |
| `assert_model` | `assert_model "expression"` | Yes | Assert expression appears in inspected model (substring match) |
| `press` | `press key` | Yes | Press a key down. Supports modifiers: `press ctrl+s` |
| `release` | `release key` | Yes | Release a key. Supports modifiers: `release ctrl+s` |
| `move` | `move "selector"` | No-op | Move mouse to a widget (requires widget bounds) |
| `move` (coords) | `move "x,y"` | Yes | Move mouse to pixel coordinates |
| `wait` | `wait 500` | Ignored (except replay) | Pause N milliseconds |

### Running scripts

```bash
python -m plushie script

# Run specific scripts
python -m plushie script tests/scripts/counter.plushie tests/scripts/todo.plushie
```

### Replaying scripts

```bash
python -m plushie replay tests/scripts/counter.plushie
```

Replay mode forces the `windowed` backend and respects `wait` timings, so you
see interactions happen in real time with real windows. Useful for debugging
visual issues, demos, and onboarding.


## Wire format in test backends

The headless and windowed backends communicate with the renderer using the same
wire protocol as the production connection. By default, both use MessagePack
(4-byte length-prefix framing). JSON is available for debugging:

```python
# Pass format when creating a connection manually
from plushie.connection import Connection

conn = Connection(MyApp, format="json")
```

The mock backend does not use a wire protocol (pure Python, no renderer
process), so the format option has no effect on it.


## Testing async workflows

### On the mock backend

The mock backend executes `task`, `stream`, and `done` commands
synchronously. When `update()` returns a command like
`Command.task(fn, tag="data_loaded")`, the fixture immediately calls the
function, gets the result, and dispatches the result through `update()` --
all within the same call.

This means `await_async()` is a no-op (the work is already done):

```python
def test_fetching_data_loads_results(plushie_pool):
    with AppFixture(MyApp, plushie_pool) as app:
        app.click("#fetch")
        # On mock, the task command already executed synchronously.
        # await_async() is a no-op; the model is already updated.
        app.await_async()
        assert len(app.model.results) > 0
```

Widget ops (focus, scroll), window ops, and timers are silently skipped on
mock because they require a renderer. Test the command shape at the
unit test level instead:

<!-- test: test_clicking_fetch_starts_async_load -- keep this code block in sync with the test -->
```python
def test_clicking_fetch_starts_async_load():
    app = MyApp()
    model = dataclasses.replace(app.init(), loading=False, data=None)
    model, cmd = app.update(model, Click(id="fetch"))

    assert model.loading is True
    assert cmd.type == "task"
    assert cmd.payload["tag"] == "data_loaded"
```

### On headless and windowed backends

All backend modes execute async commands synchronously. `await_async()`
returns immediately on all modes because the commands have already
completed.


## Debugging and error messages

### Element not found

```python
app.find("#nonexistent")
# ElementNotFoundError: element not found: '#nonexistent'. Available IDs: ['inc', 'dec', 'count']
```

Use `app.tree` to inspect the current tree and verify the widget's ID or
text content:

```python
import pprint
pprint.pprint(app.tree)
```

### Wrong interaction type

```python
app.click("#my-checkbox")
# TypeError: cannot click a checkbox widget, use toggle() instead
```

Use the correct interaction method for the widget type. See the
[interaction table](#interaction-methods) for the mapping.

### Headless binary not built

```
PlushieNotFoundError: failed to start renderer: ...
```

Download or build the renderer:

```bash
python -m plushie download
```

### Inspecting state when a test fails

`model` and `tree` are your best debugging tools:

```python
def test_debugging_a_failing_test(plushie_pool):
    with AppFixture(Counter, plushie_pool) as app:
        app.click("#increment")

        print("model:", app.model)
        print("tree:", app.tree)

        assert app.find("#count").text() == "1"
```


## CI configuration

### Mock CI (simplest)

No special setup. Works anywhere Python runs.

```yaml
- run: pip install plushie
- run: pytest
```

### Headless CI

Requires the plushie binary (download or build from source).

```yaml
- run: pip install plushie
- run: python -m plushie download
- run: PLUSHIE_TEST_BACKEND=headless pytest
```

### Windowed CI

Requires a display server and GPU/software rendering. Two options:

**Option A: Xvfb (X11)**

```yaml
- run: pip install plushie
- run: python -m plushie download
- run: sudo apt-get install -y xvfb mesa-vulkan-drivers
- run: |
    Xvfb :99 -screen 0 1024x768x24 &
    export DISPLAY=:99
    export WINIT_UNIX_BACKEND=x11
    PLUSHIE_TEST_BACKEND=windowed pytest
```

**Option B: Weston (Wayland)**

Weston's headless backend provides a Wayland compositor without a physical
display. Combined with `vulkan-swrast` (Mesa software rasterizer), this
runs the full rendering pipeline on CPU.

```yaml
- run: pip install plushie
- run: python -m plushie download
- run: sudo apt-get install -y weston mesa-vulkan-drivers
- run: |
    export XDG_RUNTIME_DIR=/tmp/plushie-xdg-runtime
    mkdir -p "$XDG_RUNTIME_DIR" && chmod 0700 "$XDG_RUNTIME_DIR"
    weston --backend=headless --width=1024 --height=768 --socket=plushie-test &
    sleep 1
    export WAYLAND_DISPLAY=plushie-test
    PLUSHIE_TEST_BACKEND=windowed pytest
```

On Arch Linux, `weston` and `vulkan-swrast` are available via pacman.

### Progressive CI

Run mock tests fast, then promote to higher-fidelity backends for subsets:

```yaml
# All tests on mock (fast, catches logic bugs)
- run: pytest

# Full suite on headless for protocol verification
- run: PLUSHIE_TEST_BACKEND=headless pytest

# Windowed for pixel regression (tagged subset)
- run: |
    Xvfb :99 -screen 0 1024x768x24 &
    export DISPLAY=:99
    PLUSHIE_TEST_BACKEND=windowed pytest -m windowed
```

Tag tests that need a specific backend with pytest markers:

```python
import pytest

@pytest.mark.headless
def test_protocol_round_trip(plushie_pool):
    ...

@pytest.mark.windowed
def test_window_opens_and_renders(plushie_pool):
    ...
```


## Testing extensions

Extension widgets have two testing layers: Python-side logic (node building,
command generation, demo app behavior) and Rust-side rendering (the widget
actually renders, handles events, etc.).

### Python-side: unit tests (no renderer)

Native widget definitions produce nodes and commands via `build_node()`
and `build_command()`. Test these directly:

```python
from plushie.native_widget import build_node, build_command

def test_build_node_creates_correct_type():
    node = build_node(gauge_def, "g1", {"value": 50})
    assert node["type"] == "gauge"
    assert node["props"]["value"] == 50

def test_build_command_creates_extension_command():
    cmd = build_command(gauge_def, "g1", "set_value", {"value": 42.0})
    assert cmd.type == "extension_command"
```

Demo apps test the extension in context:

```python
def test_view_produces_a_gauge_widget():
    app = GaugeDemo()
    model = app.init()
    tree = normalize(app.view(model))
    gauge = find(tree, "my-gauge")
    assert gauge["type"] == "gauge"
```

### Rust-side: unit tests (no Python)

The `plushie_widget_sdk::testing` module provides `TestEnv` and node factories
for testing `WidgetExtension::render()` in isolation:

```rust
use plushie_widget_sdk::testing::*;
use plushie_widget_sdk::prelude::*;

#[test]
fn gauge_renders_without_panic() {
    let ext = MyGaugeExtension::new();
    let test = TestEnv::default();
    let node = node_with_props("g1", "gauge", json!({"value": 75}));
    let env = test.env();
    let _element = ext.render(&node, &env);
}
```

### End-to-end: through the renderer

To verify extension widgets survive the wire protocol round-trip and
render correctly, build a custom renderer binary that includes the
extension's Rust crate:

```bash
# Build the custom renderer with your extension compiled in
python -m plushie build

# Run tests through the real renderer (headless, no display server)
PLUSHIE_TEST_BACKEND=headless pytest
```

Write end-to-end tests with `AppFixture`:

```python
def test_gauge_appears_in_rendered_tree(plushie_pool):
    with AppFixture(GaugeDemo, plushie_pool) as app:
        app.assert_exists("#my-gauge")

def test_gauge_responds_to_command(plushie_pool):
    with AppFixture(GaugeDemo, plushie_pool) as app:
        app.click("#push-value")
        app.assert_text("#value-display", "42")
```

These tests run on `mock` by default (fast, logic-only). Set
`PLUSHIE_TEST_BACKEND=headless` to exercise the full Rust rendering path
with the extension compiled in.


## Key name validation

`press()`, `type_key()`, and `release()` validate key names at call
time. Input is case-insensitive. Named keys use PascalCase matching
the renderer's wire format (same strings that appear in event data):

```python
press("Tab")
press("ArrowRight")
press("Shift+PageUp")
press("a")
```

Unrecognized key names raise immediately:

```
ValueError: unknown key "tabb". Examples: Tab, ArrowRight, PageUp, Escape, Enter.
```

Single characters are also accepted and lowercased (`"a"`, `"Z"`,
`"1"`). Modifier combos use `+`: `"Ctrl+s"`, `"Shift+ArrowUp"`.
Modifiers: `shift`, `ctrl`, `alt`, `logo`, `command`.


## Known limitations

- Script instruction `move` (move cursor to a widget by selector) is a
  no-op. It requires widget bounds from layout, which only the renderer knows.
- `move_to` on the mock backend dispatches cursor events but has no spatial
  layout info. Mouse area enter/exit events will not fire.
- Pixel screenshots are only available on the headless and windowed backends
  (mock returns stubs).
- Headless screenshots use software rendering (tiny-skia) and may not match
  GPU output pixel-for-pixel.
- Script `assert_model` uses substring matching against the inspected model.
  Use specific substrings or use pytest assertions for precise model checks.
- The `CommandProcessor` executes task/stream/batch commands synchronously
  in all test backends. Timing and concurrency bugs will not surface in mock
  tests. Use headless or windowed backends for concurrency-sensitive tests.
- There is a safety limit of 100 levels of recursive command processing to
  prevent infinite command loops.
