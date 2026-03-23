"""Integration test for the Todo example app.

Runs the Todo app through the real plushie renderer binary. Tests
scoped IDs, dynamic list rendering, text input, toggle, delete,
and filter functionality.
"""

from __future__ import annotations

import pytest
from examples.todo import Model, TodoApp

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the Todo app."""
    with AppFixture(TodoApp, plushie_pool) as fixture:
        yield fixture


class TestTodoIntegration:
    """End-to-end tests for the Todo example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """Todo app starts with empty list."""
        assert len(app.model.items) == 0
        assert app.model.input_value == ""

    def test_add_todo(self, app: AppFixture[Model]) -> None:
        """Can add a todo via text input and submit."""
        app.type_text("#new-todo", "Buy milk")
        app.submit("#new-todo")
        assert len(app.model.items) == 1
        assert app.model.items[0].text == "Buy milk"
        assert app.model.input_value == ""

    def test_add_multiple_todos(self, app: AppFixture[Model]) -> None:
        """Can add multiple todos."""
        app.type_text("#new-todo", "Buy milk")
        app.submit("#new-todo")
        app.type_text("#new-todo", "Walk dog")
        app.submit("#new-todo")
        assert len(app.model.items) == 2

    def test_toggle_todo(self, app: AppFixture[Model]) -> None:
        """Can toggle a todo's done state via scoped ID."""
        app.type_text("#new-todo", "Buy milk")
        app.submit("#new-todo")
        item_id = app.model.items[0].id

        # The todo item is inside a container with its id
        app.toggle(f"#{item_id}/done")
        assert app.model.items[0].done is True

    def test_delete_todo(self, app: AppFixture[Model]) -> None:
        """Can delete a todo via scoped ID."""
        app.type_text("#new-todo", "Buy milk")
        app.submit("#new-todo")
        item_id = app.model.items[0].id

        app.click(f"#{item_id}/delete")
        assert len(app.model.items) == 0

    def test_empty_submit_ignored(self, app: AppFixture[Model]) -> None:
        """Submitting empty text does nothing."""
        app.submit("#new-todo")
        assert len(app.model.items) == 0

    def test_filter_active(self, app: AppFixture[Model]) -> None:
        """Active filter shows only incomplete items."""
        app.type_text("#new-todo", "Task 1")
        app.submit("#new-todo")
        app.type_text("#new-todo", "Task 2")
        app.submit("#new-todo")

        item_id = app.model.items[0].id
        app.toggle(f"#{item_id}/done")

        app.click("#filter-active")
        assert app.model.filter == "active"

    def test_filter_done(self, app: AppFixture[Model]) -> None:
        """Done filter shows only completed items."""
        app.type_text("#new-todo", "Task 1")
        app.submit("#new-todo")

        item_id = app.model.items[0].id
        app.toggle(f"#{item_id}/done")

        app.click("#filter-done")
        assert app.model.filter == "done"
