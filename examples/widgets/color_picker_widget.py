"""Canvas-based HSV color picker widget.

A hue ring surrounds a saturation/value square. Drag the ring to
select a hue; drag the square to adjust saturation and value.
Keyboard accessible: Tab to focus cursors, arrow keys to adjust.

Usage::

    ColorPickerWidget.build("picker")

Events:

- ``:change`` with ``{"hue": h, "saturation": s, "value": v}``
"""

from __future__ import annotations

import math
from typing import Any

from plushie import canvas as c
from plushie import ui
from plushie.canvas_widget import CanvasWidgetDef, EventAction, EventActionResult
from plushie.events import (
    CanvasElementKeyPress,
    CanvasMove,
    CanvasPress,
    CanvasRelease,
)

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

FINE_STEP = 1
COARSE_STEP = 15
SV_FINE_STEP = 0.01
SV_COARSE_STEP = 0.1


class ColorPickerWidget(CanvasWidgetDef):
    """Canvas widget that renders an HSV color picker with keyboard support."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"hue": 0.0, "saturation": 1.0, "value": 1.0, "drag": "none"}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        match event:
            case CanvasPress(x=x, y=y, button="left"):
                dx = x - CX
                dy = y - CY
                dist = math.sqrt(dx * dx + dy * dy)

                if INNER_R <= dist <= OUTER_R:
                    new_state = {
                        **state,
                        "drag": "ring",
                        "hue": _hue_from_point(dx, dy),
                    }
                    return EventAction.emit(
                        "change", _hsv_data(new_state), state=new_state
                    )
                elif _in_square(x, y):
                    new_state = _apply_sv({**state, "drag": "square"}, x, y)
                    return EventAction.emit(
                        "change", _hsv_data(new_state), state=new_state
                    )
                else:
                    return EventAction.consumed()

            case CanvasMove(x=x, y=y):
                if state["drag"] == "ring":
                    new_state = {**state, "hue": _hue_from_point(x - CX, y - CY)}
                    return EventAction.emit(
                        "change", _hsv_data(new_state), state=new_state
                    )
                elif state["drag"] == "square":
                    new_state = _apply_sv(state, x, y)
                    return EventAction.emit(
                        "change", _hsv_data(new_state), state=new_state
                    )
                else:
                    return EventAction.consumed()

            case CanvasRelease():
                return EventAction.update_state({**state, "drag": "none"})

            case CanvasElementKeyPress(element_id=eid, key=key, modifiers=mods):
                shift = bool(mods.get("shift", False))
                return _handle_key(eid, key, shift, state)

            case _:
                return EventAction.consumed()

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        hue = state["hue"]
        saturation = state["saturation"]
        value = state["value"]

        return ui.canvas(
            widget_id,
            width=CANVAS_SIZE,
            height=CANVAS_SIZE,
            on_press=True,
            on_release=True,
            on_move=True,
            arrow_mode="none",
            alt="HSV color picker",
            description="Drag the ring to select a hue, drag the square to adjust saturation and value. Tab to focus cursors, use arrow keys to adjust.",
            layers=dict(
                [
                    c.layer("a_ring", *_ring_shapes()),
                    c.layer("b_sv_hue", *_sv_hue_shapes(hue)),
                    c.layer("c_sv_dark", *_sv_dark_shapes()),
                    c.layer("d_cursors", *_cursor_groups(hue, saturation, value)),
                ]
            ),
        )


# -- Keyboard ----------------------------------------------------------------


def _handle_key(
    element_id: str, key: str, shift: bool, state: dict[str, Any]
) -> EventActionResult:
    if element_id == "hue-cursor":
        return _handle_hue_key(key, shift, state)
    elif element_id == "sv-cursor":
        return _handle_sv_key(key, shift, state)
    return EventAction.consumed()


def _handle_hue_key(key: str, shift: bool, state: dict[str, Any]) -> EventActionResult:
    hue = state["hue"]
    step = COARSE_STEP if shift else FINE_STEP

    if key in ("ArrowRight", "ArrowUp"):
        new_hue = _fmod(hue + step, 360.0)
    elif key in ("ArrowLeft", "ArrowDown"):
        new_hue = _fmod(hue - step + 360.0, 360.0)
    elif key == "PageUp":
        new_hue = _fmod(hue + COARSE_STEP, 360.0)
    elif key == "PageDown":
        new_hue = _fmod(hue - COARSE_STEP + 360.0, 360.0)
    elif key == "Home":
        new_hue = 0.0
    elif key == "End":
        new_hue = 359.0
    else:
        new_hue = hue

    if new_hue != hue:
        new_state = {**state, "hue": new_hue}
        return EventAction.emit("change", _hsv_data(new_state), state=new_state)
    return EventAction.consumed()


def _handle_sv_key(key: str, shift: bool, state: dict[str, Any]) -> EventActionResult:
    s = state["saturation"]
    v = state["value"]
    step = SV_COARSE_STEP if shift else SV_FINE_STEP

    if key == "ArrowRight":
        s = _clamp(s + step, 0.0, 1.0)
    elif key == "ArrowLeft":
        s = _clamp(s - step, 0.0, 1.0)
    elif key == "ArrowUp":
        v = _clamp(v + step, 0.0, 1.0)
    elif key == "ArrowDown":
        v = _clamp(v - step, 0.0, 1.0)
    elif key == "PageUp":
        v = _clamp(v + SV_COARSE_STEP, 0.0, 1.0)
    elif key == "PageDown":
        v = _clamp(v - SV_COARSE_STEP, 0.0, 1.0)
    elif key == "Home":
        v = 1.0
    elif key == "End":
        v = 0.0

    if s != state["saturation"] or v != state["value"]:
        new_state = {**state, "saturation": s, "value": v}
        return EventAction.emit("change", _hsv_data(new_state), state=new_state)
    return EventAction.consumed()


# -- Cursors -----------------------------------------------------------------


def _cursor_groups(hue: float, saturation: float, value: float) -> list[dict[str, Any]]:
    angle = (hue - 90) * math.pi / 180
    ring_x = CX + MID_R * math.cos(angle)
    ring_y = CY + MID_R * math.sin(angle)

    sv_x = SQ_ORIGIN + saturation * SQ_SIZE
    sv_y = SQ_ORIGIN + (1.0 - value) * SQ_SIZE

    cursor_stroke = c.stroke("#333333", 2)
    focus_stroke = {"stroke": {"color": "#3b82f6", "width": 3}}

    return [
        c.group(
            c.circle(0, 0, CURSOR_R, fill="#ffffff", stroke=cursor_stroke),
            "hue-cursor",
            x=ring_x,
            y=ring_y,
            focusable=True,
            on_click=True,
            focus_style=focus_stroke,
            show_focus_ring=False,
            a11y={
                "role": "slider",
                "label": "Hue",
                "value": f"{round(hue)} degrees",
                "orientation": "horizontal",
            },
        ),
        c.group(
            c.circle(0, 0, CURSOR_R, fill="#ffffff", stroke=cursor_stroke),
            "sv-cursor",
            x=sv_x,
            y=sv_y,
            focusable=True,
            on_click=True,
            focus_style=focus_stroke,
            show_focus_ring=False,
            a11y={
                "role": "slider",
                "label": "Saturation and brightness",
                "value": f"{round(saturation * 100)}% saturation, {round(value * 100)}% brightness",
                "orientation": "horizontal",
            },
        ),
    ]


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


# -- Hit testing -------------------------------------------------------------


def _in_square(x: float, y: float) -> bool:
    return (
        SQ_ORIGIN <= x <= SQ_ORIGIN + SQ_SIZE and SQ_ORIGIN <= y <= SQ_ORIGIN + SQ_SIZE
    )


# -- Coordinate math ---------------------------------------------------------


def _hue_from_point(dx: float, dy: float) -> float:
    angle = math.atan2(dy, dx)
    hue = angle + math.pi / 2
    if hue < 0:
        hue += 2 * math.pi
    return hue * 180.0 / math.pi


def _apply_sv(state: dict[str, Any], x: float, y: float) -> dict[str, Any]:
    s = _clamp((x - SQ_ORIGIN) / SQ_SIZE, 0.0, 1.0)
    v = _clamp(1.0 - (y - SQ_ORIGIN) / SQ_SIZE, 0.0, 1.0)
    return {**state, "saturation": s, "value": v}


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _hsv_data(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "hue": state["hue"],
        "saturation": state["saturation"],
        "value": state["value"],
    }


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
