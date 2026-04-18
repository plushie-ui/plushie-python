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

    def a11y(self) -> dict[str, Any]:
        """Return the accessibility props dict.

        Returns an empty dict if no ``a11y`` key is present.
        """
        return self.props.get("a11y", {})

    def resolved_a11y(self) -> dict[str, Any]:
        """Return the resolved a11y map for this element.

        Layers render-pipeline inference on top of the normalized
        ``a11y`` prop: ``placeholder`` flows into ``description`` for
        ``text_input``/``text_editor``/``combo_box``/``pick_list`` when
        unset, and ``alt`` flows into ``label`` for ``image``/``svg``/
        ``qr_code``.

        Returns an empty dict for widgets the normalizer left
        untouched, so tests can match on individual keys without
        special-casing absence.
        """
        explicit: dict[str, Any] = self.a11y()
        inferred = _infer_a11y(self.type, self.props)
        merged: dict[str, Any] = dict(inferred)
        merged.update(explicit)
        return merged

    def inferred_role(self) -> str:
        """Return the accessible role, inferring from widget type if not explicit.

        Checks ``props.a11y.role`` first. If absent, falls back to
        the widget ``type`` field (e.g. ``"button"`` -> ``"button"``).
        """
        a11y = self.a11y()
        role = a11y.get("role")
        if isinstance(role, str) and role:
            return role
        return self.type


class ElementNotFoundError(Exception):
    """Raised when a query expected to find an element returns nothing."""


_PLACEHOLDER_WIDGETS = frozenset(
    {"text_input", "text_editor", "combo_box", "pick_list"}
)
_ALT_WIDGETS = frozenset({"image", "svg", "qr_code"})


def _infer_a11y(widget_type: str, props: dict[str, Any]) -> dict[str, Any]:
    """Infer widget-sdk-equivalent a11y defaults for a node.

    Kept aligned with the Rust SDK's ``resolve_a11y_for_node`` so parity
    holds across host SDKs.
    """
    if widget_type in _PLACEHOLDER_WIDGETS:
        ph = props.get("placeholder")
        if isinstance(ph, str) and ph:
            return {"description": ph}
        return {}
    if widget_type in _ALT_WIDGETS:
        alt = props.get("alt")
        if isinstance(alt, str) and alt:
            return {"label": alt}
        return {}
    return {}


__all__ = [
    "Element",
    "ElementNotFoundError",
]
