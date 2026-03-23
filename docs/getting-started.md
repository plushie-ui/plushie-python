# Getting started

Build native desktop GUIs from Python. Plushie handles rendering via
iced (Rust) while you own state, logic, and UI trees in pure Python.

## Prerequisites

- **Python** 3.12+
- **pip** (or any PEP 517-compatible installer)

The plushie renderer binary is downloaded automatically. No Rust
toolchain needed unless you are building custom native extensions.

## Setup

### 1. Install the package

```sh
pip install plushie
```

Or from source:

```sh
git clone https://github.com/plushie-ui/plushie-python.git
cd plushie-python
pip install -e ".[dev]"
```

### 2. Download the renderer binary

```sh
python -m plushie download
```

This fetches a precompiled binary for your platform and places it in
`~/.local/share/plushie/bin/` (Linux/macOS) or
`%LOCALAPPDATA%\plushie\bin\` (Windows).

## Your first app: a counter

Create `counter.py`:

<!-- test: test_getting_started_counter_init, test_getting_started_counter_increment, test_getting_started_counter_decrement, test_getting_started_counter_unknown_event, test_getting_started_counter_view, test_getting_started_counter_view_after_increments -- keep this code block in sync with tests/docs/test_getting_started.py -->

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0


class Counter(plushie.App[Model]):
    def init(self):
        return Model()

    def update(self, model, event):
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case Click(id="dec"):
                return replace(model, count=model.count - 1)
            case _:
                return model

    def view(self, model):
        return ui.window(
            "main",
            ui.column(
                ui.text("count", f"Count: {model.count}", size=20),
                ui.row(
                    ui.button("inc", "+"),
                    ui.button("dec", "-"),
                    spacing=8,
                ),
                padding=16,
                spacing=8,
            ),
            title="Counter",
        )


if __name__ == "__main__":
    plushie.run(Counter)
```

Run it:

```sh
python counter.py
```

Or via the CLI:

```sh
python -m plushie run counter:Counter
```

A native window appears with the count and two buttons.

## The Elm architecture

Plushie follows the Elm architecture. Your app class implements
callbacks on a `plushie.App` subclass:

- **`init()`** -- returns the initial model (any Python object;
  frozen dataclasses recommended).
- **`update(model, event)`** -- takes the current model and an event,
  returns the new model. Pure function. To run side effects, return
  `(model, command)` instead. See [Commands](commands.md).
- **`view(model)`** -- takes the model and returns a UI tree as a
  plain dict. Plushie diffs trees and sends only patches to the
  renderer.
- **`subscribe(model)`** (optional) -- returns a list of active
  subscriptions (timers, keyboard events).

See [App](app.md) for the full callback API.

## Event types

Events are frozen dataclasses under `plushie.events`. Pattern match
in `update()` using Python's `match` statement:

| Event | Meaning |
|---|---|
| `Click(id=id)` | Button click |
| `Input(id=id, value=val)` | Text input change |
| `Submit(id=id, value=val)` | Text input Enter |
| `Toggle(id=id, value=val)` | Checkbox/toggler |
| `Slide(id=id, value=val)` | Slider moved |
| `Select(id=id, value=val)` | Pick list/radio |
| `TimerTick(tag=tag)` | Timer fired |

See [Events](events.md) for the full taxonomy.

## CLI commands

```bash
python -m plushie run myapp:Counter        # run an app
python -m plushie run myapp:Counter --json # JSON wire format (debug)
python -m plushie run myapp:Counter --watch # live reload on file change
python -m plushie connect myapp:App        # connect mode (stdio transport)
python -m plushie download                 # download precompiled binary
python -m plushie download --wasm          # download WASM renderer
python -m plushie build                    # build renderer with extensions
python -m plushie inspect myapp:App        # print UI tree as JSON
python -m plushie script tests/*.plushie   # run test scripts
python -m plushie replay test.plushie      # replay script with real windows
```

## Debugging

Use JSON wire format to see messages between Python and the renderer:

```sh
python -m plushie run myapp:Counter --json
```

Enable verbose renderer logging:

```sh
RUST_LOG=plushie=debug python -m plushie run myapp:Counter
```

## Error handling

If `update()` or `view()` raises, the runtime catches the exception,
logs it, and continues with the previous state. The GUI does not
crash. Fix the code and the next event works normally.

After 100 consecutive errors, log output is suppressed to prevent
flooding. A periodic reminder is logged every 1000 errors.

## Dev mode

Live code reloading without losing application state:

```sh
python -m plushie run myapp:Counter --watch
```

In watch mode, the runner monitors your source files for changes.
When a `.py` file is saved, the module is reimported and `view()` is
re-evaluated with the preserved model. The window updates instantly.

If the reload fails (syntax error, import error), the error is logged
and the previous code continues running.

Uses [watchfiles](https://pypi.org/project/watchfiles/) when
available for fast, low-overhead change detection. Falls back to
polling if watchfiles is not installed.

## Decorator API

For simple apps or quick prototypes, a Flask-like decorator API is
available:

<!-- test: test_getting_started_decorator_init, test_getting_started_decorator_increment, test_getting_started_decorator_unknown_event, test_getting_started_decorator_view -- keep this code block in sync with tests/docs/test_getting_started.py -->

```python
import plushie
from plushie import ui
from plushie.events import Click

app = plushie.create_app()

@app.init
def init():
    return {"count": 0}

@app.update
def update(model, event):
    match event:
        case Click(id="inc"):
            return {**model, "count": model["count"] + 1}
        case _:
            return model

@app.view
def view(model):
    return ui.window(
        "main",
        ui.column(
            ui.text("count", f"Count: {model['count']}"),
            ui.button("inc", "+"),
            padding=16,
            spacing=8,
        ),
        title="Counter",
    )

if __name__ == "__main__":
    app.run()
```

## Next steps

- [Tutorial: building a todo app](tutorial.md) -- step-by-step guide
- Browse the [examples](https://github.com/plushie-ui/plushie-python/tree/main/examples) for patterns
- [App](app.md) -- full callback API
- [Layout](layout.md) -- sizing and positioning widgets
- [Commands](commands.md) -- async work, file dialogs, effects
- [Events](events.md) -- complete event taxonomy
- [Testing](testing.md) -- writing tests against your UI
- [Theming](theming.md) -- custom themes and palettes
