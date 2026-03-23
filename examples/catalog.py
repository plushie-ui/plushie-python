"""Catalog -- comprehensive widget reference exercising every widget type.

Organized as a column layout with tab-like navigation across four sections:
layout, input, display, and composite. Each section demonstrates a category
of widgets with realistic props and interactive state.

Demonstrated widgets:

- **Layout:** column, row, container, scrollable, stack, grid, pin, float,
  responsive, keyed_column, themer, space
- **Input:** button, text_input, checkbox, toggler, radio, slider,
  vertical_slider, pick_list, combo_box, text_editor
- **Display:** text, rule, progress_bar, tooltip, image, svg, markdown,
  rich_text, canvas
- **Interactive/Composite:** mouse_area, sensor, pane_grid, table,
  simulated tabs, modal, collapsible panel

Run::

    python -m plushie run examples.catalog:Catalog
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.events import (
    Click,
    Input,
    MouseAreaEnter,
    MouseAreaExit,
    Select,
    SensorResize,
    Slide,
    Toggle,
)


@dataclass(frozen=True, slots=True)
class Model:
    """Catalog model -- tracks all interactive widget state."""

    active_tab: str = "layout"
    demo_tabs_active: str = "tab_one"
    text_value: str = ""
    checkbox_checked: bool = False
    toggler_on: bool = False
    slider_value: float = 50
    vslider_value: float = 50
    radio_selected: str = "a"
    pick_list_selected: str | None = None
    combo_value: str | None = None
    editor_content: str = "Edit me..."
    progress: float = 65
    panel_collapsed: bool = False
    modal_visible: bool = False
    click_count: int = 0
    mouse_area_status: str = "idle"
    sensor_status: str = "waiting"


class Catalog(plushie.App[Model]):
    """Comprehensive widget catalog across four tabbed sections."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            # Tab switching
            case Click(id="tab_layout"):
                return replace(model, active_tab="layout")
            case Click(id="tab_input"):
                return replace(model, active_tab="input")
            case Click(id="tab_display"):
                return replace(model, active_tab="display")
            case Click(id="tab_composite"):
                return replace(model, active_tab="composite")

            # Input widgets
            case Input(id="demo_input", value=v):
                return replace(model, text_value=v)
            case Toggle(id="demo_check", value=v):
                return replace(model, checkbox_checked=v)
            case Toggle(id="demo_toggler", value=v):
                return replace(model, toggler_on=v)
            case Slide(id="demo_slider", value=v):
                return replace(model, slider_value=v)
            case Slide(id="demo_vslider", value=v):
                return replace(model, vslider_value=v)
            case Select(id="demo_radio", value=v):
                return replace(model, radio_selected=v)
            case Select(id="demo_pick", value=v):
                return replace(model, pick_list_selected=v)
            case Select(id="demo_combo", value=v):
                return replace(model, combo_value=v)
            case Input(id="demo_editor", value=v):
                return replace(model, editor_content=v)

            # Composite section
            case Click(id="tab_one"):
                return replace(model, demo_tabs_active="tab_one")
            case Click(id="tab_two"):
                return replace(model, demo_tabs_active="tab_two")
            case Click(id="show_modal"):
                return replace(model, modal_visible=True)
            case Click(id="hide_modal"):
                return replace(model, modal_visible=False)
            case Click(id="demo_panel"):
                return replace(model, panel_collapsed=not model.panel_collapsed)
            case Click(id="counter_btn"):
                return replace(model, click_count=model.click_count + 1)
            case Click(id="inc_progress"):
                return replace(model, progress=min(model.progress + 5, 100))

            # Interactive widgets
            case MouseAreaEnter(id="demo_mouse_area"):
                return replace(model, mouse_area_status="hovering")
            case MouseAreaExit(id="demo_mouse_area"):
                return replace(model, mouse_area_status="idle")
            case SensorResize(id="demo_sensor"):
                return replace(model, sensor_status="activated")

            case _:
                return model

    def view(self, model: Model) -> dict[str, Any]:
        tab_content: dict[str, Any]
        match model.active_tab:
            case "layout":
                tab_content = _layout_tab()
            case "input":
                tab_content = _input_tab(model)
            case "display":
                tab_content = _display_tab(model)
            case "composite":
                tab_content = _composite_tab(model)
            case _:
                tab_content = _layout_tab()

        return ui.window(
            "catalog",
            ui.column(
                ui.text("catalog_title", "Plushie Widget Catalog", size=24),
                ui.rule(),
                ui.row(
                    ui.button("tab_layout", "Layout"),
                    ui.button("tab_input", "Input"),
                    ui.button("tab_display", "Display"),
                    ui.button("tab_composite", "Composite"),
                    spacing=8,
                ),
                ui.rule(),
                tab_content,
                spacing=12,
                padding=16,
            ),
            title="Widget Catalog",
        )


