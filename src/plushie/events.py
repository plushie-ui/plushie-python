"""Event dataclasses for the plushie wire protocol.

Each wire event family maps to its own frozen dataclass with precisely
typed fields. Pattern match on class type in ``update()``::

    from plushie.events import Click, Input, KeyPress

    match event:
        case Click(id="save"):
            handle_save(model)
        case Input(id="name", value=v):
            replace(model, name=v)
        case KeyPress(key="Escape"):
            handle_escape(model)

Widget events carry ``id`` (the widget's local ID after scope splitting),
``window_id`` (the window that emitted the event), and ``scope`` (tuple
of ancestor container IDs, nearest first). For example, a button "save"
inside container "form" in window "main" produces
``Click(id="save", window_id="main", scope=("form",))``.

Subscription events (key, mouse, touch, IME, window) are global and
carry no scope. Runtime events (AsyncResult, StreamChunk, TimerTick,
EffectResult) are generated Python-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from plushie.types import KeyModifiers

# ---------------------------------------------------------------------------
# Helper types
# ---------------------------------------------------------------------------

type MouseButton = Literal["left", "right", "middle", "back", "forward"] | str
"""Mouse button identifier.

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
# Widget events -- scoped (carry id and scope)
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
class Scroll:
    """A scrollable widget's viewport changed position.

    Wire family: ``scroll``.

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
class WidgetEvent:
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
# MouseArea events -- scoped
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MouseAreaRightPress:
    """Right mouse button pressed inside a mouse_area widget.

    Wire family: ``mouse_right_press``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaRightRelease:
    """Right mouse button released inside a mouse_area widget.

    Wire family: ``mouse_right_release``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaMiddlePress:
    """Middle mouse button pressed inside a mouse_area widget.

    Wire family: ``mouse_middle_press``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaMiddleRelease:
    """Middle mouse button released inside a mouse_area widget.

    Wire family: ``mouse_middle_release``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaDoubleClick:
    """Double-click detected inside a mouse_area widget.

    Wire family: ``mouse_double_click``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaEnter:
    """Mouse cursor entered a mouse_area widget's bounds.

    Wire family: ``mouse_enter``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaExit:
    """Mouse cursor exited a mouse_area widget's bounds.

    Wire family: ``mouse_exit``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaMove:
    """Mouse cursor moved within a mouse_area widget.

    Wire family: ``mouse_move``. Coordinates are in the widget's local space.

    Attributes:
        x: Horizontal cursor position in local coordinates.
        y: Vertical cursor position in local coordinates.
    """

    id: str
    x: float
    y: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MouseAreaScroll:
    """Mouse wheel scrolled inside a mouse_area widget.

    Wire family: ``mouse_scroll``.

    Attributes:
        delta_x: Horizontal scroll delta.
        delta_y: Vertical scroll delta.
    """

    id: str
    delta_x: float
    delta_y: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Canvas events -- scoped
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CanvasPress:
    """A mouse button was pressed on a canvas widget.

    Wire family: ``canvas_press``.

    Attributes:
        x: Horizontal position in canvas local coordinates.
        y: Vertical position in canvas local coordinates.
        button: The mouse button name (e.g. ``"left"``, ``"right"``).
    """

    id: str
    x: float
    y: float
    button: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasRelease:
    """A mouse button was released on a canvas widget.

    Wire family: ``canvas_release``.

    Attributes:
        x: Horizontal position in canvas local coordinates.
        y: Vertical position in canvas local coordinates.
        button: The mouse button name.
    """

    id: str
    x: float
    y: float
    button: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasMove:
    """The mouse cursor moved within a canvas widget.

    Wire family: ``canvas_move``.

    Attributes:
        x: Horizontal position in canvas local coordinates.
        y: Vertical position in canvas local coordinates.
    """

    id: str
    x: float
    y: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasScroll:
    """The mouse wheel was scrolled within a canvas widget.

    Wire family: ``canvas_scroll``.

    Attributes:
        x: Horizontal cursor position.
        y: Vertical cursor position.
        delta_x: Horizontal scroll delta.
        delta_y: Vertical scroll delta.
    """

    id: str
    x: float
    y: float
    delta_x: float
    delta_y: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Canvas shape events -- scoped
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CanvasElementEnter:
    """Mouse entered an interactive canvas element's bounds.

    Wire family: ``canvas_element_enter``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        x: Horizontal cursor position.
        y: Vertical cursor position.
        captured: Whether a subscription already consumed this event.
    """

    id: str
    element_id: str
    x: float
    y: float
    window_id: str = ""
    captured: bool = False
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementLeave:
    """Mouse left an interactive canvas element's bounds.

    Wire family: ``canvas_element_leave``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        captured: Whether a subscription already consumed this event.
    """

    id: str
    element_id: str
    window_id: str = ""
    captured: bool = False
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementClick:
    """An interactive canvas element was clicked.

    Wire family: ``canvas_element_click``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        x: Horizontal click position.
        y: Vertical click position.
        button: The mouse button name, or ``"keyboard"`` when activated
            via Enter/Space.
        captured: Whether a subscription already consumed this event.
    """

    id: str
    element_id: str
    x: float
    y: float
    button: str
    window_id: str = ""
    captured: bool = False
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementDrag:
    """An interactive canvas element is being dragged.

    Wire family: ``canvas_element_drag``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        x: Current horizontal drag position.
        y: Current vertical drag position.
        delta_x: Horizontal movement since last drag event.
        delta_y: Vertical movement since last drag event.
        captured: Whether a subscription already consumed this event.
    """

    id: str
    element_id: str
    x: float
    y: float
    delta_x: float
    delta_y: float
    window_id: str = ""
    captured: bool = False
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementDragEnd:
    """Drag ended on an interactive canvas element.

    Wire family: ``canvas_element_drag_end``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        x: Final horizontal position.
        y: Final vertical position.
        captured: Whether a subscription already consumed this event.
    """

    id: str
    element_id: str
    x: float
    y: float
    window_id: str = ""
    captured: bool = False
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementFocused:
    """An interactive canvas element received keyboard focus.

    Wire family: ``canvas_element_focused``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        captured: Whether a subscription already consumed this event.
    """

    id: str
    element_id: str
    window_id: str = ""
    captured: bool = False
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementBlurred:
    """An interactive canvas element lost keyboard focus.

    Wire family: ``canvas_element_blurred``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        captured: Whether a subscription already consumed this event.
    """

    id: str
    element_id: str
    window_id: str = ""
    captured: bool = False
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementKeyPress:
    """A key was pressed while a canvas element has focus.

    Wire family: ``canvas_element_key_press``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        key: The logical key name (e.g. ``"ArrowRight"``, ``"Enter"``).
        modifiers: Modifier state (string-keyed bool map from wire).
    """

    id: str
    element_id: str
    key: str
    modifiers: dict[str, bool] = field(default_factory=dict)
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasElementKeyRelease:
    """A key was released while a canvas element has focus.

    Wire family: ``canvas_element_key_release``.

    Attributes:
        element_id: The interactive element's identifier within the canvas.
        key: The logical key name.
        modifiers: Modifier state (string-keyed bool map from wire).
    """

    id: str
    element_id: str
    key: str
    modifiers: dict[str, bool] = field(default_factory=dict)
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasFocused:
    """The canvas widget gained iced focus (no coordinates).

    Wire family: ``canvas_focused``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasBlurred:
    """The canvas widget lost iced focus (no coordinates).

    Wire family: ``canvas_blurred``.
    """

    id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasGroupFocused:
    """A focusable group within the canvas was entered.

    Wire family: ``canvas_group_focused``.

    Attributes:
        group_id: The focusable group's identifier within the canvas.
    """

    id: str
    group_id: str
    window_id: str = ""
    scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanvasGroupBlurred:
    """A focusable group within the canvas was exited.

    Wire family: ``canvas_group_blurred``.

    Attributes:
        group_id: The focusable group's identifier within the canvas.
    """

    id: str
    group_id: str
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
    """

    level: str
    element_id: str
    code: str
    message: str


