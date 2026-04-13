"""Animation system for plushie apps.

Two approaches to animation:

**Renderer-side descriptors** (preferred for widget properties):

- :class:`Transition` - timed animation with easing curves
- :class:`Spring` - physics-based spring with presets
- :class:`Sequence` - chain of transitions and springs

These run at full frame rate on the renderer with zero wire traffic.
Use them as prop values in your view::

    from plushie.animation import Transition, Spring

    opacity=Transition(to=0.0, duration=300, easing="ease_out")
    scale=Spring.preset("bouncy", to=1.05)

**SDK-side tween** (for canvas, physics, model-driven values):

- :class:`Tween` - stateful interpolator managed in your model

Use with ``on_animation_frame`` subscriptions for frame-by-frame
control.
"""

from __future__ import annotations

from plushie.animation.easing import (
    NAMED_EASINGS,
    Easing,
    EasingSpec,
    by_name,
    cubic_bezier,
    ease_in,
    ease_in_back,
    ease_in_bounce,
    ease_in_circ,
    ease_in_cubic,
    ease_in_elastic,
    ease_in_expo,
    ease_in_out,
    ease_in_out_back,
    ease_in_out_bounce,
    ease_in_out_circ,
    ease_in_out_cubic,
    ease_in_out_elastic,
    ease_in_out_expo,
    ease_in_out_quad,
    ease_in_out_quart,
    ease_in_out_quint,
    ease_in_quad,
    ease_in_quart,
    ease_in_quint,
    ease_out,
    ease_out_back,
    ease_out_bounce,
    ease_out_circ,
    ease_out_cubic,
    ease_out_elastic,
    ease_out_expo,
    ease_out_quad,
    ease_out_quart,
    ease_out_quint,
    linear,
)
from plushie.animation.sequence import Sequence
from plushie.animation.spring import PRESETS, Spring
from plushie.animation.transition import Transition
from plushie.animation.tween import FINISHED, Tween, interpolate

__all__ = [
    "FINISHED",
    "NAMED_EASINGS",
    "PRESETS",
    "Easing",
    "EasingSpec",
    "Sequence",
    "Spring",
    "Transition",
    "Tween",
    "by_name",
    "cubic_bezier",
    "ease_in",
    "ease_in_back",
    "ease_in_bounce",
    "ease_in_circ",
    "ease_in_cubic",
    "ease_in_elastic",
    "ease_in_expo",
    "ease_in_out",
    "ease_in_out_back",
    "ease_in_out_bounce",
    "ease_in_out_circ",
    "ease_in_out_cubic",
    "ease_in_out_elastic",
    "ease_in_out_expo",
    "ease_in_out_quad",
    "ease_in_out_quart",
    "ease_in_out_quint",
    "ease_in_quad",
    "ease_in_quart",
    "ease_in_quint",
    "ease_out",
    "ease_out_back",
    "ease_out_bounce",
    "ease_out_circ",
    "ease_out_cubic",
    "ease_out_elastic",
    "ease_out_expo",
    "ease_out_quad",
    "ease_out_quart",
    "ease_out_quint",
    "interpolate",
    "linear",
]
