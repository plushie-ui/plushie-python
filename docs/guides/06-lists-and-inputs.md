# Lists and Inputs

The pad already renders a sidebar of experiments from `model.experiments` and loads a new experiment when the user clicks one. In this chapter we sharpen that flow: we swap the sidebar's plain `column` for a `keyed_column` so widget state survives reorders, we replace the `+ New` button with a proper create form built around a `text_input`, and we add a couple of extra controls (an autosave `toggler`, an optional font-size `slider`) that round out the input vocabulary.

The focus is on dynamic lists, controlled inputs, and the small set of form patterns you will reach for over and over: validation, error display, and focus handoff after submit. The underlying widgets are covered in the [built-in widgets reference](../reference/built-in-widgets.md); the events they emit live in the [events reference](../reference/events.md).

## Dynamic lists

A list in the view is just a `for` comprehension that unpacks model data into widgets. The existing sidebar does exactly this:

```python
from plushie import ui


def _sidebar(model):
    return ui.column(
        ui.text("sidebar-title", "Experiments", size=14),
        *(
            ui.button(
                f"select-{exp.name}",
                exp.name,
                style="primary" if exp.name == model.selected else None,
            )
            for exp in model.experiments
        ),
        padding=12,
        spacing=8,
        width=220,
    )
```

A couple of things make this work. `ui.column` flattens generator expressions one level, so `*(... for exp in ...)` lands each button as a sibling child rather than a nested list. Every button also carries a stable, unique ID (`select-hello`, `select-notes`, and so on). The IDs are how `update()` knows which experiment to load when a click lands:

```python
case Click(id=exp_id) if exp_id.startswith("select-"):
    name = exp_id.removeprefix("select-")
    ...
```

Stable IDs earn their keep in more than one place. The event handler needs them, as shown above. The runtime also needs them for diffing: when the list changes between renders, the differ matches old children to new children by ID and only sends patches for what actually changed. If you rebuild IDs from array indices (`f"select-{i}"`), the IDs shift when you insert or remove an item, and the renderer loses track of which widget is which.

## keyed_column vs column

`ui.column` matches children to their previous tree by position. If the list grows at the top, every existing child shifts down and inherits the previous sibling's widget state: scroll offset, text cursor, focus ring, animation progress. For a list of static labels this is invisible. For a list of inputs, text editors, or focused items, it is jarring.

`ui.keyed_column` matches by ID instead. Insert at the top, reorder, or remove a middle item, and the surviving children keep their state no matter where they land. The signature is identical to `ui.column`, so the swap is a one-line change:

```python
def _sidebar(model):
    return ui.container(
        "sidebar",
        ui.keyed_column(
            ui.text("sidebar-title", "Experiments", size=14),
            *(
                ui.button(
                    f"select-{exp.name}",
                    exp.name,
                    style="primary" if exp.name == model.selected else None,
                )
                for exp in model.experiments
            ),
            ui.rule(),
            ui.button("new", "+ New", style="secondary"),
            padding=12,
            spacing=8,
            width=220,
        ),
        width=220,
        height="fill",
    )
```

Use `keyed_column` for any list that changes at runtime: sidebars, todo lists, chat logs, notification stacks. Use `column` for static layouts where the children are fixed. The rule of thumb: if you are inside a `for` comprehension that reads from the model, reach for `keyed_column`.

## Text inputs

`ui.text_input` is a single-line controlled input. You pass in an ID and the current value from the model; the renderer displays it and emits events when the user types:

```python
ui.text_input(
    "new-name",
    model.new_name,
    placeholder="experiment name",
    on_submit=True,
)
```

- `placeholder` shows greyed hint text when the value is empty.
- `on_submit=True` enables the `Submit` event when the user presses Enter. Without it, only `Input` events fire.

A text input emits events on different triggers. `Input` fires on every keystroke and carries the current text:

```python
from plushie.events import Input

case Input(id="new-name", value=text):
    return replace(model, new_name=text)
```

`Submit` fires when the user presses Enter (if `on_submit=True` is set) and carries the text at the moment of submission:

```python
from plushie.events import Submit

case Submit(id="new-name", value=name):
    return _create_named(model, name.strip())
```

