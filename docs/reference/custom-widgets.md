# Custom Widgets

Plushie has three tiers of custom widget in Python. The simplest is a
plain function that returns a node dict: no framework involvement, just
composition. The middle tier is a `WidgetDef` subclass that owns local
state, transforms events, and can declare subscriptions. The top tier
is a `NativeWidget` backed by a Rust crate, used when you need GPU
drawing or input types the built-ins cannot express.

This reference covers the three tiers, the `handle_event` protocol, the
event dispatch chain, widget-local state, widget-scoped subscriptions,
event validation via `event_specs`, the caching hook, registration, and
the `WidgetFixture` test harness.

## Composition: a function returning a node

The lightest form of a custom widget is a function. Take the slice of
the model you need, return the same kind of dict `plushie.ui` builders
emit. Nothing is registered, no state is tracked, events flow straight
to the app's `update`.

```python
from typing import Any

from plushie import ui


def user_card(user_id: str, name: str, email: str) -> dict[str, Any]:
    return ui.container(
        f"user:{user_id}",
        ui.column(
            ui.text(name, size=16),
            ui.text(email, color="#666"),
            spacing=4,
        ),
        padding=12,
    )
```

Use this whenever the component has no local state and no new event
semantics. See [Composition Patterns](composition-patterns.md) for
larger recipes.

## `WidgetDef`: stateful, self-contained widgets

For components that keep state between events or rewrite events into
higher-level ones, subclass `plushie.widget.WidgetDef`. The same class
covers both canvas-backed widgets (view returns a `ui.canvas` with
`plushie.canvas` shapes) and composite widgets (view returns a
composition of built-in widgets). `plushie.canvas_widget.CanvasWidgetDef`
is an alias kept for clarity in canvas-heavy code; it is the same class.

### Required methods

```python
from typing import Any

from plushie.widget import WidgetDef


class MyWidget(WidgetDef):
    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        ...

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        ...
```

| Method | Signature | Required? |
|---|---|---|
| `init` | `(self, props) -> state` | Yes |
| `view` | `(self, widget_id, props, state) -> node` | Yes |
| `handle_event` | `(self, event, state) -> EventActionResult` | No |
| `subscribe` | `(self, props, state) -> list[Subscription]` | No |
| `cache_key` | `(self, props, state) -> Any` | No |

`init` returns the starting state dict for a fresh instance. `view`
returns a node dict exactly as a `plushie.ui` builder would, using
`widget_id` as the outermost `id`. The default `handle_event` returns
`EventAction.ignored()`, making the widget transparent. The default
`subscribe` returns an empty list. The default `cache_key` returns
`None`, disabling the cache.

### Building a placeholder

Widgets enter the view tree through `MyWidget.build(widget_id, props=...)`,
which returns a placeholder node carrying the class and props in its
`meta`. The runtime detects placeholders during normalization, looks up
or initialises state, calls `view`, and replaces the placeholder with
the rendered subtree.

```python
from plushie import ui


def view(self, model):
    return ui.window(
        "main",
        ui.column(
            StarRating.build("rating", props={"rating": model.rating}),
            padding=16,
        ),
        title="Review",
    )
```

Widgets must be rendered inside a window. Rendering a placeholder
outside one raises `ValueError`.

### Example: canvas-backed widget

```python
import math
from typing import Any

from plushie import canvas as c
from plushie import ui
from plushie.events import Click, Enter, Exit
from plushie.widget import EventAction, EventActionResult, WidgetDef

STAR_COUNT = 5


class StarRating(WidgetDef):
    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"hover": None}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
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
                return EventAction.consumed()

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        rating = props.get("rating", 0)
        hover = state.get("hover")
        display = hover if hover is not None else rating
        stars = [_star(i, filled=i < display) for i in range(STAR_COUNT)]
        return ui.canvas(
            widget_id,
            width=160,
            height=32,
            layers=dict([c.layer("stars", *stars)]),
        )
```

