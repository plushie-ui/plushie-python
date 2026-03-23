"""Integration test for the Color Picker example app.

Runs the ColorPicker app through the real plushie renderer binary.
Tests initial HSV state, canvas presence, and hex color display.
"""

from __future__ import annotations

import re

import pytest
from examples.color_picker import ColorPicker, Model

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the ColorPicker app."""
    with AppFixture(ColorPicker, plushie_pool) as fixture:
        yield fixture


class TestColorPickerIntegration:
    """End-to-end tests for the Color Picker example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """Picker starts with hue=0, saturation=1, value=1, no drag."""
        assert app.model.hue == 0.0
        assert app.model.saturation == 1.0
        assert app.model.value == 1.0
        assert app.model.drag == "none"

    def test_canvas_exists(self, app: AppFixture[Model]) -> None:
        """The picker canvas widget exists."""
        assert app.exists("#picker")

    def test_hex_display_exists(self, app: AppFixture[Model]) -> None:
        """The hex color display text exists."""
        assert app.exists("#hex_display")

    def test_hex_display_format(self, app: AppFixture[Model]) -> None:
        """The hex display shows a valid hex color string."""
        hex_text = app.text("#hex_display")
        assert hex_text is not None
        assert re.match(r"^#[0-9a-f]{6}$", hex_text)

    def test_initial_hex_is_red(self, app: AppFixture[Model]) -> None:
        """With hue=0, s=1, v=1 the color should be pure red (#ff0000)."""
        assert app.text("#hex_display") == "#ff0000"

    def test_hsv_display_exists(self, app: AppFixture[Model]) -> None:
        """The HSV label display text exists."""
        assert app.exists("#hsv_display")

    def test_swatch_exists(self, app: AppFixture[Model]) -> None:
        """The color swatch container exists."""
        assert app.exists("#swatch")

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The color_picker window node exists."""
        assert app.exists("#color_picker")
