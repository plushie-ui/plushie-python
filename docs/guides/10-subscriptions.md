# Subscriptions

Every event in the pad so far has come from direct interaction with a
widget. Some events come from outside the tree: keyboard shortcuts,
timers, window resizes, system theme changes. Plushie delivers those
through **subscriptions**.

Subscriptions live in `plushie.subscriptions.Subscription`, re-exported
as `plushie.Subscription`. They pair with the `subscribe` method on the
app class, which is called after every update cycle.

## Subscriptions are a function of the model

`subscribe` receives the current model and returns a list of
subscription specs. The runtime diffs that list against the previous
cycle and starts or stops underlying event sources to match.

```python
from plushie import Subscription


def subscribe(self, model):
    return [Subscription.on_key_press()]
```

You never call a "start" or "stop" function. You describe what you
want, and the list drives the lifecycle. This mirrors `view`: both are
pure functions of the model.

The pad already follows this shape. Here is the current `subscribe`:

```python
def subscribe(self, model: Model) -> list[Subscription]:
    subs: list[Subscription] = [Subscription.on_key_press()]
    if model.autosave:
        subs.append(Subscription.every(1500, "autosave"))
    return subs
```

Two subscriptions. One is always present (global key listener). The
other flips on and off with `model.autosave`.

## Timer subscriptions

`Subscription.every(interval_ms, tag)` fires a `TimerTick` event on a
recurring schedule. The `tag` argument is a string that identifies the
timer in the delivered event.

```python
from plushie.events import TimerTick

case TimerTick(tag="autosave"):
    return _save(model) if model.dirty else model
```

The interval is in milliseconds. The runtime arms a `threading.Timer`
and re-arms it after each tick. If the interval changes between cycles
(for example from `every(1000, "tick")` to `every(500, "tick")`), the
old timer is cancelled and a new one starts. You do not handle
cancellation.

Multiple timers coexist when they carry different tags or intervals.
A timer's identity is `("every", interval_ms, tag)`.

## Auto-save in the pad

The pad already wires auto-save end to end. The model carries two
booleans, `autosave` and `dirty`. `dirty` flips to `True` when the
editor buffer diverges from the last saved source, and back to `False`
when the save lands:

```python
case Input(id="editor", value=source):
    return replace(
        model,
        editor_source=source,
        dirty=source != model.last_saved_source,
    )

case Click(id="autosave"):
    return replace(model, autosave=not model.autosave)

case TimerTick(tag="autosave"):
    if model.autosave and model.dirty:
        return _save(model)
    return model
```

The subscription list activates the timer only while the user opted
in:

```python
def subscribe(self, model: Model) -> list[Subscription]:
    subs: list[Subscription] = [Subscription.on_key_press()]
    if model.autosave:
        subs.append(Subscription.every(1500, "autosave"))
    return subs
```

The guard inside the tick handler is belt-and-braces: the timer only
exists when `autosave` is true, and `_save` clears `dirty`. The double
check costs nothing and documents intent.

## Global keyboard shortcuts

`Subscription.on_key_press()` delivers a `KeyEvent` to `update` for
every key press, regardless of which widget has focus. `KeyEvent`
carries `type` (`"press"` or `"release"`), `key` (a name like
`"Escape"` or a single character like `"s"`), and `modifiers`, a
`KeyModifiers` record with `ctrl`, `shift`, `alt`, `logo`, and
`command` flags.

The pad already handles Cmd+S:

```python
case KeyEvent(type="press", key="s", modifiers=mods) if mods.command:
    return _save(model)
```

`command` is platform-aware: Ctrl on Linux and Windows, Cmd on macOS.
Matching on `mods.command` gives cross-platform shortcuts without
per-OS branches.

Let us extend the vocabulary. Cmd+N focuses the new experiment input
(the input does not exist in the current toolbar, but the shortcut is
the same shape once it does). Cmd+Shift+P opens a command palette
stub. Escape clears the preview error display.

```python
from plushie import Command

case KeyEvent(type="press", key="n", modifiers=mods) if mods.command:
    return model, Command.focus("new-name")

case KeyEvent(
    type="press",
    key="p",
    modifiers=mods,
) if mods.command and mods.shift:
    return replace(model, palette_open=True)

case KeyEvent(type="press", key="Escape"):
    return replace(model, preview_error=None, palette_open=False)
```

Two patterns to notice. First, `Command.focus` pairs naturally with a
key shortcut: the subscription delivers the key event, `update`
returns a command, the runtime tells the renderer to move focus. The
renderer is the source of truth for focus; the model does not track
it. Second, guards distinguish Cmd+P from Cmd+Shift+P. Without the
guard, the plain-Cmd case would swallow the shift variant.

`Subscription.on_key_release()` exists if you need key-up events.
`Subscription.on_modifiers_changed()` delivers a `ModifiersChanged`
event whenever a modifier's held state flips, without requiring
another key to be pressed. Useful for UIs that show alternate labels
while Shift is held.

## Pointer subscriptions

Three constructors cover pointer input that is not tied to a specific
widget:

```python
Subscription.on_pointer_move(max_rate=60)
Subscription.on_pointer_button()
Subscription.on_pointer_scroll()
```

