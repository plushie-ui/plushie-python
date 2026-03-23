# Getting started

Build native desktop GUIs from Python. Plushie handles rendering via
iced (Rust) while you own state, logic, and UI trees in pure Python.

## Prerequisites

- **Python** 3.12+
- **pip** (or any PEP 517-compatible installer)

The plushie renderer binary is downloaded automatically on first use.
No Rust toolchain needed unless you are building custom extensions.

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
        return ui.window("main",
            ui.column(
                ui.text("count", f"Count: {model.count}"),
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

A native window appears with the count and two buttons.

## The Elm architecture

Plushie follows the Elm architecture. Your app class implements:

- **`init()`** -- returns the initial model (any Python object).
- **`update(model, event)`** -- takes the current model and an event,
  returns the new model. To run side effects, return
  `(model, command)` instead.
- **`view(model)`** -- takes the model and returns a UI tree as a
  plain dict. Plushie diffs trees and sends only patches to the
  renderer.
- **`subscribe(model)`** (optional) -- returns a list of active
  subscriptions (timers, keyboard events).

## Event types

Events are frozen dataclasses under `plushie.events`. Pattern match
in `update()`:

| Event | Meaning |
|---|---|
| `Click(id=id)` | Button click |
| `Input(id=id, value=val)` | Text input change |
| `Submit(id=id, value=val)` | Text input Enter |
| `Toggle(id=id, value=val)` | Checkbox/toggler |
| `Slide(id=id, value=val)` | Slider moved |
| `Select(id=id, value=val)` | Pick list/radio |
| `TimerTick(tag=tag)` | Timer fired |

## Running apps

```sh
python -m plushie run myapp:Counter     # run by module:class path
python -m plushie run myapp:Counter --json  # JSON wire format (debug)
python -m plushie connect myapp:App     # connect mode (stdio transport)
python -m plushie inspect myapp:App     # print UI tree as JSON
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

## Next steps

- Browse the examples in `examples/` for patterns
- [Testing](testing.md) -- writing tests against your UI
- [Standalone executables](standalone.md) -- bundling for distribution
