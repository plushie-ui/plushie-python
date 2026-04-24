# App Lifecycle

A plushie app implements the Elm architecture: `init` produces an
initial model, `view` renders window nodes, `update` handles events
that change the model, and the loop repeats. The runtime owns the
model on a single thread and drives everything else around it
(reader thread, thread pool, timer threads) through a single event
queue.

This reference covers the `App` subclass shape, the decorator factory
alternative, return-value validation, the update cycle, multi-window
handling, renderer restart recovery, and external event injection.

## App subclass shape

`plushie.App[M]` is an abstract base class generic over the model
type. Subclasses implement three required methods and may override
four optional ones.

| Method | Required | Return |
|---|---|---|
| `init(self)` | yes | `M` or `(M, Command)` or `(M, [Command])` |
| `update(self, model, event)` | yes | same as `init` |
| `view(self, model)` | yes | window node or `list` of window nodes |
| `subscribe(self, model)` | no | `list[Subscription]` (default: `[]`) |
| `settings(self)` | no | `dict[str, Any]` (default: `{}`) |
| `window_config(self, model)` | no | `dict[str, Any]` (default: `{}`) |
| `handle_renderer_exit(self, model, info)` | no | `M` (default: passthrough) |

`self` exists on every method and is available for per-instance
configuration or injected dependencies. It is not for model state.
The model is passed explicitly to every callback, preserving the Elm
separation.

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui, Command
from plushie.events import Click


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0


class Counter(plushie.App[Model]):
    def init(self):
        return Model()

    def update(self, model, event):
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case _:
                return model

    def view(self, model):
        return ui.window(
            "main",
            ui.column(
                ui.text("count", f"Count: {model.count}"),
                ui.button("inc", "+"),
                padding=16,
            ),
            title="Counter",
        )


if __name__ == "__main__":
    plushie.run(Counter)
```

### init

Called once at startup. Returns the initial model, optionally paired
with commands to run after the first snapshot is sent.

### update

Called for every event. Receives the current model and the event,
returns the next model and optional commands. Always include a
catch-all `case _: return model` clause. See
[return value validation](#return-value-validation) for what happens
without one.

### view

Called after every successful `update`. Returns window nodes that
make up the UI. The runtime diffs the new tree against the previous
one and sends only the changes to the renderer. A full snapshot is
sent instead of a patch when the previous tree is `None` (startup,
successful reconnect).

### subscribe

Called after every update cycle. Returns the subscriptions that
should be active given the current model. The runtime diffs the
returned list against the active set, starting new subscriptions
and stopping removed ones. Default: no subscriptions.

See the [Subscriptions reference](subscriptions.md).

### settings

Called once at startup. Returns a dict of renderer-level defaults
(font, text size, theme, antialiasing, event rate). The dict is sent
to the renderer before the first snapshot and is re-sent after
renderer restart.

### window_config

Called when a new window is detected in the view tree, or when all
windows are re-opened after a renderer restart. Returns a base
settings dict that is overlaid by the per-window props from the view
tree. Per-window props always win.

Supported keys: `title`, `size`, `width`, `height`, `position`,
`min_size`, `max_size`, `maximized`, `fullscreen`, `visible`,
`resizable`, `closeable`, `minimizable`, `decorations`,
`transparent`, `blur`, `level`, `exit_on_close_request`,
`scale_factor`, `theme`.

### handle_renderer_exit

Called during recovery after the renderer process exits. Receives
the current model and a `RendererExitInfo` describing the exit.
Returns the model to use when the runtime re-renders against the
new renderer process. See
[renderer restart recovery](#renderer-restart-recovery) for the full
sequence and the exit types.

## Decorator factory alternative

For scripts and prototypes, `plushie.create_app` returns an
`AppBuilder` that accepts callbacks via decorators. It builds an
equivalent `App` subclass on demand.

```python
import plushie
from plushie import ui
from plushie.events import Click

app = plushie.create_app("Counter")


@app.init
def init():
    return {"count": 0}


@app.update
def update(model, event):
    match event:
        case Click(id="inc"):
            return {"count": model["count"] + 1}
        case _:
            return model


@app.view
def view(model):
    return ui.window(
        "main",
        ui.column(
            ui.text("count", f"Count: {model['count']}"),
            ui.button("inc", "+"),
        ),
    )


