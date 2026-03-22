"""Server-side animation interpolation and easing functions.

Pure functions operating on frozen dataclasses -- no processes, no state
management beyond what lives in your app model.  The host computes
interpolated values on each animation frame tick.

Easing functions
----------------

All easing functions take a ``t`` value in ``0.0..1.0`` and return a
curved ``t`` value:

- :func:`linear` -- identity
- :func:`ease_in` -- cubic ease in
- :func:`ease_out` -- cubic ease out
- :func:`ease_in_out` -- cubic ease in-out
- :func:`ease_in_quad` -- quadratic ease in
- :func:`ease_out_quad` -- quadratic ease out
- :func:`ease_in_out_quad` -- quadratic ease in-out
- :func:`spring` -- spring with overshoot

Interpolation
-------------

:func:`interpolate` lerps between two numbers with an optional easing
function applied to ``t`` first.

Animation lifecycle
-------------------

Create with :func:`Animation.new`, start with :meth:`Animation.start`,
advance each frame with :meth:`Animation.advance`, read the value with
:meth:`Animation.value`.

Example::

    anim = Animation.new(0.0, 1.0, 300, easing=ease_out)
    anim = anim.start(timestamp)

    # each frame:
    value, anim = anim.advance(timestamp)
    # value is the interpolated float; anim is either a new Animation
    # or the sentinel FINISHED when the animation completes.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

__all__ = [
    "FINISHED",
    "Animation",
    "Easing",
    "ease_in",
    "ease_in_out",
    "ease_in_out_quad",
    "ease_in_quad",
    "ease_out",
    "ease_out_quad",
    "interpolate",
    "linear",
    "spring",
]

# ---------------------------------------------------------------------------
# Easing type
# ---------------------------------------------------------------------------

type Easing = Callable[[float], float]

# ---------------------------------------------------------------------------
# Easing functions
# ---------------------------------------------------------------------------


def linear(t: float) -> float:
    """Linear easing (identity).  Returns ``t`` unchanged."""
    return t


def ease_in(t: float) -> float:
    """Cubic ease in.  Starts slow, accelerates."""
    return t * t * t


def ease_out(t: float) -> float:
    """Cubic ease out.  Starts fast, decelerates."""
    inv = 1.0 - t
    return 1.0 - inv * inv * inv


def ease_in_out(t: float) -> float:
    """Cubic ease in-out.  Slow start, fast middle, slow end."""
    if t < 0.5:
        return 4.0 * t * t * t
    inv = -2.0 * t + 2.0
    return 1.0 - inv * inv * inv / 2.0


def ease_in_quad(t: float) -> float:
    """Quadratic ease in.  Starts slow, accelerates."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Quadratic ease out.  Starts fast, decelerates."""
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_out_quad(t: float) -> float:
    """Quadratic ease in-out.  Slow start and end, fast middle."""
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0


def spring(t: float) -> float:
    """Spring easing with overshoot.

    Overshoots the target slightly before settling.  Uses a
    single-period damped sine approximation.
    """
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    c4 = 2.0 * math.pi / 3.0
    return math.pow(2.0, -10.0 * t) * math.sin((t * 10.0 - 0.75) * c4) + 1.0


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------


def interpolate(
    from_val: float,
    to_val: float,
    t: float,
    easing: Easing = linear,
) -> float:
    """Linearly interpolate between *from_val* and *to_val* at progress *t*.

    *t* is clamped to ``0.0..1.0`` before *easing* is applied.

    Example::

        >>> interpolate(0.0, 100.0, 0.5)
        50.0
        >>> interpolate(0.0, 100.0, 0.5, ease_in)
        12.5
    """
    clamped = _clamp(t)
    eased = easing(clamped)
    return from_val + (to_val - from_val) * eased


# ---------------------------------------------------------------------------
# Sentinel for finished animations
# ---------------------------------------------------------------------------

FINISHED: Literal["finished"] = "finished"
"""Sentinel returned by :meth:`Animation.advance` when the animation completes."""


# ---------------------------------------------------------------------------
# Animation dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Animation:
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

    # -- Construction -------------------------------------------------------

    @staticmethod
    def new(
        from_val: float,
        to_val: float,
        duration_ms: int,
        *,
        easing: Easing = linear,
    ) -> Animation:
        """Create a new animation.

        Args:
            from_val: Starting value.
            to_val: Target value.
            duration_ms: Duration in milliseconds (must be > 0).
            easing: Easing function, defaults to :func:`linear`.

        Example::

            >>> anim = Animation.new(0.0, 1.0, 300)
            >>> anim.value()
            0.0
        """
        if duration_ms <= 0:
            msg = f"duration_ms must be positive, got {duration_ms}"
            raise ValueError(msg)
        return Animation(
            from_val=from_val,
            to_val=to_val,
            duration_ms=duration_ms,
            easing=easing,
            started_at=None,
            current_value=from_val,
        )

    # -- Lifecycle ----------------------------------------------------------

    def start(self, timestamp: int) -> Animation:
        """Start (or restart) the animation at the given frame timestamp.

        Resets the current value to ``from_val``.
        """
        return replace(self, started_at=timestamp, current_value=self.from_val)

    def advance(self, timestamp: int) -> tuple[float, Animation | Literal["finished"]]:
        """Advance the animation to the given frame timestamp.

        Returns ``(current_value, updated_animation)`` while in progress,
        or ``(final_value, FINISHED)`` when the animation completes.

        If the animation has not been started, returns
        ``(from_val, self)`` unchanged.
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

    # -- repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        state = (
            "not started" if self.started_at is None else f"at {self.current_value:.4f}"
        )
        return (
            f"Animation({self.from_val} -> {self.to_val}, "
            f"{self.duration_ms}ms, {state})"
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _clamp(t: float) -> float:
    if t < 0.0:
        return 0.0
    if t > 1.0:
        return 1.0
    return t
