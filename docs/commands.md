# Commands and subscriptions

Iced has two mechanisms beyond the basic update/view cycle: `Task` (async
commands from update) and `Subscription` (ongoing event sources). Plushie
provides Python equivalents for both.

## Commands

Sometimes `update()` needs to do more than return a new model. It might
need to focus a text input, start an HTTP request, open a new window, or
schedule a delayed event. These are commands.

### Returning commands from update

`update()` can return either a bare model or a `(model, command)` tuple:

<!-- test: test_update_returns_bare_model, test_update_returns_model_command_tuple -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click, AsyncResult

def update(self, model, event):
    match event:
        # No commands -- just return the model:
        case Click(id="simple"):
            return model

        # With commands -- return a tuple:
        case Click(id="save"):
            return replace(model, saving=True), Command.task(
                lambda: save_to_disk(model), "save_result"
            )

        case AsyncResult(tag="save_result", value=result):
            if isinstance(result, Exception):
                return replace(model, error=str(result))
            return replace(model, saved=True)
```

### Available commands

#### Async work

<!-- test: test_command_task -- keep this code block in sync with the test -->
```python
# Run a function in a background thread. Result is delivered as an AsyncResult event.
Command.task(fn, tag)

# The function runs in a thread. When it returns, the runtime delivers:
#   AsyncResult(tag=tag, value=result)
```

<!-- test: test_command_task -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click, AsyncResult

def update(self, model, event):
    match event:
        case Click(id="fetch"):
            cmd = Command.task(
                lambda: requests.get("https://api.example.com/data").json(),
                "data_fetched",
            )
            return replace(model, loading=True), cmd

        case AsyncResult(tag="data_fetched", value=body):
            return replace(model, loading=False, data=body)
```

#### Streaming async work

`Command.stream()` spawns a thread that sends multiple intermediate
results to `update()` over time. The function receives an `emit`
callback; each call to `emit` delivers a `StreamChunk(tag=tag, value=value)`
event through the normal update cycle. The function's final return value
is delivered as `AsyncResult(tag=tag, value=result)`.

<!-- test: test_command_stream -- keep this code block in sync with the test -->
```python
Command.stream(fn, tag)

# fn receives an emit callback: fn(emit) -> result
# Each emit(value) dispatches StreamChunk(tag=tag, value=value) through update().
# The function's final return value dispatches AsyncResult(tag=tag, value=result).
```

<!-- test: test_command_stream -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click, StreamChunk, AsyncResult

def update(self, model, event):
    match event:
        case Click(id="import"):
            def do_import(emit):
                rows = []
                for n, line in enumerate(open("big.csv"), 1):
                    row = parse_row(line)
                    emit(("progress", n))
                    rows.append(row)
                return ("complete", rows)

            return replace(model, importing=True), Command.stream(do_import, "file_import")

        case StreamChunk(tag="file_import", value=("progress", n)):
            return replace(model, rows_imported=n)

        case AsyncResult(tag="file_import", value=("complete", rows)):
            return replace(model, importing=False, data=rows)
```

This is convenience sugar. You can achieve the same thing with a bare
thread and queue -- see [DIY patterns](#diy-patterns) below.

#### Cancelling async work

`Command.cancel()` cancels a running `task` or `stream` command by its
tag. The runtime tracks running threads by tag and terminates the
associated work. If the task has already completed, this is a no-op.

<!-- test: test_command_cancel -- keep this code block in sync with the test -->
```python
Command.cancel(tag)
```

<!-- test: test_command_cancel -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="cancel_import"):
            return replace(model, importing=False), Command.cancel("file_import")
```

#### Done (lift a value)

`Command.done()` wraps an already-resolved value as a command. The runtime
immediately dispatches `mapper(value)` through `update()` without spawning
a thread. Useful for lifting a pure value into the command pipeline.

<!-- test: test_command_done -- keep this code block in sync with the test -->
```python
Command.done(value, mapper)
```

