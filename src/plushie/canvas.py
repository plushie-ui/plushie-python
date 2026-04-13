"""Canvas shape builders for plushie UI trees.

Shape builders return plain dicts suitable for use in canvas ``layers``
or ``shapes`` props. Interactive wrapping attaches hit-test and event
handling metadata to any shape.

Basic shapes: rect, circle, line, path, canvas_text, canvas_image,
canvas_svg.

Structure: group (groups children), layer (named layer of shapes).

Interactive: interactive(shape, id, ...) wraps a shape as a group with
click/hover/drag behavior. The renderer only recognizes interactive
fields on group nodes.

Path commands: move_to, line_to, bezier_to, quadratic_to, arc, arc_to,
ellipse, rounded_rect, close.

Transforms: translate, rotate, scale, scale_uniform. Value objects for
the group ``transforms`` list.

Clipping: clip(x, y, w, h). Value object for the group ``clip`` field.

Stroke helper: stroke(color, width, ...).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

type Shape = dict[str, Any]
"""A canvas shape descriptor (plain dict with ``"type"`` key)."""


# ---------------------------------------------------------------------------
# Stroke helper
# ---------------------------------------------------------------------------


def stroke(
    color: str,
    width: float,
    /,
    *,
    cap: str | None = None,
    join: str | None = None,
    miter_limit: float | None = None,
) -> dict[str, Any]:
    """Build a stroke descriptor.

    Args:
        color: Stroke color (hex string).
        width: Stroke width in pixels.
        cap: Line cap style (``"butt"``, ``"round"``, ``"square"``).
        join: Line join style (``"miter"``, ``"round"``, ``"bevel"``).
        miter_limit: Miter limit for miter joins.
    """
    result: dict[str, Any] = {"color": color, "width": width}
    if cap is not None:
        result["cap"] = cap
    if join is not None:
        result["join"] = join
    if miter_limit is not None:
        result["miter_limit"] = miter_limit
    return result


# ---------------------------------------------------------------------------
# Linear gradient helper
# ---------------------------------------------------------------------------


def linear_gradient(
    start: tuple[float, float],
    end: tuple[float, float],
    stops: list[tuple[float, str]],
) -> dict[str, Any]:
    """Build a linear gradient fill value.

    Args:
        start: ``(x, y)`` start point.
        end: ``(x, y)`` end point.
        stops: List of ``(offset, color)`` tuples.
    """
    return {
        "type": "linear",
        "start": list(start),
        "end": list(end),
        "stops": [[offset, color] for offset, color in stops],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _shape(type_name: str, **fields: Any) -> Shape:
    """Build a shape dict, stripping None-valued fields."""
    result: dict[str, Any] = {"type": type_name}
    for k, v in fields.items():
        if v is not None:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Basic shapes
# ---------------------------------------------------------------------------


def rect(
    x: float,
    y: float,
    w: float,
    h: float,
    /,
    *,
    fill: str | dict[str, Any] | None = None,
    stroke: dict[str, Any] | None = None,
    radius: float | None = None,
    opacity: float | None = None,
) -> Shape:
    """Rectangle shape."""
    return _shape(
        "rect",
        x=x,
        y=y,
        w=w,
        h=h,
        fill=fill,
        stroke=stroke,
        radius=radius,
        opacity=opacity,
    )


def circle(
    x: float,
    y: float,
    r: float,
    /,
    *,
    fill: str | dict[str, Any] | None = None,
    stroke: dict[str, Any] | None = None,
    opacity: float | None = None,
) -> Shape:
    """Circle shape."""
    return _shape("circle", x=x, y=y, r=r, fill=fill, stroke=stroke, opacity=opacity)


def line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    /,
    *,
    stroke: dict[str, Any] | None = None,
    opacity: float | None = None,
) -> Shape:
    """Line shape."""
    return _shape("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=stroke, opacity=opacity)


def path(
    commands: list[Any],
    /,
    *,
    fill: str | dict[str, Any] | None = None,
    stroke: dict[str, Any] | None = None,
    opacity: float | None = None,
) -> Shape:
    """Arbitrary path shape built from path commands."""
    return _shape("path", commands=commands, fill=fill, stroke=stroke, opacity=opacity)


def canvas_text(
    x: float,
    y: float,
    content: str,
    /,
    *,
    fill: str | None = None,
    size: float | None = None,
    font: str | dict[str, Any] | None = None,
    align_x: str | None = None,
    align_y: str | None = None,
    opacity: float | None = None,
) -> Shape:
    """Canvas text shape."""
    return _shape(
        "text",
        x=x,
        y=y,
        content=content,
        fill=fill,
        size=size,
        font=font,
        align_x=align_x,
        align_y=align_y,
        opacity=opacity,
    )


def canvas_image(
    source: str, x: float, y: float, w: float, h: float, /, **kwargs: Any
) -> Shape:
    """Canvas image shape."""
    return _shape("image", source=source, x=x, y=y, w=w, h=h, **kwargs)


def canvas_svg(
    source: str, x: float, y: float, w: float, h: float, /, **kwargs: Any
) -> Shape:
    """Canvas SVG shape."""
    return _shape("svg", source=source, x=x, y=y, w=w, h=h, **kwargs)


# ---------------------------------------------------------------------------
# Structure shapes
# ---------------------------------------------------------------------------


def group(
    *args: Any,
    transforms: list[dict[str, Any]] | None = None,
    clip: dict[str, Any] | None = None,
    x: float | None = None,
    y: float | None = None,
    on_click: bool | None = None,
    on_hover: bool | None = None,
    draggable: bool | None = None,
    drag_axis: str | None = None,
    drag_bounds: dict[str, Any] | None = None,
    cursor: str | None = None,
    hit_rect: dict[str, Any] | None = None,
    tooltip: str | None = None,
    hover_style: dict[str, Any] | None = None,
    pressed_style: dict[str, Any] | None = None,
    focus_style: dict[str, Any] | None = None,
    show_focus_ring: bool | None = None,
    focus_ring_radius: float | None = None,
    a11y: dict[str, Any] | None = None,
    focusable: bool | None = None,
) -> Shape:
    """Group of shapes with optional transforms, clip, and interactivity.

    The first positional arg may be a string ``id`` (making the group
    interactive). Remaining positional args are children.
    If ``x`` or ``y`` kwargs are present, they desugar to a leading
    translate in the transforms list.
    """
    id_val: str | None = None
    children_args: tuple[Any, ...]
    if args and isinstance(args[0], str):
        id_val = args[0]
        children_args = args[1:]
    else:
        children_args = args

    flat: list[Shape] = []
    for child in children_args:
        if isinstance(child, dict):
            flat.append(child)
        elif isinstance(child, (list, tuple)):
            flat.extend(child)
        else:
            try:
                flat.extend(child)
            except TypeError:
                flat.append(child)

    xforms = list(transforms) if transforms else []
    if x is not None or y is not None:
        xforms.insert(0, translate(x or 0.0, y or 0.0))

    result: dict[str, Any] = {"type": "group", "children": flat}
    if xforms:
        result["transforms"] = xforms
    if clip is not None:
        result["clip"] = clip
    if id_val is not None:
        result["id"] = id_val

    for key, val in [
        ("on_click", on_click),
        ("on_hover", on_hover),
        ("draggable", draggable),
        ("drag_axis", drag_axis),
        ("drag_bounds", drag_bounds),
        ("cursor", cursor),
        ("hit_rect", hit_rect),
        ("tooltip", tooltip),
        ("hover_style", hover_style),
        ("pressed_style", pressed_style),
        ("focus_style", focus_style),
        ("show_focus_ring", show_focus_ring),
        ("focus_ring_radius", focus_ring_radius),
        ("a11y", a11y),
        ("focusable", focusable),
    ]:
        if val is not None:
            result[key] = val

    return result


def layer(name: str, *children: Any) -> tuple[str, list[Shape]]:
    """Named layer of shapes for canvas ``layers`` prop."""
    flat: list[Shape] = []
    for child in children:
        if isinstance(child, dict):
            flat.append(child)
        elif isinstance(child, (list, tuple)):
            flat.extend(child)
        else:
            try:
                flat.extend(child)
            except TypeError:
                flat.append(child)
    return (name, flat)


# ---------------------------------------------------------------------------
# Interactive wrapper
# ---------------------------------------------------------------------------


def interactive(
    shape: Shape,
    id: str,
    /,
    *,
    on_click: bool | None = None,
    on_hover: bool | None = None,
    draggable: bool | None = None,
    drag_axis: str | None = None,
    drag_bounds: dict[str, Any] | None = None,
    cursor: str | None = None,
    hover_style: dict[str, Any] | None = None,
    pressed_style: dict[str, Any] | None = None,
    focus_style: dict[str, Any] | None = None,
    show_focus_ring: bool | None = None,
    focus_ring_radius: float | None = None,
    tooltip: str | None = None,
    a11y: dict[str, Any] | None = None,
    hit_rect: dict[str, Any] | None = None,
    focusable: bool | None = None,
) -> Shape:
    """Make a shape interactive by wrapping it in a group.

    The renderer only recognizes interactive fields on group nodes.
    If the shape is already a group, interactive fields are merged
    directly into it. If it is a leaf shape, it is wrapped as the
    sole child of a new group.
    """
    opts: dict[str, Any] = {"id": id}
    for key, val in [
        ("on_click", on_click),
        ("on_hover", on_hover),
        ("draggable", draggable),
        ("drag_axis", drag_axis),
        ("drag_bounds", drag_bounds),
        ("cursor", cursor),
        ("hover_style", hover_style),
        ("pressed_style", pressed_style),
        ("focus_style", focus_style),
        ("show_focus_ring", show_focus_ring),
        ("focus_ring_radius", focus_ring_radius),
        ("tooltip", tooltip),
        ("a11y", a11y),
        ("hit_rect", hit_rect),
        ("focusable", focusable),
    ]:
        if val is not None:
            opts[key] = val

    if shape.get("type") == "group":
        return {**shape, **opts}

    return {"type": "group", **opts, "children": [shape]}


# ---------------------------------------------------------------------------
# Path commands
# ---------------------------------------------------------------------------


def move_to(x: float, y: float) -> list[Any]:
    """Move-to path command."""
    return ["move_to", x, y]


def line_to(x: float, y: float) -> list[Any]:
    """Line-to path command."""
    return ["line_to", x, y]


def bezier_to(
    cp1x: float, cp1y: float, cp2x: float, cp2y: float, x: float, y: float
) -> list[Any]:
    """Cubic bezier curve path command."""
    return ["bezier_to", cp1x, cp1y, cp2x, cp2y, x, y]


def quadratic_to(cpx: float, cpy: float, x: float, y: float) -> list[Any]:
    """Quadratic bezier curve path command."""
    return ["quadratic_to", cpx, cpy, x, y]


def arc(
    cx: float, cy: float, r: float, start_angle: float, end_angle: float
) -> list[Any]:
    """Arc path command."""
    return ["arc", cx, cy, r, start_angle, end_angle]


def arc_to(x1: float, y1: float, x2: float, y2: float, radius: float) -> list[Any]:
    """Tangent arc path command."""
    return ["arc_to", x1, y1, x2, y2, radius]


def ellipse(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    rotation: float,
    start_angle: float,
    end_angle: float,
) -> list[Any]:
    """Ellipse path command."""
    return ["ellipse", cx, cy, rx, ry, rotation, start_angle, end_angle]


def rounded_rect(x: float, y: float, w: float, h: float, radius: float) -> list[Any]:
    """Rounded rectangle path command."""
    return ["rounded_rect", x, y, w, h, radius]


def close() -> str:
    """Close path command."""
    return "close"


# ---------------------------------------------------------------------------
# Transform value objects
# ---------------------------------------------------------------------------


def translate(x: float, y: float) -> dict[str, Any]:
    """Translate transform value for the group ``transforms`` list."""
    return {"type": "translate", "x": x, "y": y}


def rotate(angle: float) -> dict[str, Any]:
    """Rotate transform value (angle in radians)."""
    return {"type": "rotate", "angle": angle}


def scale(x: float, y: float) -> dict[str, Any]:
    """Non-uniform scale transform value."""
    return {"type": "scale", "x": x, "y": y}


def scale_uniform(factor: float) -> dict[str, Any]:
    """Uniform scale transform value."""
    return {"type": "scale", "factor": factor}


# ---------------------------------------------------------------------------
# Clip value object
# ---------------------------------------------------------------------------


def clip(x: float, y: float, w: float, h: float) -> dict[str, Any]:
    """Clip rectangle value for the group ``clip`` field."""
    return {"x": x, "y": y, "w": w, "h": h}


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "Shape",
    "arc",
    "arc_to",
    "bezier_to",
    "canvas_image",
    "canvas_svg",
    "canvas_text",
    "circle",
    "clip",
    "close",
    "ellipse",
    "group",
    "interactive",
    "layer",
    "line",
    "line_to",
    "linear_gradient",
    "move_to",
    "path",
    "quadratic_to",
    "rect",
    "rotate",
    "rounded_rect",
    "scale",
    "scale_uniform",
    "stroke",
    "translate",
]