The hover state is local to the widget. The app only sees a `Select`
event with `value=1..5` when the user clicks.

### Example: composite widget

When `view` returns a composition of built-in widgets instead of a
canvas, nothing else changes:

```python
from typing import Any

from plushie import ui
from plushie.events import Click
from plushie.widget import EventAction, EventActionResult, WidgetDef


class NoteCard(WidgetDef):
    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"expanded": False}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        match event:
            case Click(id="toggle"):
                return EventAction.update_state({"expanded": not state["expanded"]})
            case _:
                return EventAction.ignored()

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        body = props.get("body", "")
        visible = body if state["expanded"] else body[:80]
        return ui.container(
            widget_id,
            ui.column(
                ui.text(props.get("title", "")),
                ui.text(visible),
                ui.button("toggle", "Collapse" if state["expanded"] else "Expand"),
            ),
        )
```

## `handle_event` return values

`handle_event` must return one of the `EventAction` results. The
runtime uses the result to decide whether propagation stops, whether
state changes, and whether a new event replaces the original.

| Factory | Meaning |
|---|---|
| `EventAction.ignored()` | Not captured. Event passes through to the next handler and then to `update`. |
| `EventAction.consumed()` | Captured. Drop the event. |
| `EventAction.update_state(state)` | Captured. Replace internal state. Drop the event. |
| `EventAction.emit(kind, data, state=...)` | Captured. Rewrite the event as a new one. Optionally update state. |

`EventAction.emit` accepts either a dict (structured data) or a scalar
(wrapped into `{"value": data}`). When `kind` matches a built-in event
family (`"click"`, `"input"`, `"select"`, `"toggle"`, `"slide"`, etc.)
the framework constructs the matching typed dataclass, so the consumer
writes `case Select(id="rating", value=n):` in `update`. For any other
`kind`, the framework builds a `RawEvent` with `kind="my_event_name"`,
`id` set to the widget ID, and `data` carrying the payload.

```python
from plushie.events import RawEvent, Select


def update(self, model, event):
    match event:
        case Select(id="rating", value=n):
            return replace(model, rating=n)
        case RawEvent(kind="change", id="picker", data=hsv):
            return replace(model, color=hsv)
        case _:
            return model
```

## Event dispatch chain

Events with a `scope` walk the widget chain from innermost to
outermost. Each widget in the chain gets a chance at `handle_event` in
order.

1. The event arrives carrying `id`, `scope` (ancestor IDs, nearest
   first), and `window_id`.
2. The runtime builds the handler chain from `scope`, looking up each
   ancestor path in the widget registry.
3. Each handler sees the event. The first captured result wins:
   - `ignored` continues to the next handler unchanged.
   - `consumed` drops the event and stops the chain.
   - `update_state` updates state and stops the chain.
   - `emit` replaces the event with a new typed event and continues
     through the remaining outer handlers.
4. If nothing captures, the original event reaches `update`.

Because the chain follows scope, nested widgets compose naturally: an
inner widget can emit a higher-level event, and an outer widget can
intercept it and rewrite it again.

## Widget-local state

State follows tree presence. It is keyed by `(window_id, scoped_id)` in
the handler registry.

- **Appear**: when a placeholder enters the tree, state is initialised
  from `init(props)`.
- **Update**: when `handle_event` returns `update_state` or `emit` with
  a `state=` kwarg, the registry entry is updated in place.
- **Re-render**: `view` is called with the current state on each render.
- **Disappear**: when the placeholder leaves the tree, the state is
  dropped.

Widget IDs are transparent to scoping. A widget does not create its own
scope; children rendered by `view` inherit the parent container's
scope. See [Scoped IDs](scoped-ids.md) for the full rules.

If the widget ID changes between renders the runtime treats it as a
removal followed by a fresh insertion, so state resets.

## Widget-scoped subscriptions

