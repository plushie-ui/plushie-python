"""HSV color picker using a canvas_widget.

The color picker widget handles all interaction internally (mouse drag,
keyboard adjustment, focus tracking). The app receives ``:change`` events
with the current HSV values.

Run::

    python -m plushie run examples.color_picker:ColorPicker
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from examples.widgets.color_picker_widget import ColorPickerWidget
from plushie import ui
from plushie.events import WidgetEvent


@dataclass(frozen=True, slots=True)
class Model:
    """Color picker model -- tracks HSV values."""

    hue: float = 0.0
    saturation: float = 1.0
    value: float = 1.0
    drag: str = "none"


class ColorPicker(plushie.App[Model]):
    """HSV color picker with canvas_widget interaction."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            case WidgetEvent(kind="change", id="picker", data=data):
                return replace(
                    model,
                    hue=data["hue"],
                    saturation=data["saturation"],
                    value=data["value"],
                )
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
                ColorPickerWidget.build("picker"),
                ui.row(
                    ui.container(
                        "swatch",
                        width=48,
                        height=48,
                        background=hex_color,
                        border={"width": 1, "color": "#cccccc", "rounded": 4},
                        a11y={"role": "image", "label": f"Selected color: {hex_color}"},
                    ),
                    ui.column(
                        ui.text(
                            "hex_display",
                            hex_color,
                            size=18,
                            a11y={
                                "live": "polite",
                                "busy": model.hue == 0.0
                                and model.saturation == 1.0
                                and model.value == 1.0,
                            },
                        ),
                        ui.text("hsv_display", hsv_label, a11y={"live": "polite"}),
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


if __name__ == "__main__":
    plushie.run(ColorPicker)
