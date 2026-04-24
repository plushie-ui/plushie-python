"""Tree normalization utilities."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from plushie.tree._types import Node, WireEncodable
from plushie.tree.a11y import (
    _apply_a11y_defaults,
    _infer_radio_groups,
    _post_normalize,
    _resolve_a11y_id_refs,
)

logger = logging.getLogger("plushie")

_VALID_ID_RE = re.compile(r"^[\x21-\x7e]+$")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMPTY_CONTAINER: Node = {
    "id": "root",
    "type": "container",
    "props": {},
    "children": [],
}

# ---------------------------------------------------------------------------
# ScopedId
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScopedId:
    """Structured representation of a scoped widget ID.

    Wire IDs use the canonical format ``window#scope/path/id``::

        "main#form/email"     widget in window
        "main#users/u1"      table row
        "main"               the window itself
        "form/email"         widget without window qualification

    Event structs use flat fields (``id``, ``scope``, ``window``) for
    ergonomic pattern matching. Use :func:`ScopedId.parse` to convert
    to the structured form when programmatic manipulation is needed.

    Attributes:
        id: The local widget ID (last path segment).
        scope: Reversed scope chain (immediate parent first).
            For ``"main#form/email"``, scope is ``("form",)``.
        window: The window ID or ``None`` if no window qualifier.
        full: The canonical wire ID string.

    Examples:
        >>> ScopedId.parse("main#sidebar/form/email")
        ScopedId(id='email', scope=('form', 'sidebar'), window='main', full='main#sidebar/form/email')
        >>> ScopedId.parse("form/email")
        ScopedId(id='email', scope=('form',), window=None, full='form/email')
        >>> ScopedId.parse("email")
        ScopedId(id='email', scope=(), window=None, full='email')
    """

    id: str
    scope: tuple[str, ...] = ()
    window: str | None = None
    full: str = ""

    def __post_init__(self) -> None:
        if not self.full:
            object.__setattr__(
                self, "full", _build_full(self.window, self.scope, self.id)
            )

    @staticmethod
    def parse(canonical: str) -> ScopedId:
        """Parse a canonical wire ID into its components.

        The ``#`` separates the window from the widget path. The ``/``
        separates scope segments within the path. The last segment
        is the local ``id``.

        Args:
            canonical: Wire ID string (e.g. ``"main#sidebar/form/email"``).

        Returns:
            Populated ``ScopedId`` instance.
        """
        if not canonical:
            return ScopedId(id="", scope=(), window=None, full="")

        if "#" in canonical:
            win, rest = canonical.split("#", 1)
            window = win if win else None
        else:
            window = None
            rest = canonical

        parts = rest.split("/") if rest else []
        if not parts or not parts[0]:
            return ScopedId(id="", scope=(), window=window, full=canonical)

        if len(parts) == 1:
            return ScopedId(id=parts[0], scope=(), window=window, full=canonical)

        *scope_parts, local_id = parts
        return ScopedId(
            id=local_id,
            scope=tuple(reversed(scope_parts)),
            window=window,
            full=canonical,
        )

    @staticmethod
    def from_event(event: dict[str, Any]) -> ScopedId:
        """Build a ScopedId from event fields.

        The event's scope tuple includes the window_id as its last
        element (appended by the protocol decoder). This method strips
        it to produce the correct canonical ``full`` ID.

        Args:
            event: Event dict with ``id`` and ``scope`` keys.
                May also have ``window`` or ``window_id``.
        """
        eid = event.get("id", "")
        escope = event.get("scope", ())
        ewindow = event.get("window") or event.get("window_id")
        if ewindow and escope and escope[-1] == ewindow:
            escope = escope[:-1]
        full = _build_full(ewindow, escope, eid)
        return ScopedId(
            id=eid if eid else "",
            scope=escope if escope else (),
            window=ewindow,
            full=full,
        )

    def matches_local(self, name: str) -> bool:
        """True if the local ID matches the given name."""
        return self.id == name

    def matches_scope(self, ancestor: str) -> bool:
        """True if the ancestor appears anywhere in the scope chain."""
        return ancestor in self.scope

    def in_window(self, window: str) -> bool:
        """True if the ID is in the given window."""
        return self.window == window

    def parent(self) -> str | None:
        """Returns the immediate parent (nearest ancestor), or None."""
        return self.scope[0] if self.scope else None


def _build_full(window: str | None, scope: tuple[str, ...], local_id: str) -> str:
    """Build the canonical full ID from components."""
    if not local_id:
        return ""

    if window is None and not scope:
        return local_id

    if window is None:
        path = "/".join(reversed(scope))
        return f"{path}/{local_id}"

    if not scope:
        return f"{window}#{local_id}"

    path = "/".join(reversed(scope))
    return f"{window}#{path}/{local_id}"


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------


def normalize(
    tree: None | Node | list[Node],
    *,
    registry: Any = None,
    memo_cache_prev: dict[Any, Any] | None = None,
    memo_cache_new: dict[Any, Any] | None = None,
    widget_cache_prev: dict[Any, Any] | None = None,
    widget_cache_new: dict[Any, Any] | None = None,
) -> Node:
    """Normalize a UI tree into canonical node shape.

    Accepts:
    - ``None`` - returns an empty root container.
    - A single node dict. Normalizes and returns it.
    - A list of node dicts. Wraps in a root container (the root
      does not create a scope boundary).

    Args:
        registry: Canvas widget registry for placeholder rendering
            during normalization.
        memo_cache_prev: Previous render's memo cache (read). Keys
            are ``(node_id, scope, window_id, deps)`` tuples; values
            are cached normalized subtrees. When supplied together
            with ``memo_cache_new``, memo subtrees whose deps match
            the previous render's value are reused instead of being
            re-evaluated.
        memo_cache_new: This render's memo cache (written).
        widget_cache_prev: Previous render's widget view cache (read).
            Keys are ``(window_id, scoped_id)`` tuples; values are
            ``(cache_key, rendered_node)`` pairs. When a widget's
            ``cache_key`` matches the stored value, its expanded
            view is reused and ``view()`` is not re-invoked.
        widget_cache_new: This render's widget view cache (written).

    Every node in the result is guaranteed to have ``id``, ``type``,
    ``props``, and ``children`` keys. Auto-IDs are assigned to nodes
    with ``id=None``: ``auto:{type}:{child_index}`` (deterministic).
    Named non-window, non-auto containers push their ID onto the
    scope chain for their children.

    Raises:
        ValueError: If a user-provided ID contains ``/``.
    """
    ctx = _NormCtx(
        registry=registry,
        memo_prev=memo_cache_prev,
        memo_new=memo_cache_new,
        widget_prev=widget_cache_prev,
        widget_new=widget_cache_new,
    )

    if tree is None:
        return _empty_container()

    if isinstance(tree, list):
        if len(tree) == 0:
            return _empty_container()
        if len(tree) == 1:
            return _post_normalize(
                _normalize_with_scope(tree[0], "", 0, window_id=None, ctx=ctx)
            )
        normalized_children = [
            _normalize_with_scope(child, "", i, window_id=None, ctx=ctx)
            for i, child in enumerate(tree)
        ]
        _check_duplicate_ids(normalized_children)
        return _post_normalize(
            {
                "id": "root",
                "type": "container",
                "props": {},
                "children": normalized_children,
            }
        )

    return _post_normalize(_normalize_with_scope(tree, "", 0, window_id=None, ctx=ctx))


@dataclass(slots=True)
class _NormCtx:
    """Per-render normalization context.

    Threaded through ``_normalize_with_scope`` so recursion doesn't
    need to forward a growing list of optional arguments. The four
    cache dicts are optional; when ``None``, their feature (memo /
    widget view cache) is disabled.
    """

    registry: Any = None
    memo_prev: dict[Any, Any] | None = None
    memo_new: dict[Any, Any] | None = None
    widget_prev: dict[Any, Any] | None = None
    widget_new: dict[Any, Any] | None = None


def normalize_view(
    tree: None | Node | list[Node],
    *,
    registry: Any = None,
    memo_cache_prev: dict[Any, Any] | None = None,
    memo_cache_new: dict[Any, Any] | None = None,
    widget_cache_prev: dict[Any, Any] | None = None,
    widget_cache_new: dict[Any, Any] | None = None,
) -> Node:
    """Normalize a top-level app view and require explicit windows."""
    normalized = normalize(
        tree,
        registry=registry,
        memo_cache_prev=memo_cache_prev,
        memo_cache_new=memo_cache_new,
        widget_cache_prev=widget_cache_prev,
        widget_cache_new=widget_cache_new,
    )

    if normalized["type"] == "window":
        return normalized

    children = normalized.get("children", [])
    if children and all(
        isinstance(child, dict) and child.get("type") == "window" for child in children
    ):
        return normalized

    if _is_window_layout(normalized):
        return normalized

    raise ValueError(
        "view() must be a window tree: every top-level branch must end at a window node"
    )


def _is_window_layout(node: Node) -> bool:
    if node.get("type") == "window":
        return True
    if node.get("type") not in _WINDOW_LAYOUT_WRAPPERS:
        return False
    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    return bool(children) and all(_is_window_layout(child) for child in children)


_WINDOW_LAYOUT_WRAPPERS = frozenset(
    {
        "container",
        "scrollable",
        "pin",
        "float",
        "pointer_area",
        "sensor",
        "themer",
        "column",
        "row",
        "stack",
        "grid",
        "keyed_column",
        "responsive",
    }
)


def _empty_container() -> Node:
    """Return a fresh empty container (never mutate the constant)."""
    return {
        "id": "root",
        "type": "container",
        "props": {},
        "children": [],
    }


_MAX_TREE_DEPTH_WARN = 200
_MAX_TREE_DEPTH_HARD = 256


def _normalize_with_scope(
    node: Node,
    scope: str,
    index: int,
    *,
    window_id: str | None,
    ctx: _NormCtx,
    depth: int = 0,
) -> Node:
    """Normalize a single node with scope context.

    Args:
        node: Raw node dict (may have missing keys).
        scope: Current scope prefix (e.g. ``"sidebar/form"``).
        index: Child index within parent (for auto-ID generation).
        ctx: Per-render context (registry plus optional memo and
            widget view caches).
        depth: Current nesting depth (for max depth protection).
    """
    if depth >= _MAX_TREE_DEPTH_HARD:
        raise ValueError(
            f"UI tree exceeds maximum depth of {_MAX_TREE_DEPTH_HARD}. "
            "This usually indicates a circular widget composition."
        )
    if depth >= _MAX_TREE_DEPTH_WARN:
        logger.warning(
            "plushie: UI tree depth %d exceeds %d, which may indicate "
            "a circular widget composition",
            depth,
            _MAX_TREE_DEPTH_WARN,
        )
    raw_id = node.get("id")
    node_type = node.get("type", "container")
    props: dict[str, Any] = node.get("props") or {}
    children: list[Node] = node.get("children") or []

    # Auto-ID for nodes without an explicit ID
    node_id = f"auto:{node_type}:{index}" if raw_id is None else str(raw_id)
    is_auto = node_id.startswith("auto:")
    current_window_id = node_id if node_type == "window" else window_id

    # Validate user-provided IDs (auto-IDs skip validation).
    if not is_auto:
        if node_id == "":
            raise ValueError("widget ID must not be empty")
        if "/" in node_id:
            raise ValueError(
                f'widget ID {node_id!r} cannot contain "/" '
                "-- scoped paths are built automatically by named containers"
            )
        if "#" in node_id:
            raise ValueError(
                f'widget ID {node_id!r} cannot contain "#" '
                "-- # is a reserved separator for window-qualified paths"
            )
        if len(node_id.encode("utf-8")) > 1024:
            raise ValueError(
                f"widget ID {node_id!r} exceeds maximum length of 1024 bytes"
            )
        if not _VALID_ID_RE.match(node_id):
            raise ValueError(
                f"widget ID {node_id!r} contains invalid characters "
                "-- IDs must contain only printable ASCII (0x21-0x7E)"
            )

    # Apply scope prefix to this node's ID.
    # Window nodes keep their bare ID. Children of windows get "window#id".
    # Deeper descendants get "window#parent/id" (# only at window boundary).
    if is_auto:
        scoped_id = node_id
    elif scope.endswith("#"):
        scoped_id = f"{scope}{node_id}"
    elif scope:
        scoped_id = f"{scope}/{node_id}"
    else:
        scoped_id = node_id

    meta = node.get("meta")

    # __memo__ handling: reuse the cached subtree when deps match the
    # previous render's value. On a miss, evaluate the body, normalize
    # it, and stash the result for next render. When no caches are
    # threaded through (``ctx.memo_new is None``), still evaluate the
    # body so callers that don't maintain caches see the same tree
    # shape; it just re-evaluates every render.
    if node_type == "__memo__" and meta and "__memo_fun__" in meta:
        return _normalize_memo(
            node=node,
            scope=scope,
            scoped_id=scoped_id,
            window_id=current_window_id,
            ctx=ctx,
            depth=depth,
        )

    # Canvas widget rendering: if this node is a placeholder, render it
    # with stored state and normalize the output.
    if ctx.registry is not None and meta and "__widget__" in meta:
        try:
            from plushie.widget import _with_widget_metadata, render_placeholder

            widget_cls = meta.get("__widget__")
            widget_props = meta.get("__widget_props__", {})
            widget_cache_key_value: Any = None
            widget_cache_lookup_key: Any = None
            if (
                isinstance(widget_cls, type)
                and current_window_id is not None
                and ctx.widget_prev is not None
                and ctx.widget_new is not None
            ):
                existing_entry = ctx.registry.get(
                    (str(current_window_id), str(scoped_id))
                )
                if (
                    existing_entry is not None
                    and type(existing_entry.definition) is widget_cls
                ):
                    try:
                        widget_cache_key_value = existing_entry.definition.cache_key(
                            widget_props, existing_entry.state
                        )
                    except Exception:
                        widget_cache_key_value = None
                    if widget_cache_key_value is not None:
                        widget_cache_lookup_key = (
                            str(current_window_id),
                            str(scoped_id),
                        )
                        cached_entry = ctx.widget_prev.get(widget_cache_lookup_key)
                        if (
                            cached_entry is not None
                            and cached_entry[0] == widget_cache_key_value
                        ):
                            cached_node = _with_widget_metadata(
                                cached_entry[1],
                                widget_cls=widget_cls,
                                widget_props=widget_props,
                                widget_state=existing_entry.state,
                                widget_definition=existing_entry.definition,
                            )
                            ctx.widget_new[widget_cache_lookup_key] = (
                                widget_cache_key_value,
                                cached_node,
                            )
                            return cached_node

            placeholder = render_placeholder(
                node, current_window_id, scoped_id, node_id, ctx.registry
            )
            if placeholder is not None:
                _key, rendered_node, entry = placeholder
                rendered_type = rendered_node.get("type", "container")
                if rendered_type == "window":
                    child_scope = f"{scoped_id}#"
                else:
                    child_scope = scoped_id
                rendered_children = rendered_node.get("children") or []
                normalized_children = [
                    _normalize_with_scope(
                        c,
                        child_scope,
                        i,
                        window_id=current_window_id,
                        ctx=ctx,
                        depth=depth + 1,
                    )
                    for i, c in enumerate(rendered_children)
                ]
                rendered_props = _encode_props(dict(rendered_node.get("props") or {}))
                # Auto-apply standard widget options (a11y, event_rate)
                # from the original widget props so widget authors don't
                # have to manually forward them in view().
                props_raw = node.get("props") or {}
                for key in ("a11y", "event_rate"):
                    if key in props_raw and key not in rendered_props:
                        rendered_props[key] = _encode_prop_value(props_raw[key])
                rendered_props = _apply_a11y_defaults(
                    rendered_node.get("type", "canvas"), rendered_props
                )
                normalized_props = _resolve_a11y_id_refs(rendered_props, scope)
                result_node: Node = {
                    "id": scoped_id,
                    "type": rendered_node.get("type", "canvas"),
                    "props": normalized_props,
                    "children": normalized_children,
                    "meta": rendered_node.get("meta", {}),
                }
                if (
                    widget_cache_key_value is None
                    and isinstance(widget_cls, type)
                    and current_window_id is not None
                    and ctx.widget_new is not None
                ):
                    try:
                        widget_cache_key_value = entry.definition.cache_key(
                            widget_props, entry.state
                        )
                    except Exception:
                        widget_cache_key_value = None
                    if widget_cache_key_value is not None:
                        widget_cache_lookup_key = (
                            str(current_window_id),
                            str(scoped_id),
                        )
                if (
                    widget_cache_key_value is not None
                    and widget_cache_lookup_key is not None
                    and ctx.widget_new is not None
                ):
                    ctx.widget_new[widget_cache_lookup_key] = (
                        widget_cache_key_value,
                        result_node,
                    )
                return result_node
        except ValueError:
            raise
        except Exception:
            logger.exception("plushie: canvas widget render failed for %s", scoped_id)

    # Determine scope for children: window nodes set "window#" scope,
    # auto-ID nodes are transparent, named containers propagate their scoped ID.
    if node_type == "window":
        child_scope = f"{scoped_id}#"
    elif is_auto:
        child_scope = scope
    else:
        child_scope = scoped_id

    # Encode dataclass prop values to wire-compatible dicts/values,
    # apply a11y defaults, then resolve a11y ID refs relative to scope.
    encoded_props = _encode_props(dict(props))
    encoded_props = _apply_a11y_defaults(node_type, encoded_props)
    normalized_props = _resolve_a11y_id_refs(encoded_props, scope)

    # Normalize children
    normalized_children = _normalize_children(
        children,
        child_scope,
        window_id=current_window_id,
        ctx=ctx,
        depth=depth + 1,
    )

    result: Node = {
        "id": scoped_id,
        "type": node_type,
        "props": normalized_props,
        "children": normalized_children,
    }

    # Preserve meta if present. Never sent on the wire, not compared in diffs.
    if meta is not None:
        result["meta"] = meta

    return result


def _normalize_children(
    children: list[Node],
    scope: str,
    *,
    window_id: str | None,
    ctx: _NormCtx,
    depth: int = 0,
) -> list[Node]:
    """Normalize a list of child nodes, checking for duplicate IDs."""
    normalized = [
        _normalize_with_scope(
            child, scope, i, window_id=window_id, ctx=ctx, depth=depth
        )
        for i, child in enumerate(children)
    ]
    _check_duplicate_ids(normalized)
    normalized = _infer_radio_groups(normalized)
    return normalized


def _normalize_memo(
    *,
    node: Node,
    scope: str,
    scoped_id: str,
    window_id: str | None,
    ctx: _NormCtx,
    depth: int,
) -> Node:
    """Normalize a ``__memo__`` node, consulting the memo cache.

    Hit: reuse the previously-normalized subtree. Miss: invoke the
    body, normalize its output, and cache the result under the same
    key for the next render.

    When no memo caches are present on ``ctx``, evaluate the body
    every render (uncached fallback) so callers that opt out still
    get a valid tree.
    """
    meta = node.get("meta") or {}
    deps = meta.get("__memo_deps__")
    body = meta.get("__memo_fun__")
    cache_key = (scoped_id, scope, window_id, _safe_hashable(deps))

    if ctx.memo_prev is not None and ctx.memo_new is not None:
        cached = ctx.memo_prev.get(cache_key)
        if cached is not None and cached[0] == deps:
            ctx.memo_new[cache_key] = cached
            return cached[1]

    raw = body() if callable(body) else body
    normalized = _normalize_memo_body(
        raw=raw,
        scope=scope,
        scoped_id=scoped_id,
        window_id=window_id,
        ctx=ctx,
        depth=depth,
    )

    if ctx.memo_new is not None:
        ctx.memo_new[cache_key] = (deps, normalized)

    return normalized


def _safe_hashable(value: Any) -> Any:
    """Best-effort stable key component for memo cache lookup.

    Tuples stay tuples, lists become tuples, dicts become sorted
    item tuples, everything else passes through.
    """
    if isinstance(value, tuple):
        return tuple(_safe_hashable(v) for v in value)
    if isinstance(value, list):
        return tuple(_safe_hashable(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _safe_hashable(v)) for k, v in value.items()))
    return value


def _normalize_memo_body(
    *,
    raw: Any,
    scope: str,
    scoped_id: str,
    window_id: str | None,
    ctx: _NormCtx,
    depth: int,
) -> Node:
    """Evaluate a memo body's output and normalize it at the memo site.

    Accepts a single node, a list of nodes, or ``None``. Multi-child
    output is wrapped in a transparent auto-id container so the
    cache stores a single node.
    """
    if raw is None:
        return {
            "id": f"auto:memo:{scoped_id}",
            "type": "container",
            "props": {},
            "children": [],
        }

    if isinstance(raw, list):
        items = [r for r in raw if r is not None]
        if not items:
            return {
                "id": f"auto:memo:{scoped_id}",
                "type": "container",
                "props": {},
                "children": [],
            }
        if len(items) == 1:
            return _normalize_with_scope(
                items[0], scope, 0, window_id=window_id, ctx=ctx, depth=depth + 1
            )
        wrapper: Node = {
            "id": f"auto:memo_wrap:{scoped_id}",
            "type": "container",
            "props": {},
            "children": items,
        }
        return _normalize_with_scope(
            wrapper, scope, 0, window_id=window_id, ctx=ctx, depth=depth + 1
        )

    return _normalize_with_scope(
        raw, scope, 0, window_id=window_id, ctx=ctx, depth=depth + 1
    )


def _check_duplicate_ids(children: list[Node]) -> None:
    """Raise if sibling nodes have duplicate IDs."""
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
        raise ValueError(
            "duplicate sibling IDs detected during normalize: "
            + ", ".join(repr(dupe) for dupe in unique_dupes)
        )


def _encode_prop_value(value: Any) -> Any:
    """Convert a prop value to its wire-compatible representation.

    Types implementing :class:`WireEncodable` (with a ``to_wire()``
    method) are encoded automatically. Tuples are converted to lists
    (wire format uses arrays). Other values pass through unchanged.
    """
    if isinstance(value, WireEncodable):
        return value.to_wire()
    if isinstance(value, tuple):
        return list(value)
    return value


def _encode_props(props: dict[str, Any]) -> dict[str, Any]:
    """Encode all prop values, converting dataclass types to wire dicts."""
    return {k: _encode_prop_value(v) for k, v in props.items()}


def expand_rows(node: Node) -> Node:
    """Expand data-based table rows into table_row/table_cell children.

    If the node is a table with a ``rows`` prop but no children, the
    rows are converted into ``table_row``/``table_cell`` child nodes.
    Each cell gets a ``column`` prop matching its column key. The
    ``rows`` prop is removed from the node.

    If the node already has children or has no ``rows`` prop, it is
    returned unchanged.

    Raises:
        ValueError: If the node has both ``rows`` prop and children.
    """
    if node.get("type") != "table":
        return node

    props = dict(node.get("props", {}))
    rows = props.get("rows")
    children = node.get("children", [])

    if not rows:
        return node

    if children:
        raise ValueError(
            f"table {node.get('id')!r}: cannot combine rows prop "
            "with child nodes. Use one or the other."
        )

    columns = props.get("columns", [])
    col_keys = [
        str(col.get("key", col) if isinstance(col, dict) else col) for col in columns
    ]

    row_nodes: list[Node] = []
    for idx, row_data in enumerate(rows):
        row_id = row_data.get("id")
        row_id = str(row_id) if row_id else f"row_{idx}"
        cells: list[Node] = []
        for key in col_keys:
            raw_val = row_data.get(key)
            value = str(raw_val) if raw_val is not None else ""
            cells.append(
                {
                    "id": key,
                    "type": "table_cell",
                    "props": {"column": key},
                    "children": [
                        {
                            "id": f"{row_id}.{key}",
                            "type": "text",
                            "props": {"content": value},
                            "children": [],
                        }
                    ],
                }
            )
        row_nodes.append(
            {
                "id": row_id,
                "type": "table_row",
                "props": {},
                "children": cells,
            }
        )

    props.pop("rows", None)
    return {
        "id": node.get("id", ""),
        "type": "table",
        "props": props,
        "children": row_nodes,
    }
