"""Tests for plushie.tree: normalization, diffing, and search."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from plushie.framing import MsgpackFraming
from plushie.tree import (
    diff,
    exists,
    expand_rows,
    find,
    find_all,
    ids,
    normalize,
    text_of,
)
from plushie.types import (
    A11y,
    Border,
    Font,
    Gradient,
    Shadow,
    StyleMap,
    Theme,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(
    node_id: str,
    node_type: str = "container",
    props: dict | None = None,
    children: list | None = None,
) -> dict:
    """Shorthand for building a tree node dict."""
    return {
        "id": node_id,
        "type": node_type,
        "props": props or {},
        "children": children or [],
    }


# ===========================================================================
# Normalize
# ===========================================================================


class TestNormalizeNone:
    def test_returns_empty_container(self) -> None:
        result = normalize(None)
        assert result["id"] == "root"
        assert result["type"] == "container"
        assert result["props"] == {}
        assert result["children"] == []


class TestNormalizeEmptyList:
    def test_returns_empty_container(self) -> None:
        result = normalize([])
        assert result["id"] == "root"
        assert result["type"] == "container"


class TestNormalizeSingleElementList:
    def test_unwraps_single_element(self) -> None:
        node = _node("main", "window")
        result = normalize([node])
        assert result["id"] == "main"
        assert result["type"] == "window"


class TestNormalizeMultipleElementList:
    def test_wraps_in_root_container(self) -> None:
        nodes = [_node("win1", "window"), _node("win2", "window")]
        result = normalize(nodes)
        assert result["id"] == "root"
        assert result["type"] == "container"
        assert len(result["children"]) == 2
        assert result["children"][0]["id"] == "win1"
        assert result["children"][1]["id"] == "win2"


class TestNormalizeSingleNode:
    def test_preserves_explicit_id(self) -> None:
        result = normalize(_node("my-btn", "button", {"label": "Hi"}))
        assert result["id"] == "my-btn"
        assert result["type"] == "button"
        assert result["props"]["label"] == "Hi"
        assert result["children"] == []

    def test_fills_missing_fields(self) -> None:
        result = normalize({"id": "x"})
        assert result["type"] == "container"
        # Post-normalize auto-populates a11y.role from the widget type.
        assert result["props"] == {"a11y": {"role": "generic_container"}}
        assert result["children"] == []


class TestNormalizeAutoId:
    def test_assigns_auto_id_when_none(self) -> None:
        node = {"type": "text", "props": {"content": "Hello"}}
        result = normalize(node)
        assert result["id"] == "auto:text:0"

    def test_auto_id_uses_child_index(self) -> None:
        parent = _node(
            "root",
            "container",
            children=[
                {"type": "text", "props": {"content": "A"}},
                {"type": "button", "props": {"label": "B"}},
            ],
        )
        result = normalize(parent)
        assert result["children"][0]["id"] == "auto:text:0"
        assert result["children"][1]["id"] == "auto:button:1"

    def test_auto_id_defaults_to_container_type(self) -> None:
        node: dict = {"props": {"x": 1}}
        result = normalize(node)
        assert result["id"] == "auto:container:0"


class TestNormalizeSlashValidation:
    def test_rejects_slash_in_user_id(self) -> None:
        with pytest.raises(ValueError, match="/"):
            normalize(_node("bad/id", "button"))

    def test_rejects_hash_in_user_id(self) -> None:
        with pytest.raises(ValueError, match="#"):
            normalize(_node("bad#id", "button"))

    def test_rejects_empty_id(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            normalize(_node("", "button"))

    def test_rejects_non_ascii(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            normalize(_node("héllo", "button"))

    def test_rejects_control_chars(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            normalize(_node("bad\nid", "button"))

    def test_rejects_space(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            normalize(_node("bad id", "button"))

    def test_rejects_oversized_id(self) -> None:
        with pytest.raises(ValueError, match="1024"):
            normalize(_node("x" * 1025, "button"))

    def test_accepts_valid_id(self) -> None:
        result = normalize(_node("my-button_123", "button"))
        assert result["id"] == "my-button_123"

    def test_allows_auto_id_with_colon(self) -> None:
        """Auto-IDs are internal and always valid."""
        node = {"type": "text", "props": {}}
        result = normalize(node)
        assert result["id"].startswith("auto:")


class TestNormalizeScopedIds:
    def test_named_container_scopes_children(self) -> None:
        parent = _node(
            "form",
            "container",
            children=[
                _node("email", "text_input"),
                _node("submit", "button"),
            ],
        )
        result = normalize(parent)
        assert result["id"] == "form"
        assert result["children"][0]["id"] == "form/email"
        assert result["children"][1]["id"] == "form/submit"

    def test_nested_scoping(self) -> None:
        tree = _node(
            "page",
            "container",
            children=[
                _node(
                    "form",
                    "container",
                    children=[
                        _node("save", "button"),
                    ],
                ),
            ],
        )
        result = normalize(tree)
        assert result["children"][0]["id"] == "page/form"
        assert result["children"][0]["children"][0]["id"] == "page/form/save"

    def test_window_does_not_scope(self) -> None:
        tree = _node(
            "main",
            "window",
            children=[
                _node("btn", "button"),
            ],
        )
        result = normalize(tree)
        # Window nodes scope their children with the "window#" prefix
        assert result["children"][0]["id"] == "main#btn"

    def test_auto_id_node_does_not_scope(self) -> None:
        tree = _node(
            "page",
            "container",
            children=[
                {
                    "type": "container",
                    "children": [
                        _node("btn", "button"),
                    ],
                },
            ],
        )
        result = normalize(tree)
        # The unnamed container gets auto-ID, doesn't add scope
        auto_child = result["children"][0]
        assert auto_child["id"].startswith("auto:")
        # Its child gets page scope (from grandparent), not auto scope
        assert auto_child["children"][0]["id"] == "page/btn"

    def test_root_list_wrapper_does_not_scope(self) -> None:
        """Synthetic root from list normalization doesn't scope."""
        nodes = [
            _node(
                "a",
                "container",
                children=[
                    _node("x", "button"),
                ],
            ),
            _node(
                "b",
                "container",
                children=[
                    _node("y", "button"),
                ],
            ),
        ]
        result = normalize(nodes)
        # Root "root" is a synthetic wrapper; children get their own scope
        assert result["children"][0]["children"][0]["id"] == "a/x"
        assert result["children"][1]["children"][0]["id"] == "b/y"


