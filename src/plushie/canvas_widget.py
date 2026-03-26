"""Canvas widget system for pure-Python widgets rendered via canvas shapes.

Canvas widgets manage internal state, render via canvas shapes, and
transform raw canvas events into semantic widget events. They follow
iced's captured/ignored dispatch model.

Usage::

    from plushie.canvas_widget import CanvasWidgetDef, EventAction

    class StarRating(CanvasWidgetDef):
        def init(self, props):
            return {"hovered": None}

        def render(self, id, props, state):
            return canvas.canvas(id, canvas.group(...))

        def handle_event(self, event, state):
            match event:
                case CanvasElementEnter(element_id=eid):
                    return EventAction.update_state({"hovered": eid})
                case CanvasElementClick(element_id=eid):
                    return EventAction.emit("select", {"value": eid})
                case _:
                    return EventAction.ignored()

    # In your view:
    StarRating.build("stars", props={"max": 5, "value": 3})
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from plushie.events import WidgetEvent, split_scoped_id
from plushie.subscriptions import Subscription

logger = logging.getLogger("plushie")


# ---------------------------------------------------------------------------
# Event action results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Ignored:
    """Handler did not capture the event."""


@dataclass(frozen=True, slots=True)
class _Consumed:
    """Handler captured the event with no output."""


@dataclass(frozen=True, slots=True)
class _UpdateState:
    """Handler captured the event and updated internal state."""

    state: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Emit:
    """Handler captured the event and emits a semantic widget event."""

    kind: str
    data: dict[str, Any]
    state: dict[str, Any] | None = None


type EventActionResult = _Ignored | _Consumed | _UpdateState | _Emit


class EventAction:
    """Factory for canvas widget event handler results."""

    @staticmethod
    def ignored() -> _Ignored:
        """Event not captured -- continue to next handler."""
        return _Ignored()

    @staticmethod
    def consumed() -> _Consumed:
        """Event captured -- suppress without output."""
        return _Consumed()

    @staticmethod
    def update_state(state: dict[str, Any]) -> _UpdateState:
        """Event captured -- update internal state, no output."""
        return _UpdateState(state=state)

    @staticmethod
    def emit(
        kind: str,
        data: Any = None,
        *,
        state: dict[str, Any] | None = None,
    ) -> _Emit:
        """Event captured -- emit a semantic widget event.

        Args:
            kind: Event family name (e.g. ``"select"``, ``"change"``).
            data: Event data. Dicts pass through; other values are
                wrapped as ``{"value": data}``.
            state: Optional new internal state.
        """
        if isinstance(data, dict):
            normalized = data
        elif data is not None:
            normalized = {"value": data}
        else:
            normalized = {}
        return _Emit(kind=kind, data=normalized, state=state)


# ---------------------------------------------------------------------------
# Canvas widget definition (ABC)
# ---------------------------------------------------------------------------


class CanvasWidgetDef(ABC):
    """Abstract base for canvas widget definitions.

    Subclass and implement ``init``, ``render``, and ``handle_event``.
    Optionally implement ``subscribe`` for timer-based updates.
    """

    @abstractmethod
    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        """Return initial internal state for a new widget instance.

        Args:
            props: The widget's resolved props.
        """
        ...

    @abstractmethod
    def render(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Render the widget as a canvas node dict.

        Args:
            widget_id: The widget's scoped ID.
            props: Resolved props.
            state: Current internal state.
        """
        ...

    @abstractmethod
    def handle_event(
        self,
        event: Any,
        state: dict[str, Any],
    ) -> EventActionResult:
        """Handle an incoming event.

        Args:
            event: The event (canvas element events, timer ticks, etc.).
            state: Current internal state.

        Returns:
            An ``EventAction`` result.
        """
        ...

    def subscribe(
        self,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> list[Subscription]:
        """Return subscriptions for this widget instance.

        Override to add timer or other subscriptions. Default returns
        an empty list.

        Args:
            props: Resolved props.
            state: Current internal state.
        """
        return []

    @classmethod
    def build(
        cls,
        widget_id: str,
        *,
        props: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a placeholder node for this canvas widget.

        The placeholder carries the widget definition class and props
        in ``meta``. During normalization, the runtime detects these
        and renders them with the appropriate state.

        Args:
            widget_id: Widget ID.
            props: Widget props.
        """
        resolved_props = props or {}
        return {
            "id": widget_id,
            "type": "canvas",
            "props": {},
            "children": [],
            "meta": {
                "__canvas_widget__": cls,
                "__canvas_widget_props__": resolved_props,
            },
        }


# ---------------------------------------------------------------------------
# Registry: derive from tree, dispatch events
# ---------------------------------------------------------------------------

type WidgetRegistry = dict[str, RegistryEntry]


@dataclass(slots=True)
class RegistryEntry:
    """A registered canvas widget instance."""

    definition: CanvasWidgetDef
    state: dict[str, Any]
    props: dict[str, Any]


def derive_registry(tree: dict[str, Any] | None) -> WidgetRegistry:
    """Derive the canvas widget registry from the normalized tree.

    Walks the tree and extracts widget metadata from ``meta`` fields.
    Returns a flat dict keyed by scoped ID for O(1) dispatch lookups.
    """
    if tree is None:
        return {}
    registry: WidgetRegistry = {}
    _collect_entries(tree, registry)
    return registry


def _collect_entries(
    node: dict[str, Any],
    registry: WidgetRegistry,
) -> None:
    """Recursively collect canvas widget entries from the tree."""
    meta = node.get("meta")
    if isinstance(meta, dict):
        widget_cls = meta.get("__canvas_widget__")
        if widget_cls is not None and isinstance(widget_cls, type):
            node_id = node.get("id", "")
            state = meta.get("__canvas_widget_state__", {})
            props = meta.get("__canvas_widget_props__", {})
            instance = widget_cls()
            # Initialize state for new widgets
            if not state and hasattr(instance, "init"):
                state = instance.init(props)
            registry[node_id] = RegistryEntry(
                definition=instance, state=state, props=props
            )

    for child in node.get("children", []):
        if isinstance(child, dict):
            _collect_entries(child, registry)


# ---------------------------------------------------------------------------
# Event dispatch through widget scope chain
# ---------------------------------------------------------------------------


def dispatch_through_widgets(
    registry: WidgetRegistry,
    event: Any,
) -> tuple[Any | None, WidgetRegistry]:
    """Dispatch an event through the canvas widget handler chain.

    Builds an ordered list of handlers from the event's scope (innermost
    to outermost) and walks it following iced's captured/ignored model.

    Returns ``(event_or_none, updated_registry)``. If no handler captures,
    the original event passes through. If captured, returns the transformed
    event or ``None``.
    """
    if not registry:
        return event, registry

    scope = getattr(event, "scope", None)
    event_id = getattr(event, "id", None)

    if scope is None or not isinstance(scope, tuple):
        return event, registry

    chain = _build_handler_chain(registry, scope)

    if not chain and event_id:
        # Check if the event's target itself is a canvas widget
        target_id = _scope_to_id(scope, event_id)
        entry = registry.get(target_id)
        if entry is not None:
            chain = [(target_id, entry)]

    if not chain:
        return event, registry

    return _walk_chain(registry, event, chain)


def _build_handler_chain(
    registry: WidgetRegistry,
    scope: tuple[str, ...],
) -> list[tuple[str, RegistryEntry]]:
    """Build handler chain from scope, innermost to outermost."""
    if not scope:
        return []

    forward = list(reversed(scope))
    chain: list[tuple[str, RegistryEntry]] = []

    for n in range(len(forward), 0, -1):
        scoped_id = "/".join(forward[:n])
        entry = registry.get(scoped_id)
        if entry is not None:
            chain.append((scoped_id, entry))

    return chain


def _scope_to_id(scope: tuple[str, ...], local_id: str) -> str:
    """Reconstruct scoped ID from reversed scope + local ID."""
    if not scope:
        return local_id
    return "/".join((*reversed(scope), local_id))


def _walk_chain(
    registry: WidgetRegistry,
    event: Any,
    chain: list[tuple[str, RegistryEntry]],
) -> tuple[Any | None, WidgetRegistry]:
    """Walk the handler chain, dispatching through each widget."""
    for scoped_id, entry in chain:
        try:
            action = entry.definition.handle_event(event, entry.state)
        except Exception:
            logger.warning(
                "canvas_widget %s.%s (%s) raised in handle_event",
                type(entry.definition).__module__,
                type(entry.definition).__name__,
                scoped_id,
                exc_info=True,
            )
            action = EventAction.ignored()

        if isinstance(action, _Ignored):
            continue

        if isinstance(action, _Consumed):
            return None, registry

        if isinstance(action, _UpdateState):
            entry.state = action.state
            return None, registry

        if isinstance(action, _Emit):
            if action.state is not None:
                entry.state = action.state

            emit_id, emit_scope = _resolve_emit_identity(event, scoped_id)
            emitted = WidgetEvent(
                kind=action.kind,
                id=emit_id,
                value=action.data.get("value"),
                data=action.data,
                scope=emit_scope,
            )
            event = emitted

    return event, registry


def _resolve_emit_identity(
    event: Any,
    widget_id: str,
) -> tuple[str, tuple[str, ...]]:
    """Resolve the ID and scope for emitted events.

    For widget events (which carry scope), the canvas widget's ID is
    the first scope element. For non-widget events, falls back to
    splitting the explicit widget_id.
    """
    scope = getattr(event, "scope", None)
    event_id = getattr(event, "id", None)

    if isinstance(scope, tuple) and scope:
        return scope[0], scope[1:]

    if isinstance(scope, tuple) and not scope and event_id:
        return event_id, ()

    # Timer or other non-widget event -- split the widget ID
    local_id, parent_scope = split_scoped_id(widget_id)
    return local_id, parent_scope


# ---------------------------------------------------------------------------
# Subscription collection with tag namespacing
# ---------------------------------------------------------------------------


def collect_subscriptions(registry: WidgetRegistry) -> list[Subscription]:
    """Collect subscriptions from all registered canvas widgets.

    Tags are namespaced with the widget ID to prevent collisions.
    """
    result: list[Subscription] = []
    for widget_id, entry in registry.items():
        try:
            subs = entry.definition.subscribe(entry.props, entry.state)
        except Exception:
            logger.warning(
                "canvas_widget %s subscribe() raised",
                widget_id,
                exc_info=True,
            )
            continue

        for sub in subs:
            namespaced = sub.map_tag(
                lambda tag, wid=widget_id: (  # type: ignore[misc]
                    "__canvas_widget__",
                    wid,
                    tag,
                )
            )
            result.append(namespaced)
    return result


def maybe_handle_timer(
    registry: WidgetRegistry,
    tag: Any,
) -> tuple[bool, Any | None, WidgetRegistry]:
    """Check if a timer event is for a canvas widget subscription.

    Returns ``(handled, event_or_none, registry)``.
    """
    if not (isinstance(tag, tuple) and len(tag) == 3 and tag[0] == "__canvas_widget__"):
        return False, None, registry

    _, widget_id, inner_tag = tag
    entry = registry.get(widget_id)
    if entry is None:
        return False, None, registry

    from plushie.events import TimerTick

    timer_event = TimerTick(tag=inner_tag, timestamp=0)

    try:
        action = entry.definition.handle_event(timer_event, entry.state)
    except Exception:
        logger.warning(
            "canvas_widget %s handle_event(timer) raised",
            widget_id,
            exc_info=True,
        )
        return True, None, registry

    if isinstance(action, _Emit):
        if action.state is not None:
            entry.state = action.state
        emit_id, emit_scope = _resolve_emit_identity(timer_event, widget_id)
        emitted = WidgetEvent(
            kind=action.kind,
            id=emit_id,
            value=action.data.get("value"),
            data=action.data,
            scope=emit_scope,
        )
        # Dispatch through remaining scope chain
        result_event, registry = dispatch_through_widgets(registry, emitted)
        return True, result_event, registry

    if isinstance(action, (_Consumed, _UpdateState)):
        if isinstance(action, _UpdateState):
            entry.state = action.state
        return True, None, registry

    return True, None, registry


__all__ = [
    "CanvasWidgetDef",
    "EventAction",
    "EventActionResult",
    "RegistryEntry",
    "WidgetRegistry",
    "collect_subscriptions",
    "derive_registry",
    "dispatch_through_widgets",
    "maybe_handle_timer",
]
