# Animation

Plushie has two animation systems. Renderer-side descriptors
(`Transition`, `Spring`, `Sequence`) wrap a prop value in the view
tree; the renderer interpolates locally at full frame rate and the
SDK sends nothing further while the animation plays. SDK-side
`Tween` keeps the animated value in your model and advances one
frame at a time, driven by an `on_animation_frame` subscription.
All of these live in `plushie.animation` and are re-exported at the
top level for convenience.

Prefer renderer-side descriptors for widget props. Reach for
`Tween` only when you need the animated value inside `update` or
`view` (canvas drawing, physics, values that drive model logic).

## Renderer-side vs SDK-side

| Concern | Renderer-side | SDK-side |
|---|---|---|
| Where interpolation runs | Renderer, per frame | Python runtime, per frame |
| Wire traffic while playing | None | One patch per frame |
| Triggers `update` each frame | No | Yes (via `AnimationFrame`) |
| Value visible to Python | No (only on completion) | Yes |
| Good for | Opacity, scale, slide, color, layout | Canvas, physics, model-driven math |

## Transition

`plushie.animation.Transition` is a timed animation with a fixed
duration and an easing curve.

```python
from plushie import ui
from plushie.animation import Transition

ui.container(
    "panel",
    ui.text("Hello"),
    max_width=Transition(to=200, duration=300, easing="ease_out"),
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `to` | `Any` | required | Target value (number, color, etc.) |
| `duration` | `int` | required | Duration in milliseconds |
| `easing` | `EasingSpec` | `"ease_in_out"` | Curve name or callable |
| `delay` | `int` | `0` | Delay before start (ms) |
| `from_` | `Any` | `None` | Explicit start value, used on first mount |
| `repeat` | `int \| None` | `None` | Repeat count, `-1` for infinite |
| `auto_reverse` | `bool` | `False` | Reverse direction on each repeat |
| `on_complete` | `str \| None` | `None` | Event tag sent when finished |

`from_` is applied only when the widget first appears. Subsequent
renders ignore it; changing `to` starts a new interpolation from
the current value, with no jump.

`Transition.loop` is sugar for repeating transitions. It sets
`repeat=-1` and `auto_reverse=True` by default, and takes `cycles`
for a finite repeat count.

```python
opacity=Transition.loop(to=0.4, from_=1.0, duration=1500)
rotation=Transition.loop(to=360, from_=0, duration=1000, auto_reverse=False)
opacity=Transition.loop(to=1.0, from_=0.5, duration=800, cycles=3)
```

### Wire format

Descriptors encode themselves via `to_wire()` during tree
normalization. You do not call this directly, but the shape is:

```python
{
    "type": "transition",
    "to": 200,
    "duration": 300,
    "easing": "ease_out",
}
```

Default values are omitted, so `easing="ease_in_out"` and
`delay=0` never appear in the payload.

## Spring

`plushie.animation.Spring` is a physics-based animation with no
fixed duration. The spring pulls toward `to`, damping removes
energy, and the animation settles when velocity and displacement
both approach zero. Springs preserve momentum across target
changes, so they feel natural for interactive controls (hover,
drag release, toggles).

```python
from plushie.animation import Spring

scale=Spring(to=1.05, stiffness=200, damping=20)
scale=Spring.preset("bouncy", to=1.05)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `to` | `Any` | required | Target value |
| `stiffness` | `float` | `100` | Spring constant (higher is snappier) |
| `damping` | `float` | `10` | Friction (higher is less bounce) |
| `mass` | `float` | `1.0` | Inertia (higher is heavier) |
| `velocity` | `float` | `0.0` | Initial velocity |
| `from_` | `Any` | `None` | Explicit start value |
| `on_complete` | `str \| None` | `None` | Event tag sent when the spring settles |

### Presets

`Spring.preset(name, to=...)` looks up named parameters in
`PRESETS` and lets you override any field via kwargs.

| Preset | Stiffness | Damping | Feel |
|---|---|---|---|
| `"gentle"` | 120 | 14 | Slow, smooth, no overshoot |
| `"snappy"` | 200 | 20 | Quick, minimal overshoot |
| `"bouncy"` | 300 | 10 | Quick with visible bounce |
| `"stiff"` | 400 | 30 | Very quick, crisp stop |
| `"molasses"` | 60 | 12 | Slow, heavy |

