# Commands and Effects

Commands are pure data returned from `init` and `update`. The runtime
executes them after the update cycle completes. They are how your app
triggers side effects: background work, focus changes, window
operations, platform effects, and more.

Command factories live on `plushie.commands.Command` (re-exported as
`plushie.Command`). Platform effect factories live in
`plushie.effects`.

## Returning commands

`init` and `update` support three return forms:

```python
# Bare model (no commands)
def update(self, model, event):
    return model

# Model + single command
def update(self, model, event):
    match event:
        case Click(id="save"):
            return model, Command.focus("editor")

# Model + command list
def update(self, model, event):
    match event:
        case Click(id="export"):
            return model, [
                effects.file_save("export", title="Export"),
                effects.notification("notify", "Exporting", "Saving to file..."),
            ]
```

Invalid return shapes (3-tuples, non-Command values in a command
position, etc.) raise `TypeError` immediately. Returning `None`
from `update` (no `match` arm hit) logs a warning and keeps the
previous model. See
[App Lifecycle](app-lifecycle.md) for return-value validation.

## Command categories

All factories live on `Command` unless noted otherwise.

### Control flow

| Factory | Purpose |
|---|---|
| `Command.none()` | No-op (useful in conditional pipelines) |
| `Command.dispatch(value, mapper)` | Apply `mapper(value)` and queue the resulting event into `update` next cycle, no task spawned |
| `Command.batch(commands)` | Execute a list of commands in order |
| `Command.exit()` | Shut down the runtime and close all windows |

`Command.batch` executes commands in order. Each command threads
through the runtime state sequentially. Use it to combine multiple
side effects from a single `update` clause.

### Async

| Factory | Purpose |
|---|---|
| `Command.task(fn, tag)` | Run `fn()` on the thread pool. Result delivered as `AsyncResult(tag=tag, value=...)`. |
| `Command.stream(fn, tag)` | Run `fn(emit)` on the thread pool. Each `emit(value)` delivers `StreamChunk(tag=tag, value=...)`. Final return delivered as `AsyncResult`. |
| `Command.cancel(tag)` | Cancel an in-flight task or stream by tag. |
| `Command.send_after(delay_ms, event)` | One-shot delayed event. Delivers `event` to `update` after the delay. Replaces any pending timer with the same event. |

`Command.send_after` is a one-shot timer (fires once). For recurring
timers, use `Subscription.every` from
[Subscriptions](subscriptions.md).

**Python has no `async` factory name.** `async` is a reserved word;
use `Command.task` instead. `fn` is a zero-argument callable; the
runtime runs it on a `ThreadPoolExecutor` and posts the return value
back as `AsyncResult`.

### Focus

| Factory | Purpose |
|---|---|
| `Command.focus(widget_id)` | Set focus on a widget or canvas element. Supports `"window#widget"` paths. |
| `Command.focus_element(canvas_id, element_id)` | Focus a canvas element by its internal ID. |
| `Command.focus_next()` | Move focus to the next focusable widget. |
| `Command.focus_previous()` | Move focus to the previous focusable widget. |
| `Command.focus_next_within(scope)` | Move focus to the next focusable widget within a scope. |
| `Command.focus_previous_within(scope)` | Move focus to the previous focusable widget within a scope. |

### Text

| Factory | Purpose |
|---|---|
| `Command.select_all(widget_id)` | Select all text in a text input or editor |
| `Command.select_range(widget_id, start, end)` | Select a text range |
| `Command.move_cursor_to(widget_id, position)` | Move cursor to a specific position |
| `Command.move_cursor_to_front(widget_id)` | Move cursor to start |
| `Command.move_cursor_to_end(widget_id)` | Move cursor to end |

All text commands support window-qualified IDs (`"main#editor"`).

### Scroll

| Factory | Purpose |
|---|---|
| `Command.scroll_to(widget_id, x, y)` | Scroll to an absolute position (animated) |
| `Command.snap_to(widget_id, x=0.0, y=0.0)` | Snap scroll to a position (instant) |
| `Command.snap_to_end(widget_id)` | Snap scroll to the end |
| `Command.scroll_by(widget_id, x=0.0, y=0.0)` | Scroll by a relative offset |

### Pane grid

| Factory | Purpose |
|---|---|
| `Command.pane_split(pane_grid_id, pane_id, axis, ratio)` | Split a pane in a pane grid |
| `Command.pane_close(pane_grid_id, pane_id)` | Close a pane |
| `Command.pane_swap(pane_grid_id, pane_a, pane_b)` | Swap two panes |
| `Command.pane_maximize(pane_grid_id, pane_id)` | Maximize a single pane |
| `Command.pane_restore(pane_grid_id)` | Restore all panes to their split positions |

