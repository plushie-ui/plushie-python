"""Counter: the canonical plushie example.

Demonstrates the core Elm architecture: a frozen dataclass model, event
matching on widget clicks, and a view built from ``ui.window``,
``ui.column``, ``ui.row``, ``ui.text``, and ``ui.button``.

Run::

    python -m plushie run examples.counter:Counter
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click


@dataclass(frozen=True, slots=True)
class Model:
    """Counter model: just an integer count."""

    count: int = 0


class Counter(plushie.App[Model]):
    """A simple increment/decrement counter."""

    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case Click(id="dec"):
                return replace(model, count=model.count - 1)
            case _:
                return model

    def view(self, model: Model) -> dict:
        return ui.window(
            "main",
            ui.column(
                ui.text("count", f"Count: {model.count}"),
                ui.row(
                    ui.button("inc", "+"),
                    ui.button("dec", "-"),
                    spacing=8,
                ),
                padding=16,
                spacing=8,
            ),
            title="Counter",
        )


if __name__ == "__main__":
    plushie.run(Counter)
