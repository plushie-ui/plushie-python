"""Easing functions for animations.

All easing functions take a progress value ``t`` in ``0.0..1.0`` and
return a curved ``t`` value.  31 named curves organized by family plus
``cubic_bezier()`` for custom curves.

Named curves match the renderer's easing vocabulary: pass the function
name (e.g. ``"ease_out_cubic"``) as a string in Transition descriptors,
or call the function directly for SDK-side Tween interpolation.
"""

from __future__ import annotations

import math
from collections.abc import Callable

type Easing = Callable[[float], float]
"""An easing function: takes ``t`` in 0..1, returns curved ``t``."""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PI = math.pi
_C1 = 1.70158
_C2 = _C1 * 1.525
_C3 = _C1 + 1.0
_C4 = 2.0 * _PI / 3.0
_C5 = 2.0 * _PI / 4.5
_N1 = 7.5625
_D1 = 2.75

# ---------------------------------------------------------------------------
# Named easing curves
# ---------------------------------------------------------------------------

NAMED_EASINGS: tuple[str, ...] = (
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "ease_in_quad",
    "ease_out_quad",
    "ease_in_out_quad",
    "ease_in_cubic",
    "ease_out_cubic",
    "ease_in_out_cubic",
    "ease_in_quart",
    "ease_out_quart",
    "ease_in_out_quart",
    "ease_in_quint",
    "ease_out_quint",
    "ease_in_out_quint",
    "ease_in_expo",
    "ease_out_expo",
    "ease_in_out_expo",
    "ease_in_circ",
    "ease_out_circ",
    "ease_in_out_circ",
    "ease_in_back",
    "ease_out_back",
    "ease_in_out_back",
    "ease_in_elastic",
    "ease_out_elastic",
    "ease_in_out_elastic",
    "ease_in_bounce",
    "ease_out_bounce",
    "ease_in_out_bounce",
)
"""All named easing curve names recognized by the renderer."""

# -- Linear ----------------------------------------------------------------


def linear(t: float) -> float:
    """Linear easing (identity)."""
    return t


# -- Sine ------------------------------------------------------------------


def ease_in(t: float) -> float:
    """Sine ease in."""
    return 1.0 - math.cos(t * _PI / 2.0)


def ease_out(t: float) -> float:
    """Sine ease out."""
    return math.sin(t * _PI / 2.0)


def ease_in_out(t: float) -> float:
    """Sine ease in-out."""
    return -(math.cos(_PI * t) - 1.0) / 2.0


# -- Quadratic -------------------------------------------------------------


def ease_in_quad(t: float) -> float:
    """Quadratic ease in."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Quadratic ease out."""
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_out_quad(t: float) -> float:
    """Quadratic ease in-out."""
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0


# -- Cubic -----------------------------------------------------------------


def ease_in_cubic(t: float) -> float:
    """Cubic ease in."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease out."""
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease in-out."""
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0


# -- Quartic ---------------------------------------------------------------


def ease_in_quart(t: float) -> float:
    """Quartic ease in."""
    return t * t * t * t


def ease_out_quart(t: float) -> float:
    """Quartic ease out."""
    return 1.0 - (1.0 - t) ** 4


def ease_in_out_quart(t: float) -> float:
    """Quartic ease in-out."""
    if t < 0.5:
        return 8.0 * t * t * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 4 / 2.0


# -- Quintic ---------------------------------------------------------------


def ease_in_quint(t: float) -> float:
    """Quintic ease in."""
    return t * t * t * t * t


def ease_out_quint(t: float) -> float:
    """Quintic ease out."""
    return 1.0 - (1.0 - t) ** 5


def ease_in_out_quint(t: float) -> float:
    """Quintic ease in-out."""
    if t < 0.5:
        return 16.0 * t * t * t * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 5 / 2.0


# -- Exponential -----------------------------------------------------------


def ease_in_expo(t: float) -> float:
    """Exponential ease in."""
    if t == 0.0:
        return 0.0
    return 2.0 ** (10.0 * t - 10.0)


def ease_out_expo(t: float) -> float:
    """Exponential ease out."""
    if t == 1.0:
        return 1.0
    return 1.0 - 2.0 ** (-10.0 * t)


def ease_in_out_expo(t: float) -> float:
    """Exponential ease in-out."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    if t < 0.5:
        return 2.0 ** (20.0 * t - 10.0) / 2.0
    return (2.0 - 2.0 ** (-20.0 * t + 10.0)) / 2.0