# -- Tab views ---------------------------------------------------------------


def _layout_tab() -> dict[str, Any]:
    return ui.column(
        ui.text("layout_heading", "Layout Widgets", size=18),
        # Row
        ui.row(
            ui.text("Row child 1"),
            ui.text("Row child 2"),
            ui.text("Row child 3"),
            spacing=8,
        ),
        # Nested column
        ui.column(
            ui.text("Nested column child 1"),
            ui.text("Nested column child 2"),
            spacing=4,
        ),
        # Container with padding
        ui.container(
            "demo_container",
            ui.text("Inside a container"),
            padding=12,
        ),
        # Scrollable
        ui.scrollable(
            "demo_scrollable",
            ui.column(
                ui.text("Scrollable item 1"),
                ui.text("Scrollable item 2"),
                ui.text("Scrollable item 3"),
                ui.text("Scrollable item 4"),
                ui.text("Scrollable item 5"),
                spacing=4,
            ),
        ),
        # Stack
        ui.stack(
            ui.text("Stack layer 1 (back)"),
            ui.text("Stack layer 2 (front)"),
        ),
        # Grid layout
        ui.grid(
            ui.text("Grid 1"),
            ui.text("Grid 2"),
            ui.text("Grid 3"),
            ui.text("Grid 4"),
            ui.text("Grid 5"),
            ui.text("Grid 6"),
            columns=3,
            spacing=4,
        ),
        # Pin
        ui.pin(
            "demo_pin",
            ui.text("Pinned content"),
            x=0,
            y=0,
        ),
        # Float
        ui.floating(
            "demo_float",
            ui.text("Floating element"),
            translate_x=100,
            translate_y=10,
        ),
        # Responsive
        ui.responsive(
            ui.column(ui.text("Responsive content adapts to width")),
        ),
        # Keyed column
        ui.keyed_column(
            ui.text("key_a", "Keyed item A"),
            ui.text("key_b", "Keyed item B"),
            ui.text("key_c", "Keyed item C"),
            spacing=4,
        ),
        # Themer
        ui.themer(
            "demo_themer",
            ui.container(
                "themed_box",
                ui.column(
                    ui.text("Themed section with custom palette"),
                    ui.button("themed_btn", "Themed Button"),
                    spacing=4,
                ),
                padding=12,
            ),
            theme={"background": "#1a1a2e", "text": "#e0e0e0", "primary": "#0f3460"},
        ),
        # Space
        ui.space(height=16),
        spacing=8,
    )


def _input_tab(model: Model) -> dict[str, Any]:
    return ui.column(
        ui.text("input_heading", "Input Widgets", size=18),
        # Text input
        ui.text_input("demo_input", model.text_value, placeholder="Type here..."),
        # Button
        ui.button("demo_button", "A Button"),
        # Checkbox
        ui.checkbox("demo_check", model.checkbox_checked, label="Check me"),
        # Toggler
        ui.toggler("demo_toggler", model.toggler_on, label="Toggle me"),
        # Radio group
        ui.row(
            ui.radio(
                "demo_radio_a",
                "a",
                model.radio_selected,
                label="Option A",
                group="demo_radio",
            ),
            ui.radio(
                "demo_radio_b",
                "b",
                model.radio_selected,
                label="Option B",
                group="demo_radio",
            ),
            ui.radio(
                "demo_radio_c",
                "c",
                model.radio_selected,
                label="Option C",
                group="demo_radio",
            ),
            spacing=8,
        ),
        # Slider
        ui.slider("demo_slider", (0, 100), model.slider_value, step=1),
        ui.text(f"Slider: {model.slider_value}"),
        # Vertical slider
        ui.vertical_slider("demo_vslider", (0, 100), model.vslider_value, step=1),
        # Pick list
        ui.pick_list(
            "demo_pick",
            ["Small", "Medium", "Large"],
            model.pick_list_selected,
            placeholder="Pick a size...",
        ),
        # Combo box
        ui.combo_box(
            "demo_combo",
            ["Elixir", "Rust", "Go"],
            model.combo_value or "",
            placeholder="Choose a language...",
        ),
        # Text editor
        ui.text_editor("demo_editor", model.editor_content, height=100),
        spacing=8,
    )


