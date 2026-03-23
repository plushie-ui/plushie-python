"""Tests for code examples in docs/app.md.

Each test corresponds to an HTML test marker comment in the doc.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from plushie import ui
from plushie.commands import Command
from plushie.events import (
    Click,
    Input,
    Submit,
    WindowCloseRequested,
    WindowFocused,
    WindowResized,
)
from plushie.subscriptions import Subscription

# -- Helpers -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Todo:
    id: str
    text: str
    done: bool = False


@dataclass(frozen=True, slots=True)
class Model:
    todos: tuple[Todo, ...] = ()
    input_value: str = ""
    filter: str = "all"
    loading: bool = False
    auto_refresh: bool = False
    inspector_open: bool = True
    window_size: tuple[float, float] = (0.0, 0.0)
    active_window: str | None = None
    confirm_dialog: bool = False
    unsaved_changes: bool = False
    confirm_exit: bool = False
    settings_open: bool = False


_next_id = 0


def next_id() -> str:
    global _next_id
    _next_id += 1
    return str(_next_id)


def filtered_todos(model: Model) -> tuple[Todo, ...]:
    return model.todos


# -- init examples -----------------------------------------------------------


class TestInitBareModel:
    def test_init_bare_model(self) -> None:
        """Docs: init returning a bare model."""
        model = Model(
            todos=(),
            input_value="",
            filter="all",
        )
        assert model.todos == ()
        assert model.input_value == ""
        assert model.filter == "all"


def _load_todos_from_disk() -> str:
    return "loaded"


class TestInitWithCommand:
    def test_init_with_command(self) -> None:
        """Docs: init returning (model, command)."""
        model = Model(todos=(), loading=True)
        cmd = Command.task(_load_todos_from_disk, "todos_loaded")
        result = (model, cmd)

        assert result[0].loading is True
        assert result[0].todos == ()
        assert result[1].type == "task"
        assert result[1].payload["tag"] == "todos_loaded"


# -- update examples ---------------------------------------------------------


def update(model: Model, event: object) -> Model | tuple[Model, Command]:
    match event:
        case Click(id="add_todo"):
            todo = Todo(id=next_id(), text=model.input_value)
            return replace(model, todos=(*model.todos, todo), input_value="")

        case Input(id="todo_field", value=v):
            return replace(model, input_value=v)

        case Submit(id="todo_field", value=v) if v.strip():
            todo = Todo(id=next_id(), text=v.strip())
            new_model = replace(model, todos=(*model.todos, todo), input_value="")
            return new_model, Command.focus("todo_field")

        case _:
            return model


class TestUpdateModelChange:
    def test_update_input_changes_model(self) -> None:
        """Docs: update with Input changes input_value."""
        model = Model()
        result = update(model, Input(id="todo_field", value="Buy milk"))
        assert isinstance(result, Model)
        assert result.input_value == "Buy milk"

    def test_update_add_todo(self) -> None:
        """Docs: update with Click adds a todo and clears input."""
        model = Model(input_value="Buy milk")
        result = update(model, Click(id="add_todo"))
        assert isinstance(result, Model)
        assert result.input_value == ""
        assert len(result.todos) == 1
        assert result.todos[0].text == "Buy milk"

    def test_update_unknown_event(self) -> None:
        """Docs: catch-all returns model unchanged."""
        model = Model()
        result = update(model, Click(id="unknown"))
        assert result is model


class TestUpdateCommandReturn:
    def test_update_submit_returns_focus_command(self) -> None:
        """Docs: update returning (model, command)."""
        model = Model(input_value="Walk dog")
        result = update(model, Submit(id="todo_field", value="Walk dog"))
        assert isinstance(result, tuple)
        new_model, cmd = result
        assert new_model.input_value == ""
        assert len(new_model.todos) == 1
        assert new_model.todos[0].text == "Walk dog"
        assert cmd == Command.focus("todo_field")


# -- view example ------------------------------------------------------------


class TestViewTreeStructure:
    def test_view_basic_structure(self) -> None:
        """Docs: view returns a well-formed UI tree."""
        model = Model(
            input_value="Buy milk",
            todos=(Todo(id="todo_1", text="Walk dog"),),
        )
        tree = ui.window(
            "main",
            ui.column(
                ui.row(
                    ui.text_input(
                        "todo_field", model.input_value, placeholder="What needs doing?"
                    ),
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

        assert tree["type"] == "window"
        assert tree["id"] == "main"
        assert tree["props"]["title"] == "Todos"

        children = tree["children"]
        assert len(children) == 1
        col = children[0]
        assert col["type"] == "column"

        col_children = col["children"]
        assert len(col_children) == 2  # input row + 1 todo row

        input_row = col_children[0]
        assert input_row["type"] == "row"
        assert input_row["children"][0]["type"] == "text_input"
        assert input_row["children"][0]["props"]["value"] == "Buy milk"
        assert input_row["children"][1]["type"] == "button"
        assert input_row["children"][1]["props"]["label"] == "Add"

        todo_row = col_children[1]
        assert todo_row["type"] == "row"
        assert todo_row["id"] == "todo_1"


# -- subscribe example -------------------------------------------------------


def subscribe(model: Model) -> list[Subscription]:
    subs = [Subscription.on_key_press("key_event")]

    if model.auto_refresh:
        subs.append(Subscription.every(5000, "refresh"))

    return subs


class TestSubscribe:
    def test_subscribe_without_auto_refresh(self) -> None:
        """Docs: subscribe returns key_press only when auto_refresh is off."""
        model = Model(auto_refresh=False)
        subs = subscribe(model)
        assert len(subs) == 1
        assert subs[0] == Subscription.on_key_press("key_event")

    def test_subscribe_with_auto_refresh(self) -> None:
        """Docs: subscribe adds timer when auto_refresh is on."""
        model = Model(auto_refresh=True)
        subs = subscribe(model)
        assert len(subs) == 2
        assert subs[0] == Subscription.on_key_press("key_event")
        assert subs[1] == Subscription.every(5000, "refresh")


# -- window_config example --------------------------------------------------


class TestWindowConfig:
    def test_window_config_returns_dict(self) -> None:
        """Docs: window_config returns a config dict."""
        config: dict[str, Any] = {
            "title": "My App",
            "width": 800,
            "height": 600,
            "min_size": {"width": 400, "height": 300},
            "resizable": True,
            "theme": "dark",
        }
        assert config["title"] == "My App"
        assert config["width"] == 800
        assert config["height"] == 600
        assert config["resizable"] is True
        assert config["theme"] == "dark"


# -- settings example --------------------------------------------------------


class TestSettings:
    def test_settings_returns_dict(self) -> None:
        """Docs: settings returns a settings dict."""
        settings: dict[str, Any] = {
            "default_font": {"family": "monospace"},
            "default_text_size": 16,
            "antialiasing": True,
            "fonts": ["assets/fonts/Inter.ttf"],
        }
        assert settings["default_text_size"] == 16
        assert settings["antialiasing"] is True
        assert settings["fonts"] == ["assets/fonts/Inter.ttf"]
        assert settings["default_font"] == {"family": "monospace"}


# -- multi-window: view returning list of windows ---------------------------


class TestMultiWindowViewList:
    def test_multi_window_view_returns_list(self) -> None:
        """Docs: view returns a list of window nodes."""
        model = Model(inspector_open=True)

        def main_content(_m: Model) -> dict[str, Any]:
            return ui.text("hello")

        def inspector_panel(_m: Model) -> dict[str, Any]:
            return ui.text("inspector")

        windows: list[dict[str, Any]] = [
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

        assert len(windows) == 2
        assert windows[0]["id"] == "main"
        assert windows[1]["id"] == "inspector"
        assert windows[1]["props"]["title"] == "Inspector"
        assert windows[1]["props"]["size"] == (400, 600)


# -- multi-window: window events --------------------------------------------


class TestWindowEvents:
    def test_window_close_requested(self) -> None:
        """Docs: WindowCloseRequested match."""
        model = Model(inspector_open=True)
        event = WindowCloseRequested(window_id="inspector")

        match event:
            case WindowCloseRequested(window_id="inspector"):
                model = replace(model, inspector_open=False)

        assert model.inspector_open is False

    def test_window_resized(self) -> None:
        """Docs: WindowResized match updates window_size."""
        model = Model()
        event = WindowResized(window_id="main", width=1024.0, height=768.0)

        match event:
            case WindowResized(window_id="main", width=w, height=h):
                model = replace(model, window_size=(w, h))

        assert model.window_size == (1024.0, 768.0)

    def test_window_focused(self) -> None:
        """Docs: WindowFocused match updates active_window."""
        model = Model()
        event = WindowFocused(window_id="editor")

        match event:
            case WindowFocused(window_id=wid):
                model = replace(model, active_window=wid)

        assert model.active_window == "editor"

    def test_window_close_main_unsaved(self) -> None:
        """Docs: close main window with unsaved changes."""
        model = Model(unsaved_changes=True)
        event = WindowCloseRequested(window_id="main")

        result: Model | tuple[Model, Command] = model
        match event:
            case WindowCloseRequested(window_id="main"):
                if model.unsaved_changes:
                    result = replace(model, confirm_exit=True)
                else:
                    result = model, Command.close_window("main")

        assert isinstance(result, Model)
        assert result.confirm_exit is True

    def test_window_close_main_saved(self) -> None:
        """Docs: close main window when no unsaved changes."""
        model = Model(unsaved_changes=False)
        event = WindowCloseRequested(window_id="main")

        result: Model | tuple[Model, Command] = model
        match event:
            case WindowCloseRequested(window_id="main"):
                if model.unsaved_changes:
                    result = replace(model, confirm_exit=True)
                else:
                    result = model, Command.close_window("main")

        assert isinstance(result, tuple)
        _, cmd = result
        assert cmd.type == "widget_op"
        assert cmd.payload["op"] == "close_window"

    def test_set_window_mode_command(self) -> None:
        """Docs: Command.set_window_mode produces a window_op command."""
        cmd = Command.set_window_mode("main", "fullscreen")
        assert cmd.type == "window_op"
        assert cmd.payload["window_id"] == "main"
        assert cmd.payload["mode"] == "fullscreen"


# -- multi-window: dialog example -------------------------------------------


class TestDialogWindow:
    def test_dialog_window_tree(self) -> None:
        """Docs: dialog window with confirm/cancel buttons."""

        def main_content(_m: Model) -> dict[str, Any]:
            return ui.text("main")

        model = Model(confirm_dialog=True)
        main = ui.window("main", main_content(model), title="App")

        result: list[dict[str, Any]] | dict[str, Any]
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
            result = [main, dialog]
        else:
            result = main

        assert isinstance(result, list)
        assert len(result) == 2
        dialog_node = result[1]
        assert dialog_node["id"] == "confirm"
        assert dialog_node["props"]["title"] == "Confirm"

        col = dialog_node["children"][0]
        prompt = col["children"][0]
        assert prompt["props"]["content"] == "Are you sure?"

        btns_row = col["children"][1]
        assert btns_row["children"][0]["props"]["label"] == "Yes"
        assert btns_row["children"][1]["props"]["label"] == "No"
