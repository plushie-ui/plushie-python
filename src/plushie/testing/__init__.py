"""pytest-native testing framework for plushie applications.

Provides:

- ``AppFixture`` - synchronous test driver for plushie apps
- ``Element`` - wrapper for renderer query results

Usage::

    from plushie.testing import AppFixture, Element

    def test_counter(plushie_pool):
        with AppFixture(Counter, plushie_pool) as app:
            app.click("#inc")
            assert app.model.count == 1
            el = app.find("#count")
            assert el.text() == "Count: 1"
"""

from __future__ import annotations

from plushie.testing.element import Element, ElementNotFoundError
from plushie.testing.fixture import AppFixture

__all__ = [
    "AppFixture",
    "Element",
    "ElementNotFoundError",
]
