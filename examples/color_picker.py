"""Color picker -- HSV color picker using a custom canvas widget.

A hue ring surrounds a saturation/value square. Drag the ring to select
a hue; drag the square to adjust saturation and value. The selected color
is displayed as a swatch and hex string below the canvas.

Demonstrates:

- Canvas events (``CanvasPress``, ``CanvasMove``, ``CanvasRelease``)
- Drag interaction with coordinate math
- HSV color conversion
- Reusable canvas widget module (``widgets/color_picker_widget.py``)

Run::

    python -m plushie run examples.color_picker:ColorPicker
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Literal

import plushie
from examples.widgets.color_picker_widget import (
    CX,
    CY,
    INNER_R,
    OUTER_R,
    SQ_ORIGIN,
    SQ_SIZE,
)
from examples.widgets.color_picker_widget import render as picker_render
from plushie import ui
from plushie.events import CanvasMove, CanvasPress, CanvasRelease

type DragTarget = Literal["ring", "square", "none"]


@dataclass(frozen=True, slots=True)
class Model:
    """Color picker model -- tracks HSV values and drag state."""

    hue: float = 0.0
    saturation: float = 1.0
    value: float = 1.0
    drag: DragTarget = "none"


def _hue_from_point(dx: float, dy: float) -> float:
    angle = math.atan2(dy, dx)
    hue = angle + math.pi / 2
    if hue < 0:
        hue += 2 * math.pi
    return hue * 180.0 / math.pi


def _in_square(x: float, y: float) -> bool:
    return (
        SQ_ORIGIN <= x <= SQ_ORIGIN + SQ_SIZE and SQ_ORIGIN <= y <= SQ_ORIGIN + SQ_SIZE
    )


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _apply_sv(model: Model, x: float, y: float) -> Model:
    s = _clamp((x - SQ_ORIGIN) / SQ_SIZE, 0.0, 1.0)
    v = _clamp(1.0 - (y - SQ_ORIGIN) / SQ_SIZE, 0.0, 1.0)
    return replace(model, saturation=s, value=v)


def _hsv_to_hex(h: float, s: float, v: float) -> str:
    h = h % 360.0
    if h < 0:
        h += 360.0

    c = v * s
    h_sector = h / 60.0
    x = c * (1.0 - abs(h_sector % 2.0 - 1.0))
    m = v - c

    if h_sector < 1:
        r1, g1, b1 = c, x, 0.0
    elif h_sector < 2:
        r1, g1, b1 = x, c, 0.0
    elif h_sector < 3:
        r1, g1, b1 = 0.0, c, x
    elif h_sector < 4:
        r1, g1, b1 = 0.0, x, c
    elif h_sector < 5:
        r1, g1, b1 = x, 0.0, c
    else:
        r1, g1, b1 = c, 0.0, x

    r = round((r1 + m) * 255)
    g = round((g1 + m) * 255)
    b = round((b1 + m) * 255)

    return (
        f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"
    )


class ColorPicker(plushie.App[Model]):
    """HSV color picker with drag interaction on a canvas widget."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            case CanvasPress(id="picker", x=x, y=y, button="left"):
                dx = x - CX
                dy = y - CY
                dist = math.sqrt(dx * dx + dy * dy)

                if INNER_R <= dist <= OUTER_R:
                    return replace(model, drag="ring", hue=_hue_from_point(dx, dy))
                elif _in_square(x, y):
                    return _apply_sv(replace(model, drag="square"), x, y)
                else:
                    return model

            case CanvasMove(id="picker", x=x, y=y):
                match model.drag:
                    case "ring":
                        return replace(model, hue=_hue_from_point(x - CX, y - CY))
                    case "square":
                        return _apply_sv(model, x, y)
                    case _:
                        return model

            case CanvasRelease(id="picker"):
                return replace(model, drag="none")

            case _:
                return model

    def view(self, model: Model) -> dict[str, Any]:
        hex_color = _hsv_to_hex(model.hue, model.saturation, model.value)
        h_int = round(model.hue)
        s_pct = round(model.saturation * 100)
        v_pct = round(model.value * 100)
        hsv_label = f"H: {h_int}  S: {s_pct}%  V: {v_pct}%"

        return ui.window(
            "color_picker",
            ui.column(
                picker_render("picker", model.hue, model.saturation, model.value),
                ui.row(
                    ui.container(
                        "swatch",
                        width=48,
                        height=48,
                        background=hex_color,
                        border={"width": 1, "color": "#cccccc", "rounded": 4},
                    ),
                    ui.column(
                        ui.text("hex_display", hex_color, size=18),
                        ui.text("hsv_display", hsv_label),
                        spacing=4,
                    ),
                    spacing=16,
                    align_y="center",
                ),
                padding=20,
                spacing=16,
                align_x="center",
            ),
            title="Color Picker",
        )


if __name__ == "__main__":
    plushie.run(ColorPicker)
