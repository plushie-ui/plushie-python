# Subscriptions

Subscriptions are declarative event sources. You return a list of
subscription specs from `App.subscribe(model)` and the runtime
handles starting, stopping, and diffing them each cycle.
Subscriptions are a function of the model: when the model changes,
the active subscriptions change with it.

All constructors live on `plushie.subscriptions.Subscription`
(re-exported as `plushie.Subscription`).

## Timer subscriptions

`Subscription.every(interval_ms, tag)` fires on a recurring interval:

```python
from plushie import Subscription
from plushie.events import TimerTick

def subscribe(self, model):
    if model.auto_save and model.dirty:
        return [Subscription.every(1000, "auto_save")]
    return []

def update(self, model, event):
    match event:
        case TimerTick(tag="auto_save"):
            return save(model)
        case _:
            return model
```

Timer subscriptions run on a Python `threading.Timer` inside the
runtime. After each tick, the timer is re-armed for the next
interval. The `tag` you provide is carried on the `TimerTick`
event.

If the interval changes between cycles (e.g. switching from
`every(1000, "tick")` to `every(500, "tick")`), the runtime cancels
the old timer and starts a new one automatically. No manual cleanup
needed.

## Renderer subscriptions

Renderer subscriptions are forwarded to the renderer binary via the
wire protocol. They take no tag argument. Lifecycle management is
keyed by `(kind, window_id)`, so only one subscription of each kind
per window (or globally when unscoped) can be active.

### Keyboard

| Function | Event delivered |
|---|---|
| `on_key_press()` | `KeyEvent(type="press", ...)` |
| `on_key_release()` | `KeyEvent(type="release", ...)` |
| `on_modifiers_changed()` | `ModifiersChanged` |

