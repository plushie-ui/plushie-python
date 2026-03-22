"""Element wrapper for renderer node dicts returned by queries.

An ``Element`` wraps the raw dict returned by the renderer's query
response, providing typed access to node properties and convenience
methods for text extraction.

Usage::

    from plushie.testing import AppFixture

    fixture = AppFixture(MyApp, pool)
    el = fixture.find("#greeting")
    assert el.type == "text"
    assert el.text() == "Hello, world!"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Element:
    """A wrapper around a renderer node dict.

    Provides typed property access and text extraction.

    Attributes:
        node: The raw node dict from the renderer query response.
    """

    node: dict[str, Any] = field(repr=False)

    @property
    def id(self) -> str:
        """The node's ID (scoped if inside a named container)."""
        return self.node.get("id", "")

    @property
    def type(self) -> str:
        """The widget type name (e.g. ``"button"``, ``"text"``)."""
        return self.node.get("type", "")

    @property
    def props(self) -> dict[str, Any]:
        """The node's property dict."""
        return self.node.get("props", {})

    @property
    def children(self) -> list[Element]:
        """Child elements, wrapped as ``Element`` instances."""
        raw = self.node.get("children", [])
        return [Element(node=child) for child in raw if isinstance(child, dict)]

    def text(self) -> str | None:
        """Extract display text from the node.

        Checks props in priority order: ``content``, ``label``,
        ``value``, ``placeholder``. Returns ``None`` if none are
        present or the value is not a string.
        """
        props = self.props
        for key in ("content", "label", "value", "placeholder"):
            val = props.get(key)
            if isinstance(val, str):
                return val
        return None


class ElementNotFoundError(Exception):
    """Raised when a query expected to find an element returns nothing."""


__all__ = [
    "Element",
    "ElementNotFoundError",
]