# ---------------------------------------------------------------------------
# Sensor events -- scoped
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SensorResize:
    """A sensor widget detected that its rendered dimensions changed.

    Wire family: ``sensor_resize``.

    Attributes:
        width: New rendered width in logical pixels.
        height: New rendered height in logical pixels.
    """

    id: str
    width: float
    height: float
    window_id: str = ""
    scope: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Pane events -- scoped
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
# Key events -- global (subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeyPress:
    """A key was pressed.

    Wire family: ``key_press``. Fired from keyboard subscriptions.

    Attributes:
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
        repeat: Whether this is an auto-repeat event from holding the key.
        captured: Whether a widget already consumed this event.
    """

    key: str
    modified_key: str
    modifiers: KeyModifiers
    physical_key: str | None = None
    location: KeyLocation = "standard"
    text: str | None = None
    repeat: bool = False
    captured: bool = False


@dataclass(frozen=True, slots=True)
class KeyRelease:
    """A key was released.

    Wire family: ``key_release``. Fired from keyboard subscriptions.

    Attributes:
        key: The logical key name.
        modified_key: The key value after applying modifier transforms.
        modifiers: Current keyboard modifier state.
        physical_key: Physical key code, or ``None``.
        location: Physical key location on the keyboard.
        text: Text value, or ``None`` for non-printable keys.
        captured: Whether a widget already consumed this event.
    """

    key: str
    modified_key: str
    modifiers: KeyModifiers
    physical_key: str | None = None
    location: KeyLocation = "standard"
    text: str | None = None
    captured: bool = False


