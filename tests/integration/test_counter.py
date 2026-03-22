"""Integration test for the Counter example app.

Runs the Counter app through the real plushie renderer binary using
the AppFixture. Validates the full cycle: init -> view -> interact ->
update -> diff -> patch.
"""

from __future__ import annotations

import pytest

# Import the example app
from examples.counter import Counter, Model

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the Counter app."""
    with AppFixture(Counter, plushie_pool) as fixture:
        yield fixture


class TestCounterIntegration:
    """End-to-end tests for the Counter example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """Counter starts at zero."""
        assert app.model.count == 0

    def test_initial_view(self, app: AppFixture[Model]) -> None:
        """Initial view contains the count text."""
        assert app.exists("#count")
        assert app.text("#count") == "Count: 0"

    def test_increment(self, app: AppFixture[Model]) -> None:
        """Clicking inc increments the counter."""
        app.click("#inc")
        assert app.model.count == 1
        assert app.text("#count") == "Count: 1"

    def test_decrement(self, app: AppFixture[Model]) -> None:
        """Clicking dec decrements the counter."""
        app.click("#dec")
        assert app.model.count == -1
        assert app.text("#count") == "Count: -1"

    def test_multiple_clicks(self, app: AppFixture[Model]) -> None:
        """Multiple clicks accumulate correctly."""
        app.click("#inc")
        app.click("#inc")
        app.click("#inc")
        app.click("#dec")
        assert app.model.count == 2
        assert app.text("#count") == "Count: 2"

    def test_buttons_exist(self, app: AppFixture[Model]) -> None:
        """Both buttons are present in the tree."""
        assert app.exists("#inc")
        assert app.exists("#dec")

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The main window node exists."""
        assert app.exists("#main")

    def test_reset(self, app: AppFixture[Model]) -> None:
        """Reset restores initial state."""
        app.click("#inc")
        app.click("#inc")
        assert app.model.count == 2
        app.reset()
        assert app.model.count == 0
