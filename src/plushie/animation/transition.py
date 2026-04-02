"""Renderer-side timed transition descriptor.

Declares animation intent in the view tree. The renderer handles
interpolation locally with zero wire traffic during animation.

Usage::

    from plushie.animation import Transition

    def view(self, model):
        return ui.window("main",
            ui.container("box",
                opacity=Transition(to=0.0, duration=300, easing="ease_out"),
            ),
        )

Enter animations use ``from_`` to set the starting value on mount::

    opacity=Transition(to=1.0, duration=200, from_=0.0)

Looping::

    opacity=Transition.loop(to=0.4, from_=1.0, duration=800)
    rotation=Transition.loop(to=360, from_=0, duration=1000, auto_reverse=False)

Completion events::

    opacity=Transition(to=0.0, duration=300, on_complete="faded_out")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plushie.animation.easing import encode_easing


@dataclass(frozen=True, slots=True)
class Transition:
    """A timed transition animation descriptor.

    Attributes:
        to: Target value.
        duration: Duration in milliseconds.
        easing: Easing curve name or callable. Default ``"ease_in_out"``.
        delay: Delay before animation starts (ms). Default 0.
        from_: Starting value for enter animations. ``None`` means
            animate from the current value.
        repeat: Number of repetitions. ``None`` for one-shot, ``-1``
            or ``"forever"`` for infinite.
        auto_reverse: Reverse direction on each repeat cycle.
        on_complete: Event tag string sent when the animation finishes.
    """

    to: Any
    duration: int
    easing: str | Any = "ease_in_out"
    delay: int = 0
    from_: Any = None
    repeat: int | None = None
    auto_reverse: bool = False
    on_complete: str | None = None

    @staticmethod
    def loop(
        *,
        to: Any,
        duration: int,
        from_: Any = None,
        easing: str | Any = "ease_in_out",
        cycles: int | None = None,
        auto_reverse: bool = True,
        on_complete: str | None = None,
    ) -> Transition:
        """Create a looping transition.

        Args:
            to: Target value.
            duration: Duration per cycle in milliseconds.
            from_: Starting value (required for visual looping).
            easing: Easing curve. Default ``"ease_in_out"``.
            cycles: Number of cycles. ``None`` for infinite.
            auto_reverse: Reverse on each cycle. Default ``True``.
            on_complete: Completion event tag.
        """
        repeat = cycles if cycles is not None else -1
        return Transition(
            to=to,
            duration=duration,
            easing=easing,
            from_=from_,
            repeat=repeat,
            auto_reverse=auto_reverse,
            on_complete=on_complete,
        )

    def to_wire(self) -> dict[str, Any]:
        """Encode to the wire protocol format.

        Returns a dict suitable for use as a prop value in the view tree.
        """
        result: dict[str, Any] = {
            "type": "transition",
            "to": self.to,
            "duration": self.duration,
        }
        if self.easing != "ease_in_out":
            result["easing"] = encode_easing(self.easing)
        if self.delay != 0:
            result["delay"] = self.delay
        if self.from_ is not None:
            result["from"] = self.from_
        if self.repeat is not None:
            result["repeat"] = self.repeat
        if self.auto_reverse:
            result["auto_reverse"] = True
        if self.on_complete is not None:
            result["on_complete"] = self.on_complete
        return result
