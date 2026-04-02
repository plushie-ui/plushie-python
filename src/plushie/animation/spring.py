"""Renderer-side physics-based spring descriptor.

Springs animate using a damped harmonic oscillator with no fixed
duration. They settle naturally based on stiffness, damping, and mass.
Ideal for interactive animations where the target changes frequently
(drag, scroll, hover) because interruption preserves velocity.

Usage::

    from plushie.animation import Spring

    scale=Spring(to=1.05, stiffness=200, damping=20)
    scale=Spring.preset("bouncy", to=1.05)

Presets:

- ``"gentle"``   -- stiffness=120, damping=14 (slow, smooth)
- ``"snappy"``   -- stiffness=200, damping=20 (quick, minimal overshoot)
- ``"bouncy"``   -- stiffness=300, damping=10 (quick with overshoot)
- ``"stiff"``    -- stiffness=400, damping=30 (very quick, crisp)
- ``"molasses"`` -- stiffness=60,  damping=12 (slow, heavy)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRESETS: dict[str, dict[str, float]] = {
    "gentle": {"stiffness": 120, "damping": 14},
    "snappy": {"stiffness": 200, "damping": 20},
    "bouncy": {"stiffness": 300, "damping": 10},
    "stiff": {"stiffness": 400, "damping": 30},
    "molasses": {"stiffness": 60, "damping": 12},
}
"""Named spring parameter presets."""


@dataclass(frozen=True, slots=True)
class Spring:
    """A physics-based spring animation descriptor.

    Attributes:
        to: Target value.
        stiffness: Spring constant (higher = faster, snappier). Default 100.
        damping: Friction (higher = less oscillation). Default 10.
        mass: Object mass (higher = slower, heavier). Default 1.0.
        velocity: Initial velocity. Default 0.0.
        from_: Starting value for enter animations.
        on_complete: Event tag string sent when the spring settles.
    """

    to: Any
    stiffness: float = 100
    damping: float = 10
    mass: float = 1.0
    velocity: float = 0.0
    from_: Any = None
    on_complete: str | None = None

    @staticmethod
    def preset(name: str, /, *, to: Any, **kwargs: Any) -> Spring:
        """Create a Spring from a named preset.

        Args:
            name: Preset name (gentle, snappy, bouncy, stiff, molasses).
            to: Target value.
            **kwargs: Override any Spring field.
        """
        if name not in PRESETS:
            available = ", ".join(sorted(PRESETS))
            raise ValueError(f"unknown spring preset {name!r} (available: {available})")
        params = {**PRESETS[name], "to": to, **kwargs}
        return Spring(**params)

    def to_wire(self) -> dict[str, Any]:
        """Encode to the wire protocol format."""
        result: dict[str, Any] = {
            "type": "spring",
            "to": self.to,
            "stiffness": self.stiffness,
            "damping": self.damping,
        }
        if self.mass != 1.0:
            result["mass"] = self.mass
        if self.velocity != 0.0:
            result["velocity"] = self.velocity
        if self.from_ is not None:
            result["from"] = self.from_
        if self.on_complete is not None:
            result["on_complete"] = self.on_complete
        return result
