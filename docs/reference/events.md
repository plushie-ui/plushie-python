# Events

All user interactions, system responses, and asynchronous results
are delivered to your `App.update` method as frozen dataclasses from
`plushie.events`. Each wire event family maps to its own class with
precisely typed fields, so `match` arms bind directly to the fields
you care about.

For a gentler introduction, see the [Events guide](../guides/05-events.md).

## Event dataclasses

There is no single `WidgetEvent` struct. Instead, every event family
is its own class:

```python
from dataclasses import replace
from plushie.events import Click, Input, KeyEvent

def update(self, model, event):
    match event:
        case Click(id="save"):
            return save(model)
        case Input(id="search", value=text):
            return replace(model, query=text)
        case KeyEvent(type="press", key="Escape"):
            return close_dialog(model)
        case _:
            return model
```

Every widget event dataclass carries `id`, `window_id`, and `scope`
(a tuple of ancestor container IDs, nearest first). Widget event
classes that carry a payload expose it as typed fields
(`value`, `x`, `y`, `delta_x`, etc.) rather than a generic
`value: Any` field.

`plushie.events.Event` is a union type over every event class the
runtime can produce. Use it for signature annotations; prefer class
patterns in `update`.

## Event taxonomy

| Category | Classes | Source |
|---|---|---|
| Widget interaction | `Click`, `Input`, `Submit`, `Toggle`, `Select`, `Slide`, `SlideRelease`, `Scrolled`, `Paste`, `Sort`, `Open`, `Close`, `OptionHovered`, `KeyBinding`, `LinkClicked`, `Focused`, `Blurred`, `Drag`, `DragEnd`, `Enter`, `Exit`, `RawEvent` | Renderer (widget callbacks) |
| Pointer (unified) | `Press`, `Release`, `Move`, `Scroll`, `DoubleClick`, `Resize` | Renderer (pointer_area, canvas, sensor) |
| Pane grid | `PaneResized`, `PaneDragged`, `PaneClicked`, `PaneFocusCycle` | Renderer (pane_grid) |
| Keyboard | `KeyEvent`, `ModifiersChanged` | Subscription (key press / release) |
| IME | `ImeEvent` | Subscription (input method editor) |
| Window lifecycle | `WindowEvent` | Renderer (open, close, resize, etc.) |
| System / query | `AnimationFrame`, `ThemeChanged`, `AllWindowsClosed`, `SystemInfo`, `SystemTheme`, `ImageList`, `FocusedWidget`, `TreeHash`, `TransitionComplete`, `Announce` | Renderer |
| Diagnostic | `Diagnostic`, `DiagnosticMessage`, `DuplicateNodeIds`, `CommandError`, `RendererError`, `RecoveryFailed` | Renderer |
| Effect result | `EffectResult` wrapping one of `FileOpened`, `FilesOpened`, `FileSaved`, `DirectorySelected`, `DirectoriesSelected`, `ClipboardText`, `ClipboardHtml`, `ClipboardWritten`, `ClipboardCleared`, `NotificationShown`, `EffectCancelled`, `EffectTimeout`, `EffectError`, `EffectUnsupported`, `RendererRestarted` | Renderer (dialogs, clipboard, notifications) |
| Async | `AsyncResult`, `StreamChunk`, `TimerTick` | Runtime (generated Python-side) |
| Session | `SessionError`, `SessionClosed` | Multiplexed renderer (pool mode) |
| Effect stubs | `EffectStubAck` | Renderer (test mode) |

## Standard widget events

| Class | Payload | Description |
|---|---|---|
| `Click` | | Button pressed |
| `Input` | `value: str` | Text input changed |
| `Submit` | `value: str` | Text input submitted (Enter) |
| `Toggle` | `value: bool` | Toggler / checkbox toggled |
| `Select` | `value: str` | Pick list / combo box / radio selection |
| `Slide` | `value: float` | Slider moved |
| `SlideRelease` | `value: float` | Slider released at final value |
| `Paste` | `value: str` | Paste action on a text input |
| `Open` | | Expandable opened |
| `Close` | | Expandable closed |
| `OptionHovered` | `value: str` | Pick list option hovered |
| `KeyBinding` | `value: str` | Key binding activated |
| `Sort` | `value: str` | Table column sort requested (column key) |
| `Scrolled` | `data: ScrollData` | Scrollable viewport offset changed |
| `TransitionComplete` | `tag: str \| None`, `prop: str \| None` | Renderer-side animation finished (requires `on_complete=tag`) |
| `LinkClicked` | `link: str` | Hyperlink in rich_text or markdown was activated |

