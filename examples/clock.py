"""Clock: demonstrates subscriptions and timer events.

Features exercised:

- ``Subscription.every(1000, "tick")`` for a one-second timer
- ``TimerTick`` event handling to update displayed time
- Start/stop button to control the subscription
- Formatted time display

Run::

    python -m plushie run examples.clock:Clock
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click, TimerTick
from plushie.subscriptions import Subscription


@dataclass(frozen=True, slots=True)
class Model:
    """Clock model: tracks current time and running state."""

    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    running: bool = True


def _time_from_localtime() -> tuple[int, int, int]:
    """Return (hours, minutes, seconds) from the system clock."""
    t = time.localtime()
    return t.tm_hour, t.tm_min, t.tm_sec


class Clock(plushie.App[Model]):
    """A simple clock that ticks every second."""

    def init(self) -> Model:
        h, m, s = _time_from_localtime()
        return Model(hours=h, minutes=m, seconds=s)

    def update(self, model: Model, event: object) -> Model:
        match event:
            case TimerTick(tag="tick"):
                h, m, s = _time_from_localtime()
                return replace(model, hours=h, minutes=m, seconds=s)
            case Click(id="toggle"):
                return replace(model, running=not model.running)
            case _:
                return model

    def view(self, model: Model) -> dict:
        time_str = f"{model.hours:02d}:{model.minutes:02d}:{model.seconds:02d}"
        button_label = "Stop" if model.running else "Start"

        return ui.window(
            "main",
            ui.column(
                ui.text("time", time_str, size=48),
                ui.button("toggle", button_label),
                padding=16,
                spacing=8,
                align_x="center",
            ),
            title="Clock",
        )

    def subscribe(self, model: Model) -> list[Subscription]:
        if model.running:
            return [Subscription.every(1000, "tick")]
        return []


if __name__ == "__main__":
    plushie.run(Clock)
