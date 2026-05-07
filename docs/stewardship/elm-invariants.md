# Elm-architecture invariants

The contract between user apps and the runtime. These invariants
hold across every plushie-python app; the runtime enforces them
and the test fixture relies on them. Other host SDKs implement
the same shape (modulo language idiom); plushie-elixir is the
canonical reference per `posture.md`, plushie-python is the
Python expression of that shape.

## The three callbacks

A Plushie app subclasses `plushie.App[Model]` and implements:

- `init(self) -> M | tuple[M, Command]` - called once at
  startup. Returns the initial model, optionally with a
  command (or list of commands) to dispatch (load initial
  data, configure UI).
- `update(self, model: M, event: Event) -> M | tuple[M, Command]`
  - called for every event. Returns the next model, optionally
  with commands. Pure function of model + event.
- `view(self, model: M) -> dict` - called after every update.
  Returns a UI tree as a plain dict (the wire-format node).
  Pure function of model. The top level must be a window node
  or a list of window nodes.

Optional callbacks with default implementations:
`subscribe(self, model) -> list[Subscription]`,
`settings(self) -> dict[str, Any]`,
`window_config(self, model) -> dict[str, Any]`,
`handle_renderer_exit(self, model, reason) -> M`.

The decorator factory (`plushie.create_app(...)`) is sugar for
the same shape; internally it builds an `App` subclass.

`self` exists but is not for model state. The model is passed
explicitly to every callback, keeping the Elm separation. `self`
is available for per-instance configuration, helper methods, or
injected dependencies (e.g. a database handle wired in at
construction time).

## Return-shape validation

`init` and `update` must return one of:

- A bare model (no side effects needed).
- `(model, Command)` (single command).
- `(model, [Command, ...])` (list of commands; can be empty).

`plushie.runtime.unwrap_result` enforces this. Anything else
raises `TypeError` immediately:

- A two-tuple where the second element is neither a `Command`
  nor a list of `Command`s raises with the offending value.
- A non-two-tuple (e.g., `(model, command, extra)`) raises
  with the tuple length and the expected shapes listed.
- A list inside the command list that contains a non-Command
  raises with the offending element.

This is fail-fast on purpose. A misshapen return silently
corrupting state is harder to debug than an immediate raise.

## The None-return footgun

Python's `match` returns `None` when no `case` matches and
there is no fallthrough `case _`. A user `update` that forgets
the fallthrough returns `None` for unhandled events. The
runtime detects `None` returns explicitly: keep the previous
model, log a warning with the offending event. The encouraged
pattern is `case _: return model` at the end of every `match`
in `update`; the detection is a backstop, not the primary
defense. This is the one Python-specific shape deviation in
the contract.

## Commands are pure data

A command is a `@dataclass(frozen=True, slots=True)` with `type`
and `payload` fields. The runtime executes it; user code never
executes a command directly. This is what makes `update`
testable without going through I/O: the test asserts the
command was returned; the runtime is what would have run it.

Categories live in `plushie.commands.Command`: async work
(`task`, `stream`, `cancel`, `done`, `send_after`, `exit`,
`batch`, `none`, `dispatch`); widget operations (`focus`,
`select_all`, `scroll_to`, `command`, `commands`, etc.);
window operations (`close_window`, `resize_window`,
`set_window_mode`, `screenshot_window`, window queries, etc.);
effects (file dialogs, clipboard, notifications); image ops;
and animation (`advance_frame`).

The async-work command is `Command.task(fn, tag)`, not
`Command.async(...)`, because `async` is a reserved word in
Python. This is the one unavoidable cross-SDK shape deviation
in the command vocabulary.

A user dispatching a side effect that is not a command is a
design problem with the side effect, not a request for an
escape hatch. If a needed side effect cannot be expressed as a
command, the missing command is the work.

## View is a pure function of model

`view(model)` returns the UI tree from the model. It does not
read process state, does not start threads, does not perform
I/O. The runtime calls `view` after every update; it must be
deterministic from the model alone.

