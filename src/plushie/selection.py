"""Selection state for lists and tables.

Pure data structure supporting single, multi, and range selection modes.

Modes
-----

- ``"single"`` - at most one item selected at a time.
- ``"multi"`` - multiple items selectable; ``extend=True`` adds to
  the set.
- ``"range"`` - like multi, but :meth:`Selection.range_select` selects
  a contiguous slice of the *order* list between the anchor and target.

Example::

    sel = Selection.new(mode="multi", order=["a", "b", "c", "d"])
    sel = sel.select("b")
    sel = sel.select("d", extend=True)
    sel.selected()
    #=> frozenset({"b", "d"})
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

__all__ = [
    "Selection",
    "SelectionMode",
]

type SelectionMode = Literal["single", "multi", "range"]


@dataclass(frozen=True, slots=True)
class Selection:
    """Immutable selection state.

    Create via :meth:`new`.  All mutating methods return a new
    ``Selection``.
    """

    mode: SelectionMode
    _selected: frozenset[Any]
    anchor: Any | None
    order: tuple[Any, ...]

    # -- Construction -------------------------------------------------------

    @staticmethod
    def new(
        *,
        mode: SelectionMode = "single",
        order: tuple[Any, ...] | list[Any] = (),
    ) -> Selection:
        """Create a new empty selection.

        Args:
            mode: Selection mode. ``"single"``, ``"multi"``, or
                ``"range"``.
            order: Ordered sequence of item IDs for range selection.

        Example::

            >>> sel = Selection.new(mode="multi")
            >>> sel.selected()
            frozenset()
        """
        return Selection(
            mode=mode,
            _selected=frozenset(),
            anchor=None,
            order=tuple(order),
        )

    # -- Mutating operations (return new Selection) -------------------------

    def select(self, id: Any, *, extend: bool = False) -> Selection:
        """Select *id*.

        In ``"single"`` mode, replaces the selection.  In ``"multi"``
        and ``"range"`` modes, replaces unless ``extend=True``, in which
        case *id* is added to the existing selection.

        Sets the anchor to *id* for subsequent range selections.
        """
        if self.mode == "single":
            return replace(self, _selected=frozenset({id}), anchor=id)
        if extend:
            return replace(self, _selected=self._selected | {id}, anchor=id)
        return replace(self, _selected=frozenset({id}), anchor=id)

    def deselect(self, id: Any) -> Selection:
        """Remove *id* from the selection."""
        return replace(self, _selected=self._selected - {id})

    def toggle(self, id: Any) -> Selection:
        """Toggle *id* in the selection.

        If already selected, removes it; otherwise adds it.  In
        ``"single"`` mode, toggling a selected item clears the
        selection entirely.
        """
        if self.mode == "single":
            if id in self._selected:
                return replace(self, _selected=frozenset(), anchor=None)
            return replace(self, _selected=frozenset({id}), anchor=id)
        if id in self._selected:
            return replace(self, _selected=self._selected - {id})
        return replace(self, _selected=self._selected | {id}, anchor=id)

    def clear(self) -> Selection:
        """Clear all selected items and reset the anchor."""
        return replace(self, _selected=frozenset(), anchor=None)

    def select_all(self) -> Selection:
        """Select all items in *order*."""
        return replace(self, _selected=frozenset(self.order))

    def range_select(self, id: Any) -> Selection:
        """Select all items between the anchor and *id* (inclusive).

        Requires *order* to have been set at creation time.  If there
        is no anchor, selects only *id*.
        """
        if self.anchor is None:
            return replace(self, _selected=frozenset({id}), anchor=id)

        try:
            anchor_idx = self.order.index(self.anchor)
        except ValueError:
            return replace(self, _selected=frozenset({id}), anchor=id)

        try:
            id_idx = self.order.index(id)
        except ValueError:
            return replace(self, _selected=frozenset({id}), anchor=id)

        lo, hi = (anchor_idx, id_idx) if anchor_idx <= id_idx else (id_idx, anchor_idx)
        range_ids = self.order[lo : hi + 1]
        return replace(self, _selected=frozenset(range_ids))

    # -- Queries ------------------------------------------------------------

    def selected(self) -> frozenset[Any]:
        """Return the ``frozenset`` of currently selected item IDs."""
        return self._selected

    def is_selected(self, id: Any) -> bool:
        """Return ``True`` if *id* is currently selected."""
        return id in self._selected
