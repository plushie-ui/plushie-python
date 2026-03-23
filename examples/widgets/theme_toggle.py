"""Animated theme toggle with a face on the thumb.

A toggle switch where the thumb has a drawn face. Light mode shows a
smiley; dark mode shows the face rotated upside down. The face rotates
during the transition.

Usage::

    from examples.widgets.theme_toggle import ThemeToggle

    ThemeToggle.render("my-toggle", model.toggle_progress)

Events: ``CanvasElementClick`` with element_id ``"switch"``.
Drive ``progress`` from 0.0 (light) to 1.0 (dark) with a timer.
"""

from __future__ import annotations

import math
from typing import Any

from plushie import canvas as c
from plushie import ui

TRACK_W = 64
TRACK_H = 32
THUMB_R = 13


def render(id: str, progress: float) -> dict[str, Any]:
    """Render the theme toggle canvas widget."""
    eased = _smoothstep(progress)
    thumb_x = _lerp(TRACK_H / 2, TRACK_W - TRACK_H / 2, eased)
    track_color = _lerp_color((253, 230, 138), (91, 33, 182), eased)
    rotation = eased * math.pi
    face_color = "#665500" if progress < 0.5 else "#4c1d95"

    toggle_group = c.interactive(
        c.group(
            # Track
            c.rect(0, 0, TRACK_W, TRACK_H, fill=track_color, radius=TRACK_H / 2),
            # Thumb circle
            c.circle(thumb_x, TRACK_H / 2, THUMB_R, fill="#ffffff"),
            # Face drawn with transforms (rotates during transition)
            c.group(
                # Left eye
                c.circle(-3.5, -3, 2, fill=face_color),
                # Right eye
                c.circle(3.5, -3, 2, fill=face_color),
                # Mouth (smile drawn as a path)
                c.path(
                    _smile_path(),
                    stroke=c.stroke(face_color, 2),
                ),
                transforms=[c.translate(thumb_x, TRACK_H / 2), c.rotate(rotation)],
            ),
        ),
        "switch",
        on_click=True,
        cursor="pointer",
        hit_rect={"x": 0, "y": 0, "w": TRACK_W, "h": TRACK_H},
        a11y={"role": "switch", "label": "Dark humor"},
    )

    return ui.canvas(
        id,
        width=TRACK_W,
        height=TRACK_H,
        layers=dict([c.layer("toggle", toggle_group)]),
    )


def _smile_path() -> list[Any]:
    return [c.move_to(-5, 1), c.line_to(-3, 5), c.line_to(3, 5), c.line_to(5, 1)]


def _smoothstep(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3 - 2 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> str:
    r = round(_lerp(c1[0], c2[0], t))
    g = round(_lerp(c1[1], c2[1], t))
    b = round(_lerp(c1[2], c2[2], t))
    return f"#{_hex(r)}{_hex(g)}{_hex(b)}"


def _hex(n: int) -> str:
    return f"{max(0, min(255, n)):02x}"