The input is **controlled**: its displayed value always comes from the model. If `update()` does not store the latest `value` into the model and the view does not pass that field back in, the user will see their keystrokes revert. The pattern is always: receive `Input`, store `value`, re-render.

Other useful kwargs: `secure=True` for password fields, `input_purpose="email"` for software-keyboard hints, `icon={...}` for a leading glyph. The full list is in the [built-in widgets reference](../reference/built-in-widgets.md).

## A create form for new experiments

The pad's current `+ New` button just clears the editor. Let's turn the new-experiment flow into a real form: a text input for the name, a submit button, and validation that rejects empty names and duplicates.

Start by adding form state to the model:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Model:
    experiments: tuple = ()
    selected: str | None = None
    editor_source: str = ""
    last_saved_source: str = ""
    autosave: bool = False
    dirty: bool = False
    # New form fields
    new_name: str = ""
    errors: dict[str, str] = None  # set in __post_init__
```

The `errors` dict is keyed by field name (`"new_name"`, `"editor"`, and so on). A field is valid when it is absent from the dict. Storing errors this way lets the view render inline messages next to the relevant input without juggling separate flags.

The form sits in the sidebar under the experiment list:

```python
def _create_form(model):
    return ui.column(
        ui.text_input(
            "new-name",
            model.new_name,
            placeholder="experiment name",
            on_submit=True,
        ),
        (
            ui.text("new-name-error", model.errors["new_name"], color="#d32f2f", size=12)
            if model.errors and "new_name" in model.errors
            else None
        ),
        ui.button("create", "Create"),
        spacing=4,
    )
```

`ui.column` filters `None` out of its children, so the conditional error text appears only when an error is present. No `if` wrapping around the whole branch, no extra container.

Update handling lives in the `update()` method:

```python
from dataclasses import replace

from plushie.events import Click, Input, Submit


def update(self, model, event):
    match event:
        case Input(id="new-name", value=text):
            return replace(
                model,
                new_name=text,
                errors=_clear_error(model.errors, "new_name"),
            )

        case Submit(id="new-name"):
            return _try_create(model)

        case Click(id="create"):
            return _try_create(model)

        case _:
            return model


def _try_create(model):
    name = model.new_name.strip()
    if not name:
        return replace(model, errors=_set_error(model.errors, "new_name", "name required"))
    if any(exp.name == name for exp in model.experiments):
        return replace(
            model,
            errors=_set_error(model.errors, "new_name", f"{name} already exists"),
        )

    exp = pad_experiments.save(name, model.editor_source)
    exps = pad_experiments.list_experiments()
    return replace(
        model,
        experiments=exps,
        selected=name,
        last_saved_source=exp.source,
        new_name="",
        errors={},
        dirty=False,
    )
```

The `_clear_error` and `_set_error` helpers are plain dict operations; keep them next to the model definition:

```python
def _clear_error(errors, field):
    if not errors or field not in errors:
        return errors or {}
    return {k: v for k, v in errors.items() if k != field}


def _set_error(errors, field, message):
    return {**(errors or {}), field: message}
```

Notice that `Submit` and `Click(id="create")` both route to `_try_create`: Enter and the button do the same thing, and validation lives in one place. The error is cleared on the next keystroke (`Input`), so the user sees feedback the moment they start correcting the mistake, not on the next submit.

## Focus handoff with Command.focus

After creating an experiment the user almost certainly wants to start editing it. The runtime can move keyboard focus for you: return a `Command.focus(widget_id)` alongside the new model and the renderer will put the cursor in that widget:

```python
from plushie import Command


def _try_create(model):
    ...
    return (
        replace(model, ..., new_name=""),
        Command.focus("editor"),
    )
```

Commands are pure data. The runtime interprets them after `update()` returns, so the new model lands first and the focus shift happens against the updated tree. See the [commands reference](../reference/commands.md) for the full list.

## Checkbox and toggler

`ui.checkbox` and `ui.toggler` are both boolean inputs. The visual difference is the renderer's choice; the event is identical. Both emit `Toggle` with a `bool` in `value`.

The pad's toolbar already has an autosave button that flips `model.autosave` on click. A `toggler` gives the state a clearer affordance:

```python
def _toolbar(model):
    return ui.row(
        ui.button("save", "Save" + (" *" if model.dirty else "")),
        ui.toggler("autosave", model.autosave, label="Autosave"),
        padding=8,
        spacing=8,
    )