if __name__ == "__main__":
    plushie.run(app)
```

`@app.subscribe`, `@app.settings`, `@app.window_config`, and
`@app.handle_renderer_exit` register the optional callbacks the same
way. `plushie.run` accepts an `AppBuilder` directly and calls
`build()` internally.

## Return value validation

`init` and `update` both support three return shapes:

```python
return model                      # bare model, no commands
return model, Command.focus("x")  # model + single command
return model, [cmd_a, cmd_b]      # model + command list
```

The runtime validates the return value on every call. Invalid shapes
raise `TypeError` immediately rather than corrupting state
downstream:

- A tuple with more than two elements.
- A two-tuple whose second element is not a `Command` or a list.
- A list in the command position that contains non-`Command` items.

Returning `None` from `update` (for example, forgetting a catch-all
`case _`) is not an error but is still a bug. The runtime detects
it, logs a warning of the form `"update() returned None. forgot a
catch-all? Add 'case _: return model'"`, keeps the previous model,
and carries on. The logging is rate-limited so a hot loop of
`None` returns does not flood the log.

When `update` raises an exception, the model reverts to its
pre-exception state, `view` is skipped, and the previous tree stays
on screen. Log levels escalate with consecutive errors (full
stacktrace for the first bursts, debug-level after that, silent with
periodic reminders at pathological rates). The counter resets on
the next successful `update`.

## Starting the app

`plushie.run` is the blocking entrypoint. It resolves the renderer
binary, opens the connection, creates a `Runtime`, and blocks until
the app exits.

```python
import plushie

plushie.run(Counter)                     # windowed renderer
plushie.run(Counter, mode="headless")    # headless renderer
plushie.run(Counter, daemon=True)        # keep runtime alive across disconnect
plushie.run(Counter, binary_path="/path/to/plushie")
```

`plushie.start` starts the runtime on a background thread and
returns a `RuntimeHandle`. The handle exposes `stop()`, `wait()`,
`inject()`, `is_running`, and `model`. Use it when the runtime needs
to live alongside another blocking loop (Flask, asyncio, a REPL).

```python
handle = plushie.start(Counter)
try:
    handle.wait()
finally:
    handle.stop()
```

Both functions accept an `App` subclass (instantiated internally),
an already-constructed `App` instance, or an `AppBuilder`. Extra
keyword arguments are forwarded to `Connection.open`.

## The update cycle

One runtime thread owns the model and drives the full cycle. It
blocks on a `queue.Queue` that receives events from every other
source.

| Thread | Role |
|---|---|
| Runtime | Owns the model. Calls `update`, `view`, diffs the tree, runs commands, syncs subscriptions and windows. |
| Reader | Reads wire messages from the renderer, decodes them into event dataclasses, posts them on the queue. |
| Thread pool | `ThreadPoolExecutor` runs `Command.task` and `Command.stream` functions. Results and stream chunks are posted to the queue. |
| Timer | `threading.Timer` instances drive `Subscription.every` ticks and `Command.send_after` delivery. Each fire posts an event to the queue. |

On every event pulled from the queue, the runtime:

1. Calls `update(model, event)`, validates the return, captures
   any commands.
2. Executes the commands. Synchronous ones run inline, async ones
   go to the thread pool, platform effects go to the renderer.
3. Calls `view(model)`, runs tree normalization, diffs against the
   previous tree.
4. Sends a patch (or a full snapshot when the previous tree is
   `None`). If the trees are identical, no wire traffic is sent.
5. Diffs `subscribe(model)` against the active subscriptions, starts
   new ones and stops removed ones.
6. Syncs windows (see below).

Because every mutation happens on the runtime thread, `update` and
`view` see a stable model with no locking required.

High-frequency events (`Move`) are coalesced. The runtime stores the
latest per `(window_id, id)` key and flushes them once on a
zero-delay timer, so the model only sees the final position per
flush cycle.

## Multi-window

The runtime detects window nodes anywhere in the view tree. Each
cycle it compares the detected window IDs against the previously
tracked set.

- **Opened windows** (ID in the new tree, not the old): the runtime
  calls `window_config(model)` for base settings, overlays the
  per-window props extracted from the tree node, and sends an open
  operation to the renderer.