def _display_tab(model: Model) -> dict[str, Any]:
    return ui.column(
        ui.text("display_heading", "Display Widgets", size=18),
        # Plain text
        ui.text("Plain text label"),
        # Rule
        ui.rule(),
        # Progress bar with interactive control
        ui.row(
            ui.progress_bar((0, 100), model.progress),
            ui.button("inc_progress", "+5%"),
            spacing=8,
        ),
        # Tooltip wrapping a button
        ui.tooltip(
            "demo_tooltip",
            "This is a tooltip",
            ui.button("tooltip_target", "Hover me for tooltip"),
            position="top",
        ),
        # Image
        ui.image("demo_image", "/assets/placeholder.png", width=120, height=80),
        # SVG
        ui.svg("demo_svg", "/assets/icon.svg", width=24, height=24),
        # Markdown
        ui.markdown(
            "demo_markdown",
            "## Markdown\n\nSome **bold** and *italic* text.\n\n- Item one\n- Item two",
        ),
        # Rich text with styled spans
        ui.rich_text(
            "demo_rich_text",
            spans=[
                {"text": "Bold text ", "weight": "bold", "size": 16},
                {"text": "italic text ", "style": "italic"},
                {"text": "normal text "},
                {"text": "colored text", "color": "#e74c3c"},
            ],
        ),
        # Canvas with geometric shapes
        ui.canvas(
            "demo_canvas",
            width=200,
            height=150,
            layers={
                "default": [
                    {
                        "type": "rect",
                        "x": 10,
                        "y": 10,
                        "w": 80,
                        "h": 60,
                        "fill": "#3498db",
                    },
                    {"type": "circle", "x": 150, "y": 75, "r": 40, "fill": "#e74c3c"},
                    {
                        "type": "line",
                        "x1": 10,
                        "y1": 130,
                        "x2": 190,
                        "y2": 130,
                        "stroke": {"color": "#2ecc71", "width": 2},
                    },
                ],
            },
        ),
        spacing=8,
    )


def _composite_tab(model: Model) -> dict[str, Any]:
    # Modal (conditionally shown)
    modal_children: list[dict[str, Any]] = [ui.button("show_modal", "Show Modal")]
    if model.modal_visible:
        modal_children.append(
            ui.container(
                "demo_modal",
                ui.column(
                    ui.text("Modal Content"),
                    ui.button("hide_modal", "Close"),
                    spacing=8,
                ),
                padding=16,
            )
        )

    # Collapsible panel
    panel_label = "Expand Panel" if model.panel_collapsed else "Collapse Panel"
    panel_children: list[dict[str, Any]] = [ui.button("demo_panel", panel_label)]
    if not model.panel_collapsed:
        panel_children.append(
            ui.container(
                "panel_content",
                ui.text("Panel content that can be collapsed"),
                padding=8,
            )
        )

    # Tab content
    tab_text = (
        "Tab one content" if model.demo_tabs_active == "tab_one" else "Tab two content"
    )

    return ui.column(
        ui.text("composite_heading", "Interactive & Composite Widgets", size=18),
        # Mouse area
        ui.mouse_area(
            "demo_mouse_area",
            ui.container(
                "mouse_area_box",
                ui.text(f"Mouse area: {model.mouse_area_status}"),
                padding=12,
            ),
            on_enter=True,
            on_exit=True,
        ),
        # Sensor
        ui.sensor(
            "demo_sensor",
            ui.container(
                "sensor_box",
                ui.text(f"Sensor: {model.sensor_status}"),
                padding=12,
            ),
        ),
        # Simulated tabs
        ui.container(
            "demo_tabs",
            ui.column(
                ui.row(
                    ui.button("tab_one", "Tab One"),
                    ui.button("tab_two", "Tab Two"),
                    spacing=4,
                ),
                ui.text(tab_text),
                spacing=4,
            ),
        ),
        # Modal
        *modal_children,
        # Collapsible panel
        *panel_children,
        # Counter
        ui.row(
            ui.button("counter_btn", "Click me"),
            ui.text(f"Clicked {model.click_count} times"),
            spacing=8,
        ),
        # PaneGrid
        ui.pane_grid(
            "demo_panes",
            ui.container(
                "pane_left",
                ui.column(
                    ui.text("Left pane"),
                    ui.text("Navigation or file tree"),
                ),
                padding=8,
            ),
            ui.container(
                "pane_right",
                ui.column(
                    ui.text("Right pane"),
                    ui.text("Main editor area"),
                ),
                padding=8,
            ),
            spacing=2,
        ),
        # Table
        ui.table(
            "demo_table",
            columns=[
                {"key": "name", "label": "Name"},
                {"key": "lang", "label": "Language"},
                {"key": "stars", "label": "Stars"},
            ],
            rows=[
                {"name": "Phoenix", "lang": "Elixir", "stars": "20k"},
                {"name": "Iced", "lang": "Rust", "stars": "24k"},
                {"name": "React", "lang": "JavaScript", "stars": "220k"},
            ],
        ),
        spacing=8,
    )


if __name__ == "__main__":
    plushie.run(Catalog)
