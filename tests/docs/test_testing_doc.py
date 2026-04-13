"""Tests mirroring code examples from docs/testing.md.

Validates that the unit testing patterns shown in the doc produce
correct results with real plushie APIs.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from plushie import ui
from plushie.app import App
from plushie.commands import Command
from plushie.events import Click, Submit
from plushie.tree import exists, find, find_all, ids, normalize, text_of

# ---------------------------------------------------------------------------
# Fixture app used by doc examples
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class TodoModel:
    todos: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    input: str = ""
    loading: bool = False
    data: str | None = None


class MyApp(App[TodoModel]):
    def init(self) -> TodoModel:
        return TodoModel()

    def update(
        self, model: TodoModel, event: object
    ) -> TodoModel | tuple[TodoModel, Command]:
        match event:
            case Click(id="add_todo"):
                new_todos = [*model.todos, {"text": model.input, "done": False}]
                return dataclasses.replace(model, todos=new_todos, input="")
            case Submit(id="todo_input", value=text):
                new_todos = [*model.todos, {"text": text}]
                updated = dataclasses.replace(model, todos=new_todos, input="")
                return updated, Command.focus("todo_input")
            case Click(id="save"):
                return (
                    dataclasses.replace(model, loading=True),
                    Command.task(lambda: "saved", tag="save_result"),
                )
            case Click(id="fetch"):
                return (
                    dataclasses.replace(model, loading=True),
                    Command.task(lambda: [1, 2, 3], tag="data_loaded"),
                )
            case _:
                return model

    def view(self, model: TodoModel) -> dict[str, Any]:
        return ui.window(
            "main",
            ui.column(
                ui.text("todo_count", f"{len(model.todos)} items"),
                ui.text_input("todo_input", model.input),
                ui.button("add_todo", "Add"),
            ),
        )


# ---------------------------------------------------------------------------
# Testing update()
# ---------------------------------------------------------------------------


class TestUpdateExamples:
    """Doc section: Testing update()."""

    def test_adding_a_todo_appends_and_clears_input(self) -> None:
        app = MyApp()
        model = app.init()
        model = dataclasses.replace(model, todos=[], input="Buy milk")
        model_result = app.update(model, Click(id="add_todo"))

        # update returns bare model here
        assert isinstance(model_result, TodoModel)
        assert model_result.todos == [{"text": "Buy milk", "done": False}]
        assert model_result.input == ""


# ---------------------------------------------------------------------------
# Testing commands from update()
# ---------------------------------------------------------------------------


class TestCommandExamples:
    """Doc section: Testing commands from update()."""

    def test_submitting_todo_returns_focus_command(self) -> None:
        app = MyApp()
        model = dataclasses.replace(app.init(), todos=[], input="Buy milk")
        result = app.update(model, Submit(id="todo_input", value="Buy milk"))

        assert isinstance(result, tuple)
        model_out, cmd = result
        assert model_out.todos == [{"text": "Buy milk"}]
        assert cmd.type == "widget_op"
        assert cmd.payload["target"] == "todo_input"

    def test_save_triggers_async_task(self) -> None:
        app = MyApp()
        model = dataclasses.replace(app.init(), data="unsaved")
        result = app.update(model, Click(id="save"))

        assert isinstance(result, tuple)
        _model, cmd = result
        assert cmd.type == "task"
        assert cmd.payload["tag"] == "save_result"


# ---------------------------------------------------------------------------
# Testing view()
# ---------------------------------------------------------------------------


class TestViewExamples:
    """Doc section: Testing view()."""

    def test_view_shows_todo_count(self) -> None:
        app = MyApp()
        model = dataclasses.replace(
            app.init(),
            todos=[{"id": 1, "text": "Buy milk", "done": False}],
            input="",
        )
        tree = normalize(app.view(model))

        counter = find(tree, "todo_count")
        assert counter is not None
        assert "1" in (text_of(counter) or "")


# ---------------------------------------------------------------------------
# Testing init()
# ---------------------------------------------------------------------------


class TestInitExamples:
    """Doc section: Testing init()."""

    def test_init_returns_valid_initial_state(self) -> None:
        app = MyApp()
        model = app.init()

        assert isinstance(model.todos, list)
        assert model.input == ""


# ---------------------------------------------------------------------------
# Tree query helpers
# ---------------------------------------------------------------------------


class TestTreeQueryHelpers:
    """Doc section: Tree query helpers."""

    def test_find_by_id(self) -> None:
        tree = normalize(
            ui.column(
                ui.button("my_button", "Click me"),
                ui.text("label", "Hello"),
            )
        )

        assert find(tree, "my_button") is not None

    def test_exists(self) -> None:
        tree = normalize(
            ui.column(
                ui.button("my_button", "Click me"),
            )
        )

        assert exists(tree, "my_button") is True
        assert exists(tree, "missing") is False

    def test_ids(self) -> None:
        tree = normalize(
            ui.column(
                ui.button("a", "A"),
                ui.button("b", "B"),
            )
        )

        all_ids = ids(tree)
        assert "a" in all_ids
        assert "b" in all_ids

    def test_find_all_by_predicate(self) -> None:
        tree = normalize(
            ui.column(
                ui.button("a", "A"),
                ui.button("b", "B"),
                ui.text("label", "Not a button"),
            )
        )

        buttons = find_all(tree, lambda node: node["type"] == "button")
        assert len(buttons) == 2


# ---------------------------------------------------------------------------
# Async testing pattern (unit test level)
# ---------------------------------------------------------------------------


class TestAsyncPatterns:
    """Doc section: Testing async workflows: unit test level."""

    def test_clicking_fetch_starts_async_load(self) -> None:
        app = MyApp()
        model = dataclasses.replace(app.init(), loading=False, data=None)
        result = app.update(model, Click(id="fetch"))

        assert isinstance(result, tuple)
        model_out, cmd = result
        assert model_out.loading is True
        assert cmd.type == "task"
        assert cmd.payload["tag"] == "data_loaded"
