"""Shared public tree types."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

type Node = dict[str, Any]
"""A normalized tree node: ``{id, type, props, children}``."""

type PatchOp = dict[str, Any]
"""A patch operation dict with ``op``, ``path``, and operation-specific keys."""


@runtime_checkable
class WireEncodable(Protocol):
    """Any type that can encode itself for the wire protocol.

    Types implementing ``to_wire()`` are automatically recognized by
    the tree normalizer and encoded when used as prop values. No manual
    registration needed.
    """

    def to_wire(self) -> Any:
        """Return the wire-protocol representation of this value."""
        ...
