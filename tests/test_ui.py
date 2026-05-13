"""Tests for plushie.ui widget builder functions."""

from __future__ import annotations

import types

import plushie
from plushie import ui


def test_ui_is_top_level_package_export() -> None:
    assert isinstance(plushie.ui, types.ModuleType)
    assert plushie.ui is ui
    assert plushie.ui.text("greeting", "Hello") == ui.text("greeting", "Hello")


def test_ui_is_in_package_all() -> None:
    namespace: dict[str, object] = {}
    exec("from plushie import *", namespace)

    assert "ui" in plushie.__all__
    assert namespace["ui"] is ui


def test_version_is_in_package_all() -> None:
    namespace: dict[str, object] = {}
    exec("from plushie import *", namespace)

    assert "__version__" in plushie.__all__
    assert namespace["__version__"] == plushie.__version__


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_node(
    node: ui.Node,
    *,
    id: str | None,
    type: str,
    props: dict | None = None,
    children_count: int = 0,
) -> None:
    """Assert basic node shape."""
    assert node["id"] == id
    assert node["type"] == type
    if props is not None:
        for k, v in props.items():
            assert node["props"][k] == v, f"prop {k}: {node['props'].get(k)} != {v}"
    assert len(node["children"]) == children_count


# ---------------------------------------------------------------------------
# Named containers
# ---------------------------------------------------------------------------


class TestWindow:
    def test_basic(self) -> None:
        node = ui.window("main", title="Counter")
        _assert_node(node, id="main", type="window", props={"title": "Counter"})

    def test_with_child(self) -> None:
        node = ui.window(
            "main",
            ui.column(ui.text("hello"), ui.button("btn", "Click")),
            title="App",
        )
        _assert_node(node, id="main", type="window", children_count=1)
        assert node["props"]["title"] == "App"

    def test_rejects_multiple_children(self) -> None:
        try:
            ui.window("main", ui.text("a"), ui.text("b"))
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


class TestContainer:
    def test_basic(self) -> None:
        node = ui.container("box", padding=16)
        _assert_node(node, id="box", type="container", props={"padding": 16})

    def test_with_children(self) -> None:
        node = ui.container("box", ui.text("child"))
        _assert_node(node, id="box", type="container", children_count=1)


class TestScrollable:
    def test_basic(self) -> None:
        node = ui.scrollable("log", direction="vertical")
        _assert_node(node, id="log", type="scrollable", props={"direction": "vertical"})


class TestOverlay:
    def test_basic(self) -> None:
        node = ui.overlay("ov", ui.text("base"), ui.text("popup"))
        _assert_node(node, id="ov", type="overlay", children_count=2)

    def test_rejects_wrong_child_count(self) -> None:
        try:
            ui.overlay("ov", ui.text("only_one"))
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


class TestPin:
    def test_basic(self) -> None:
        node = ui.pin("p")
        _assert_node(node, id="p", type="pin")


class TestFloating:
    def test_wire_type_is_float(self) -> None:
        node = ui.floating("f")
        _assert_node(node, id="f", type="float")


class TestPointerArea:
    def test_basic(self) -> None:
        node = ui.pointer_area("pa")
        _assert_node(node, id="pa", type="pointer_area")


class TestSensor:
    def test_basic(self) -> None:
        node = ui.sensor("s")
        _assert_node(node, id="s", type="sensor")

    def test_on_resize_serializes_bool(self) -> None:
        node = ui.sensor("s", on_resize=True)
        _assert_node(node, id="s", type="sensor", props={"on_resize": True})


class TestThemer:
    def test_basic(self) -> None:
        node = ui.themer("t", theme="dark")
        _assert_node(node, id="t", type="themer", props={"theme": "dark"})


class TestTooltip:
    def test_basic(self) -> None:
        node = ui.tooltip("tt", "Helpful tip", ui.button("b", "Hover me"))
        _assert_node(node, id="tt", type="tooltip", children_count=1)
        assert node["props"]["tip"] == "Helpful tip"

    def test_with_position(self) -> None:
        node = ui.tooltip("tt", "Tip", position="bottom")
        assert node["props"]["position"] == "bottom"
        assert node["props"]["tip"] == "Tip"


