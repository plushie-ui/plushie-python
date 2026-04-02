"""Canvas-based star rating widget.

Renders 5 stars as a radio group. Interactive by default (click to rate,
hover to preview, Tab/arrow keys to navigate, Enter/Space to select).
Pass ``readonly=True`` for a display-only version.

Usage::

    StarRating.build("my-rating", props={"rating": 3, "theme_progress": 0.5})
    StarRating.build("review-stars", props={"rating": 4, "readonly": True, "scale": 0.5})

Events:

- ``:select`` with ``{"value": n}`` when the user clicks a star
"""

from __future__ import annotations

import math
from typing import Any

from plushie import canvas as c
from plushie import ui
from plushie.canvas_widget import CanvasWidgetDef, EventAction, EventActionResult
from plushie.events import CanvasElementClick, CanvasElementEnter, CanvasElementLeave

STAR_COUNT = 5


class StarRating(CanvasWidgetDef):
    """Canvas widget that renders an interactive 5-star rating."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"hover": None}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        match event:
            case CanvasElementClick(element_id=eid) if eid.startswith("star-"):
                n = int(eid.removeprefix("star-"))
                return EventAction.emit("select", n + 1)

            case CanvasElementEnter(element_id=eid) if eid.startswith("star-"):
                n = int(eid.removeprefix("star-"))
                return EventAction.update_state({"hover": n + 1})

            case CanvasElementLeave():
                return EventAction.update_state({"hover": None})

            case _:
                return EventAction.consumed()

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        rating = props.get("rating", 0)
        readonly = props.get("readonly", False)
        scale = props.get("scale", 1.0)
        theme_progress = props.get("theme_progress", 0.0)

        outer_r = 13 * scale
        inner_r = 5 * scale
        size = round(30 * scale)
        gap = round(2 * scale)
        hover = state.get("hover")
        display = hover if hover is not None else rating
        width = STAR_COUNT * size + (STAR_COUNT - 1) * gap

        commands = _star_commands(outer_r, inner_r)

        if readonly:
            stars: list[dict[str, Any]] = []
            for i in range(STAR_COUNT):
                cx = i * (size + gap) + size / 2
                cy = size / 2
                star_path = c.path(
                    commands,
                    fill=_star_color(i < rating, False, theme_progress),
                )
                stars.append(c.group(star_path, x=cx, y=cy))

            return ui.canvas(
                widget_id,
                width=width,
                height=size,
                alt=f"{rating} out of {STAR_COUNT} stars",
                layers=dict([c.layer("stars", *stars)]),
            )
        else:
            stars_interactive: list[dict[str, Any]] = []
            for i in range(STAR_COUNT):
                cx = i * (size + gap) + size / 2
                cy = size / 2
                filled = i < display
                preview = hover is not None and i < hover and i >= rating

                star_path = c.path(
                    commands,
                    fill=_star_color(filled, preview, theme_progress),
                )

                interactive_star = c.group(
                    star_path,
                    f"star-{i}",
                    x=cx,
                    y=cy,
                    on_click=True,
                    on_hover=True,
                    cursor="pointer",
                    focus_style={"stroke": {"color": "#3b82f6", "width": 2 * scale}},
                    show_focus_ring=False,
                    a11y={
                        "role": "radio",
                        "label": f"{i + 1} star{'s' if i > 0 else ''}",
                        "selected": rating >= i + 1,
                        "position_in_set": i + 1,
                        "size_of_set": STAR_COUNT,
                    },
                )
                stars_interactive.append(interactive_star)

            return ui.canvas(
                widget_id,
                width=width,
                height=size,
                alt="Star rating",
                role="radiogroup",
                layers=dict([c.layer("stars", *stars_interactive)]),
            )


def _star_commands(outer_r: float, inner_r: float) -> list[Any]:
    points: list[tuple[float, float]] = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        points.append((r * math.cos(angle), r * math.sin(angle)))

    fx, fy = points[0]
    cmds: list[Any] = [c.move_to(fx, fy)]
    for x, y in points[1:]:
        cmds.append(c.line_to(x, y))
    cmds.append(c.close())
    return cmds


def _star_color(filled: bool, preview: bool, progress: float) -> str:
    if preview:
        return _fade((255, 200, 50), (200, 160, 80), progress)
    if filled:
        return _fade((255, 180, 0), (255, 200, 50), progress)
    return _fade((224, 224, 224), (60, 60, 80), progress)


def _fade(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> str:
    r = round(c1[0] + (c2[0] - c1[0]) * t)
    g = round(c1[1] + (c2[1] - c1[1]) * t)
    b = round(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"
