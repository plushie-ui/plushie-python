# Tutorial: building a todo app

This tutorial walks through building a complete todo app, introducing
one concept per step. By the end you'll understand text inputs,
dynamic lists, scoped IDs, commands, and conditional rendering.

## Step 1: the model

Start with a frozen dataclass that tracks a list of todos and the
current input text.

<!-- test: test_tutorial_step1_init, test_tutorial_step1_view -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.events import Click, Submit, Toggle


@dataclass(frozen=True, slots=True)
class Todo:
    id: str
    text: str
    done: bool = False


@dataclass(frozen=True, slots=True)
class Model:
    items: tuple[Todo, ...] = ()
    input_value: str = ""
    filter: str = "all"
    next_id: int = 1


class TodoApp(plushie.App[Model]):
    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        return model

    def view(self, model: Model) -> dict[str, Any]:
        return ui.window(
            "main",
            ui.column(
                ui.text("title", "My Todos", size=24),
                ui.text("empty", "No todos yet"),
                id="app",
                padding=20,
                spacing=12,
                width="fill",
            ),
            title="Todos",
        )
```

Run it with `python -m plushie run my_app:TodoApp`. You'll see a
title and a placeholder message. Not much yet, but the structure is
in place: `init` sets up state, `view` renders it.

## Step 2: adding a text input

Add a text input that updates the model on every keystroke, and a
submit handler that creates a todo when the user presses Enter.

<!-- test: test_tutorial_step2_input_updates_model, test_tutorial_step2_submit_creates_todo, test_tutorial_step2_empty_submit_does_nothing -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
def update(self, model: Model, event: object) -> Model:
    match event:
        case plushie.Input(id="new-todo", value=v):
            return replace(model, input_value=v)

        case Submit(id="new-todo", value=v) if v.strip():
            todo = Todo(id=f"todo-{model.next_id}", text=v.strip())
            return replace(
                model,
                items=(*model.items, todo),
                input_value="",
                next_id=model.next_id + 1,
            )

        case _:
            return model
```

And the view:

<!-- test: test_tutorial_step2_view_has_text_input -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
def view(self, model: Model) -> dict[str, Any]:
    return ui.window(
        "main",
        ui.column(
            ui.text("title", "My Todos", size=24),
            ui.text_input(
                "new-todo",
                model.input_value,
                placeholder="What needs doing?",
                on_submit=True,
            ),
            id="app",
            padding=20,
            spacing=12,
            width="fill",
        ),
        title="Todos",
    )
```

Type something and press Enter. The input clears (the model's
`input_value` resets to `""`), but you can't see the todos yet.
Let's fix that.

## Step 3: rendering the list with scoped IDs

Each todo needs its own row with a checkbox and a delete button.
We wrap each item in a named container using the todo's ID. This
creates a **scope** -- children get unique IDs automatically without
manual prefixing.

<!-- test: test_tutorial_step3_view_renders_todo_list, test_tutorial_step3_todo_row_structure -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
def view(self, model: Model) -> dict[str, Any]:
    return ui.window(
        "main",
        ui.column(
            ui.text("title", "My Todos", size=24),
            ui.text_input(
                "new-todo",
                model.input_value,
                placeholder="What needs doing?",
                on_submit=True,
            ),
            ui.column(
                *(_todo_row(item) for item in model.items),
                id="list",
                spacing=4,
            ),
            id="app",
            padding=20,
            spacing=12,
            width="fill",
        ),
        title="Todos",
    )


def _todo_row(item: Todo) -> dict[str, Any]:
    return ui.container(
        item.id,
        ui.row(
            ui.checkbox("toggle", item.done),
            ui.text(item.text),
            ui.button("delete", "x"),
            spacing=8,
        ),
    )
```

Each todo row lives in `container(item.id, ...)` (e.g.,
`"todo-1"`). Inside it, the checkbox has local id `"toggle"` and
the button has `"delete"`. On the wire, these become
`"list/todo-1/toggle"` and `"list/todo-1/delete"` -- unique across
all items.

## Step 4: handling toggle and delete with scope

When the checkbox or delete button is clicked, the event carries the
local `id` and a `scope` tuple with the todo's container ID as the
immediate parent. Pattern match on both:

<!-- test: test_tutorial_step4_toggle, test_tutorial_step4_delete -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
case Toggle(id="toggle", scope=(item_id, *_)):
    items = tuple(
        replace(item, done=not item.done) if item.id == item_id else item
        for item in model.items
    )
    return replace(model, items=items)

case Click(id="delete", scope=(item_id, *_)):
    items = tuple(item for item in model.items if item.id != item_id)
    return replace(model, items=items)
```

The `scope=(item_id, *_)` pattern binds the immediate parent's ID
(e.g., `"todo-1"`) regardless of how deep the row is nested. If you
later move the list into a sidebar or tab, the pattern still works.

## Step 5: refocusing with a command

After submitting a todo, the text input loses focus. Let's refocus
it automatically using `Command.focus()`:

<!-- test: test_tutorial_step5_submit_returns_focus_command -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
from plushie.commands import Command

# Inside update:
case Submit(id="new-todo", value=v) if v.strip():
    todo = Todo(id=f"todo-{model.next_id}", text=v.strip())
    new_model = replace(
        model,
        items=(*model.items, todo),
        input_value="",
        next_id=model.next_id + 1,
    )
    return new_model, Command.focus("app/new-todo")
```

Return a `(model, command)` tuple from `update` to schedule a side
effect. Commands always use the full scoped path -- the text input
is inside the `id="app"` column, so its full path is
`"app/new-todo"`.

## Step 6: filtering

