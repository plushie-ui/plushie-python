"""Integration test for the Rate Plushie example app.

Runs the RatePlushie app through the real plushie renderer binary.
Tests initial state, star rating canvas, and review form elements.
"""

from __future__ import annotations

import pytest
from examples.rate_plushie import Model, RatePlushie

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the RatePlushie app."""
    with AppFixture(RatePlushie, plushie_pool) as fixture:
        yield fixture


class TestRatePlushieIntegration:
    """End-to-end tests for the Rate Plushie example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """App starts with zero rating and no toggle animation."""
        assert app.model.rating == 0
        assert app.model.hover_star is None
        assert app.model.toggle_progress == 0.0
        assert app.model.toggle_target == 0.0

    def test_initial_reviews(self, app: AppFixture[Model]) -> None:
        """App starts with the seeded reviews."""
        assert len(app.model.reviews) > 0

    def test_star_canvas_exists(self, app: AppFixture[Model]) -> None:
        """The star rating canvas widget exists (scoped under page-theme/page/rating-card)."""
        assert app.exists("#page-theme/page/rating-card/stars")

    def test_heading_exists(self, app: AppFixture[Model]) -> None:
        """The heading text is displayed."""
        assert app.text("#heading") == "Rate Plushie"

    def test_review_form_elements(self, app: AppFixture[Model]) -> None:
        """The review form inputs and submit button exist (scoped under page-theme/page)."""
        assert app.exists("#page-theme/page/rating-card/review-form/review-name")
        assert app.exists("#page-theme/page/rating-card/review-form/review-comment")
        assert app.exists("#page-theme/page/rating-card/review-form/submit-review")

    def test_theme_toggle_exists(self, app: AppFixture[Model]) -> None:
        """The theme toggle canvas exists (scoped under page-theme/page/rating-card)."""
        assert app.exists("#page-theme/page/rating-card/theme-row/theme-toggle")

    def test_review_name_input(self, app: AppFixture[Model]) -> None:
        """Typing in the review name input updates the model."""
        app.type_text("#review-name", "test_user")
        assert app.model.review_name == "test_user"

    def test_review_comment_input(self, app: AppFixture[Model]) -> None:
        """Typing in the review comment editor updates the model."""
        app.type_text("#review-comment", "Great app!")
        assert app.model.review_comment == "Great app!"

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The main window node exists."""
        assert app.exists("#main")
