"""Event dataclasses for the plushie wire protocol.

Each wire event family maps to its own frozen dataclass with precisely
typed fields. Pattern match on class type in ``update()``::

    from plushie.events import Click, Input, KeyEvent

    match event:
        case Click(id="save"):
            handle_save(model)
        case Input(id="name", value=v):
            replace(model, name=v)
        case KeyEvent(type="press", key="Escape"):
            handle_escape(model)

Widget events carry ``id`` (the widget's local ID after scope splitting),
``window_id`` (the window that emitted the event), and ``scope`` (tuple
of ancestor container IDs, nearest first). For example, a button "save"
inside container "form" in window "main" produces
``Click(id="save", window_id="main", scope=("form",))``.

Subscription events (key, mouse, touch, IME) carry ``window_id``
(the window that was focused when the event fired, or ``""`` when
absent). Window lifecycle events carry ``window_id`` natively.
Runtime events (AsyncResult, StreamChunk, TimerTick, EffectResult)
are generated Python-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from plushie.types import KeyModifiers

# ---------------------------------------------------------------------------
# Helper types
# ---------------------------------------------------------------------------

type PointerType = Literal["mouse", "touch", "pen"]
"""Pointer device type."""

type PointerButton = Literal["left", "right", "middle", "back", "forward"] | str
"""Pointer button identifier.

Standard buttons use literal strings. Non-standard buttons use
arbitrary string names from the renderer.
"""

type ScrollUnit = Literal["line", "pixel"]
"""Scroll delta measurement unit.

