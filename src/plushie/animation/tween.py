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

    Create via :meth:`new` or :meth:`looping`, start with :meth:`start`,
    advance each frame with :meth:`advance`, and read the current value
    with :meth:`value`.

    Use ``repeat`` to replay the animation a fixed number of times or
    indefinitely. Use ``auto_reverse`` with repeat for ping-pong behavior
    (the animation smoothly reverses direction each cycle instead of
    snapping back to the start value).
    """

    from_val: float
    to_val: float
    duration_ms: int
    easing: Easing
    started_at: int | None
    current_value: float
    repeat: int | None = None
    auto_reverse: bool = False
    is_done: bool = False

    @staticmethod
    def new(
        from_val: float,
        to_val: float,
        duration_ms: int,
        *,
        easing: Easing = linear,
        repeat: int | None = None,
        auto_reverse: bool = False,
    ) -> Tween:
        """Create a new tween animation.

        Args:
            from_val: Starting value.
            to_val: Target value.
            duration_ms: Duration in milliseconds (must be > 0).
            easing: Easing function, defaults to :func:`linear`.
            repeat: Number of repetitions, ``None`` for single play,
                or a positive integer for that many plays total.
            auto_reverse: When ``True``, swap from/to on each repeat
                cycle for ping-pong behavior.
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
            repeat=repeat,
            auto_reverse=auto_reverse,
        )

    @staticmethod
    def looping(
        from_val: float,
        to_val: float,
        duration_ms: int,
        *,
        easing: Easing = linear,
    ) -> Tween:
        """Create a tween that loops forever with ping-pong behavior.

        Convenience for ``new(..., repeat=None, auto_reverse=True)``.
        The animation smoothly oscillates between from and to values.
        """
        return Tween.new(
            from_val,
            to_val,
            duration_ms,
            easing=easing,
            repeat=None,
            auto_reverse=True,
        )

    def start(self, timestamp: int) -> Tween:
        """Start (or restart) the animation at the given frame timestamp."""
        return replace(
            self, started_at=timestamp, current_value=self.from_val, is_done=False
        )

    def advance(self, timestamp: int) -> tuple[float, Tween | Literal["finished"]]:
        """Advance the animation to the given frame timestamp.

        Returns ``(current_value, updated_tween)`` while in progress,
        or ``(final_value, FINISHED)`` when complete.
        """
        if self.started_at is None:
            return (self.current_value, self)

        if self.is_done:
            return (self.current_value, FINISHED)

        elapsed = timestamp - self.started_at
        t = _clamp(elapsed / self.duration_ms)
        current = interpolate(self.from_val, self.to_val, t, self.easing)

        if t < 1.0:
            return (current, replace(self, current_value=current))

        if self.repeat is None and not self.auto_reverse:
            return (self.to_val, FINISHED)

        updated = self._restart_cycle()
        return (self.to_val, updated)

    def _restart_cycle(self) -> Tween:
        if self.auto_reverse:
            return replace(
                self,
                from_val=self.to_val,
                to_val=self.from_val,
                current_value=self.to_val,
                started_at=(self.started_at or 0) + self.duration_ms,
            )
        if self.repeat is not None and self.repeat > 1:
            return replace(
                self,
                repeat=self.repeat - 1,
                current_value=self.from_val,
                started_at=(self.started_at or 0) + self.duration_ms,
            )
        return replace(self, current_value=self.to_val, is_done=True)

    def finished(self) -> bool:
        """Return ``True`` if the animation has completed."""
        return self.is_done

    def value(self) -> float:
        """Return the current interpolated value."""
        return self.current_value

    def __repr__(self) -> str:
        state = (
            "finished"
            if self.is_done
            else "not started"
            if self.started_at is None
            else f"at {self.current_value:.4f}"
        )
        return f"Tween({self.from_val} -> {self.to_val}, {self.duration_ms}ms, {state})"