Add filter controls that toggle between all, active, and completed
todos. We use radio buttons grouped by the same `id`:

<!-- test: test_tutorial_step6_filter_select -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
from plushie.events import Select

# Inside update:
case Click(id="filter-all"):
                return replace(model, filter="all")
            case Click(id="filter-active"):
                return replace(model, filter="active")
            case Click(id="filter-done"):
    return replace(model, filter=v)
```

Add the filter radios and apply the filter in the view:

<!-- test: test_tutorial_step6_view_has_filter_radios, test_tutorial_step6_view_filters_todos, test_tutorial_step6_visible_items_helper -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
def view(self, model: Model) -> dict[str, Any]:
    visible = _visible_items(model)

    return ui.window(
        "main",
        ui.column(
            ui.text("title", "My Todos", size=24),
            ui.text_input(
                "new-todo",
                model.input_value,
                placeholder="What needs doing?",
                on_submit=True,
            ),
            ui.row(
                ui.radio("filter", "all", model.filter, label="All"),
                ui.radio("filter", "active", model.filter, label="Active"),
                ui.radio("filter", "done", model.filter, label="Done"),
                spacing=8,
            ),
            ui.column(
                *(_todo_row(item) for item in visible),
                id="list",
                spacing=4,
            ),
            id="app",
            padding=20,
            spacing=12,
            width="fill",
        ),
        title="Todos",
    )


def _visible_items(model: Model) -> tuple[Todo, ...]:
    match model.filter:
        case "active":
            return tuple(item for item in model.items if not item.done)
        case "done":
            return tuple(item for item in model.items if item.done)
        case _:
            return model.items
```

Notice `_todo_row()` and `_visible_items()` are extracted as
standalone helper functions. In Python, view helpers are just regular
functions that return `ui.*` node dicts.

## The complete app

The full source is in
[`examples/todo.py`](https://github.com/plushie-ui/plushie-python/blob/main/examples/todo.py)
with tests in
[`tests/integration/test_todo.py`](https://github.com/plushie-ui/plushie-python/blob/main/tests/integration/test_todo.py).

<!-- test: test_tutorial_complete_app_init, test_tutorial_complete_app_full_workflow -- keep this code block in sync with tests/docs/test_tutorial.py -->

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.commands import Command
from plushie.events import Click, Select, Submit, Toggle


@dataclass(frozen=True, slots=True)
class Todo:
    id: str
    text: str
    done: bool = False


@dataclass(frozen=True, slots=True)
class Model:
    items: tuple[Todo, ...] = ()
    input_value: str = ""
    filter: str = "all"
    next_id: int = 1


def _visible_items(model: Model) -> tuple[Todo, ...]:
    match model.filter:
        case "active":
            return tuple(item for item in model.items if not item.done)
        case "done":
            return tuple(item for item in model.items if item.done)
        case _:
            return model.items


def _todo_row(item: Todo) -> dict[str, Any]:
    return ui.container(
        item.id,
        ui.row(
            ui.checkbox("toggle", item.done, label=item.text),
            ui.button("delete", "x"),
            spacing=8,
        ),
    )


class TodoApp(plushie.App[Model]):
    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model | tuple[Model, Command]:
        match event:
            case plushie.Input(id="new-todo", value=v):
                return replace(model, input_value=v)

            case Submit(id="new-todo", value=v) if v.strip():
                todo = Todo(id=f"todo-{model.next_id}", text=v.strip())
                new_model = replace(
                    model,
                    items=(*model.items, todo),
                    input_value="",
                    next_id=model.next_id + 1,
                )
                return new_model, Command.focus("app/new-todo")

            case Toggle(id="toggle", scope=(item_id, *_)):
                items = tuple(
                    replace(item, done=not item.done) if item.id == item_id else item
                    for item in model.items
                )
                return replace(model, items=items)

            case Click(id="delete", scope=(item_id, *_)):
                items = tuple(item for item in model.items if item.id != item_id)
                return replace(model, items=items)

            case Click(id="filter-all"):
                return replace(model, filter="all")
            case Click(id="filter-active"):
                return replace(model, filter="active")
            case Click(id="filter-done"):
                return replace(model, filter=v)

            case _:
                return model

    def view(self, model: Model) -> dict[str, Any]:
        visible = _visible_items(model)

        return ui.window(
            "main",
            ui.column(
                ui.text("title", "My Todos", size=24),
                ui.text_input(
                    "new-todo",
                    model.input_value,
                    placeholder="What needs doing?",
                    on_submit=True,
                ),
                ui.row(
                    ui.radio("filter", "all", model.filter, label="All"),
                    ui.radio("filter", "active", model.filter, label="Active"),
                    ui.radio("filter", "done", model.filter, label="Done"),
                    spacing=8,
                ),
                ui.column(
                    *(_todo_row(item) for item in visible),
                    id="list",
                    spacing=4,
                ),
                id="app",
                padding=20,
                spacing=12,
                width="fill",
            ),
            title="Todos",
        )


if __name__ == "__main__":
    plushie.run(TodoApp)
```

## What you've learned

- **Text inputs** with `on_submit=True` for form-like behavior
- **Scoped IDs** via named containers (`ui.container(item.id, ...)`)
- **Scope binding** in update (`scope=(item_id, *_)`)
- **Commands** for side effects (`Command.focus()` with scoped paths)
- **Conditional rendering** with filter functions
- **View helpers** extracted as standalone functions

## Next steps

- [Commands](commands.md) -- async work, file dialogs, timers
- [Scoped IDs](scoped-ids.md) -- full scoping reference
- [Composition patterns](composition-patterns.md) -- scaling beyond
  a single module
- [Testing](testing.md) -- unit and integration testing
