"""Wire protocol encode/decode for all plushie message types.

This module is pure functions operating on plain dicts. No I/O.
Message builders produce dicts ready for ``MsgpackFraming.encode``
or ``JsonFraming.encode``. The ``decode_message`` function converts
an inbound dict (already deserialized by the framing layer) into
the appropriate event dataclass from ``plushie.events``.

Reference: ``~/projects/plushie-renderer/docs/protocol.md`` for every message
type, field, and value.
"""

from __future__ import annotations

import logging
from typing import Any

from plushie.events import (
    AllWindowsClosed,
    AnimationFrame,
    Announce,
    Blurred,
    Click,
    Close,
    CommandError,
    Diagnostic,
    DiagnosticMessage,
    DoubleClick,
    Drag,
    DragEnd,
    DuplicateNodeIds,
    EffectResult,
    EffectStubAck,
    Enter,
    Exit,
    Focused,
    FocusedWidget,
    ImageList,
    ImeEvent,
    Input,
    KeyBinding,
    KeyEvent,
    LinkClicked,
    ModifiersChanged,
    Move,
    Open,
    OptionHovered,
    PaneClicked,
    PaneDragged,
    PaneFocusCycle,
    PaneResized,
    Paste,
    PointerButton,
    PointerType,
    Press,
    RawEvent,
    Release,
    RendererError,
    Resize,
    Scroll,
    ScrollData,
    Scrolled,
    Select,
    SessionClosed,
    SessionError,
    Slide,
    SlideRelease,
    Sort,
    Submit,
    SystemInfo,
    SystemTheme,
    ThemeChanged,
    Toggle,
    TransitionComplete,
    TreeHash,
    WidgetStatus,
    WindowEvent,
    split_scoped_id,
)
from plushie.types import HelloInfo, KeyModifiers

PROTOCOL_VERSION: int = 1
"""Current protocol version."""

logger = logging.getLogger("plushie.protocol")
"""Module logger. Used to mirror renderer diagnostics to Python logging."""

_SUPPORTED_SETTING_KEYS: frozenset[str] = frozenset(
    {
        "default_font",
        "default_text_size",
        "antialiasing",
        "vsync",
        "scale_factor",
        "theme",
        "fonts",
        "default_event_rate",
        "widget_config",
        "required_widgets",
        "validate_props",
        "protocol_version",
    }
)


def _strip_internal_meta(value: Any) -> Any:
    """Remove runtime-only ``meta`` fields before sending data on the wire."""
    if isinstance(value, dict):
        return {
            key: _strip_internal_meta(inner)
            for key, inner in value.items()
            if key != "meta"
        }
    if isinstance(value, list):
        return [_strip_internal_meta(item) for item in value]
    return value


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
    if not isinstance(settings_dict, dict):
        raise ValueError("settings must be a dict")
    unknown = set(settings_dict) - _SUPPORTED_SETTING_KEYS
    if unknown:
        keys = ", ".join(sorted(unknown))
        raise ValueError(f"unknown setting key: {keys}")

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
    return {"type": "snapshot", "session": session, "tree": _strip_internal_meta(tree)}


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
    return {"type": "patch", "session": session, "ops": _strip_internal_meta(ops)}


