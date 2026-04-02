"""Animated theme toggle with a face on the thumb.

A toggle switch where the thumb has a drawn face. Light mode shows a
smiley; dark mode shows the face rotated upside down. The face rotates
during the transition. Animation is managed internally.

Usage::

    ThemeToggle.build("my-toggle")

Events: ``:toggle`` with ``{"value": bool}`` when the user clicks.
"""

from __future__ import annotations

import math
from typing import Any

from plushie import canvas as c
from plushie import ui
from plushie.canvas_widget import CanvasWidgetDef, EventAction, EventActionResult
from plushie.events import Click, TimerTick
from plushie.subscriptions import Subscription

TRACK_W = 64
TRACK_H = 32
THUMB_R = 13


class ThemeToggle(CanvasWidgetDef):
    """Canvas widget that renders an animated light/dark toggle."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"progress": 0.0, "target": 0.0}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        match event:
            case Click():
                new_target = 1.0 if state["target"] == 0.0 else 0.0
                new_state = {"progress": state["progress"], "target": new_target}
                return EventAction.emit("toggle", new_target >= 0.5, state=new_state)

            case TimerTick(tag="animate"):
                new_progress = _approach(state["progress"], state["target"], 0.06)
                return EventAction.update_state(
                    {"progress": new_progress, "target": state["target"]}
                )

            case _:
                return EventAction.consumed()

    def subscribe(
        self, props: dict[str, Any], state: dict[str, Any]
    ) -> list[Subscription]:
        if state["progress"] != state["target"]:
            return [Subscription.every(16, "animate")]
        return []

    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        progress = state["progress"]
        eased = _smoothstep(progress)
        thumb_x = _lerp(TRACK_H / 2, TRACK_W - TRACK_H / 2, eased)
        track_color = _lerp_color((253, 230, 138), (91, 33, 182), eased)
        rotation = eased * math.pi
        face_color = "#665500" if progress < 0.5 else "#4c1d95"

        ring_pad = 4

        toggle_group = c.interactive(
            c.group(
                # Track
                c.rect(0, 0, TRACK_W, TRACK_H, fill=track_color, radius=TRACK_H / 2),
                # Thumb circle
                c.circle(thumb_x, TRACK_H / 2, THUMB_R, fill="#ffffff"),
                # Face drawn with transforms (rotates during transition)
                c.group(
                    c.circle(-3.5, -3, 2, fill=face_color),
                    c.circle(3.5, -3, 2, fill=face_color),
                    c.path(_smile_path(), stroke=c.stroke(face_color, 2)),
                    transforms=[c.translate(thumb_x, TRACK_H / 2), c.rotate(rotation)],
                ),
                x=ring_pad,
                y=ring_pad,
            ),
            "switch",
            on_click=True,
            cursor="pointer",
            hit_rect={"x": 0, "y": 0, "w": TRACK_W, "h": TRACK_H},
            focus_ring_radius=TRACK_H / 2 + ring_pad,
            a11y={
                "role": "switch",
                "label": "Dark humor",
                "toggled": progress >= 0.5,
            },
        )

        return ui.canvas(
            widget_id,
            width=TRACK_W + ring_pad * 2,
            height=TRACK_H + ring_pad * 2,
            alt="Theme toggle",
            layers=dict([c.layer("toggle", toggle_group)]),
        )


def _smile_path() -> list[Any]:
    return [c.move_to(-5, 1), c.line_to(-3, 5), c.line_to(3, 5), c.line_to(5, 1)]


def _approach(current: float, target: float, step: float) -> float:
    if current < target:
        return min(current + step, target)
    if current > target:
        return max(current - step, target)
    return current


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
    return (
        f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"
    )
