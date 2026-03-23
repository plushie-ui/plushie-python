"""Notes -- state helpers composition example.

Demonstrates all five state helpers working together:

- ``State`` for nested state management with path-based access
- ``UndoStack`` for reversible edits on title and body
- ``Selection`` for multi-select with toggle
- ``Route`` for stack-based view navigation (/list vs /edit)
- ``query()`` for full-text search across note fields

Run::

    python -m plushie run examples.notes:Notes
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.commands import Command
from plushie.data import query
from plushie.events import Click, Input, Toggle
from plushie.route import Route
from plushie.selection import Selection
from plushie.state import State
from plushie.undo import UndoCommand, UndoStack


@dataclass(frozen=True, slots=True)
class NoteData:
    """Undo-tracked editor state for a single note."""

    title: str = ""
    text: str = ""


@dataclass(slots=True)
class Model:
    """Notes app model.

    Uses ``slots=True`` without ``frozen=True`` because ``State`` is
    mutable (it tracks revisions internally). The rest of the fields
    are immutable dataclasses replaced via ``dataclasses.replace`` on
    the outer model... except State which mutates in place.
    """

    state: State
    selection: Selection
    undo: UndoStack
    route: Route


def _save_current_edit(model: Model) -> Model:
    """Persist undo buffer contents back into the notes list."""
    editing_id = model.state.get(["editing_id"])
    if editing_id is None:
        return model

    current: NoteData = model.undo.current

    def update_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {**n, "title": current.title, "body": current.text}
            if n["id"] == editing_id
            else n
            for n in notes
        ]

    model.state.update(["notes"], update_notes)
    return model


class Notes(plushie.App[Model]):
    """Notes app combining State, Undo, Selection, Route, and Data query."""

    def init(self) -> Model:
        return Model(
            state=State.new(
                {
                    "notes": [],
                    "next_id": 1,
                    "search_query": "",
                    "editing_id": None,
                }
            ),
            selection=Selection.new(mode="multi"),
            undo=UndoStack.new(NoteData()),
            route=Route.new("/list"),
        )

    def update(self, model: Model, event: object) -> Model | tuple[Model, Command]:
        match event:
            # -- List view ------------------------------------------------
            case Click(id="new_note"):
                note_id = model.state.get(["next_id"])
                note = {"id": note_id, "title": "", "body": ""}
                model.state.update(["notes"], lambda ns: [*ns, note])
                model.state.put(["next_id"], note_id + 1)
                model.state.put(["editing_id"], note_id)
                return replace(
                    model,
                    undo=UndoStack.new(NoteData()),
                    route=model.route.push("/edit"),
                )

            case Click(id=click_id) if click_id.startswith("note:"):
                note_id = int(click_id.removeprefix("note:"))
                notes: list[dict[str, Any]] = model.state.get(["notes"])
                note = next((n for n in notes if n["id"] == note_id), None)
                if note is None:
                    return model
                model.state.put(["editing_id"], note_id)
                return replace(
                    model,
                    undo=UndoStack.new(
                        NoteData(title=note["title"], text=note["body"])
                    ),
                    route=model.route.push("/edit"),
                )

            case Click(id="delete_selected"):
                selected = model.selection.selected()
                model.state.update(
                    ["notes"],
                    lambda ns: [n for n in ns if n["id"] not in selected],
                )
                return replace(model, selection=model.selection.clear())

            case Input(id="search", value=q):
                model.state.put(["search_query"], q)
                return model

            case Toggle(id=tid) if tid.startswith("note_select:"):
                note_id = int(tid.removeprefix("note_select:"))
                return replace(model, selection=model.selection.toggle(note_id))

            # -- Edit view ------------------------------------------------
            case Click(id="back"):
                model = _save_current_edit(model)
                model.state.put(["editing_id"], None)
                return replace(model, route=model.route.pop())

            case Input(id="title", value=v):
                old_title = model.undo.current.title
                cmd = UndoCommand(
                    apply_fn=lambda cur, _v=v: replace(cur, title=_v),
                    undo_fn=lambda cur, _t=old_title: replace(cur, title=_t),
                    label="edit title",
                )
                return replace(model, undo=model.undo.apply_command(cmd))

            case Input(id="body", value=v):
                old_text = model.undo.current.text
                cmd = UndoCommand(
                    apply_fn=lambda cur, _v=v: replace(cur, text=_v),
                    undo_fn=lambda cur, _t=old_text: replace(cur, text=_t),
                    label="edit body",
                )
                return replace(model, undo=model.undo.apply_command(cmd))

            case Click(id="undo"):
                return replace(model, undo=model.undo.undo())

            case Click(id="redo"):
                return replace(model, undo=model.undo.redo())

            case _:
                return model

    def view(self, model: Model) -> dict[str, Any]:
        match model.route.current():
            case "/list":
                return _view_list(model)
            case "/edit":
                return _view_edit(model)
            case _:
                return _view_list(model)


def _view_list(model: Model) -> dict[str, Any]:
    search_query: str = model.state.get(["search_query"])
    notes: list[dict[str, Any]] = model.state.get(["notes"])

    if search_query:
        # Convert notes dicts to the format query() expects
        result = query(notes, search=(["title", "body"], search_query))
        filtered = result.entries
    else:
        filtered = notes

    note_rows = [
        ui.container(
            f"note_row:{note['id']}",
            ui.row(
                ui.checkbox(
                    f"note_select:{note['id']}",
                    model.selection.is_selected(note["id"]),
                    label=note["title"] or "(untitled)",
                ),
                ui.button(f"note:{note['id']}", "Edit"),
                spacing=8,
                width="fill",
            ),
        )
        for note in filtered
    ]

    return ui.window(
        "main",
        ui.column(
            ui.text("heading", "Notes", size=24),
            ui.text_input("search", search_query, placeholder="Search notes..."),
            ui.scrollable(
                "notes_list",
                ui.column(*note_rows, spacing=4, width="fill"),
                height="fill",
            ),
            ui.row(
                ui.button("new_note", "New Note"),
                ui.button("delete_selected", "Delete Selected"),
                spacing=8,
            ),
            padding=16,
            spacing=12,
            width="fill",
        ),
        title="Notes",
    )


def _view_edit(model: Model) -> dict[str, Any]:
    current: NoteData = model.undo.current

    return ui.window(
        "main",
        ui.column(
            ui.row(
                ui.button("back", "Back"),
                ui.button("undo", "Undo"),
                ui.button("redo", "Redo"),
                spacing=8,
            ),
            ui.text_input("title", current.title, placeholder="Note title"),
            ui.text_editor("body", current.text, width="fill", height="fill"),
            padding=16,
            spacing=12,
            width="fill",
        ),
        title="Edit Note",
    )


if __name__ == "__main__":
    plushie.run(Notes)