<!-- test: test_command_done -- keep this code block in sync with the test -->
```python
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="reset"):
            return model, Command.done("defaults", lambda v: ("config_loaded", v))
```

#### Exit

`Command.exit()` terminates the application.

<!-- test: test_command_exit -- keep this code block in sync with the test -->
```python
Command.exit()
```

#### Widget operations

##### Focus

<!-- test: test_command_focus, test_command_focus_next, test_command_focus_previous -- keep this code block in sync with the test -->
```python
Command.focus(widget_id)           # Focus a text input
Command.focus_next()               # Focus next focusable widget
Command.focus_previous()           # Focus previous focusable widget
```

Example:

<!-- test: test_command_focus -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="new_todo"):
            return replace(model, input=""), Command.focus("todo_input")
```

##### Text operations

<!-- test: test_command_select_all, test_command_select_range, test_command_move_cursor_to, test_command_move_cursor_to_front, test_command_move_cursor_to_end -- keep this code block in sync with the test -->
```python
Command.select_all(widget_id)                       # Select all text
Command.move_cursor_to_front(widget_id)              # Cursor to start
Command.move_cursor_to_end(widget_id)                # Cursor to end
Command.move_cursor_to(widget_id, position)          # Cursor to char position
Command.select_range(widget_id, start, end)          # Select character range
```

Example:

<!-- test: test_command_select_range -- keep this code block in sync with the test -->
```python
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="select_word"):
            return model, Command.select_range("editor", 5, 10)
```

##### Scroll operations

<!-- test: test_command_scroll_to, test_command_snap_to, test_command_snap_to_end, test_command_scroll_by -- keep this code block in sync with the test -->
```python
Command.scroll_to(widget_id, offset_y)   # Scroll to absolute vertical position
Command.snap_to(widget_id, x, y)         # Snap scroll to absolute offset
Command.snap_to_end(widget_id)           # Snap to end of scrollable content
Command.scroll_by(widget_id, x, y)       # Scroll by relative delta
```

Example:

<!-- test: test_command_snap_to_end -- keep this code block in sync with the test -->
```python
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="scroll_bottom"):
            return model, Command.snap_to_end("chat_log")
