# App class

`plushie.App` is the only base class an app developer subclasses. It follows
the Elm architecture: model, update, view.

## Callbacks

```python
from plushie import App
from plushie.commands import Command
from plushie.subscriptions import Subscription

class MyApp(App[M]):
    # Required:
    def init(self) -> M | tuple[M, Command]: ...
    def update(self, model: M, event: object) -> M | tuple[M, Command]: ...
    def view(self, model: M) -> dict[str, Any]: ...

    # Optional:
    def subscribe(self, model: M) -> list[Subscription]: ...
    def handle_renderer_exit(self, model: M, reason: object) -> M: ...
    def window_config(self, model: M) -> dict[str, Any]: ...
    def settings(self) -> dict[str, Any]: ...
```

### init

Returns the initial model, optionally with commands. Called once when the
runtime starts.

```python
def init(self) -> Model:
    return Model(
        todos=(),
        input_value="",
        filter="all",
    )

# Or with a command:
def init(self) -> tuple[Model, Command]:
    model = Model(todos=(), loading=True)
    return model, Command.task(load_todos_from_disk, "todos_loaded")
```

The model can be any type, but frozen dataclasses work best. The runtime
does not inspect or modify the model -- it is fully owned by the app.

### update

Receives the current model and an event, returns the next model --
optionally with commands.

```python
from plushie.events import Click, Input, Submit
from plushie.commands import Command

def update(self, model: Model, event: object) -> Model | tuple[Model, Command]:
    match event:
        case Click(id="add_todo"):
            todo = Todo(id=next_id(), text=model.input_value)
            return replace(model, todos=(*model.todos, todo), input_value="")

        case Input(id="todo_field", value=v):
            return replace(model, input_value=v)

        # Returning commands:
        case Submit(id="todo_field", value=v) if v.strip():
            todo = Todo(id=next_id(), text=v.strip())
            new_model = replace(model, todos=(*model.todos, todo), input_value="")
            return new_model, Command.focus("todo_field")

        case _:
            return model
```

Return a bare model when no side effects are needed. Return
`(model, command)` when you need async work, widget operations, window
management, or timers. See [commands.md](commands.md) for the full
command API.

Events are frozen dataclasses under `plushie.events`. Common types:

- `Click(id=id)` -- button press
- `Input(id=id, value=val)` -- text input change
- `Select(id=id, value=val)` -- selection change
- `Toggle(id=id, value=val)` -- checkbox/toggler change
- `Submit(id=id, value=val)` -- form field submission
- `KeyPress(key=key, modifiers=mods)` -- keyboard event (via subscription)
- `KeyRelease(key=key, modifiers=mods)` -- keyboard release (via subscription)
- `WindowCloseRequested(window_id=id)` -- window close requested
- `WindowResized(window_id=id, width=w, height=h)` -- window resized
- `CanvasPress(id=id, x=x, y=y, button=btn)` -- canvas interaction
- `SensorResize(id=id, width=w, height=h)` -- sensor size change
- `PaneClicked(id=id, pane=pane)` -- pane grid click

### view

Receives the current model, returns a UI tree.

```python
from plushie import ui

def view(self, model: Model) -> dict[str, Any]:
    return ui.window(
        "main",
        ui.column(
            ui.row(
                ui.text_input("todo_field", model.input_value,
                              placeholder="What needs doing?"),
                ui.button("add_todo", "Add"),
                spacing=8,
            ),
            *(
                ui.row(
                    ui.checkbox("toggle", todo.done),
                    ui.text(todo.text),
                    id=todo.id,
                    spacing=8,
                )
                for todo in filtered_todos(model)
            ),
            padding=16,
            spacing=8,
        ),
        title="Todos",
    )
```

The view function is called after every update. It must be a pure function
of the model. The runtime diffs the returned tree against the previous one
and sends only the changes to the renderer.

UI trees are plain dicts. The `plushie.ui` module provides builder
functions that return `{"id": ..., "type": ..., "props": {...},
"children": [...]}` dicts. You can also build dicts directly if preferred.

## Lifecycle

```
plushie.run(MyApp)
  |
  v
init() -> model (or (model, commands))
  |
  v
subscribe(model) -> active subscriptions
  |
  v
view(model) -> initial tree -> send snapshot to renderer
  |
  v
[event from renderer / subscription / command result]
  |
  v
update(model, event) -> model (or (model, commands))
  |
  v
subscribe(model) -> diff subscriptions (start/stop as needed)
  |
  v
view(model) -> next tree -> diff -> send patch to renderer
  |
  v
[repeat from event]
```

### subscribe (optional)

Returns a list of active subscriptions based on the current model. Called
after every `update`. The runtime diffs the list and starts/stops
subscriptions automatically.

```python
from plushie.subscriptions import Subscription

def subscribe(self, model: Model) -> list[Subscription]:
    subs = [Subscription.on_key_press("key_event")]

    if model.auto_refresh:
        subs.append(Subscription.every(5000, "refresh"))

    return subs
```

