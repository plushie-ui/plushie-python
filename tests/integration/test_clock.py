"""Integration test for the Clock example app.

Runs the Clock app through the real plushie renderer binary. Validates
initial state, time display format, and start/stop toggle.
"""

from __future__ import annotations

import re

import pytest
from examples.clock import Clock, Model

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the Clock app."""
    with AppFixture(Clock, plushie_pool) as fixture:
        yield fixture


class TestClockIntegration:
    """End-to-end tests for the Clock example."""

    def test_initial_running(self, app: AppFixture[Model]) -> None:
        """Clock starts in the running state."""
        assert app.model.running is True

    def test_initial_time_format(self, app: AppFixture[Model]) -> None:
        """Initial time fields are populated from localtime."""
        assert 0 <= app.model.hours <= 23
        assert 0 <= app.model.minutes <= 59
        assert 0 <= app.model.seconds <= 59

    def test_time_display_format(self, app: AppFixture[Model]) -> None:
        """Time display uses HH:MM:SS format."""
        time_text = app.text("#time")
        assert time_text is not None
        assert re.match(r"\d{2}:\d{2}:\d{2}", time_text)

    def test_toggle_button_shows_stop_when_running(
        self, app: AppFixture[Model]
    ) -> None:
        """Toggle button reads 'Stop' when clock is running."""
        assert app.exists("#toggle")

    def test_stop_toggle(self, app: AppFixture[Model]) -> None:
        """Clicking toggle stops the clock."""
        app.click("#toggle")
        assert app.model.running is False

    def test_start_after_stop(self, app: AppFixture[Model]) -> None:
        """Clicking toggle twice restores the running state."""
        app.click("#toggle")
        assert app.model.running is False
        app.click("#toggle")
        assert app.model.running is True

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The main window node exists."""
        assert app.exists("#main")