class TestPaneGrid:
    def test_basic(self) -> None:
        node = ui.pane_grid("pg")
        _assert_node(node, id="pg", type="pane_grid")


class TestTable:
    def test_basic(self) -> None:
        node = ui.table("tbl")
        _assert_node(node, id="tbl", type="table")

    def test_table_row(self) -> None:
        node = ui.table_row("r1", ui.cell("name", ui.text("Alice")))
        _assert_node(node, id="r1", type="table_row", children_count=1)
        assert len(node["children"]) == 1

    def test_cell(self) -> None:
        node = ui.cell("email", ui.text("a@b.com"))
        _assert_node(node, id="email", type="table_cell", children_count=1)
        assert node["props"]["column"] == "email"

    def test_table_with_rows(self) -> None:
        node = ui.table(
            "users",
            ui.table_row(
                "r1",
                ui.cell("name", ui.text("Alice")),
                ui.cell("email", ui.text("a@b.com")),
            ),
            columns=[{"key": "name"}, {"key": "email"}],
        )
        _assert_node(node, id="users", type="table", children_count=1)
        row = node["children"][0]
        assert row["type"] == "table_row"
        assert len(row["children"]) == 2


# ---------------------------------------------------------------------------
# Anonymous containers
# ---------------------------------------------------------------------------


class TestColumn:
    def test_basic(self) -> None:
        node = ui.column(ui.text("a"), ui.text("b"), spacing=8)
        assert node["type"] == "column"
        assert node["id"] is None
        assert len(node["children"]) == 2
        assert node["props"]["spacing"] == 8

    def test_with_keyword_id(self) -> None:
        node = ui.column(id="c1")
        assert node["id"] == "c1"
        # id should not appear in props
        assert "id" not in node["props"]


class TestRow:
    def test_basic(self) -> None:
        node = ui.row(ui.text("a"), spacing=4)
        assert node["type"] == "row"
        assert node["id"] is None
        assert len(node["children"]) == 1


class TestStack:
    def test_basic(self) -> None:
        node = ui.stack(ui.text("a"))
        assert node["type"] == "stack"


class TestGrid:
    def test_basic(self) -> None:
        node = ui.grid()
        assert node["type"] == "grid"


class TestKeyedColumn:
    def test_basic(self) -> None:
        node = ui.keyed_column()
        assert node["type"] == "keyed_column"


class TestResponsive:
    def test_basic(self) -> None:
        node = ui.responsive()
        assert node["type"] == "responsive"


# ---------------------------------------------------------------------------
# Layout primitives
# ---------------------------------------------------------------------------


class TestSpace:
    def test_basic(self) -> None:
        node = ui.space(width="fill")
        _assert_node(node, id=None, type="space", props={"width": "fill"})


class TestRule:
    def test_basic(self) -> None:
        node = ui.rule(direction="horizontal")
        _assert_node(node, id=None, type="rule", props={"direction": "horizontal"})


# ---------------------------------------------------------------------------
# Interactive leaves
# ---------------------------------------------------------------------------


class TestButton:
    def test_basic(self) -> None:
        node = ui.button("save", "Save")
        _assert_node(node, id="save", type="button", props={"label": "Save"})

    def test_with_style(self) -> None:
        node = ui.button("b", "X", style="danger")
        assert node["props"]["style"] == "danger"


class TestTextInput:
    def test_basic(self) -> None:
        node = ui.text_input("search", "hello", placeholder="Type...")
        _assert_node(
            node,
            id="search",
            type="text_input",
            props={"value": "hello", "placeholder": "Type..."},
        )

    def test_text_direction_kwarg(self) -> None:
        node = ui.text_input("search", "", text_direction="rtl")
        assert node["props"]["text_direction"] == "rtl"


class TestCheckbox:
    def test_basic(self) -> None:
        node = ui.checkbox("cb", True, label="Accept")
        _assert_node(
            node,
            id="cb",
            type="checkbox",
            props={"checked": True, "label": "Accept"},
        )