An unknown preset name raises `ValueError`.

## Sequence

`plushie.animation.Sequence` chains transitions and springs on the
same prop. Each step runs to completion before the next begins.

```python
from plushie.animation import Sequence, Transition

opacity=Sequence(
    steps=(
        Transition(to=1.0, duration=200, from_=0.0),
        Transition.loop(to=0.7, duration=800, from_=1.0, cycles=3),
        Transition(to=0.0, duration=300),
    ),
    on_complete="fade_cycle_done",
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `steps` | `tuple[Transition \| Spring, ...]` | required | Ordered animation steps |
| `on_complete` | `str \| None` | `None` | Event tag sent when the full sequence finishes |

Only the sequence-level `on_complete` fires. Per-step
`on_complete` tags on members are ignored.

## TransitionComplete

When a `Transition`, `Sequence`, or `Spring` carries
`on_complete="tag"`, the renderer emits a `TransitionComplete`
event once the animation lands at its target.

```python
from dataclasses import replace

from plushie.events import TransitionComplete


def update(self, model, event):
    match event:
        case TransitionComplete(tag="collapsed", prop="max_width"):
            return replace(model, panel_visible=False)
        case _:
            return model
```

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Widget that owns the animated property |
| `tag` | `str \| None` | The `on_complete` tag from the descriptor |
| `prop` | `str \| None` | Property name that completed (e.g. `"opacity"`) |
| `window_id` | `str` | Window containing the widget |
| `scope` | `tuple[str, ...]` | Ancestor container IDs, nearest first |

Pair completion events with tree removal to build choreographed
exits: animate `max_width` to zero with `on_complete="collapsed"`,
then drop the widget from the view on the matching event.

## Easing

Easing curves are passed to `Transition` and inside `Sequence`
steps. Two forms are accepted: a string name for renderer-side
lookup, or a callable for SDK-side Tween use. The type alias is
`EasingSpec = str | Easing` where
`Easing = Callable[[float], float]`.

The 31 named curves live in `NAMED_EASINGS` and are all exposed as
functions from `plushie.animation`:

### Standard

| Name | Function | Feel |
|---|---|---|
| `"linear"` | `linear` | Constant velocity |
| `"ease_in"` | `ease_in` | Sine acceleration |
| `"ease_out"` | `ease_out` | Sine deceleration |
| `"ease_in_out"` | `ease_in_out` | Sine both ends (default) |

### Power curves

| Family | In | Out | In-out |
|---|---|---|---|
| Quadratic | `"ease_in_quad"` | `"ease_out_quad"` | `"ease_in_out_quad"` |
| Cubic | `"ease_in_cubic"` | `"ease_out_cubic"` | `"ease_in_out_cubic"` |
| Quartic | `"ease_in_quart"` | `"ease_out_quart"` | `"ease_in_out_quart"` |
| Quintic | `"ease_in_quint"` | `"ease_out_quint"` | `"ease_in_out_quint"` |

### Exponential and circular

| Family | In | Out | In-out |
|---|---|---|---|
| Exponential | `"ease_in_expo"` | `"ease_out_expo"` | `"ease_in_out_expo"` |
| Circular | `"ease_in_circ"` | `"ease_out_circ"` | `"ease_in_out_circ"` |

### Overshoot

| Family | In | Out | In-out |
|---|---|---|---|
| Back | `"ease_in_back"` | `"ease_out_back"` | `"ease_in_out_back"` |
| Elastic | `"ease_in_elastic"` | `"ease_out_elastic"` | `"ease_in_out_elastic"` |
| Bounce | `"ease_in_bounce"` | `"ease_out_bounce"` | `"ease_in_out_bounce"` |

`by_name(name)` resolves a string to its callable counterpart, and
raises `KeyError` for unknown names.

### Cubic bezier

For curves outside the named set, `cubic_bezier(x1, y1, x2, y2)`
returns an `Easing` callable with control points attached. The
points match the CSS `cubic-bezier()` function and cross the wire
as `{"cubic_bezier": [x1, y1, x2, y2]}`.

```python
from plushie.animation import Transition, cubic_bezier

easing = cubic_bezier(0.25, 0.1, 0.25, 1.0)