class TestNormalizeA11yRefs:
    def test_resolves_labelled_by_in_scope(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("label", "text", {"content": "Name"}),
                _node(
                    "input",
                    "text_input",
                    {
                        "a11y": {"labelled_by": "label"},
                    },
                ),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][1]["props"]["a11y"]
        assert a11y["labelled_by"] == "form/label"

    def test_resolves_described_by(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("help", "text"),
                _node(
                    "input",
                    "text_input",
                    {
                        "a11y": {"described_by": "help"},
                    },
                ),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][1]["props"]["a11y"]
        assert a11y["described_by"] == "form/help"

    def test_resolves_error_message(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("err", "text"),
                _node(
                    "input",
                    "text_input",
                    {
                        "a11y": {"error_message": "err"},
                    },
                ),
            ],
        )
        result = normalize(tree)
        assert result["children"][1]["props"]["a11y"]["error_message"] == "form/err"

    def test_already_scoped_ref_unchanged(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node(
                    "input",
                    "text_input",
                    {
                        "a11y": {"labelled_by": "other/label"},
                    },
                ),
            ],
        )
        result = normalize(tree)
        assert result["children"][0]["props"]["a11y"]["labelled_by"] == "other/label"

    def test_no_scope_leaves_ref_unchanged(self) -> None:
        tree = _node(
            "main",
            "window",
            children=[
                _node(
                    "input",
                    "text_input",
                    {
                        "a11y": {"labelled_by": "label"},
                    },
                ),
            ],
        )
        result = normalize(tree)
        # Window scopes its children with "main#", so the ref is prefixed
        assert result["children"][0]["props"]["a11y"]["labelled_by"] == "main#label"

    def test_a11y_defaults_applied(self) -> None:
        tree = _node("btn", "button", {"label": "OK"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "button"
        assert a11y["label"] == "OK"


class TestNormalizeA11yBuilderDefaults:
    """Normalizer projections from widget-level props onto a11y."""

    def test_placeholder_flows_into_description(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("email", "text_input", {"placeholder": "Your email"}),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][0]["props"]["a11y"]
        assert a11y["description"] == "Your email"

    def test_explicit_description_wins_over_placeholder(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node(
                    "email",
                    "text_input",
                    {"placeholder": "Ph", "a11y": {"description": "Explicit"}},
                ),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][0]["props"]["a11y"]
        assert a11y["description"] == "Explicit"

    def test_required_prop_flows_into_a11y_required(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("email", "text_input", {"required": True}),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][0]["props"]["a11y"]
        assert a11y["required"] is True

    def test_validation_invalid_flows_into_a11y(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node(
                    "email",
                    "text_input",
                    {"validation": ("invalid", "Not a valid email")},
                ),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][0]["props"]["a11y"]
        assert a11y["invalid"] is True
        assert a11y["error_message"] == "Not a valid email"

    def test_validation_valid_sets_invalid_false(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("email", "text_input", {"validation": "valid"}),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][0]["props"]["a11y"]
        assert a11y["invalid"] is False

    def test_tooltip_scopes_described_by_onto_trigger_child(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node(
                    "help",
                    "tooltip",
                    {"tip": "Enter your email"},
                    children=[_node("email", "text_input", {})],
                ),
            ],
        )
        result = normalize(tree)
        trigger = result["children"][0]["children"][0]
        assert trigger["props"]["a11y"]["described_by"] == "form/help"


class TestA11yDefaults:
    """Per-widget a11y defaults applied during normalization."""

    def test_button_defaults(self) -> None:
        tree = _node("save", "button", {"label": "Save"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "button"
        assert a11y["label"] == "Save"

    def test_text_defaults_with_content(self) -> None:
        tree = {"type": "text", "props": {"content": "Hello"}}
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "label"
        assert a11y["label"] == "Hello"

    def test_text_input_defaults_from_placeholder(self) -> None:
        tree = _node("search", "text_input", {"value": "", "placeholder": "Search..."})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "text_input"
        assert a11y["label"] == "Search..."

    def test_checkbox_defaults_from_label(self) -> None:
        tree = _node("agree", "checkbox", {"checked": False, "label": "I agree"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "check_box"
        assert a11y["label"] == "I agree"

    def test_combo_box_has_popup(self) -> None:
        tree = _node(
            "cb",
            "combo_box",
            {"options": [], "selected": None, "placeholder": "Choose"},
        )
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "combo_box"
        assert a11y["has_popup"] == "listbox"
        assert a11y["label"] == "Choose"

    def test_pick_list_has_popup(self) -> None:
        tree = _node(
            "pl",
            "pick_list",
            {"options": ["a", "b"], "selected": None, "placeholder": "Pick"},
        )
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "combo_box"
        assert a11y["has_popup"] == "listbox"
        assert a11y["label"] == "Pick"

    def test_slider_defaults(self) -> None:
        tree = _node("vol", "slider", {"range": [0, 100], "value": 50})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "slider"
        assert "label" not in a11y

    def test_image_defaults(self) -> None:
        tree = _node("img", "image", {"source": "photo.png"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "image"

    def test_window_defaults(self) -> None:
        tree = _node("main", "window", {"title": "App"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "window"

    def test_container_has_generic_container_role(self) -> None:
        tree = _node("box", "container")
        result = normalize(tree)
        # Post-normalize maps container to the generic_container role.
        assert result["props"]["a11y"]["role"] == "generic_container"

    def test_column_has_generic_container_role(self) -> None:
        tree = {"type": "column", "props": {}, "children": []}
        result = normalize(tree)
        assert result["props"]["a11y"]["role"] == "generic_container"

    def test_rule_defaults(self) -> None:
        tree = {"type": "rule", "props": {}}
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "splitter"

    def test_progress_bar_defaults(self) -> None:
        tree = {"type": "progress_bar", "props": {"range": [0, 100], "value": 50}}
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "progress_indicator"

    def test_scrollable_defaults(self) -> None:
        tree = _node("scroll", "scrollable")
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "scroll_view"

    def test_toggler_defaults(self) -> None:
        tree = _node("toggle", "toggler", {"is_toggled": False, "label": "Dark mode"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "switch"
        assert a11y["label"] == "Dark mode"

    def test_text_editor_defaults(self) -> None:
        tree = _node("ed", "text_editor", {"content": "", "placeholder": "Type here"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "multiline_text_input"
        assert a11y["label"] == "Type here"

    def test_markdown_defaults(self) -> None:
        tree = {"type": "markdown", "props": {"content": "# Hello"}}
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "document"

    def test_user_a11y_merges_with_defaults(self) -> None:
        tree = _node("btn", "button", {"label": "Go", "a11y": {"label": "Custom"}})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        # User-provided label wins; post-normalize still supplies the
        # widget-type role since the author didn't specify one.
        assert a11y["label"] == "Custom"
        assert a11y["role"] == "button"

    def test_user_a11y_dataclass_replaces_defaults(self) -> None:
        tree = _node("btn", "button", {"label": "Go", "a11y": A11y(role="link")})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "link"
        assert "label" not in a11y

    def test_label_from_not_in_wire_output(self) -> None:
        tree = _node("btn", "button", {"label": "Go"})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert "label_from" not in a11y

    def test_no_label_from_when_label_prop_missing(self) -> None:
        tree = _node("btn", "button", {})
        result = normalize(tree)
        a11y = result["props"]["a11y"]
        assert a11y["role"] == "button"
        assert "label" not in a11y


class TestRadioA11yInference:
    """Radio group position_in_set / size_of_set inference during normalize."""

    def test_radio_group_inference(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node(
                    "r1",
                    "radio",
                    {"value": "a", "selected": "a", "label": "A", "group": "colors"},
                ),
                _node(
                    "r2",
                    "radio",
                    {"value": "b", "selected": "a", "label": "B", "group": "colors"},
                ),
                _node(
                    "r3",
                    "radio",
                    {"value": "c", "selected": "a", "label": "C", "group": "colors"},
                ),
            ],
        )
        result = normalize(tree)
        children = result["children"]
        for i, child in enumerate(children, 1):
            a11y = child["props"]["a11y"]
            assert a11y["position_in_set"] == i
            assert a11y["size_of_set"] == 3

    def test_multiple_groups(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("r1", "radio", {"value": "a", "selected": "a", "group": "g1"}),
                _node("r2", "radio", {"value": "b", "selected": "a", "group": "g1"}),
                _node("r3", "radio", {"value": "x", "selected": "x", "group": "g2"}),
            ],
        )
        result = normalize(tree)
        children = result["children"]
        assert children[0]["props"]["a11y"]["position_in_set"] == 1
        assert children[0]["props"]["a11y"]["size_of_set"] == 2
        assert children[1]["props"]["a11y"]["position_in_set"] == 2
        assert children[1]["props"]["a11y"]["size_of_set"] == 2
        assert children[2]["props"]["a11y"]["position_in_set"] == 1
        assert children[2]["props"]["a11y"]["size_of_set"] == 1

    def test_no_group_prop_skipped(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("r1", "radio", {"value": "a", "selected": "a"}),
            ],
        )
        result = normalize(tree)
        a11y = result["children"][0]["props"]["a11y"]
        assert "position_in_set" not in a11y
        assert "size_of_set" not in a11y

    def test_manual_position_respected(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node(
                    "r1",
                    "radio",
                    {
                        "value": "a",
                        "selected": "a",
                        "group": "g",
                        "a11y": {"position_in_set": 5},
                    },
                ),
                _node("r2", "radio", {"value": "b", "selected": "a", "group": "g"}),
            ],
        )
        result = normalize(tree)
        c0_a11y = result["children"][0]["props"]["a11y"]
        assert c0_a11y["position_in_set"] == 5
        assert c0_a11y["size_of_set"] == 2

        c1_a11y = result["children"][1]["props"]["a11y"]
        assert c1_a11y["position_in_set"] == 2
        assert c1_a11y["size_of_set"] == 2

    def test_manual_position_and_size_skipped(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node(
                    "r1",
                    "radio",
                    {
                        "value": "a",
                        "selected": "a",
                        "group": "g",
                        "a11y": {"position_in_set": 1, "size_of_set": 10},
                    },
                ),
                _node("r2", "radio", {"value": "b", "selected": "a", "group": "g"}),
            ],
        )
        result = normalize(tree)
        c0_a11y = result["children"][0]["props"]["a11y"]
        assert c0_a11y["position_in_set"] == 1
        assert c0_a11y["size_of_set"] == 10

        c1_a11y = result["children"][1]["props"]["a11y"]
        assert c1_a11y["position_in_set"] == 2
        assert c1_a11y["size_of_set"] == 2

    def test_non_radio_unaffected(self) -> None:
        tree = _node(
            "form",
            "container",
            children=[
                _node("btn", "button", {"label": "OK"}),
                _node("r1", "radio", {"value": "a", "selected": "a", "group": "g"}),
            ],
        )
        result = normalize(tree)
        btn_a11y = result["children"][0]["props"]["a11y"]
        assert "position_in_set" not in btn_a11y


class TestNormalizeDuplicateIds:
    def test_raises_on_duplicate_sibling_ids(self) -> None:
        tree = _node(
            "root",
            "container",
            children=[
                _node("dup", "button"),
                _node("dup", "button"),
            ],
        )
        with pytest.raises(
            ValueError,
            match="duplicate sibling IDs detected during normalize: 'root/dup'",
        ):
            normalize(tree)


class TestNormalizeMeta:
    """Meta is preserved through normalize but excluded from diffs."""

    def test_meta_preserved(self) -> None:
        tree = {"id": "btn", "type": "button", "props": {}, "meta": {"custom": 42}}
        result = normalize(tree)
        assert result["meta"] == {"custom": 42}

    def test_meta_none_not_set(self) -> None:
        tree = {"id": "btn", "type": "button", "props": {}}
        result = normalize(tree)
        assert "meta" not in result

    def test_meta_on_children(self) -> None:
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                {"id": "a", "type": "button", "props": {}, "meta": {"tag": "one"}},
            ],
        }
        result = normalize(tree)
        assert result["children"][0]["meta"] == {"tag": "one"}

    def test_meta_ignored_in_diff(self) -> None:
        old = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [],
            "meta": {"version": 1},
        }
        new = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [],
            "meta": {"version": 2},
        }
        assert diff(normalize(old), normalize(new)) == []


# ===========================================================================
# Diff
# ===========================================================================


class TestDiffNilCases:
    def test_both_none(self) -> None:
        assert diff(None, None) == []

    def test_old_none_new_tree(self) -> None:
        new = _node("root", "container")
        ops = diff(None, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "replace_node"
        assert ops[0]["path"] == []
        assert ops[0]["node"] is new

    def test_old_tree_new_none(self) -> None:
        old = _node("root", "container")
        ops = diff(old, None)
        assert len(ops) == 1
        assert ops[0]["op"] == "remove_child"
        assert ops[0]["path"] == []
        assert ops[0]["index"] == 0


class TestDiffIdentical:
    def test_same_tree_no_ops(self) -> None:
        tree = _node(
            "root",
            "container",
            {"x": 1},
            [
                _node("a", "text", {"content": "hello"}),
            ],
        )
        assert diff(tree, tree) == []

    def test_equal_trees_no_ops(self) -> None:
        old = _node("root", "container", {"x": 1})
        new = _node("root", "container", {"x": 1})
        assert diff(old, new) == []


class TestDiffRootIdChanged:
    def test_replace_node_on_id_change(self) -> None:
        old = _node("root1", "container")
        new = _node("root2", "container")
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "replace_node"
        assert ops[0]["path"] == []


class TestDiffTypeChanged:
    def test_replace_node_on_type_change(self) -> None:
        old = _node("root", "container")
        new = _node("root", "column")
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "replace_node"


class TestDiffProps:
    def test_changed_prop(self) -> None:
        old = _node("root", "button", {"label": "A"})
        new = _node("root", "button", {"label": "B"})
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "update_props"
        assert ops[0]["props"] == {"label": "B"}

    def test_added_prop(self) -> None:
        old = _node("root", "button", {"label": "A"})
        new = _node("root", "button", {"label": "A", "color": "red"})
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["props"] == {"color": "red"}

    def test_removed_prop(self) -> None:
        old = _node("root", "button", {"label": "A", "color": "red"})
        new = _node("root", "button", {"label": "A"})
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["props"] == {"color": None}

    def test_no_change_no_ops(self) -> None:
        old = _node("root", "button", {"label": "A"})
        new = _node("root", "button", {"label": "A"})
        assert diff(old, new) == []

    def test_multiple_prop_changes(self) -> None:
        old = _node("root", "text", {"content": "A", "size": 12, "color": "red"})
        new = _node("root", "text", {"content": "B", "size": 12, "weight": "bold"})
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["props"]["content"] == "B"
        assert ops[0]["props"]["color"] is None
        assert ops[0]["props"]["weight"] == "bold"
        assert "size" not in ops[0]["props"]


class TestDiffIdKeyedLists:
    """Canvas shape lists and similar id-bearing prop lists compare
    by element id rather than positional deep-equality. A rebuilt
    list with the same content does not produce a diff; any content
    change or structural change still does.
    """

    def test_identical_id_keyed_list_no_diff(self) -> None:
        shapes = [
            {"id": "s1", "type": "rect", "x": 0},
            {"id": "s2", "type": "circle", "r": 10},
        ]
        old = _node("c", "canvas", {"shapes": list(shapes)})
        new = _node("c", "canvas", {"shapes": list(shapes)})
        assert diff(old, new) == []

    def test_id_keyed_list_content_change_produces_patch(self) -> None:
        old = _node(
            "c",
            "canvas",
            {"shapes": [{"id": "s1", "type": "rect", "x": 0}]},
        )
        new = _node(
            "c",
            "canvas",
            {"shapes": [{"id": "s1", "type": "rect", "x": 5}]},
        )
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "update_props"

    def test_id_keyed_list_added_element_produces_patch(self) -> None:
        old = _node("c", "canvas", {"shapes": [{"id": "s1", "type": "rect"}]})
        new = _node(
            "c",
            "canvas",
            {
                "shapes": [
                    {"id": "s1", "type": "rect"},
                    {"id": "s2", "type": "circle"},
                ]
            },
        )
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "update_props"

    def test_non_id_keyed_list_uses_deep_equality(self) -> None:
        # Lists without an id on every element fall through to plain
        # deep-equality. Identical content, no diff.
        old = _node("c", "canvas", {"tags": ["a", "b", "c"]})
        new = _node("c", "canvas", {"tags": ["a", "b", "c"]})
        assert diff(old, new) == []

        # Same pattern, content change still produces a patch.
        new2 = _node("c", "canvas", {"tags": ["a", "b", "d"]})
        ops = diff(old, new2)
        assert len(ops) == 1
        assert ops[0]["op"] == "update_props"


class TestDiffChildRemovals:
    def test_remove_single_child(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
            ],
        )
        ops = diff(old, new)
        assert any(op["op"] == "remove_child" and op["index"] == 1 for op in ops)

    def test_remove_first_child(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("b", "text"),
            ],
        )
        ops = diff(old, new)
        assert any(op["op"] == "remove_child" and op["index"] == 0 for op in ops)

    def test_remove_multiple_descending_order(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text"),
                _node("c", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("b", "text"),
            ],
        )
        ops = diff(old, new)
        remove_ops = [op for op in ops if op["op"] == "remove_child"]
        indices = [op["index"] for op in remove_ops]
        assert indices == [2, 0]  # descending order


class TestDiffChildInserts:
    def test_insert_single_child(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text"),
            ],
        )
        ops = diff(old, new)
        insert_ops = [op for op in ops if op["op"] == "insert_child"]
        assert len(insert_ops) == 1
        assert insert_ops[0]["index"] == 1
        assert insert_ops[0]["node"]["id"] == "b"

    def test_insert_at_beginning(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("b", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text"),
            ],
        )
        ops = diff(old, new)
        insert_ops = [op for op in ops if op["op"] == "insert_child"]
        assert len(insert_ops) == 1
        assert insert_ops[0]["index"] == 0


class TestDiffReorder:
    def test_reorder_triggers_replace(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("b", "text"),
                _node("a", "text"),
            ],
        )
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "replace_node"
        assert ops[0]["path"] == []


class TestDiffNested:
    def test_nested_prop_change(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text", {"content": "old"}),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("a", "text", {"content": "new"}),
            ],
        )
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "update_props"
        assert ops[0]["path"] == [0]
        assert ops[0]["props"] == {"content": "new"}

    def test_deeply_nested_change(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node(
                    "a",
                    "container",
                    children=[
                        _node("b", "text", {"content": "old"}),
                    ],
                ),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node(
                    "a",
                    "container",
                    children=[
                        _node("b", "text", {"content": "new"}),
                    ],
                ),
            ],
        )
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["path"] == [0, 0]


