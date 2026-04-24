"""Tree diffing utilities."""

from __future__ import annotations

import logging
from typing import Any

from plushie.tree._types import Node, PatchOp

logger = logging.getLogger("plushie")

# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff(old: Node | None, new: Node | None) -> list[PatchOp]:
    """Compare two normalized trees and return a list of patch operations.

    Patch operations (applied sequentially by the renderer):

    - ``replace_node`` - replace entire subtree at ``path``.
    - ``update_props`` - merge changed/removed props at ``path``.
    - ``insert_child`` - insert a child node at ``path`` + ``index``.
    - ``remove_child`` - remove the child at ``path`` + ``index``.

    ``path`` is a list of child indices from the root. An empty path
    ``[]`` means the root node.

    Child matching is by ID (dict lookup, not positional). If common
    children are reordered, the differ emits ``replace_node`` for the
    parent (O(n) simplicity over O(n^2) LCS).
    """
    if old is None and new is None:
        return []
    if old is None and new is not None:
        return [{"op": "replace_node", "path": [], "node": new}]
    if old is not None and new is None:
        return [{"op": "remove_child", "path": [], "index": 0}]

    assert old is not None and new is not None

    # Root ID changed -> full replace
    if old["id"] != new["id"]:
        return [{"op": "replace_node", "path": [], "node": new}]

    return _diff_node(old, new, [])


def _diff_node(old: Node, new: Node, path: list[int]) -> list[PatchOp]:
    """Diff two nodes at the same tree position."""
    if old["type"] != new["type"]:
        return [{"op": "replace_node", "path": path, "node": new}]

    child_ops = _diff_children(old["children"], new["children"], path)
    if child_ops is None:
        # Reordered; replace the whole node
        return [{"op": "replace_node", "path": path, "node": new}]

    prop_ops = _diff_props(old["props"], new["props"], path)
    return prop_ops + child_ops


def _diff_props(
    old_props: dict[str, Any],
    new_props: dict[str, Any],
    path: list[int],
) -> list[PatchOp]:
    """Compute prop changes between two nodes."""
    if old_props == new_props:
        return []

    changed: dict[str, Any] = {}

    # Changed or added keys. For list props where every element has
    # an ``id`` key (canvas shape lists, for example), reconstructed
    # lists with identical content compare equal via the id-keyed
    # check below. That avoids a spurious ``update_props`` when the
    # view recreated the list without changing any shape.
    for k, v in new_props.items():
        old_v = old_props.get(k, _SENTINEL)
        if old_v is _SENTINEL or (old_v != v and not _id_keyed_lists_equal(old_v, v)):
            changed[k] = v

    # Removed keys -> set to None so the renderer can clear them
    for k in old_props:
        if k not in new_props:
            changed[k] = None

    if not changed:
        return []

    return [{"op": "update_props", "path": path, "props": changed}]


# Sentinel for detecting missing keys vs None values
_SENTINEL = object()


def _id_keyed_lists_equal(old_val: Any, new_val: Any) -> bool:
    """Check whether two list props are semantically equal by id.

    When both values are lists of dicts and every element carries an
    ``id`` field, compare elements by id rather than positional
    deep-equality. Catches the case where the view function rebuilt
    the list with identical content but a different object identity.

    Returns False for any shape that doesn't fit the pattern, so
    normal deep-equality wins for non-id-bearing lists.
    """
    if not isinstance(old_val, list) or not isinstance(new_val, list):
        return False
    if len(old_val) != len(new_val):
        return False
    if not old_val:
        return False
    for el in old_val:
        if not isinstance(el, dict) or "id" not in el:
            return False
    for el in new_val:
        if not isinstance(el, dict) or "id" not in el:
            return False

    old_by_id: dict[Any, dict[str, Any]] = {el["id"]: el for el in old_val}
    for el in new_val:
        cached = old_by_id.get(el["id"])
        if cached != el:
            return False
    return True


def _diff_children(
    old_children: list[Node],
    new_children: list[Node],
    path: list[int],
) -> list[PatchOp] | None:
    """Diff child lists. Returns ``None`` if children were reordered.

    Uses ID-based matching. Reorder detection compares the relative
    order of common IDs between old and new lists. If the order
    differs, returns None to signal a full parent replacement.
    """
    # Build ID -> (node, index) maps
    old_by_id: dict[str, tuple[Node, int]] = {}
    for i, child in enumerate(old_children):
        child_id = child["id"]
        if child_id in old_by_id:
            logger.error(
                "plushie tree: duplicate child IDs will cause rendering errors: %s",
                [child_id],
            )
        old_by_id[child_id] = (child, i)

    new_by_id: dict[str, tuple[Node, int]] = {}
    new_ids: list[str] = []
    for i, child in enumerate(new_children):
        child_id = child["id"]
        new_ids.append(child_id)
        if child_id in new_by_id:
            logger.error(
                "plushie tree: duplicate child IDs will cause rendering errors: %s",
                [child_id],
            )
        new_by_id[child_id] = (child, i)

    old_ids = [child["id"] for child in old_children]

    # Reorder detection: filter common IDs, compare order
    common_old = [oid for oid in old_ids if oid in new_by_id]
    common_new = [nid for nid in new_ids if nid in old_by_id]

    if common_old != common_new:
        return None  # reordered

    # Removals: old IDs not in new, descending index order
    removed_indices: list[int] = sorted(
        (idx for cid, (_, idx) in old_by_id.items() if cid not in new_by_id),
        reverse=True,
    )

    remove_ops: list[PatchOp] = [
        {"op": "remove_child", "path": path, "index": idx} for idx in removed_indices
    ]

    # Walk new children for updates and inserts
    update_ops: list[PatchOp] = []
    insert_ops: list[PatchOp] = []

    for idx, child in enumerate(new_children):
        child_id = child["id"]
        old_entry = old_by_id.get(child_id)

        if old_entry is not None:
            old_child, old_idx = old_entry
            adjusted = _index_after_removals(old_idx, removed_indices)
            child_path = [*path, adjusted]
            update_ops.extend(_diff_node(old_child, child, child_path))
        else:
            insert_ops.append(
                {
                    "op": "insert_child",
                    "path": path,
                    "index": idx,
                    "node": child,
                }
            )

    return remove_ops + update_ops + insert_ops


def _index_after_removals(old_idx: int, removed_indices: list[int]) -> int:
    """Adjust an old child index after removals have been applied.

    ``removed_indices`` is sorted descending. Count how many removed
    indices are *less than* ``old_idx`` to compute the adjusted position.
    """
    return old_idx - sum(1 for r in removed_indices if r < old_idx)
