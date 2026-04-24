# Custom Widgets

The pad's `view` is starting to sprawl. The sidebar, the event log, and
the preview pane each have local shape and tiny responsibilities, but
they all live in one file reaching into one model. This chapter pulls
one of those pieces out into a **custom widget**: a reusable unit with
its own view, its own local state, and its own event vocabulary.

Plushie has three tiers of custom widget authoring in Python. Pick the
lightest one that does the job. The [Custom Widgets reference](../reference/custom-widgets.md)
has the exhaustive API surface; this chapter walks each tier in order.

## Tier 1: compose with a function

Before reaching for a framework, reach for a function. If a chunk of UI
has no local state and emits no new event vocabulary, a plain function
that returns a node dict is enough.

```python
from typing import Any

from plushie import ui


def field_row(field_id: str, label: str, value: str) -> dict[str, Any]:
    return ui.row(
        ui.text(f"{field_id}-label", label, size=12),
        ui.text_input(field_id, value),
        spacing=8,
    )
```

Nothing is registered. Events from the inner `text_input` flow straight
to the app's `update` the same way they would inline. Use this pattern
as long as it works. Reach for the next tier only when the component
needs state the parent should not have to care about.

## Tier 2: stateful widgets with `WidgetDef`

A rating picker has local state the app should not know about: which
star is hovered, whether the user is mid-drag, whether the focus ring
is visible. The app only wants the final number. That is the job of
`WidgetDef`.

`plushie.widget.WidgetDef` is the base class for pure-Python custom
widgets. `CanvasWidgetDef` is an alias for canvas-heavy code; it is the
same class. A subclass has two required methods (`init` for starting
state, `view` for rendering) plus an optional `handle_event` that
intercepts events before they reach the app.

```python
from typing import Any

from plushie.widget import EventAction, EventActionResult, WidgetDef


class MyWidget(WidgetDef):
    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def handle_event(
        self, event: Any, state: dict[str, Any]
    ) -> EventActionResult:
        return EventAction.ignored()
```

### Building a `StarRating` from scratch

Add `plushie_pad/widgets/star_rating.py`. The widget renders five stars
on a canvas, tracks the hovered star locally, and emits a `select`
event when the user clicks.

```python
from __future__ import annotations

from typing import Any

from plushie import canvas as c
from plushie import ui
from plushie.events import Click, Enter, Exit
from plushie.widget import EventAction, EventActionResult, WidgetDef

STAR_COUNT = 5


class StarRating(WidgetDef):
    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"hover": None}

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        rating = props.get("rating", 0)
        hover = state.get("hover")
        display = hover if hover is not None else rating

        stars = [
            _star(i, filled=i < display, is_hovered=(hover is not None))
            for i in range(STAR_COUNT)
        ]
        return ui.canvas(
            widget_id,
            width=160,
            height=32,
            layers=dict([c.layer("stars", *stars)]),
            role="radiogroup",
            alt="Star rating",
        )
```

The `view` renders a canvas with one interactive group per star. The
group IDs (`star-0` through `star-4`) are scoped to the widget, so the
handler sees short names.

```python
def _star(index: int, filled: bool, is_hovered: bool) -> dict[str, Any]:
    cx = index * 32 + 16
    color = "#ffb000" if filled else "#e0e0e0"
    return c.group(
        c.path(_star_path(), fill=color),
        f"star-{index}",
        x=cx,
        y=16,
        on_click=True,
        on_hover=True,
        cursor="pointer",
    )
```

`_star_path` returns a list of `c.move_to` and `c.line_to` commands
tracing a five-pointed star; see the [Canvas guide](12-canvas.md) for
the vocabulary.

### `handle_event` return values

The interesting method is `handle_event`. It receives every event whose
scope passes through this widget's ID, together with the current state.
It returns one of four `EventAction` results, and the runtime uses the
result to decide what happens next.

