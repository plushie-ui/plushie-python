"""Tests for plushie.tree -- normalization, diffing, and search."""

from __future__ import annotations

import logging

import pytest

from plushie.tree import (
    diff,
    exists,
    find,
    find_all,
    ids,
    normalize,
    text_of,
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
        assert result["props"] == {}
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
        # Window nodes don't create scope -- children get no prefix
        # (scope stays whatever was passed in, which is "" at root)
        assert result["children"][0]["id"] == "btn"

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
        # Root "root" is a synthetic wrapper -- children get their own scope
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
        # Window doesn't scope, so "" scope -- ref stays as-is
        assert result["children"][0]["props"]["a11y"]["labelled_by"] == "label"

    def test_no_a11y_prop_unchanged(self) -> None:
        tree = _node("btn", "button", {"label": "OK"})
        result = normalize(tree)
        assert "a11y" not in result["props"]


class TestNormalizeDuplicateIds:
    def test_logs_warning_on_duplicate_sibling_ids(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        tree = _node(
            "root",
            "container",
            children=[
                _node("dup", "button"),
                _node("dup", "button"),
            ],
        )
        with caplog.at_level(logging.ERROR, logger="plushie"):
            normalize(tree)
        assert "Duplicate sibling IDs" in caplog.text


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