opacity=Transition(to=1.0, duration=400, easing=easing)
```

## Tween

`plushie.animation.Tween` is a frozen dataclass that interpolates
a single `float` value on the SDK side. You store the tween in
your model, start it at an `AnimationFrame` timestamp, and advance
it each frame.

```python
from dataclasses import dataclass, replace

import plushie
from plushie import Subscription, ui
from plushie.animation import Tween, ease_out
from plushie.events import Click, AnimationFrame


@dataclass(frozen=True, slots=True)
class Model:
    tween: Tween | None = None


class Fader(plushie.App[Model]):
    def init(self):
        return Model()

    def subscribe(self, model):
        if model.tween is None:
            return []
        return [Subscription.on_animation_frame()]

    def update(self, model, event):
        match event:
            case Click(id="start"):
                anim = Tween.new(0.0, 1.0, 300, easing=ease_out)
                return replace(model, tween=anim)
            case AnimationFrame(timestamp=ts):
                tween = model.tween
                if tween is None:
                    return model
                if tween.started_at is None:
                    tween = tween.start(int(ts))
                value, updated = tween.advance(int(ts))
                if updated == "finished":
                    return replace(model, tween=None)
                return replace(model, tween=updated)
            case _:
                return model

    def view(self, model):
        opacity = model.tween.value() if model.tween else 1.0
        return ui.window(
            "main",
            ui.column(
                ui.container("box", opacity=opacity, width=100, height=100),
                ui.button("start", "Fade in"),
            ),
        )
```

### Constructors

| Function | Description |
|---|---|
| `Tween.new(from_val, to_val, duration_ms, *, easing=linear, repeat=None, auto_reverse=False)` | Create a new tween. `duration_ms` must be positive. |
| `Tween.looping(from_val, to_val, duration_ms, *, easing=linear)` | Create an infinite ping-pong tween (`repeat=None, auto_reverse=True`). |

### Instance methods

| Method | Description |
|---|---|
| `start(timestamp)` | Start or restart at a frame timestamp (returns a new tween). |
| `advance(timestamp)` | Return `(current_value, updated_tween_or_FINISHED)`. |
| `value()` | Current interpolated value. |
| `finished()` | `True` if the tween has completed. |

`advance` returns the sentinel `FINISHED` (the literal string
`"finished"`) in the tuple's second slot when the animation is
done. Compare directly: `if updated == "finished":`.

`interpolate(from_val, to_val, t, easing=linear)` is a
standalone helper that applies the same math without a `Tween`
instance.

## Animation frames

Subscribe to frame ticks with `Subscription.on_animation_frame()`.
The runtime delivers `AnimationFrame(timestamp=float)` events,
where `timestamp` is a monotonic millisecond clock suitable for
passing to `Tween.start` and `Tween.advance`.

Keep the subscription active only while something is animating.
Returning it from `subscribe` unconditionally costs an event per
frame for as long as the app is running.

## Animatable props

Not every prop supports animation descriptors. The renderer must
know how to interpolate between values. Commonly animated props:

| Prop | Typical use |
|---|---|
| `opacity` | Fade in/out |
| `scale` | Grow/shrink emphasis |
| `rotation` | Degrees of rotation on `text`, `image`, `rich_text` |
| `max_width`, `max_height` | Expand/collapse layout |
| `spacing` | Gap between children in `column` / `row` |
| `border_radius` | Animate corner rounding |
| `size`, `text_size` | Type size transitions |
| `translate_x`, `translate_y` | Slide on `floating` |
| `x`, `y` | Absolute position on `pin` |
| `width`, `height` | Specific widget dimensions (slider, text_editor) |
| `value` | Smooth changes on `progress_bar` |
| `background`, `color` | Color transitions (renderer interpolates in Oklch) |

`Length` values (`"fill"`, `"shrink"`, fill portions) are layout
directives, not numbers; use `max_width` / `max_height` instead
for size animation. Boolean props (`visible`, `disabled`, `clip`)
snap immediately.

## See also

- [Events](events.md)
- [Subscriptions](subscriptions.md)
- [Built-in widgets](built-in-widgets.md)
- [Themes and styling](themes-and-styling.md)
- [Windows and layout](windows-and-layout.md)