```python
def handle_event(
    self, event: Any, state: dict[str, Any]
) -> EventActionResult:
    match event:
        case Click(id=eid) if eid.startswith("star-"):
            n = int(eid.removeprefix("star-"))
            return EventAction.emit("select", n + 1)

        case Enter(id=eid) if eid.startswith("star-"):
            n = int(eid.removeprefix("star-"))
            return EventAction.update_state({"hover": n + 1})

        case Exit():
            return EventAction.update_state({"hover": None})

        case _:
            return EventAction.ignored()
```

The four factories mean different things:

| Factory | Meaning |
|---|---|
| `EventAction.ignored()` | Not captured. Event passes through to outer widgets and then `update`. |
| `EventAction.consumed()` | Captured. Drop the event. Nothing reaches `update`. |
| `EventAction.update_state(state)` | Captured. Replace widget-local state. Drop the event. |
| `EventAction.emit(kind, data, state=...)` | Captured. Rewrite the event as a new one. Optionally update state. |

A click on a star becomes `EventAction.emit("select", n + 1)`. Because
`"select"` matches a built-in event family, the framework routes it to
the parent as a typed `Select` event with `id` set to the widget ID and
`value` set to `n + 1`. Hover in and out update local state and suppress
the event. Anything else passes through with `ignored`.

### Widget-local state vs app model

The `hover` field lives on the widget. It exists only while the widget
is in the tree; when the placeholder leaves, the hover state is
dropped. The rating itself lives on the app's model, because it
survives page changes and must be persisted. Rule of thumb: if state
is meaningful after the widget disappears, it belongs on the app
model; everything else belongs on the widget.

State is keyed by `(window_id, scoped_id)`. Two `StarRating` instances
with different IDs have independent state. Changing a widget's ID
between renders looks like a removal plus a fresh insertion, so state
resets. Keep widget IDs stable.

### Wiring it into the pad

Widgets enter the view tree through a placeholder. `MyWidget.build(id,
props=...)` returns a node the runtime recognises during normalization,
looks up state for, and replaces with the rendered subtree.

```python
from plushie_pad.widgets.star_rating import StarRating


def view(self, model):
    return ui.window(
        "main",
        ui.column(
            ui.text("title", "Rate this experiment", size=16),
            StarRating.build(
                "experiment-rating",
                props={"rating": model.rating},
            ),
            padding=16,
            spacing=12,
        ),
        title="Plushie Pad",
    )
```

Handle the emitted `Select` in `update`:

```python
from dataclasses import replace

from plushie.events import Select


def update(self, model, event):
    match event:
        case Select(id="experiment-rating", value=n):
            return replace(model, rating=n)
        case _:
            return model
```

Widgets must be rendered inside a window. A placeholder at the root,
outside `ui.window`, raises `ValueError` during normalization.

## Widget-scoped subscriptions

An animated widget often needs its own timer. A `WidgetDef` can declare
subscriptions with an optional `subscribe(props, state)` method. The
runtime diffs the returned list against the previous cycle: new
subscriptions start, removed ones stop, and the timer ticks route
through the widget's `handle_event` instead of the app's `update`.

```python
from plushie.events import TimerTick
from plushie.subscriptions import Subscription


class PulsingIndicator(WidgetDef):
    def init(self, props):
        return {"phase": 0.0}

    def subscribe(self, props, state) -> list[Subscription]:
        if props.get("active", False):
            return [Subscription.every(16, "pulse")]
        return []

    def handle_event(self, event, state) -> EventActionResult:
        match event:
            case TimerTick(tag="pulse"):
                phase = (state["phase"] + 0.05) % 1.0
                return EventAction.update_state({"phase": phase})
            case _:
                return EventAction.ignored()
```

The tag seen inside `handle_event` is the short form (`"pulse"`). The
framework adds a `(window_id, widget_id)` namespace so multiple
instances never collide and the tick never leaks to `update`. Return an
empty list when idle to stop the timer until the widget needs it again.

## Declaring event specs

The `event_specs` class attribute documents and validates the events a
widget emits. When set, the framework checks every `emit` at the moment
it is produced, raising `ValueError` for undeclared names or missing
required fields and `TypeError` for mismatched field types.