class TestDiffIndexAdjustment:
    def test_update_after_removal_adjusts_index(self) -> None:
        """When a child before the updated one is removed, the update
        path must account for the removal shifting indices down."""
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text", {"content": "old"}),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("b", "text", {"content": "new"}),
            ],
        )
        ops = diff(old, new)
        remove_ops = [op for op in ops if op["op"] == "remove_child"]
        update_ops = [op for op in ops if op["op"] == "update_props"]

        assert len(remove_ops) == 1
        assert remove_ops[0]["index"] == 0

        assert len(update_ops) == 1
        # After removing index 0, "b" shifts from index 1 to 0
        assert update_ops[0]["path"] == [0]

    def test_complex_removal_and_update(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text"),
                _node("c", "text", {"content": "old"}),
                _node("d", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("c", "text", {"content": "new"}),
                _node("d", "text"),
            ],
        )
        ops = diff(old, new)
        remove_ops = [op for op in ops if op["op"] == "remove_child"]
        update_ops = [op for op in ops if op["op"] == "update_props"]

        # Removals at indices 1 and 0, in descending order
        remove_indices = [op["index"] for op in remove_ops]
        assert remove_indices == [1, 0]

        # After removing indices 1 and 0, "c" was at old index 2,
        # two removals before it (0 and 1), so adjusted index = 0
        assert len(update_ops) == 1
        assert update_ops[0]["path"] == [0]


