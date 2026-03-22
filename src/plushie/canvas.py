"""Canvas shape builders for plushie UI trees.

Shape builders return plain dicts suitable for use in canvas ``layers``
or ``shapes`` props. Interactive wrapping attaches hit-test and event
handling metadata to any shape.

Basic shapes: rect, circle, line, path, canvas_text, canvas_image,
canvas_svg.

Structure: group (groups children), layer (named layer of shapes).

Interactive: interactive(shape, ...) wraps a shape with click/hover/drag
behavior.

Path commands: move_to, line_to, bezier_to, quadratic_to, arc, arc_to,
ellipse, rounded_rect, close.

Transforms: push_transform, pop_transform, translate, rotate, scale.

Clipping: push_clip, pop_clip.

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
    """Rectangle shape.

    Args:
        x: X position.
        y: Y position.
        w: Width.
        h: Height.
        fill: Fill color (hex string) or gradient dict.
        stroke: Stroke descriptor (from ``stroke()``).
        radius: Corner radius.
        opacity: Opacity (0.0 to 1.0).
    """
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
    """Circle shape.

    Args:
        x: Center X position.
        y: Center Y position.
        r: Radius.
        fill: Fill color or gradient.
        stroke: Stroke descriptor.
        opacity: Opacity (0.0 to 1.0).
    """
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
    """Line shape.

    Args:
        x1: Start X.
        y1: Start Y.
        x2: End X.
        y2: End Y.
        stroke: Stroke descriptor.
        opacity: Opacity (0.0 to 1.0).
    """
    return _shape("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=stroke, opacity=opacity)


def path(
    commands: list[Any],
    /,
    *,
    fill: str | dict[str, Any] | None = None,
    stroke: dict[str, Any] | None = None,
    opacity: float | None = None,
) -> Shape:
    """Arbitrary path shape built from path commands.

    Args:
        commands: List of path commands (from ``move_to``, ``line_to``, etc.).
        fill: Fill color or gradient.
        stroke: Stroke descriptor.
        opacity: Opacity (0.0 to 1.0).
    """
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
    """Canvas text shape.

    Args:
        x: X position.
        y: Y position.
        content: Text string.
        fill: Text fill color.
        size: Font size in pixels.
        font: Font specification.
        align_x: Horizontal alignment (``"left"``, ``"center"``, ``"right"``).
        align_y: Vertical alignment (``"top"``, ``"center"``, ``"bottom"``).
        opacity: Opacity (0.0 to 1.0).
    """
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
    source: str,
    x: float,
    y: float,
    w: float,
    h: float,
    /,
    **kwargs: Any,
) -> Shape:
    """Canvas image shape.

    Args:
        source: Path to image file.
        x: X position.
        y: Y position.
        w: Width.
        h: Height.
        **kwargs: Additional props (opacity, etc.).
    """
    return _shape("image", source=source, x=x, y=y, w=w, h=h, **kwargs)


def canvas_svg(
    source: str,
    x: float,
    y: float,
    w: float,
    h: float,
    /,
    **kwargs: Any,
) -> Shape:
    """Canvas SVG shape.

    Args:
        source: Path to SVG file.
        x: X position.
        y: Y position.
        w: Width.
        h: Height.
        **kwargs: Additional props (color, opacity, etc.).
    """
    return _shape("svg", source=source, x=x, y=y, w=w, h=h, **kwargs)


# ---------------------------------------------------------------------------
# Structure shapes
# ---------------------------------------------------------------------------


def group(
    *children: Any,
    x: float | None = None,
    y: float | None = None,
) -> Shape:
    """Group of shapes, optionally positioned.

    Args:
        *children: Shape dicts or lists of shapes (flattened one level).
        x: Group X offset.
        y: Group Y offset.
    """
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
    return _shape("group", children=flat, x=x, y=y)


def layer(name: str, *children: Any) -> tuple[str, list[Shape]]:
    """Named layer of shapes for canvas ``layers`` prop.

    Returns a ``(name, shapes)`` tuple suitable for building a layers dict::

        canvas("chart", layers=dict([
            layer("bg", rect(0, 0, 100, 100, fill="#eee")),
            layer("data", *bars),
        ]))

    Args:
        name: Layer name.
        *children: Shape dicts or lists of shapes (flattened one level).
    """
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
    /,
    *,
    id: str,
    on_click: bool | None = None,
    on_hover: bool | None = None,
    draggable: bool | None = None,
    drag_axis: str | None = None,
    drag_bounds: dict[str, Any] | None = None,
    cursor: str | None = None,
    hover_style: dict[str, Any] | None = None,
    pressed_style: dict[str, Any] | None = None,
    tooltip: str | None = None,
    a11y: dict[str, Any] | None = None,
    hit_rect: dict[str, Any] | None = None,
) -> Shape:
    """Wrap a shape with interactive hit-test and event handling.

    Args:
        shape: The shape to make interactive.
        id: Interactive element identifier (required).
        on_click: Enable click events.
        on_hover: Enable hover events.
        draggable: Enable drag events.
        drag_axis: Constrain drag to axis (``"x"`` or ``"y"``).
        drag_bounds: Drag boundary constraints.
        cursor: Cursor style on hover.
        hover_style: Style overrides on hover.
        pressed_style: Style overrides when pressed.
        tooltip: Tooltip text.
        a11y: Accessibility metadata.
        hit_rect: Custom hit rectangle.
    """
    interactive_data: dict[str, Any] = {"id": id}
    if on_click is not None:
        interactive_data["on_click"] = on_click
    if on_hover is not None:
        interactive_data["on_hover"] = on_hover
    if draggable is not None:
        interactive_data["draggable"] = draggable
    if drag_axis is not None:
        interactive_data["drag_axis"] = drag_axis
    if drag_bounds is not None:
        interactive_data["drag_bounds"] = drag_bounds
    if cursor is not None:
        interactive_data["cursor"] = cursor
    if hover_style is not None:
        interactive_data["hover_style"] = hover_style
    if pressed_style is not None:
        interactive_data["pressed_style"] = pressed_style
    if tooltip is not None:
        interactive_data["tooltip"] = tooltip
    if a11y is not None:
        interactive_data["a11y"] = a11y
    if hit_rect is not None:
        interactive_data["hit_rect"] = hit_rect

    return {**shape, "interactive": interactive_data}


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
    cp1x: float,
    cp1y: float,
    cp2x: float,
    cp2y: float,
    x: float,
    y: float,
) -> list[Any]:
    """Cubic bezier curve path command."""
    return ["bezier_to", cp1x, cp1y, cp2x, cp2y, x, y]


def quadratic_to(cpx: float, cpy: float, x: float, y: float) -> list[Any]:
    """Quadratic bezier curve path command."""
    return ["quadratic_to", cpx, cpy, x, y]


def arc(
    cx: float,
    cy: float,
    r: float,
    start_angle: float,
    end_angle: float,
) -> list[Any]:
    """Arc path command (center, radius, start and end angles in radians)."""
    return ["arc", cx, cy, r, start_angle, end_angle]


def arc_to(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
) -> list[Any]:
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
# Transform commands
# ---------------------------------------------------------------------------


def push_transform() -> Shape:
    """Push (save) the current transform state."""
    return {"type": "push_transform"}


def pop_transform() -> Shape:
    """Pop (restore) the previously saved transform state."""
    return {"type": "pop_transform"}


def translate(x: float, y: float) -> Shape:
    """Translate the coordinate origin."""
    return {"type": "translate", "x": x, "y": y}


def rotate(angle: float) -> Shape:
    """Rotate the coordinate system (angle in radians)."""
    return {"type": "rotate", "angle": angle}


def scale(x: float, y: float) -> Shape:
    """Scale the coordinate system."""
    return {"type": "scale", "x": x, "y": y}


# ---------------------------------------------------------------------------
# Clipping commands
# ---------------------------------------------------------------------------


def push_clip(x: float, y: float, w: float, h: float) -> Shape:
    """Push a clipping rectangle."""
    return {"type": "push_clip", "x": x, "y": y, "w": w, "h": h}


def pop_clip() -> Shape:
    """Pop the most recent clipping rectangle."""
    return {"type": "pop_clip"}


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    # Type
    "Shape",
    "arc",
    "arc_to",
    "bezier_to",
    "canvas_image",
    "canvas_svg",
    "canvas_text",
    "circle",
    "close",
    "ellipse",
    # Structure
    "group",
    # Interactive
    "interactive",
    "layer",
    "line",
    "line_to",
    "linear_gradient",
    # Path commands
    "move_to",
    "path",
    "pop_clip",
    "pop_transform",
    # Clipping
    "push_clip",
    # Transforms
    "push_transform",
    "quadratic_to",
    # Basic shapes
    "rect",
    "rotate",
    "rounded_rect",
    "scale",
    # Helpers
    "stroke",
    "translate",
]
