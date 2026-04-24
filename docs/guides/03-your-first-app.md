# Your First App

In the previous chapter we installed the SDK and downloaded the renderer
binary. Now we start building **Plushie Pad**, a live Python experiment
editor that will grow alongside this guide. Each chapter adds one
capability on top of the last.

This chapter sets up the pad's skeleton: a sidebar listing saved
experiments, a text editor showing the currently selected one, and the
plumbing that keeps them in sync. Nothing renders the experiment yet,
that comes in chapter 5 once we have enough layout and event vocabulary
under our belt. For now we focus on the shape of an app: model, update,
view.

## Project layout

Create a new project next to your other Python work. The pad is a
regular Python package plus a sibling `experiments/` directory that
holds the saved scripts.

```
plushie_pad/
├── plushie_pad/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── compile.py
│   └── experiments.py
├── experiments/
│   └── hello.py
└── pyproject.toml
```

A minimal `pyproject.toml` is enough. Plushie itself is the only runtime
dependency:

```toml
[project]
name = "plushie-pad"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["plushie"]

[build-system]
requires = ["hatchling>=1.18"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["plushie_pad"]

[tool.plushie]
artifacts = ["bin"]
```

The `[tool.plushie]` table tells `python -m plushie download` which
artifacts to fetch. See the [Configuration
reference](../reference/configuration.md) for the full set of keys.

Seed the first experiment in `experiments/hello.py`:

```python
from plushie import ui


def view():
    return ui.column(
        ui.text("greeting", "Hello, Plushie!", size=24),
        ui.button("btn", "Click Me"),
        padding=16,
        spacing=8,
    )
```

Each experiment is a self-contained module that exposes a `view()`
callable. The pad will load them from disk, compile them on demand, and
(eventually) render the result. For this chapter we only list them.

## Loading experiments from disk

`plushie_pad/experiments.py` owns disk I/O. It knows where experiments
live and how to list, load, and save them. The pad's `app.py` never
touches the filesystem directly.

```python
from dataclasses import dataclass
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent / "experiments"


@dataclass(frozen=True, slots=True)
class Experiment:
    name: str
    source: str


def list_experiments() -> tuple[Experiment, ...]:
    if not EXPERIMENTS_DIR.exists():
        return ()
    return tuple(
        Experiment(name=path.stem, source=path.read_text())
        for path in sorted(EXPERIMENTS_DIR.glob("*.py"))
    )


def load(name: str) -> Experiment | None:
    path = EXPERIMENTS_DIR / f"{name}.py"
    if not path.exists():
        return None
    return Experiment(name=name, source=path.read_text())


def save(name: str, source: str) -> Experiment:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPERIMENTS_DIR / f"{name}.py"
    path.write_text(source)
    return Experiment(name=name, source=source)
```

`Experiment` is a frozen dataclass with `slots=True`. The rest of the
pad treats it as immutable, which is exactly the discipline the Elm
architecture wants for everything that ends up in the model.

`compile.py` will do the heavy lifting in chapter 5. For now, create it
as an empty module so the imports line up:

```python
# plushie_pad/compile.py
# Filled in later once we start rendering experiments.
```

## The model

The pad's model lives in `plushie_pad/app.py`. Keep it small for now.
We track the loaded experiments, which one is selected, and the editor
buffer:

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click, Input

from plushie_pad import experiments as pad_experiments


@dataclass(frozen=True, slots=True)
class Model:
    experiments: tuple[pad_experiments.Experiment, ...] = ()
    selected: str | None = None
    editor_source: str = ""
```

Tuples, not lists. Frozen dataclass, not a namespace of mutable
attributes. Later chapters add fields (`dirty`, `autosave`,
`event_log`), but the shape stays the same: one dataclass, all state,
no hidden corners.

## init

`init()` runs once at startup. It returns the initial model. The pad
lists what is on disk, picks the first experiment, and seeds the editor
buffer with its source:

```python
class Pad(plushie.App[Model]):
    def init(self) -> Model:
        exps = pad_experiments.list_experiments()
        selected = exps[0].name if exps else None
        source = exps[0].source if exps else ""
        return Model(
            experiments=exps,
            selected=selected,
            editor_source=source,
        )
```

`plushie.App[Model]` is generic over the model type, which gives the
type checker something to hold onto. The `App` base class is an ABC
with `init`, `update`, `view`, plus optional hooks for subscriptions
and window configuration. See the [App lifecycle
reference](../reference/app-lifecycle.md) for the full surface.

## view

The view returns a plain dict describing the UI tree. The `ui` module
ships builder functions that produce the right shape, and since nodes
are just dicts you can mix builders with raw data when that reads
better. For the pad we stick to the builders.

```python
def view(self, model: Model) -> dict:
    return ui.window(
        "pad",
        ui.row(
            _sidebar(model),
            _editor(model),
            spacing=0,
            width="fill",
            height="fill",
        ),
        title="Plushie Pad",
        size=(1100, 700),
    )


