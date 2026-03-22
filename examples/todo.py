"""Todo app -- demonstrates dynamic lists, scoped IDs, and commands.

Features exercised:

- Text input with submit (Enter key)
- Scoped IDs: each todo item lives in a named container, so toggle
  and delete events carry the item's ID in their scope
- Dynamic list rendering with a generator expression
- Toggle (checkbox) and delete (button) per item
- Filter tabs (all / active / done) using radio buttons
- ``Command.focus`` to return focus to the input after adding an item
- Frozen dataclass model with ``tuple[Todo, ...]`` for the item list

Run::

    python -m plushie run examples.todo:TodoApp
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.commands import Command
from plushie.events import Click, Select, Submit, Toggle


@dataclass(frozen=True, slots=True)
class Todo:
    """A single todo item."""

    id: str
    text: str
    done: bool = False


@dataclass(frozen=True, slots=True)
class Model:
    """Todo app model."""

    items: tuple[Todo, ...] = ()
    input_value: str = ""
    filter: str = "all"
    next_id: int = 1


def _visible_items(model: Model) -> tuple[Todo, ...]:
    """Return items matching the current filter."""
    match model.filter:
        case "active":
            return tuple(item for item in model.items if not item.done)
        case "done":
            return tuple(item for item in model.items if item.done)
        case _:
            return model.items


class TodoApp(plushie.App[Model]):
    """A todo list with filtering and scoped item interactions."""

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
                return new_model, Command.focus("new-todo")

            case Toggle(id="done", scope=(item_id, *_)):
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

    def view(self, model: Model) -> dict[str, Any]:
        visible = _visible_items(model)

        return ui.window(
            "main",
            ui.column(
                ui.text("title", "Todo"),
                ui.text_input(
                    "new-todo",
                    model.input_value,
                    placeholder="What needs to be done?",
                    on_submit=True,
                ),
                ui.row(
                    ui.radio("filter-all", "all", model.filter, label="All"),
                    ui.radio("filter-active", "active", model.filter, label="Active"),
                    ui.radio("filter-done", "done", model.filter, label="Done"),
                    spacing=12,
                ),
                *(_todo_item(item) for item in visible),
                padding=16,
                spacing=8,
            ),
            title="Todo",
        )


def _todo_item(item: Todo) -> dict[str, Any]:
    """Render a single todo item inside a scoped container."""
    return ui.container(
        item.id,
        ui.row(
            ui.checkbox("done", item.done, label=item.text),
            ui.button("delete", "x"),
            spacing=8,
        ),
    )


if __name__ == "__main__":
    plushie.run(TodoApp)
