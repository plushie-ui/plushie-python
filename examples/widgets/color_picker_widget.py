"""Canvas-based HSV color picker widget.

Renders a hue ring surrounding a saturation/value square. The ring is built
from path segments covering the hue spectrum. The SV square uses overlapping
linear gradients (hue-to-white horizontal, transparent-to-black vertical).
Cursor circles mark the current hue position on the ring and the current
SV position in the square.

Usage::

    from examples.widgets.color_picker_widget import ColorPickerWidget

    ColorPickerWidget.render("picker", model.hue, model.saturation, model.value)

Events: ``CanvasPress``, ``CanvasMove``, ``CanvasRelease`` with absolute x/y
coordinates for computing hue angles and SV positions from the geometry
constants.
"""

from __future__ import annotations

import math
from typing import Any

from plushie import canvas as c
from plushie import ui

# -- Geometry constants ------------------------------------------------------

CANVAS_SIZE = 400
CX = CANVAS_SIZE // 2
CY = CANVAS_SIZE // 2
OUTER_R = 190
INNER_R = 150
MID_R = (INNER_R + OUTER_R) // 2
SQ_ORIGIN = 100
SQ_SIZE = 200
SEGMENTS = 72
CURSOR_R = 7


def render(
    id: str,
    hue: float,
    saturation: float,
    value: float,
) -> dict[str, Any]:
    """Render the color picker canvas.

    Returns a canvas node with interactive hue ring and SV square.
    """
    return ui.canvas(
        id,
        width=CANVAS_SIZE,
        height=CANVAS_SIZE,
        on_press=True,
        on_release=True,
        on_move=True,
        layers=dict(
            [
                c.layer("a_ring", *_ring_shapes()),
                c.layer("b_sv_hue", *_sv_hue_shapes(hue)),
                c.layer("c_sv_dark", *_sv_dark_shapes()),
                c.layer("d_cursors", *_cursor_shapes(hue, saturation, value)),
            ]
        ),
    )


# -- Ring layer --------------------------------------------------------------


def _ring_shapes() -> list[dict[str, Any]]:
    deg_per_segment = 360 / SEGMENTS
    shapes: list[dict[str, Any]] = []

    for i in range(SEGMENTS):
        hue_deg = i * deg_per_segment
        a1 = (hue_deg - 90) * math.pi / 180
        a2 = (hue_deg + deg_per_segment - 90) * math.pi / 180

        commands = [
            c.move_to(CX + INNER_R * math.cos(a1), CY + INNER_R * math.sin(a1)),
            c.line_to(CX + OUTER_R * math.cos(a1), CY + OUTER_R * math.sin(a1)),
            c.line_to(CX + OUTER_R * math.cos(a2), CY + OUTER_R * math.sin(a2)),
            c.line_to(CX + INNER_R * math.cos(a2), CY + INNER_R * math.sin(a2)),
            c.close(),
        ]
        shapes.append(c.path(commands, fill=_hsv_to_hex(hue_deg, 1.0, 1.0)))

    return shapes


# -- SV layers ---------------------------------------------------------------


def _sv_hue_shapes(hue: float) -> list[dict[str, Any]]:
    hue_color = _hsv_to_hex(hue, 1.0, 1.0)
    return [
        c.rect(
            SQ_ORIGIN,
            SQ_ORIGIN,
            SQ_SIZE,
            SQ_SIZE,
            fill=c.linear_gradient(
                (SQ_ORIGIN, SQ_ORIGIN),
                (SQ_ORIGIN + SQ_SIZE, SQ_ORIGIN),
                [(0.0, "#ffffff"), (1.0, hue_color)],
            ),
        ),
    ]


def _sv_dark_shapes() -> list[dict[str, Any]]:
    return [
        c.rect(
            SQ_ORIGIN,
            SQ_ORIGIN,
            SQ_SIZE,
            SQ_SIZE,
            fill=c.linear_gradient(
                (SQ_ORIGIN, SQ_ORIGIN),
                (SQ_ORIGIN, SQ_ORIGIN + SQ_SIZE),
                [(0.0, "#00000000"), (1.0, "#000000ff")],
            ),
        ),
    ]


# -- Cursors -----------------------------------------------------------------


def _cursor_shapes(hue: float, saturation: float, value: float) -> list[dict[str, Any]]:
    angle = (hue - 90) * math.pi / 180
    ring_x = CX + MID_R * math.cos(angle)
    ring_y = CY + MID_R * math.sin(angle)

    sv_x = SQ_ORIGIN + saturation * SQ_SIZE
    sv_y = SQ_ORIGIN + (1.0 - value) * SQ_SIZE

    cursor_stroke = c.stroke("#333333", 2)

    return [
        c.circle(ring_x, ring_y, CURSOR_R, fill="#ffffff", stroke=cursor_stroke),
        c.circle(sv_x, sv_y, CURSOR_R, fill="#ffffff", stroke=cursor_stroke),
    ]


# -- Color conversion --------------------------------------------------------


def _hsv_to_hex(h: float, s: float, v: float) -> str:
    h = _fmod(h, 360.0)
    if h < 0:
        h += 360.0

    ch = v * s
    h_sector = h / 60.0
    x = ch * (1.0 - abs(_fmod(h_sector, 2.0) - 1.0))
    m = v - ch

    if h_sector < 1:
        r1, g1, b1 = ch, x, 0.0
    elif h_sector < 2:
        r1, g1, b1 = x, ch, 0.0
    elif h_sector < 3:
        r1, g1, b1 = 0.0, ch, x
    elif h_sector < 4:
        r1, g1, b1 = 0.0, x, ch
    elif h_sector < 5:
        r1, g1, b1 = x, 0.0, ch
    else:
        r1, g1, b1 = ch, 0.0, x

    r = round((r1 + m) * 255)
    g = round((g1 + m) * 255)
    b = round((b1 + m) * 255)

    return f"#{_hex_byte(r)}{_hex_byte(g)}{_hex_byte(b)}"


def _hex_byte(n: int) -> str:
    return f"{max(0, min(255, n)):02x}"


def _fmod(a: float, b: float) -> float:
    return a - b * math.floor(a / b)