@dataclass(frozen=True, slots=True)
class ModifiersChanged:
    """The set of held modifier keys changed.

    Wire family: ``modifiers_changed``. Useful for updating UI hints
    (e.g. showing shortcut overlays) without waiting for a key event.

    Attributes:
        modifiers: The new modifier state.
        captured: Whether a widget already consumed this event.
    """

    modifiers: KeyModifiers
    captured: bool = False


# ---------------------------------------------------------------------------
# Mouse events -- global (subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MouseMove:
    """The mouse cursor moved to a new position.

    Wire family: ``cursor_moved``.

    Attributes:
        x: Horizontal cursor position.
        y: Vertical cursor position.
        captured: Whether a widget already consumed this event.
    """

    x: float
    y: float
    captured: bool = False


@dataclass(frozen=True, slots=True)
class MouseEnter:
    """The mouse cursor entered the application window.

    Wire family: ``cursor_entered``.

    Attributes:
        captured: Whether a widget already consumed this event.
    """

    captured: bool = False


@dataclass(frozen=True, slots=True)
class MouseLeave:
    """The mouse cursor left the application window.

    Wire family: ``cursor_left``.

    Attributes:
        captured: Whether a widget already consumed this event.
    """

    captured: bool = False


@dataclass(frozen=True, slots=True)
class MouseButtonPress:
    """A mouse button was pressed (global subscription).

    Wire family: ``button_pressed``.

    Attributes:
        button: The mouse button identifier.
        captured: Whether a widget already consumed this event.
    """

    button: str
    captured: bool = False


@dataclass(frozen=True, slots=True)
class MouseButtonRelease:
    """A mouse button was released (global subscription).

    Wire family: ``button_released``.

    Attributes:
        button: The mouse button identifier.
        captured: Whether a widget already consumed this event.
    """

    button: str
    captured: bool = False


@dataclass(frozen=True, slots=True)
class MouseWheel:
    """The mouse wheel was scrolled (global subscription).

    Wire family: ``wheel_scrolled``.

    Attributes:
        delta_x: Horizontal scroll delta.
        delta_y: Vertical scroll delta.
        unit: Whether deltas are in lines or pixels.
        captured: Whether a widget already consumed this event.
    """

    delta_x: float
    delta_y: float
    unit: ScrollUnit = "line"
    captured: bool = False


# ---------------------------------------------------------------------------
# Touch events -- global (subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TouchPress:
    """A finger touched the screen.

    Wire family: ``finger_pressed``.

    Attributes:
        finger_id: Unique identifier for the finger.
        x: Horizontal touch position.
        y: Vertical touch position.
        captured: Whether a widget already consumed this event.
    """

    finger_id: int
    x: float
    y: float
    captured: bool = False