### Window operations

| Factory | Purpose |
|---|---|
| `Command.close_window(window_id)` | Close a window |
| `Command.resize_window(window_id, width, height)` | Set window size |
| `Command.move_window(window_id, x, y)` | Set window position |
| `Command.maximize_window(window_id, maximized=True)` | Maximize / unmaximize |
| `Command.minimize_window(window_id, minimized=True)` | Minimize / unminimize |
| `Command.set_window_mode(window_id, mode)` | Set fullscreen / windowed mode |
| `Command.toggle_maximize(window_id)` | Toggle maximized state |
| `Command.toggle_decorations(window_id)` | Toggle window decorations |
| `Command.focus_window(window_id)` | Bring window to front |
| `Command.set_window_level(window_id, level)` | Set window z-level |
| `Command.drag_window(window_id)` | Begin window drag |
| `Command.drag_resize_window(window_id, direction)` | Begin window resize drag |
| `Command.request_attention(window_id, urgency=None)` | Request user attention (taskbar bounce / flash) |
| `Command.set_resizable(window_id, resizable)` | Toggle whether the window can be resized |
| `Command.set_min_size(window_id, width, height)` | Clamp minimum window size |
| `Command.set_max_size(window_id, width, height)` | Clamp maximum window size |
| `Command.enable_mouse_passthrough(window_id)` | Pass pointer events through the window |
| `Command.disable_mouse_passthrough(window_id)` | Restore pointer capture |
| `Command.show_system_menu(window_id)` | Show the OS window menu |
| `Command.set_icon(window_id, rgba, width, height)` | Set the window icon |
| `Command.set_resize_increments(...)` | Snap resizing to a step |
| `Command.allow_automatic_tabbing(enabled)` | macOS automatic tab management |
| `Command.screenshot_window(window_id, tag)` | Capture window screenshot |

Screenshot results arrive as a `("screenshot_response", data)` tuple
in `update`. The data dict contains `name`, `hash`, `width`,
`height`, and optionally `rgba` bytes.

### Window queries

| Factory | Purpose |
|---|---|
| `Command.window_size(window_id, tag)` | Query window dimensions |
| `Command.window_position(window_id, tag)` | Query window position |
| `Command.window_mode(window_id, tag)` | Query fullscreen / windowed mode |
| `Command.scale_factor(window_id, tag)` | Query DPI scale factor |
| `Command.is_maximized(window_id, tag)` | Query maximized state |
| `Command.is_minimized(window_id, tag)` | Query minimized state |
| `Command.raw_id(window_id, tag)` | Query platform window handle |
| `Command.monitor_size(window_id, tag)` | Query monitor dimensions |

