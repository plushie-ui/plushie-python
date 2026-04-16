"""pytest-native testing framework for plushie applications.

Provides:

- ``AppFixture`` - synchronous test driver for plushie apps
- ``Element`` - wrapper for renderer query results
- ``TreeHash`` - structural tree hash and golden-file assertions
- ``Screenshot`` - screenshot golden-file assertions
- ``WidgetFixture`` - test harness for custom widgets

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
from plushie.testing.screenshot import Screenshot
from plushie.testing.tree_hash import TreeHash
from plushie.testing.widget_case import WidgetFixture

__all__ = [
    "AppFixture",
    "Element",
    "ElementNotFoundError",
    "Screenshot",
    "TreeHash",
    "WidgetFixture",
]
