"""Tests for code blocks in docs/scoped-ids.md.

Verifies scope matching patterns, dynamic list scoping,
target() reconstruction, and normalize with scoped containers.
"""

from __future__ import annotations

import pytest

from plushie import ui
from plushie.events import Click, Toggle, target
from plushie.tree import exists, find, normalize

# ---------------------------------------------------------------------------
# test_normalize_scoped_ids
# ---------------------------------------------------------------------------


def test_normalize_builds_scoped_ids():
    """Named containers scope their children's IDs with '/' separators."""
    tree = normalize(
        ui.container(
            "sidebar",
            ui.container(
                "form",
                ui.column(
                    ui.text_input("email", ""),
                    ui.button("save", "Save"),
                ),
            ),
        )
    )

    assert find(tree, "sidebar") is not None
    assert find(tree, "sidebar/form") is not None
    assert find(tree, "sidebar/form/email") is not None
    assert find(tree, "sidebar/form/save") is not None


def test_auto_id_containers_do_not_scope():
    """Auto-ID containers (no explicit ID) don't create scope boundaries."""
    tree = normalize(
        ui.container(
            "sidebar",
            ui.column(  # auto-ID column
                ui.button("save", "Save"),
            ),
        )
    )

    # The button should be scoped under sidebar, not column
    assert find(tree, "sidebar/save") is not None


def test_window_nodes_do_not_scope():
    """Window nodes don't create scope boundaries."""
    tree = normalize(
        ui.window(
            "main",
            ui.container(
                "form",
                ui.button("save", "Save"),
            ),
        )
    )

    # The button is scoped under form, not main/form
    assert find(tree, "form/save") is not None
    assert find(tree, "main/form/save") is None


def test_slash_in_user_id_raises():
    """User-provided IDs cannot contain '/'."""
    with pytest.raises(ValueError, match="cannot contain"):
        normalize(ui.button("bad/id", "Nope"))


# ---------------------------------------------------------------------------
# test_event_scope_splitting
# ---------------------------------------------------------------------------


def test_click_scope_structure():
    """Wire ID 'sidebar/form/save' splits into id='save', scope=('form', 'sidebar')."""
    event = Click(id="save", scope=("form", "sidebar"))

    assert event.id == "save"
    assert event.scope == ("form", "sidebar")


def test_scope_match_local_id_only():
    """Pattern match on local ID ignores scope entirely."""
    event = Click(id="save", scope=("form", "sidebar"))

    match event:
        case Click(id="save"):
            matched = True
        case _:
            matched = False

    assert matched


def test_scope_match_immediate_parent():
    """Pattern match on ID + immediate parent container."""
    event = Click(id="save", scope=("form", "sidebar"))

    match event:
        case Click(id="save", scope=("form", *_)):
            matched = True
        case _:
            matched = False

    assert matched


def test_scope_match_dynamic_list_binding():
    """Bind the parent for dynamic list item identification."""
    event = Toggle(id="done", value=True, scope=("item_42", "todo_list"))

    match event:
        case Toggle(id="done", scope=(item_id, *_)):
            bound_id = item_id
        case _:
            bound_id = None

    assert bound_id == "item_42"


# ---------------------------------------------------------------------------
# test_target_reconstruction
# ---------------------------------------------------------------------------


def test_target_reconstructs_full_path():
    """target() joins reversed scope + id into a forward-order path."""
    event = Click(id="save", scope=("form", "sidebar"))
    result = target(event)

    assert result == "sidebar/form/save"


def test_target_unscoped():
    """target() returns just the id when scope is empty."""
    event = Click(id="save")
    result = target(event)

    assert result == "save"


# ---------------------------------------------------------------------------
# test_tree_search
# ---------------------------------------------------------------------------


def test_find_by_full_scoped_path():
    """tree.find() matches against the full scoped ID."""
    tree = normalize(
        ui.container(
            "sidebar",
            ui.container(
                "form",
                ui.button("save", "Save"),
            ),
        )
    )

    node = find(tree, "sidebar/form/save")
    assert node is not None
    assert node["type"] == "button"


def test_find_falls_back_to_local_id():
    """tree.find() falls back to local ID match when no '/' in target."""
    tree = normalize(
        ui.container(
            "sidebar",
            ui.container(
                "form",
                ui.button("save", "Save"),
            ),
        )
    )

    node = find(tree, "save")
    assert node is not None
    assert node["type"] == "button"


def test_exists_with_scoped_path():
    """tree.exists() works with both scoped and local IDs."""
    tree = normalize(
        ui.container(
            "form",
            ui.button("save", "Save"),
        )
    )

    assert exists(tree, "form/save")
    assert exists(tree, "save")


# ---------------------------------------------------------------------------
# test_dynamic_list_scoping
# ---------------------------------------------------------------------------


def test_dynamic_list_scoping():
    """Wrapping list items in named containers gives unique scoped IDs."""
    from dataclasses import dataclass

    @dataclass
    class Item:
        id: str
        completed: bool

    items = [Item("item_1", False), Item("item_2", True)]

    tree = normalize(
        ui.column(
            *(
                ui.row(
                    ui.checkbox("done", item.completed),
                    ui.button("delete", "X"),
                    id=item.id,
                )
                for item in items
            ),
            id="todo_list",
        )
    )

    # Each item's children are scoped under todo_list/<item_id>
    assert find(tree, "todo_list/item_1/done") is not None
    assert find(tree, "todo_list/item_2/done") is not None
    assert find(tree, "todo_list/item_1/delete") is not None
    assert find(tree, "todo_list/item_2/delete") is not None


def test_dynamic_list_scope_matching():
    """Event pattern matching extracts the item ID from scope."""
    event = Toggle(id="done", value=True, scope=("item_1", "todo_list"))

    match event:
        case Toggle(id="done", scope=(item_id, *_)):
            result = item_id
        case _:
            result = None

    assert result == "item_1"

    # Delete button from item_2
    event2 = Click(id="delete", scope=("item_2", "todo_list"))

    match event2:
        case Click(id="delete", scope=(item_id, *_)):
            result2 = item_id
        case _:
            result2 = None

    assert result2 == "item_2"


# ---------------------------------------------------------------------------
# test_pattern_matching_tips
# ---------------------------------------------------------------------------


def test_depth_agnostic_match():
    """Depth-agnostic match works whether widget is at root or nested."""
    shallow = Click(id="query", scope=("search",))
    deep = Click(id="query", scope=("search", "panel", "app"))

    for event in [shallow, deep]:
        match event:
            case Click(id="query", scope=("search", *_)):
                matched = True
            case _:
                matched = False
        assert matched, f"Failed for scope={event.scope}"


def test_exact_depth_match():
    """Exact depth match only matches a specific nesting level."""
    exact = Click(id="query", scope=("search",))
    deeper = Click(id="query", scope=("search", "panel"))

    match exact:
        case Click(id="query", scope=("search",)):
            matched_exact = True
        case _:
            matched_exact = False
    assert matched_exact

    match deeper:
        case Click(id="query", scope=("search",)):
            matched_deeper = True
        case _:
            matched_deeper = False
    assert not matched_deeper


def test_no_scope_match():
    """No-scope match only matches unscoped widgets."""
    unscoped = Click(id="save", scope=())
    scoped = Click(id="save", scope=("form",))

    match unscoped:
        case Click(id="save", scope=()):
            matched_unscoped = True
        case _:
            matched_unscoped = False
    assert matched_unscoped

    match scoped:
        case Click(id="save", scope=()):
            matched_scoped = True
        case _:
            matched_scoped = False
    assert not matched_scoped