``"line"`` for mouse wheel notches, ``"pixel"`` for trackpad smooth
scrolling.
"""

type KeyLocation = Literal["standard", "left", "right", "numpad"]
"""Physical key location on the keyboard."""

type EffectStatus = Literal["ok", "cancelled", "error"]
"""Platform effect result status."""


@dataclass(frozen=True, slots=True)
class ScrollData:
    """Widget scroll viewport data. All measurements in logical pixels.

    Attributes:
        absolute_x: Current horizontal scroll offset from content origin.
        absolute_y: Current vertical scroll offset from content origin.
        relative_x: Fractional horizontal position (0.0 = start, 1.0 = end).
        relative_y: Fractional vertical position (0.0 = start, 1.0 = end).
        bounds_width: Visible viewport width.
        bounds_height: Visible viewport height.
        content_width: Total scrollable content width.
        content_height: Total scrollable content height.
    """

    absolute_x: float
    absolute_y: float
    relative_x: float
    relative_y: float
    bounds_width: float
    bounds_height: float
    content_width: float
    content_height: float


# ---------------------------------------------------------------------------
# Widget events (scoped, carry id and scope)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Click:
    """A widget was clicked (button, clickable container, etc.).

    Wire family: ``click``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Input:
    """Text was entered into a text_input or text_editor widget.

    Wire family: ``input``.

    Attributes:
        value: The current text content of the input widget.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Submit:
    """A text input was submitted (e.g. user pressed Enter).

    Wire family: ``submit``.

    Attributes:
        value: The text content at time of submission.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Toggle:
    """A toggler or checkbox widget changed state.

    Wire family: ``toggle``.

    Attributes:
        value: The new boolean state of the toggle.
    """

    id: str
    value: bool
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Select:
    """An option was selected in a pick_list, combo_box, or radio widget.

    Wire family: ``select``.

    Attributes:
        value: The selected option string.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Slide:
    """A slider value changed during dragging.

    Wire family: ``slide``.

    Attributes:
        value: The current slider value.
    """

    id: str
    value: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SlideRelease:
    """A slider was released at its final value.

    Wire family: ``slide_release``.

    Attributes:
        value: The final slider value on release.
    """

    id: str
    value: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Scrolled:
    """A scrollable widget's viewport changed position.

    Wire family: ``scrolled``.

    Attributes:
        data: Full scroll viewport state including offsets, ratios,
            and dimensions.
    """

    id: str
    data: ScrollData
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Paste:
    """Text was pasted into a text input or text editor.

    Wire family: ``paste``.

    Attributes:
        value: The pasted text content.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Sort:
    """A sortable column header was clicked in a table widget.

    Wire family: ``sort``.

    Attributes:
        value: The column key that was clicked.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Open:
    """A collapsible or expandable widget was opened (e.g. combo_box dropdown).

    Wire family: ``open``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Close:
    """A collapsible or expandable widget was closed.

    Wire family: ``close``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OptionHovered:
    """An option in a pick_list or combo_box was hovered.

    Wire family: ``option_hovered``.

    Attributes:
        value: The hovered option string.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KeyBinding:
    """A registered key binding was triggered on a widget.

    Wire family: ``key_binding``.

    Attributes:
        value: The key binding identifier string.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LinkClicked:
    """A hyperlink in a link-capable widget was clicked.

    Wire family: ``link_click``. Emitted by widgets that render
    hyperlinked spans (``rich_text``, ``markdown``, and future link
    emitters).

    Attributes:
        link: The URL of the clicked link.
    """

    id: str
    link: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Focused:
    """A widget or canvas element received keyboard focus.

    Wire family: ``focused``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Blurred:
    """A widget or canvas element lost keyboard focus.

    Wire family: ``blurred``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WidgetStatus:
    """Widget interaction status changed (focus, hover, press, etc.).

    Wire family: ``status``. The runtime intercepts these to track
    focus state and derive Focused/Blurred events. This event is
    absorbed by the runtime and not delivered to ``update``.
    """

    id: str
    value: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Drag:
    """A widget or canvas element is being dragged.

    Wire family: ``drag``.

    Attributes:
        x: Current horizontal drag position.
        y: Current vertical drag position.
        delta_x: Horizontal movement since last drag event.
        delta_y: Vertical movement since last drag event.
        button: The mouse button name (e.g. ``"left"``).
    """

    id: str
    x: float
    y: float
    delta_x: float
    delta_y: float
    button: PointerButton = "left"
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DragEnd:
    """Drag ended on a widget or canvas element.

    Wire family: ``drag_end``.

    Attributes:
        x: Final horizontal position.
        y: Final vertical position.
        button: The mouse button name.
    """

    id: str
    x: float
    y: float
    button: PointerButton = "left"
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Enter:
    """Pointer entered a widget's bounds.

    Wire family: ``enter``.

    Attributes:
        id: Widget ID.
        x: Horizontal position in widget-local coordinates, or ``None``
            for widget-level enter events (populated when the source is
            a canvas element).
        y: Vertical position in widget-local coordinates, or ``None``
            for widget-level enter events (populated when the source is
            a canvas element).
        captured: Whether the event was captured by a parent widget.
        window_id: Source window ID.
        scope: Ancestor container IDs.
    """

    id: str
    x: float | None = None
    y: float | None = None
    captured: bool = False
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Exit:
    """Pointer left a widget's bounds.

    Wire family: ``exit``.

    Attributes:
        id: Widget ID.
        x: Horizontal position in widget-local coordinates, or ``None``
            for widget-level exit events (populated when the source is
            a canvas element).
        y: Vertical position in widget-local coordinates, or ``None``
            for widget-level exit events (populated when the source is
            a canvas element).
        captured: Whether the event was captured by a parent widget.
        window_id: Source window ID.
        scope: Ancestor container IDs.
    """

    id: str
    x: float | None = None
    y: float | None = None
    captured: bool = False
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RawEvent:
    """Catch-all for uncommon or future widget event types.

    Used when the wire ``family`` does not match any of the typed event
    classes above.

    Attributes:
        kind: The wire family string.
        value: The event value field (type varies by family).
        data: Additional event data (type varies by family).
        window_id: Runtime-delivered widget events always include this.
            Hand-built test events may leave it empty.
    """

    kind: str
    id: str
    value: Any
    data: Any
    window_id: str = ""
    scope: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Unified pointer events (scoped)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Press:
    """A pointer button was pressed on a widget.

    Wire family: ``press``. Replaces mouse_area right/middle/left press
    and canvas_press with a single type carrying full pointer metadata.

    Attributes:
        x: Horizontal position in widget-local coordinates.
        y: Vertical position in widget-local coordinates.
        button: The button name (e.g. ``"left"``, ``"right"``).
        pointer: The pointer device type.
        modifiers: Active keyboard modifiers at press time.
        finger: Touch finger identifier, or ``None`` for mouse/pen.
        captured: Whether the event was captured by a parent widget.
    """

    id: str
    x: float
    y: float
    button: PointerButton = "left"
    pointer: PointerType = "mouse"
    modifiers: KeyModifiers = field(default_factory=KeyModifiers)
    finger: int | None = None
    captured: bool = False
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Release:
    """A pointer button was released on a widget.

    Wire family: ``release``. Replaces mouse_area right/middle/left release
    and canvas_release. Also used for ``finger_lifted`` and ``finger_lost``.

    Attributes:
        x: Horizontal position in widget-local coordinates.
        y: Vertical position in widget-local coordinates.
        button: The button name.
        pointer: The pointer device type.
        modifiers: Active keyboard modifiers at release time.
        finger: Touch finger identifier, or ``None`` for mouse/pen.
        lost: ``True`` if the touch was lost (finger went out of range),
            ``False`` for a normal release.
    """

    id: str
    x: float
    y: float
    button: PointerButton = "left"
    pointer: PointerType = "mouse"
    modifiers: KeyModifiers = field(default_factory=KeyModifiers)
    finger: int | None = None
    lost: bool = False
    captured: bool = False
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Move:
    """Pointer moved within a widget.

    Wire family: ``move``. Replaces mouse_area move and canvas_move.

    Attributes:
        x: Horizontal position in widget-local coordinates.
        y: Vertical position in widget-local coordinates.
        pointer: The pointer device type.
        modifiers: Active keyboard modifiers during movement.
        finger: Touch finger identifier, or ``None`` for mouse/pen.
        captured: Whether the event was captured by a parent widget.
    """

    id: str
    x: float
    y: float
    pointer: PointerType = "mouse"
    modifiers: KeyModifiers = field(default_factory=KeyModifiers)
    finger: int | None = None
    captured: bool = False
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Scroll:
    """Pointer wheel scrolled within a widget.

    Wire family: ``scroll``.

    Attributes:
        x: Horizontal cursor position.
        y: Vertical cursor position.
        delta_x: Horizontal scroll delta.
        delta_y: Vertical scroll delta.
        unit: Scroll delta measurement unit (``"line"`` or ``"pixel"``).
        pointer: The pointer device type.
        modifiers: Active keyboard modifiers during scroll.
    """

    id: str
    x: float
    y: float
    delta_x: float
    delta_y: float
    unit: ScrollUnit = "line"
    pointer: PointerType = "mouse"
    modifiers: KeyModifiers = field(default_factory=KeyModifiers)
    captured: bool = False
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DoubleClick:
    """Double-click detected on a widget.

    Wire family: ``double_click``. Replaces MouseAreaDoubleClick.

    Attributes:
        x: Horizontal click position.
        y: Vertical click position.
        pointer: The pointer device type.
        modifiers: Active keyboard modifiers at click time.
    """

    id: str
    x: float
    y: float
    pointer: PointerType = "mouse"
    modifiers: KeyModifiers = field(default_factory=KeyModifiers)
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Resize:
    """A widget's rendered dimensions changed.

    Wire family: ``resize``. Replaces SensorResize.

    Attributes:
        width: New rendered width in logical pixels.
        height: New rendered height in logical pixels.
    """

    id: str
    width: float
    height: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Validation warning from the renderer.

    Wire family: ``diagnostic``.

    Attributes:
        level: Severity level (e.g. ``"warning"``).
        element_id: The element that triggered the diagnostic.
        code: Machine-readable diagnostic code.
        message: Human-readable diagnostic message.
        id: Originating widget or canvas ID (may be ``None``).
        window_id: Originating window ID (may be ``None``).
    """

    level: str
    element_id: str
    code: str
    message: str
    id: str | None = None
    window_id: str | None = None