- **Closed windows** (ID in the old tree, not the new): the runtime
  sends a close operation.
- **Changed windows** (ID in both, props differ): the runtime sends
  an update operation with the changed props.

Window IDs must be stable strings. Changing an ID between renders
registers as a close plus an open, not an update.

Return a list of window nodes from `view` to open more than one
window:

```python
def view(self, model):
    return [
        ui.window("main", self._main_panel(model), title="Main"),
        ui.window("inspector", self._inspector(model), title="Inspector"),
    ]
```

See [Windows and Layout](windows-and-layout.md) for the full window
prop vocabulary.

## Renderer restart recovery

When the renderer process exits, the reader thread detects the
broken connection, posts a sentinel to the event queue, and
terminates. The runtime picks up the sentinel and begins reconnect.

1. The raw exit reason is mapped to a `RendererExitInfo` with `type`
   one of `"crash"`, `"shutdown"`, `"heartbeat_timeout"`, plus a
   `message` and optional `details`. The helper is
   `plushie.events.build_renderer_exit`.
2. `handle_renderer_exit(model, exit_info)` is called. Its return
   value becomes the candidate model for the new session. If it
   raises, the runtime logs the exception and dispatches a
   `RecoveryFailed` event into `update` after recovery completes.
3. Reconnect is attempted up to five times with exponential
   backoff (`100ms`, `200ms`, `400ms`, `800ms`, `1600ms`, capped at
   `5000ms`). The runtime sleeps, restarts the connection, re-sends
   `settings()`, and waits for the renderer hello.
4. On success, `view(candidate_model)` is called, a full snapshot
   is sent (not a patch), subscriptions are re-synced so renderer
   subscriptions re-register, and every tracked window is re-opened.
5. Python-side widget state (the model) is preserved across the
   restart. Renderer-side widget state (scroll offsets, text cursor,
   hover state) resets because the new process has no memory of the
   old one.

If all five attempts fail, the runtime logs an error and stops.

The heartbeat watchdog runs a timer that expects periodic traffic
from the renderer. When it fires, the runtime injects a reconnect
trigger with reason `"heartbeat_timeout"`, which flows into the same
recovery path.

### The RecoveryFailed event

If `handle_renderer_exit` raises, the runtime still completes the
reconnect and then dispatches `RecoveryFailed(kind=..., error=...,
renderer_exit=...)` into `update`. Match on it to fall back to a
safe state:

```python
from plushie.events import RecoveryFailed

def update(self, model, event):
    match event:
        case RecoveryFailed(renderer_exit=info):
            return self._reset_to_safe_state(model, info)
        case _:
            return model
```

## Daemon mode

When the last window closes, the renderer delivers `AllWindowsClosed`
to `update`. In normal mode the runtime processes that event, lets
`update` run any cleanup, then stops. Pass `daemon=True` to
`plushie.run` or `plushie.start` to keep the runtime alive after the
event. The model, subscriptions, and async tasks persist; open new
windows by returning them from a future `view`.

| Mode | After `AllWindowsClosed` |
|---|---|
| Default | `update` runs, runtime stops |
| Daemon | `update` runs, runtime continues |

Daemon mode fits tray apps, menu-bar utilities, and apps that open
windows in response to external events.

## External event injection

`Runtime.inject(event)` (or `RuntimeHandle.inject(event)`) posts an
event onto the runtime queue from any thread. It is thread-safe
because the queue is the only shared state the writer touches.

```python
handle = plushie.start(App)

# From a Flask route, message consumer, or other thread:
handle.inject(MessageReceived(payload))
```

Injected events flow through `update` exactly like renderer or
subscription events. Use it to integrate plushie with Flask, an
asyncio loop on another thread, a message queue consumer, or any
background producer that needs to push work into the Elm loop.

## See also

- [Events reference](events.md) - the event classes delivered to
  `update`, including `RecoveryFailed` and `RendererExitInfo`
- [Commands reference](commands.md) - commands returned from `init`
  and `update`
- [Subscriptions reference](subscriptions.md) - the specs returned
  from `subscribe`
- [Windows and Layout reference](windows-and-layout.md) - window
  node props and layout vocabulary
- [Testing reference](testing.md) - driving the cycle from tests
