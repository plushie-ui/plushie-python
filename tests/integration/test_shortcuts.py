"""Integration test for the Shortcuts example app.

Runs the Shortcuts app through the real plushie renderer binary.
KeyEvent events come from subscriptions which aren't fired by the
mock renderer, so we test init state and view structure only.
"""

from __future__ import annotations

import pytest
from examples.shortcuts import Model, Shortcuts

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the Shortcuts app."""
    with AppFixture(Shortcuts, plushie_pool) as fixture:
        yield fixture


class TestShortcutsIntegration:
    """End-to-end tests for the Shortcuts example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """Log starts empty with zero count."""
        assert app.model.log == ()
        assert app.model.count == 0

    def test_header_text(self, app: AppFixture[Model]) -> None:
        """Header text is present."""
        assert app.text("#header") == "Press any key"

    def test_count_text(self, app: AppFixture[Model]) -> None:
        """Count text reflects zero key events."""
        assert app.text("#count") == "0 key events captured"

    def test_scrollable_log_exists(self, app: AppFixture[Model]) -> None:
        """The scrollable log container exists."""
        assert app.exists("#log")

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The main window node exists."""
        assert app.exists("#main")
