"""Tests for code examples in docs/layout.md.

Each test corresponds to an HTML test marker comment in the doc.
"""

from __future__ import annotations

from plushie import ui

# -- Length examples ---------------------------------------------------------


class TestLengthFill:
    def test_fill(self) -> None:
        """Docs: width='fill' on a column."""
        tree = ui.column(ui.text("x"), width="fill")
        assert tree["type"] == "column"
        assert tree["props"]["width"] == "fill"


class TestLengthFixed:
    def test_fixed(self) -> None:
        """Docs: width=250 on a container."""
        tree = ui.container("sidebar", ui.text("x"), width=250)
        assert tree["type"] == "container"
        assert tree["id"] == "sidebar"
        assert tree["props"]["width"] == 250


class TestLengthFillPortion:
    def test_fill_portion(self) -> None:
        """Docs: proportional fill_portion layout."""
        tree = ui.row(
            ui.container("left", ui.text("x"), width=("fill_portion", 2)),
            ui.container("right", ui.text("y"), width=("fill_portion", 1)),
        )
        assert tree["type"] == "row"
        children = tree["children"]
        assert children[0]["id"] == "left"
        assert children[0]["props"]["width"] == {"fill_portion": 2}
        assert children[1]["id"] == "right"
        assert children[1]["props"]["width"] == {"fill_portion": 1}


class TestLengthShrink:
    def test_shrink(self) -> None:
        """Docs: width='shrink' on a button."""
        tree = ui.button("save", "Save", width="shrink")
        assert tree["type"] == "button"
        assert tree["props"]["width"] == "shrink"


# -- Padding examples -------------------------------------------------------


class TestPaddingUniform:
    def test_uniform(self) -> None:
        """Docs: padding=16 uniform."""
        tree = ui.container("box", ui.text("x"), padding=16)
        assert tree["props"]["padding"] == 16


class TestPaddingXY:
    def test_xy(self) -> None:
        """Docs: padding=(8, 16) vertical/horizontal."""
        tree = ui.container("box", ui.text("x"), padding=(8, 16))
        # (v, h) shorthand expands to {top: v, right: h, bottom: v, left: h}
        # on the wire; the renderer rejects tuple encodings.
        assert tree["props"]["padding"] == {
            "top": 8,
            "right": 16,
            "bottom": 8,
            "left": 16,
        }


class TestPaddingPerSide:
    def test_per_side(self) -> None:
        """Docs: per-side padding dict."""
        tree = ui.container(
            "box",
            ui.text("x"),
            padding={"top": 0, "right": 16, "bottom": 8, "left": 16},
        )
        assert tree["props"]["padding"] == {
            "top": 0,
            "right": 16,
            "bottom": 8,
            "left": 16,
        }


# -- Spacing example ---------------------------------------------------------


class TestSpacing:
    def test_spacing_between_children(self) -> None:
        """Docs: spacing=8 in a column."""
        tree = ui.column(
            ui.text("First"),
            ui.text("Second"),
            ui.text("Third"),
            spacing=8,
        )
        assert tree["type"] == "column"
        assert tree["props"]["spacing"] == 8
        assert len(tree["children"]) == 3
        assert tree["children"][0]["props"]["content"] == "First"
        assert tree["children"][1]["props"]["content"] == "Second"
        assert tree["children"][2]["props"]["content"] == "Third"


# -- Alignment examples -----------------------------------------------------


class TestAlignXColumn:
    def test_align_x_center(self) -> None:
        """Docs: align_x='center' in a column."""
        tree = ui.column(
            ui.text("Centered"),
            ui.button("ok", "OK"),
            align_x="center",
        )
        assert tree["type"] == "column"
        assert tree["props"]["align_x"] == "center"
        assert tree["children"][0]["props"]["content"] == "Centered"
        assert tree["children"][1]["props"]["label"] == "OK"


class TestAlignCenterContainer:
    def test_center_shorthand(self) -> None:
        """Docs: center=True on container."""
        tree = ui.container(
            "page",
            ui.text("Dead center"),
            width="fill",
            height="fill",
            center=True,
        )
        assert tree["type"] == "container"
        assert tree["props"]["width"] == "fill"
        assert tree["props"]["height"] == "fill"
        assert tree["props"]["center"] is True
        assert tree["children"][0]["props"]["content"] == "Dead center"


# -- Layout container examples -----------------------------------------------


class TestColumnWithProps:
    def test_column_full_props(self) -> None:
        """Docs: column with spacing, padding, width, align_x."""
        tree = ui.column(
            ui.text("title", "Title", size=24),
            ui.text("subtitle", "Subtitle", size=14),
            id="main",
            spacing=16,
            padding=20,
            width="fill",
            align_x="center",
        )
        assert tree["type"] == "column"
        assert tree["id"] == "main"
        assert tree["props"]["spacing"] == 16
        assert tree["props"]["padding"] == 20
        assert tree["props"]["width"] == "fill"
        assert tree["props"]["align_x"] == "center"
        children = tree["children"]
        assert children[0]["props"]["size"] == 24
        assert children[1]["props"]["size"] == 14


class TestRowWithAlignY:
    def test_row_align_y(self) -> None:
        """Docs: row with spacing and align_y."""
        tree = ui.row(
            ui.button("back", "<"),
            ui.text("Page 1 of 5"),
            ui.button("next", ">"),
            spacing=8,
            align_y="center",
        )
        assert tree["type"] == "row"
        assert tree["props"]["spacing"] == 8
        assert tree["props"]["align_y"] == "center"
        children = tree["children"]
        assert children[0]["props"]["label"] == "<"
        assert children[1]["props"]["content"] == "Page 1 of 5"
        assert children[2]["props"]["label"] == ">"


