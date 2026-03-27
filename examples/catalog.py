"""Widget catalog example.

Run::

    python -m plushie run examples.catalog:Catalog
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click, Input, Select, Slide, Toggle


@dataclass(frozen=True, slots=True)
class Model:
    """Catalog state."""

    active_tab: str = "layout"
    text_value: str = ""
    checkbox_checked: bool = False
    toggler_on: bool = False
    slider_value: int = 50
    radio_selected: str = "a"
    click_count: int = 0


class Catalog(plushie.App[Model]):
    """Simple widget catalog split into four tabs."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            case Click(id=tab_id) if tab_id.startswith("tab_"):
                return replace(model, active_tab=tab_id.removeprefix("tab_"))
            case Click(id="demo_action"):
                return replace(model, click_count=model.click_count + 1)
            case Input(id="demo_input", value=value):
                return replace(model, text_value=value)
            case Toggle(id="demo_check", value=value):
                return replace(model, checkbox_checked=value)
            case Toggle(id="demo_toggler", value=value):
                return replace(model, toggler_on=value)
            case Slide(id="demo_slider", value=value):
                return replace(model, slider_value=int(value))
            case Select(id="demo_radio", value=value):
                return replace(model, radio_selected=value)
            case _:
                return model

    def view(self, model: Model) -> dict:
        return ui.window(
            "catalog",
            ui.column(
                ui.text("catalog_title", "Plushie Widget Catalog", size=28),
                ui.row(
                    self._tab_button("layout", "Layout", model.active_tab),
                    self._tab_button("input", "Input", model.active_tab),
                    self._tab_button("display", "Display", model.active_tab),
                    self._tab_button("composite", "Composite", model.active_tab),
                    spacing=8,
                ),
                self._tab_content(model),
                spacing=16,
                padding=16,
            ),
            title="Plushie Widget Catalog",
            width=820,
            height=640,
        )

    def _tab_button(self, tab_id: str, label: str, active_tab: str) -> dict:
        active = tab_id == active_tab
        button_label = f"[{label}]" if active else label
        return ui.button(f"tab_{tab_id}", button_label)

    def _tab_content(self, model: Model) -> dict:
        match model.active_tab:
            case "layout":
                return ui.container(
                    "layout_tab",
                    ui.text("layout_copy", "Layout widgets and containers live here."),
                    padding=12,
                )
            case "input":
                return ui.column(
                    ui.text_input(
                        "demo_input",
                        model.text_value,
                        placeholder="Type here",
                    ),
                    ui.checkbox(
                        "demo_check",
                        model.checkbox_checked,
                        label="Enable checkbox",
                    ),
                    ui.toggler(
                        "demo_toggler",
                        model.toggler_on,
                        label="Enable toggler",
                    ),
                    ui.slider("demo_slider", (0, 100), float(model.slider_value)),
                    ui.pick_list(
                        "demo_radio",
                        ["a", "b"],
                        model.radio_selected,
                        placeholder="Pick an option",
                    ),
                    spacing=12,
                )
            case "display":
                return ui.column(
                    ui.text("display_copy", "Display widgets preview"),
                    ui.progress_bar(
                        "display_progress",
                        (0.0, 100.0),
                        float(model.slider_value),
                    ),
                    spacing=12,
                )
            case "composite":
                return ui.column(
                    ui.text("composite_copy", f"Clicks: {model.click_count}"),
                    ui.button("demo_action", "Increment"),
                    spacing=12,
                )
            case _:
                return ui.text("unknown_tab", f"Unknown tab: {model.active_tab}")


if __name__ == "__main__":
    plushie.run(Catalog)