```

##### Accessibility

<!-- test: test_command_announce -- keep this code block in sync with the test -->
```python
Command.announce(text)           # Announce text to screen readers
```

##### Font loading

<!-- test: test_command_load_font -- keep this code block in sync with the test -->
```python
Command.load_font(data)          # Load a font at runtime from raw TTF/OTF bytes
```

##### Renderer queries

<!-- test: test_command_tree_hash_query, test_command_find_focused_query, test_command_list_images_query -- keep this code block in sync with the test -->
```python
Command.tree_hash_query(tag)        # SHA-256 hash of the renderer's current tree
Command.find_focused_query(tag)     # Which widget currently has keyboard focus
Command.list_images_query(tag)      # List all registered image handles
```

Results arrive as system events in `update()`.

#### Window management

Windows are opened declaratively by including window nodes in the view tree.
There is no `open_window` command. To open a window, add a `window` node to
the tree returned by `view()`. To close one, remove it or use
`close_window()`.

<!-- test: test_command_close_window, test_command_resize_window, test_command_move_window, test_command_maximize_window, test_command_minimize_window, test_command_set_window_mode, test_command_toggle_maximize, test_command_toggle_decorations, test_command_gain_focus, test_command_set_window_level, test_command_drag_window, test_command_drag_resize_window, test_command_request_user_attention, test_command_screenshot_window, test_command_set_resizable, test_command_set_min_max_size, test_command_mouse_passthrough, test_command_show_system_menu, test_command_set_icon, test_command_set_resize_increments, test_command_allow_automatic_tabbing -- keep this code block in sync with the test -->
```python
Command.close_window(window_id)                            # Close a window
Command.resize_window(window_id, width, height)            # Resize
Command.move_window(window_id, x, y)                       # Move
Command.maximize_window(window_id)                         # Maximize (default: True)
Command.maximize_window(window_id, False)                  # Restore from maximized
Command.minimize_window(window_id)                         # Minimize (default: True)
Command.minimize_window(window_id, False)                  # Restore from minimized
Command.set_window_mode(window_id, mode)                   # "fullscreen", "windowed", etc.
Command.toggle_maximize(window_id)                         # Toggle maximize state
Command.toggle_decorations(window_id)                      # Toggle title bar/borders
Command.gain_focus(window_id)                              # Bring window to front
Command.set_window_level(window_id, level)                 # "normal", "always_on_top", etc.
Command.drag_window(window_id)                             # Initiate OS window drag
Command.drag_resize_window(window_id, direction)           # Initiate OS resize from edge
Command.request_user_attention(window_id, urgency)         # Flash taskbar ("informational", "critical")
Command.screenshot_window(window_id, tag)                  # Capture window pixels
Command.set_resizable(window_id, value)                    # Enable/disable resize
Command.set_min_size(window_id, width, height)             # Set minimum window size
Command.set_max_size(window_id, width, height)             # Set maximum window size
Command.enable_mouse_passthrough(window_id)                # Click-through window
Command.disable_mouse_passthrough(window_id)               # Normal click handling
Command.show_system_menu(window_id)                        # Show OS window menu
Command.set_icon(window_id, rgba_data, width, height)      # Set window icon (raw RGBA)
Command.set_resize_increments(window_id, width, height)    # Set resize step increments
Command.allow_automatic_tabbing(enabled)                   # Enable/disable macOS automatic tab grouping
```

Example:

<!-- test: test_command_set_window_mode, test_command_set_window_level -- keep this code block in sync with the test -->
```python
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="go_fullscreen"):
            return model, Command.set_window_mode("main", "fullscreen")
        case Click(id="pin_on_top"):
            return model, Command.set_window_level("main", "always_on_top")
```

`set_icon()` sends raw RGBA pixel data (base64-encoded for wire transport).
The `rgba_data` must be a `bytes` object of `width * height * 4` bytes.

#### Window queries

Window queries are commands whose results arrive as events in `update()`.
Despite accepting a `tag` parameter, window property queries use the
**effect response** transport -- results arrive as
`EffectResult(request_id=id, ...)` where `id` is the **window_id string**
(the `tag` is currently unused for these queries). System queries use a
separate path where the tag is used.

##### Window property queries

These go through the effect/window_op system. Results arrive in `update()`
as `EffectResult(request_id=window_id, status="ok", result=data)` where
`window_id` is the string ID of the window and `data` varies by query type.

<!-- test: test_command_get_window_size, test_command_get_window_position, test_command_get_mode, test_command_get_scale_factor, test_command_is_maximized, test_command_is_minimized, test_command_raw_id, test_command_monitor_size -- keep this code block in sync with the test -->
```python
Command.get_window_size(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result={"width": w, "height": h})

Command.get_window_position(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result={"x": x, "y": y})
# (None if position is unavailable)

Command.get_mode(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result=mode)
# mode is "windowed", "fullscreen", or "hidden"

Command.get_scale_factor(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result=factor)

Command.is_maximized(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result=boolean)

Command.is_minimized(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result=boolean)

Command.raw_id(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result=platform_id)

Command.monitor_size(window_id, tag)
# Result: EffectResult(request_id=window_id, status="ok", result={"width": w, "height": h})
# (None if monitor cannot be determined)
```

Example:

<!-- test: test_command_get_window_size -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click, EffectResult

def update(self, model, event):
    match event:
        case Click(id="check_size"):
            return model, Command.get_window_size("main", "got_size")

        case EffectResult(request_id="main", status="ok", result={"width": w, "height": h}):
            return replace(model, window_width=w, window_height=h)
```

**Note:** Because the response is keyed by `window_id` rather than `tag`,
issuing multiple different queries against the same window will produce
results that share the same `window_id` key. Distinguish them by the shape
of the `result` dict (e.g. `{"width": _, "height": _}` for size vs.
`{"x": _, "y": _}` for position).