### ScrollData

The `Scrolled` event's `data` field is a `plushie.events.ScrollData`
dataclass:

| Field | Type | Description |
|---|---|---|
| `absolute_x` | float | Horizontal scroll offset from content origin |
| `absolute_y` | float | Vertical scroll offset from content origin |
| `relative_x` | float | Fractional position (0.0 start, 1.0 end) |
| `relative_y` | float | Fractional position (0.0 start, 1.0 end) |
| `bounds_width` | float | Visible viewport width |
| `bounds_height` | float | Visible viewport height |
| `content_width` | float | Total scrollable content width |
| `content_height` | float | Total scrollable content height |

### Status events

Every built-in widget emits internal `WidgetStatus` events when its
interaction status changes. The runtime absorbs these to track focus
and hover internally, and dispatches `Focused` / `Blurred` events to
`update` on focus transitions. Your code never receives
`WidgetStatus` directly.

Status names tracked internally: `"active"`, `"hovered"`,
`"focused"`, `"pressed"`, `"dragged"`, `"disabled"`, `"opened"`.

## Unified pointer events

Pointer events use a device-agnostic model. The `pointer` field
identifies the input device (`"mouse"`, `"touch"`, `"pen"`) and
`button` identifies which button was involved (mouse / pen only).

| Class | Fields |
|---|---|
| `Press` | `x`, `y`, `button`, `pointer`, `modifiers`, `finger`, `captured` |
| `Release` | `x`, `y`, `button`, `pointer`, `modifiers`, `finger`, `lost`, `captured` |
| `Move` | `x`, `y`, `pointer`, `modifiers`, `finger`, `captured` |
| `Scroll` | `x`, `y`, `delta_x`, `delta_y`, `unit`, `pointer`, `modifiers`, `captured` |
| `DoubleClick` | `x`, `y`, `pointer`, `modifiers` |
| `Resize` | `width`, `height` |

- `button` is one of `"left"`, `"right"`, `"middle"`, `"back"`,
  `"forward"`, or an arbitrary string for non-standard buttons.
- `pointer` is one of `"mouse"`, `"touch"`, `"pen"`.
- `finger` is the touch finger identifier, `None` for mouse and pen.
- `unit` (on `Scroll`) is `"line"` for wheel notches or `"pixel"`
  for trackpad smooth scrolling.
- `modifiers` is a `plushie.types.KeyModifiers` instance.

`Scroll` is pointer input (wheel delta at a coordinate). `Scrolled`
(in the standard widget events table above) is container state: a
scrollable widget reporting its viewport offset changed.

## Generic element events

Focus, drag, and enter / exit events emitted by interactive elements
(canvas groups, pointer_area children, widgets).

| Class | Fields |
|---|---|
| `Focused` | |
| `Blurred` | |
| `Drag` | `x`, `y`, `delta_x`, `delta_y`, `button` |
| `DragEnd` | `x`, `y`, `button` |
| `Enter` | `x`, `y`, `captured` |
| `Exit` | `x`, `y`, `captured` |

Canvas element clicks are ordinary `Click` events with the canvas
ID in `scope`. See the [Canvas reference](canvas.md) for element
identification.

## Pane grid events

| Class | Fields |
|---|---|
| `PaneResized` | `split`, `ratio` |
| `PaneDragged` | `pane`, `target`, `action`, `region`, `edge` |
| `PaneClicked` | `pane` |
| `PaneFocusCycle` | `pane` |

`action` on `PaneDragged` is `"picked"`, `"dropped"`, or
`"canceled"`.

## KeyEvent and ModifiersChanged

Keyboard events from subscriptions and widget-scoped key events.

