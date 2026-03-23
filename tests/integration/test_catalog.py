"""Integration test for the Catalog example app.

Runs the Catalog app through the real plushie renderer binary. Tests
tab navigation, input widgets (text, checkbox, slider), and initial
state across all four sections.
"""

from __future__ import annotations

import pytest
from examples.catalog import Catalog, Model

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the Catalog app."""
    with AppFixture(Catalog, plushie_pool) as fixture:
        yield fixture


class TestCatalogIntegration:
    """End-to-end tests for the Catalog example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """Catalog starts on the layout tab with default values."""
        assert app.model.active_tab == "layout"
        assert app.model.text_value == ""
        assert app.model.checkbox_checked is False
        assert app.model.slider_value == 50
        assert app.model.click_count == 0

    def test_catalog_title(self, app: AppFixture[Model]) -> None:
        """Catalog title is displayed."""
        assert app.text("#catalog_title") == "Plushie Widget Catalog"

    def test_tab_buttons_exist(self, app: AppFixture[Model]) -> None:
        """All four tab buttons exist."""
        assert app.exists("#tab_layout")
        assert app.exists("#tab_input")
        assert app.exists("#tab_display")
        assert app.exists("#tab_composite")

    def test_switch_to_input_tab(self, app: AppFixture[Model]) -> None:
        """Clicking the input tab switches the active tab."""
        app.click("#tab_input")
        assert app.model.active_tab == "input"

    def test_switch_to_display_tab(self, app: AppFixture[Model]) -> None:
        """Clicking the display tab switches the active tab."""
        app.click("#tab_display")
        assert app.model.active_tab == "display"

    def test_switch_to_composite_tab(self, app: AppFixture[Model]) -> None:
        """Clicking the composite tab switches the active tab."""
        app.click("#tab_composite")
        assert app.model.active_tab == "composite"

    def test_text_input(self, app: AppFixture[Model]) -> None:
        """Typing in the text input updates the model."""
        app.click("#tab_input")
        app.type_text("#demo_input", "hello world")
        assert app.model.text_value == "hello world"

    def test_checkbox_toggle(self, app: AppFixture[Model]) -> None:
        """Toggling the checkbox updates the model."""
        app.click("#tab_input")
        app.toggle("#demo_check")
        assert app.model.checkbox_checked is True

    def test_toggler_toggle(self, app: AppFixture[Model]) -> None:
        """Toggling the toggler updates the model."""
        app.click("#tab_input")
        app.toggle("#demo_toggler")
        assert app.model.toggler_on is True

    def test_slider(self, app: AppFixture[Model]) -> None:
        """Sliding the slider updates the model."""
        app.click("#tab_input")
        app.slide("#demo_slider", 75)
        assert app.model.slider_value == 75

    def test_radio_selection(self, app: AppFixture[Model]) -> None:
        """Selecting a radio option updates the model."""
        app.click("#tab_input")
        app.select("#demo_radio", "b")
        assert app.model.radio_selected == "b"

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The catalog window node exists."""
        assert app.exists("#catalog")
