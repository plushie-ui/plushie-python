# Testing

## Philosophy

Progressive fidelity: test your app's logic with fast mock tests;
promote to headless or windowed backends when you need wire-protocol
verification or pixel-accurate screenshots.

All testing goes through the real renderer binary. The renderer's
`--mock` mode is the mock. No Python-side simulation of widget
behavior or event synthesis.

## Unit testing

`update()` is pure, `view()` returns dicts. Plain pytest -- no
framework needed.

### Testing `update()`

```python
from dataclasses import replace
from plushie.events import Click

def test_increment():
    app = Counter()
    model = app.init()
    model = app.update(model, Click(id="inc"))
    assert model.count == 1

def test_unknown_event_returns_model():
    app = Counter()
    model = app.init()
    result = app.update(model, "something unknown")
    assert result == model
```

### Testing `view()`

```python
from plushie.tree import normalize, find, text_of

def test_view_shows_count():
    app = Counter()
    model = replace(app.init(), count=42)
    tree = normalize(app.view(model))
    node = find(tree, "count")
    assert node is not None
    assert text_of(node) == "Count: 42"
```

### Testing commands from `update()`

Commands are plain `Command` dataclasses. Inspect `type` and `payload`:

```python
def test_save_triggers_async():
    app = MyApp()
    model, cmd = app.update(model, Click(id="save"))
    assert cmd.type == "async"
    assert cmd.payload["tag"] == "save_result"
```

## The test framework

Unit tests cover logic but cannot click a button or verify a widget
appears after an interaction. That is what `AppFixture` is for.

```python
from plushie.testing import AppFixture

def test_counter(plushie_pool):
    with AppFixture(Counter, plushie_pool) as app:
        app.click("#inc")
        assert app.model.count == 1
        assert app.text("#count") == "Count: 1"
```

`AppFixture` starts a session, processes commands synchronously, and
tears down on exit.

## AppFixture API

| Method | Description |
|---|---|
| `app.click(selector)` | Click a button |
| `app.type_text(selector, text)` | Type text into a text_input |
| `app.submit(selector)` | Submit a text_input (press enter) |
| `app.toggle(selector)` | Toggle a checkbox or toggler |
| `app.select(selector, value)` | Select from pick_list, combo_box, radio |
| `app.slide(selector, value)` | Slide a slider to a value |
| `app.find(selector)` | Find an element (returns Element or raises) |
| `app.text(selector)` | Extract text content from a widget |
| `app.model` | Current model (property) |
| `app.tree` | Current normalized UI tree (property) |

Selectors use `#id` syntax (e.g. `"#save_btn"`).

## Backends

All tests work on all backends. Write tests once, swap backends
without changing assertions.

### Three backends

| | mock | headless | windowed |
|---|---|---|---|
| **Speed** | ~ms | ~100ms | ~seconds |
| **Renderer** | `--mock` | `--headless` | full |
| **Display server** | No | No | Yes (Xvfb) |
| **Protocol round-trip** | Yes | Yes | Yes |
| **Pixel screenshots** | No | Yes (software) | Yes |
| **Real rendering** | No | Yes (tiny-skia) | Yes (GPU) |

- **mock** -- shared `plushie --mock` process with session
  multiplexing. Tests app logic, tree structure, and wire protocol.
  Sub-millisecond. The default for most tests.

- **headless** -- `plushie --headless` with software rendering via
  tiny-skia. Pixel screenshots for visual regression. No display
  server needed.

- **windowed** -- real iced windows and GPU rendering. Effects
  execute, subscriptions fire. Needs a display server (Xvfb in CI).

### Backend selection

Backend is an infrastructure decision, not a test-code decision.

```sh
pytest                                      # mock (default)
PLUSHIE_TEST_BACKEND=headless pytest        # headless
PLUSHIE_TEST_BACKEND=windowed pytest        # windowed
```

## Golden files

### Tree snapshots

Normalize a view tree and compare against a stored JSON file:

```python
from plushie.tree import normalize
import json
from pathlib import Path

def test_initial_view_snapshot():
    app = MyApp()
    tree = normalize(app.view(app.init()))
    golden = Path("tests/snapshots/initial_view.json")
    if not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(json.dumps(tree, indent=2))
    else:
        expected = json.loads(golden.read_text())
        assert tree == expected
```

### Pixel screenshots

Available on headless and windowed backends. Mock mode returns stubs.

## CI configuration

### Mock CI (simplest)

```yaml
- run: pip install plushie
- run: pytest
```

### Headless CI

```yaml
- run: pip install plushie
- run: python -m plushie download
- run: PLUSHIE_TEST_BACKEND=headless pytest
```

### Windowed CI

```yaml
- run: pip install plushie
- run: python -m plushie download
- run: |
    sudo apt-get install -y xvfb mesa-vulkan-drivers
    Xvfb :99 -screen 0 1024x768x24 &
    export DISPLAY=:99
    PLUSHIE_TEST_BACKEND=windowed pytest
```