@dataclass(frozen=True, slots=True)
class TouchMove:
    """A finger moved on the screen.

    Wire family: ``finger_moved``.

    Attributes:
        finger_id: Unique identifier for the finger.
        x: Current horizontal touch position.
        y: Current vertical touch position.
        captured: Whether a widget already consumed this event.
    """

    finger_id: int
    x: float
    y: float
    captured: bool = False


@dataclass(frozen=True, slots=True)
class TouchLift:
    """A finger was lifted from the screen.

    Wire family: ``finger_lifted``.

    Attributes:
        finger_id: Unique identifier for the finger.
        x: Final horizontal touch position.
        y: Final vertical touch position.
        captured: Whether a widget already consumed this event.
    """

    finger_id: int
    x: float
    y: float
    captured: bool = False


@dataclass(frozen=True, slots=True)
class TouchLost:
    """Touch tracking was interrupted by the OS.

    Wire family: ``finger_lost``.

    Attributes:
        finger_id: Unique identifier for the finger.
        x: Last known horizontal touch position.
        y: Last known vertical touch position.
        captured: Whether a widget already consumed this event.
    """

    finger_id: int
    x: float
    y: float
    captured: bool = False


# ---------------------------------------------------------------------------
# IME events -- global (subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ImeOpen:
    """The IME composition session started.

    Wire family: ``ime_opened``.

    Attributes:
        captured: Whether a widget already consumed this event.
    """

    captured: bool = False


@dataclass(frozen=True, slots=True)
class ImePreedit:
    """The IME is composing text.

    Wire family: ``ime_preedit``.

    Attributes:
        text: The current preedit composition string.
        cursor: Selection range within the preedit string as a
            ``(start, end)`` tuple of byte offsets, or ``None`` when
            no cursor info is available.
        captured: Whether a widget already consumed this event.
    """

    text: str
    cursor: tuple[int, int] | None = None
    captured: bool = False


@dataclass(frozen=True, slots=True)
class ImeCommit:
    """The IME committed final text to the input.

    Wire family: ``ime_commit``.

    Attributes:
        text: The committed text string.
        captured: Whether a widget already consumed this event.
    """

    text: str
    captured: bool = False


@dataclass(frozen=True, slots=True)
class ImeClose:
    """The IME composition session ended.

    Wire family: ``ime_closed``.

    Attributes:
        captured: Whether a widget already consumed this event.
    """

    captured: bool = False


# ---------------------------------------------------------------------------
# Window events -- global (subscription)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WindowOpen:
    """A window finished opening.

    Wire family: ``window_opened``.

    Attributes:
        window_id: The window's unique identifier.
        width: Initial window width in logical pixels.
        height: Initial window height in logical pixels.
        position_x: Initial horizontal screen position, or ``None``.
        position_y: Initial vertical screen position, or ``None``.
        scale_factor: DPI scale factor for the window's display.
    """

    window_id: str
    width: float
    height: float
    scale_factor: float
    position_x: float | None = None
    position_y: float | None = None


@dataclass(frozen=True, slots=True)
class WindowClosed:
    """A window was closed and destroyed.

    Wire family: ``window_closed``.

    Attributes:
        window_id: The closed window's identifier.
    """

    window_id: str


@dataclass(frozen=True, slots=True)
class WindowCloseRequested:
    """The user requested to close a window (e.g. clicked the X button).

    Wire family: ``window_close_requested``. Handle this to show
    confirmation dialogs or prevent accidental closure.

    Attributes:
        window_id: The window that received the close request.
    """

    window_id: str


@dataclass(frozen=True, slots=True)
class WindowResized:
    """A window was resized to new dimensions.

    Wire family: ``window_resized``.

    Attributes:
        window_id: The resized window's identifier.
        width: New width in logical pixels.
        height: New height in logical pixels.
    """

    window_id: str
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class WindowMoved:
    """A window was moved to a new screen position.

    Wire family: ``window_moved``.

    Attributes:
        window_id: The moved window's identifier.
        x: New horizontal position in logical pixels.
        y: New vertical position in logical pixels.
    """

    window_id: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class WindowFocused:
    """A window gained keyboard/input focus.

    Wire family: ``window_focused``.

    Attributes:
        window_id: The focused window's identifier.
    """

    window_id: str