Results arrive as the appropriate
[system event](events.md#system-events) class. The `tag` field
matches the string you provided.

### System

| Factory | Purpose |
|---|---|
| `Command.system_theme(tag)` | Query OS light / dark preference |
| `Command.system_info(tag)` | Query system information |
| `Command.announce(text, politeness="polite")` | Screen reader announcement |

`Command.announce` triggers a live-region assertion for assistive
technology. The text is immediately spoken by the screen reader
without requiring a visible widget. Use for status updates, error
notifications, and dynamic content.

### Images

| Factory | Purpose |
|---|---|
| `Command.create_image(handle, data)` | Create an in-memory image from encoded PNG / JPEG bytes |
| `Command.create_image_rgba(handle, width, height, rgba)` | Create from raw RGBA pixels |
| `Command.update_image(handle, data)` | Replace the pixels of an existing handle |
| `Command.update_image_rgba(handle, width, height, rgba)` | Replace from raw pixels |
| `Command.delete_image(handle)` | Remove the handle from the renderer |
| `Command.clear_images()` | Remove every registered handle |
| `Command.list_images_query(tag)` | Query the list of active image handles |

### Other

| Factory | Purpose |
|---|---|
| `Command.load_font(family, data)` | Load a font from binary data at runtime |
| `Command.tree_hash_query(tag)` | Query structural hash of the UI tree |
| `Command.find_focused_query(tag)` | Query which widget has focus |
| `Command.advance_frame(timestamp)` | Manual animation frame advance (test / headless mode) |
| `Command.command(widget_id, family, value=None)` | Send a command to any widget by ID and family |
| `Command.widget_command(widget_id, family, value=None)` | Alias for `command` |
| `Command.commands(widget_id, commands)` | Send a batch of widget commands processed atomically |
| `Command.widget_batch(commands)` | Multi-widget batch variant |

## Platform effects

All factories live in `plushie.effects`. Each takes a string `tag`
as its first argument and returns a `Command`. Results arrive as
[`EffectResult(tag=..., result=...)`](events.md#effectresult-and-its-payloads)
events with a typed `result` payload.

```python
from plushie import effects, ui
from plushie.events import EffectResult, FileOpened, EffectCancelled

def update(self, model, event):
    match event:
        case Click(id="import"):
            return model, effects.file_open(
                "import",
                title="Import",
                filters=[("Python", "*.py")],
            )
        case EffectResult(tag="import", result=FileOpened(path=p)):
            return load_file(model, p)
        case EffectResult(tag="import", result=EffectCancelled()):
            return model
```

### File dialogs

| Function | Purpose |
|---|---|
| `effects.file_open(tag, **opts)` | Single file picker |
| `effects.file_open_multiple(tag, **opts)` | Multi-file picker |
| `effects.file_save(tag, **opts)` | Save dialog |
| `effects.directory_select(tag, **opts)` | Single directory picker |
| `effects.directory_select_multiple(tag, **opts)` | Multi-directory picker |

Options: `title`, `directory`, `filters` (list of
`(label, pattern)` tuples), `default_name`.

### Clipboard

| Function | Purpose |
|---|---|
| `effects.clipboard_read(tag)` | Read plain text |
| `effects.clipboard_write(tag, text)` | Write plain text |
| `effects.clipboard_read_html(tag)` | Read HTML content |
| `effects.clipboard_write_html(tag, html, alt_text=None)` | Write HTML content |
| `effects.clipboard_clear(tag)` | Clear clipboard |
| `effects.clipboard_read_primary(tag)` | Read primary selection (Linux) |
| `effects.clipboard_write_primary(tag, text)` | Write primary selection (Linux) |

### Notifications

```python
effects.notification(
    "saved",
    title="Exported",
    body=f"File saved to {path}",
)
```

Options: `icon`, `timeout` (auto-dismiss ms), `urgency`
(`"low"`, `"normal"`, `"critical"`), `sound`.

## Async mechanics

- **One task per tag.** Starting `Command.task` or `Command.stream`
  with a tag that is already in-flight cancels the previous task.
  Use unique tags for concurrent work.
- **Nonce-based stale rejection.** Each task gets a nonce at
  creation. Results from cancelled tasks carry a stale nonce and
  are silently discarded.
- **Exceptions become error results.** If the task raises, the
  `AsyncResult.value` field carries the `Exception` instance.
  Pattern match on it:

  ```python
  case AsyncResult(tag="fetch", value=Exception() as exc):
      return replace(model, error=str(exc))
  ```

- **Renderer restarts.** In-flight async tasks survive renderer
  restarts (they run in the Python process, not the renderer).
  Results may be stale if the work depended on renderer state.

### Streaming

```python
def fetch(emit):
    for chunk in fetch_chunks():
        emit({"progress": chunk.index, "value": chunk.data})
    return "done"

cmd = Command.stream(fetch, "import")
```

Each `emit(...)` call delivers a `StreamChunk(tag="import",
value=...)`. The function's final return value is delivered as
`AsyncResult(tag="import", value=...)`.

## Effect lifecycle

- **Tag-based matching.** Every effect takes a string tag. The tag
  returns in `EffectResult.tag` for direct pattern matching.
- **One effect per tag.** Starting a new effect with a tag that has
  a pending request discards the previous one.
- **Default timeouts:** file dialogs 120 seconds, clipboard and
  notifications 5 seconds. Override with the `timeout` option.
- **Timeout delivery.** `result=EffectTimeout()`.
- **Cancellation.** User dismissing a dialog delivers
  `result=EffectCancelled()` (not an error).
- **Effect stubs.** The testing fixture's
  `register_effect_stub(kind, result)` intercepts effects by kind in
  tests. See the [Testing reference](testing.md).

## DIY patterns

The runtime event queue is thread-safe. You can bypass the command
system and inject events directly:

```python
import threading

def update(self, model, event):
    match event:
        case Click(id="fetch"):
            def worker():
                result = http_get("/api/data")
                self.runtime.inject(("fetched", result))
            threading.Thread(target=worker, daemon=True).start()
            return model
        case ("fetched", result):
            return replace(model, data=result)
```

This is useful for integrating with existing threaded infrastructure
such as Flask endpoints, asyncio loops running in a background
thread, or message queue consumers. The tradeoff: you lose tag-based
cancellation and stale-result rejection that `Command.task` provides.

## See also

- [Async and Effects guide](../guides/11-async-and-effects.md) -
  effects, async, streaming, and multi-window
- [App Lifecycle reference](app-lifecycle.md) - return value
  validation and the update cycle
- [Events reference](events.md) - the event classes commands
  produce
- [Subscriptions reference](subscriptions.md) - the recurring timer
  alternative to `Command.send_after`
- [Testing reference](testing.md) - effect stubs and fake results