##### System queries

System-level queries use a different transport path. Results arrive as
dedicated event dataclasses where the **tag** (stringified) identifies
the response.

<!-- test: test_command_get_system_theme, test_command_get_system_info -- keep this code block in sync with the test -->
```python
Command.get_system_theme(tag)
# Result: SystemTheme(tag=tag_string, theme=mode)
# mode is "light", "dark", or "none"

Command.get_system_info(tag)
# Result: SystemInfo(tag=tag_string, data=info_dict)
# info_dict keys: "system_name", "system_kernel", "system_version",
#   "system_short_version", "cpu_brand", "cpu_cores", "memory_total",
#   "memory_used", "graphics_backend", "graphics_adapter"
# Requires the renderer to be built with the `sysinfo` feature.
```

**Important:** The `tag` arrives as a **string** in `update()`, even if you
pass a non-string value. Match on the string.

<!-- test: test_command_get_system_theme -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click, SystemTheme

def update(self, model, event):
    match event:
        case Click(id="detect_theme"):
            return model, Command.get_system_theme("theme_detected")
        case SystemTheme(tag="theme_detected", theme=mode):
            return replace(model, os_theme=mode)
```

#### Image operations

In-memory images can be created, updated, and deleted at runtime. The
`Image` widget references them via `{"handle": "name"}` as its source.

<!-- test: test_command_create_image, test_command_create_image_rgba, test_command_update_image, test_command_update_image_rgba, test_command_delete_image, test_command_clear_images -- keep this code block in sync with the test -->
```python
Command.create_image(handle, data)                         # From PNG/JPEG bytes
Command.create_image_rgba(handle, width, height, pixels)   # From raw RGBA pixels
Command.update_image(handle, data)                         # Update with PNG/JPEG
Command.update_image_rgba(handle, width, height, pixels)   # Update with raw RGBA
Command.delete_image(handle)                               # Remove in-memory image
Command.clear_images()                                     # Delete all in-memory images
```

Example:

<!-- test: test_command_create_image, test_command_task -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from pathlib import Path
from plushie.commands import Command
from plushie.events import Click, AsyncResult

def update(self, model, event):
    match event:
        case Click(id="load_preview"):
            cmd = Command.task(lambda: Path("preview.png").read_bytes(), "preview_loaded")
            return model, cmd
        case AsyncResult(tag="preview_loaded", value=data):
            return model, Command.create_image("preview", data)
```

#### PaneGrid operations

Commands for manipulating panes in a `pane_grid` widget.

<!-- test: test_command_pane_split, test_command_pane_close, test_command_pane_swap, test_command_pane_maximize, test_command_pane_restore -- keep this code block in sync with the test -->
```python
Command.pane_split(pane_grid_id, pane, axis, new_pane_id)  # Split a pane
Command.pane_close(pane_grid_id, pane)                     # Close a pane
Command.pane_swap(pane_grid_id, pane_a, pane_b)            # Swap two panes
Command.pane_maximize(pane_grid_id, pane)                  # Maximize a pane
Command.pane_restore(pane_grid_id)                         # Restore from maximized
```

Example:

<!-- test: test_command_pane_split -- keep this code block in sync with the test -->
```python
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="split_editor"):
            return model, Command.pane_split("pane_grid", "editor", "horizontal", "new_editor")
```

#### Timers

<!-- test: test_command_send_after -- keep this code block in sync with the test -->
```python
Command.send_after(delay_ms, event)  # Deliver event to update after delay
```

<!-- test: test_command_send_after -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="flash_message"):
            return (
                replace(model, message="Saved!"),
                Command.send_after(3000, "clear_message"),
            )
        case "clear_message":
            return replace(model, message=None)