```python
@dataclass(frozen=True, slots=True)
class KeyEvent:
    type: Literal["press", "release"]
    key: str
    modified_key: str
    modifiers: KeyModifiers
    physical_key: str | None = None
    location: KeyLocation = "standard"
    text: str | None = None
    repeat: bool = False
    captured: bool = False
    window_id: str = ""
    id: str | None = None
    scope: tuple[str, ...] = ()
```

| Field | Description |
|---|---|
| `type` | `"press"` or `"release"` |
| `key` | Logical key name (`"a"`, `"Enter"`, `"ArrowUp"`) |
| `modified_key` | Key after modifier transforms (Shift+a produces `"A"`) |
| `modifiers` | `KeyModifiers` instance |
| `physical_key` | Physical key code (`"KeyA"`) or `None` |
| `location` | `"standard"`, `"left"`, `"right"`, or `"numpad"` |
| `text` | Text produced by the key press, or `None` |
| `repeat` | Auto-repeat event (always `False` for release) |
| `captured` | Whether a widget consumed this event |
| `window_id` | Source window, or `""` when absent |
| `id` / `scope` | Populated for widget-scoped events, `None` / `()` for global subscriptions |

`ModifiersChanged` fires when the set of held modifier keys changes
without a key event:

| Field | Description |
|---|---|
| `modifiers` | New `KeyModifiers` state |
| `captured` | Whether a widget consumed this event |
| `window_id` | Source window, or `""` when absent |

### KeyModifiers

`plushie.types.KeyModifiers` is a frozen dataclass with boolean
fields:

| Field | Purpose |
|---|---|
| `ctrl` | Control key |
| `shift` | Shift key |
| `alt` | Alt key (Option on macOS) |
| `logo` | Logo / Super key (Windows key, Command on macOS) |
| `command` | Platform-aware: Ctrl on Linux / Windows, Cmd on macOS |

`command` is the one to use for cross-platform shortcuts. Match on
`command=True` and it works on all platforms.

## ImeEvent

Input Method Editor lifecycle steps. Typical order:
`"opened"` -> `"preedit"` (repeated) -> `"commit"` -> `"closed"`.

| Field | Type | Description |
|---|---|---|
| `type` | `"opened"` / `"preedit"` / `"commit"` / `"closed"` | IME phase |
| `text` | `str \| None` | Composition or commit text |
| `cursor` | `tuple[int, int] \| None` | Byte offsets in preedit |
| `captured` | bool | Subscription captured |
| `window_id` | str | Source window, or `""` when absent |

## WindowEvent

Window lifecycle events from the renderer.

| Field | Type | Notes |
|---|---|---|
| `type` | literal | See types below |
| `window_id` | str | Window identifier |
| `width`, `height` | `float \| None` | For `"opened"` and `"resized"` |
| `x`, `y` | `float \| None` | For `"moved"` |
| `scale_factor` | `float \| None` | For `"opened"` and `"rescaled"` |
| `path` | `str \| None` | For `"file_hovered"` and `"file_dropped"` |
| `position_x`, `position_y` | `float \| None` | Initial screen position on `"opened"` |

Types: `"opened"`, `"closed"`, `"close_requested"`, `"resized"`,
`"moved"`, `"focused"`, `"unfocused"`, `"rescaled"`,
`"file_hovered"`, `"file_dropped"`, `"files_hovered_left"`.

## System events

Query responses and runtime signals from the renderer.

| Class | Fields |
|---|---|
| `AnimationFrame` | `timestamp` |
| `ThemeChanged` | `theme` (`"light"` or `"dark"`) |
| `AllWindowsClosed` | |
| `SystemInfo` | `tag`, `value` (dict) |
| `SystemTheme` | `tag`, `theme` |
| `ImageList` | `tag`, `handles` |
| `FocusedWidget` | `tag`, `widget_id` |
| `TreeHash` | `tag`, `hash` |
| `TransitionComplete` | `id`, `tag`, `prop`, `window_id`, `scope` |
| `Announce` | `text` |

`AnimationFrame` only fires when `Subscription.on_animation_frame()`
is active.

## Diagnostic and error events

