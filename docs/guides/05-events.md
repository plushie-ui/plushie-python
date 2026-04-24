# Events

The pad's skeleton responds to a few events already: saving the editor
buffer, picking an experiment in the sidebar. This chapter widens that
vocabulary. We look at how events are modelled in Python, how to match
on them precisely, and how to introduce new ones as the pad grows. By
the end the pad will create new experiments from a text input, save
with Cmd+S, and maintain a visible event log so every interaction is
traceable.

Events live in `plushie.events`. The full catalogue is in the
[Events reference](../reference/events.md). Here we focus on the
shape of the Python model and the patterns that matter for day-to-day
update functions.

## Events are frozen dataclasses

There is no single `Event` class with a `type` field. Each wire family
is its own frozen, slotted dataclass. `Click`, `Input`, `Toggle`,
`Submit`, `Select`, `Slide`, `KeyEvent`, `TimerTick`, `EffectResult`
and so on are all distinct types. Pattern matching narrows to the
exact shape:

```python
from plushie.events import Click, Input, Toggle

match event:
    case Click(id="save"):
        ...
    case Input(id="name", value=v):
        ...
    case Toggle(id="dark_mode", value=on):
        ...
```

Each class has exactly the fields that family carries. `Click` has no
`value`. `Input.value` is `str`. `Toggle.value` is `bool`.
`Slide.value` is `float`. The type checker sees those types in each
arm, which means less runtime guessing and no stringly typed
dispatch.

A small exception: `KeyEvent`, `WindowEvent`, `ImeEvent`, and
`EffectResult` fold multiple related wire families into one class
distinguished by a `type` field or a typed `result` payload. Match on
that field inside the class pattern (see the keyboard section below).

## Widget events

Widget events are emitted by user interaction with widgets in the
tree. The common ones in the pad so far:

| Event | Fields | Emitted by |
|---|---|---|
| `Click` | `id`, `scope` | `button`, clickable containers |
| `Input` | `id`, `value`, `scope` | `text_input`, `text_editor` |
| `Submit` | `id`, `value`, `scope` | `text_input` when Enter is pressed |
| `Toggle` | `id`, `value`, `scope` | `checkbox`, `toggler` |
| `Select` | `id`, `value`, `scope` | `pick_list`, `combo_box`, `radio` |
| `Slide` | `id`, `value`, `scope` | `slider` during drag |

All of them also carry `window_id`, the window the event came from.
The Events reference lists every widget event family and their
wire-level equivalents.

The pad's editor input arm is a direct `Input` match:

```python
case Input(id="editor", value=source):
    return replace(
        model,
        editor_source=source,
        dirty=source != model.last_saved_source,
    )
```

And the save toolbar button:

```python
case Click(id="save"):
    return _save(model)
```

Nothing stringly typed. Nothing to unpack manually. The `value` in
the `Input` arm is statically known to be `str`.

## Scope-based matching

Widget IDs do not have to be static. The sidebar draws a button per
experiment with an ID derived from the experiment name:

```python
ui.button(
    f"select-{exp.name}",
    exp.name,
    style="primary" if exp.name == model.selected else None,
)
```

Matching on a literal ID will not work for these. Use a guard to
capture the ID and inspect it:

```python
case Click(id=exp_id) if exp_id.startswith("select-"):
    name = exp_id.removeprefix("select-")
    exp = pad_experiments.load(name)
    if exp is None:
        return model
    return replace(
        model,
        selected=exp.name,
        editor_source=exp.source,
        last_saved_source=exp.source,
        dirty=False,
        preview_error=None,
    )
```

The other tool for disambiguating repeated IDs is the `scope` tuple.
When a `delete` button lives inside each row of a list, every row
emits `Click(id="delete", ...)`. The scope tells you which row.
Matching on `scope=(item_id, *_)` captures the nearest ancestor
container ID, which is usually the per-row identifier set by the view.
Scope patterns come into play properly in the list chapter; for now
the ID-prefix form is enough.

See the [Scoped IDs reference](../reference/scoped-ids.md) for the
full resolution rules.

## Keyboard events

Keyboard input does not arrive through widgets. It arrives through a
subscription, which the app declares in `subscribe()`:

```python
def subscribe(self, model: Model) -> list[Subscription]:
    subs: list[Subscription] = [Subscription.on_key_press()]
    if model.autosave:
        subs.append(Subscription.every(1500, "autosave"))
    return subs
```

`Subscription.on_key_press()` turns on global key press events.
Releases come from `Subscription.on_key_release()`. Window-scoped
variants are available on both. The
[Subscriptions reference](../reference/subscriptions.md) covers
every constructor.

A `KeyEvent` carries the logical key name, the active modifiers, and
whether it is a press or release. The `modifiers` field is a
`KeyModifiers` dataclass with `shift`, `ctrl`, `alt`, `logo`, and
`command` booleans. `command` is the platform-correct save-shortcut
modifier (Cmd on macOS, Ctrl elsewhere), so that is what the pad uses
for Cmd+S:

```python
case KeyEvent(type="press", key="s", modifiers=mods) if mods.command:
    return _save(model)
```