Default: `[]` (no subscriptions). See [commands.md](commands.md) for the
full subscription API.

### handle_renderer_exit (optional)

Called when the renderer process exits unexpectedly. Return the model to
use when the renderer restarts. Default: return model unchanged.

```python
def handle_renderer_exit(self, model: Model, reason: object) -> Model:
    return replace(model, status="renderer_restarting")
```

### window_config (optional)

Called when windows are opened, including at startup and after renderer
restart. Default: empty dict (renderer defaults).

```python
def window_config(self, model: Model) -> dict[str, Any]:
    return {
        "title": "My App",
        "width": 800,
        "height": 600,
        "min_size": {"width": 400, "height": 300},
        "resizable": True,
        "theme": "dark",
    }
```

### settings (optional)

Called once at startup to provide application-level settings to the
renderer. Returns a dict.

```python
def settings(self) -> dict[str, Any]:
    return {
        "default_font": {"family": "monospace"},
        "default_text_size": 16,
        "antialiasing": True,
        "fonts": ["assets/fonts/Inter.ttf"],
    }
```

Supported keys:

- `default_font` -- a font specification dict (same format as font props)
- `default_text_size` -- a number (pixels)
- `antialiasing` -- boolean
- `fonts` -- list of font file paths to load
- `vsync` -- boolean (default `True`). Controls vertical sync.
- `scale_factor` -- number (default `1.0`). Global UI scale factor applied
  to all windows.

To follow the OS light/dark preference automatically, set the window
`theme` prop to `"system"`. The renderer detects the current OS theme
and applies the matching built-in light or dark theme.

Default: `{}` (renderer uses its own defaults).

## Starting the runtime

```python
import plushie

# Blocking (main thread):
plushie.run(MyApp)
plushie.run(MyApp, binary_path="/path/to/plushie")

# Background thread:
handle = plushie.start(MyApp)
handle.wait()       # block until exit
handle.stop()       # signal shutdown
handle.inject(evt)  # send a synthetic event

# Decorator-based app:
app = plushie.create_app("MyApp")

@app.init
def init():
    return {"count": 0}

@app.update
def update(model, event):
    return model

@app.view
def view(model):
    return ui.window("main", ui.text("Hello"))

plushie.run(app)
```

## Testing

Apps can be tested without a renderer:

```python
from plushie.events import Input, Click

def test_adding_a_todo():
    app = TodoApp()
    model = app.init()
    model = app.update(model, Input(id="todo_field", value="Buy milk"))
    model = app.update(model, Click(id="add_todo"))

    assert len(model.todos) == 1
    assert model.todos[0].text == "Buy milk"
    assert model.input_value == ""

def test_view_renders_todo_list():
    model = Model(todos=(Todo(id="1", text="Buy milk"),), input_value="", filter="all")
    app = TodoApp()
    tree = app.view(model)
    # tree is a plain dict -- inspect it directly
```

Since `update` is a pure function and `view` returns plain dicts, no
special test infrastructure is needed. The renderer is not involved.

## Multi-window

Plushie supports multiple windows driven declaratively from `view()`.
Windows are nodes in the tree -- if a window node is present, the window
is open; if it disappears, the window closes.

### Returning multiple windows

`view()` returns a list of window nodes (or a single window node for
single-window apps):

```python
def view(self, model: Model) -> list[dict[str, Any]]:
    windows = [
        ui.window("main", main_content(model), title="My App"),
    ]

    if model.inspector_open:
        windows.append(
            ui.window(
                "inspector",
                inspector_panel(model),
                title="Inspector",
                size=(400, 600),
            )
        )

    return windows
```

Single-window apps can return a single window node directly (no list
needed). The runtime normalizes both forms internally.

### Window identity

Each window node has an `id` (like all nodes). The renderer uses this ID
to track which OS window corresponds to which tree node:

- **New ID appears** -- renderer opens a new OS window.
- **Existing ID present** -- renderer updates that window's content.
- **ID disappears** -- renderer closes that OS window.

Window IDs must be stable strings. Do not generate random IDs per render
or the renderer will close and reopen the window on every update.

### Window properties

```python
ui.window(
    "main",
    content(model),
    title="My App",
    size=(800, 600),
    min_size=(400, 300),
    max_size=(1920, 1080),
    position=(100, 100),
    resizable=True,
    closeable=True,
    minimizable=True,
    decorations=True,
    transparent=False,
    visible=True,
    theme="dark",          # or "system" to follow OS preference
    level="normal",        # "normal" | "always_on_top" | "always_on_bottom"
    scale_factor=1.5,      # per-window UI scale (overrides global setting)
)
```

Properties are set when the window first appears. To change properties
after creation, use window commands:

```python
def update(self, model: Model, event: object) -> tuple[Model, Command]:
    match event:
        case Click(id="go_fullscreen"):
            return model, Command.set_window_mode("main", "fullscreen")
```

