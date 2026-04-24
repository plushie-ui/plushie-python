# Animation and Transitions

Styling gave the pad a consistent palette. Motion gives it
feedback. This chapter wires three kinds of motion into the pad:
a fade on experiment switch, a slide-in save flash, and a spring
on the sidebar button hover.

## Renderer-side vs SDK-side

Plushie offers two animation systems. Renderer-side descriptors
wrap a prop value in a `Transition`, `Spring`, or `Sequence`; the
renderer interpolates locally and the SDK sends nothing further
while the animation plays. SDK-side `Tween` keeps the animated
value in your Python model. It advances one frame at a time,
driven by an `on_animation_frame` subscription, so `update` and
`view` run every frame for as long as the tween is active.

Rule of thumb: if the animated value only affects a prop on a
built-in widget, reach for a descriptor. If the value appears in
your model or inside a canvas callback, reach for `Tween`. Both
systems live in the `plushie.animation` package.

## Transition: duration and easing

`Transition` is the workhorse. It has a fixed duration, an easing
curve, and a target value. You declare it on the prop and the
renderer takes it from there.

```python
from plushie import ui
from plushie.animation import Transition

ui.container(
    "preview",
    ui.text("greeting", "Hello, Plushie!"),
    opacity=Transition(to=1.0, duration=200, easing="ease_out"),
    padding=12,
)
```

When the target changes (say the view function recomputes `to`
from the model), the renderer interpolates from the current value
to the new one without a jump. That is what makes a transition
different from swapping the value outright: continuity is
preserved even mid-animation.

`from_` sets an explicit starting value on first mount. Use it
for enter animations where the widget should appear from a
specific state:

```python
opacity=Transition(to=1.0, duration=200, from_=0.0, easing="ease_out")
```

Subsequent renders ignore `from_`; only the first appearance in
the tree uses it.

Pad application: a soft fade whenever the user switches
experiments. The preview rebuilds with a fresh `opacity`
descriptor keyed on the selected name, and the renderer cross
fades the container to its new content:

```python
def _preview(model):
    return ui.container(
        f"preview-{model.selected or 'empty'}",
        _preview_body(model),
        opacity=Transition(to=1.0, duration=220, from_=0.0, easing="ease_out"),
        padding=12,
        width="fill",
        height={"fill_portion": 2},
    )
```

The id changes with `model.selected`, so the container remounts
and the `from_=0.0` fade kicks in on every switch. That trick
keeps the animation declarative: no tracking of "previous
experiment" in the model, just a different id.

`Transition.loop` is sugar for ping-pong patterns. It sets
`repeat=-1` and `auto_reverse=True` by default; pass `cycles=N`
for a finite repeat.

## Spring: physics-based motion

Springs have no fixed duration. They pull toward `to`, lose
energy to damping, and settle when velocity and displacement
both approach zero. They interrupt gracefully: if the target
changes mid flight, the spring preserves momentum and redirects.
That is what makes them feel right for hover, drag release, and
other interactions where the user is pushing on the value.

```python
from plushie.animation import Spring

scale=Spring(to=1.05, stiffness=200, damping=20)
```

For the pad's sidebar hover, pull in a named preset. Presets cover
the common feels; each takes the same `to` you would pass to
`Spring` directly:

```python
from plushie.animation import Spring

ui.button(
    f"select-{exp.name}",
    exp.name,
    scale=Spring.preset("snappy", to=1.0),
    style="primary" if exp.name == model.selected else None,
)
```

Presets accept keyword overrides so a tweak stays cheap:
`Spring.preset("bouncy", to=1.0, damping=14)`. An unknown preset
name raises `ValueError` at view time.

| Preset | Feel |
|---|---|
| `"gentle"` | Slow, smooth, no overshoot |
| `"snappy"` | Quick, minimal overshoot |
| `"bouncy"` | Quick with visible bounce |
| `"stiff"` | Very quick, crisp stop |
| `"molasses"` | Slow, heavy |

Springs are best on interactive props: `scale`, `translate_x`,
`translate_y`, `rotation`. For size and opacity, a `Transition`
usually reads better.

## Sequence: chained segments

`Sequence` chains transitions and springs on the same prop. Each
step runs to completion before the next starts. Each step's
starting value defaults to the previous step's ending value.

```python
from plushie.animation import Sequence, Transition

opacity=Sequence(
    steps=(
        Transition(to=1.0, duration=150, from_=0.0, easing="ease_out"),
        Transition.loop(to=0.75, duration=600, from_=1.0, cycles=2),
        Transition(to=0.0, duration=250, easing="ease_in"),
    ),
    on_complete="flash_gone",
)
```

Only the sequence level `on_complete` fires when the whole chain
finishes. Per step `on_complete` tags on members are ignored.

Sequences shine for choreographed flashes: fade a badge in, pulse
it, then fade it out, with a single descriptor the view function
emits while a flag is set on the model.

## TransitionComplete