# -- Circular --------------------------------------------------------------


def ease_in_circ(t: float) -> float:
    """Circular ease in."""
    return 1.0 - math.sqrt(1.0 - t * t)


def ease_out_circ(t: float) -> float:
    """Circular ease out."""
    return math.sqrt(1.0 - (t - 1.0) * (t - 1.0))


def ease_in_out_circ(t: float) -> float:
    """Circular ease in-out."""
    if t < 0.5:
        return (1.0 - math.sqrt(1.0 - (2.0 * t) ** 2)) / 2.0
    return (math.sqrt(1.0 - (-2.0 * t + 2.0) ** 2) + 1.0) / 2.0


# -- Back (overshoot) ------------------------------------------------------


def ease_in_back(t: float) -> float:
    """Back ease in: pulls back before accelerating."""
    return _C3 * t * t * t - _C1 * t * t


def ease_out_back(t: float) -> float:
    """Back ease out: overshoots then settles."""
    return 1.0 + _C3 * (t - 1.0) ** 3 + _C1 * (t - 1.0) ** 2


def ease_in_out_back(t: float) -> float:
    """Back ease in-out: pulls back and overshoots."""
    if t < 0.5:
        return ((2.0 * t) ** 2 * ((_C2 + 1.0) * 2.0 * t - _C2)) / 2.0
    return ((2.0 * t - 2.0) ** 2 * ((_C2 + 1.0) * (2.0 * t - 2.0) + _C2) + 2.0) / 2.0


# -- Elastic (oscillating overshoot) ---------------------------------------


def ease_in_elastic(t: float) -> float:
    """Elastic ease in: oscillates then accelerates."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    return -(2.0 ** (10.0 * t - 10.0)) * math.sin((10.0 * t - 10.75) * _C4)


def ease_out_elastic(t: float) -> float:
    """Elastic ease out: overshoots with oscillation."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    return 2.0 ** (-10.0 * t) * math.sin((10.0 * t - 0.75) * _C4) + 1.0


def ease_in_out_elastic(t: float) -> float:
    """Elastic ease in-out."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    if t < 0.5:
        return -(2.0 ** (20.0 * t - 10.0) * math.sin((20.0 * t - 11.125) * _C5)) / 2.0
    return (2.0 ** (-20.0 * t + 10.0) * math.sin((20.0 * t - 11.125) * _C5)) / 2.0 + 1.0


# -- Bounce ----------------------------------------------------------------


def ease_out_bounce(t: float) -> float:
    """Bounce ease out: bouncing ball effect."""
    if t < 1.0 / _D1:
        return _N1 * t * t
    if t < 2.0 / _D1:
        t2 = t - 1.5 / _D1
        return _N1 * t2 * t2 + 0.75
    if t < 2.5 / _D1:
        t2 = t - 2.25 / _D1
        return _N1 * t2 * t2 + 0.9375
    t2 = t - 2.625 / _D1
    return _N1 * t2 * t2 + 0.984375


def ease_in_bounce(t: float) -> float:
    """Bounce ease in."""
    return 1.0 - ease_out_bounce(1.0 - t)


def ease_in_out_bounce(t: float) -> float:
    """Bounce ease in-out."""
    if t < 0.5:
        return (1.0 - ease_out_bounce(1.0 - 2.0 * t)) / 2.0
    return (1.0 + ease_out_bounce(2.0 * t - 1.0)) / 2.0


# ---------------------------------------------------------------------------
# Cubic bezier
# ---------------------------------------------------------------------------


def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> Easing:
    """Create an easing function from cubic bezier control points.

    Control points match the CSS ``cubic-bezier()`` function. The curve
    starts at (0, 0) and ends at (1, 1); ``(x1, y1)`` and ``(x2, y2)``
    are the two intermediate control points.

    Uses Newton-Raphson iteration to solve for the bezier parameter.
    """

    def _bezier_easing(t: float) -> float:
        if t <= 0.0:
            return 0.0
        if t >= 1.0:
            return 1.0
        s = _newton_raphson(t, x1, x2, t, 8)
        return _bezier_eval(s, y1, y2)

    return _bezier_easing


def _bezier_eval(s: float, p1: float, p2: float) -> float:
    """Evaluate cubic bezier polynomial B(s) for one axis."""
    s2 = s * s
    s3 = s2 * s
    return 3.0 * (1.0 - s) * (1.0 - s) * s * p1 + 3.0 * (1.0 - s) * s2 * p2 + s3


def _bezier_derivative(s: float, p1: float, p2: float) -> float:
    """Derivative B'(s) for one axis."""
    return (
        3.0 * (1.0 - s) * (1.0 - s) * p1
        + 6.0 * (1.0 - s) * s * (p2 - p1)
        + 3.0 * s * s * (1.0 - p2)
    )


