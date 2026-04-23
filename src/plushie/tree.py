"""Tree normalization, diffing, and search utilities.

Provides the core tree operations for the plushie SDK:

- **normalize** - assign auto-IDs, resolve scoped IDs, validate
  constraints, resolve a11y cross-references.
- **diff** - produce minimal patch operations (replace_node,
  update_props, insert_child, remove_child) for incremental
  renderer updates.
- **find / find_all / exists / ids** - tree search utilities.
- **text_of** - extract display text from a node.

Tree nodes are plain dicts with the shape::

    {"id": "btn", "type": "button", "props": {"label": "Click"}, "children": []}

Reference: plushie-elixir ``lib/plushie/tree.ex`` for the exact
diff algorithm and normalization rules.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("plushie")

_VALID_ID_RE = re.compile(r"^[\x21-\x7e]+$")

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

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

_WIDGET_A11Y_DEFAULTS: dict[str, dict[str, Any]] = {
    "button": {"role": "button", "label_from": "label"},
    "canvas": {"role": "canvas"},
    "checkbox": {"role": "check_box", "label_from": "label"},
    "combo_box": {
        "role": "combo_box",
        "has_popup": "listbox",
        "label_from": "placeholder",
    },
    "image": {"role": "image"},
    "markdown": {"role": "document"},
    "pane_grid": {"role": "group"},
    "pick_list": {
        "role": "combo_box",
        "has_popup": "listbox",
        "label_from": "placeholder",
    },
    "progress_bar": {"role": "progress_indicator"},
    "qr_code": {"role": "image"},
    "radio": {"role": "radio_button", "label_from": "label"},
    "rich_text": {"role": "label"},
    "rule": {"role": "splitter"},
    "scrollable": {"role": "scroll_view"},
    "slider": {"role": "slider"},
    "svg": {"role": "image"},
    "table": {"role": "table"},
    "text": {"role": "label", "label_from": "content"},
    "text_editor": {"role": "multiline_text_input", "label_from": "placeholder"},
    "text_input": {"role": "text_input", "label_from": "placeholder"},
    "toggler": {"role": "switch", "label_from": "label"},
    "tooltip": {"role": "tooltip"},
    "vertical_slider": {"role": "slider"},
    "window": {"role": "window"},
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

    raise ValueError(
        "view() must return a window node or a root node whose direct children are window nodes"
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


def _apply_a11y_defaults(node_type: str, props: dict[str, Any]) -> dict[str, Any]:
    """Apply per-widget a11y defaults and resolve label_from directives.

    If no a11y prop exists and the widget type has defaults, creates an a11y
    dict from defaults. User-provided a11y replaces defaults entirely (no merge).

    The ``label_from`` directive copies the named prop's value into the a11y
    ``label`` field when ``label`` is not already set. ``label_from`` is always
    removed before the a11y dict goes on the wire (it is a build-time directive).
    """
    defaults = _WIDGET_A11Y_DEFAULTS.get(node_type)
    raw_a11y = props.get("a11y")

    if raw_a11y is None:
        if defaults is None:
            return props
        a11y: dict[str, Any] = dict(defaults)
    elif isinstance(raw_a11y, dict):
        a11y = dict(raw_a11y)
    else:
        return props

    label_from = a11y.pop("label_from", None)
    if label_from and "label" not in a11y:
        source_value = props.get(str(label_from))
        if source_value is not None:
            a11y["label"] = str(source_value)

    if a11y:
        return {**props, "a11y": a11y}

    result = dict(props)
    result.pop("a11y", None)
    return result


def _infer_radio_groups(children: list[Node]) -> list[Node]:
    """Infer position_in_set and size_of_set for radio button groups.

    Scans sibling children for radio widgets with a ``group`` prop,
    groups them by that value, and patches their a11y with set position
    and size. Manual overrides are respected: if position_in_set is already
    set, only size_of_set is backfilled.
    """
    radio_groups: dict[str, list[tuple[int, Node]]] = {}
    for idx, child in enumerate(children):
        if child.get("type") == "radio":
            group_prop = child.get("props", {}).get("group")
            if isinstance(group_prop, str) and group_prop:
                radio_groups.setdefault(group_prop, []).append((idx, child))

    if not radio_groups:
        return children

    patches: dict[int, dict[str, Any]] = {}
    for members in radio_groups.values():
        size = len(members)
        for pos, (child_idx, node) in enumerate(members, 1):
            a11y = dict(node.get("props", {}).get("a11y") or {})
            has_position = "position_in_set" in a11y
            has_size = "size_of_set" in a11y

            if has_position and has_size:
                continue
            elif has_position:
                a11y["size_of_set"] = size
            else:
                a11y["position_in_set"] = pos
                a11y["size_of_set"] = size

            patches[child_idx] = a11y

    if not patches:
        return children

    return [
        dict(child, props={**child["props"], "a11y": patches[idx]})
        if idx in patches
        else child
        for idx, child in enumerate(children)
    ]


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


# ---------------------------------------------------------------------------
# Post-normalize a11y pass
# ---------------------------------------------------------------------------
#
# Runs after the first pass produces a fully scoped tree. Mirrors the
# Rust SDK: auto-populate a11y.role, rewrite active_descendant and
# radio_group list refs, populate implicit radio_group when radios
# share a ``group`` prop, emit a11y_ref_unresolved diagnostics for
# dangling refs, emit missing_accessible_name diagnostics for
# interactive widgets with no accessible name source.

_A11Y_SINGLE_REF_KEYS = (
    "labelled_by",
    "described_by",
    "error_message",
    "active_descendant",
)

_NAMED_INTERACTIVE_TYPES = frozenset({"button", "toggler", "checkbox", "pointer_area"})

_WIDGET_ROLE_DEFAULTS: dict[str, str] = {
    "button": "button",
    "checkbox": "check_box",
    "toggler": "switch",
    "radio": "radio_button",
    "text_input": "text_input",
    "text_editor": "multiline_text_input",
    "text": "label",
    "rich_text": "label",
    "slider": "slider",
    "vertical_slider": "slider",
    "pick_list": "combo_box",
    "combo_box": "combo_box",
    "progress_bar": "progress_indicator",
    "image": "image",
    "svg": "image",
    "qr_code": "image",
    "scrollable": "scroll_view",
    "container": "generic_container",
    "column": "generic_container",
    "row": "generic_container",
    "stack": "generic_container",
    "grid": "generic_container",
    "pane_grid": "generic_container",
    "table": "table",
    "canvas": "canvas",
    "rule": "separator",
}


def _post_normalize(tree: Node) -> Node:
    """Run the a11y post-pass on an already-scoped tree in-place."""
    declared: set[str] = set()
    _collect_declared_ids(tree, declared)
    radio_groups: dict[tuple[str, str], list[str]] = {}
    _collect_radio_groups(tree, "", radio_groups)
    _rewrite_a11y(tree, "", declared, radio_groups)
    _check_missing_accessible_name(tree)
    return tree


def _collect_declared_ids(node: Node, out: set[str]) -> None:
    """Collect every non-auto, non-empty scoped ID present in the tree."""
    node_id = node.get("id", "")
    if isinstance(node_id, str) and node_id and not node_id.startswith("auto:"):
        out.add(node_id)
    for child in node.get("children", []):
        _collect_declared_ids(child, out)


def _child_scope_of(node: Node, scope: str) -> str:
    kind = node.get("type", "")
    node_id = node.get("id", "")
    if kind == "window":
        return f"{node_id}#"
    if not node_id or (isinstance(node_id, str) and node_id.startswith("auto:")):
        return scope
    return node_id


def _collect_radio_groups(
    node: Node,
    scope: str,
    out: dict[tuple[str, str], list[str]],
) -> None:
    if node.get("type") == "radio":
        group = _fetch_group_prop(node.get("props") or {})
        if group:
            key = (scope, group)
            out.setdefault(key, []).append(node.get("id", ""))
    child_scope = _child_scope_of(node, scope)
    for child in node.get("children", []):
        _collect_radio_groups(child, child_scope, out)


def _fetch_group_prop(props: dict[str, Any]) -> str | None:
    group = props.get("group")
    return group if isinstance(group, str) and group else None


def _rewrite_a11y(
    node: Node,
    scope: str,
    declared: set[str],
    radio_groups: dict[tuple[str, str], list[str]],
    tooltip_parent_id: str | None = None,
) -> None:
    _apply_a11y_rewrites(node, scope, declared, radio_groups, tooltip_parent_id)
    child_scope = _child_scope_of(node, scope)
    # A tooltip's children are its trigger content; flow described_by
    # down to them so AT announces the tip text when focus lands there.
    tooltip_for_children = node.get("id", "") if node.get("type") == "tooltip" else None
    for child in node.get("children", []):
        _rewrite_a11y(child, child_scope, declared, radio_groups, tooltip_for_children)


# Widget types that project :placeholder -> a11y.description.
_PLACEHOLDER_DESCRIPTION_WIDGETS = frozenset(
    {"text_input", "text_editor", "combo_box", "pick_list"}
)

# Widget types that honour :required / :validation builder props.
_VALIDATABLE_WIDGETS = frozenset(
    {"text_input", "text_editor", "checkbox", "pick_list", "combo_box"}
)


def _placeholder_description(kind: str, props: dict[str, Any]) -> str | None:
    if kind not in _PLACEHOLDER_DESCRIPTION_WIDGETS:
        return None
    ph = props.get("placeholder")
    return ph if isinstance(ph, str) and ph else None


def _required_from_props(kind: str, props: dict[str, Any]) -> bool | None:
    if kind not in _VALIDATABLE_WIDGETS:
        return None
    req = props.get("required")
    return req if isinstance(req, bool) else None


def _invalid_from_props(
    kind: str, props: dict[str, Any]
) -> tuple[bool | None, str | None]:
    """Project a validation prop onto (a11y.invalid, a11y.error_message).

    Accepted shapes mirror the Elixir SDK's permissive matcher:

    - ``"valid"`` (or ``ValidationState.VALID``)                    -> (False, None)
    - ``"pending"`` / ``ValidationState.PENDING``                   -> (None, None)
    - ``("invalid", message)`` / ``["invalid", message]``           -> (True, message)
    - ``{"state": "invalid", "message": m}``                        -> (True, m)
    - ``{"state": "valid"}``                                        -> (False, None)
    """
    if kind not in _VALIDATABLE_WIDGETS:
        return (None, None)
    v = props.get("validation")
    if v is None:
        return (None, None)
    if v in ("valid",):
        return (False, None)
    if v in ("pending",):
        return (None, None)
    if isinstance(v, tuple) and len(v) == 2 and v[0] == "invalid":
        msg = v[1]
        return (True, msg if isinstance(msg, str) else None)
    if isinstance(v, list) and len(v) == 2 and v[0] == "invalid":
        msg = v[1]
        return (True, msg if isinstance(msg, str) else None)
    if isinstance(v, dict):
        state = v.get("state")
        if state == "valid":
            return (False, None)
        if state == "pending":
            return (None, None)
        if state == "invalid":
            msg = v.get("message")
            return (True, msg if isinstance(msg, str) else None)
    return (None, None)


def _apply_a11y_rewrites(
    node: Node,
    scope: str,
    declared: set[str],
    radio_groups: dict[tuple[str, str], list[str]],
    tooltip_parent_id: str | None = None,
) -> None:
    kind = node.get("type", "")
    owner_id = node.get("id", "")
    props = node.get("props")
    if not isinstance(props, dict):
        return

    role_default = _WIDGET_ROLE_DEFAULTS.get(kind)
    radio_ids: list[str] | None = None
    if kind == "radio":
        group = _fetch_group_prop(props)
        if group:
            radio_ids = radio_groups.get((scope, group))

    placeholder_desc = _placeholder_description(kind, props)
    required_prop = _required_from_props(kind, props)
    invalid_prop, error_text = _invalid_from_props(kind, props)

    existing_a11y = props.get("a11y")
    a11y: dict[str, Any] | None = (
        dict(existing_a11y) if isinstance(existing_a11y, dict) else None
    )

    needs_update = (
        (role_default is not None and not (a11y and "role" in a11y))
        or radio_ids is not None
        or (a11y is not None and _has_any_ref(a11y))
        or placeholder_desc is not None
        or required_prop is not None
        or invalid_prop is not None
        or error_text is not None
        or tooltip_parent_id is not None
    )

    if a11y is None and not needs_update:
        return

    if a11y is None:
        a11y = {}

    if role_default is not None and "role" not in a11y:
        a11y["role"] = role_default

    for key in _A11Y_SINGLE_REF_KEYS:
        ref = a11y.get(key)
        if isinstance(ref, str) and ref:
            rewritten = _scope_ref(ref, scope)
            if rewritten not in declared:
                _warn_unresolved(key, ref, owner_id)
            a11y[key] = rewritten

    existing_group = a11y.get("radio_group")
    if isinstance(existing_group, list):
        rewritten_group: list[Any] = []
        for item in existing_group:
            if isinstance(item, str) and item:
                r = _scope_ref(item, scope)
                if r not in declared:
                    _warn_unresolved("radio_group", item, owner_id)
                rewritten_group.append(r)
            else:
                rewritten_group.append(item)
        a11y["radio_group"] = rewritten_group
    elif radio_ids is not None:
        a11y["radio_group"] = list(radio_ids)

    if placeholder_desc is not None and "description" not in a11y:
        a11y["description"] = placeholder_desc

    if required_prop is True and "required" not in a11y:
        a11y["required"] = True

    if invalid_prop is not None and "invalid" not in a11y:
        a11y["invalid"] = invalid_prop

    if error_text is not None and "error_message" not in a11y:
        a11y["error_message"] = error_text

    if tooltip_parent_id is not None and "described_by" not in a11y:
        a11y["described_by"] = tooltip_parent_id

    props["a11y"] = a11y


def _has_any_ref(a11y: dict[str, Any]) -> bool:
    for key in _A11Y_SINGLE_REF_KEYS:
        if key in a11y:
            return True
    return "radio_group" in a11y


def _warn_unresolved(key: str, ref: str, owner_id: str) -> None:
    import logging

    logging.getLogger("plushie.tree").warning(
        "a11y_ref_unresolved: a11y.%s %r on %r does not match any declared widget ID",
        key,
        ref,
        owner_id,
    )


def _check_missing_accessible_name(node: Node) -> None:
    kind = node.get("type", "")
    if kind in _NAMED_INTERACTIVE_TYPES and not _has_accessible_name(node):
        import logging

        logging.getLogger("plushie.tree").warning(
            "missing_accessible_name: %s %r has no label, text child, "
            "a11y.label, or a11y.labelled_by; screen readers will announce no name",
            kind,
            node.get("id", ""),
        )
    for child in node.get("children", []):
        _check_missing_accessible_name(child)


def _has_accessible_name(node: Node) -> bool:
    props = node.get("props") or {}
    label = props.get("label")
    if isinstance(label, str) and label:
        return True
    a11y = props.get("a11y")
    if isinstance(a11y, dict):
        a11y_label = a11y.get("label")
        if isinstance(a11y_label, str) and a11y_label:
            return True
        a11y_lb = a11y.get("labelled_by")
        if isinstance(a11y_lb, str) and a11y_lb:
            return True
    return _has_text_child(node.get("children", []))


def _has_text_child(children: list[Node]) -> bool:
    for child in children:
        if child.get("type") == "text":
            content = (child.get("props") or {}).get("content")
            if isinstance(content, str) and content:
                return True
        if _has_text_child(child.get("children", [])):
            return True
    return False


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

    Already-scoped references (containing ``/`` or ``#``) pass through
    unchanged. Handles the ``#`` window boundary: if scope ends with
    ``#``, the ref is appended directly (e.g. ``"main#"`` + ``"label"``
    -> ``"main#label"``).
    """
    if not scope or not ref or "/" in ref or "#" in ref:
        return ref
    if scope.endswith("#"):
        return f"{scope}{ref}"
    return f"{scope}/{ref}"


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


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "Node",
    "PatchOp",
    "ScopedId",
    "WireEncodable",
    "diff",
    "exists",
    "expand_rows",
    "find",
    "find_all",
    "ids",
    "normalize",
    "normalize_view",
    "text_of",
]
