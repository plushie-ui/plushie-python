"""Custom widget system for pure-Python widgets.

Widgets manage internal state, produce view trees as either canvas
shapes or compositions of built-in widgets, transform raw events into
semantic widget events, and follow iced's captured/ignored dispatch model.

**Canvas widget** (renders custom shapes)::

    from plushie.widget import WidgetDef, EventAction

    class StarRating(WidgetDef):
        def init(self, props):
            return {"hovered": None}

        def view(self, id, props, state):
            return canvas.canvas(id, canvas.group("star-0", ...))

        def handle_event(self, event, state):
            match event:
                case Click(id="star-0"):
                    return EventAction.emit("select", 1)
                case _:
                    return EventAction.ignored()

**Composite widget** (composes built-in widgets)::

    class NoteCard(WidgetDef):
        def init(self, props):
            return {}

        def view(self, id, props, state):
            return ui.container(id,
                ui.text(f"{id}/title", props.get("title", "")),
                ui.button(f"{id}/expand", "Read more"),
            )

        def handle_event(self, event, state):
            match event:
                case Click(id="expand"):
                    return EventAction.emit("open", None)
                case _:
                    return EventAction.ignored()

Build a placeholder node for your view tree::

    StarRating.build("stars", props={"max": 5, "value": 3})
    NoteCard.build("card-1", props={"title": "Hello", "body": "..."})
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from plushie.events import (
    Click,
    Close,
    Input,
    Open,
    OptionHovered,
    Paste,
    RawEvent,
    Select,
    Slide,
    SlideRelease,
    Sort,
    Submit,
    Toggle,
    split_scoped_id,
)
from plushie.subscriptions import Subscription

logger = logging.getLogger("plushie")


# ---------------------------------------------------------------------------
# Built-in event routing
# ---------------------------------------------------------------------------

# Maps wire family names to (event_class, carrier) where carrier is:
#   "none"  - no payload (just id/scope/window_id)
#   "value" - scalar in the event's `value` field
_BUILTIN_EVENT_MAP: dict[str, tuple[type, str]] = {
    "click": (Click, "none"),
    "input": (Input, "value"),
    "submit": (Submit, "value"),
    "toggle": (Toggle, "value"),
    "select": (Select, "value"),
    "slide": (Slide, "value"),
    "slide_release": (SlideRelease, "value"),
    "paste": (Paste, "value"),
    "open": (Open, "none"),
    "close": (Close, "none"),
    "option_hovered": (OptionHovered, "value"),
    "sort": (Sort, "value"),
}


# ---------------------------------------------------------------------------
# Event specs for custom widget events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EventSpec:
    """Declaration of a custom widget event's payload shape.

    Widgets declare their emitted events via ``event_specs`` on the
    class.  The framework validates emitted data against the spec at
    emit time, catching typos and structural mismatches immediately
    instead of letting them surface in the consumer's ``update()``.

    Three forms:

    **No payload** (just the event name)::

        EventSpec()

    **Scalar value** (goes in the event's ``value`` field)::

        EventSpec(value_type=int)
        EventSpec(value_type=float)

    **Structured data** (dict with named fields)::

        EventSpec(fields={"hue": float, "saturation": float})

    All fields are required by default. Use ``optional`` to mark
    fields that may be omitted from emitted data without error::

        EventSpec(fields={"hue": float, "modifier": str}, optional=("modifier",))

    Optional fields absent from emit data are silently omitted. When
    present, their type is still validated.

    Field types use Python's built-in types (``int``, ``float``,
    ``str``, ``bool``).  Use ``object`` for fields that accept any
    type.
    """

    fields: dict[str, type] | None = None
    """Field names and types for data-carrier events."""

    value_type: type | None = None
    """Expected type for value-carrier events."""

    optional: tuple[str, ...] = ()
    """Field names that may be omitted from emit data."""

    def __post_init__(self) -> None:
        if self.fields is not None and self.value_type is not None:
            raise ValueError(
                "EventSpec cannot have both fields and value_type. "
                "use fields for structured data or value_type for scalars"
            )
        if self.optional and self.fields is None:
            raise ValueError("EventSpec optional fields require a fields declaration")
        if self.optional:
            unknown = set(self.optional) - set(self.fields or ())
            if unknown:
                raise ValueError(
                    f"EventSpec optional fields not in fields: {sorted(unknown)}"
                )


def _validate_emit(
    kind: str,
    data: dict[str, Any],
    event_specs: dict[str, EventSpec],
    widget_name: str,
) -> None:
    """Validate emitted event data against the widget's event specs.

    Raises:
        ValueError: The event name is undeclared, or required fields
            are missing from the emitted data.
        TypeError: A field or value has the wrong type.
    """
    if not event_specs:
        return

    spec = event_specs.get(kind)

    # Undeclared event name
    if spec is None and kind not in _BUILTIN_EVENT_MAP:
        declared = sorted(event_specs.keys())
        raise ValueError(
            f"{widget_name} emitted undeclared event {kind!r}. "
            f"Declared events: {declared}. "
            f"Declare it in event_specs or emit a built-in event name."
        )

    if spec is None:
        # Built-in event; no custom spec to validate against
        return

    # Data-carrier: check required fields are present
    if spec.fields is not None:
        required_fields = [f for f in spec.fields if f not in spec.optional]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(
                f"{widget_name} event {kind!r} is missing declared fields: {missing}"
            )
        for field_name, field_type in spec.fields.items():
            if field_type is object:
                continue
            value = data.get(field_name)
            if value is not None and not isinstance(value, field_type):
                raise TypeError(
                    f"{widget_name} event {kind!r} field {field_name!r}: "
                    f"expected {field_type.__name__}, got {type(value).__name__}"
                )

    # Value-carrier: check value type
    if spec.value_type is not None and spec.value_type is not object:
        value = data.get("value")
        if value is not None and not isinstance(value, spec.value_type):
            raise TypeError(
                f"{widget_name} event {kind!r} value: "
                f"expected {spec.value_type.__name__}, got {type(value).__name__}"
            )


def _build_emitted_event(
    kind: str,
    data: dict[str, Any],
    *,
    id: str,
    window_id: str,
    scope: tuple[str, ...],
    event_specs: dict[str, EventSpec] | None = None,
    widget_name: str = "",
) -> Any:
    """Build a typed event from an emit action.

    When *kind* matches a built-in widget event family, constructs the
    corresponding typed dataclass (e.g. ``Select``, ``Toggle``).  This
    makes widget emissions indistinguishable from real widget events in
    the consumer's ``update()``.

    For unrecognized kinds, falls back to :class:`RawEvent`.

    If *event_specs* is provided, validates the emitted data against
    the widget's declared event specs before constructing the event.
    """
    # Validate against event specs if the widget declares them
    if event_specs:
        _validate_emit(kind, data, event_specs, widget_name)

    # Route to typed event class for built-in families
    builtin = _BUILTIN_EVENT_MAP.get(kind)
    if builtin is not None:
        cls, carrier = builtin
        if carrier == "value":
            return cls(
                id=id,
                value=data.get("value"),
                window_id=window_id,
                scope=scope,
            )
        # carrier == "none"
        return cls(id=id, window_id=window_id, scope=scope)

    # Custom event -> RawEvent
    return RawEvent(
        kind=kind,
        id=id,
        window_id=window_id,
        value=data.get("value"),
        data=data,
        scope=scope,
    )


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
    """Factory for widget event handler results."""

    @staticmethod
    def ignored() -> _Ignored:
        """Event not captured: continue to next handler."""
        return _Ignored()

    @staticmethod
    def consumed() -> _Consumed:
        """Event captured: suppress without output."""
        return _Consumed()

    @staticmethod
    def update_state(state: dict[str, Any]) -> _UpdateState:
        """Event captured: update internal state, no output."""
        return _UpdateState(state=state)

    @staticmethod
    def emit(
        kind: str,
        data: Any = None,
        *,
        state: dict[str, Any] | None = None,
    ) -> _Emit:
        """Event captured: emit a semantic widget event.

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
# Widget definition (ABC)
# ---------------------------------------------------------------------------


