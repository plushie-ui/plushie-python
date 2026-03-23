"""Tree normalization, diffing, and search utilities.

Provides the core tree operations for the plushie SDK:

- **normalize** -- assign auto-IDs, resolve scoped IDs, validate
  constraints, resolve a11y cross-references.
- **diff** -- produce minimal patch operations (replace_node,
  update_props, insert_child, remove_child) for incremental
  renderer updates.
- **find / find_all / exists / ids** -- tree search utilities.
- **text_of** -- extract display text from a node.

Tree nodes are plain dicts with the shape::

    {"id": "btn", "type": "button", "props": {"label": "Click"}, "children": []}

Reference: toddy-elixir ``lib/plushie/tree.ex`` for the exact
diff algorithm and normalization rules.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from plushie.types import A11y, Border, Font, Gradient, Shadow, StyleMap, Theme

logger = logging.getLogger("plushie")

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

type Node = dict[str, Any]
"""A normalized tree node: ``{id, type, props, children}``."""

type PatchOp = dict[str, Any]
"""A patch operation dict with ``op``, ``path``, and operation-specific keys."""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMPTY_CONTAINER: Node = {
    "id": "root",
    "type": "container",
    "props": {},
    "children": [],
}

_A11Y_ID_REF_KEYS = ("labelled_by", "described_by", "error_message")

# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------


def normalize(tree: None | Node | list[Node]) -> Node:
    """Normalize a UI tree into canonical node shape.

    Accepts:
    - ``None`` -- returns an empty root container.
    - A single node dict -- normalizes and returns it.
    - A list of node dicts -- wraps in a root container (the root
      does not create a scope boundary).

    Every node in the result is guaranteed to have ``id``, ``type``,
    ``props``, and ``children`` keys. Auto-IDs are assigned to nodes
    with ``id=None``: ``auto:{type}:{child_index}`` (deterministic).
    Named non-window, non-auto containers push their ID onto the
    scope chain for their children.

    Raises:
        ValueError: If a user-provided ID contains ``/``.
    """
    if tree is None:
        return _empty_container()

    if isinstance(tree, list):
        if len(tree) == 0:
            return _empty_container()
        if len(tree) == 1:
            return _normalize_with_scope(tree[0], "", 0)
        return {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                _normalize_with_scope(child, "", i) for i, child in enumerate(tree)
            ],
        }

    return _normalize_with_scope(tree, "", 0)


def _empty_container() -> Node:
    """Return a fresh empty container (never mutate the constant)."""
    return {
        "id": "root",
        "type": "container",
        "props": {},
        "children": [],
    }


def _normalize_with_scope(node: Node, scope: str, index: int) -> Node:
    """Normalize a single node with scope context.

    Args:
        node: Raw node dict (may have missing keys).
        scope: Current scope prefix (e.g. ``"sidebar/form"``).
        index: Child index within parent (for auto-ID generation).
    """
    raw_id = node.get("id")
    node_type = node.get("type", "container")
    props: dict[str, Any] = node.get("props") or {}
    children: list[Node] = node.get("children") or []

    # Auto-ID for nodes without an explicit ID
    node_id = f"auto:{node_type}:{index}" if raw_id is None else str(raw_id)
    is_auto = node_id.startswith("auto:")

    # Validate: user-provided IDs must not contain "/"
    if not is_auto and "/" in node_id:
        raise ValueError(
            f'widget ID {node_id!r} cannot contain "/" '
            "-- scoped paths are built automatically by named containers"
        )

    # Apply scope prefix to this node's ID
    scoped_id = f"{scope}/{node_id}" if scope and not is_auto else node_id

    # Determine scope for children: named (non-auto) non-window nodes
    # propagate their scoped ID as the child scope.
    child_scope = scope if is_auto or node_type == "window" else scoped_id

    # Encode dataclass prop values to wire-compatible dicts/values,
    # then resolve a11y ID refs relative to scope.
    encoded_props = _encode_props(dict(props))
    normalized_props = _resolve_a11y_id_refs(encoded_props, scope)

    # Normalize children
    normalized_children = _normalize_children(children, child_scope)

    return {
        "id": scoped_id,
        "type": node_type,
        "props": normalized_props,
        "children": normalized_children,
    }


def _normalize_children(children: list[Node], scope: str) -> list[Node]:
    """Normalize a list of child nodes, checking for duplicate IDs."""
    normalized = [
        _normalize_with_scope(child, scope, i) for i, child in enumerate(children)
    ]
    _check_duplicate_ids(normalized)
    return normalized


def _check_duplicate_ids(children: list[Node]) -> None:
    """Log a warning if sibling nodes have duplicate IDs."""
    seen: set[str] = set()
    dupes: list[str] = []
    for child in children:
        child_id = child["id"]
        if child_id in seen:
            dupes.append(child_id)
        else:
            seen.add(child_id)
    if dupes:
        unique_dupes = list(dict.fromkeys(dupes))
        logger.error(
            "Duplicate sibling IDs detected during normalize: %s",
            unique_dupes,
        )


_WIRE_TYPES = (StyleMap, Border, Shadow, Font, Gradient, A11y, Theme)


def _encode_prop_value(value: Any) -> Any:
    """Convert a known dataclass type to its wire-compatible representation.

    Recognized types: StyleMap, Border, Shadow, Font, Gradient, A11y, Theme.
    Tuples are converted to lists (wire format uses arrays).
    Other values pass through unchanged.
    """
    if isinstance(value, _WIRE_TYPES):
        return value.to_wire()
    if isinstance(value, tuple):
        return list(value)
    return value


def _encode_props(props: dict[str, Any]) -> dict[str, Any]:
    """Encode all prop values, converting dataclass types to wire dicts."""
    return {k: _encode_prop_value(v) for k, v in props.items()}


def _resolve_a11y_id_refs(props: dict[str, Any], scope: str) -> dict[str, Any]:
    """Resolve a11y ID references relative to the current scope.

    Fields ``labelled_by``, ``described_by``, and ``error_message``
    inside the ``a11y`` sub-dict reference sibling widgets by local
    ID. The renderer needs the full scoped path.
    """
    a11y = props.get("a11y")
    if not isinstance(a11y, dict):
        return props

    resolved = dict(a11y)
    for key in _A11Y_ID_REF_KEYS:
        ref = resolved.get(key)
        if isinstance(ref, str) and ref:
            resolved[key] = _scope_ref(ref, scope)

    return {**props, "a11y": resolved}


def _scope_ref(ref: str, scope: str) -> str:
    """Prefix an ID reference with the current scope.

    Already-scoped references (containing ``/``) pass through unchanged.
    """
    if not scope or "/" in ref:
        return ref
    return f"{scope}/{ref}"


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff(old: Node | None, new: Node | None) -> list[PatchOp]:
    """Compare two normalized trees and return a list of patch operations.

    Patch operations (applied sequentially by the renderer):

    - ``replace_node`` -- replace entire subtree at ``path``.
    - ``update_props`` -- merge changed/removed props at ``path``.
    - ``insert_child`` -- insert a child node at ``path`` + ``index``.
    - ``remove_child`` -- remove the child at ``path`` + ``index``.

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
        # Reordered -- replace the whole node
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

    # Changed or added keys
    for k, v in new_props.items():
        old_v = old_props.get(k, _SENTINEL)
        if old_v is _SENTINEL or old_v != v:
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


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def find(tree: Node, target_id: str) -> Node | None:
    """Find the first node whose ``id`` matches *target_id*.

    Matches against the full scoped ID first. If no match is found
    and *target_id* does not contain ``/``, falls back to matching
    the local segment (the part after the last ``/``) of each node's
    scoped ID.

    Returns the node dict, or ``None`` if not found. Searches depth-first.
    """
    result = _find_exact(tree, target_id)
    if result is not None:
        return result

    if "/" not in target_id:
        return _find_by_local(tree, target_id)

    return None