def subscribe_msg(
    kind: str,
    tag: str,
    *,
    max_rate: int | None = None,
    window_id: str | None = None,
    session: str = "",
) -> dict[str, Any]:
    """Build a Subscribe message.

    Args:
        kind: Event category (e.g. ``"on_key_press"``).
        tag: Tag included in events for routing.
        max_rate: Maximum events per second (omit for unlimited).
        window_id: Optional window to scope events to.
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
    if window_id is not None:
        msg["window_id"] = window_id
    return msg


def unsubscribe_msg(
    kind: str,
    *,
    tag: str | None = None,
    session: str = "",
) -> dict[str, Any]:
    """Build an Unsubscribe message.

    Args:
        kind: Event category to unsubscribe from.
        tag: Optional tag for targeted removal of a specific
            subscription when multiple subscriptions of the same
            kind coexist (e.g. different window scopes).
        session: Session identifier.
    """
    msg: dict[str, Any] = {"type": "unsubscribe", "session": session, "kind": kind}
    if tag is not None:
        msg["tag"] = tag
    return msg


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
    payload: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a WindowOp message.

    Uses the unified ``_op`` envelope: op-specific data lives under
    ``payload``; the ``window_id`` addressing field stays flat beside ``op``.

    Args:
        op: Operation name (e.g. ``"open"``, ``"resize"``).
        window_id: Target window identifier.
        payload: Operation-specific payload dict.
        session: Session identifier.
    """
    msg: dict[str, Any] = {
        "type": "window_op",
        "session": session,
        "op": op,
        "window_id": window_id,
        "payload": payload if payload is not None else {},
    }
    return msg