class TestDiffEmptyChildren:
    def test_empty_to_empty(self) -> None:
        old = _node("root", "container")
        new = _node("root", "container")
        assert diff(old, new) == []

    def test_empty_to_children(self) -> None:
        old = _node("root", "container")
        new = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
            ],
        )
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "insert_child"

    def test_children_to_empty(self) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
            ],
        )
        new = _node("root", "container")
        ops = diff(old, new)
        assert len(ops) == 1
        assert ops[0]["op"] == "remove_child"


class TestDiffDuplicateIds:
    def test_duplicate_ids_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("a", "text"),
            ],
        )
        with caplog.at_level(logging.ERROR, logger="plushie"):
            diff(old, new)
        assert "duplicate child IDs" in caplog.text


class TestDiffOpOrdering:
    def test_removes_before_updates_before_inserts(self) -> None:
        """Patch operations are ordered: remove, update, insert."""
        old = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node("b", "text", {"content": "old"}),
            ],
        )
        new = _node(
            "root",
            "container",
            children=[
                _node("b", "text", {"content": "new"}),
                _node("c", "text"),
            ],
        )
        ops = diff(old, new)
        op_types = [op["op"] for op in ops]
        # remove_child, then update_props, then insert_child
        assert op_types == ["remove_child", "update_props", "insert_child"]