@dataclass(frozen=True, slots=True)
class RendererDiagnostic:
    """Structured diagnostic emitted by the renderer.

    Wire message type: ``diagnostic`` (top-level, distinct from the
    legacy ``diagnostic`` event family used for canvas a11y
    validations). Carries a typed payload keyed by ``kind``.

    Attributes:
        session: Session the diagnostic is attributable to.
        level: Severity: ``"info"``, ``"warn"``, or ``"error"``.
        kind: Discriminator identifying the diagnostic variant
            (e.g. ``"font_family_not_found"``).
        details: The full typed payload dict as sent on the wire,
            including ``kind`` and any variant-specific fields.
    """

    session: str
    level: str
    kind: str
    details: dict[str, Any]


# ---------------------------------------------------------------------------
# Pane events (scoped)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PaneResized:
    """A pane_grid split divider was resized.

    Wire family: ``pane_resized``.

    Attributes:
        split: Pane split identifier (renderer-specific).
        ratio: New split position ratio (0.0 to 1.0).
    """

    id: str
    split: Any
    ratio: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PaneDragged:
    """A pane was dragged in a pane_grid.

    Wire family: ``pane_dragged``.

    Attributes:
        pane: The pane identifier being dragged.
        target: The drop target pane identifier.
        action: Drag action: ``"picked"``, ``"dropped"``, or ``"canceled"``.
        region: Drop region (e.g. ``"center"``, ``"top"``), or ``None``.
        edge: Drop edge hint, or ``None``.
    """

    id: str
    pane: Any
    target: Any
    action: str
    window_id: str = ""
    region: str | None = None
    edge: str | None = None
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PaneClicked:
    """A pane was clicked in a pane_grid, making it the active pane.

    Wire family: ``pane_clicked``.

    Attributes:
        pane: The clicked pane identifier.
    """

    id: str
    pane: Any
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PaneFocusCycle:
    """Focus cycled to the next pane in a pane_grid (e.g. via Tab/F6).

    Wire family: ``pane_focus_cycle``.

    Attributes:
        pane: The pane that received focus.
    """

    id: str
    pane: Any
    window_id: str = ""
    scope: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Key events (global, subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """A key was pressed or released.

    Wire families: ``key_press``, ``key_release``. Fired from keyboard
    subscriptions (global, with ``id=None``) or from widget-scoped key
    events (with ``id`` and ``scope`` populated). Match on ``type`` to
    distinguish press from release::

        case KeyEvent(type="press", key="Escape"):
            ...

    Attributes:
        type: ``"press"`` or ``"release"``.
        key: The logical key name (e.g. ``"a"``, ``"Enter"``, ``"ArrowUp"``).
        modified_key: The key value after applying modifier transforms
            (e.g. Shift+a produces ``"A"``). Falls back to ``key`` when
            no transform applies.
        modifiers: Current keyboard modifier state.
        physical_key: Physical key code (e.g. ``"KeyA"``), or ``None``
            when unavailable.
        location: Physical key location on the keyboard.
        text: Text input produced by this key press, or ``None`` for
            non-printable keys.
        repeat: Whether this is an auto-repeat event from holding the
            key. Always ``False`` for release events.
        captured: Whether a widget already consumed this event.
        window_id: The window that was focused, or ``""`` when absent.
        id: Widget ID for widget-scoped key events, ``None`` for
            subscription (global) key events.
        scope: Ancestor container IDs for widget-scoped key events.
    """

    type: Literal["press", "release"]
    key: str
    modified_key: str
    modifiers: KeyModifiers
    physical_key: str | None = None
    location: KeyLocation = "standard"
    text: str | None = None
    repeat: bool = False
    captured: bool = False
    window_id: str = ""
    id: str | None = None
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModifiersChanged:
    """The set of held modifier keys changed.

    Wire family: ``modifiers_changed``. Useful for updating UI hints
    (e.g. showing shortcut overlays) without waiting for a key event.

    Attributes:
        modifiers: The new modifier state.
        captured: Whether a widget already consumed this event.
        window_id: The window that was focused when modifiers changed,
            or ``""`` when absent.
    """

    modifiers: KeyModifiers
    captured: bool = False
    window_id: str = ""


# ---------------------------------------------------------------------------
# IME events (global, subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ImeEvent:
    """An Input Method Editor lifecycle step.

    Wire families: ``ime_opened``, ``ime_preedit``, ``ime_commit``,
    ``ime_closed``. Match on ``type`` to distinguish each step::

        case ImeEvent(type="commit", text=committed):
            ...

    Attributes:
        type: ``"opened"``, ``"preedit"``, ``"commit"``, or ``"closed"``.
        text: Current preedit or committed text; ``None`` for opened /
            closed events.
        cursor: Selection range inside the preedit string as a
            ``(start, end)`` byte-offset tuple, or ``None``.
        captured: Whether a widget already consumed this event.
        window_id: The window with IME focus, or ``""`` if absent.
    """

    type: Literal["opened", "preedit", "commit", "closed"]
    text: str | None = None
    cursor: tuple[int, int] | None = None
    captured: bool = False
    window_id: str = ""


# ---------------------------------------------------------------------------
# Window events (global, subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WindowEvent:
    """A window lifecycle event.

    Wire families: ``window_opened``, ``window_closed``,
    ``window_close_requested``, ``window_resized``, ``window_moved``,
    ``window_focused``, ``window_unfocused``, ``window_rescaled``,
    ``file_hovered``, ``file_dropped``, ``files_hovered_left``. Match
    on ``type`` to distinguish each event::

        case WindowEvent(type="resized", width=w, height=h):
            ...

    Attributes:
        type: The lifecycle event kind.
        window_id: The window the event applies to.
        width: New width for ``"opened"`` and ``"resized"`` events.
        height: New height for ``"opened"`` and ``"resized"`` events.
        x: New horizontal position for ``"moved"`` events.
        y: New vertical position for ``"moved"`` events.
        scale_factor: Scale factor for ``"opened"`` and ``"rescaled"``.
        path: File path for ``"file_hovered"`` and ``"file_dropped"``.
        position_x: Initial screen x on ``"opened"`` when available.
        position_y: Initial screen y on ``"opened"`` when available.
    """

    type: Literal[
        "opened",
        "closed",
        "close_requested",
        "resized",
        "moved",
        "focused",
        "unfocused",
        "rescaled",
        "file_hovered",
        "file_dropped",
        "files_hovered_left",
    ]
    window_id: str = ""
    width: float | None = None
    height: float | None = None
    x: float | None = None
    y: float | None = None
    scale_factor: float | None = None
    path: str | None = None
    position_x: float | None = None
    position_y: float | None = None


# ---------------------------------------------------------------------------
# System / query events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnimationFrame:
    """An animation frame tick with a monotonic timestamp.

    Wire family: ``animation_frame``. Only fires when
    ``on_animation_frame`` is subscribed.

    Attributes:
        timestamp: Monotonic timestamp in milliseconds.
    """

    timestamp: float


@dataclass(frozen=True, slots=True)
class TransitionComplete:
    """A renderer-side animation finished.

    Wire family: ``transition_complete``. Fired when a Transition or
    Sequence with an ``on_complete`` tag finishes its animation.

    Attributes:
        id: Widget that owns the animated property.
        tag: The ``on_complete`` tag from the animation descriptor.
        prop: The property name that completed (e.g. ``"opacity"``).
        window_id: Window containing the widget.
        scope: Ancestor container IDs (nearest first).
    """

    id: str
    tag: str | None
    prop: str | None
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ThemeChanged:
    """The OS theme preference changed at runtime.

    Wire family: ``theme_changed``.

    Attributes:
        theme: The new theme preference (``"light"`` or ``"dark"``).
    """

    theme: str


@dataclass(frozen=True, slots=True)
class AllWindowsClosed:
    """All windows have been closed.

    Wire family: ``all_windows_closed``. Typically used to trigger
    app exit.
    """


@dataclass(frozen=True, slots=True)
class SystemInfo:
    """Response to a GetSystemInfo query.

    Wire family: ``system_info`` (via ``op_query_response``).

    Attributes:
        tag: The tag from the originating query command.
        value: System info dict with keys like ``"cpu_brand"``,
            ``"memory_total"``, etc.
    """

    tag: str
    value: Any


@dataclass(frozen=True, slots=True)
class SystemTheme:
    """Response to a GetSystemTheme query.

    Wire family: ``system_theme`` (via ``op_query_response``).

    Attributes:
        tag: The tag from the originating query command.
        theme: The current OS theme (``"light"``, ``"dark"``, or ``"none"``).
    """

    tag: str
    theme: str


@dataclass(frozen=True, slots=True)
class ImageList:
    """Response to a ListImages query.

    Wire family: ``list_images`` (via ``op_query_response``).

    Attributes:
        tag: The tag from the originating query command.
        handles: List of registered image handle name strings.
    """

    tag: str
    handles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FocusedWidget:
    """Response to a FindFocused query.

    Wire family: ``find_focused`` (via ``op_query_response``).

    Attributes:
        tag: The tag from the originating query command.
        widget_id: ID of the focused widget, or ``None`` if no widget
            has focus.
    """

    tag: str
    widget_id: str | None


@dataclass(frozen=True, slots=True)
class TreeHash:
    """Response to a TreeHashQuery.

    Wire family: ``tree_hash`` (via ``op_query_response``).

    Attributes:
        tag: The tag from the originating query command.
        hash: SHA-256 hex string of the current renderer tree state.
    """

    tag: str
    hash: str


# ---------------------------------------------------------------------------
# Error / announce events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DuplicateNodeIds:
    """The tree contains duplicate node IDs after normalization.

    Wire family: ``duplicate_node_ids`` (via ``error``). Usually
    indicates a bug in the view function.

    Attributes:
        details: List or description of the duplicate IDs.
    """

    details: Any


@dataclass(frozen=True, slots=True)
class CommandError:
    """Renderer error for a widget-targeted command.

    Wire family: ``error`` with ``id = "command"``.

    Attributes:
        reason: Machine-readable error reason.
        id: Target widget ID when known.
        family: Command family name when known.
        widget: Widget type name when known.
        message: Human-readable error text.
    """

    reason: str
    id: str | None = None
    family: str | None = None
    widget: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class RendererError:
    """A renderer-side error event that is not a typed protocol error."""

    id: str
    data: Any


@dataclass(frozen=True, slots=True)
class RecoveryFailed:
    """Dispatched when handle_renderer_exit() raises an exception.

    Contains information about the recovery callback failure so the
    app can react (show an error, reset to safe state, etc.).

    This event is generated Python-side, never on the wire.
    """

    kind: str
    error: str
    renderer_exit: RendererExitInfo


@dataclass(frozen=True, slots=True)
class RendererExitInfo:
    """Structured renderer exit reason passed to handle_renderer_exit().

    Use ``build_renderer_exit()`` to construct from raw exit reasons.
    """

    type: str
    message: str
    details: Any = None


def build_renderer_exit(reason: Any) -> RendererExitInfo:
    """Convert a raw renderer exit reason into a structured RendererExitInfo.

    Maps raw reasons to typed exit info:
    - ``"normal"`` or ``"shutdown"`` -> type ``"shutdown"``
    - ``"heartbeat_timeout"`` -> type ``"heartbeat_timeout"``
    - ``{"exit_status": status}`` -> type ``"crash"`` with status as details
    - anything else -> type ``"crash"`` with the raw reason as details
    """
    if reason == "normal":
        return RendererExitInfo(type="shutdown", message="renderer shut down normally")
    if reason == "shutdown":
        return RendererExitInfo(type="shutdown", message="renderer shut down")
    if reason == "heartbeat_timeout":
        return RendererExitInfo(
            type="heartbeat_timeout",
            message="renderer unresponsive (heartbeat timeout)",
        )
    if isinstance(reason, dict) and "exit_status" in reason:
        status = reason["exit_status"]
        return RendererExitInfo(
            type="crash",
            message=f"renderer crashed with exit status {status}",
            details=status,
        )
    return RendererExitInfo(
        type="crash",
        message=f"renderer exited unexpectedly: {reason!r}",
        details=reason,
    )


@dataclass(frozen=True, slots=True)
class Announce:
    """Request the system screen reader to announce text.

    Wire family: ``announce``.

    Attributes:
        text: The text to be announced.
    """

    text: str


# ---------------------------------------------------------------------------
# Effect response
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FileOpened:
    """A file was selected from an open-file dialog."""

    path: str


@dataclass(frozen=True, slots=True)
class FilesOpened:
    """Multiple files were selected from a multi-file open dialog."""

    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FileSaved:
    """A file path was chosen in a save dialog."""

    path: str


@dataclass(frozen=True, slots=True)
class DirectorySelected:
    """A directory was selected from a directory picker."""

    path: str


@dataclass(frozen=True, slots=True)
class DirectoriesSelected:
    """Multiple directories were selected from a multi-directory picker."""

    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClipboardText:
    """Clipboard text was read."""

    text: str


@dataclass(frozen=True, slots=True)
class ClipboardHtml:
    """Clipboard HTML was read. ``alt_text`` may be None."""

    html: str
    alt_text: str | None = None


@dataclass(frozen=True, slots=True)
class ClipboardWritten:
    """Clipboard write completed."""


@dataclass(frozen=True, slots=True)
class ClipboardCleared:
    """Clipboard was cleared."""


@dataclass(frozen=True, slots=True)
class NotificationShown:
    """An OS notification was shown."""


@dataclass(frozen=True, slots=True)
class EffectCancelled:
    """The user dismissed a dialog."""


@dataclass(frozen=True, slots=True)
class EffectTimeout:
    """The effect did not receive a response within its timeout."""


@dataclass(frozen=True, slots=True)
class EffectError:
    """A platform error occurred."""

    message: str


@dataclass(frozen=True, slots=True)
class EffectUnsupported:
    """The backend does not support this effect."""


@dataclass(frozen=True, slots=True)
class RendererRestarted:
    """The renderer restarted while this effect was in flight."""


EffectResultValue = (
    FileOpened
    | FilesOpened
    | FileSaved
    | DirectorySelected
    | DirectoriesSelected
    | ClipboardText
    | ClipboardHtml
    | ClipboardWritten
    | ClipboardCleared
    | NotificationShown
    | EffectCancelled
    | EffectTimeout
    | EffectError
    | EffectUnsupported
    | RendererRestarted
)


@dataclass(frozen=True, slots=True)
class EffectResult:
    """Response to a platform Effect command (file dialog, clipboard, etc.).

    Wire type: ``effect_response``.

    Attributes:
        tag: The tag from the originating effect command.
        result: A typed result dataclass (``FileOpened``, ``ClipboardText``,
            ``EffectCancelled``, ``EffectTimeout``, etc.). Pattern match
            on the dataclass type to branch on the outcome.

    Example:
        match event:
            case EffectResult(tag="import", result=FileOpened(path=p)):
                load_file(p)
            case EffectResult(tag="import", result=EffectCancelled()):
                ...
    """

    tag: str
    result: EffectResultValue


def decode_effect_result(
    kind: str, status: str, result: Any, error: str | None
) -> EffectResultValue:
    """Decode a wire ``effect_response`` into a typed result dataclass.

    `kind` is the effect's original kind string (e.g. ``"file_open"``)
    tracked in the runtime alongside the user's tag. `status` is the
    wire status. `result` is the decoded ok-payload; `error` is the
    error reason.
    """
    if status == "cancelled":
        return EffectCancelled()
    if status == "unsupported":
        return EffectUnsupported()
    if status == "error":
        return EffectError(message=str(error) if error is not None else "")
    if status != "ok":
        return EffectError(message=f"unknown effect status: {status}")

    payload = result if isinstance(result, dict) else {}

    if kind == "file_open":
        return FileOpened(path=_str(payload.get("path")))
    if kind == "file_open_multiple":
        return FilesOpened(paths=_tuple_str(payload.get("paths")))
    if kind == "file_save":
        return FileSaved(path=_str(payload.get("path")))
    if kind == "directory_select":
        return DirectorySelected(path=_str(payload.get("path")))
    if kind == "directory_select_multiple":
        return DirectoriesSelected(paths=_tuple_str(payload.get("paths")))
    if kind in ("clipboard_read", "clipboard_read_primary"):
        return ClipboardText(text=_str(payload.get("text")))
    if kind == "clipboard_read_html":
        return ClipboardHtml(
            html=_str(payload.get("html")),
            alt_text=(
                payload.get("alt_text")
                if isinstance(payload.get("alt_text"), str)
                else None
            ),
        )
    if kind in ("clipboard_write", "clipboard_write_html", "clipboard_write_primary"):
        return ClipboardWritten()
    if kind == "clipboard_clear":
        return ClipboardCleared()
    if kind == "notification":
        return NotificationShown()
    return EffectError(message=f"unknown effect kind: {kind}")


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _tuple_str(v: Any) -> tuple[str, ...]:
    if isinstance(v, (list, tuple)):
        return tuple(x for x in v if isinstance(x, str))
    return ()


# ---------------------------------------------------------------------------
# Runtime events (generated Python-side, never on the wire)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AsyncResult:
    """Result from a ``Command.task()`` async operation.

    Generated by the runtime when an async task completes. The ``tag``
    matches the tag passed to the originating ``Command.task()``.

    Attributes:
        tag: The task's identifying tag.
        value: The result value on success, or an Exception on failure.
    """

    tag: str
    value: Any


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """An intermediate value emitted by a ``Command.stream()`` operation.

    Generated by the runtime when a stream function calls its emit
    callback. The ``tag`` matches the originating ``Command.stream()``.

    Attributes:
        tag: The stream's identifying tag.
        value: The emitted value.
    """

    tag: str
    value: Any


@dataclass(frozen=True, slots=True)
class TimerTick:
    """A timer subscription fired.

    Generated by the runtime for ``Subscription.every()`` timers.

    Attributes:
        tag: The subscription's identifying tag.
        timestamp: Monotonic timestamp in milliseconds.
    """

    tag: str
    timestamp: int


# ---------------------------------------------------------------------------
# Session lifecycle events (multiplexed mode)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionError:
    """A multiplexed session encountered an error.

    Wire family: ``session_error``.

    Emitted by the multiplexed renderer when a session fails.
    Only relevant in multiplexed (pool) mode.

    Attributes:
        session: The session ID that errored.
        error: Error description from the renderer.
    """

    session: str
    error: str


@dataclass(frozen=True, slots=True)
class SessionClosed:
    """A multiplexed session was closed by the renderer.

    Wire family: ``session_closed``.

    Emitted by the multiplexed renderer when a session terminates.
    Only relevant in multiplexed (pool) mode.

    Attributes:
        session: The session ID that was closed.
        reason: Close reason from the renderer.
    """

    session: str
    reason: str


# ---------------------------------------------------------------------------
# Effect stub acknowledgement
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EffectStubAck:
    """Acknowledgement of an effect stub registration or unregistration.

    Wire types: ``effect_stub_register_ack`` or ``effect_stub_unregister_ack``.

    Attributes:
        kind: The effect kind that was stubbed.
        registered: ``True`` if this is a registration ack,
            ``False`` if unregistration.
    """

    kind: str
    registered: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def split_scoped_id(
    wire_id: str,
) -> tuple[str, tuple[str, ...], str | None]:
    """Split a wire-format scoped ID into local ID, reversed scope, and window.

    Handles the canonical ``window#scope/path/id`` format. The ``#``
    separates the window name from the widget path. The ``/`` separates
    scope segments within the path. The last segment is the local ``id``.

    Args:
        wire_id: The scoped ID string from the wire
            (e.g. ``"main#sidebar/form/email"``).

    Returns:
        A ``(local_id, scope, window)`` tuple. The scope is reversed
        (nearest parent first). Window is ``None`` when no ``#``
        separator is present.

    Examples:
        >>> split_scoped_id("save")
        ('save', (), None)
        >>> split_scoped_id("form/save")
        ('save', ('form',), None)
        >>> split_scoped_id("main#form/save")
        ('save', ('form',), 'main')
        >>> split_scoped_id("app/form/section/save")
        ('save', ('section', 'form', 'app'), None)
        >>> split_scoped_id("main#sidebar/form/email")
        ('email', ('form', 'sidebar'), 'main')
    """
    if not wire_id:
        return ("", (), None)

    window: str | None = None
    if "#" in wire_id:
        win, rest = wire_id.split("#", 1)
        if win:
            window = win
        else:
            rest = wire_id
    else:
        rest = wire_id

    parts = rest.split("/") if rest else []
    if not parts or not parts[0]:
        return ("", (), window)

    if len(parts) == 1:
        return (parts[0], (), window)

    *scope_parts, local_id = parts
    return (local_id, tuple(reversed(scope_parts)), window)


def target(
    event: Click
    | Input
    | Submit
    | Toggle
    | Select
    | Slide
    | SlideRelease
    | Scrolled
    | Paste
    | Sort
    | Open
    | Close
    | OptionHovered
    | KeyBinding
    | LinkClicked
    | RawEvent
    | Focused
    | Blurred
    | WidgetStatus
    | Drag
    | DragEnd
    | Enter
    | Exit
    | Press
    | Release
    | Move
    | Scroll
    | DoubleClick
    | Resize
    | PaneResized
    | PaneDragged
    | PaneClicked
    | PaneFocusCycle,
) -> str:
    """Reconstruct the full scoped ID path from a scoped event.

    Joins the reversed scope segments and the local ID with ``/``
    separators, producing the forward-order path suitable for
    ``Command.focus()`` and other ID-based operations.

    The window_id at the end of the scope tuple (added by the protocol
    decoder) is stripped before constructing the path.

    Args:
        event: Any event that carries ``id``, ``scope``, and
            ``window_id`` fields.

    Returns:
        The full path string (e.g. ``"form/section/save"``).

    Examples:
        >>> target(Click(id="save", scope=("section", "form", "main"), window_id="main"))
        'form/section/save'
        >>> target(Click(id="save"))
        'save'
    """
    scope = event.scope
    window_id = getattr(event, "window_id", "")
    # Strip window_id from the end of scope if present
    if scope and window_id and scope[-1] == window_id:
        scope = scope[:-1]
    if not scope:
        return event.id
    return "/".join((*reversed(scope), event.id))


# ---------------------------------------------------------------------------
# Union types
# ---------------------------------------------------------------------------

type ScopedWidgetEvent = (
    Click
    | Input
    | Submit
    | Toggle
    | Select
    | Slide
    | SlideRelease
    | Scrolled
    | Paste
    | Sort
    | Open
    | Close
    | OptionHovered
    | KeyBinding
    | LinkClicked
    | RawEvent
    | Focused
    | Blurred
    | WidgetStatus
    | Drag
    | DragEnd
    | Enter
    | Exit
    | Press
    | Release
    | Move
    | Scroll
    | DoubleClick
    | Resize
)
"""Union of all widget events that carry ``id`` and ``scope``."""

type PointerEvent = Press | Release | Move | Scroll | DoubleClick
"""Union of all unified pointer events."""

type PaneEvent = PaneResized | PaneDragged | PaneClicked | PaneFocusCycle
"""Union of all pane_grid events."""

type KeyboardEvent = KeyEvent | ModifiersChanged
"""Union of all keyboard events (key press / release plus modifier changes)."""

type SystemEvent = (
    AnimationFrame
    | ThemeChanged
    | TransitionComplete
    | AllWindowsClosed
    | SystemInfo
    | SystemTheme
    | ImageList
    | FocusedWidget
    | TreeHash
    | CommandError
    | RendererError
    | RecoveryFailed
)
"""Union of all system/query response events."""

type RuntimeEvent = AsyncResult | StreamChunk | TimerTick
"""Union of all runtime-generated events (never on the wire)."""

type Event = (
    ScopedWidgetEvent
    | Diagnostic
    | RendererDiagnostic
    | PaneEvent
    | KeyboardEvent
    | ImeEvent
    | WindowEvent
    | SystemEvent
    | DuplicateNodeIds
    | Announce
    | EffectResult
    | RuntimeEvent
    | SessionError
    | SessionClosed
)
"""Union of all event types that can arrive in ``update()``."""


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "AllWindowsClosed",
    "AnimationFrame",
    "Announce",
    "AsyncResult",
    "Blurred",
    "Click",
    "ClipboardCleared",
    "ClipboardHtml",
    "ClipboardText",
    "ClipboardWritten",
    "Close",
    "CommandError",
    "Diagnostic",
    "DirectoriesSelected",
    "DirectorySelected",
    "DoubleClick",
    "Drag",
    "DragEnd",
    "DuplicateNodeIds",
    "EffectCancelled",
    "EffectError",
    "EffectResult",
    "EffectResultValue",
    "EffectStatus",
    "EffectStubAck",
    "EffectTimeout",
    "EffectUnsupported",
    "Enter",
    "Event",
    "Exit",
    "FileOpened",
    "FileSaved",
    "FilesOpened",
    "Focused",
    "FocusedWidget",
    "ImageList",
    "ImeEvent",
    "Input",
    "KeyBinding",
    "KeyEvent",
    "KeyLocation",
    "KeyboardEvent",
    "LinkClicked",
    "ModifiersChanged",
    "Move",
    "NotificationShown",
    "Open",
    "OptionHovered",
    "PaneClicked",
    "PaneDragged",
    "PaneEvent",
    "PaneFocusCycle",
    "PaneResized",
    "Paste",
    "PointerButton",
    "PointerEvent",
    "PointerType",
    "Press",
    "RawEvent",
    "RecoveryFailed",
    "Release",
    "RendererDiagnostic",
    "RendererError",
    "RendererExitInfo",
    "RendererRestarted",
    "Resize",
    "RuntimeEvent",
    "ScopedWidgetEvent",
    "Scroll",
    "ScrollData",
    "ScrollUnit",
    "Scrolled",
    "Select",
    "SessionClosed",
    "SessionError",
    "Slide",
    "SlideRelease",
    "Sort",
    "StreamChunk",
    "Submit",
    "SystemEvent",
    "SystemInfo",
    "SystemTheme",
    "ThemeChanged",
    "TimerTick",
    "Toggle",
    "TransitionComplete",
    "TreeHash",
    "WidgetStatus",
    "WindowEvent",
    "build_renderer_exit",
    "decode_effect_result",
    "split_scoped_id",
    "target",
]
