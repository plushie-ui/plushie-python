"""Backwards-compatibility re-exports from :mod:`plushie.widget`.

This module exists so ``from plushie.canvas_widget import CanvasWidgetDef``
continues to work.  New code should import from :mod:`plushie.widget`.

``CanvasWidgetDef`` is an alias for :class:`~plushie.widget.WidgetDef`.
"""

from __future__ import annotations

from plushie.widget import (
    EventAction as EventAction,
)
from plushie.widget import (
    EventActionResult as EventActionResult,
)
from plushie.widget import (
    RegistryEntry as RegistryEntry,
)
from plushie.widget import (
    WidgetDef as WidgetDef,
)
from plushie.widget import (
    WidgetKey as WidgetKey,
)
from plushie.widget import (
    WidgetRegistry as WidgetRegistry,
)
from plushie.widget import (
    collect_subscriptions as collect_subscriptions,
)
from plushie.widget import (
    derive_registry as derive_registry,
)
from plushie.widget import (
    dispatch_through_widgets as dispatch_through_widgets,
)
from plushie.widget import (
    maybe_handle_timer as maybe_handle_timer,
)
from plushie.widget import (
    render_placeholder as render_placeholder,
)

#: Alias for :class:`WidgetDef`.
CanvasWidgetDef = WidgetDef

__all__ = [
    "CanvasWidgetDef",
    "EventAction",
    "EventActionResult",
    "RegistryEntry",
    "WidgetDef",
    "WidgetKey",
    "WidgetRegistry",
    "collect_subscriptions",
    "derive_registry",
    "dispatch_through_widgets",
    "maybe_handle_timer",
    "render_placeholder",
]