`KeyEvent` includes `key` (string name for named keys like
`"Escape"`, `"Enter"`, single characters for printable input),
`modifiers` (`KeyModifiers` with boolean `ctrl`, `shift`, `alt`,
`logo`, `command` fields), and `type` (`"press"` or `"release"`).
See the [Events reference](events.md#keyevent-and-modifierschanged)
for the full field list.

The `command` modifier is platform-aware: Ctrl on Linux / Windows,
Cmd on macOS. Match on `command=True` for cross-platform
shortcuts.

### Window lifecycle

| Function | Event delivered | Scope |
|---|---|---|
| `on_window_event()` | `WindowEvent` | All window events |
| `on_window_open()` | `WindowEvent(type="opened")` | Open only |
| `on_window_close()` | `WindowEvent(type="close_requested")` | Close only |
| `on_window_resize()` | `WindowEvent(type="resized")` | Resize only |
| `on_window_focus()` | `WindowEvent(type="focused")` | Focus only |
| `on_window_unfocus()` | `WindowEvent(type="unfocused")` | Unfocus only |
| `on_window_move()` | `WindowEvent(type="moved")` | Move only |

`on_window_event()` is a superset that delivers all window event
types. If you subscribe to both `on_window_event` and a specific
variant (e.g. `on_window_resize`), matching events are delivered
twice. Use one or the other, not both.

### Pointer

| Function | Events delivered |
|---|---|
| `on_pointer_move()` | `Move`, `Enter`, `Exit` |
| `on_pointer_button()` | `Press`, `Release` |
| `on_pointer_scroll()` | `Scroll` |
| `on_pointer_touch()` | `Press`, `Move`, `Release` with `pointer="touch"` |

Pointer subscriptions are global. They deliver the unified pointer
event classes (see the
[Events reference](events.md#unified-pointer-events)) with
`id=window_id` and `scope=()`. For widget-specific pointer handling,
use the `pointer_area` widget instead.

### Other

| Function | Event delivered |
|---|---|
| `on_ime()` | `ImeEvent` |
| `on_theme_change()` | `ThemeChanged` |
| `on_animation_frame()` | `AnimationFrame` |
| `on_file_drop()` | `WindowEvent` (`file_hovered`, `file_dropped`, `files_hovered_left`) |

`on_animation_frame()` delivers vsync ticks for SDK-side animation
via `plushie.animation.Tween`. Renderer-side transitions
(`Transition`, `Spring`, `Sequence`) do not require this
subscription; they run independently in the renderer.

### Catch-all

`on_event()` subscribes to every renderer event: widget, keyboard,
pointer, window, and system. Use it for debugging or logging, not as
a primary event source. It delivers a lot of traffic.

## All subscription constructors

Renderer constructors take keyword-only `max_rate` and `window`
arguments. Timer subscriptions take an interval and a tag:

```python
Subscription.on_key_press()
Subscription.on_key_press(max_rate=30)
Subscription.on_pointer_move(max_rate=60)
Subscription.every(1000, "tick")
```

Renderer subscriptions are keyed by `(kind, window_id)`. Only one
subscription of each kind per window (or globally when unscoped) is
active at a time.

## Rate limiting

`max_rate=` throttles high-frequency renderer events. The renderer
coalesces intermediate events, delivering only the latest state at
each interval:

```python
Subscription.on_pointer_move(max_rate=30)
```

`max_rate` is a keyword argument on every renderer subscription
constructor. It has no effect on timer subscriptions; those control
their frequency via the interval argument.

A rate of `0` means "capture but never emit". The subscription is
active (the renderer tracks the state) but no events are delivered.
Useful when you need capture tracking without event processing.

### Three-level hierarchy

Rate limiting applies at three levels, from most to least specific:

1. **Per-widget** - `event_rate=` prop on individual widgets
2. **Per-subscription** - `max_rate=` on subscription specs
3. **Global** - `default_event_rate` from `App.settings()`

More specific settings override less specific ones. See the
[Configuration reference](configuration.md) for the global setting.

## Window scoping

Scope subscriptions to a specific window in multi-window apps.
Either pass `window=` per subscription, or wrap a list with
`Subscription.for_window`:

```python
Subscription.for_window("settings", [
    Subscription.on_key_press(),
    Subscription.on_pointer_move(max_rate=60),
])
```

Without window scoping, events from any window are delivered. With
scoping, only events from the named window arrive.

## Conditional subscriptions

Because `subscribe` is a function of the model, you activate
subscriptions conditionally:

```python
def subscribe(self, model):
    subs = [Subscription.on_key_press()]
    if model.auto_save and model.dirty:
        subs.append(Subscription.every(1000, "auto_save"))
    return subs
```

When `auto_save` becomes `False` or the dirty flag clears, the
timer disappears from the list. The runtime stops it. When the
conditions are met again, the timer starts. No manual start / stop
logic needed.

**Performance:** returning the same list every cycle is nearly free.
The runtime generates a sorted key set from the list and
short-circuits if it has not changed. Only `max_rate` changes are
checked beyond that. When the list does change, the diff is
efficient: set operations identify added and removed subscriptions.

## Diffing lifecycle

The runtime calls `subscribe` after every update cycle and diffs
the result against active subscriptions:

1. Generate a key for each spec via `Subscription.key`:
   - Timer: `("every", interval_ms, tag)`
   - Renderer: `(kind, window_id)`
2. Sort and compare keys against the previous cycle's key set.
3. **Short-circuit:** if the sorted key set is unchanged, only
   check for `max_rate` changes on existing subscriptions.
4. **New keys:** start timers (`threading.Timer`) or send
   subscribe messages to the renderer.
5. **Removed keys:** cancel timers or send unsubscribe messages.
6. **Changed max_rate:** re-send the subscribe message with the new
   rate.

Subscriptions are idempotent. The same spec list produces no work.
Different lists trigger precise add / remove operations.

## Widget-scoped subscriptions

Custom widgets with a `subscribe` callback get namespaced
subscriptions. Tags are automatically wrapped so the runtime can
route timer events back to the correct widget instance instead of
the app's `update`. The widget sees only the inner tag on the
event.

Multiple instances of the same widget each get independent
subscriptions. See the
[Custom Widgets reference](custom-widgets.md) for details.

## See also

- [Subscriptions guide](../guides/10-subscriptions.md) - keyboard
  shortcuts, timers, and auto-save applied to the pad
- [Events reference](events.md) - the event classes delivered by
  subscriptions
- [Configuration reference](configuration.md) - `default_event_rate`
  and `settings()`
- [Custom Widgets reference](custom-widgets.md) - widget-scoped
  subscriptions