```

#### Batch

<!-- test: test_command_batch -- keep this code block in sync with the test -->
```python
Command.batch([
    Command.focus("name_input"),
    Command.send_after(5000, "auto_save"),
])
```

Commands in a batch are dispatched sequentially. Async commands spawn
concurrent threads, but the dispatch loop itself processes each command
in order.

#### Extension commands

Push data directly to a native Rust extension widget without triggering the
view/diff/patch cycle. Used for high-frequency data like terminal output or
streaming log lines.

<!-- test: test_command_extension_command, test_command_extension_commands -- keep this code block in sync with the test -->
```python
# Single command
Command.extension_command("term-1", "write", {"data": output})

# Batch (all processed before next view cycle)
Command.extension_commands([
    ("term-1", "write", {"data": line1}),
    ("log-1", "append", {"line": entry}),
])
```

Extension commands are only meaningful for widgets backed by a
`WidgetExtension` Rust implementation. They are silently ignored for
widgets without an extension handler.

#### Animation

<!-- test: test_command_advance_frame -- keep this code block in sync with the test -->
```python
Command.advance_frame(timestamp)  # Advance the animation clock (test/headless only)
```

The `timestamp` is monotonic milliseconds. Used for stepping through
animations deterministically in tests.

#### No-op

<!-- test: test_command_none -- keep this section in sync with the test -->

When `update` returns a bare model (not a tuple), the runtime treats it as
`(model, Command.none())`. You never need to write `Command.none()`
explicitly.

### Chaining commands

In iced, commands support `.then()` and `.chain()` for sequencing async
work. Plushie does not need dedicated chaining combinators because the Elm
update cycle provides this naturally: each `update()` can return
`(model, command)`, and the result of each command feeds back into
`update()` as an event, which can return more commands.

The model is updated and `view()` is re-rendered between each step. This
is actually more powerful than iced's chaining because you get full model
updates and UI refreshes at every link in the chain, not just at the end.

<!-- test: test_chaining_via_update_cycle -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.events import Click, AsyncResult

def update(self, model, event):
    match event:
        # Step 1: user clicks "deploy" -- validate first
        case Click(id="deploy"):
            cmd = Command.task(lambda: validate_config(model.config), "validated")
            return replace(model, status="validating"), cmd

        # Step 2: validation result arrives -- if OK, start the build
        case AsyncResult(tag="validated", value="ok"):
            cmd = Command.task(lambda: build_release(model.config), "built")
            return replace(model, status="building"), cmd

        case AsyncResult(tag="validated", value=("error", reason)):
            return replace(model, status=("failed", reason))

        # Step 3: build result arrives -- if OK, push it
        case AsyncResult(tag="built", value=("ok", artifact)):
            cmd = Command.task(lambda: push_artifact(artifact), "deployed")
            return replace(model, status="deploying"), cmd

        # Step 4: done
        case AsyncResult(tag="deployed", value="ok"):
            return replace(model, status="live")
```

Each step is a separate match arm with its own model state. The UI
reflects progress at every stage. No special chaining API needed --
the architecture is the API.

### How commands work internally

Commands are data. They describe what should happen, not how. The runtime
interprets them:

- **Async commands** spawn a Python thread managed by the runtime.
  When the thread completes, the result is wrapped in `AsyncResult` and
  dispatched through `update()`.
- **Widget operations** are encoded as wire messages and sent to the
  renderer.
- **Window commands** are encoded as wire messages to the renderer.
- **Window property queries** (get_size, get_position, etc.) are sent as
  window_op wire messages. The renderer responds with an `effect_response`
  keyed by window_id. **System queries** (get_system_theme, get_system_info)
  use a separate `query_response` wire message keyed by tag.
- **Image operations** are encoded as wire messages to the renderer.
- **PaneGrid operations** are encoded as widget ops sent to the renderer.
- **Timers** use Python's `threading.Timer` under the hood.

Commands are not side effects in `update`. They are descriptions of side
effects that the runtime executes after `update` returns. This keeps
`update` testable:

<!-- test: test_update_returns_inspectable_command -- keep this code block in sync with the test -->
```python
from plushie.events import Click

model = {"loading": False}
result = my_app.update(model, Click(id="fetch"))
new_model, cmd = result
assert new_model["loading"] is True
assert cmd.type == "task"
```

### DIY patterns

The `Command` class is convenience sugar, not a requirement. Python
already has all the concurrency primitives you need. Some users will
prefer the direct approach, and that is perfectly fine.

#### Streaming with bare threads

The runtime accepts events from any thread via its event queue. You
can send events directly from a worker thread:

```python
import threading
from dataclasses import replace
from plushie.commands import Command

def update(self, model, event):
    match event:
        case Click(id="import"):
            runtime = self._runtime  # reference to the runtime's event queue

            def do_import():
                for n, line in enumerate(open("big.csv"), 1):
                    row = parse_row(line)
                    runtime.dispatch(("import_progress", n, row))
                runtime.dispatch("import_done")

            threading.Thread(target=do_import, daemon=True).start()
            return replace(model, importing=True)

        case ("import_progress", n, row):
            return replace(model, rows_imported=n, data=[*model.data, row])

        case "import_done":
            return replace(model, importing=False)
```

#### Cancellation with threads

If you track the thread yourself, you can implement cooperative
cancellation via a `threading.Event`:

```python
import threading

def update(self, model, event):
    match event:
        case Click(id="start_import"):
            cancel = threading.Event()
            thread = threading.Thread(
                target=import_worker, args=(cancel, runtime_ref)
            )
            thread.start()
            return replace(model, importing=True, cancel_event=cancel)

        case Click(id="cancel_import"):
            if model.cancel_event is not None:
                model.cancel_event.set()
            return replace(model, importing=False, cancel_event=None)
```

Note: Python threads cannot be forcibly killed (unlike Erlang
processes). `Command.cancel()` prevents delivery of stale results
but cannot stop a blocked thread. Design task functions to check a
cancellation flag periodically for long-running work.

#### When to use which

Use `Command.task()` and `Command.stream()` when you want the runtime
to manage thread lifecycle and deliver results through the standard
`AsyncResult`/`StreamChunk` convention. Use bare threads when you need
more control over message shapes, or when the command abstraction feels
like overhead for your use case.

## Subscriptions

Subscriptions are ongoing event sources. Unlike commands (one-shot),
subscriptions produce events continuously as long as they are active.

**Important: tag semantics differ by subscription type.** For timer
subscriptions (`every()`), the tag becomes the event wrapper -- `update()`
receives `TimerTick(tag=tag, timestamp=ts)`. For all renderer subscriptions
(keyboard, mouse, window, etc.), the tag is management-only and does NOT
appear in the event. Renderer events arrive as their own dataclasses like
`KeyPress(...)` regardless of what tag you chose.

### The subscribe callback

<!-- test: test_subscription_every, test_subscription_on_key_press -- keep this code block in sync with the test -->
```python
from plushie.subscriptions import Subscription

def subscribe(self, model):
    subs = []

    # Tick every second while the timer is running
    if model.timer_running:
        subs.append(Subscription.every(1000, "tick"))

    # Always listen for keyboard shortcuts
    subs.append(Subscription.on_key_press("key_event"))

    return subs
```

`subscribe()` is called after every `update`. The runtime diffs the
returned subscription list against the previous one and starts/stops
subscriptions as needed. Subscriptions are identified by their
specification -- returning the same `Subscription.every(1000, "tick")` on
consecutive calls keeps the existing subscription alive; removing it stops
it.

### Available subscriptions

#### Time

<!-- test: test_subscription_every -- keep this code block in sync with the test -->
```python
Subscription.every(interval_ms, tag)
# Delivers: TimerTick(tag=tag, timestamp=ts) every interval_ms
```

#### Keyboard