```

Handle it in `update()`:

```python
from plushie.events import Toggle

case Toggle(id="autosave", value=on):
    return replace(model, autosave=on)
```

Like text inputs, these widgets are controlled: `is_toggled` comes from the model, the model updates on `Toggle`, and the view re-renders. If you forget to store `value` into the model, the toggler visually snaps back on the next render.

## Slider

`ui.slider` takes an ID, a `(min, max)` tuple, and the current value. A font-size slider for the editor is a handy bonus:

```python
ui.slider("font-size", (10.0, 24.0), model.font_size, step=1.0, width=160)
```

Sliders emit at different moments. `Slide` fires continuously while the user drags (useful for live preview). `SlideRelease` fires once when they let go (useful for committing expensive work):

```python
from plushie.events import Slide, SlideRelease

case Slide(id="font-size", value=size):
    return replace(model, font_size=size)

case SlideRelease(id="font-size", value=size):
    return replace(model, font_size=size, event_log=_log(model.event_log, "font", str(size)))
```

Feed the value back into the editor:

```python
ui.text_editor(
    "editor",
    model.editor_source,
    width="fill",
    height={"fill_portion": 3},
    size=model.font_size,
    highlight_syntax="python",
)
```

For a vertical slider, use `ui.vertical_slider` with the same argument shape.

## Pick list and combo box

When the set of choices is fixed and known, `ui.pick_list` gives you a dropdown:

```python
ui.pick_list("theme", ["light", "dark", "auto"], model.theme)
```

`ui.combo_box` is the searchable, free-text variant; the user can pick an option or type something new:

```python
ui.combo_box("tag", known_tags, model.current_tag, placeholder="add a tag")
```

Both emit `Select` with the chosen string:

```python
from plushie.events import Select

case Select(id="theme", value=choice):
    return replace(model, theme=choice)
```

`combo_box` also emits `Input` as the user types, so you can filter the options list or validate free-form entries.

## Form patterns

A few patterns recur across any non-trivial form:

- **Errors on the model, not in UI state.** Keeping errors in `model.errors` means `view()` stays a pure function of the model, tests can assert on model state instead of poking at widgets, and undo/redo naturally covers form state.
- **Clear errors on input, set on submit.** Users expect feedback to disappear as they fix the problem. Route validation through a single submit path; clear relevant errors inside the field's `Input` handler.
- **One submit path for Enter and button.** Both the `Submit` event and the `Click` on the button should call the same helper. If they diverge, sooner or later they diverge in user-visible ways.
- **Disable while submitting.** For forms that trigger async work, flip a `model.submitting = True` flag in the submit handler and pass `disabled=True` to the input and button while it is set. Re-enable on the `AsyncResult` that marks the task complete.
- **Scope for repeated rows.** When the same form fields appear per-item (tags, contact rows, steps in a recipe), wrap each row in a named `ui.container` and rely on scoped IDs so `update()` can tell `name` in row `alice` from `name` in row `bob`. See the [scoped IDs reference](../reference/scoped-ids.md).

## Verify it

A short test covers the create flow end to end: the error appears on empty submit, and a valid name creates the experiment.

```python
def test_create_form(app):
    app.click("create")
    assert app.text("new-name-error") == "name required"

    app.type("new-name", "demo")
    app.submit("new-name")
    assert app.model.selected == "demo"
    assert app.find("select-demo") is not None
```

The `AppFixture` drives clicks, typing, and submits through the real renderer; there are no Python-side shortcuts around `update()`. See the [testing reference](../reference/testing.md).

## What's next

The sidebar now has a keyed list, a real create form, error display, and a handful of new inputs. The pad also grew a few more widgets in the toolbar, which is starting to look cramped. The [next chapter](07-layout.md) tightens up spacing, sizing, and alignment so the panes sit together the way you want them to. For cross-cutting patterns like reusable form helpers and composable field components, see the [composition patterns reference](../reference/composition-patterns.md); for multi-window forms (an advanced preferences dialog, say) see [windows and layout](../reference/windows-and-layout.md).
