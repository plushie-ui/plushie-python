"""Tree search/query helpers."""

from __future__ import annotations

from collections.abc import Callable

from plushie.tree._types import Node


def find(tree: Node, target_id: str) -> Node | None:
    """Find the first node whose ``id`` matches *target_id*.

    Matches against the full scoped ID first. If no match is found
    and *target_id* does not contain ``/`` or ``#``, falls back to
    matching the local segment (the part after the last ``/`` or ``#``)
    of each node's scoped ID.

    Returns the node dict, or ``None`` if not found. Searches depth-first.
    """
    result = _find_exact(tree, target_id)
    if result is not None:
        return result

    if "/" not in target_id and "#" not in target_id:
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
    """Depth-first match on the local segment of scoped IDs.

    The local segment is the part after the last ``/`` or ``#``.
    """
    node_id = node.get("id", "")
    local = node_id.rsplit("/", 1)[-1]
    if "#" in local:
        local = local.rsplit("#", 1)[-1]
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