<!-- test: test_subscription_on_key_press, test_subscription_on_key_release, test_subscription_on_modifiers_changed -- keep this code block in sync with the test -->
```python
Subscription.on_key_press(tag)
# Delivers: KeyPress(key=..., modifiers=..., ...)

Subscription.on_key_release(tag)
# Delivers: KeyRelease(key=..., modifiers=..., ...)

Subscription.on_modifiers_changed(tag)
# Delivers: ModifiersChanged(modifiers=KeyModifiers(...))

# The tag is used by the runtime to register/unregister the
# subscription with the renderer. It is NOT included in the event
# delivered to update(). See docs/events.md for the full
# KeyPress and KeyModifiers dataclass definitions.
```

#### Window lifecycle

<!-- test: test_subscription_on_window_close, test_subscription_on_window_open, test_subscription_on_window_resize, test_subscription_on_window_focus, test_subscription_on_window_unfocus, test_subscription_on_window_move, test_subscription_on_window_event -- keep this code block in sync with the test -->
```python
Subscription.on_window_close(tag)
# Delivers: WindowCloseRequested(window_id=wid)

Subscription.on_window_open(tag)
# Delivers: WindowOpen(window_id=wid, width=w, height=h, ...)

Subscription.on_window_resize(tag)
# Delivers: WindowResized(window_id=wid, width=w, height=h)

Subscription.on_window_focus(tag)
# Delivers: WindowFocused(window_id=wid)

Subscription.on_window_unfocus(tag)
# Delivers: WindowUnfocused(window_id=wid)

Subscription.on_window_move(tag)
# Delivers: WindowMoved(window_id=wid, x=x, y=y)

Subscription.on_window_event(tag)
# Delivers: various Window* dataclasses (catch-all for window events)
```

#### Mouse

<!-- test: test_subscription_on_mouse_move, test_subscription_on_mouse_button, test_subscription_on_mouse_scroll -- keep this code block in sync with the test -->
```python
Subscription.on_mouse_move(tag)
# Delivers: MouseMove(x=x, y=y)

Subscription.on_mouse_button(tag)
# Delivers: MouseButtonPress(button=btn) or MouseButtonRelease(button=btn)

Subscription.on_mouse_scroll(tag)
# Delivers: MouseWheel(delta_x=dx, delta_y=dy, unit=unit)
```

#### Touch

<!-- test: test_subscription_on_touch -- keep this code block in sync with the test -->
```python
Subscription.on_touch(tag)
# Delivers: TouchPress(finger_id=fid, x=x, y=y)
#           TouchMove(...)
#           TouchLift(...)
#           TouchLost(...)
```

#### IME (Input Method Editor)

<!-- test: test_subscription_on_ime -- keep this code block in sync with the test -->
```python
Subscription.on_ime(tag)
# Delivers: ImeOpen()
#           ImePreedit(text=text, cursor=(start, end_pos))
#           ImeCommit(text=text)
#           ImeClose()
```

#### System

<!-- test: test_subscription_on_theme_change, test_subscription_on_animation_frame, test_subscription_on_file_drop -- keep this code block in sync with the test -->
```python
Subscription.on_theme_change(tag)
# Delivers: ThemeChanged(theme=mode)  (mode is "light" or "dark")

Subscription.on_animation_frame(tag)
# Delivers: AnimationFrame(timestamp=ts)

Subscription.on_file_drop(tag)
# Delivers: FileDropped(window_id=wid, path=path)
#           FileHovered(window_id=wid, path=path)
#           FilesHoveredLeft(window_id=wid)
```

#### Catch-all

<!-- test: test_subscription_on_event -- keep this code block in sync with the test -->
```python
Subscription.on_event(tag)
# Receives all renderer events. Dataclass type varies by event family.
```

### Event rate limiting

The renderer supports rate limiting for high-frequency events (mouse moves,
scroll, animation frames, slider drags, etc.). This reduces wire traffic
and host CPU usage. Three configuration levels, in order of priority:

#### Per-widget `event_rate` prop

Widgets that emit high-frequency events accept an `event_rate` option:

```python
# Volume slider limited to 15 events/sec, seek bar at 60:
slider("volume", (0, 100), model.volume, event_rate=15)
slider("seek", (0, model.duration), model.position, event_rate=60)
```

Supported on: `Slider`, `VerticalSlider`, `Canvas`, `MouseArea`, `Sensor`,
`PaneGrid`, and all extension widgets.

#### Per-subscription `max_rate`

Renderer subscriptions accept a `max_rate` keyword argument:

<!-- test: test_subscription_max_rate, test_subscription_every_no_max_rate -- keep this code block in sync with the test -->
```python
# Rate-limit mouse moves to 30 events per second:
Subscription.on_mouse_move("mouse", max_rate=30)

# Animation frames at 60fps:
Subscription.on_animation_frame("frame", max_rate=60)

# Subscribe but never emit (capture tracking only):
Subscription.on_mouse_move("mouse", max_rate=0)
```

Timer subscriptions (`every()`) do not support `max_rate`.

#### Global `default_event_rate` setting

A global default applied to all coalescable event types:

```python
def settings(self):
    return {"default_event_rate": 60}
```

Set to 60 for most apps. Lower for dashboards or remote rendering.
Omit for unlimited (current default behavior).

### Subscription lifecycle

Subscriptions are declarative. You do not start or stop them imperatively.
You return a list from `subscribe()`, and the runtime manages the rest:

<!-- test: test_subscription_lifecycle_declarative, test_subscription_key_identity -- keep this code block in sync with the test -->
```python
from dataclasses import replace
from plushie.commands import Command
from plushie.subscriptions import Subscription
from plushie.events import Click, TimerTick, AsyncResult

def subscribe(self, model):
    if model.polling:
        return [Subscription.every(5000, "poll")]
    return []

def update(self, model, event):
    match event:
        case Click(id="start_polling"):
            return replace(model, polling=True)
        case Click(id="stop_polling"):
            return replace(model, polling=False)
        case TimerTick(tag="poll"):
            return model, Command.task(fetch_data, "data_received")
```

When `polling` becomes true, the runtime starts the timer. When it becomes
false, the runtime stops it. No explicit cleanup needed.

### How subscriptions work internally

- **Time subscriptions** use Python's `threading.Timer` loop.
- **Keyboard, mouse, touch, and window subscriptions** are registered with
  the renderer via wire messages. The renderer sends events when they occur.
- **System subscriptions** (theme change, animation frame, file drop) are
  also renderer-side event sources.

Subscriptions that require the renderer (everything except timers) are
paused during renderer restart and resumed once the renderer is back.

## Application settings

The `settings()` callback configures the renderer. Notable settings
relevant to commands and rendering:

- `vsync` -- boolean (default `True`). Controls vertical sync. Set to
  `False` for uncapped frame rates (useful for benchmarks or animation-heavy
  apps at the cost of higher GPU usage).
- `scale_factor` -- number (default `1.0`). Global UI scale factor applied
  to all windows. Values greater than 1.0 make the UI larger; less than 1.0
  makes it smaller.
- `default_event_rate` -- integer. Maximum events per second for coalescable
  event types. Omit for unlimited (default). See [Event rate limiting](#event-rate-limiting).

```python
def settings(self):
    return {
        "antialiasing": True,
        "vsync": False,
        "scale_factor": 1.5,
        "default_event_rate": 60,
    }
```

## Commands vs. effects

Commands are Python-side operations handled by the runtime. Effects are
native platform operations handled by the renderer (see [effects.md](effects.md)).

| | Commands | Effects |
|---|---|---|
| Handled by | Python runtime | Rust renderer |
| Examples | async work, timers, focus | file dialogs, clipboard, notifications |
| Transport | internal | wire protocol request/response |
| Return from | `update()` | `update()` (via `plushie.effects` functions) |

Widget operations and window commands are a hybrid -- they are initiated
from the Python side but executed by the renderer. They use the command
mechanism for the API but effect/effect_response for the transport.