# ===========================================================================
# Search
# ===========================================================================


class TestFind:
    def test_find_root(self) -> None:
        tree = _node("root", "container")
        assert find(tree, "root") is tree

    def test_find_child(self) -> None:
        child = _node("btn", "button")
        tree = _node("root", "container", children=[child])
        assert find(tree, "btn") is child

    def test_find_deep(self) -> None:
        deep = _node("deep", "text")
        tree = _node(
            "root",
            "container",
            children=[
                _node("mid", "container", children=[deep]),
            ],
        )
        assert find(tree, "deep") is deep

    def test_find_missing_returns_none(self) -> None:
        tree = _node("root", "container")
        assert find(tree, "nope") is None

    def test_find_scoped_path(self) -> None:
        tree = _node(
            "root",
            "container",
            children=[
                _node("form/email", "text_input"),
            ],
        )
        assert find(tree, "form/email") is not None

    def test_find_local_fallback(self) -> None:
        """When exact match fails, fall back to matching local ID segment."""
        tree = _node(
            "root",
            "container",
            children=[
                {"id": "form/save", "type": "button", "props": {}, "children": []},
            ],
        )
        result = find(tree, "save")
        assert result is not None
        assert result["id"] == "form/save"

    def test_find_scoped_target_no_fallback(self) -> None:
        """Scoped target IDs (containing '/') don't use local fallback."""
        tree = _node(
            "root",
            "container",
            children=[
                {"id": "form/save", "type": "button", "props": {}, "children": []},
            ],
        )
        assert find(tree, "other/save") is None