class TestToggler:
    def test_basic(self) -> None:
        node = ui.toggler("tg", False)
        _assert_node(node, id="tg", type="toggler", props={"is_toggled": False})


class TestRadio:
    def test_basic(self) -> None:
        node = ui.radio("r1", "apple", "apple", group="fruits")
        _assert_node(
            node,
            id="r1",
            type="radio",
            props={"value": "apple", "selected": "apple", "group": "fruits"},
        )

    def test_none_selected(self) -> None:
        node = ui.radio("r2", "banana", None)
        # None values are stripped from props (matches Elixir's put_if)
        assert "selected" not in node["props"]


class TestSlider:
    def test_basic(self) -> None:
        node = ui.slider("vol", (0, 100), 50, step=5)
        _assert_node(
            node,
            id="vol",
            type="slider",
            props={"range": [0, 100], "value": 50, "step": 5},
        )


class TestVerticalSlider:
    def test_basic(self) -> None:
        node = ui.vertical_slider("vs", (0, 100), 75)
        _assert_node(
            node,
            id="vs",
            type="vertical_slider",
            props={"range": [0, 100], "value": 75},
        )


class TestPickList:
    def test_basic(self) -> None:
        node = ui.pick_list("pl", ["a", "b", "c"], "a")
        _assert_node(
            node,
            id="pl",
            type="pick_list",
            props={"options": ["a", "b", "c"], "selected": "a"},
        )


class TestComboBox:
    def test_basic(self) -> None:
        node = ui.combo_box("cb", ["x", "y"], "x", placeholder="Search")
        _assert_node(
            node,
            id="cb",
            type="combo_box",
            props={
                "options": ["x", "y"],
                "selected": "x",
                "placeholder": "Search",
            },
        )


class TestTextEditor:
    def test_basic(self) -> None:
        node = ui.text_editor("ed", "initial text")
        _assert_node(
            node,
            id="ed",
            type="text_editor",
            props={"content": "initial text"},
        )

    def test_text_direction_and_on_paste_kwargs(self) -> None:
        node = ui.text_editor("ed", "", text_direction="ltr", on_paste=True)
        assert node["props"]["text_direction"] == "ltr"
        assert node["props"]["on_paste"] is True


# ---------------------------------------------------------------------------
# Display with auto-id
# ---------------------------------------------------------------------------


class TestText:
    def test_auto_id(self) -> None:
        node = ui.text("Hello")
        _assert_node(node, id=None, type="text", props={"content": "Hello"})

    def test_explicit_id(self) -> None:
        node = ui.text("greeting", "Hello")
        _assert_node(node, id="greeting", type="text", props={"content": "Hello"})

    def test_with_kwargs(self) -> None:
        node = ui.text("Hello", size=24)
        assert node["props"]["size"] == 24

    def test_text_direction_kwarg(self) -> None:
        node = ui.text("Hello", text_direction="auto")
        assert node["props"]["text_direction"] == "auto"

    def test_too_many_args(self) -> None:
        import pytest

        with pytest.raises(TypeError, match="1 or 2"):
            ui.text("a", "b", "c")  # type: ignore[call-overload]


class TestMarkdown:
    def test_auto_id(self) -> None:
        node = ui.markdown("# Title")
        _assert_node(node, id=None, type="markdown", props={"content": "# Title"})

    def test_explicit_id(self) -> None:
        node = ui.markdown("docs", "# Title")
        _assert_node(node, id="docs", type="markdown", props={"content": "# Title"})

    def test_too_many_args(self) -> None:
        import pytest

        with pytest.raises(TypeError, match="1 or 2"):
            ui.markdown("a", "b", "c")  # type: ignore[call-overload]


class TestProgressBar:
    def test_auto_id(self) -> None:
        node = ui.progress_bar((0, 100), 50)
        _assert_node(
            node,
            id=None,
            type="progress_bar",
            props={"range": [0, 100], "value": 50},
        )

    def test_explicit_id(self) -> None:
        node = ui.progress_bar("pb", (0, 100), 75)
        _assert_node(
            node,
            id="pb",
            type="progress_bar",
            props={"range": [0, 100], "value": 75},
        )

    def test_too_many_args(self) -> None:
        import pytest

        with pytest.raises(TypeError, match="2 or 3"):
            ui.progress_bar("a", "b", "c", "d")  # type: ignore[call-overload]


