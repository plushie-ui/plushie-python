# Introduction

For a reference-style lookup, see the [docs index](../README.md).

## What is Plushie?

Plushie is a native desktop GUI platform with SDKs for several languages.
This guide covers the Python SDK.

When you build an app with Plushie, you get real native windows. Not
Electron, not a web view. Your application is a Python process that owns
all the state. A separate Rust binary handles rendering, input, and
platform integration. The two processes talk over a wire protocol
(MessagePack by default, JSON available for debugging).

The renderer is built on [Iced](https://github.com/iced-rs/iced), a
cross-platform GUI toolkit for Rust. It provides GPU-accelerated
rendering, a software fallback for headless environments, and
accessibility support including keyboard navigation and screen reader
integration. You never interact with Iced directly. The SDK handles the
communication, and you write everything in Python.

## The Elm architecture

Plushie follows the Elm architecture, a pattern for building UIs around
one-way data flow. If you have used Elm, Redux, or LiveView, the shape
will feel familiar.

There are three pieces:

**Model.** Your application state. A frozen dataclass, a dict, a tuple,
a single integer. Whatever you return from `init` becomes the initial
model.

**Update.** A function that receives the current model and an event,
then returns the next model. Events arrive from user interaction (a
button click, a key press), from the system (a window resized, a timer
fired), or from your own async work. The update function is where all
state transitions happen.

**View.** A function that takes the current model and returns a UI tree
describing what should be on screen. The runtime calls `view` after
every successful update. You never mutate the UI directly. You return a
description of what the screen should look like based on the current
state.

The cycle:

```
event -> update -> new model -> view -> UI tree -> render
```

Events go in, state comes out, the view reflects it. No two-way
binding, no hidden mutation. When something looks wrong on screen, you
look at the model. When the model is wrong, you look at the event that
changed it. Every bug has a short trail.

Plushie also supports **subscriptions**, declarative specs for ongoing
event sources like timers, keyboard shortcuts, and window events. Your
app declares which subscriptions are active based on the current model,
and the runtime starts and stops them automatically. See the
[Subscriptions reference](../reference/subscriptions.md) for the full
catalog.

## Python idioms

The guides lean on three Python idioms. They are not novelties. They
are what a modern typed Python codebase looks like.

**Frozen dataclasses for models.** Model types are `@dataclass(frozen=True,
slots=True)` with `tuple[...]` collections rather than lists. Updates use
`dataclasses.replace(model, field=value)`. Immutability makes reasoning
about the update cycle trivial: the old model is still around, the new
one is a separate value, nothing shifted under your feet.

```python
from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0
    items: tuple[str, ...] = ()
```

**Per-family dataclass events, matched with `match` / `case`.** Each
wire event family is its own frozen dataclass: `Click`, `Input`,
`Toggle`, `Slide`, and so on. No stringly-typed discriminator. The
`value` field on `Input` is always `str`; on `Toggle` it is always
`bool`. Pattern match on the class:

```python
from dataclasses import replace

from plushie.events import Click, Input


def update(self, model, event):
    match event:
        case Click(id="inc"):
            return replace(model, count=model.count + 1)
        case Input(id="search", value=text):
            return replace(model, query=text)
        case _:
            return model
```

The trailing `case _: return model` matters. If no branch matches,
`match` returns `None`, and the runtime will log a warning and hold the
previous model. Always terminate `update` with a catch-all. See the
[Events reference](../reference/events.md) for the full taxonomy.

**`App` as a typed generic ABC.** Applications subclass
`plushie.App[Model]`, parameterised by their model type. Required
methods: `init`, `update`, `view`. Optional: `subscribe`, `settings`,
`window_config`, `handle_renderer_exit`. `self` is available for
per-instance configuration or injected dependencies, but it never
holds model state. The model is always passed in explicitly.

```python
import plushie
from plushie import ui


class Counter(plushie.App[Model]):
    def init(self):
        return Model()

    def update(self, model, event):
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case _:
                return model

    def view(self, model):
        return ui.window(
            "main",
            ui.column(
                ui.text("count", f"Count: {model.count}"),
                ui.button("inc", "+"),
                padding=16,
            ),
            title="Counter",
        )
```

The SDK is synchronous. `update`, `view`, and `subscribe` all run on a
single runtime thread. There is no `async def` in user code. For
background work, the runtime offers `Command.task`, which runs a
function on a thread pool and posts the result back as an event. See
the [Commands reference](../reference/commands.md) for the full set.

## What you will build

Across the guides you will build **Plushie Pad**, a live Python
experiment editor. The pad dogfoods the SDK: you type widget code in
the editor pane, save, and the pad compiles the module with
`compile(source, ...)` / `exec(code, ns)` and renders the result in the
preview pane. An event log on the side shows every event that fires as
you interact with the rendered output. It doubles as a personal
playground for any part of the API.

## Reading order

Chapter 2 walks through installation, binary download, and a first
run. Chapter 3 introduces the pad scaffold and the Elm loop. Chapters
covering events, layout, styling, animation, subscriptions, async and
effects, canvas, custom widgets, state management, and testing layer
capabilities onto the pad. The final chapter covers WASM deployment so
you can ship the same application to a browser.

The reference pages are orthogonal to this arc. Reach for them when you
need the exhaustive list of widget props, event constructors, or CLI
flags. Useful starting points: the
[Built-in Widgets reference](../reference/built-in-widgets.md), the
[Events reference](../reference/events.md), and the
[Commands reference](../reference/commands.md).

Let's get started.

---

Next: [Getting Started](02-getting-started.md)
