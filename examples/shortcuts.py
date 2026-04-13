"""Shortcuts: keyboard event logging with a scrollable log.

Demonstrates:

- ``Subscription.on_key_press("keys")`` for global keyboard events
- ``KeyPress`` event handling with modifier inspection
- ``scrollable`` for overflow content with dynamic list items
- Capped log buffer (50 entries)

Run::

    python -m plushie run examples.shortcuts:Shortcuts
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plushie
from plushie import ui
from plushie.events import KeyPress
from plushie.subscriptions import Subscription

MAX_LOG_ENTRIES = 50


@dataclass(frozen=True, slots=True)
class Model:
    """Shortcuts model: tracks key event log and count."""

    log: tuple[str, ...] = ()
    count: int = 0


def _format_key_event(event: KeyPress, n: int) -> str:
    mods = _format_modifiers(event)
    key = repr(event.key)
    prefix = f"{mods}+" if mods else ""
    return f"#{n}: {prefix}{key}"


def _format_modifiers(event: KeyPress) -> str:
    parts: list[str] = []
    if event.modifiers.ctrl:
        parts.append("Ctrl")
    if event.modifiers.alt:
        parts.append("Alt")
    if event.modifiers.shift:
        parts.append("Shift")
    if event.modifiers.logo:
        parts.append("Super")
    return "+".join(parts)


class Shortcuts(plushie.App[Model]):
    """Logs keyboard events to a scrollable list."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            case KeyPress():
                entry = _format_key_event(event, model.count + 1)
                new_log = (entry, *model.log)[:MAX_LOG_ENTRIES]
                return replace(model, log=new_log, count=model.count + 1)
            case _:
                return model

    def subscribe(self, model: Model) -> list[Subscription]:
        return [Subscription.on_key_press("keys")]

    def view(self, model: Model) -> dict[str, Any]:
        return ui.window(
            "main",
            ui.column(
                ui.text("header", "Press any key", size=20),
                ui.text(
                    "count",
                    f"{model.count} key events captured",
                    size=12,
                    color="#888888",
                ),
                ui.rule(),
                ui.scrollable(
                    "log",
                    ui.column(
                        *(
                            ui.text(f"log_{i}", entry, size=13)
                            for i, entry in enumerate(model.log)
                        ),
                        spacing=2,
                        width="fill",
                    ),
                    height="fill",
                ),
                padding=16,
                spacing=12,
                width="fill",
            ),
            title="Keyboard Shortcuts",
        )


if __name__ == "__main__":
    plushie.run(Shortcuts)