class TestContainerWithStyle:
    def test_container_style(self) -> None:
        """Docs: container with style='rounded_box'."""
        tree = ui.container(
            "card",
            ui.column(
                ui.text("Card title"),
                ui.text("Card content"),
            ),
            padding=16,
            style="rounded_box",
            width="fill",
        )
        assert tree["type"] == "container"
        assert tree["id"] == "card"
        assert tree["props"]["style"] == "rounded_box"
        assert tree["props"]["width"] == "fill"
        assert tree["props"]["padding"] == 16
        col = tree["children"][0]
        assert col["type"] == "column"
        assert col["children"][0]["props"]["content"] == "Card title"
        assert col["children"][1]["props"]["content"] == "Card content"


class TestScrollable:
    def test_scrollable(self) -> None:
        """Docs: scrollable with height and width."""
        tree = ui.scrollable(
            "list",
            ui.column(
                ui.text("item", "Item"),
                spacing=4,
            ),
            height=400,
            width="fill",
        )
        assert tree["type"] == "scrollable"
        assert tree["id"] == "list"
        assert tree["props"]["height"] == 400
        assert tree["props"]["width"] == "fill"
        col = tree["children"][0]
        assert col["type"] == "column"
        assert col["props"]["spacing"] == 4


class TestStack:
    def test_stack_overlay(self) -> None:
        """Docs: stack with image background and overlay."""
        tree = ui.stack(
            ui.image("bg", "background.png", width="fill", height="fill"),
            ui.container(
                "overlay",
                ui.text("overlay_text", "Overlaid text", size=48),
                width="fill",
                height="fill",
                center=True,
            ),
        )
        assert tree["type"] == "stack"
        children = tree["children"]
        assert children[0]["type"] == "image"
        assert children[0]["props"]["source"] == "background.png"
        assert children[0]["props"]["width"] == "fill"
        assert children[1]["type"] == "container"
        text_node = children[1]["children"][0]
        assert text_node["props"]["content"] == "Overlaid text"
        assert text_node["props"]["size"] == 48


class TestSpace:
    def test_space_pushes_right(self) -> None:
        """Docs: space as flexible separator in a row."""
        tree = ui.row(
            ui.text("Left"),
            ui.space(width="fill"),
            ui.text("Right"),
        )
        assert tree["type"] == "row"
        children = tree["children"]
        assert children[0]["props"]["content"] == "Left"
        assert children[1]["type"] == "space"
        assert children[1]["props"]["width"] == "fill"
        assert children[2]["props"]["content"] == "Right"


class TestGrid:
    def test_grid_layout(self) -> None:
        """Docs: grid with columns and spacing."""
        items = [{"id": "1", "url": "a.png"}, {"id": "2", "url": "b.png"}]
        tree = ui.grid(
            *(
                ui.image(f"img:{item['id']}", item["url"], width="fill")
                for item in items
            ),
            id="gallery",
            num_columns=3,
            spacing=8,
        )
        assert tree["type"] == "grid"
        assert tree["id"] == "gallery"
        assert tree["props"]["spacing"] == 8
        assert tree["props"]["num_columns"] == 3
        assert len(tree["children"]) == 2
        assert all(c["type"] == "image" for c in tree["children"])


# -- Common layout patterns --------------------------------------------------


class TestCenteredPage:
    def test_centered_page(self) -> None:
        """Docs: centered page pattern."""
        tree = ui.container(
            "page",
            ui.column(
                ui.text("welcome", "Welcome", size=32),
                ui.button("start", "Get Started"),
                spacing=16,
                align_x="center",
            ),
            width="fill",
            height="fill",
            center=True,
        )
        assert tree["type"] == "container"
        assert tree["id"] == "page"
        assert tree["props"]["width"] == "fill"
        assert tree["props"]["height"] == "fill"
        assert tree["props"]["center"] is True
        col = tree["children"][0]
        assert col["props"]["align_x"] == "center"
        assert col["props"]["spacing"] == 16
        text_node = col["children"][0]
        assert text_node["props"]["content"] == "Welcome"
        assert text_node["props"]["size"] == 32
        assert col["children"][1]["props"]["label"] == "Get Started"


class TestSidebarContent:
    def test_sidebar_content_layout(self) -> None:
        """Docs: sidebar + content pattern."""
        tree = ui.row(
            ui.container(
                "sidebar",
                ui.text("nav"),
                width=250,
                height="fill",
                padding=16,
            ),
            ui.container(
                "content",
                ui.text("main"),
                width="fill",
                height="fill",
                padding=16,
            ),
            width="fill",
            height="fill",
        )
        assert tree["type"] == "row"
        assert tree["props"]["width"] == "fill"
        children = tree["children"]
        assert children[0]["id"] == "sidebar"
        assert children[0]["props"]["width"] == 250
        assert children[1]["id"] == "content"
        assert children[1]["props"]["width"] == "fill"


class TestHeaderBodyFooter:
    def test_header_body_footer(self) -> None:
        """Docs: header + body + footer pattern."""
        tree = ui.column(
            ui.container("header", ui.text("hdr"), width="fill", padding=(8, 16)),
            ui.scrollable(
                "body",
                ui.text("content"),
                width="fill",
                height="fill",
            ),
            ui.container("footer", ui.text("ftr"), width="fill", padding=(8, 16)),
            width="fill",
            height="fill",
        )
        assert tree["type"] == "column"
        children = tree["children"]
        assert children[0]["id"] == "header"
        assert children[0]["props"]["padding"] == {
            "top": 8,
            "right": 16,
            "bottom": 8,
            "left": 16,
        }
        assert children[1]["id"] == "body"
        assert children[1]["type"] == "scrollable"
        assert children[2]["id"] == "footer"