Three things to notice. First, the guard on `mods.command` matters:
plain "s" typed into the editor also produces a key press, and we do
not want every keystroke to save. Second, `type="press"` filters out
the release event that fires when the user lets the keys go. Third,
no return wrapping: the match produces a new `Model`, and the runtime
takes care of the rest.

## Creating new experiments

The sidebar has a `+ New` button. Clicking it should clear the editor
so the user can type a fresh experiment. Pressing Enter in a name
input should save the new buffer under that name.

The `+ New` button is a plain `Click`:

```python
case Click(id="new"):
    return _new_experiment(model)
```

with the helper doing the clearing:

```python
def _new_experiment(model: Model) -> Model:
    return replace(model, selected=None, editor_source="", dirty=True)
```

`dirty=True` because the empty buffer differs from the last saved
source. `selected=None` tells the view there is no current experiment
backing the editor, which is our signal to show a name prompt.

When the user types a name in a prompt input and presses Enter, the
`text_input` widget emits `Submit(id="new-name", value=...)`. That
arm creates the experiment:

```python
case Submit(id="new-name", value=name):
    return _create_named(model, name.strip())
```

```python
def _create_named(model: Model, name: str) -> Model:
    if not name:
        return model
    exp = pad_experiments.save(name, model.editor_source)
    exps = pad_experiments.list_experiments()
    return replace(
        model,
        experiments=exps,
        selected=name,
        last_saved_source=exp.source,
        dirty=False,
    )
```

`Submit` is distinct from `Input`. `Input` fires on every keystroke.
`Submit` fires once, on Enter, with the final value. Pick the one
that matches the interaction. A search box that updates results as
the user types uses `Input`. A name prompt that commits on Enter uses
`Submit`.

## An event log

The best way to learn a new widget's events is to see them. Add an
event log pane to the pad. Anything the user does, whether or not
there is a dedicated arm, shows up in the log.

Start with a small dataclass for log entries:

```python
@dataclass(frozen=True, slots=True)
class EventLogEntry:
    kind: str
    detail: str
```

Add a tuple of entries to the model:

```python
@dataclass(frozen=True, slots=True)
class Model:
    experiments: tuple[pad_experiments.Experiment, ...] = ()
    selected: str | None = None
    editor_source: str = ""
    last_saved_source: str = ""
    preview_error: pad_compile.CompileError | None = None
    event_log: tuple[EventLogEntry, ...] = ()
    autosave: bool = False
    dirty: bool = False
```

A tuple instead of a list: the model is frozen, and tuples compose
naturally with `replace()`. The helper that prepends an entry and
caps the log:

```python
def _log(
    log: tuple[EventLogEntry, ...], kind: str, detail: str
) -> tuple[EventLogEntry, ...]:
    entry = EventLogEntry(kind=kind, detail=detail)
    trimmed = (entry, *log)[:50]
    return trimmed
```

The `_save` helper is a natural place to record a log entry. Every
save produces one:

```python
def _save(model: Model) -> Model:
    if model.selected is None:
        return model
    exp = pad_experiments.save(model.selected, model.editor_source)
    exps = pad_experiments.list_experiments()
    return replace(
        model,
        experiments=exps,
        last_saved_source=exp.source,
        dirty=False,
        event_log=_log(model.event_log, "saved", exp.name),
    )
```

And a log pane in the view:

```python
def _event_log(model: Model) -> dict[str, Any]:
    return ui.container(
        "log",
        ui.column(
            ui.text("log-title", "Event log", size=14),
            *(
                ui.text(f"log-{idx}", f"{entry.kind}: {entry.detail}")
                for idx, entry in enumerate(model.event_log)
            ),
            padding=8,
            spacing=4,
        ),
        width=240,
        height="fill",
    )
```

Dropped into the pad's top-level row, the log sits alongside the
sidebar and main pane. Each time the user saves, the pane grows a
line. Extend `_log()` into other arms as you add them: autosave
ticks, experiment creation, keyboard shortcuts. The log is a free
teaching tool and a cheap debugging aid.

## The catch-all clause

Python's `match` is an expression in a statement wrapper: if no arm
matches, nothing is returned. `update()` would then silently return
`None`, the runtime would log a warning, and the model would stay
put. That is not terrible, but the warning is noise and the bug is
easy to miss.

Always close with a wildcard:

```python
case _:
    return model
```

Keep the catch-all minimal. Returning the model unchanged is the
right default. If you want to log unmatched events, add them to the
event log explicitly rather than burying the logic in the catch-all.
A quiet default arm reads more clearly.

## What's next

The pad now reacts to mouse, keyboard, and text input across a
growing surface area. Next we tackle list patterns properly: per-row
delete buttons with scope-based matching, inline editing, reorderable
items, and the input widgets that go with them.

See the [Events reference](../reference/events.md), the
[Subscriptions reference](../reference/subscriptions.md), the
[Built-in widgets reference](../reference/built-in-widgets.md), and
the [Scoped IDs reference](../reference/scoped-ids.md) for the full
surface area this chapter touches.