| Class | Fields |
|---|---|
| `Diagnostic` | `level`, `element_id`, `code`, `message`, `id`, `window_id` |
| `DiagnosticMessage` | Typed subclasses from `plushie.diagnostics` |
| `DuplicateNodeIds` | `details` |
| `CommandError` | `reason`, `id`, `family`, `widget`, `message` |
| `RendererError` | `id`, `data` |
| `RecoveryFailed` | `kind`, `error`, `renderer_exit` |

`DiagnosticMessage` is a typed facade over `Diagnostic` with
case classes per validation code. See `plushie.diagnostics` for
the full catalog.

`RecoveryFailed` is dispatched when `handle_renderer_exit` raises.
It carries a `RendererExitInfo` (with `type`, `message`, `details`)
describing why the renderer exited in the first place.

## EffectResult and its payloads

`EffectResult` is the single event class for platform effect
responses. Its `result` field is a typed payload dataclass:

| Payload | Emitted by | Fields |
|---|---|---|
| `FileOpened` | `Effect.file_open` | `path` |
| `FilesOpened` | `Effect.file_open_multiple` | `paths` |
| `FileSaved` | `Effect.file_save` | `path` |
| `DirectorySelected` | `Effect.directory_select` | `path` |
| `DirectoriesSelected` | `Effect.directory_select_multiple` | `paths` |
| `ClipboardText` | `Effect.clipboard_read` / `clipboard_read_primary` | `text` |
| `ClipboardHtml` | `Effect.clipboard_read_html` | `html`, `alt_text` |
| `ClipboardWritten` | `Effect.clipboard_write*` | |
| `ClipboardCleared` | `Effect.clipboard_clear` | |
| `NotificationShown` | `Effect.notification` | |
| `EffectCancelled` | User dismissed dialog | |
| `EffectTimeout` | Effect exceeded its timeout | |
| `EffectError` | Platform error | `message` |
| `EffectUnsupported` | Backend does not support this effect | |
| `RendererRestarted` | Renderer restarted while effect in flight | |

```python
from plushie.events import EffectResult, FileOpened, EffectCancelled

match event:
    case EffectResult(tag="import", result=FileOpened(path=p)):
        return load_file(model, p)
    case EffectResult(tag="import", result=EffectCancelled()):
        return model
```

`EffectCancelled` is a normal outcome (user dismissed a dialog), not
an error.

## Runtime events

Generated Python-side; never arrive on the wire.

| Class | Source | Fields |
|---|---|---|
| `AsyncResult` | `Command.task` completion | `tag`, `value` (result or `Exception`) |
| `StreamChunk` | `Command.stream` emit | `tag`, `value` |
| `TimerTick` | `Subscription.every` fire | `tag`, `timestamp` |

## Session events

Multiplexed (pool) renderer mode only.

| Class | Fields |
|---|---|
| `SessionError` | `session`, `code`, `error` |
| `SessionClosed` | `session`, `reason` |

`code` on `SessionError` is one of `"session_panic"`,
`"max_sessions_reached"`, `"session_channel_closed"`,
`"writer_dead"`, `"font_cap_exceeded"`, `"renderer_panic"`,
`"session_reset_in_progress"`, `"session_backpressure_overflow"`.

## Pattern matching cookbook

### Match by widget ID

```python
match event:
    case Click(id="save"):
        return save(model)
```

### Match by class with payload

```python
match event:
    case Input(id="search", value=text):
        return replace(model, query=text)
    case Toggle(id="dark_mode", value=on):
        return replace(model, dark_mode=on)
    case Slide(id="volume", value=level):
        return replace(model, volume=level)
```

### Match by scope (dynamic lists)

When items are rendered in a named container with a dynamic ID, the
container's ID appears first in the event's `scope`:

```python
match event:
    case Click(id="delete", scope=(item_id, *_)):
        return replace(model, items=model.items - {item_id})
```

### Match key with modifiers

```python
match event:
    case KeyEvent(type="press", key="s", modifiers=m) if m.command:
        return save(model)
    case KeyEvent(type="press", key="Escape"):
        return close_dialog(model)
```

### Match pointer event with device type

```python
match event:
    case Press(id="area", pointer="mouse", button="left"):
        return select(model)
    case Press(id="area", pointer="touch", finger=f):
        return touch_start(model, f)
```

### Match pointer event with modifiers