class WidgetDef(ABC):
    """Abstract base for custom widget definitions.

    Subclass and implement ``init`` and ``view``.

    Override ``handle_event`` for interactive widgets that need to
    intercept canvas element events, transform them into semantic
    widget events, or manage internal state.  The default returns
    ``EventAction.ignored()`` (transparent, events pass through
    to the app's ``update()``).

    Override ``subscribe`` for timer-based updates.

    Declare ``event_specs`` to document and validate emitted events::

        class ColorPicker(WidgetDef):
            event_specs: ClassVar[dict[str, EventSpec]] = {
                "change": EventSpec(fields={"hue": float, "saturation": float}),
                "cleared": EventSpec(),
            }

    When ``event_specs`` is declared, the framework validates emitted
    event names and data at emit time.  Undeclared event names raise
    ``ValueError``; mismatched data raises ``TypeError``.
    """

    event_specs: ClassVar[dict[str, EventSpec]] = {}
    """Custom event declarations for emit-time validation.

    Maps event family names to :class:`EventSpec` instances.  Empty
    dict (the default) disables validation. All event names are
    accepted.
    """

    @abstractmethod
    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        """Return initial internal state for a new widget instance.

        Args:
            props: The widget's resolved props.
        """
        ...

    @abstractmethod
    def view(
        self,
        widget_id: str,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the widget's view tree as a node dict.

        Args:
            widget_id: The widget's scoped ID.
            props: Resolved props.
            state: Current internal state.
        """
        ...

    def handle_event(
        self,
        event: Any,
        state: dict[str, Any],
    ) -> EventActionResult:
        """Handle an incoming event.

        The default implementation returns ``EventAction.ignored()``,
        making the widget transparent to events.  Override this to
        intercept events, emit semantic widget events, or update
        internal state.

        Args:
            event: The event (canvas element events, timer ticks, etc.).
            state: Current internal state.

        Returns:
            An ``EventAction`` result.
        """
        return EventAction.ignored()

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

    def cache_key(
        self,
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> Any:
        """Optional cache key derived from props and state.

        When this returns a non-``None`` value, the runtime records
        it alongside the widget's expanded view tree. On the next
        render, if the widget's cache key compares equal to the
        stored value, the cached view is reused and ``view()`` is
        not re-invoked.

        The default returns ``None``, which disables caching for the
        widget: ``view()`` runs every render. Override this for
        widgets whose ``view()`` is expensive and whose output
        depends on a small number of inputs.

        Example::

            def cache_key(self, props, state):
                return (props.get("source"), state.get("theme"))

        Args:
            props: Resolved props.
            state: Current internal state.

        Returns:
            A hashable-equal value, or ``None`` to disable caching.
        """
        return None

    @classmethod
    def build(
        cls,
        widget_id: str,
        *,
        props: dict[str, Any] | None = None,
        event_rate: int | None = None,
    ) -> dict[str, Any]:
        """Build a placeholder node for this widget.

        The placeholder carries the widget definition class and props
        in ``meta``. During normalization, the runtime detects these
        and renders them with the appropriate state.

        Args:
            widget_id: Widget ID.
            props: Widget props.
            event_rate: Maximum event frequency for renderer-side events.
        """
        resolved_props = dict(props or {})
        placeholder_props: dict[str, Any] = {}
        if event_rate is not None:
            placeholder_props["event_rate"] = event_rate
        return {
            "id": widget_id,
            "type": "canvas",
            "props": placeholder_props,
            "children": [],
            "meta": {
                "__widget__": cls,
                "__widget_props__": resolved_props,
            },
        }


type WidgetKey = tuple[str, str]


def _widget_key(window_id: str, widget_id: str) -> WidgetKey:
    return (window_id, widget_id)


def render_placeholder(
    node: dict[str, Any],
    window_id: str | None,
    scoped_id: str,
    local_id: str,
    registry: WidgetRegistry,
) -> tuple[WidgetKey, dict[str, Any], Any] | None:
    """Render a widget placeholder during normalization.

    Args:
        node: The placeholder node (has meta with __widget__).
        window_id: The containing window ID.
        scoped_id: The fully scoped ID for this node.
        local_id: The local (pre-scoped) ID passed to view().
        registry: Existing widget registry for state lookup.

    Returns:
        (key, rendered_node, entry) or None if rendering fails.
    """
    meta = node.get("meta", {})
    widget_cls = meta.get("__widget__")
    widget_props = meta.get("__widget_props__", {})
    if widget_cls is None:
        return None

    if not window_id:
        raise ValueError(f"widget {local_id!r} must be rendered inside a window")

    # Look up existing state or initialize
    key = _widget_key(window_id, scoped_id)
    existing = registry.get(key)
    if existing is not None and type(existing.definition) is widget_cls:
        instance = existing.definition
        state = existing.state
    else:
        instance = widget_cls()
        state = instance.init(widget_props)

    # Produce the widget's view tree
    rendered = instance.view(local_id, widget_props, state)
    if rendered is None:
        raise ValueError(
            f"{widget_cls.__name__}.view() returned None for widget {scoped_id!r} "
            f"(local id {local_id!r})"
        )
    if not isinstance(rendered, dict):
        raise ValueError(
            f"{widget_cls.__name__}.view() must return a dict for widget "
            f"{scoped_id!r} (local id {local_id!r}); got "
            f"{type(rendered).__name__}"
        )

    # Attach metadata to the rendered node for registry derivation
    entry = RegistryEntry(definition=instance, state=state, props=widget_props)
    rendered_with_meta = _with_widget_metadata(
        rendered,
        widget_cls=widget_cls,
        widget_props=widget_props,
        widget_state=state,
        widget_definition=instance,
    )
    rendered_with_meta["id"] = scoped_id
    return key, rendered_with_meta, entry


# ---------------------------------------------------------------------------
# Registry: derive from tree, dispatch events
# ---------------------------------------------------------------------------

type WidgetRegistry = dict[WidgetKey, RegistryEntry]


@dataclass(slots=True)
class RegistryEntry:
    """A registered widget instance."""

    definition: WidgetDef
    state: dict[str, Any]
    props: dict[str, Any]


def _with_widget_metadata(
    node: dict[str, Any],
    *,
    widget_cls: type[WidgetDef],
    widget_props: dict[str, Any],
    widget_state: dict[str, Any],
    widget_definition: WidgetDef,
) -> dict[str, Any]:
    rendered = dict(node)
    meta = dict(rendered.get("meta") or {})
    meta.update(
        {
            "__widget__": widget_cls,
            "__widget_props__": widget_props,
            "__widget_state__": widget_state,
            "__widget_definition__": widget_definition,
        }
    )
    rendered["meta"] = meta
    return rendered


def derive_registry(tree: dict[str, Any] | None) -> WidgetRegistry:
    """Derive the widget registry from the normalized tree.

    Walks the tree and extracts widget metadata from ``meta`` fields.
    Returns a flat dict keyed by scoped ID for O(1) dispatch lookups.
    """
    if tree is None:
        return {}
    registry: WidgetRegistry = {}
    _collect_entries(tree, registry, None)
    return registry


def _collect_entries(
    node: dict[str, Any],
    registry: WidgetRegistry,
    window_id: str | None,
) -> None:
    """Recursively collect widget entries from the tree."""
    current_window_id = node.get("id") if node.get("type") == "window" else window_id
    meta = node.get("meta")
    if isinstance(meta, dict):
        widget_cls = meta.get("__widget__")
        if widget_cls is not None and isinstance(widget_cls, type):
            if not current_window_id:
                raise ValueError(
                    f"widget {node.get('id', '')!r} must be rendered inside a window"
                )
            node_id = node.get("id", "")
            state = meta.get("__widget_state__", {})
            props = meta.get("__widget_props__", {})
            instance = meta.get("__widget_definition__")
            if isinstance(instance, WidgetDef):
                registry[_widget_key(str(current_window_id), str(node_id))] = (
                    RegistryEntry(definition=instance, state=state, props=props)
                )

    for child in node.get("children", []):
        if isinstance(child, dict):
            _collect_entries(child, registry, current_window_id)


# ---------------------------------------------------------------------------
# Event dispatch through widget scope chain
# ---------------------------------------------------------------------------


def dispatch_through_widgets(
    registry: WidgetRegistry,
    event: Any,
) -> tuple[Any | None, WidgetRegistry, bool]:
    """Dispatch an event through the widget handler chain.

    Builds an ordered list of handlers from the event's scope (innermost
    to outermost) and walks it following iced's captured/ignored model.

    Returns ``(event_or_none, updated_registry, state_changed)``.
    If no handler captures, the original event passes through with
    ``state_changed=False``.
    """
    if not registry:
        return event, registry, False

    scope = getattr(event, "scope", None)
    event_id = getattr(event, "id", None)
    window_id = getattr(event, "window_id", None)

    if scope is None or not isinstance(scope, tuple):
        return event, registry, False

    chain = _build_handler_chain(
        registry, str(window_id) if isinstance(window_id, str) else None, scope
    )

    if not chain and event_id and isinstance(window_id, str):
        # Check if the event's target itself is a widget
        target_id = _widget_key(window_id, _scope_to_id(window_id, scope, event_id))
        entry = registry.get(target_id)
        if entry is not None:
            chain = [(target_id, entry)]

    if not chain:
        return event, registry, False

    return _walk_chain(registry, event, chain)


def _build_handler_chain(
    registry: WidgetRegistry,
    window_id: str | None,
    scope: tuple[str, ...],
) -> list[tuple[WidgetKey, RegistryEntry]]:
    """Build handler chain from scope, innermost to outermost.

    Strips the window_id from the end of the scope (appended by the
    protocol decoder), reverses the remaining ancestors to forward
    order, and builds canonical ``window#path`` keys for registry lookup.
    """
    if not scope or window_id is None:
        return []

    ancestors = list(scope)
    if ancestors and ancestors[-1] == window_id:
        ancestors = ancestors[:-1]
    if not ancestors:
        return []

    forward = list(reversed(ancestors))
    chain: list[tuple[WidgetKey, RegistryEntry]] = []

    for n in range(len(forward), 0, -1):
        path = "/".join(forward[:n])
        full_id = f"{window_id}#{path}"
        key = _widget_key(window_id, full_id)
        entry = registry.get(key)
        if entry is not None:
            chain.append((key, entry))

    return chain


def _scope_to_id(window_id: str | None, scope: tuple[str, ...], local_id: str) -> str:
    """Reconstruct canonical wire ID from window, reversed scope, and local ID.

    Strips the window_id from the end of scope (appended by the protocol
    decoder) before building the path. Produces ``window#path/id`` format.
    """
    ancestors = list(scope)
    if window_id and ancestors and ancestors[-1] == window_id:
        ancestors = ancestors[:-1]

    if not ancestors:
        return f"{window_id}#{local_id}" if window_id else local_id

    path = "/".join((*reversed(ancestors), local_id))
    return f"{window_id}#{path}" if window_id else path


def _walk_chain(
    registry: WidgetRegistry,
    event: Any,
    chain: list[tuple[WidgetKey, RegistryEntry]],
) -> tuple[Any | None, WidgetRegistry, bool]:
    """Walk the handler chain, dispatching through each widget.

    Returns ``(event_or_none, registry, state_changed)`` where
    ``state_changed`` is True if any widget's internal state was updated.
    """
    state_changed = False
    for widget_key, entry in chain:
        try:
            action = entry.definition.handle_event(event, entry.state)
        except Exception:
            logger.warning(
                "widget %s.%s (%s) raised in handle_event",
                type(entry.definition).__module__,
                type(entry.definition).__name__,
                widget_key,
                exc_info=True,
            )
            action = EventAction.ignored()

        if isinstance(action, _Ignored):
            continue

        if isinstance(action, _Consumed):
            return None, registry, state_changed

        if isinstance(action, _UpdateState):
            entry.state = action.state
            return None, registry, True

        if isinstance(action, _Emit):
            if action.state is not None:
                entry.state = action.state
                state_changed = True

            emit_window_id, emit_id, emit_scope = _resolve_emit_identity(
                event, widget_key
            )
            widget_cls = type(entry.definition)
            event = _build_emitted_event(
                action.kind,
                action.data,
                id=emit_id,
                window_id=emit_window_id,
                scope=emit_scope,
                event_specs=widget_cls.event_specs or None,
                widget_name=widget_cls.__name__,
            )

    return event, registry, state_changed


def _resolve_emit_identity(
    event: Any,
    widget_key: WidgetKey,
) -> tuple[str, str, tuple[str, ...]]:
    """Resolve the ID and scope for emitted events.

    For widget events (which carry scope), the widget's ID is
    the first scope element. For non-widget events, falls back to
    splitting the explicit widget_id.
    """
    scope = getattr(event, "scope", None)
    event_id = getattr(event, "id", None)

    if isinstance(scope, tuple) and scope:
        return widget_key[0], scope[0], scope[1:]

    if isinstance(scope, tuple) and not scope and event_id:
        return widget_key[0], event_id, ()

    # Timer or other non-widget event; split the widget ID
    local_id, parent_scope, _window = split_scoped_id(widget_key[1])
    return widget_key[0], local_id, parent_scope


# ---------------------------------------------------------------------------
# Subscription collection with tag namespacing
# ---------------------------------------------------------------------------


def collect_subscriptions(registry: WidgetRegistry) -> list[Subscription]:
    """Collect subscriptions from all registered widgets.

    Tags are namespaced with the window-local widget key to prevent collisions.
    """
    result: list[Subscription] = []
    for widget_id, entry in registry.items():
        try:
            subs = entry.definition.subscribe(entry.props, entry.state)
        except Exception:
            logger.warning(
                "widget %s subscribe() raised",
                widget_id,
                exc_info=True,
            )
            continue

        for sub in subs:
            namespaced = sub.map_tag(
                lambda tag, wid=widget_id: (  # type: ignore[misc]
                    "__widget__",
                    wid[0],
                    wid[1],
                    tag,
                )
            )
            result.append(namespaced)
    return result


def maybe_handle_timer(
    registry: WidgetRegistry,
    tag: Any,
) -> tuple[bool, Any | None, WidgetRegistry]:
    """Check if a timer event is for a widget subscription.

    Returns ``(handled, event_or_none, registry)``.
    """
    if not (isinstance(tag, tuple) and len(tag) == 4 and tag[0] == "__widget__"):
        return False, None, registry

    _, window_id, widget_id, inner_tag = tag
    key = _widget_key(str(window_id), str(widget_id))
    entry = registry.get(key)
    if entry is None:
        return False, None, registry

    from plushie.events import TimerTick

    timer_event = TimerTick(tag=inner_tag, timestamp=0)

    try:
        action = entry.definition.handle_event(timer_event, entry.state)
    except Exception:
        logger.warning(
            "widget %s handle_event(timer) raised",
            key,
            exc_info=True,
        )
        return True, None, registry

    if isinstance(action, _Emit):
        if action.state is not None:
            entry.state = action.state
        emit_window_id, emit_id, emit_scope = _resolve_emit_identity(timer_event, key)
        widget_cls = type(entry.definition)
        emitted = _build_emitted_event(
            action.kind,
            action.data,
            id=emit_id,
            window_id=emit_window_id,
            scope=emit_scope,
            event_specs=widget_cls.event_specs or None,
            widget_name=widget_cls.__name__,
        )
        # Dispatch through remaining scope chain
        result_event, registry, _changed = dispatch_through_widgets(registry, emitted)
        return True, result_event, registry

    if isinstance(action, (_Consumed, _UpdateState)):
        if isinstance(action, _UpdateState):
            entry.state = action.state
        return True, None, registry

    return True, None, registry


__all__ = [
    "EventAction",
    "EventActionResult",
    "EventSpec",
    "RegistryEntry",
    "WidgetDef",
    "WidgetRegistry",
    "collect_subscriptions",
    "derive_registry",
    "dispatch_through_widgets",
    "maybe_handle_timer",
    "render_placeholder",
]
