"""Integration test for the Notes example app.

Runs the Notes app through the real plushie renderer binary. Tests
state helpers composition: State, UndoStack, Selection, Route, and
data query filtering.
"""

from __future__ import annotations

import pytest
from examples.notes import Model, Notes

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the Notes app."""
    with AppFixture(Notes, plushie_pool) as fixture:
        yield fixture


class TestNotesIntegration:
    """End-to-end tests for the Notes example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """Notes app starts on the list route with no notes."""
        assert app.model.route.current() == "/list"
        assert app.model.state.get(["notes"]) == []
        assert app.model.state.get(["search_query"]) == ""

    def test_initial_view(self, app: AppFixture[Model]) -> None:
        """List view contains heading and action buttons."""
        assert app.text("#heading") == "Notes"
        assert app.exists("#new_note")
        assert app.exists("#delete_selected")
        assert app.exists("#search")

    def test_create_new_note(self, app: AppFixture[Model]) -> None:
        """Clicking new_note creates a note and navigates to edit view."""
        app.click("#new_note")
        assert app.model.route.current() == "/edit"
        notes = app.model.state.get(["notes"])
        assert len(notes) == 1
        assert notes[0]["id"] == 1

    def test_edit_title(self, app: AppFixture[Model]) -> None:
        """Typing in the title field updates the undo buffer."""
        app.click("#new_note")
        app.type_text("#title", "My Note")
        assert app.model.undo.current.title == "My Note"

    def test_edit_body(self, app: AppFixture[Model]) -> None:
        """Typing in the body field updates the undo buffer."""
        app.click("#new_note")
        app.type_text("#body", "Some content")
        assert app.model.undo.current.text == "Some content"

    def test_back_saves_and_returns_to_list(self, app: AppFixture[Model]) -> None:
        """Clicking back persists edits and returns to list view."""
        app.click("#new_note")
        app.type_text("#title", "Saved Note")
        app.click("#back")
        assert app.model.route.current() == "/list"
        notes = app.model.state.get(["notes"])
        assert notes[0]["title"] == "Saved Note"

    def test_search_filtering(self, app: AppFixture[Model]) -> None:
        """Search query updates the state filter value."""
        # Create two notes with different titles
        app.click("#new_note")
        app.type_text("#title", "Alpha")
        app.click("#back")

        app.click("#new_note")
        app.type_text("#title", "Beta")
        app.click("#back")

        # Type a search query
        app.type_text("#search", "Alpha")
        assert app.model.state.get(["search_query"]) == "Alpha"

    def test_selection_toggle(self, app: AppFixture[Model]) -> None:
        """Toggling a note's checkbox updates the selection."""
        app.click("#new_note")
        app.click("#back")

        note_id = app.model.state.get(["notes"])[0]["id"]
        app.toggle(f"#note_select:{note_id}")
        assert app.model.selection.is_selected(note_id) is True

        app.toggle(f"#note_select:{note_id}")
        assert app.model.selection.is_selected(note_id) is False

    def test_undo_redo(self, app: AppFixture[Model]) -> None:
        """Undo and redo reverse and replay title edits."""
        app.click("#new_note")
        app.type_text("#title", "First")
        app.type_text("#title", "Second")
        assert app.model.undo.current.title == "Second"

        app.click("#undo")
        assert app.model.undo.current.title == "First"

        app.click("#redo")
        assert app.model.undo.current.title == "Second"

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The main window node exists."""
        assert app.exists("#main")
