"""SDK-side animation interpolation (tween).

For animations that need frame-by-frame SDK control: canvas drawing,
physics simulations, or values that drive model logic. For most widget
property animations, prefer renderer-side descriptors (Transition,
Spring, Sequence) which run at full frame rate with zero wire traffic.

Usage::

    from plushie.animation import Tween
    from plushie.animation.easing import ease_out

    anim = Tween.new(0.0, 1.0, 300, easing=ease_out)
    anim = anim.start(timestamp)

    # Each animation frame:
    value, anim = anim.advance(timestamp)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from plushie.animation.easing import Easing, linear

__all__ = [
    "FINISHED",
    "Tween",
]

FINISHED: Literal["finished"] = "finished"
"""Sentinel returned by :meth:`Tween.advance` when the animation completes."""


def _clamp(t: float) -> float:
    if t < 0.0:
        return 0.0
    if t > 1.0:
        return 1.0
    return t


def interpolate(
    from_val: float,
    to_val: float,
    t: float,
    easing: Easing = linear,
) -> float:
    """Linearly interpolate between *from_val* and *to_val* at progress *t*.

    *t* is clamped to ``0.0..1.0`` before *easing* is applied.
    """
    clamped = _clamp(t)
    eased = easing(clamped)
    return from_val + (to_val - from_val) * eased


@dataclass(frozen=True, slots=True)
class Tween:
    """A single animated value transitioning over time.

    Create via :meth:`new`, start with :meth:`start`, advance each frame
    with :meth:`advance`, and read the current value with :meth:`value`.
    """

    from_val: float
    to_val: float
    duration_ms: int
    easing: Easing
    started_at: int | None
    current_value: float

    @staticmethod
    def new(
        from_val: float,
        to_val: float,
        duration_ms: int,
        *,
        easing: Easing = linear,
    ) -> Tween:
        """Create a new tween animation.

        Args:
            from_val: Starting value.
            to_val: Target value.
            duration_ms: Duration in milliseconds (must be > 0).
            easing: Easing function, defaults to :func:`linear`.
        """
        if duration_ms <= 0:
            msg = f"duration_ms must be positive, got {duration_ms}"
            raise ValueError(msg)
        return Tween(
            from_val=from_val,
            to_val=to_val,
            duration_ms=duration_ms,
            easing=easing,
            started_at=None,
            current_value=from_val,
        )

    def start(self, timestamp: int) -> Tween:
        """Start (or restart) the animation at the given frame timestamp."""
        return replace(self, started_at=timestamp, current_value=self.from_val)

    def advance(self, timestamp: int) -> tuple[float, Tween | Literal["finished"]]:
        """Advance the animation to the given frame timestamp.

        Returns ``(current_value, updated_tween)`` while in progress,
        or ``(final_value, FINISHED)`` when complete.
        """
        if self.started_at is None:
            return (self.current_value, self)

        elapsed = timestamp - self.started_at
        t = _clamp(elapsed / self.duration_ms)
        current = interpolate(self.from_val, self.to_val, t, self.easing)

        if t >= 1.0:
            return (self.to_val, FINISHED)

        updated = replace(self, current_value=current)
        return (current, updated)

    def finished(self) -> bool:
        """Return ``True`` if the animation has reached its target value."""
        if self.started_at is None:
            return False
        return self.current_value == self.to_val

    def value(self) -> float:
        """Return the current interpolated value."""
        return self.current_value

    def __repr__(self) -> str:
        state = (
            "not started" if self.started_at is None else f"at {self.current_value:.4f}"
        )
        return f"Tween({self.from_val} -> {self.to_val}, {self.duration_ms}ms, {state})"
