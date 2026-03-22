"""pytest plugin for plushie testing.

Auto-discovered via the ``pytest11`` entry point. Provides a shared
``SessionPool`` that starts once per test session and a
``plushie_pool`` fixture for test functions.

Backend selection respects the ``PLUSHIE_TEST_BACKEND`` environment
variable:

- ``mock`` (default) -- lightweight rendering, no display server
- ``headless`` -- real rendering, software backend
- ``windowed`` -- real iced windows (needs Xvfb or a display)

Usage::

    # pyproject.toml
    [project.entry-points.pytest11]
    plushie = "plushie.testing.plugin"

    # test_counter.py
    from plushie.testing import AppFixture

    def test_increment(plushie_pool):
        with AppFixture(Counter, plushie_pool) as app:
            app.click("#inc")
            assert app.model.count == 1
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pytest

logger = logging.getLogger("plushie.testing")


def _get_backend() -> str:
    """Read the test backend from the environment.

    Returns:
        Backend mode string (``"mock"``, ``"headless"``, or ``"windowed"``).
    """
    return os.environ.get("PLUSHIE_TEST_BACKEND", "mock").lower()


# Store the pool at module level so configure/unconfigure can share it
_pool: Any = None


def pytest_configure(config: pytest.Config) -> None:
    """Start the shared session pool when pytest starts."""
    global _pool

    # Only start the pool if plushie.testing is importable (the package
    # may not be installed in all environments).
    try:
        from plushie.testing.pool import SessionPool
    except ImportError:
        return

    backend = _get_backend()
    max_sessions = int(os.environ.get("PLUSHIE_TEST_MAX_SESSIONS", "8"))

    try:
        pool = SessionPool(mode=backend, max_sessions=max_sessions)
        pool.start()
        _pool = pool
        logger.info(
            "plushie test pool started (backend=%s, max_sessions=%d)",
            backend,
            max_sessions,
        )
    except Exception:
        logger.warning(
            "plushie test pool failed to start -- integration tests will be skipped",
            exc_info=True,
        )
        _pool = None


def pytest_unconfigure(config: pytest.Config) -> None:
    """Stop the shared session pool when pytest exits."""
    global _pool
    if _pool is not None:
        _pool.stop()
        _pool = None


@pytest.fixture(scope="session")
def plushie_pool() -> Any:
    """Provide the shared ``SessionPool`` for test functions.

    Yields the pool if it was started successfully, otherwise skips
    the test.
    """
    if _pool is None:
        pytest.skip("plushie renderer not available")
    return _pool


__all__ = [
    "plushie_pool",
    "pytest_configure",
    "pytest_unconfigure",
]
