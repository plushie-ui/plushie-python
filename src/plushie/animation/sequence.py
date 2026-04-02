"""Renderer-side sequential animation chain.

Executes multiple transitions and springs one after another on the
same property. Each step's ``from_`` defaults to the previous step's
final value if not specified.

Usage::

    from plushie.animation import Sequence, Transition

    opacity=Sequence(
        steps=[
            Transition(to=1.0, duration=200, from_=0.0),
            Transition.loop(to=0.7, duration=800, from_=1.0, cycles=3),
            Transition(to=0.0, duration=300),
        ],
        on_complete="fade_cycle_done",
    )

Only the sequence-level ``on_complete`` fires; individual step
completion tags are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from plushie.animation.spring import Spring
    from plushie.animation.transition import Transition


@dataclass(frozen=True, slots=True)
class Sequence:
    """A sequential animation chain.

    Attributes:
        steps: Ordered list of Transition and/or Spring descriptors.
        on_complete: Event tag string sent when the full sequence finishes.
    """

    steps: tuple[Transition | Spring, ...] | list[Transition | Spring]
    on_complete: str | None = None

    def to_wire(self) -> dict[str, Any]:
        """Encode to the wire protocol format."""
        encoded_steps = [step.to_wire() for step in self.steps]
        result: dict[str, Any] = {"type": "sequence", "steps": encoded_steps}
        if self.on_complete is not None:
            result["on_complete"] = self.on_complete
        return result