def _sidebar(model: Model) -> dict:
    return ui.container(
        "sidebar",
        ui.column(
            ui.text("sidebar-title", "Experiments", size=14),
            *(
                ui.button(
                    f"select-{exp.name}",
                    exp.name,
                    style="primary" if exp.name == model.selected else None,
                )
                for exp in model.experiments
            ),
            padding=12,
            spacing=8,
            width=220,
        ),
        width=220,
        height="fill",
    )


def _editor(model: Model) -> dict:
    return ui.text_editor(
        "editor",
        model.editor_source,
        width="fill",
        height="fill",
        highlight_syntax="python",
    )
```

A few things worth pausing on.

`ui.window` is a named container. Its first positional argument is the
ID. Anonymous containers (`ui.column`, `ui.row`, `ui.stack`) take no
ID and receive children as positional args and options as kwargs.
Leaf widgets that carry state (`ui.text_editor`, `ui.text_input`,
`ui.button`) take their ID first. See [Built-in
widgets](../reference/built-in-widgets.md) for the full catalogue.

`width="fill"` and `size=(1100, 700)` are examples of prop values that
pass through to the renderer. The Python SDK does not validate them.
The renderer does. See [Windows and
layout](../reference/windows-and-layout.md) for the sizing vocabulary.

The sidebar generates one button per experiment using a generator
expression unpacked into `ui.column`'s children. Each button gets a
stable ID of the form `select-<name>`. We will match on that prefix in
`update`.

The editor widget is a `text_editor` with syntax highlighting set to
`"python"`. Stateful widgets like `text_editor`, `text_input`, and
`scrollable` need explicit string IDs so the renderer can preserve
cursor position and scroll offset across renders. Layout widgets are
fine with auto-generated IDs.

## update

`update` is a pure function of model and event. It returns the new
model. Two events matter for this chapter: clicking a sidebar button
and typing in the editor.

```python
def update(self, model: Model, event) -> Model:
    match event:
        case Click(id=exp_id) if exp_id.startswith("select-"):
            name = exp_id.removeprefix("select-")
            exp = pad_experiments.load(name)
            if exp is None:
                return model
            return replace(
                model,
                selected=exp.name,
                editor_source=exp.source,
            )

        case Input(id="editor", value=source):
            return replace(model, editor_source=source)

        case _:
            return model
```

`Click` and `Input` are imported from `plushie.events`. Each event
family has its own frozen dataclass, which means `Click` has an `id`
but no `value`, and `Input.value` is `str`. The type checker catches
mistakes before the renderer does. See the [Events
reference](../reference/events.md) for the full taxonomy.

The guard clause on `Click(id=exp_id) if exp_id.startswith("select-")`
is the Python-native way to match on a string prefix. `removeprefix`
does the rest.

The catch-all `case _: return model` is not optional. If no branch
matches and you fall off the end of `update`, Python returns `None`.
The runtime notices, logs a warning, and keeps the previous model.
Losing state silently is exactly the kind of bug that wastes an
afternoon, so make the catch-all a habit.

`dataclasses.replace` builds a new `Model` with overridden fields. The
old model is never mutated. This is what lets the runtime diff
efficiently between cycles.

## Wire it up

`__main__.py` starts the runtime:

```python
import plushie

from plushie_pad.app import Pad


def main() -> None:
    plushie.run(Pad)


if __name__ == "__main__":
    main()
```

`__init__.py` re-exports the app class so `plushie inspect` and other
tools can find it:

```python
from plushie_pad.app import Pad

__all__ = ["Pad"]
```

## Running it

Install the package in editable mode, then fetch the renderer binary:

```bash
pip install -e .
python -m plushie download
```

Run the pad:

```bash
python -m plushie_pad
```

A window opens. The sidebar lists `hello` (and whatever else is in
`experiments/`). Click a sidebar button and the editor content
switches. Type in the editor and the buffer follows along. That is the
whole init/update/view cycle, end to end, backed by a real renderer
over MessagePack.

If the window does not appear, double-check that `python -m plushie
download` completed and that `experiments/hello.py` exists next to the
package. Chapter 4 covers the development loop in detail: hot reload,
inspecting the tree, and what to do when the renderer dies.

Next: [The Development Loop](04-the-development-loop.md).