A widget can register its own subscriptions via `subscribe(props,
state)`. The runtime namespaces the tag of each returned subscription
behind the widget's `(window_id, widget_id)` key, so multiple instances
of the same widget never collide, and timer ticks route back through
the widget's `handle_event` instead of reaching `update`.

```python
from plushie.events import TimerTick
from plushie.subscriptions import Subscription
from plushie.widget import EventAction, EventActionResult, WidgetDef


class ThemeToggle(WidgetDef):
    def init(self, props):
        return {"progress": 0.0, "target": 0.0}

    def subscribe(self, props, state) -> list[Subscription]:
        if state["progress"] != state["target"]:
            return [Subscription.every(16, "animate")]
        return []

    def handle_event(self, event, state) -> EventActionResult:
        match event:
            case TimerTick(tag="animate"):
                progress = _approach(state["progress"], state["target"], 0.06)
                return EventAction.update_state({**state, "progress": progress})
            case _:
                return EventAction.ignored()
```

The inner tag (`"animate"`) is what the widget sees on the `TimerTick`.
The outer `("__widget__", window_id, widget_id, "animate")` wrapping is
an implementation detail that never reaches user code. Starting and
stopping subscriptions is handled automatically across renders: if the
list returned by `subscribe` changes between cycles, the runtime starts
new subscriptions and stops removed ones.

## Declaring event specs

A widget can document and validate the events it emits through the
class-level `event_specs` dict. When set, the framework checks every
`emit` at the moment it is produced, raising `ValueError` for
undeclared event names or missing required fields and `TypeError` for
mismatched field types.

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

`EventSpec` has three forms:

| Form | Purpose |
|---|---|
| `EventSpec()` | No payload; just the event name. |
| `EventSpec(value_type=T)` | Scalar payload delivered as `RawEvent.value`. |
| `EventSpec(fields={...})` | Structured payload delivered as `RawEvent.data`. |

Pass `optional=("field_name",)` to mark fields that may be omitted from
the emit data. Optional fields are still type-checked when present.
`EventSpec` rejects specs that declare both `fields` and `value_type`,
and rejects `optional` without a `fields` declaration.

Leaving `event_specs` empty (the default) disables validation entirely.
Built-in event names (`"click"`, `"select"`, etc.) do not need specs:
the framework always recognises them and routes them to the matching
typed dataclass.

## Optional caching via `cache_key`

Override `cache_key(props, state)` to return a hashable-equal value
summarising everything `view` depends on. When the runtime re-renders
and the key compares equal to the stored value, the cached view tree is
reused and `view` is not called. Return `None` to disable caching for
that render.

```python
def cache_key(self, props, state):
    return (props.get("source"), state.get("theme"))
```

Use this only for widgets whose `view` is expensive and whose inputs
are small and stable. Most widgets do not need it.

## Registration

Registration happens automatically from the view tree. When `view`
returns a placeholder node produced by `MyWidget.build(...)`, the
runtime records the instance, its state, and its props under the
canonical `(window_id, widget_id)` key. The registry is rebuilt by
walking the normalized tree each cycle via
`plushie.widget.derive_registry`, so there is no global state to
register at import time and no teardown to manage.

Test code that needs an isolated registry can construct one ad hoc from
a tree (`derive_registry(tree)`), feed it into `dispatch_through_widgets`,
or use the `WidgetFixture` described below.

## `NativeWidget`: Rust-backed custom widgets

When you need GPU drawing or an input type the built-ins and canvas do
not cover, define a native widget. `plushie.native_widget.NativeWidget`
describes the Rust crate, constructor, props, and commands. The Python
side uses `build_node` to produce view-tree nodes and `build_command`
to send commands to live instances.