def _newton_raphson(
    target: float, p1: float, p2: float, guess: float, iterations: int
) -> float:
    """Newton-Raphson iteration to find s where B_x(s) == target."""
    for _ in range(iterations):
        x = _bezier_eval(guess, p1, p2)
        dx = _bezier_derivative(guess, p1, p2)
        if abs(x - target) < 1.0e-7 or abs(dx) < 1.0e-7:
            return guess
        guess = guess - (x - target) / dx
    return guess


# ---------------------------------------------------------------------------
# Lookup by name
# ---------------------------------------------------------------------------

_EASING_MAP: dict[str, Easing] = {
    "linear": linear,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "ease_in_quad": ease_in_quad,
    "ease_out_quad": ease_out_quad,
    "ease_in_out_quad": ease_in_out_quad,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "ease_in_quart": ease_in_quart,
    "ease_out_quart": ease_out_quart,
    "ease_in_out_quart": ease_in_out_quart,
    "ease_in_quint": ease_in_quint,
    "ease_out_quint": ease_out_quint,
    "ease_in_out_quint": ease_in_out_quint,
    "ease_in_expo": ease_in_expo,
    "ease_out_expo": ease_out_expo,
    "ease_in_out_expo": ease_in_out_expo,
    "ease_in_circ": ease_in_circ,
    "ease_out_circ": ease_out_circ,
    "ease_in_out_circ": ease_in_out_circ,
    "ease_in_back": ease_in_back,
    "ease_out_back": ease_out_back,
    "ease_in_out_back": ease_in_out_back,
    "ease_in_elastic": ease_in_elastic,
    "ease_out_elastic": ease_out_elastic,
    "ease_in_out_elastic": ease_in_out_elastic,
    "ease_in_bounce": ease_in_bounce,
    "ease_out_bounce": ease_out_bounce,
    "ease_in_out_bounce": ease_in_out_bounce,
}


def by_name(name: str) -> Easing:
    """Look up an easing function by its string name.

    Raises ``KeyError`` if the name is not recognized.
    """
    return _EASING_MAP[name]


def encode_easing(
    easing: str | Easing | tuple[str, float, float, float, float],
) -> str | dict[str, list[float]]:
    """Encode an easing value for the wire protocol.

    Accepts:
    - A string name (e.g. ``"ease_out"``) -- passed through
    - A cubic bezier tuple ``("cubic_bezier", x1, y1, x2, y2)``
    - An ``Easing`` callable (looked up by identity in the named map)

    Returns a string name or ``{"cubic_bezier": [x1, y1, x2, y2]}``.
    """
    if isinstance(easing, str):
        return easing
    if isinstance(easing, tuple) and len(easing) == 5 and easing[0] == "cubic_bezier":
        return {"cubic_bezier": list(easing[1:])}
    # Try to find the callable in the named map
    for name, fn in _EASING_MAP.items():
        if fn is easing:
            return name
    raise ValueError(f"unknown easing: {easing!r}")