class TestFindAll:
    def test_find_all_by_type(self) -> None:
        tree = _node(
            "root",
            "container",
            children=[
                _node("a", "button"),
                _node("b", "text"),
                _node("c", "button"),
            ],
        )
        buttons = find_all(tree, lambda n: n.get("type") == "button")
        assert len(buttons) == 2
        assert {b["id"] for b in buttons} == {"a", "c"}

    def test_find_all_empty(self) -> None:
        tree = _node("root", "container")
        result = find_all(tree, lambda n: n.get("type") == "button")
        assert result == []

    def test_find_all_includes_root(self) -> None:
        tree = _node("root", "container")
        result = find_all(tree, lambda n: n.get("type") == "container")
        assert len(result) == 1

    def test_find_all_depth_first_order(self) -> None:
        tree = _node(
            "root",
            "container",
            children=[
                _node(
                    "a",
                    "container",
                    children=[
                        _node("a1", "text"),
                    ],
                ),
                _node("b", "text"),
            ],
        )
        all_nodes = find_all(tree, lambda _: True)
        node_ids = [n["id"] for n in all_nodes]
        assert node_ids == ["root", "a", "a1", "b"]


class TestExists:
    def test_exists_true(self) -> None:
        tree = _node(
            "root",
            "container",
            children=[
                _node("btn", "button"),
            ],
        )
        assert exists(tree, "btn") is True

    def test_exists_false(self) -> None:
        tree = _node("root", "container")
        assert exists(tree, "nope") is False

    def test_exists_none_tree(self) -> None:
        assert exists(None, "anything") is False


class TestIds:
    def test_single_node(self) -> None:
        tree = _node("root", "container")
        assert ids(tree) == ["root"]

    def test_nested_depth_first(self) -> None:
        tree = _node(
            "root",
            "container",
            children=[
                _node("a", "text"),
                _node(
                    "b",
                    "container",
                    children=[
                        _node("c", "text"),
                    ],
                ),
            ],
        )
        assert ids(tree) == ["root", "a", "b", "c"]

    def test_none_tree(self) -> None:
        assert ids(None) == []


class TestTextOf:
    def test_content_priority(self) -> None:
        node = _node("t", "text", {"content": "hello", "label": "world"})
        assert text_of(node) == "hello"

    def test_label_fallback(self) -> None:
        node = _node("b", "button", {"label": "Save"})
        assert text_of(node) == "Save"

    def test_value_fallback(self) -> None:
        node = _node("i", "text_input", {"value": "typed"})
        assert text_of(node) == "typed"

    def test_placeholder_fallback(self) -> None:
        node = _node("i", "text_input", {"placeholder": "Search..."})
        assert text_of(node) == "Search..."

    def test_no_text_returns_none(self) -> None:
        node = _node("s", "space")
        assert text_of(node) is None

    def test_non_string_value_skipped(self) -> None:
        node = _node("s", "slider", {"value": 42})
        assert text_of(node) is None

    def test_empty_props(self) -> None:
        node = _node("x", "container")
        assert text_of(node) is None


# ===========================================================================
# Prop encoding during normalize
# ===========================================================================