def system_op(
    op: str,
    payload: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a SystemOp message.

    Uses the unified ``_op`` envelope: op-specific data lives under ``payload``.
    """
    return {
        "type": "system_op",
        "session": session,
        "op": op,
        "payload": payload if payload is not None else {},
    }


def system_query(
    op: str,
    payload: dict[str, Any] | None = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a SystemQuery message.

    Uses the unified ``_op`` envelope: query-specific data lives under ``payload``.
    """
    return {
        "type": "system_query",
        "session": session,
        "op": op,
        "payload": payload if payload is not None else {},
    }


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

    Uses the unified ``_op`` envelope: op-specific data (``handle``,
    ``data``, ``pixels``, ``width``, ``height``) lives under ``payload``.

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
    payload: dict[str, Any] = {"handle": handle}
    if data is not None:
        payload["data"] = data
    if pixels is not None:
        payload["pixels"] = pixels
    if width is not None:
        payload["width"] = width
    if height is not None:
        payload["height"] = height
    return {
        "type": "image_op",
        "session": session,
        "op": op,
        "payload": payload,
    }


def command(
    widget_id: str,
    family: str,
    value: Any = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a widget-targeted command message.

    Uses the unified wire format matching events:
    ``{type: "command", id, family, value}``.

    Args:
        widget_id: Target widget ID (scoped path).
        family: Operation name (e.g. ``"focus"``, ``"scroll_to"``).
        value: Operation-specific data.
        session: Session identifier.
    """
    msg: dict[str, Any] = {
        "type": "command",
        "session": session,
        "id": widget_id,
        "family": family,
    }
    if value is not None:
        msg["value"] = value
    return msg


def widget_command(
    widget_id: str,
    family: str,
    value: Any = None,
    *,
    session: str = "",
) -> dict[str, Any]:
    """Compatibility alias for :func:`command`."""
    return command(widget_id, family, value, session=session)


def commands(
    command_list: list[tuple[str, str, Any]],
    *,
    session: str = "",
) -> dict[str, Any]:
    """Build a batch of widget-targeted commands processed in one cycle.

    Each item in ``commands`` should be a ``(id, family, value)`` tuple.

    Args:
        command_list: List of ``(widget_id, family, value)`` tuples.
        session: Session identifier.
    """
    return {
        "type": "commands",
        "session": session,
        "commands": [
            {
                "id": cmd_id,
                "family": family,
                **({"value": val} if val is not None else {}),
            }
            for cmd_id, family, val in command_list
        ],
    }


def widget_batch(
    command_list: list[tuple[str, str, Any]],
    *,
    session: str = "",
) -> dict[str, Any]:
    """Compatibility alias for :func:`commands`."""
    return commands(command_list, session=session)


def interact_msg(
    request_id: str,
    action: str,
    selector: dict[str, Any] | None = None,
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
    selector: dict[str, Any] | None = None,
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

    - ``"#widget_id"`` - find by node ID (strips leading ``#``)
    - ``"text content"`` - find by text content (content, label, value)

    For richer selector forms see :func:`parse_selector`.

    Args:
        selector: Selector string.

    Returns:
        Wire selector dict (e.g. ``{"by": "id", "value": "widget_id"}``).
    """
    if selector.startswith("#"):
        return {"by": "id", "value": selector[1:]}
    return {"by": "text", "value": selector}


def parse_selector(selector: str) -> dict[str, str]:
    """Parse a unified selector string into a wire selector dict.

    Supported syntax:

    - ``"save"`` or ``"#save"`` - ID selector
    - ``"form/save"`` or ``"#form/save"`` - scoped ID selector
    - ``"main#save"`` - window-qualified ID selector
    - ``":focused"`` - focused element pseudo-selector
    - ``"main#:focused"`` - window-qualified focused selector
    - ``"[text=Save]"`` - text content attribute selector
    - ``"[role=button]"`` - accessibility role attribute selector
    - ``"[label=Name]"`` - accessibility label attribute selector

    Args:
        selector: Selector string.

    Returns:
        Wire selector dict with ``"by"`` and optionally ``"value"``
        and ``"window_id"`` keys.
    """
    window_id: str | None = None
    target = selector

    if "#" in selector:
        parts = selector.split("#", 1)
        if parts[0]:
            window_id = parts[0]
            target = parts[1]

    if target.startswith("#"):
        target = target[1:]

    if target.startswith(":"):
        result: dict[str, str] = {"by": target[1:]}
    elif target.startswith("[") and target.endswith("]"):
        inner = target[1:-1]
        eq_pos = inner.find("=")
        if eq_pos >= 0:
            result = {"by": inner[:eq_pos], "value": inner[eq_pos + 1 :]}
        else:
            result = {"by": "id", "value": target}
    else:
        result = {"by": "id", "value": target}

    if window_id is not None:
        result["window_id"] = window_id

    return result


def selector_by_id(node_id: str, window_id: str | None = None) -> dict[str, str]:
    """Build a selector that finds a node by its exact ID.

    Args:
        node_id: The node ID to search for.
    """
    selector = {"by": "id", "value": node_id}
    if window_id is not None:
        selector["window_id"] = window_id
    return selector


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

    Raises:
        ValueError: If required fields are missing or have wrong types.
    """
    required_keys = ("version", "name", "mode", "backend")
    missing = [k for k in required_keys if k not in msg]
    if "protocol_version" in msg:
        protocol_key = "protocol_version"
    elif "protocol" in msg:
        protocol_key = "protocol"
    else:
        protocol_key = "protocol_version"
        missing.insert(0, "protocol_version")
    if missing:
        raise ValueError(f"hello message missing required fields: {missing}")

    protocol = msg[protocol_key]
    if type(protocol) is not int:
        raise ValueError(
            f"hello message field {protocol_key!r} must be int, "
            f"got {type(protocol).__name__}"
        )

    for key in ("version", "name", "mode", "backend"):
        if not isinstance(msg[key], (str, int)):
            raise ValueError(
                f"hello message field {key!r} must be str or int, got {type(msg[key]).__name__}"
            )

    extensions = msg.get("extensions", [])
    native_widgets = msg.get("native_widgets", msg.get("extension_widgets", []))
    widgets = msg.get("widgets", [])
    return HelloInfo(
        protocol=protocol,
        version=msg["version"],
        name=msg["name"],
        mode=msg["mode"],
        backend=msg["backend"],
        transport=msg.get("transport", "stdio"),
        extensions=tuple(extensions),
        native_widgets=tuple(native_widgets),
        widgets=tuple(widgets),
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
) -> tuple[str, str, str, Any, str | None]:
    """Parse an effect_response message into wire components.

    The runtime maps the wire ID to the user's tag before creating
    an ``EffectResult``. Returns a tagged tuple that the runtime
    intercepts in the event loop.

    Args:
        msg: Deserialized effect_response message.

    Returns:
        ``("_effect_response", wire_id, status, result, error)`` tuple.
    """
    return (
        "_effect_response",
        msg["id"],
        msg["status"],
        msg.get("result"),
        msg.get("error"),
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
    | Scrolled
    | Paste
    | Sort
    | Open
    | Close
    | OptionHovered
    | KeyBinding
    | LinkClicked
    | RawEvent
    | Press
    | Release
    | Move
    | Scroll
    | DoubleClick
    | Resize
    | Focused
    | Blurred
    | Drag
    | DragEnd
    | Enter
    | Exit
    | Diagnostic
    | PaneResized
    | PaneDragged
    | PaneClicked
    | PaneFocusCycle
    | KeyEvent
    | ModifiersChanged
    | ImeEvent
    | WindowEvent
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
    | DiagnosticMessage
    | SessionError
    | SessionClosed
    | EffectStubAck
    | tuple[str, str, str, Any, str | None]
    | dict[str, Any]
):
    """Decode an inbound wire message dict into the appropriate event or response.

    Dispatches on the ``type`` field, then on ``family`` for events.
    Effect responses return a ``("_effect_response", wire_id, status,
    result, error)`` tuple for the runtime to resolve tags.
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

    if msg_type == "diagnostic":
        return _decode_diagnostic(msg)

    if msg_type in ("effect_stub_register_ack", "effect_stub_unregister_ack"):
        return EffectStubAck(
            kind=msg.get("kind", ""),
            registered=msg_type == "effect_stub_register_ack",
        )

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


_POINTER_TYPES = {"mouse", "touch", "pen"}


def _parse_pointer_type(raw: Any) -> PointerType:
    """Parse a wire pointer type string, defaulting to ``"mouse"``."""
    if raw in _POINTER_TYPES:
        return raw  # type: ignore[return-value]
    return "mouse"


def _parse_pointer_button(raw: Any) -> PointerButton:
    """Parse a wire button string, defaulting to ``"left"``."""
    if isinstance(raw, str) and raw:
        return raw  # type: ignore[return-value]
    return "left"


def _extract_window_id(msg: dict[str, Any]) -> str:
    """Extract window_id from a wire event, defaulting to empty string.

    The renderer includes ``window_id`` on widget events when the tree
    has window nodes.  Older renderers or mock mode may omit it.
    """
    wid = msg.get("window_id")
    return wid if isinstance(wid, str) else ""


def _split_scoped_with_window(
    wire_id: str, msg: dict[str, Any]
) -> tuple[str, str, tuple[str, ...]]:
    """Split a wire ID and append window_id to the end of the scope tuple.

    Returns ``(local_id, window_id, scope)`` where scope includes the
    window_id as its last element when present.

    Prefers the window extracted from ``#`` in the wire ID, falling back
    to the separate ``window_id`` field for backward compatibility.
    """
    local_id, scope, window_from_id = split_scoped_id(wire_id)
    window_id = window_from_id or _extract_window_id(msg)
    if window_id:
        scope = (*scope, window_id)
    return local_id, window_id, scope


def _decode_event(msg: dict[str, Any]) -> Any:
    """Dispatch an event message on family."""
    family = msg.get("family", "")
    wire_id = msg.get("id", "")
    value = msg.get("value")
    data = msg.get("value") if isinstance(msg.get("value"), dict) else None
    if data is None:
        data = msg.get("data") or {}
    captured = bool(msg.get("captured", False))
    modifiers_raw = msg.get("modifiers")
    sub_window_id = str(msg.get("window_id", "") or "")

    # ------- Widget events (scoped) -------

    if family == "click":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Click(
            id=local_id,
            window_id=_wid,
            scope=scope,
        )

    if family == "input":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Input(
            id=local_id,
            value=str(value or ""),
            window_id=_wid,
            scope=scope,
        )

    if family == "submit":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Submit(
            id=local_id,
            value=str(value or ""),
            window_id=_wid,
            scope=scope,
        )

    if family == "toggle":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Toggle(
            id=local_id,
            value=bool(value),
            window_id=_wid,
            scope=scope,
        )

    if family == "select":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Select(
            id=local_id,
            value=str(value or ""),
            window_id=_wid,
            scope=scope,
        )

    if family == "slide":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Slide(
            id=local_id,
            value=float(value or 0),
            window_id=_wid,
            scope=scope,
        )

    if family == "slide_release":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return SlideRelease(
            id=local_id,
            value=float(value or 0),
            window_id=_wid,
            scope=scope,
        )

    if family in ("scroll", "scrolled") and "absolute_x" in data:
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
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
        return Scrolled(
            id=local_id,
            data=sd,
            window_id=_wid,
            scope=scope,
        )

    if family == "paste":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Paste(
            id=local_id,
            value=str(value or ""),
            window_id=_wid,
            scope=scope,
        )

    if family == "sort":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        column = data.get("column", "") if isinstance(data, dict) else str(value or "")
        return Sort(
            id=local_id,
            value=str(column),
            window_id=_wid,
            scope=scope,
        )

    if family == "open":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Open(
            id=local_id,
            window_id=_wid,
            scope=scope,
        )

    if family == "close":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Close(
            id=local_id,
            window_id=_wid,
            scope=scope,
        )

    if family == "option_hovered":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return OptionHovered(
            id=local_id,
            value=str(value or ""),
            window_id=_wid,
            scope=scope,
        )

    if family == "key_binding":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        # Wire sends binding name in `data` (string) or `data.binding` (dict).
        if isinstance(data, dict):
            binding = str(data.get("binding", ""))
        elif isinstance(data, str):
            binding = data
        else:
            binding = str(value or "")
        return KeyBinding(
            id=local_id,
            value=binding,
            window_id=_wid,
            scope=scope,
        )

    if family == "link_click":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        link = str(data.get("link", "")) if isinstance(data, dict) else ""
        return LinkClicked(
            id=local_id,
            link=link,
            window_id=_wid,
            scope=scope,
        )

    # ------- Unified pointer events (scoped) -------

    if family == "press":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        mods = _parse_modifiers(data.get("modifiers"))
        return Press(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button=_parse_pointer_button(data.get("button")),
            pointer=_parse_pointer_type(data.get("pointer")),
            modifiers=mods,
            finger=data.get("finger"),
            window_id=_wid,
            scope=scope,
        )

    if family == "release":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        mods = _parse_modifiers(data.get("modifiers"))
        return Release(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button=_parse_pointer_button(data.get("button")),
            pointer=_parse_pointer_type(data.get("pointer")),
            modifiers=mods,
            finger=data.get("finger"),
            window_id=_wid,
            scope=scope,
        )

    if family == "move":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        mods = _parse_modifiers(data.get("modifiers"))
        return Move(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            pointer=_parse_pointer_type(data.get("pointer")),
            modifiers=mods,
            finger=data.get("finger"),
            window_id=_wid,
            scope=scope,
        )

    if family == "scroll":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        mods = _parse_modifiers(data.get("modifiers"))
        return Scroll(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            delta_x=float(data.get("delta_x", 0)),
            delta_y=float(data.get("delta_y", 0)),
            pointer=_parse_pointer_type(data.get("pointer")),
            modifiers=mods,
            window_id=_wid,
            scope=scope,
        )

    if family == "double_click":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        mods = _parse_modifiers(data.get("modifiers"))
        return DoubleClick(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            pointer=_parse_pointer_type(data.get("pointer")),
            modifiers=mods,
            window_id=_wid,
            scope=scope,
        )

    if family == "resize":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Resize(
            id=local_id,
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
            window_id=_wid,
            scope=scope,
        )

    # ------- Unified focus/drag/enter/exit events (scoped) -------

    if family == "focused":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Focused(
            id=local_id,
            window_id=_wid,
            scope=scope,
        )

    if family == "blurred":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Blurred(
            id=local_id,
            window_id=_wid,
            scope=scope,
        )

    if family == "status":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return WidgetStatus(
            id=local_id,
            value=str(data.get("value", "")),
            window_id=_wid,
            scope=scope,
        )

    if family == "drag":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Drag(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            delta_x=float(data.get("delta_x", 0)),
            delta_y=float(data.get("delta_y", 0)),
            button=_parse_pointer_button(data.get("button")),
            window_id=_wid,
            scope=scope,
        )

    if family == "drag_end":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return DragEnd(
            id=local_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button=_parse_pointer_button(data.get("button")),
            window_id=_wid,
            scope=scope,
        )

    if family == "enter":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Enter(
            id=local_id,
            x=_opt_float(data.get("x")),
            y=_opt_float(data.get("y")),
            captured=bool(data.get("captured", captured)),
            window_id=_wid,
            scope=scope,
        )

    if family == "exit":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return Exit(
            id=local_id,
            x=_opt_float(data.get("x")),
            y=_opt_float(data.get("y")),
            captured=bool(data.get("captured", captured)),
            window_id=_wid,
            scope=scope,
        )

    # ------- Diagnostic -------

    if family == "diagnostic":
        return Diagnostic(
            level=str(data.get("level", "warning")),
            element_id=str(data.get("element_id", "")),
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
            id=msg.get("id"),
            window_id=msg.get("window_id"),
        )

    # ------- Pane events (scoped) -------

    if family == "pane_resized":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return PaneResized(
            id=local_id,
            split=data.get("split"),
            ratio=float(data.get("ratio", 0)),
            window_id=_wid,
            scope=scope,
        )

    if family == "pane_dragged":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return PaneDragged(
            id=local_id,
            pane=data.get("pane"),
            target=data.get("target"),
            action=str(data.get("action", "")),
            window_id=_wid,
            region=data.get("region"),
            edge=data.get("edge"),
            scope=scope,
        )

    if family == "pane_clicked":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return PaneClicked(
            id=local_id,
            pane=data.get("pane"),
            window_id=_wid,
            scope=scope,
        )

    if family == "pane_focus_cycle":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return PaneFocusCycle(
            id=local_id,
            pane=data.get("pane"),
            window_id=_wid,
            scope=scope,
        )

    # ------- Key events (global subscription or widget-scoped) -------

    if family == "key_press":
        mods = _parse_modifiers(modifiers_raw)
        if wire_id:
            local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
            return KeyEvent(
                type="press",
                key=str(data.get("key", "")),
                modified_key=str(data.get("modified_key", data.get("key", ""))),
                modifiers=mods,
                physical_key=data.get("physical_key"),
                location=data.get("location", "standard"),
                text=data.get("text"),
                repeat=bool(data.get("repeat", False)),
                captured=captured,
                window_id=_wid,
                id=local_id,
                scope=scope,
            )
        return KeyEvent(
            type="press",
            key=str(data.get("key", "")),
            modified_key=str(data.get("modified_key", data.get("key", ""))),
            modifiers=mods,
            physical_key=data.get("physical_key"),
            location=data.get("location", "standard"),
            text=data.get("text"),
            repeat=bool(data.get("repeat", False)),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "key_release":
        mods = _parse_modifiers(modifiers_raw)
        if wire_id:
            local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
            return KeyEvent(
                type="release",
                key=str(data.get("key", "")),
                modified_key=str(data.get("modified_key", data.get("key", ""))),
                modifiers=mods,
                physical_key=data.get("physical_key"),
                location=data.get("location", "standard"),
                text=data.get("text"),
                captured=captured,
                window_id=_wid,
                id=local_id,
                scope=scope,
            )
        return KeyEvent(
            type="release",
            key=str(data.get("key", "")),
            modified_key=str(data.get("modified_key", data.get("key", ""))),
            modifiers=mods,
            physical_key=data.get("physical_key"),
            location=data.get("location", "standard"),
            text=data.get("text"),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "modifiers_changed":
        mods = _parse_modifiers(modifiers_raw)
        return ModifiersChanged(
            modifiers=mods, captured=captured, window_id=sub_window_id
        )

    # ------- Pointer subscription events (mouse/touch) -------
    # Delivered as unified pointer types with id=window_id, scope=().

    if family == "cursor_moved":
        return Move(
            id=sub_window_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            pointer="mouse",
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "cursor_entered":
        return Enter(id=sub_window_id, captured=captured, window_id=sub_window_id)

    if family == "cursor_left":
        return Exit(id=sub_window_id, captured=captured, window_id=sub_window_id)

    if family == "button_pressed":
        return Press(
            id=sub_window_id,
            x=0.0,
            y=0.0,
            button=str(value or "left"),
            pointer="mouse",
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "button_released":
        return Release(
            id=sub_window_id,
            x=0.0,
            y=0.0,
            button=str(value or "left"),
            pointer="mouse",
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "wheel_scrolled":
        return Scroll(
            id=sub_window_id,
            x=0.0,
            y=0.0,
            delta_x=float(data.get("delta_x", 0)),
            delta_y=float(data.get("delta_y", 0)),
            unit=data.get("unit", "line")
            if data.get("unit") in ("line", "pixel")
            else "line",
            pointer="mouse",
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "finger_pressed":
        return Press(
            id=sub_window_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button="left",
            pointer="touch",
            finger=int(data.get("id", 0)),
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "finger_moved":
        return Move(
            id=sub_window_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            pointer="touch",
            finger=int(data.get("id", 0)),
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "finger_lifted":
        return Release(
            id=sub_window_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button="left",
            pointer="touch",
            finger=int(data.get("id", 0)),
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "finger_lost":
        return Release(
            id=sub_window_id,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            button="left",
            pointer="touch",
            finger=int(data.get("id", 0)),
            lost=True,
            modifiers=_parse_modifiers(modifiers_raw),
            captured=captured,
            window_id=sub_window_id,
        )

    # ------- IME events (global subscription) -------

    if family == "ime_opened":
        return ImeEvent(type="opened", captured=captured, window_id=sub_window_id)

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
        return ImeEvent(
            type="preedit",
            text=str(data.get("text", "")),
            cursor=cursor,
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "ime_commit":
        return ImeEvent(
            type="commit",
            text=str(data.get("text", "")),
            captured=captured,
            window_id=sub_window_id,
        )

    if family == "ime_closed":
        return ImeEvent(type="closed", captured=captured, window_id=sub_window_id)

    # ------- Window events (global subscription) -------

    if family == "window_opened":
        pos = data.get("position") or {}
        return WindowEvent(
            type="opened",
            window_id=str(data.get("window_id", "")),
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
            scale_factor=float(data.get("scale_factor", 1.0)),
            position_x=_opt_float(pos.get("x")),
            position_y=_opt_float(pos.get("y")),
        )

    if family == "window_closed":
        return WindowEvent(type="closed", window_id=str(data.get("window_id", "")))

    if family == "window_close_requested":
        return WindowEvent(
            type="close_requested", window_id=str(data.get("window_id", ""))
        )

    if family == "window_resized":
        return WindowEvent(
            type="resized",
            window_id=str(data.get("window_id", "")),
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
        )

    if family == "window_moved":
        return WindowEvent(
            type="moved",
            window_id=str(data.get("window_id", "")),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
        )

    if family == "window_focused":
        return WindowEvent(type="focused", window_id=str(data.get("window_id", "")))

    if family == "window_unfocused":
        return WindowEvent(type="unfocused", window_id=str(data.get("window_id", "")))

    if family == "window_rescaled":
        return WindowEvent(
            type="rescaled",
            window_id=str(data.get("window_id", "")),
            scale_factor=float(data.get("scale_factor", 1.0)),
        )

    if family == "file_hovered":
        return WindowEvent(
            type="file_hovered",
            window_id=str(data.get("window_id", "")),
            path=str(data.get("path", "")),
        )

    if family == "file_dropped":
        return WindowEvent(
            type="file_dropped",
            window_id=str(data.get("window_id", "")),
            path=str(data.get("path", "")),
        )

    if family == "files_hovered_left":
        return WindowEvent(
            type="files_hovered_left", window_id=str(data.get("window_id", ""))
        )

    # ------- System / animation / theme -------

    if family == "animation_frame":
        return AnimationFrame(timestamp=float(data.get("timestamp", 0)))

    if family == "transition_complete":
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        tag_raw = data.get("tag")
        return TransitionComplete(
            id=local_id,
            tag=str(tag_raw) if tag_raw is not None else None,
            prop=data.get("prop"),
            window_id=_wid,
            scope=scope,
        )

    if family == "theme_changed":
        return ThemeChanged(theme=str(value or ""))

    if family == "all_windows_closed":
        return AllWindowsClosed()

    # ------- Error / announce -------

    if family == "error":
        error_id = wire_id
        if error_id == "duplicate_node_ids":
            return DuplicateNodeIds(details=data)
        if error_id == "command":
            return CommandError(
                reason=str(data.get("reason", "")),
                id=str(data["id"]) if data.get("id") is not None else None,
                family=str(data["family"]) if data.get("family") is not None else None,
                widget=str(data["widget"]) if data.get("widget") is not None else None,
                message=str(data["message"])
                if data.get("message") is not None
                else None,
            )
        return RendererError(id=error_id, data=data)

    if family == "announce":
        return Announce(text=str(data.get("text", "")))

    # ------- Session lifecycle (multiplexed mode) -------

    if family in ("session_error", "session_closed"):
        session_id = str(msg.get("session", ""))
        v = value if isinstance(value, dict) else data
        if family == "session_error":
            return SessionError(
                session=session_id,
                code=str(v.get("code", "")),
                error=str(v.get("error", "")),
            )
        return SessionClosed(session=session_id, reason=str(v.get("reason", "")))

    # ------- Catch-all: unknown widget event -------
    if wire_id:
        local_id, _wid, scope = _split_scoped_with_window(wire_id, msg)
        return RawEvent(
            kind=family,
            id=local_id,
            window_id=_wid,
            value=value,
            data=data if data else None,
            scope=scope,
        )

    # Truly unknown; pass through
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
        return SystemInfo(tag=tag_val, value=data)

    # Unknown op_query_response kind
    return msg


def _decode_diagnostic(msg: dict[str, Any]) -> DiagnosticMessage:
    """Decode a top-level ``diagnostic`` wire message.

    Mirrors the diagnostic to the Python logging module at the matching
    severity, then returns a :class:`DiagnosticMessage` carrying the
    session, level, and the typed variant parsed from the payload.
    Unknown variant kinds raise ``ValueError`` at decode time so host /
    renderer version skew fails loudly instead of being silently
    swallowed.
    """
    from plushie.diagnostics import decode as _decode_variant

    session = str(msg.get("session", "") or "")
    level = str(msg.get("level", "warn") or "warn")
    raw = msg.get("diagnostic")
    if not isinstance(raw, dict):
        raise ValueError(f"diagnostic wire message missing dict payload: {msg!r}")

    variant = _decode_variant(raw)

    log_fn = {
        "error": logger.error,
        "warn": logger.warning,
        "info": logger.info,
    }.get(level, logger.warning)
    log_fn("renderer diagnostic [%s] %s", level, variant)

    return DiagnosticMessage(session=session, level=level, diagnostic=variant)


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
    "command",
    "commands",
    "decode_message",
    "effect_msg",
    "encode_selector",
    "image_op",
    "interact_msg",
    "parse_effect_response",
    "parse_hello",
    "parse_query_response",
    "parse_selector",
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
    "widget_batch",
    "widget_command",
    "widget_op",
    "window_op",
]