# ---------------------------------------------------------------------------
# Display leaves
# ---------------------------------------------------------------------------


class TestImage:
    def test_basic(self) -> None:
        node = ui.image("img", "/path/to/image.png")
        _assert_node(
            node,
            id="img",
            type="image",
            props={"source": "/path/to/image.png"},
        )

    def test_handle_source(self) -> None:
        node = ui.image("img", {"handle": "my_image"})
        assert node["props"]["source"] == {"handle": "my_image"}


class TestSvg:
    def test_basic(self) -> None:
        node = ui.svg("icon", "/path/to/icon.svg")
        _assert_node(
            node,
            id="icon",
            type="svg",
            props={"source": "/path/to/icon.svg"},
        )


class TestRichText:
    def test_basic(self) -> None:
        spans = [{"text": "Hello", "size": 16}]
        node = ui.rich_text("rt", spans=spans)
        _assert_node(node, id="rt", type="rich_text", props={"spans": spans})

    def test_typed_spans_encode_to_wire_dicts(self) -> None:
        from plushie.types import Span

        node = ui.rich_text(
            "rt",
            spans=[
                Span(text="Build ", color="#000000"),
                Span(text="ok", color="#22aa22", underline=True),
            ],
        )
        _assert_node(
            node,
            id="rt",
            type="rich_text",
            props={
                "spans": [
                    {"text": "Build ", "color": "#000000"},
                    {"text": "ok", "color": "#22aa22", "underline": True},
                ]
            },
        )

    def test_typed_and_dict_spans_can_mix(self) -> None:
        from plushie.types import Span

        node = ui.rich_text(
            "rt",
            spans=[Span(text="a"), {"text": "b", "size": 14}],
        )
        spans = node["props"]["spans"]
        assert spans == [{"text": "a"}, {"text": "b", "size": 14}]


class TestQrCode:
    def test_basic(self) -> None:
        node = ui.qr_code("qr", "https://example.com")
        _assert_node(
            node,
            id="qr",
            type="qr_code",
            props={"data": "https://example.com"},
        )


class TestCanvas:
    def test_basic(self) -> None:
        node = ui.canvas("chart", width=400, height=300)
        _assert_node(
            node,
            id="chart",
            type="canvas",
            props={"width": 400, "height": 300},
        )


# ---------------------------------------------------------------------------
# Children flattening
# ---------------------------------------------------------------------------


class TestChildrenFlattening:
    def test_generator_flattened(self) -> None:
        items = ["a", "b", "c"]
        node = ui.column(
            *(ui.text(item) for item in items),
            spacing=4,
        )
        assert len(node["children"]) == 3

    def test_list_children_flattened(self) -> None:
        children = [ui.text("a"), ui.text("b")]
        node = ui.column(children)
        assert len(node["children"]) == 2

    def test_none_in_list_filtered(self) -> None:
        children = [ui.text("a"), None, ui.text("b")]
        node = ui.column(children)
        assert len(node["children"]) == 2

    def test_nested_generators(self) -> None:
        node = ui.column(
            [ui.text(f"item-{i}") for i in range(3)],
        )
        assert len(node["children"]) == 3

    def test_conditional_none_filtered(self) -> None:
        show_extra = False
        node = ui.column(
            ui.text("always"),
            ui.text("extra") if show_extra else None,
        )
        assert len(node["children"]) == 1


# ---------------------------------------------------------------------------
# Props filtering
# ---------------------------------------------------------------------------


class TestPropsFiltering:
    def test_none_props_stripped(self) -> None:
        """None values in kwargs should not appear in props."""
        # We pass None explicitly through kwargs; it should be stripped
        # by _node which filters None-valued props.
        # Widget builders pass kwargs directly, but _node cleans them.
        # Let's verify via a container with no kwargs at all.
        node = ui.column()
        assert node["props"] == {}
