"""Wire protocol encode/decode for all plushie message types.

This module is pure functions operating on plain dicts -- no I/O.
Message builders produce dicts ready for ``MsgpackFraming.encode``
or ``JsonFraming.encode``. The ``decode_message`` function converts
an inbound dict (already deserialized by the framing layer) into
the appropriate event dataclass from ``plushie.events``.

Reference: ``~/projects/plushie-renderer/docs/protocol.md`` for every message
type, field, and value.
"""

from __future__ import annotations

from typing import Any

from plushie.events import (
    AllWindowsClosed,
    AnimationFrame,
    Announce,
    CanvasBlurred,
    CanvasElementBlurred,
    CanvasElementClick,
    CanvasElementDrag,
    CanvasElementDragEnd,
    CanvasElementEnter,
    CanvasElementFocused,
    CanvasElementKeyPress,
    CanvasElementKeyRelease,
    CanvasElementLeave,
    CanvasFocused,
    CanvasGroupBlurred,
    CanvasGroupFocused,
    CanvasMove,
    CanvasPress,
    CanvasRelease,
    CanvasScroll,
    Click,
    Close,
    Diagnostic,
    DuplicateNodeIds,
    EffectResult,
    FileDropped,
    FileHovered,
    FilesHoveredLeft,
    FocusedWidget,
    ImageList,
    ImeClose,
    ImeCommit,
    ImeOpen,
    ImePreedit,
    Input,
    KeyBinding,
    KeyPress,
    KeyRelease,
    ModifiersChanged,
    MouseAreaDoubleClick,
    MouseAreaEnter,
    MouseAreaExit,
    MouseAreaMiddlePress,
    MouseAreaMiddleRelease,
    MouseAreaMove,
    MouseAreaRightPress,
    MouseAreaRightRelease,
    MouseAreaScroll,
    MouseButtonPress,
    MouseButtonRelease,
    MouseEnter,
    MouseLeave,
    MouseMove,
    MouseWheel,
    Open,
    OptionHovered,
    PaneClicked,
    PaneDragged,
    PaneFocusCycle,
    PaneResized,
    Paste,
    Scroll,
    ScrollData,
    Select,
    SensorResize,
    Slide,
    SlideRelease,
    Sort,
    Submit,
    SystemInfo,
    SystemTheme,
    ThemeChanged,
    Toggle,
    TouchLift,
    TouchLost,
    TouchMove,
    TouchPress,
    TreeHash,
    WidgetEvent,
    WindowClosed,
    WindowCloseRequested,
    WindowFocused,
    WindowMoved,
    WindowOpen,
    WindowRescaled,
    WindowResized,
    WindowUnfocused,
    split_scoped_id,
)
from plushie.types import HelloInfo, KeyModifiers

PROTOCOL_VERSION: int = 1
"""Current protocol version."""


# ===================================================================
# Outbound message builders (host -> renderer)
# ===================================================================