@dataclass(frozen=True, slots=True)
class WindowUnfocused:
    """A window lost keyboard/input focus.

    Wire family: ``window_unfocused``.

    Attributes:
        window_id: The unfocused window's identifier.
    """

    window_id: str


@dataclass(frozen=True, slots=True)
class WindowRescaled:
    """A window's DPI scale factor changed (e.g. moved between monitors).

    Wire family: ``window_rescaled``.

    Attributes:
        window_id: The rescaled window's identifier.
        scale_factor: The new DPI scale factor.
    """

    window_id: str
    scale_factor: float


@dataclass(frozen=True, slots=True)
class FileHovered:
    """A file is being dragged over a window (not yet dropped).

    Wire family: ``file_hovered``.

    Attributes:
        window_id: The window the file is hovering over.
        path: File system path of the hovered file.
    """

    window_id: str
    path: str


@dataclass(frozen=True, slots=True)
class FileDropped:
    """A file was dropped onto a window.

    Wire family: ``file_dropped``.

    Attributes:
        window_id: The window the file was dropped on.
        path: File system path of the dropped file.
    """

    window_id: str
    path: str


@dataclass(frozen=True, slots=True)
class FilesHoveredLeft:
    """A previously hovered file drag left the window without dropping.

    Wire family: ``files_hovered_left``.

    Attributes:
        window_id: The window the file drag left.
    """

    window_id: str


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

    timestamp: int


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
        data: System info dict with keys like ``"cpu_brand"``,
            ``"memory_total"``, etc.
    """

    tag: str
    data: Any


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
class ExtensionCommandError:
    """Renderer error for an ``extension_command``.

    Wire family: ``error`` with ``id = "extension_command"``.

    Attributes:
        reason: Machine-readable error reason.
        node_id: Target widget node ID when known.
        op: Command operation name when known.
        extension: Extension widget type when known.
        message: Human-readable error text.
    """

    reason: str
    node_id: str | None = None
    op: str | None = None
    extension: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class RendererError:
    """A renderer-side error event that is not a typed protocol error."""

    id: str
    data: Any


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
class EffectResult:
    """Response to a platform Effect command (file dialog, clipboard, etc.).

    Wire type: ``effect_response``.

    Attributes:
        request_id: Correlates with the originating Effect command's ID.
        status: Result status: ``"ok"``, ``"cancelled"``, or ``"error"``.
        result: Result data when status is ``"ok"`` (shape depends on
            effect kind), ``None`` otherwise.
        error: Error message when status is ``"error"``, ``None`` otherwise.
    """

    request_id: str
    status: EffectStatus
    result: Any = None
    error: str | None = None


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
# Helpers
# ---------------------------------------------------------------------------


def split_scoped_id(wire_id: str) -> tuple[str, tuple[str, ...]]:
    """Split a wire-format scoped ID into local ID and reversed scope.

    Wire IDs use ``/`` as a scope separator. The last segment is the
    local widget ID; preceding segments form the scope (reversed, so
    the immediate parent is first).

    Args:
        wire_id: The scoped ID string from the wire (e.g. ``"form/section/save"``).

    Returns:
        A ``(local_id, scope)`` tuple. For ``"form/section/save"`` this
        returns ``("save", ("section", "form"))``.

    Examples:
        >>> split_scoped_id("save")
        ('save', ())
        >>> split_scoped_id("form/save")
        ('save', ('form',))
        >>> split_scoped_id("app/form/section/save")
        ('save', ('section', 'form', 'app'))
    """
    parts = wire_id.split("/")
    local_id = parts[-1]
    scope = tuple(reversed(parts[:-1]))
    return local_id, scope


def target(
    event: Click
    | Input
    | Submit
    | Toggle
    | Select
    | Slide
    | SlideRelease
    | Scroll
    | Paste
    | Sort
    | Open
    | Close
    | OptionHovered
    | KeyBinding
    | WidgetEvent
    | MouseAreaRightPress
    | MouseAreaRightRelease
    | MouseAreaMiddlePress
    | MouseAreaMiddleRelease
    | MouseAreaDoubleClick
    | MouseAreaEnter
    | MouseAreaExit
    | MouseAreaMove
    | MouseAreaScroll
    | CanvasPress
    | CanvasRelease
    | CanvasMove
    | CanvasScroll
    | CanvasElementEnter
    | CanvasElementLeave
    | CanvasElementClick
    | CanvasElementDrag
    | CanvasElementDragEnd
    | CanvasElementFocused
    | CanvasElementBlurred
    | CanvasElementKeyPress
    | CanvasElementKeyRelease
    | CanvasFocused
    | CanvasBlurred
    | CanvasGroupFocused
    | CanvasGroupBlurred
    | SensorResize
    | PaneResized
    | PaneDragged
    | PaneClicked
    | PaneFocusCycle,
) -> str:
    """Reconstruct the full scoped ID path from a scoped event.

    Joins the reversed scope segments and the local ID with ``/``
    separators, producing the forward-order path suitable for
    ``Command.focus()`` and other ID-based operations.

    Args:
        event: Any event that carries ``id`` and ``scope`` fields.

    Returns:
        The full path string (e.g. ``"form/section/save"``).

    Examples:
        >>> target(Click(id="save", scope=("section", "form")))
        'form/section/save'
        >>> target(Click(id="save"))
        'save'
    """
    scope = event.scope
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
    | Scroll
    | Paste
    | Sort
    | Open
    | Close
    | OptionHovered
    | KeyBinding
    | WidgetEvent
)
"""Union of all widget events that carry ``id`` and ``scope``."""

type MouseAreaEvent = (
    MouseAreaRightPress
    | MouseAreaRightRelease
    | MouseAreaMiddlePress
    | MouseAreaMiddleRelease
    | MouseAreaDoubleClick
    | MouseAreaEnter
    | MouseAreaExit
    | MouseAreaMove
    | MouseAreaScroll
)
"""Union of all mouse_area events."""

type CanvasEvent = CanvasPress | CanvasRelease | CanvasMove | CanvasScroll
"""Union of all raw canvas events."""

type CanvasElementEvent = (
    CanvasElementEnter
    | CanvasElementLeave
    | CanvasElementClick
    | CanvasElementDrag
    | CanvasElementDragEnd
    | CanvasElementFocused
    | CanvasElementBlurred
    | CanvasElementKeyPress
    | CanvasElementKeyRelease
)
"""Union of all interactive canvas element events."""

type CanvasLifecycleEvent = CanvasFocused | CanvasBlurred
"""Union of canvas focus lifecycle events (no coordinates)."""

type CanvasGroupEvent = CanvasGroupFocused | CanvasGroupBlurred
"""Union of canvas group focus events."""

type PaneEvent = PaneResized | PaneDragged | PaneClicked | PaneFocusCycle
"""Union of all pane_grid events."""

type KeyEvent = KeyPress | KeyRelease | ModifiersChanged
"""Union of all keyboard events."""

type MouseEvent = (
    MouseMove
    | MouseEnter
    | MouseLeave
    | MouseButtonPress
    | MouseButtonRelease
    | MouseWheel
)
"""Union of all global mouse subscription events."""

type TouchEvent = TouchPress | TouchMove | TouchLift | TouchLost
"""Union of all touch events."""

type ImeEvent = ImeOpen | ImePreedit | ImeCommit | ImeClose
"""Union of all IME events."""

type WindowEvent = (
    WindowOpen
    | WindowClosed
    | WindowCloseRequested
    | WindowResized
    | WindowMoved
    | WindowFocused
    | WindowUnfocused
    | WindowRescaled
    | FileHovered
    | FileDropped
    | FilesHoveredLeft
)
"""Union of all window lifecycle events."""

type SystemEvent = (
    AnimationFrame
    | ThemeChanged
    | AllWindowsClosed
    | SystemInfo
    | SystemTheme
    | ImageList
    | FocusedWidget
    | TreeHash
    | ExtensionCommandError
    | RendererError
)
"""Union of all system/query response events."""

type RuntimeEvent = AsyncResult | StreamChunk | TimerTick
"""Union of all runtime-generated events (never on the wire)."""

type Event = (
    ScopedWidgetEvent
    | MouseAreaEvent
    | CanvasEvent
    | CanvasElementEvent
    | CanvasLifecycleEvent
    | CanvasGroupEvent
    | Diagnostic
    | SensorResize
    | PaneEvent
    | KeyEvent
    | MouseEvent
    | TouchEvent
    | ImeEvent
    | WindowEvent
    | SystemEvent
    | DuplicateNodeIds
    | Announce
    | EffectResult
    | RuntimeEvent
)
"""Union of all event types that can arrive in ``update()``."""


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    # System events
    "AllWindowsClosed",
    "AnimationFrame",
    # Error / announce
    "Announce",
    # Runtime events
    "AsyncResult",
    # Canvas lifecycle events
    "CanvasBlurred",
    # Canvas element events
    "CanvasElementBlurred",
    "CanvasElementClick",
    "CanvasElementDrag",
    "CanvasElementDragEnd",
    "CanvasElementEnter",
    "CanvasElementEvent",
    "CanvasElementFocused",
    "CanvasElementKeyPress",
    "CanvasElementKeyRelease",
    "CanvasElementLeave",
    # Union types
    "CanvasEvent",
    "CanvasFocused",
    # Canvas group events
    "CanvasGroupBlurred",
    "CanvasGroupEvent",
    "CanvasGroupFocused",
    "CanvasLifecycleEvent",
    # Canvas events
    "CanvasMove",
    "CanvasPress",
    "CanvasRelease",
    "CanvasScroll",
    # Widget events
    "Click",
    "Close",
    # Diagnostic
    "Diagnostic",
    "DuplicateNodeIds",
    # Effect
    "EffectResult",
    # Helper types
    "EffectStatus",
    "Event",
    "ExtensionCommandError",
    # Window events
    "FileDropped",
    "FileHovered",
    "FilesHoveredLeft",
    "FocusedWidget",
    "ImageList",
    # IME events
    "ImeClose",
    "ImeCommit",
    "ImeEvent",
    "ImeOpen",
    "ImePreedit",
    "Input",
    "KeyBinding",
    "KeyEvent",
    "KeyLocation",
    # Key events
    "KeyPress",
    "KeyRelease",
    "ModifiersChanged",
    # MouseArea events
    "MouseAreaDoubleClick",
    "MouseAreaEnter",
    "MouseAreaEvent",
    "MouseAreaExit",
    "MouseAreaMiddlePress",
    "MouseAreaMiddleRelease",
    "MouseAreaMove",
    "MouseAreaRightPress",
    "MouseAreaRightRelease",
    "MouseAreaScroll",
    "MouseButton",
    # Mouse events
    "MouseButtonPress",
    "MouseButtonRelease",
    "MouseEnter",
    "MouseEvent",
    "MouseLeave",
    "MouseMove",
    "MouseWheel",
    "Open",
    "OptionHovered",
    # Pane events
    "PaneClicked",
    "PaneDragged",
    "PaneEvent",
    "PaneFocusCycle",
    "PaneResized",
    "Paste",
    "RendererError",
    "RuntimeEvent",
    "ScopedWidgetEvent",
    "Scroll",
    "ScrollData",
    "ScrollUnit",
    "Select",
    # Sensor
    "SensorResize",
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
    "TouchEvent",
    # Touch events
    "TouchLift",
    "TouchLost",
    "TouchMove",
    "TouchPress",
    "TreeHash",
    "WidgetEvent",
    "WindowCloseRequested",
    "WindowClosed",
    "WindowEvent",
    "WindowFocused",
    "WindowMoved",
    "WindowOpen",
    "WindowRescaled",
    "WindowResized",
    "WindowUnfocused",
    # Helpers
    "split_scoped_id",
    "target",
]