### Window events

Window events include the window ID so your app knows which window they
came from:

```python
from plushie.events import WindowCloseRequested, WindowResized, WindowFocused

def update(self, model: Model, event: object) -> Model | tuple[Model, Command]:
    match event:
        case WindowCloseRequested(window_id="inspector"):
            return replace(model, inspector_open=False)

        case WindowCloseRequested(window_id="main"):
            if model.unsaved_changes:
                return replace(model, confirm_exit=True)
            return model, Command.close_window("main")

        case WindowResized(window_id="main", width=w, height=h):
            return replace(model, window_size=(w, h))

        case WindowFocused(window_id=wid):
            return replace(model, active_window=wid)
```

### Window close behaviour

By default, when the user clicks the close button on a window, the
renderer sends a `WindowCloseRequested(window_id=...)` event instead of
closing immediately. Your app decides what to do:

```python
# Let it close (remove it from view):
case WindowCloseRequested(window_id="settings"):
    return replace(model, settings_open=False)

# Block the close:
case WindowCloseRequested(window_id="main"):
    return replace(model, show_save_dialog=True)
```

If `WindowCloseRequested` is not handled (falls through to the catch-all),
the window stays open. This prevents accidental closes. To close a window
programmatically, remove it from the tree (return `view()` without it) or
use `Command.close_window(id)`.

### Opening windows declaratively

Windows are opened by adding window nodes to the tree returned by
`view()`. There is no `open_window` command. To open a new window, set a
flag in your model and include the window node conditionally:

```python
def update(self, model: Model, event: object) -> Model:
    match event:
        case Click(id="open_settings"):
            return replace(model, settings_open=True)

def view(self, model: Model) -> list[dict[str, Any]]:
    windows = [
        ui.window("main", main_content(model), title="My App"),
    ]

    if model.settings_open:
        windows.append(
            ui.window(
                "settings",
                settings_panel(model),
                title="Settings",
                size=(500, 400),
            )
        )

    return windows
```

### Primary window

The first window in the list returned by `view()` is the primary window.
When the primary window is closed, the runtime exits (unless
`handle_renderer_exit` is overridden to prevent it).

Secondary windows can be opened and closed freely without affecting the
runtime lifecycle.

### Focus and active window

The renderer tracks which window has OS focus. Window focus/unfocus events
are delivered as:

```python
WindowFocused(window_id=window_id)
WindowUnfocused(window_id=window_id)
```

The app can use these to adjust behaviour (e.g., pause animations in
unfocused windows, track the active window for keyboard shortcuts).

### Example: dialog window

```python
from plushie.events import Click

def view(self, model: Model) -> list[dict[str, Any]] | dict[str, Any]:
    main = ui.window("main", main_content(model), title="App")

    if model.confirm_dialog:
        dialog = ui.window(
            "confirm",
            ui.column(
                ui.text("prompt", "Are you sure?"),
                ui.row(
                    ui.button("confirm_yes", "Yes"),
                    ui.button("confirm_no", "No"),
                    spacing=8,
                ),
                padding=16,
                spacing=12,
            ),
            title="Confirm",
            size=(300, 150),
            resizable=False,
            level="always_on_top",
        )
        return [main, dialog]

    return main
```

## How props reach the renderer

Values returned by `view()` go through several transformation stages
before reaching the wire. Understanding this pipeline helps when
debugging unexpected behaviour or writing custom extensions.

1. **Widget builders** (`plushie.ui` functions) return plain dicts with
   raw Python values -- strings, ints, tuples, dicts. No encoding
   happens here.

2. **Tree normalization** walks the tree and converts Python-native values
   into wire-compatible forms. Tuples become lists, enum strings are
   validated, and scoped IDs are prefixed at this stage.

3. **Protocol encoding** serializes the normalized tree with JSON or
   MessagePack to produce wire bytes.

Each stage has a single responsibility. Widget builders don't worry about
wire encoding, normalization doesn't worry about serialization format, and
the protocol layer doesn't know about widget types.

## Renderer limits

The renderer enforces hard limits on various resources. Exceeding them
results in rejection, truncation, or clamping (depending on the resource).
Design your app to stay within these bounds.

| Resource | Limit | Behavior when exceeded |
|---|---|---|
| Font data (`load_font`) | 16 MiB decoded | Rejected with warning |
| Runtime font loads | 256 per process | Rejected with warning |
| Image handles | 4096 | Error response |
| Total image bytes | 1 GiB | Error response |
| Markdown content | 1 MiB | Truncated at UTF-8 boundary with warning |
| Text editor content | 10 MiB | Truncated at UTF-8 boundary with warning |
| Window size | 1..16384 px | Clamped with warning |
| Window position | -32768..32768 | Clamped with warning |
| Tree depth | 256 levels | Rendering/caching stops descending |

Image and font limits are per-process and survive Reset. Content limits
truncate at a UTF-8 character boundary.