def _find_exact(node: Node, target_id: str) -> Node | None:
    """Depth-first exact ID match."""
    if node.get("id") == target_id:
        return node
    for child in node.get("children", []):
        result = _find_exact(child, target_id)
        if result is not None:
            return result
    return None


def _find_by_local(node: Node, target_id: str) -> Node | None:
    """Depth-first match on the local (last) segment of scoped IDs."""
    node_id = node.get("id", "")
    local = node_id.rsplit("/", 1)[-1] if "/" in node_id else node_id
    if local == target_id:
        return node
    for child in node.get("children", []):
        result = _find_by_local(child, target_id)
        if result is not None:
            return result
    return None


def find_all(tree: Node, predicate: Callable[[Node], bool]) -> list[Node]:
    """Find all nodes for which *predicate* returns truthy.

    Walks the entire tree depth-first and accumulates all matches.
    """
    results: list[Node] = []
    _do_find_all(tree, predicate, results)
    return results


def _do_find_all(
    node: Node,
    predicate: Callable[[Node], bool],
    acc: list[Node],
) -> None:
    """Recursive depth-first accumulator for find_all."""
    if predicate(node):
        acc.append(node)
    for child in node.get("children", []):
        _do_find_all(child, predicate, acc)


def exists(tree: Node | None, target_id: str) -> bool:
    """Return ``True`` if a node with *target_id* exists in *tree*.

    Supports both full scoped IDs and local IDs (see :func:`find`).
    """
    if tree is None:
        return False
    return find(tree, target_id) is not None


def ids(tree: Node | None) -> list[str]:
    """Return a flat list of all node IDs in depth-first order."""
    if tree is None:
        return []
    result: list[str] = []
    _collect_ids(tree, result)
    return result


def _collect_ids(node: Node, acc: list[str]) -> None:
    """Recursive ID collector."""
    node_id = node.get("id")
    if node_id is not None:
        acc.append(node_id)
    for child in node.get("children", []):
        _collect_ids(child, acc)


def text_of(node: Node) -> str | None:
    """Extract display text from a node.

    Checks props in priority order: ``content``, ``label``, ``value``,
    ``placeholder``. Returns ``None`` if none are present or the value
    is not a string.
    """
    props = node.get("props", {})
    for key in ("content", "label", "value", "placeholder"):
        val = props.get(key)
        if isinstance(val, str):
            return val
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "Node",
    "PatchOp",
    "diff",
    "exists",
    "find",
    "find_all",
    "ids",
    "normalize",
    "text_of",
]