They deliver the unified pointer event classes: `Move`, `Enter`, and
`Exit` for motion; `Press` and `Release` for buttons; `Scroll` for
wheel and trackpad scroll. The `id` on the delivered event is the
window id, and `scope` is the empty tuple, which separates these
global events from widget-scoped variants emitted by `pointer_area`.

Pointer motion fires fast. `max_rate=` tells the renderer to coalesce
events and deliver at most that many per second. A rate of zero means
"track internally but do not emit", useful when another subscription
needs capture to stay live without paying the event cost.

```python
Subscription.on_pointer_move(max_rate=30)
Subscription.on_pointer_scroll(max_rate=60)
```

For pointer handling inside a specific widget subtree, prefer the
`pointer_area` widget. Reach for these global subscriptions when the
behaviour is window-wide: custom gesture handlers, drag-to-resize panes
outside the widget tree, cursor-following overlays.

## Window events

Window lifecycle events flow through `WindowEvent`. A single class
covers the family; match on `type` to pick a variant.

```python
from plushie.events import WindowEvent

case WindowEvent(type="resized", width=w, height=h):
    return replace(model, viewport=(w, h))

case WindowEvent(type="focused", window_id=wid):
    return replace(model, focused_window=wid)

case WindowEvent(type="unfocused"):
    return replace(model, focused_window=None)

case WindowEvent(type="close_requested"):
    return replace(model, confirm_quit=True)
```

The constructors split the family along common lines:
`on_window_resize`, `on_window_focus`, `on_window_unfocus`,
`on_window_close`, `on_window_move`, `on_window_open`, and
`on_window_event` as a superset that delivers all of them. Subscribe
to the superset or to specific variants, not both: overlapping
subscriptions deliver matching events twice.

Tracking focus lets the pad pause auto-save while the window is in the
background. Background saves are rarely what the user wants while
their attention is elsewhere, and skipping them avoids disk churn:

```python
@dataclass(frozen=True, slots=True)
class Model:
    autosave: bool = False
    dirty: bool = False
    window_focused: bool = True


def subscribe(self, model: Model) -> list[Subscription]:
    subs: list[Subscription] = [
        Subscription.on_key_press(),
        Subscription.on_window_focus(),
        Subscription.on_window_unfocus(),
    ]
    if model.autosave and model.window_focused:
        subs.append(Subscription.every(1500, "autosave"))
    return subs
```

When focus leaves, the timer disappears from the list on the next
cycle and the runtime stops it. When focus returns, it starts again.

## Theme changes

`Subscription.on_theme_change()` delivers a `ThemeChanged` event when
the operating system's light/dark preference flips. Pair it with
`theme="system"` on the window to follow the OS setting live:

```python
case ThemeChanged(theme=new_theme):
    return replace(model, theme_hint=new_theme)
```

Without the subscription, the renderer still paints with the current
system theme on window open. Subscribe when the model itself needs to
react, for example to pick a chart palette that depends on dark mode.

## Subscription diffing lifecycle

After every `update` cycle, the runtime calls `subscribe`, keys each
spec, and compares the sorted key set against the previous cycle.

Keys are structured:

- Timer: `("every", interval_ms, tag)`
- Renderer: `(kind, window_id)`

If the key set is unchanged, the runtime checks only whether any
`max_rate` values shifted on existing specs, and returns. Returning
the same list every cycle is essentially free.

When the key set differs, set operations identify added and removed
keys. Added timers start. Added renderer subscriptions send a
subscribe message over the wire. Removed entries cancel timers or
send unsubscribe messages. A changed `max_rate` re-sends the
subscribe message with the new rate.

The consequence: you do not memoise the list or worry that returning
a fresh list each cycle will churn timers. Identical keys stay alive.

## Window-scoped subscriptions

In multi-window apps, attach subscriptions to a single window by
passing `window=` or by wrapping a list with `Subscription.for_window`:

```python
Subscription.on_key_press(window="editor")

Subscription.for_window("settings", [
    Subscription.on_key_press(),
    Subscription.on_pointer_move(max_rate=60),
])
```

Without scoping, subscriptions receive events from every window the
app has open. With scoping, only the named window delivers events. Use
scoping when a shortcut should only work in a specific panel, or when
pointer tracking should stop at a window boundary.

## `send_after` vs `every`

Two ways to get a future event. They are not interchangeable.

`Subscription.every(interval_ms, tag)` is declarative. While the
subscription is in the list, it fires on an interval. Stop it by
removing it from the next list. Use this for anything that repeats:
clocks, polling, auto-save, animation heartbeats (though prefer
`on_animation_frame` for vsync-paced work).

`Command.send_after(delay_ms, event)` is imperative. It schedules one
event to arrive after a delay and then it is done. Use this for one-off
follow-ups: dismissing a toast after three seconds, retrying a failed
request, delaying a focus change until after a render.

```python
Command.send_after(3000, DismissToast(toast_id))
```

A toast could also be built with a timer keyed per toast id, but the
one-shot semantics of `send_after` match the intent more directly. The
Commands reference has more detail in the
[Commands guide](09-commands.md).

## What's next

Next we move from ambient event sources to explicit platform
integration: file dialogs, clipboard, notifications, and the effect
round-trip. That is [Async and Effects](11-async-and-effects.md).