def settings(
    settings_dict: dict[str, Any],
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a Settings message.

    The ``settings_dict`` is placed under the ``settings`` key. The
    ``protocol_version`` field is injected automatically if not present.

    Args:
        settings_dict: Application settings (all fields optional).
        session: Session identifier.
    """
    inner = dict(settings_dict)
    inner.setdefault("protocol_version", PROTOCOL_VERSION)
    return {"type": "settings", "session": session, "settings": inner}


def snapshot(
    tree: dict[str, Any],
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a Snapshot message (full tree replacement).

    Args:
        tree: The complete UI tree as a node dict.
        session: Session identifier.
    """
    return {"type": "snapshot", "session": session, "tree": tree}


def patch(
    ops: list[dict[str, Any]],
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a Patch message (incremental tree update).

    Args:
        ops: List of patch operation dicts (replace_node, update_props,
            insert_child, remove_child).
        session: Session identifier.
    """
    return {"type": "patch", "session": session, "ops": ops}


def subscribe_msg(
    kind: str,
    tag: str,
    *,
    max_rate: int | None = None,
    session: str = "",
) -> dict[str, Any]:
    """Build a Subscribe message.

    Args:
        kind: Event category (e.g. ``"on_key_press"``).
        tag: Tag included in events for routing.
        max_rate: Maximum events per second (omit for unlimited).
        session: Session identifier.
    """
    msg: dict[str, Any] = {
        "type": "subscribe",
        "session": session,
        "kind": kind,
        "tag": tag,
    }
    if max_rate is not None:
        msg["max_rate"] = max_rate
    return msg


def unsubscribe_msg(
    kind: str,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build an Unsubscribe message.

    Args:
        kind: Event category to unsubscribe from.
        session: Session identifier.
    """
    return {"type": "unsubscribe", "session": session, "kind": kind}


def widget_op(
    op: str,
    payload: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a WidgetOp message.

    Args:
        op: Operation name (e.g. ``"focus"``, ``"scroll_to"``).
        payload: Operation-specific payload dict.
        session: Session identifier.
    """
    msg: dict[str, Any] = {
        "type": "widget_op",
        "session": session,
        "op": op,
    }
    if payload:
        msg["payload"] = payload
    else:
        msg["payload"] = {}
    return msg


def window_op(
    op: str,
    window_id: str,
    op_settings: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a WindowOp message.

    Args:
        op: Operation name (e.g. ``"open"``, ``"resize"``).
        window_id: Target window identifier.
        op_settings: Operation-specific settings dict.
        session: Session identifier.
    """
    msg: dict[str, Any] = {
        "type": "window_op",
        "session": session,
        "op": op,
        "window_id": window_id,
        "settings": op_settings if op_settings is not None else {},
    }
    return msg


def effect_msg(
    request_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build an Effect message.

    Args:
        request_id: Unique request ID for response correlation.
        kind: Effect kind (e.g. ``"file_open"``, ``"clipboard_read"``).
        payload: Effect-specific payload dict.
        session: Session identifier.
    """
    return {
        "type": "effect",
        "session": session,
        "id": request_id,
        "kind": kind,
        "payload": payload or {},
    }


def image_op(
    op: str,
    handle: str,
    *,
    data: bytes | str | None = None,
    pixels: bytes | str | None = None,
    width: int | None = None,
    height: int | None = None,
    session: str = "",
) -> dict[str, Any]:
    """Build an ImageOp message.

    For ``create_image`` / ``update_image``, provide either ``data``
    (encoded image bytes) or ``pixels`` + ``width`` + ``height``
    (raw RGBA). For ``delete_image``, only ``handle`` is needed.

    Args:
        op: Operation (``"create_image"``, ``"update_image"``,
            ``"delete_image"``).
        handle: Image handle name.
        data: Encoded image data (PNG/JPEG bytes or base64 string).
        pixels: Raw RGBA pixel data (bytes or base64 string).
        width: Image width (required with ``pixels``).
        height: Image height (required with ``pixels``).
        session: Session identifier.
    """
    msg: dict[str, Any] = {
        "type": "image_op",
        "session": session,
        "op": op,
        "handle": handle,
    }
    if data is not None:
        msg["data"] = data
    if pixels is not None:
        msg["pixels"] = pixels
    if width is not None:
        msg["width"] = width
    if height is not None:
        msg["height"] = height
    return msg


def extension_command(
    node_id: str,
    op: str,
    payload: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build an ExtensionCommand message.

    Args:
        node_id: Target extension widget node ID.
        op: Extension operation name.
        payload: Operation-specific payload.
        session: Session identifier.
    """
    return {
        "type": "extension_command",
        "session": session,
        "node_id": node_id,
        "op": op,
        "payload": payload or {},
    }


def extension_commands(
    commands: list[dict[str, Any]],
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build an ExtensionCommands (batch) message.

    Each item in ``commands`` should have ``node_id``, ``op``, and
    ``payload`` keys.

    Args:
        commands: List of extension command dicts.
        session: Session identifier.
    """
    return {
        "type": "extension_commands",
        "session": session,
        "commands": commands,
    }


def interact_msg(
    request_id: str,
    action: str,
    selector: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build an Interact message.

    Args:
        request_id: Unique request ID for response correlation.
        action: Interaction type (e.g. ``"click"``, ``"type_text"``).
        selector: Target widget selector (required for widget-specific
            actions, optional for global actions).
        payload: Action-specific parameters.
        session: Session identifier.
    """
    msg: dict[str, Any] = {
        "type": "interact",
        "session": session,
        "id": request_id,
        "action": action,
    }
    if selector is not None:
        msg["selector"] = selector
    else:
        msg["selector"] = {}
    if payload is not None:
        msg["payload"] = payload
    else:
        msg["payload"] = {}
    return msg


def query_msg(
    request_id: str,
    target: str,
    selector: dict[str, str] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a Query message.

    Args:
        request_id: Unique request ID for response correlation.
        target: Query target: ``"find"`` or ``"tree"``.
        selector: Widget selector (for ``"find"`` queries).
        session: Session identifier.
    """
    return {
        "type": "query",
        "session": session,
        "id": request_id,
        "target": target,
        "selector": selector or {},
    }


def tree_hash_msg(
    request_id: str,
    name: str,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a TreeHash message.

    Args:
        request_id: Unique request ID for response correlation.
        name: Label for this hash capture.
        session: Session identifier.
    """
    return {
        "type": "tree_hash",
        "session": session,
        "id": request_id,
        "name": name,
    }


def screenshot_msg(
    request_id: str,
    name: str,
    *,
    width: int = 1024,
    height: int = 768,
    session: str = "",
) -> dict[str, Any]:
    """Build a Screenshot message.

    Args:
        request_id: Unique request ID for response correlation.
        name: Label for this screenshot capture.
        width: Viewport width in pixels.
        height: Viewport height in pixels.
        session: Session identifier.
    """
    return {
        "type": "screenshot",
        "session": session,
        "id": request_id,
        "name": name,
        "width": width,
        "height": height,
    }


def reset_msg(
    request_id: str,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a Reset message.

    Args:
        request_id: Unique request ID for response correlation.
        session: Session identifier.
    """
    return {
        "type": "reset",
        "session": session,
        "id": request_id,
    }


def register_effect_stub(
    kind: str,
    response: Any,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a register_effect_stub message.

    Tells the renderer to return ``response`` immediately for any effect
    of the given ``kind``, without executing the real effect.

    Args:
        kind: Effect kind (e.g. ``"file_open"``, ``"clipboard_read"``).
        response: The canned response the renderer should return.
        session: Session identifier.
    """
    return {
        "type": "register_effect_stub",
        "session": session,
        "kind": kind,
        "response": response,
    }


def unregister_effect_stub(
    kind: str,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build an unregister_effect_stub message.

    Removes a previously registered effect stub.

    Args:
        kind: Effect kind to unregister.
        session: Session identifier.
    """
    return {
        "type": "unregister_effect_stub",
        "session": session,
        "kind": kind,
    }


def advance_frame_msg(
    timestamp: int,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build an AdvanceFrame message.

    Args:
        timestamp: Frame timestamp in milliseconds.
        session: Session identifier.
    """
    return {
        "type": "advance_frame",
        "session": session,
        "timestamp": timestamp,
    }


# ===================================================================
# Selector helpers
# ===================================================================


def encode_selector(selector: str) -> dict[str, str]:
    """Encode a user-facing selector string into a wire selector dict.

    Selector syntax:

    - ``"#widget_id"`` -- find by node ID (strips leading ``#``)
    - ``"text content"`` -- find by text content (content, label, value)

    Args:
        selector: Selector string.

    Returns:
        Wire selector dict (e.g. ``{"by": "id", "value": "widget_id"}``).
    """
    if selector.startswith("#"):
        return {"by": "id", "value": selector[1:]}
    return {"by": "text", "value": selector}


def selector_by_id(node_id: str) -> dict[str, str]:
    """Build a selector that finds a node by its exact ID.

    Args:
        node_id: The node ID to search for.
    """
    return {"by": "id", "value": node_id}


def selector_by_text(text: str) -> dict[str, str]:
    """Build a selector that finds a node by text content.

    Args:
        text: Text to match against content, label, value, or placeholder.
    """
    return {"by": "text", "value": text}


def selector_by_role(role: str) -> dict[str, str]:
    """Build a selector that finds a node by accessibility role.

    Args:
        role: A11y role string.
    """
    return {"by": "role", "value": role}


def selector_by_label(label: str) -> dict[str, str]:
    """Build a selector that finds a node by accessibility label.

    Args:
        label: A11y label string.
    """
    return {"by": "label", "value": label}


def selector_focused() -> dict[str, str]:
    """Build a selector that finds the currently focused widget."""
    return {"by": "focused"}


# ===================================================================
# Response parsers
# ===================================================================


def parse_hello(msg: dict[str, Any]) -> HelloInfo:
    """Parse a hello message dict into a ``HelloInfo`` dataclass.

    Args:
        msg: Deserialized hello message.

    Returns:
        Populated ``HelloInfo`` instance.
    """
    extensions = msg.get("extensions", [])
    return HelloInfo(
        protocol=msg["protocol"],
        version=msg["version"],
        name=msg["name"],
        mode=msg["mode"],
        backend=msg["backend"],
        transport=msg.get("transport", "stdio"),
        extensions=tuple(extensions),
    )


def parse_query_response(msg: dict[str, Any]) -> dict[str, Any]:
    """Parse a query_response message.

    Args:
        msg: Deserialized query_response message.

    Returns:
        Dict with ``id``, ``target``, and ``data`` keys.
    """
    return {
        "id": msg["id"],
        "target": msg["target"],
        "data": msg.get("data"),
    }


def parse_effect_response(
    msg: dict[str, Any],
) -> EffectResult:
    """Parse an effect_response message into an ``EffectResult`` event.

    Args:
        msg: Deserialized effect_response message.

    Returns:
        Populated ``EffectResult`` instance.
    """
    return EffectResult(
        request_id=msg["id"],
        status=msg["status"],
        result=msg.get("result"),
        error=msg.get("error"),
    )


# ===================================================================
# Inbound message decoder
# ===================================================================


def decode_message(
    msg: dict[str, Any],
) -> (
    HelloInfo
    | EffectResult
    | Click
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
    | Diagnostic
    | SensorResize
    | PaneResized
    | PaneDragged
    | PaneClicked
    | PaneFocusCycle
    | KeyPress
    | KeyRelease
    | ModifiersChanged
    | MouseMove
    | MouseEnter
    | MouseLeave
    | MouseButtonPress
    | MouseButtonRelease
    | MouseWheel
    | TouchPress
    | TouchMove
    | TouchLift
    | TouchLost
    | ImeOpen
    | ImePreedit
    | ImeCommit
    | ImeClose
    | WindowOpen
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
    | AnimationFrame
    | ThemeChanged
    | AllWindowsClosed
    | SystemInfo
    | SystemTheme
    | ImageList
    | FocusedWidget
    | TreeHash
    | DuplicateNodeIds
    | Announce
    | dict[str, Any]
):
    """Decode an inbound wire message dict into the appropriate event or response.

    Dispatches on the ``type`` field, then on ``family`` for events.
    Returns the original dict for unrecognized message types (e.g.
    ``interact_response``, ``query_response``).

    Args:
        msg: Deserialized message dict from the framing layer.

    Returns:
        An event dataclass, ``HelloInfo``, ``EffectResult``, or the
        raw dict for response types that the caller handles directly.
    """
    msg_type = msg.get("type", "")

    if msg_type == "hello":
        return parse_hello(msg)

    if msg_type == "effect_response":
        return parse_effect_response(msg)

    if msg_type == "op_query_response":
        return _decode_op_query_response(msg)

    if msg_type == "event":
        return _decode_event(msg)

    if msg_type in ("effect_stub_registered", "effect_stub_unregistered"):
        return {"type": msg_type, "kind": msg.get("kind", "")}

    # Pass through other response types (query_response, interact_response,
    # interact_step, tree_hash_response, screenshot_response, reset_response)
    return msg


# ===================================================================
# Internal event dispatch
# ===================================================================


def _parse_modifiers(raw: dict[str, Any] | None) -> KeyModifiers:
    """Parse a wire modifiers object into a KeyModifiers dataclass."""
    if not raw:
        return KeyModifiers()
    return KeyModifiers(
        shift=bool(raw.get("shift", False)),
        ctrl=bool(raw.get("ctrl", False)),
        alt=bool(raw.get("alt", False)),
        logo=bool(raw.get("logo", False)),
        command=bool(raw.get("command", False)),
    )


def _decode_event(msg: dict[str, Any]) -> Any:
    """Dispatch an event message on family."""
    family = msg.get("family", "")
    wire_id = msg.get("id", "")
    value = msg.get("value")
    data = msg.get("data") or {}
    captured = bool(msg.get("captured", False))
    modifiers_raw = msg.get("modifiers")

    # ------- Widget events (scoped) -------

    if family == "click":
        local_id, scope = split_scoped_id(wire_id)
        return Click(id=local_id, scope=scope)

    if family == "input":
        local_id, scope = split_scoped_id(wire_id)
        return Input(id=local_id, value=str(value or ""), scope=scope)

    if family == "submit":
        local_id, scope = split_scoped_id(wire_id)
        return Submit(id=local_id, value=str(value or ""), scope=scope)

    if family == "toggle":
        local_id, scope = split_scoped_id(wire_id)
        return Toggle(id=local_id, value=bool(value), scope=scope)

    if family == "select":
        local_id, scope = split_scoped_id(wire_id)
        return Select(id=local_id, value=str(value or ""), scope=scope)

    if family == "slide":
        local_id, scope = split_scoped_id(wire_id)
        return Slide(id=local_id, value=float(value or 0), scope=scope)

    if family == "slide_release":
        local_id, scope = split_scoped_id(wire_id)
        return SlideRelease(id=local_id, value=float(value or 0), scope=scope)

    if family == "scroll":
        local_id, scope = split_scoped_id(wire_id)
        sd = ScrollData(
            absolute_x=float(data.get("absolute_x", 0)),
            absolute_y=float(data.get("absolute_y", 0)),
            relative_x=float(data.get("relative_x", 0)),
            relative_y=float(data.get("relative_y", 0)),
            bounds_width=float(data.get("bounds_width", 0)),
            bounds_height=float(data.get("bounds_height", 0)),
            content_width=float(data.get("content_width", 0)),
            content_height=float(data.get("content_height", 0)),
        )
        return Scroll(id=local_id, data=sd, scope=scope)

    if family == "paste":
        local_id, scope = split_scoped_id(wire_id)
        return Paste(id=local_id, value=str(value or ""), scope=scope)

    if family == "sort":
        local_id, scope = split_scoped_id(wire_id)
        column = data.get("column", "") if isinstance(data, dict) else str(value or "")
        return Sort(id=local_id, value=str(column), scope=scope)

    if family == "open":
        local_id, scope = split_scoped_id(wire_id)
        return Open(id=local_id, scope=scope)

    if family == "close":
        local_id, scope = split_scoped_id(wire_id)
        return Close(id=local_id, scope=scope)

    if family == "option_hovered":
        local_id, scope = split_scoped_id(wire_id)
        return OptionHovered(id=local_id, value=str(value or ""), scope=scope)

    if family == "key_binding":
        local_id, scope = split_scoped_id(wire_id)
        # Wire sends binding name in `data` (string) or `data.binding` (dict).
        if isinstance(data, dict):
            binding = str(data.get("binding", ""))
        elif isinstance(data, str):
            binding = data
        else:
            binding = str(value or "")
        return KeyBinding(id=local_id, value=binding, scope=scope)

    # ------- MouseArea events (scoped) -------

    if family == "mouse_right_press":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaRightPress(id=local_id, scope=scope)

    if family == "mouse_right_release":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaRightRelease(id=local_id, scope=scope)

    if family == "mouse_middle_press":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaMiddlePress(id=local_id, scope=scope)

    if family == "mouse_middle_release":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaMiddleRelease(id=local_id, scope=scope)

    if family == "mouse_double_click":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaDoubleClick(id=local_id, scope=scope)

    if family == "mouse_enter":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaEnter(id=local_id, scope=scope)

    if family == "mouse_exit":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaExit(id=local_id, scope=scope)

    if family == "mouse_move":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaMove(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            scope=scope,
        )

    if family == "mouse_scroll":
        local_id, scope = split_scoped_id(wire_id)
        return MouseAreaScroll(
            id=local_id,
            delta_x=float(data.get("delta_x", 0)),
            delta_y=float(data.get("delta_y", 0)),
            scope=scope,
        )

    # ------- Canvas events (scoped) -------

    if family == "canvas_press":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasPress(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button=str(data.get("button", "left")),
            scope=scope,
        )

    if family == "canvas_release":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasRelease(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button=str(data.get("button", "left")),
            scope=scope,
        )

    if family == "canvas_move":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasMove(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            scope=scope,
        )

    if family == "canvas_scroll":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasScroll(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            delta_x=float(data.get("delta_x", 0)),
            delta_y=float(data.get("delta_y", 0)),
            scope=scope,
        )

    # ------- Canvas element events (scoped) -------

    if family == "canvas_element_enter":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementEnter(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            captured=captured,
            scope=scope,
        )

    if family == "canvas_element_leave":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementLeave(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            captured=captured,
            scope=scope,
        )

    if family == "canvas_element_click":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementClick(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button=str(data.get("button", "left")),
            captured=captured,
            scope=scope,
        )

    if family == "canvas_element_drag":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementDrag(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            delta_x=float(data.get("delta_x", 0)),
            delta_y=float(data.get("delta_y", 0)),
            captured=captured,
            scope=scope,
        )

    if family == "canvas_element_drag_end":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementDragEnd(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            captured=captured,
            scope=scope,
        )

    if family == "canvas_element_focused":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementFocused(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            captured=captured,
            scope=scope,
        )

    if family == "canvas_element_blurred":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementBlurred(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            captured=captured,
            scope=scope,
        )

    if family == "canvas_element_key_press":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementKeyPress(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            key=str(data.get("key", "")),
            scope=scope,
        )

    if family == "canvas_element_key_release":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasElementKeyRelease(
            id=local_id,
            element_id=str(data.get("element_id", "")),
            key=str(data.get("key", "")),
            scope=scope,
        )

    # ------- Canvas lifecycle events (scoped, no coordinates) -------

    if family == "canvas_focused":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasFocused(id=local_id, scope=scope)

    if family == "canvas_blurred":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasBlurred(id=local_id, scope=scope)

    # ------- Canvas group events (scoped) -------

    if family == "canvas_group_focused":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasGroupFocused(
            id=local_id,
            group_id=str(data.get("group_id", "")),
            scope=scope,
        )

    if family == "canvas_group_blurred":
        local_id, scope = split_scoped_id(wire_id)
        return CanvasGroupBlurred(
            id=local_id,
            group_id=str(data.get("group_id", "")),
            scope=scope,
        )

    # ------- Diagnostic -------

    if family == "diagnostic":
        return Diagnostic(
            level=str(data.get("level", "warning")),
            element_id=str(data.get("element_id", "")),
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
        )

    # ------- Sensor events (scoped) -------

    if family == "sensor_resize":
        local_id, scope = split_scoped_id(wire_id)
        return SensorResize(
            id=local_id,
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
            scope=scope,
        )

    # ------- Pane events (scoped) -------

    if family == "pane_resized":
        local_id, scope = split_scoped_id(wire_id)
        return PaneResized(
            id=local_id,
            split=data.get("split"),
            ratio=float(data.get("ratio", 0)),
            scope=scope,
        )

    if family == "pane_dragged":
        local_id, scope = split_scoped_id(wire_id)
        return PaneDragged(
            id=local_id,
            pane=data.get("pane"),
            target=data.get("target"),
            action=str(data.get("action", "")),
            region=data.get("region"),
            edge=data.get("edge"),
            scope=scope,
        )

    if family == "pane_clicked":
        local_id, scope = split_scoped_id(wire_id)
        return PaneClicked(
            id=local_id,
            pane=data.get("pane"),
            scope=scope,
        )

    if family == "pane_focus_cycle":
        local_id, scope = split_scoped_id(wire_id)
        return PaneFocusCycle(
            id=local_id,
            pane=data.get("pane"),
            scope=scope,
        )

    # ------- Key events (global subscription) -------

    if family == "key_press":
        mods = _parse_modifiers(modifiers_raw)
        return KeyPress(
            key=str(data.get("key", "")),
            modified_key=str(data.get("modified_key", data.get("key", ""))),
            modifiers=mods,
            physical_key=data.get("physical_key"),
            location=data.get("location", "standard"),
            text=data.get("text"),
            repeat=bool(data.get("repeat", False)),
            captured=captured,
        )

    if family == "key_release":
        mods = _parse_modifiers(modifiers_raw)
        return KeyRelease(
            key=str(data.get("key", "")),
            modified_key=str(data.get("modified_key", data.get("key", ""))),
            modifiers=mods,
            physical_key=data.get("physical_key"),
            location=data.get("location", "standard"),
            text=data.get("text"),
            captured=captured,
        )

    if family == "modifiers_changed":
        mods = _parse_modifiers(modifiers_raw)
        return ModifiersChanged(modifiers=mods, captured=captured)

    # ------- Mouse events (global subscription) -------

    if family == "cursor_moved":
        return MouseMove(
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            captured=captured,
        )

    if family == "cursor_entered":
        return MouseEnter(captured=captured)

    if family == "cursor_left":
        return MouseLeave(captured=captured)

    if family == "button_pressed":
        return MouseButtonPress(button=str(value or "left"), captured=captured)

    if family == "button_released":
        return MouseButtonRelease(button=str(value or "left"), captured=captured)

    if family == "wheel_scrolled":
        return MouseWheel(
            delta_x=float(data.get("delta_x", 0)),
            delta_y=float(data.get("delta_y", 0)),
            unit=data.get("unit", "line"),
            captured=captured,
        )

    # ------- Touch events (global subscription) -------

    if family == "finger_pressed":
        return TouchPress(
            finger_id=int(data.get("id", 0)),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            captured=captured,
        )

    if family == "finger_moved":
        return TouchMove(
            finger_id=int(data.get("id", 0)),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            captured=captured,
        )

    if family == "finger_lifted":
        return TouchLift(
            finger_id=int(data.get("id", 0)),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            captured=captured,
        )

    if family == "finger_lost":
        return TouchLost(
            finger_id=int(data.get("id", 0)),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            captured=captured,
        )

    # ------- IME events (global subscription) -------

    if family == "ime_opened":
        return ImeOpen(captured=captured)

    if family == "ime_preedit":
        cursor_raw = data.get("cursor")
        if (
            isinstance(cursor_raw, dict)
            and "start" in cursor_raw
            and "end" in cursor_raw
        ):
            cursor: tuple[int, int] | None = (
                int(cursor_raw["start"]),
                int(cursor_raw["end"]),
            )
        else:
            cursor = None
        return ImePreedit(
            text=str(data.get("text", "")),
            cursor=cursor,
            captured=captured,
        )

    if family == "ime_commit":
        return ImeCommit(text=str(data.get("text", "")), captured=captured)

    if family == "ime_closed":
        return ImeClose(captured=captured)

    # ------- Window events (global subscription) -------

    if family == "window_opened":
        pos = data.get("position") or {}
        return WindowOpen(
            window_id=str(data.get("window_id", "")),
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
            scale_factor=float(data.get("scale_factor", 1.0)),
            position_x=_opt_float(pos.get("x")),
            position_y=_opt_float(pos.get("y")),
        )

    if family == "window_closed":
        return WindowClosed(window_id=str(data.get("window_id", "")))

    if family == "window_close_requested":
        return WindowCloseRequested(window_id=str(data.get("window_id", "")))

    if family == "window_resized":
        return WindowResized(
            window_id=str(data.get("window_id", "")),
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
        )

    if family == "window_moved":
        return WindowMoved(
            window_id=str(data.get("window_id", "")),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
        )

    if family == "window_focused":
        return WindowFocused(window_id=str(data.get("window_id", "")))

    if family == "window_unfocused":
        return WindowUnfocused(window_id=str(data.get("window_id", "")))

    if family == "window_rescaled":
        return WindowRescaled(
            window_id=str(data.get("window_id", "")),
            scale_factor=float(data.get("scale_factor", 1.0)),
        )

    if family == "file_hovered":
        return FileHovered(
            window_id=str(data.get("window_id", "")),
            path=str(data.get("path", "")),
        )

    if family == "file_dropped":
        return FileDropped(
            window_id=str(data.get("window_id", "")),
            path=str(data.get("path", "")),
        )

    if family == "files_hovered_left":
        return FilesHoveredLeft(window_id=str(data.get("window_id", "")))

    # ------- System / animation / theme -------

    if family == "animation_frame":
        return AnimationFrame(timestamp=int(data.get("timestamp", 0)))

    if family == "theme_changed":
        return ThemeChanged(theme=str(value or ""))

    if family == "all_windows_closed":
        return AllWindowsClosed()

    # ------- Error / announce -------

    if family == "error":
        error_id = wire_id
        if error_id == "duplicate_node_ids":
            return DuplicateNodeIds(details=data)
        # Generic error -- return as dict
        return msg

    if family == "announce":
        return Announce(text=str(data.get("text", "")))

    # ------- Session lifecycle (multiplexed mode) -------

    if family in ("session_error", "session_closed"):
        return msg

    # ------- Catch-all: unknown widget event -------
    if wire_id:
        local_id, scope = split_scoped_id(wire_id)
        return WidgetEvent(
            kind=family,
            id=local_id,
            value=value,
            data=data if data else None,
            scope=scope,
        )

    # Truly unknown -- pass through
    return msg


def _decode_op_query_response(msg: dict[str, Any]) -> Any:
    """Decode an op_query_response into the appropriate event type."""
    kind = msg.get("kind", "")
    tag_val = msg.get("tag", "")
    data = msg.get("data")

    if kind == "tree_hash":
        hash_val = ""
        if isinstance(data, dict):
            hash_val = str(data.get("hash", ""))
        return TreeHash(tag=tag_val, hash=hash_val)

    if kind == "find_focused":
        widget_id = None
        if isinstance(data, dict):
            focused = data.get("focused")
            if focused is not None:
                widget_id = str(focused)
        return FocusedWidget(tag=tag_val, widget_id=widget_id)

    if kind == "list_images":
        handles: tuple[str, ...] = ()
        if isinstance(data, dict):
            raw_handles = data.get("handles", [])
            handles = tuple(str(h) for h in raw_handles)
        return ImageList(tag=tag_val, handles=handles)

    if kind == "system_theme":
        theme_val = str(data) if data else ""
        return SystemTheme(tag=tag_val, theme=theme_val)

    if kind == "system_info":
        return SystemInfo(tag=tag_val, data=data)

    # Unknown op_query_response kind
    return msg


def _opt_float(val: Any) -> float | None:
    """Convert a value to float, returning None for None/missing values."""
    if val is None:
        return None
    return float(val)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "PROTOCOL_VERSION",
    "advance_frame_msg",
    "decode_message",
    "effect_msg",
    "encode_selector",
    "extension_command",
    "extension_commands",
    "image_op",
    "interact_msg",
    "parse_effect_response",
    "parse_hello",
    "parse_query_response",
    "patch",
    "query_msg",
    "register_effect_stub",
    "reset_msg",
    "screenshot_msg",
    "selector_by_id",
    "selector_by_label",
    "selector_by_role",
    "selector_by_text",
    "selector_focused",
    "settings",
    "snapshot",
    "subscribe_msg",
    "tree_hash_msg",
    "unregister_effect_stub",
    "unsubscribe_msg",
    "widget_op",
    "window_op",
]