Pure-Python composite or canvas widgets defined via `WidgetDef`
that take internal state (`init(props)`, `view(id, props,
state)`, `handle_event(event, state)`) are the exception, but
the state is owned by the runtime and threaded into `view`
deterministically; the widget body is still pure with respect
to the inputs it receives.

The top level of the view must be a window node or a list of
window nodes. Returning a bare `column` or `row` from `view` is
a programming error; the renderer rejects it and the runtime
surfaces the error.

## Tree nodes are plain dicts

UI trees use the wire protocol's node format directly:
`{"id": ..., "type": ..., "props": {...}, "children": [...]}`.
The `plushie.ui` module provides builder functions that return
these dicts; users can mix `ui` calls with raw dicts. Nodes
with `id=None` (from auto-id display builders like
`text("Hello")`) get deterministic IDs during normalization
based on their position. There is no wrapper class hierarchy.
See `dsl-discipline.md` for the user-facing surface.

## Subscriptions are declarative

`subscribe(model) -> list[Subscription]` returns the list of
active subscriptions. The runtime diffs this list each cycle
(keys identify subscriptions: `(type, tag)` for timers,
`(kind, tag, window_id)` for renderer subs), starts new
subscriptions, and stops removed ones. The user does not start
or stop subscriptions imperatively; they return the list and
the runtime reconciles.

Timer subscriptions (`Subscription.every`) run as
`threading.Timer` instances in the runtime. Other subscriptions
(key, mouse, window events) are forwarded to the renderer as
subscribe/unsubscribe wire messages. Subscription failures
surface as events through the normal dispatch path.

Per-subscription `max_rate` lets the renderer coalesce
high-frequency events before they cross the wire.

## Widget event flow

Events from the renderer arrive at the runtime, flow through
custom widget `handle_event` interception, and reach `update`:

1. Event arrives from the connection.
2. Runtime looks up custom widget handlers registered for the
   widget at the event's scope chain.
3. Each handler returns one of (`EventAction`):
   - `ignored` - handler did not capture; continue to next.
   - `consumed` - captured, no output; stop the chain.
   - `update_state(new_state)` - captured, persist widget
     state; stop.
   - `emit(family, value)` - captured, replace the event with
     the emitted one; continue.
   - `emit(family, value, new_state)` - emit + persist state.
4. If the chain returns an event (or the original was not
   captured), it reaches `update`.

Canvas-internal events that no handler captures are
auto-consumed by the runtime; they never reach `update`. View-
only widgets (no events, no state) are transparent; events
pass through.

This matches iced's captured/ignored model on the renderer
side and is part of the cross-SDK shape.

## Scoped IDs

Wire IDs use the canonical format `window#scope/path/id`:

- `"main#form/email"` - widget `email` inside scope `form`
  inside window `main`.
- `"main"` - the window itself.

Events on the runtime side carry split fields: `id` (local),
`window_id`, `scope` (tuple of scope components from immediate
parent outward). This shape is what user pattern matching
operates on:

```python
match event:
    case Click(id="save", scope=("form", *_)):
        ...
    case Click(id="done", scope=(item_id, *_)):
        ...
```

Commands use forward-order path strings:
`Command.focus("form/email")`. The runtime's send path joins
window context onto commands as needed.

`plushie.tree.ScopedId` parses and constructs the canonical
form. `"/"` is forbidden in user-provided IDs.

## What these invariants buy

- **Tests can be written.** A pure `update` plus pure data
  commands plus a pure `view` is exercisable through the
  integration spine without elaborate setup. The user never
  needs to "wait for an effect" in their tests; they assert
  on what was returned.
- **The runtime can revert on exception.** Because `update` is
  a pure function that returns the new model, the runtime
  keeps the previous model and recovers by reverting. Same
  for `view`: a previous tree is preserved as the fallback.
- **The runtime can reconnect after a renderer crash.** The
  current model is enough to regenerate the full tree and
  re-establish state. The renderer holds no app state the
  runtime cannot reconstruct.
- **Cross-SDK parity is meaningful.** "What does this app do
  here" has a precise answer; other SDKs implement the same
  contract.
