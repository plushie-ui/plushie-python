"""Accessibility helpers for tree normalization."""

from __future__ import annotations

import logging
from typing import Any

from plushie.tree._types import Node

_TREE_LOGGER = logging.getLogger("plushie.tree")

_A11Y_ID_REF_KEYS = ("labelled_by", "described_by")

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

_A11Y_SINGLE_REF_KEYS = (
    "labelled_by",
    "described_by",
    "error_message",
    "active_descendant",
)

_NAMED_INTERACTIVE_TYPES = frozenset(
    {"button", "toggler", "checkbox", "pointer_area", "radio"}
)

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

_PLACEHOLDER_DESCRIPTION_WIDGETS = frozenset(
    {"text_input", "text_editor", "combo_box", "pick_list"}
)

_ALT_LABEL_WIDGETS = frozenset({"canvas", "image", "svg", "qr_code"})
_DESCRIPTION_WIDGETS = frozenset({"canvas"})

_VALIDATABLE_WIDGETS = frozenset(
    {"text_input", "text_editor", "checkbox", "pick_list", "combo_box"}
)


def _apply_a11y_defaults(node_type: str, props: dict[str, Any]) -> dict[str, Any]:
    """Apply per-widget a11y defaults and resolve label_from directives."""
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
    """Infer position_in_set and size_of_set for radio button groups."""
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
    tooltip_for_children = node.get("id", "") if node.get("type") == "tooltip" else None
    for child in node.get("children", []):
        _rewrite_a11y(child, child_scope, declared, radio_groups, tooltip_for_children)


def _placeholder_description(kind: str, props: dict[str, Any]) -> str | None:
    if kind not in _PLACEHOLDER_DESCRIPTION_WIDGETS:
        return None
    return _non_empty_string_prop(props, "placeholder")


def _non_empty_string_prop(props: dict[str, Any], key: str) -> str | None:
    value = props.get(key)
    return value if isinstance(value, str) and value else None


def _suppresses_alt_label(props: dict[str, Any]) -> bool:
    if props.get("decorative") is True:
        return True
    a11y = props.get("a11y")
    return isinstance(a11y, dict) and a11y.get("hidden") is True


def _alt_label(kind: str, props: dict[str, Any]) -> str | None:
    if kind not in _ALT_LABEL_WIDGETS:
        return None
    alt = _non_empty_string_prop(props, "alt")
    if alt is None:
        return None
    if _suppresses_alt_label(props):
        return None
    return alt


def _description(kind: str, props: dict[str, Any]) -> str | None:
    if kind not in _DESCRIPTION_WIDGETS:
        return None
    return _non_empty_string_prop(props, "description")


def _required_from_props(kind: str, props: dict[str, Any]) -> bool | None:
    if kind not in _VALIDATABLE_WIDGETS:
        return None
    req = props.get("required")
    return req if isinstance(req, bool) else None


def _invalid_from_props(
    kind: str, props: dict[str, Any]
) -> tuple[bool | None, str | None]:
    """Project a validation prop onto (a11y.invalid, a11y.error_message)."""
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
    description = _description(kind, props)
    alt_label = _alt_label(kind, props)
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
        or description is not None
        or alt_label is not None
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

    if description is not None and "description" not in a11y:
        a11y["description"] = description

    if alt_label is not None and "label" not in a11y:
        a11y["label"] = alt_label

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
    _TREE_LOGGER.warning(
        "a11y_ref_unresolved: a11y.%s %r on %r does not match any declared widget ID",
        key,
        ref,
        owner_id,
    )


def _check_missing_accessible_name(node: Node) -> None:
    kind = node.get("type", "")
    if kind in _NAMED_INTERACTIVE_TYPES and not _has_accessible_name(node):
        _TREE_LOGGER.warning(
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
    """Resolve a11y ID references relative to the current scope."""
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
    """Prefix an ID reference with the current scope."""
    if not scope or not ref or "/" in ref or "#" in ref:
        return ref
    if scope.endswith("#"):
        return f"{scope}{ref}"
    return f"{scope}/{ref}"
