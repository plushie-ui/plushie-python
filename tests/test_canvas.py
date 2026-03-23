"""Tests for plushie.canvas shape builder functions."""

from __future__ import annotations

from plushie import canvas

# ---------------------------------------------------------------------------
# Basic shapes
# ---------------------------------------------------------------------------


class TestRect:
    def test_basic(self) -> None:
        shape = canvas.rect(10, 20, 100, 50)
        assert shape["type"] == "rect"
        assert shape["x"] == 10
        assert shape["y"] == 20
        assert shape["w"] == 100
        assert shape["h"] == 50

    def test_with_fill(self) -> None:
        shape = canvas.rect(0, 0, 50, 50, fill="#ff0000")
        assert shape["fill"] == "#ff0000"

    def test_with_stroke(self) -> None:
        s = canvas.stroke("#000", 2)
        shape = canvas.rect(0, 0, 50, 50, stroke=s)
        assert shape["stroke"] == {"color": "#000", "width": 2}

    def test_with_radius(self) -> None:
        shape = canvas.rect(0, 0, 50, 50, radius=4)
        assert shape["radius"] == 4

    def test_with_opacity(self) -> None:
        shape = canvas.rect(0, 0, 50, 50, opacity=0.5)
        assert shape["opacity"] == 0.5

    def test_none_omitted(self) -> None:
        shape = canvas.rect(0, 0, 50, 50)
        assert "fill" not in shape
        assert "stroke" not in shape
        assert "radius" not in shape
        assert "opacity" not in shape


class TestCircle:
    def test_basic(self) -> None:
        shape = canvas.circle(50, 50, 25)
        assert shape["type"] == "circle"
        assert shape["x"] == 50
        assert shape["y"] == 50
        assert shape["r"] == 25

    def test_with_fill_and_stroke(self) -> None:
        shape = canvas.circle(0, 0, 10, fill="#0f0", stroke=canvas.stroke("#000", 1))
        assert shape["fill"] == "#0f0"
        assert shape["stroke"]["color"] == "#000"


class TestLine:
    def test_basic(self) -> None:
        shape = canvas.line(0, 0, 100, 100)
        assert shape["type"] == "line"
        assert shape["x1"] == 0
        assert shape["y1"] == 0
        assert shape["x2"] == 100
        assert shape["y2"] == 100

    def test_with_stroke(self) -> None:
        shape = canvas.line(0, 0, 50, 50, stroke=canvas.stroke("#333", 1, cap="round"))
        assert shape["stroke"]["cap"] == "round"


class TestPath:
    def test_basic(self) -> None:
        cmds = [canvas.move_to(0, 0), canvas.line_to(100, 0), canvas.close()]
        shape = canvas.path(cmds, fill="#00f")
        assert shape["type"] == "path"
        assert shape["commands"] == cmds
        assert shape["fill"] == "#00f"


class TestCanvasText:
    def test_basic(self) -> None:
        shape = canvas.canvas_text(10, 20, "Hello")
        assert shape["type"] == "text"
        assert shape["x"] == 10
        assert shape["y"] == 20
        assert shape["content"] == "Hello"

    def test_with_options(self) -> None:
        shape = canvas.canvas_text(0, 0, "Hi", fill="#000", size=16, align_x="center")
        assert shape["fill"] == "#000"
        assert shape["size"] == 16
        assert shape["align_x"] == "center"


class TestCanvasImage:
    def test_basic(self) -> None:
        shape = canvas.canvas_image("/img.png", 10, 20, 100, 80)
        assert shape["type"] == "image"
        assert shape["source"] == "/img.png"
        assert shape["x"] == 10
        assert shape["w"] == 100


class TestCanvasSvg:
    def test_basic(self) -> None:
        shape = canvas.canvas_svg("/icon.svg", 0, 0, 24, 24)
        assert shape["type"] == "svg"
        assert shape["source"] == "/icon.svg"


# ---------------------------------------------------------------------------
# Stroke helper
# ---------------------------------------------------------------------------


class TestStroke:
    def test_basic(self) -> None:
        s = canvas.stroke("#000", 2)
        assert s == {"color": "#000", "width": 2}

    def test_with_options(self) -> None:
        s = canvas.stroke("#fff", 1, cap="round", join="bevel", miter_limit=4.0)
        assert s["cap"] == "round"
        assert s["join"] == "bevel"
        assert s["miter_limit"] == 4.0


# ---------------------------------------------------------------------------
# Linear gradient
# ---------------------------------------------------------------------------


class TestLinearGradient:
    def test_basic(self) -> None:
        g = canvas.linear_gradient(
            (0, 0), (100, 0), [(0.0, "#ff0000"), (1.0, "#0000ff")]
        )
        assert g["type"] == "linear"
        assert g["start"] == [0, 0]
        assert g["end"] == [100, 0]
        assert g["stops"] == [[0.0, "#ff0000"], [1.0, "#0000ff"]]


