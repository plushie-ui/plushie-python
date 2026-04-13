"""Tests mirroring the tutorial (building a todo app) code examples.

<!-- test: test_tutorial_step1_init, test_tutorial_step1_view
     -- keep the tutorial step 1 code block in sync with these tests -->

<!-- test: test_tutorial_step2_input_updates_model, test_tutorial_step2_submit_creates_todo,
     test_tutorial_step2_empty_submit_does_nothing
     -- keep the tutorial step 2 code blocks in sync with these tests -->

<!-- test: test_tutorial_step3_view_renders_todo_list, test_tutorial_step3_todo_row_structure,
     test_tutorial_step2_view_has_text_input
     -- keep the tutorial step 3 code blocks in sync with these tests -->

<!-- test: test_tutorial_step4_toggle, test_tutorial_step4_delete
     -- keep the tutorial step 4 code block in sync with these tests -->

<!-- test: test_tutorial_step5_submit_returns_focus_command
     -- keep the tutorial step 5 code block in sync with these tests -->

<!-- test: test_tutorial_step6_filter_select, test_tutorial_step6_view_has_filter_radios,
     test_tutorial_step6_view_filters_todos, test_tutorial_step6_visible_items_helper
     -- keep the tutorial step 6 code blocks in sync with these tests -->

<!-- test: test_tutorial_complete_app_init, test_tutorial_complete_app_full_workflow
     -- keep the tutorial complete app code block in sync with these tests -->
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.commands import Command
from plushie.events import Click, Select, Submit, Toggle


def _model(result: Model | tuple[Model, Command]) -> Model:
    """Narrow an update result to its model (assert not a tuple)."""
    assert isinstance(result, Model)
    return result


# -- Types reproduced from the tutorial doc --


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


# -- Helper functions from the tutorial --


def _visible_items(model: Model) -> tuple[Todo, ...]:
    match model.filter:
        case "active":
            return tuple(item for item in model.items if not item.done)
        case "done":
            return tuple(item for item in model.items if item.done)
        case _:
            return model.items


def _todo_row_step3(item: Todo) -> dict[str, Any]:
    """Step 3 version: checkbox + text + button (three children)."""
    return ui.container(
        item.id,
        ui.row(
            ui.checkbox("toggle", item.done),
            ui.text(item.text),
            ui.button("delete", "x"),
            spacing=8,
        ),
    )


def _todo_row(item: Todo) -> dict[str, Any]:
    """Complete app version: checkbox with label + button (two children)."""
    return ui.container(
        item.id,
        ui.row(
            ui.checkbox("toggle", item.done, label=item.text),
            ui.button("delete", "x"),
            spacing=8,
        ),
    )


# -- TodoApp reproduced from the tutorial --


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

            case Select(id="filter", value=v):
                return replace(model, filter=v)

            case _:
                return model

    # Step 1 view (title + placeholder only)
    def step1_view(self, model: Model) -> dict[str, Any]:
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

    # Step 3 view (input + todo list, no filters)
    def step3_view(self, model: Model) -> dict[str, Any]:
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
                    *(_todo_row_step3(item) for item in model.items),
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

    # Full view (step 6, filters + extracted helpers)
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


# -- Step 1: init and initial view --


def test_tutorial_step1_init() -> None:
    app = TodoApp()
    model = app.init()
    assert model.items == ()
    assert model.input_value == ""
    assert model.filter == "all"
    assert model.next_id == 1


def test_tutorial_step1_view() -> None:
    app = TodoApp()
    model = app.init()
    tree = app.step1_view(model)

    assert tree["type"] == "window"
    assert tree["id"] == "main"
    assert tree["props"]["title"] == "Todos"

    children = tree["children"]
    assert len(children) == 1
    column = children[0]
    assert column["type"] == "column"
    assert column["id"] == "app"
    assert column["props"]["spacing"] == 12
    assert column["props"]["width"] == "fill"

    col_children = column["children"]
    assert len(col_children) == 2
    title = col_children[0]
    empty = col_children[1]
    assert title["type"] == "text"
    assert title["props"]["content"] == "My Todos"
    assert title["props"]["size"] == 24
    assert empty["type"] == "text"
    assert empty["props"]["content"] == "No todos yet"


# -- Step 2: input handling --


def test_tutorial_step2_input_updates_model() -> None:
    app = TodoApp()
    model = app.init()
    model = _model(app.update(model, plushie.Input(id="new-todo", value="Buy milk")))
    assert model.input_value == "Buy milk"


def test_tutorial_step2_submit_creates_todo() -> None:
    app = TodoApp()
    model = app.init()
    model = _model(app.update(model, plushie.Input(id="new-todo", value="Buy milk")))
    result = app.update(model, Submit(id="new-todo", value="Buy milk"))

    assert isinstance(result, tuple)
    new_model, cmd = result
    assert new_model.input_value == ""
    assert new_model.next_id == 2
    assert len(new_model.items) == 1
    assert new_model.items[0].text == "Buy milk"
    assert new_model.items[0].id == "todo-1"
    assert new_model.items[0].done is False
    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "focus"


def test_tutorial_step2_empty_submit_does_nothing() -> None:
    app = TodoApp()
    model = app.init()
    model = _model(app.update(model, plushie.Input(id="new-todo", value="   ")))
    result = _model(app.update(model, Submit(id="new-todo", value="   ")))
    assert result == model
    assert result.items == ()


def test_tutorial_step2_view_has_text_input() -> None:
    app = TodoApp()
    model = Model(input_value="Hello")
    tree = app.step3_view(model)

    column = tree["children"][0]
    col_children = column["children"]
    # title, text_input, list column
    assert len(col_children) == 3
    text_input = col_children[1]
    assert text_input["type"] == "text_input"
    assert text_input["id"] == "new-todo"
    assert text_input["props"]["value"] == "Hello"
    assert text_input["props"]["placeholder"] == "What needs doing?"
    assert text_input["props"]["on_submit"] is True


# -- Step 3: rendering the list with scoped IDs --


def test_tutorial_step3_view_renders_todo_list() -> None:
    app = TodoApp()
    model = Model(
        items=(
            Todo(id="todo-1", text="Buy milk"),
            Todo(id="todo-2", text="Walk dog", done=True),
        ),
        next_id=3,
    )
    tree = app.step3_view(model)

    column = tree["children"][0]
    list_col = column["children"][2]
    assert list_col["type"] == "column"
    assert list_col["id"] == "list"
    assert list_col["props"]["spacing"] == 4

    list_children = list_col["children"]
    assert len(list_children) == 2
    assert list_children[0]["id"] == "todo-1"
    assert list_children[0]["type"] == "container"
    assert list_children[1]["id"] == "todo-2"


def test_tutorial_step3_todo_row_structure() -> None:
    app = TodoApp()
    model = Model(items=(Todo(id="todo-1", text="Buy milk"),), next_id=2)
    tree = app.step3_view(model)

    column = tree["children"][0]
    list_col = column["children"][2]
    container = list_col["children"][0]
    assert container["type"] == "container"
    assert container["id"] == "todo-1"

    row_children = container["children"]
    assert len(row_children) == 1
    inner_row = row_children[0]
    assert inner_row["type"] == "row"
    assert inner_row["props"]["spacing"] == 8

    items = inner_row["children"]
    assert len(items) == 3
    cb = items[0]
    text_node = items[1]
    btn = items[2]
    assert cb["type"] == "checkbox"
    assert cb["id"] == "toggle"
    assert cb["props"]["checked"] is False
    assert text_node["type"] == "text"
    assert text_node["props"]["content"] == "Buy milk"
    assert btn["type"] == "button"
    assert btn["id"] == "delete"
    assert btn["props"]["label"] == "x"


# -- Step 4: toggle and delete --


def test_tutorial_step4_toggle() -> None:
    app = TodoApp()
    model = Model(items=(Todo(id="todo-1", text="Buy milk"),), next_id=2)
    model = _model(
        app.update(
            model, Toggle(id="toggle", value=True, scope=("todo-1", "list", "app"))
        )
    )
    assert len(model.items) == 1
    assert model.items[0].done is True


def test_tutorial_step4_delete() -> None:
    app = TodoApp()
    model = Model(items=(Todo(id="todo-1", text="Buy milk"),), next_id=2)
    model = _model(
        app.update(model, Click(id="delete", scope=("todo-1", "list", "app")))
    )
    assert model.items == ()


# -- Step 5: submit returns focus command --


def test_tutorial_step5_submit_returns_focus_command() -> None:
    app = TodoApp()
    model = Model(input_value="Buy milk")
    result = app.update(model, Submit(id="new-todo", value="Buy milk"))

    assert isinstance(result, tuple)
    _, cmd = result
    assert cmd == Command.focus("app/new-todo")


# -- Step 6: filtering --


def test_tutorial_step6_filter_select() -> None:
    app = TodoApp()
    model = app.init()
    model = _model(app.update(model, Select(id="filter", value="active")))
    assert model.filter == "active"
    model = _model(app.update(model, Select(id="filter", value="all")))
    assert model.filter == "all"
    model = _model(app.update(model, Select(id="filter", value="done")))
    assert model.filter == "done"


def test_tutorial_step6_view_has_filter_radios() -> None:
    app = TodoApp()
    model = app.init()
    tree = app.view(model)

    column = tree["children"][0]
    col_children = column["children"]
    # title, text_input, filter row, list column
    assert len(col_children) == 4
    filters = col_children[2]
    assert filters["type"] == "row"

    radio_children = filters["children"]
    assert len(radio_children) == 3
    assert radio_children[0]["id"] == "filter"
    assert radio_children[0]["props"]["value"] == "all"
    assert radio_children[0]["props"]["label"] == "All"
    assert radio_children[1]["props"]["value"] == "active"
    assert radio_children[1]["props"]["label"] == "Active"
    assert radio_children[2]["props"]["value"] == "done"
    assert radio_children[2]["props"]["label"] == "Done"


def test_tutorial_step6_view_filters_todos() -> None:
    app = TodoApp()
    model = Model(
        items=(
            Todo(id="todo-1", text="Buy milk"),
            Todo(id="todo-2", text="Walk dog", done=True),
        ),
        filter="active",
        next_id=3,
    )
    tree = app.view(model)

    column = tree["children"][0]
    list_col = column["children"][3]
    list_children = list_col["children"]

    # Only active todo should appear
    assert len(list_children) == 1
    assert list_children[0]["id"] == "todo-1"


def test_tutorial_step6_visible_items_helper() -> None:
    model = Model(
        items=(
            Todo(id="todo-1", text="Buy milk"),
            Todo(id="todo-2", text="Walk dog", done=True),
            Todo(id="todo-3", text="Read book"),
        ),
        next_id=4,
    )

    assert len(_visible_items(model)) == 3
    assert len(_visible_items(replace(model, filter="active"))) == 2
    assert len(_visible_items(replace(model, filter="done"))) == 1


# -- Complete app: end-to-end workflow --


def test_tutorial_complete_app_init() -> None:
    app = TodoApp()
    model = app.init()
    tree = app.view(model)

    # Renders without error, has the expected top-level shape
    assert tree["type"] == "window"
    column = tree["children"][0]
    assert len(column["children"]) == 4


def test_tutorial_complete_app_full_workflow() -> None:
    app = TodoApp()
    m = app.init()

    # Add a todo
    m = _model(app.update(m, plushie.Input(id="new-todo", value="Buy milk")))
    result = app.update(m, Submit(id="new-todo", value="Buy milk"))
    assert isinstance(result, tuple)
    m, _ = result

    # Add another
    m = _model(app.update(m, plushie.Input(id="new-todo", value="Walk dog")))
    result = app.update(m, Submit(id="new-todo", value="Walk dog"))
    assert isinstance(result, tuple)
    m, _ = result

    assert len(m.items) == 2
    assert m.items[0].text == "Buy milk"
    assert m.items[1].text == "Walk dog"

    # Toggle first item done
    m = _model(
        app.update(
            m,
            Toggle(id="toggle", value=True, scope=("todo-1", "list", "app")),
        )
    )
    assert m.items[0].done is True

    # Filter to active only
    m = _model(app.update(m, Select(id="filter", value="active")))
    tree = app.view(m)
    column = tree["children"][0]
    list_col = column["children"][3]
    assert len(list_col["children"]) == 1
    assert list_col["children"][0]["id"] == "todo-2"

    # Delete the remaining active item
    m = _model(
        app.update(
            m,
            Click(id="delete", scope=("todo-2", "list", "app")),
        )
    )
    assert len(m.items) == 1

    # Switch to done filter, see the completed item
    m = _model(app.update(m, Select(id="filter", value="done")))
    tree = app.view(m)
    column = tree["children"][0]
    list_col = column["children"][3]
    assert len(list_col["children"]) == 1
    assert list_col["children"][0]["id"] == "todo-1"