When a descriptor carries `on_complete="tag"`, the renderer emits
a `TransitionComplete` event once the animation lands on its
target. The event covers `Transition`, `Spring`, and `Sequence`
descriptors. Pattern match on the tag and act:

```python
from dataclasses import replace

from plushie.events import TransitionComplete


def update(self, model, event):
    match event:
        case TransitionComplete(tag="flash_gone"):
            return replace(model, saved_flash=False)
        case _:
            return model
```

The event carries the widget `id`, the `tag`, the `prop` that
completed, and the `scope` tuple. Pair it with tree removal to
build clean exits: animate `max_width` to zero with
`on_complete="collapsed"`, then drop the widget from the view on
the matching event so there is no flicker.

## Tween: SDK-side frame control

`Tween` is a frozen dataclass that interpolates a `float` value on
the Python side. You store it in the model, start it at an
`AnimationFrame` timestamp, and advance it each frame. The
runtime delivers frame events through
`Subscription.on_animation_frame()`:

```python
from dataclasses import dataclass, replace

import plushie
from plushie import Subscription, ui
from plushie.animation import Tween, ease_out
from plushie.events import Click, AnimationFrame


@dataclass(frozen=True, slots=True)
class Model:
    progress: Tween | None = None


class Loader(plushie.App[Model]):
    def init(self):
        return Model()

    def subscribe(self, model):
        if model.progress is None:
            return []
        return [Subscription.on_animation_frame()]

    def update(self, model, event):
        match event:
            case Click(id="start"):
                anim = Tween.new(0.0, 1.0, 600, easing=ease_out)
                return replace(model, progress=anim)
            case AnimationFrame(timestamp=ts):
                tween = model.progress
                if tween is None:
                    return model
                if tween.started_at is None:
                    tween = tween.start(int(ts))
                _value, updated = tween.advance(int(ts))
                if updated == "finished":
                    return replace(model, progress=None)
                return replace(model, progress=updated)
            case _:
                return model

    def view(self, model):
        pct = model.progress.value() if model.progress else 0.0
        return ui.window(
            "main",
            ui.column(
                ui.progress_bar("bar", pct, width=200),
                ui.button("start", "Load"),
            ),
        )
```

Return the subscription only while a tween is active; leaving
`on_animation_frame` on forever means `update` runs every frame
even when nothing needs it. `advance` returns
`(current_value, updated)` where `updated == "finished"` signals
completion; compare directly against the string.

`Tween.looping` is a convenience for infinite ping-pong tweens.
`interpolate(from_val, to_val, t, easing)` applies the same math
without a `Tween` instance.

## A saved badge for the pad

When a save completes, flash a "Saved!" badge into the toolbar,
hold it, then fade it away. Add a boolean flag to the model, set
it after a save, and clear it when the sequence reports
completion:

```python
from dataclasses import replace

from plushie.animation import Sequence, Transition
from plushie.events import Click, TransitionComplete


def update(self, model, event):
    match event:
        case Click(id="save"):
            return replace(_save(model), saved_flash=True)
        case TransitionComplete(tag="flash_gone"):
            return replace(model, saved_flash=False)
        case _:
            return model
```

The toolbar renders the badge whenever `saved_flash` is `True`.
The `Sequence` fades the badge in, holds it, then fades it out
and emits the completion tag:

```python
def _toolbar(model):
    controls = [
        ui.button("save", "Save" + (" *" if model.dirty else "")),
        ui.button(
            "autosave",
            "Autosave: On" if model.autosave else "Autosave: Off",
        ),
    ]
    if model.saved_flash:
        controls.append(
            ui.container(
                "saved-flash",
                ui.text("saved-text", "Saved!", color="#059669"),
                opacity=Sequence(
                    steps=(
                        Transition(to=1.0, duration=160, from_=0.0, easing="ease_out"),
                        Transition(to=1.0, duration=700),
                        Transition(to=0.0, duration=240, easing="ease_in"),
                    ),
                    on_complete="flash_gone",
                ),
                translate_x=Transition(to=0, duration=180, from_=-16, easing="ease_out"),
                padding=6,
            )
        )
    return ui.row(*controls, padding=8, spacing=8)
```

Two descriptors on one widget. The `opacity` sequence owns the
fade, the `translate_x` transition slides the badge in from the
left on first mount. The `TransitionComplete` event with
`tag="flash_gone"` clears `saved_flash`, the badge leaves the
tree on the next view cycle, and the motion resets for the next
save.

Animation descriptors resolve to their target values in the mock
backend, so the `AppFixture` click plus assert pattern keeps
working without frame waiting.

## Try it

- Swap the sidebar hover `Spring.preset("snappy", ...)` for
  `"bouncy"` and feel the overshoot.
- Add a `Transition` on the preview's `max_height` that collapses
  it to zero when `model.preview_error` is set, with
  `on_complete="error_collapsed"` to drop the preview from the
  tree after.
- Drive a `Tween` for a throbbing accent on the "unsaved" star,
  then compare the feel to the `Transition.loop` version above.

---

Next: Subscriptions.