```python
from typing import ClassVar

from plushie.widget import EventSpec, WidgetDef


class ColorPicker(WidgetDef):
    event_specs: ClassVar[dict[str, EventSpec]] = {
        "change": EventSpec(fields={
            "hue": float,
            "saturation": float,
            "value": float,
        }),
        "cleared": EventSpec(),
    }
```

Event names follow a `family:event` reading: the widget class picks the
family, the spec key picks the event name. Built-in family names
(`click`, `select`, `toggle`, `input`, `slide`) are delivered as the
matching typed dataclass, so `EventAction.emit("select", n)` arrives as
`Select`. Any other name becomes a `RawEvent` in the parent's `update`:

```python
from plushie.events import RawEvent, Select


def update(self, model, event):
    match event:
        case Select(id="experiment-rating", value=n):
            return replace(model, rating=n)
        case RawEvent(kind="change", id="picker", data=hsv):
            return replace(model, color=hsv)
        case RawEvent(kind="cleared", id="picker"):
            return replace(model, color=None)
        case _:
            return model
```

`RawEvent.kind` carries the event name, `id` carries the widget ID,
`data` carries the dict payload, and `value` carries a scalar when the
spec used `value_type=` instead of `fields=`. Leaving `event_specs`
empty disables validation. Fill it in as soon as the vocabulary
stabilises; the sooner typos become loud errors, the better.

## Tier 3: native widgets backed by Rust

When pure Python composition or a canvas is not enough (GPU shaders,
integration with a Rust crate, an input type the built-ins cannot
express), the escape hatch is a `NativeWidget`.

`plushie.native_widget.NativeWidget` describes the Rust crate, the
constructor, the props, and the commands the Python side can send.
`build_node` produces view-tree nodes; `build_command` produces a
`Command` targeting a live instance.

```python
from plushie.native_widget import (
    CommandDef,
    NativeWidget,
    ParamDef,
    PropDef,
    build_node,
)

gauge = NativeWidget(
    kind="gauge",
    rust_crate="native/gauge",
    rust_constructor="gauge::GaugeExtension::new()",
    props=[
        PropDef("value", "number"),
        PropDef("max", "number"),
        PropDef("color", "color"),
    ],
    commands=[CommandDef("set_value", [ParamDef("value", "number")])],
)


def gauge_node(widget_id: str, value: float, max_: float) -> dict:
    return build_node(gauge, widget_id, {"value": value, "max": max_})
```

The same widget is declared in `pyproject.toml` under `[tool.plushie]`
so that `python -m plushie build` compiles a custom renderer binary
that includes it. `python -m plushie download` refuses to fetch a
precompiled binary when extensions are declared.

```toml
[[tool.plushie.extensions]]
kind = "gauge"
rust_crate = "native/gauge"
rust_constructor = "gauge::GaugeExtension::new()"
```

The Rust crate depends on `plushie-widget-sdk` from crates.io and
implements the `PlushieWidget` trait. One requirement regularly bites
newcomers: the trait must implement `clone_for_session` so each
renderer session gets an independent instance. Without it, the session
pool hangs and the test suite times out. `column` and `row` clash with
macros in the Rust prelude, so import them from
`plushie_widget_sdk::iced::widget` explicitly.

The full build flow, trait surface, and command dispatch protocol live
in the [Custom Widgets reference](../reference/custom-widgets.md).
Native widgets are a last resort; most apps never need one.

## Try it

Keep the `StarRating` on the pad and experiment with widget authoring
in the rest of the UI:

- Extract the file list into a stateless function widget. It takes
  `files` and `active_file` and returns a column of buttons. No state,
  no new events.
- Turn the event log into a `WidgetDef` with local `expanded` state and
  a toggle button. The widget decides when to hide entries; the pad
  never sees the toggle click.
- Add a `PulsingIndicator` next to the save button that fades while a
  save command is in flight. Drive the `active` prop from the model.
- Declare `event_specs` on `StarRating` and watch the runtime reject a
  typo in the emitted name.

In the next chapter, the pad picks up structured state management:
undo, search, selection, and routing. See
[State Management](14-state-management.md).