```python
match event:
    case Press(id="item", modifiers=m) if m.shift:
        return add_to_selection(model)
    case Move(id="canvas", x=x, y=y, modifiers=m) if m.ctrl:
        return pan(model, x, y)
```

### Match custom widget event

Custom widget events are ordinary `Click`, `Input`, etc. instances
scoped by the widget's ID. Structured payloads arrive via
`RawEvent` when the widget declares a family outside the built-in
catalog:

```python
match event:
    case RawEvent(kind="color_picker:change", id="picker", value=v):
        return replace(model, hue=v["hue"])
```

See the [Custom Widgets reference](custom-widgets.md) for how
widget event declarations shape the dispatched events.

### Match async result

```python
match event:
    case AsyncResult(tag="fetch", value=list() as items):
        return replace(model, items=tuple(items), loading=False)
    case AsyncResult(tag="fetch", value=Exception() as exc):
        return replace(model, error=str(exc), loading=False)
```

### Match stream chunk

```python
match event:
    case StreamChunk(tag="download", value={"progress": pct}):
        return replace(model, progress=pct)
```

### Match effect result

```python
match event:
    case EffectResult(tag="open", result=FileOpened(path=p)):
        return load_file(model, p)
    case EffectResult(tag="open", result=EffectCancelled()):
        return model
```

### Match timer tick

```python
match event:
    case TimerTick(tag="tick"):
        return replace(model, ticks=model.ticks + 1)
```

### Match window events

```python
match event:
    case WindowEvent(type="close_requested", window_id=wid):
        return close_window(model, wid)
    case WindowEvent(type="resized", width=w, height=h):
        return replace(model, width=w, height=h)
```

### Reconstruct the full scoped path

`plushie.events.target` joins `id` and `scope` into a
forward-order path string:

```python
from plushie.events import target

event = Click(id="save", scope=("form", "sidebar"), window_id="main")
target(event)  # "sidebar/form/save"
```

### Catch-all

Always include a fall-through case. If `update` returns `None` (no
match arm hit) the runtime logs a warning and keeps the previous
model.

```python
def update(self, model, event):
    match event:
        case Click(id="save"):
            return save(model)
        # ...
        case _:
            return model
```

## Event flow

Events travel through a fixed pipeline before reaching `update`:

1. **Renderer** detects a user interaction and encodes an event
   message.
2. **Reader thread** reads wire frames from the renderer, decodes
   them via `plushie.protocol`, and posts typed event dataclasses
   to a thread-safe queue.
3. **Runtime thread** receives the event. If the event targets a
   widget with a registered `handle_event` callback, the runtime
   walks the scope chain (innermost handler first) before
   delivering to the app. Widget handlers can emit, transform,
   consume, or ignore events.
4. **App** `update` receives the event (unless a widget handler
   consumed it).

### Coalescable events

High-frequency events (`Move`, `Scroll`, `Resize`) are coalescable.
When multiple events of the same class arrive for the same source
before the runtime processes them, only the latest is delivered.
This prevents queue backup during rapid mouse movement or window
resizing. A zero-delay timer flushes coalescable events before the
next non-coalescable event, preserving relative ordering.

### Widget handler interception

Custom widgets with `handle_event` callbacks are registered in a
handler registry derived from the current view tree. When an event
arrives, the runtime checks the scope chain for registered
handlers. Each handler can return:

- `("emit", family, data)` - transform and re-emit as a new event
- `("update_state", new_state)` - update widget state, suppress
  the event
- `"ignored"` - pass through to the next handler
- `"consumed"` - suppress the event entirely

Render-only widgets (no events, no state) are skipped in the
registry and have zero overhead in the event path.

### External injection

`runtime.inject(event)` is thread-safe (uses `queue.put`). Flask
routes, message queue consumers, and background threads can inject
any event dataclass into the app's update cycle.

## See also

- [Events guide](../guides/05-events.md) - pattern-matching walkthrough
- [Subscriptions reference](subscriptions.md) - keyboard, timer, and
  other event sources
- [Scoped IDs reference](scoped-ids.md) - how container scoping
  affects event IDs
- [Commands reference](commands.md) - the commands that produce
  async and effect events
- [Custom Widgets reference](custom-widgets.md) - declaring and
  dispatching widget-specific events