class TestNormalizePropEncoding:
    """Dataclass prop values are converted to wire-compatible dicts."""

    def test_border_encoded(self) -> None:
        node = {
            "id": "box",
            "type": "container",
            "props": {"border": Border(color="#ff0000", width=2, radius=8)},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["border"] == {
            "color": "#ff0000",
            "width": 2,
            "radius": 8,
        }

    def test_shadow_encoded(self) -> None:
        node = {
            "id": "box",
            "type": "container",
            "props": {"shadow": Shadow(offset=(4.0, 2.0), blur_radius=6.0)},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["shadow"]["offset"] == [4.0, 2.0]

    def test_font_encoded(self) -> None:
        node = {
            "id": "t",
            "type": "text",
            "props": {"font": Font(family="Inter", weight="bold")},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["font"] == {"family": "Inter", "weight": "bold"}

    def test_gradient_encoded(self) -> None:
        g = Gradient.linear((0, 0), (100, 100), [(0.0, "#ff0000"), (1.0, "#0000ff")])
        node = {
            "id": "box",
            "type": "container",
            "props": {"background": g},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["background"]["type"] == "linear"
        assert result["props"]["background"]["start"] == [0, 0]
        assert result["props"]["background"]["end"] == [100, 100]

    def test_style_map_encoded(self) -> None:
        style = (
            StyleMap()
            .with_background("#ff0000")
            .with_border(Border(color="#000000", width=1))
        )
        node = {
            "id": "btn",
            "type": "button",
            "props": {"label": "Go", "style": style},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["style"]["background"] == "#ff0000"
        assert result["props"]["style"]["border"]["width"] == 1

    def test_a11y_dataclass_encoded(self) -> None:
        node = {
            "id": "btn",
            "type": "button",
            "props": {"a11y": A11y(role="button", label="Submit")},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["a11y"] == {"role": "button", "label": "Submit"}

    def test_theme_builtin_encoded(self) -> None:
        node = {
            "id": "main",
            "type": "window",
            "props": {"theme": Theme.builtin("dark")},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["theme"] == "dark"

    def test_theme_custom_encoded(self) -> None:
        t = Theme.custom("My Theme", primary="#7aa2f7")
        node = {
            "id": "main",
            "type": "window",
            "props": {"theme": t},
            "children": [],
        }
        result = normalize(node)
        assert isinstance(result["props"]["theme"], dict)
        assert result["props"]["theme"]["name"] == "My Theme"

    def test_tuple_converted_to_list(self) -> None:
        node = {
            "id": "w",
            "type": "window",
            "props": {"size": (800, 600)},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["size"] == [800, 600]

    def test_plain_props_unchanged(self) -> None:
        node = {
            "id": "t",
            "type": "text",
            "props": {"content": "hello", "size": 16},
            "children": [],
        }
        result = normalize(node)
        assert result["props"]["content"] == "hello"
        assert result["props"]["size"] == 16


class TestNormalizePropEncodingRoundTrip:
    """Encoded props survive msgpack serialization."""

    def test_style_map_through_framing(self) -> None:
        style = (
            StyleMap()
            .with_background("#ff0000")
            .with_border(Border(color="#000000", width=1, radius=4))
            .with_shadow(Shadow(offset=(2.0, 2.0), blur_radius=6.0))
        )
        node = {
            "id": "btn",
            "type": "button",
            "props": {"label": "Go", "style": style},
            "children": [],
        }
        tree = normalize(node)
        msg = {"type": "snapshot", "tree": tree}
        framed = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        decoded = framing.feed(framed)
        assert len(decoded) == 1
        rt_props = decoded[0]["tree"]["props"]
        assert rt_props["style"]["background"] == "#ff0000"
        assert rt_props["style"]["border"]["radius"] == 4
        assert rt_props["style"]["shadow"]["offset"] == [2.0, 2.0]

    def test_gradient_through_framing(self) -> None:
        g = Gradient.linear((0, 0), (1, 1), [(0.0, "#ff0000"), (1.0, "blue")])
        node = {
            "id": "box",
            "type": "container",
            "props": {"background": g},
            "children": [],
        }
        tree = normalize(node)
        msg = {"type": "snapshot", "tree": tree}
        framed = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        decoded = framing.feed(framed)
        bg = decoded[0]["tree"]["props"]["background"]
        assert bg["type"] == "linear"
        assert bg["start"] == [0, 0]
        assert bg["end"] == [1, 1]
        assert len(bg["stops"]) == 2

    def test_a11y_through_framing(self) -> None:
        node = {
            "id": "h",
            "type": "text",
            "props": {"a11y": A11y(role="heading", level=1)},
            "children": [],
        }
        tree = normalize(node)
        msg = {"type": "snapshot", "tree": tree}
        framed = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        decoded = framing.feed(framed)
        a11y = decoded[0]["tree"]["props"]["a11y"]
        assert a11y["role"] == "heading"
        assert a11y["level"] == 1
        assert "hidden" not in a11y


class TestExpandRows:
    def test_non_table_passthrough(self) -> None:
        node = {"id": "x", "type": "column", "props": {}, "children": []}
        assert expand_rows(node) is node

    def test_table_no_rows_passthrough(self) -> None:
        node = {
            "id": "tbl",
            "type": "table",
            "props": {"columns": [{"key": "name"}]},
            "children": [],
        }
        assert expand_rows(node) is node

    def test_table_with_children_unchanged(self) -> None:
        node = {
            "id": "tbl",
            "type": "table",
            "props": {"columns": [{"key": "name"}]},
            "children": [
                {"id": "r1", "type": "table_row", "props": {}, "children": []}
            ],
        }
        assert expand_rows(node) is node

    def test_expands_rows_to_children(self) -> None:
        node = {
            "id": "tbl",
            "type": "table",
            "props": {
                "columns": [{"key": "name"}, {"key": "email"}],
                "rows": [
                    {"id": "r1", "name": "Alice", "email": "a@b.com"},
                    {"id": "r2", "name": "Bob", "email": "c@d.com"},
                ],
            },
            "children": [],
        }
        result = expand_rows(node)
        assert "rows" not in result["props"]
        children = result["children"]
        assert len(children) == 2

        r1 = children[0]
        assert r1["type"] == "table_row"
        assert r1["id"] == "r1"
        assert len(r1["children"]) == 2

        name_cell = r1["children"][0]
        assert name_cell["type"] == "table_cell"
        assert name_cell["props"]["column"] == "name"
        assert name_cell["children"][0]["props"]["content"] == "Alice"

        email_cell = r1["children"][1]
        assert email_cell["props"]["column"] == "email"
        assert email_cell["children"][0]["props"]["content"] == "a@b.com"

    def test_rows_and_children_raises(self) -> None:
        node = {
            "id": "tbl",
            "type": "table",
            "props": {"rows": [{"name": "Alice"}]},
            "children": [
                {"id": "r1", "type": "table_row", "props": {}, "children": []}
            ],
        }
        with pytest.raises(ValueError, match="cannot combine"):
            expand_rows(node)

    def test_row_without_id_generates_auto_id(self) -> None:
        node = {
            "id": "tbl",
            "type": "table",
            "props": {
                "columns": [{"key": "name"}],
                "rows": [{"name": "Alice"}],
            },
            "children": [],
        }
        result = expand_rows(node)
        row = result["children"][0]
        assert row["id"] == "row_0"
        cell = row["children"][0]
        assert cell["id"] == "name"
        text_node = cell["children"][0]
        assert text_node["id"] == "row_0.name"


class TestMemoCache:
    """``memo(key, deps, body)`` marks a subtree as cacheable by
    ``deps``. Across renders, when ``deps`` compare equal, the
    cached normalized subtree is reused and ``body()`` is not
    invoked.
    """

    def test_memo_body_runs_once_per_deps_value(self) -> None:
        calls = {"n": 0}

        def body() -> dict[str, object]:
            calls["n"] += 1
            return {
                "id": "inner",
                "type": "text",
                "props": {"content": "hi"},
                "children": [],
            }

        from plushie.ui import memo

        memo_prev: dict[object, object] = {}
        # First render: miss. Body runs once.
        memo_new1: dict[object, object] = {}
        tree1 = normalize(
            memo("k", ("tag", 1), body),
            memo_cache_prev=memo_prev,
            memo_cache_new=memo_new1,
        )
        assert calls["n"] == 1

        # Second render, same deps: hit. Body does not run again.
        memo_new2: dict[object, object] = {}
        tree2 = normalize(
            memo("k", ("tag", 1), body),
            memo_cache_prev=memo_new1,
            memo_cache_new=memo_new2,
        )
        assert calls["n"] == 1, "memo hit must not re-run body"

        # The returned trees have the same shape.
        assert tree1["id"] == tree2["id"]

        # Third render, deps changed: miss. Body runs.
        memo_new3: dict[object, object] = {}
        normalize(
            memo("k", ("tag", 2), body),
            memo_cache_prev=memo_new2,
            memo_cache_new=memo_new3,
        )
        assert calls["n"] == 2, "deps change must re-run body"

        # Fourth render, new deps held: hit again.
        memo_new4: dict[object, object] = {}
        normalize(
            memo("k", ("tag", 2), body),
            memo_cache_prev=memo_new3,
            memo_cache_new=memo_new4,
        )
        assert calls["n"] == 2


class TestWidgetViewCache:
    """Widgets that override ``cache_key`` reuse their expanded
    view tree when the key is unchanged.
    """

    def test_widget_view_skipped_when_cache_key_unchanged(self) -> None:
        from plushie.widget import WidgetDef, derive_registry

        calls = {"n": 0}

        class Counting(WidgetDef):
            def init(self, props: dict[str, object]) -> dict[str, object]:
                return {}

            def view(
                self,
                widget_id: str,
                props: dict[str, object],
                state: dict[str, object],
            ) -> dict[str, object]:
                calls["n"] += 1
                label = str(props.get("label", "x"))
                return {
                    "id": widget_id,
                    "type": "button",
                    "props": {"label": label},
                    "children": [],
                }

            def cache_key(
                self,
                props: dict[str, object],
                state: dict[str, object],
            ) -> object:
                return props.get("label")

        def build_tree(label: str) -> dict[str, object]:
            return {
                "id": "main",
                "type": "window",
                "props": {},
                "children": [Counting.build("w1", props={"label": label})],
            }

        registry: Any = {}
        widget_prev: dict[object, object] = {}
        widget_new1: dict[object, object] = {}
        normalized1 = normalize(
            build_tree("hello"),
            registry=registry,
            widget_cache_prev=widget_prev,
            widget_cache_new=widget_new1,
        )
        registry = derive_registry(normalized1)
        assert calls["n"] == 1

        # Same label across two renders: cache hit, view() not called.
        widget_new2: dict[object, object] = {}
        normalize(
            build_tree("hello"),
            registry=registry,
            widget_cache_prev=widget_new1,
            widget_cache_new=widget_new2,
        )
        assert calls["n"] == 1, "widget cache hit must skip view()"

        # Different label: cache miss, view() runs.
        widget_new3: dict[object, object] = {}
        normalize(
            build_tree("world"),
            registry=registry,
            widget_cache_prev=widget_new2,
            widget_cache_new=widget_new3,
        )
        assert calls["n"] == 2

    def test_widget_without_cache_key_always_renders(self) -> None:
        from plushie.widget import WidgetDef, derive_registry

        calls = {"n": 0}

        class NoCache(WidgetDef):
            def init(self, props: dict[str, object]) -> dict[str, object]:
                return {}

            def view(
                self,
                widget_id: str,
                props: dict[str, object],
                state: dict[str, object],
            ) -> dict[str, object]:
                calls["n"] += 1
                return {
                    "id": widget_id,
                    "type": "button",
                    "props": {"label": "nc"},
                    "children": [],
                }

        tree = {
            "id": "main",
            "type": "window",
            "props": {},
            "children": [NoCache.build("w1")],
        }

        registry: Any = {}
        widget_prev: dict[object, object] = {}
        widget_new: dict[object, object] = {}
        normalized = normalize(
            tree,
            registry=registry,
            widget_cache_prev=widget_prev,
            widget_cache_new=widget_new,
        )
        registry = derive_registry(normalized)
        assert calls["n"] == 1

        # Render again. Without cache_key, view() runs every time.
        widget_new2: dict[object, object] = {}
        normalize(
            tree,
            registry=registry,
            widget_cache_prev=widget_new,
            widget_cache_new=widget_new2,
        )
        assert calls["n"] == 2
