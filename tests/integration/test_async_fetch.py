"""Integration test for the Async Fetch example app.

Runs the FetchApp through the real plushie renderer binary. Validates
initial idle state, successful fetch flow (loading -> success), and
the error fetch path.
"""

from __future__ import annotations

import pytest
from examples.async_fetch import FetchApp, Model

from plushie.testing import AppFixture


@pytest.fixture
def app(plushie_pool):
    """Create a test fixture for the FetchApp."""
    with AppFixture(FetchApp, plushie_pool) as fixture:
        yield fixture


class TestAsyncFetchIntegration:
    """End-to-end tests for the Async Fetch example."""

    def test_initial_state(self, app: AppFixture[Model]) -> None:
        """App starts idle with no data or error."""
        assert app.model.loading is False
        assert app.model.data is None
        assert app.model.error is None

    def test_initial_status_text(self, app: AppFixture[Model]) -> None:
        """Status text shows the idle prompt."""
        assert app.text("#status") == "Press a button to fetch data."

    def test_buttons_exist(self, app: AppFixture[Model]) -> None:
        """Both fetch buttons are present."""
        assert app.exists("#fetch")
        assert app.exists("#fetch-error")

    def test_successful_fetch(self, app: AppFixture[Model]) -> None:
        """Clicking fetch triggers the task and resolves to success.

        The test fixture processes Command.task synchronously, so
        the model transitions straight from idle to data-populated
        without lingering in the loading state.
        """
        app.click("#fetch")
        assert app.model.loading is False
        assert app.model.data == "Hello from the background thread!"
        assert app.model.error is None
        assert app.text("#status") == "Hello from the background thread!"

    def test_fetch_error_raises(self, app: AppFixture[Model]) -> None:
        """Clicking fetch-error raises because the fixture runs tasks inline.

        The real runtime catches task exceptions and delivers them as
        AsyncResult(value=("error", str(exc))). The synchronous fixture
        does not catch, so the TimeoutError propagates.
        """
        with pytest.raises(TimeoutError):
            app.click("#fetch-error")

    def test_window_exists(self, app: AppFixture[Model]) -> None:
        """The main window node exists."""
        assert app.exists("#main")