```python
from plushie.commands import Command
from plushie.native_widget import (
    CommandDef,
    NativeWidget,
    ParamDef,
    PropDef,
    build_command,
    build_node,
)

gauge = NativeWidget(
    kind="gauge",
    rust_crate="native/gauge",
    rust_constructor="gauge::GaugeExtension::new()",
    props=[
        PropDef("value", "number"),
        PropDef("min", "number"),
        PropDef("max", "number"),
        PropDef("color", "color"),
    ],
    commands=[
        CommandDef("set_value", [ParamDef("value", "number")]),
    ],
)


def gauge_node(widget_id: str, value: float, **kwargs: object) -> dict:
    return build_node(gauge, widget_id, {"value": value, **kwargs})


def set_gauge(node_id: str, value: float) -> Command:
    return build_command(gauge, node_id, "set_value", {"value": value})
```

`PropType` accepts `"string"`, `"number"`, `"bool"`, `"color"`,
`"length"`, `"padding"`, `"alignment"`, `"font"`, `"style"`, `"atom"`,
`"map"`, and `"any"`. `ParamType` accepts `"string"`, `"number"`, and
`"bool"`. The reserved prop names are `id`, `type`, `children`, `a11y`,
and `event_rate`: `validate(widget_def)` returns an error list for any
definition that uses them or shadows a built-in widget name.

### `pyproject.toml` wiring

The same widget is declared in `pyproject.toml` under
`[tool.plushie]` so that `python -m plushie build` compiles it into
a custom binary:

```toml
[[tool.plushie.extensions]]
kind = "gauge"
rust_crate = "native/gauge"
rust_constructor = "gauge::GaugeExtension::new()"

  [[tool.plushie.extensions.props]]
  name = "value"
  prop_type = "number"

  [[tool.plushie.extensions.commands]]
  name = "set_value"

    [[tool.plushie.extensions.commands.params]]
    name = "value"
    param_type = "number"
```

`python -m plushie download` refuses to fetch a precompiled binary when
extensions are declared: they would not be baked in. Run `python -m
plushie build` instead. See [Configuration](configuration.md) and
[CLI Commands](cli-commands.md) for the build flow.

### Rust crate requirements

The Rust crate depends on `plushie-widget-sdk` from crates.io and
implements the `PlushieWidget` trait. The trait has one requirement
that commonly bites newcomers: it must implement `clone_for_session`
so each renderer session gets an independent instance. Native widgets
without `clone_for_session` wired up will hang the session pool and
the test suite times out.

`column` and `row` clash with macros in the Rust prelude; import them
from `plushie_widget_sdk::iced::widget` explicitly.

Commands issued via `build_command` travel over the wire as a unified
`command` message targeting the widget's node ID. The Rust side
dispatches via `handle_widget_op`, reading the `family` (the op name)
and `value` payload.

## Testing custom widgets

`plushie.testing.WidgetFixture` hosts a single widget inside a harness
app wired to the real renderer. It is a subclass of `AppFixture`, so
all the standard interaction helpers (`click`, `find`, `text`, and so
on) are available. It additionally records every event the widget
emits.

```python
import pytest

from plushie.testing import WidgetFixture

from myapp.widgets.star_rating import StarRating


@pytest.fixture
def rating(plushie_pool):
    with WidgetFixture(StarRating, "rating", plushie_pool,
                       widget_props={"rating": 0}) as w:
        yield w


def test_emits_select_on_click(rating):
    rating.canvas_press("#rating", 70.0, 16.0)
    assert rating.last_event is not None
    assert rating.last_event.value == 3
```

| Attribute | Description |
|---|---|
| `last_event` | Most recent event emitted by the widget, or `None`. |
| `events` | Tuple of every emitted event, oldest first. |
| `last_value` | `value` of the most recent event, or `None`. |

See [Testing](testing.md) for the full fixture API and backend modes.

## See also

- [Events](events.md)
- [Canvas](canvas.md)
- [Subscriptions](subscriptions.md)
- [Scoped IDs](scoped-ids.md)
- [Configuration](configuration.md)
- [Testing](testing.md)