# ---------------------------------------------------------------------------
# Group and layer
# ---------------------------------------------------------------------------


class TestGroup:
    def test_basic(self) -> None:
        r = canvas.rect(0, 0, 10, 10)
        c = canvas.circle(5, 5, 3)
        g = canvas.group(r, c)
        assert g["type"] == "group"
        assert len(g["children"]) == 2

    def test_with_xy_desugar(self) -> None:
        g = canvas.group(canvas.rect(0, 0, 10, 10), x=50, y=100)
        assert "transforms" in g
        assert g["transforms"][0] == {"type": "translate", "x": 50, "y": 100}
        assert "x" not in g or g.get("x") is None  # x/y not top-level

    def test_flattens_lists(self) -> None:
        shapes = [canvas.rect(0, 0, 10, 10), canvas.circle(5, 5, 3)]
        g = canvas.group(shapes)
        assert len(g["children"]) == 2

    def test_with_id(self) -> None:
        g = canvas.group("my-group", canvas.rect(0, 0, 10, 10), on_click=True)
        assert g["id"] == "my-group"
        assert g["on_click"] is True
        assert len(g["children"]) == 1

    def test_with_transforms(self) -> None:
        t = [canvas.translate(10, 20), canvas.rotate(0.5)]
        g = canvas.group(canvas.rect(0, 0, 10, 10), transforms=t)
        assert g["transforms"] == t

    def test_with_clip(self) -> None:
        c = canvas.clip(0, 0, 100, 100)
        g = canvas.group(canvas.rect(0, 0, 200, 200), clip=c)
        assert g["clip"] == {"x": 0, "y": 0, "w": 100, "h": 100}

    def test_xy_prepends_to_transforms(self) -> None:
        t = [canvas.rotate(0.5)]
        g = canvas.group(canvas.rect(0, 0, 10, 10), transforms=t, x=50, y=100)
        assert len(g["transforms"]) == 2
        assert g["transforms"][0] == {"type": "translate", "x": 50, "y": 100}
        assert g["transforms"][1] == {"type": "rotate", "angle": 0.5}

    def test_interactive_fields_top_level(self) -> None:
        g = canvas.group(
            "btn",
            canvas.rect(0, 0, 80, 40),
            on_click=True,
            on_hover=True,
            cursor="pointer",
            a11y={"role": "button"},
            focusable=True,
            focus_style={"stroke": "#3b82f6"},
            show_focus_ring=False,
        )
        assert g["id"] == "btn"
        assert g["on_click"] is True
        assert g["on_hover"] is True
        assert g["cursor"] == "pointer"
        assert g["a11y"] == {"role": "button"}
        assert g["focusable"] is True
        assert g["focus_style"] == {"stroke": "#3b82f6"}
        assert g["show_focus_ring"] is False
        assert "interactive" not in g

    def test_none_fields_omitted(self) -> None:
        g = canvas.group(canvas.rect(0, 0, 10, 10))
        assert "id" not in g
        assert "transforms" not in g
        assert "clip" not in g
        assert "on_click" not in g


class TestLayer:
    def test_basic(self) -> None:
        name, shapes = canvas.layer("bg", canvas.rect(0, 0, 100, 100))
        assert name == "bg"
        assert len(shapes) == 1

    def test_flattens_lists(self) -> None:
        shapes = [canvas.rect(0, 0, 10, 10), canvas.circle(5, 5, 3)]
        name, flat = canvas.layer("data", shapes)
        assert name == "data"
        assert len(flat) == 2

    def test_as_layers_dict(self) -> None:
        layers = dict(
            [
                canvas.layer("bg", canvas.rect(0, 0, 100, 100, fill="#eee")),
                canvas.layer("fg", canvas.circle(50, 50, 10, fill="#f00")),
            ]
        )
        assert "bg" in layers
        assert "fg" in layers
        assert len(layers["bg"]) == 1
        assert len(layers["fg"]) == 1


# ---------------------------------------------------------------------------
# Interactive wrapper
# ---------------------------------------------------------------------------


