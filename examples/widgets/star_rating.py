"""Canvas-based star rating widget.

Renders 5 stars as a radio group. Interactive by default (click to rate,
hover to preview, Tab/arrow keys to navigate, Enter/Space to select).
Pass ``readonly=True`` for a display-only version.

Usage::

    from examples.widgets.star_rating import render as star_render

    # Interactive (full size)
    star_render("my-rating", model.rating,
        hover=model.hover_star, theme_progress=p)

    # Read-only (small, for review display)
    star_render("review-stars", 4, readonly=True, scale=0.5)

Events:

- ``CanvasElementClick`` with element_id ``"star-0"`` through ``"star-4"``
- ``CanvasElementEnter``/``CanvasElementLeave`` for hover
"""

from __future__ import annotations

import math
from typing import Any

from plushie import canvas as c
from plushie import ui


def render(
    id: str,
    rating: int,
    *,
    hover: int | None = None,
    theme_progress: float = 0.0,
    readonly: bool = False,
    scale: float = 1.0,
) -> dict[str, Any]:
    """Render a star rating canvas widget."""
    outer_r = 13 * scale
    inner_r = 5 * scale
    size = round(30 * scale)
    gap = round(2 * scale)
    display = hover if hover is not None else rating
    width = 5 * size + 4 * gap

    commands = _star_commands(outer_r, inner_r)

    if readonly:
        stars: list[dict[str, Any]] = []
        for i in range(5):
            cx = i * (size + gap) + size / 2
            cy = size / 2
            filled = i < rating
            star_path = c.path(
                commands,
                fill=_star_color(filled, False, theme_progress),
            )
            stars.append(c.group(star_path, x=cx, y=cy))

        return ui.canvas(
            id,
            width=width,
            height=size,
            alt=f"{rating} out of 5 stars",
            layers=dict([c.layer("stars", *stars)]),
        )
    else:
        stars_interactive: list[dict[str, Any]] = []
        for i in range(5):
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
                    "size_of_set": 5,
                },
            )
            stars_interactive.append(interactive_star)

        return ui.canvas(
            id,
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
    if filled and not preview:
        return "#f59e0b"
    if preview:
        return "#fcd34d"
    # Empty star -- interpolate between light and dark themes
    r = round(209 + (74 - 209) * progress)
    g = round(213 + (74 - 213) * progress)
    b = round(219 + (94 - 219) * progress)
    return f"#{_hex(r)}{_hex(g)}{_hex(b)}"


def _hex(n: int) -> str:
    return f"{max(0, min(255, n)):02x}"