class TestInteractive:
    def test_leaf_wrapped_in_group(self) -> None:
        shape = canvas.rect(0, 0, 100, 40, fill="#3498db")
        wrapped = canvas.interactive(shape, "btn", on_click=True, cursor="pointer")
        # Must be a group wrapping the original shape
        assert wrapped["type"] == "group"
        assert wrapped["id"] == "btn"
        assert wrapped["on_click"] is True
        assert wrapped["cursor"] == "pointer"
        assert len(wrapped["children"]) == 1
        assert wrapped["children"][0]["type"] == "rect"
        assert wrapped["children"][0]["fill"] == "#3498db"

    def test_group_merged(self) -> None:
        g = canvas.group(canvas.rect(0, 0, 10, 10), canvas.circle(5, 5, 3))
        wrapped = canvas.interactive(g, "grp", on_click=True)
        assert wrapped["type"] == "group"
        assert wrapped["id"] == "grp"
        assert wrapped["on_click"] is True
        assert len(wrapped["children"]) == 2

    def test_all_fields(self) -> None:
        shape = canvas.circle(50, 50, 20)
        wrapped = canvas.interactive(
            shape,
            "drag_handle",
            on_click=True,
            on_hover=True,
            draggable=True,
            drag_axis="x",
            drag_bounds={"x": 0, "y": 0, "w": 200, "h": 100},
            cursor="grab",
            hover_style={"fill": "#fff"},
            pressed_style={"fill": "#ccc"},
            focus_style={"stroke": "#3b82f6"},
            show_focus_ring=False,
            tooltip="Drag me",
            a11y={"role": "slider"},
            hit_rect={"x": -5, "y": -5, "w": 50, "h": 50},
            focusable=True,
        )
        assert wrapped["type"] == "group"
        assert wrapped["id"] == "drag_handle"
        assert wrapped["on_click"] is True
        assert wrapped["on_hover"] is True
        assert wrapped["draggable"] is True
        assert wrapped["drag_axis"] == "x"
        assert wrapped["drag_bounds"] == {"x": 0, "y": 0, "w": 200, "h": 100}
        assert wrapped["cursor"] == "grab"
        assert wrapped["hover_style"] == {"fill": "#fff"}
        assert wrapped["pressed_style"] == {"fill": "#ccc"}
        assert wrapped["focus_style"] == {"stroke": "#3b82f6"}
        assert wrapped["show_focus_ring"] is False
        assert wrapped["tooltip"] == "Drag me"
        assert wrapped["a11y"] == {"role": "slider"}
        assert wrapped["hit_rect"] == {"x": -5, "y": -5, "w": 50, "h": 50}
        assert wrapped["focusable"] is True

    def test_none_fields_omitted(self) -> None:
        shape = canvas.rect(0, 0, 10, 10)
        wrapped = canvas.interactive(shape, "x")
        assert wrapped["id"] == "x"
        # Only id and type/children should be present
        assert "on_click" not in wrapped
        assert "cursor" not in wrapped

    def test_no_nested_interactive(self) -> None:
        shape = canvas.rect(0, 0, 10, 10)
        wrapped = canvas.interactive(shape, "x", on_click=True)
        assert "interactive" not in wrapped


# ---------------------------------------------------------------------------
# Path commands
# ---------------------------------------------------------------------------


class TestPathCommands:
    def test_move_to(self) -> None:
        assert canvas.move_to(10, 20) == ["move_to", 10, 20]

    def test_line_to(self) -> None:
        assert canvas.line_to(30, 40) == ["line_to", 30, 40]

    def test_bezier_to(self) -> None:
        assert canvas.bezier_to(1, 2, 3, 4, 5, 6) == ["bezier_to", 1, 2, 3, 4, 5, 6]

    def test_quadratic_to(self) -> None:
        assert canvas.quadratic_to(1, 2, 3, 4) == ["quadratic_to", 1, 2, 3, 4]

    def test_arc(self) -> None:
        assert canvas.arc(50, 50, 25, 0, 3.14) == ["arc", 50, 50, 25, 0, 3.14]

    def test_arc_to(self) -> None:
        assert canvas.arc_to(1, 2, 3, 4, 5) == ["arc_to", 1, 2, 3, 4, 5]

    def test_ellipse(self) -> None:
        assert canvas.ellipse(1, 2, 3, 4, 5, 6, 7) == ["ellipse", 1, 2, 3, 4, 5, 6, 7]

    def test_rounded_rect(self) -> None:
        assert canvas.rounded_rect(0, 0, 100, 50, 8) == [
            "rounded_rect",
            0,
            0,
            100,
            50,
            8,
        ]

    def test_close(self) -> None:
        assert canvas.close() == "close"


# ---------------------------------------------------------------------------
# Transform value objects
# ---------------------------------------------------------------------------


class TestTransformValues:
    def test_translate(self) -> None:
        assert canvas.translate(100, 200) == {
            "type": "translate",
            "x": 100,
            "y": 200,
        }

    def test_rotate(self) -> None:
        assert canvas.rotate(1.57) == {"type": "rotate", "angle": 1.57}

    def test_scale(self) -> None:
        assert canvas.scale(2.0, 3.0) == {"type": "scale", "x": 2.0, "y": 3.0}

    def test_scale_uniform(self) -> None:
        assert canvas.scale_uniform(2.0) == {"type": "scale", "factor": 2.0}


# ---------------------------------------------------------------------------
# Clip value object
# ---------------------------------------------------------------------------


class TestClipValue:
    def test_clip(self) -> None:
        assert canvas.clip(10, 20, 100, 80) == {
            "x": 10,
            "y": 20,
            "w": 100,
            "h": 80,
        }
