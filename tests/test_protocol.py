"""Tests for plushie.protocol -- message builders and event decoder."""

from __future__ import annotations

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
)
from plushie.protocol import (
    PROTOCOL_VERSION,
    advance_frame_msg,
    decode_message,
    effect_msg,
    encode_selector,
    extension_command,
    extension_commands,
    image_op,
    interact_msg,
    parse_effect_response,
    parse_hello,
    parse_query_response,
    patch,
    query_msg,
    reset_msg,
    screenshot_msg,
    selector_by_id,
    selector_by_label,
    selector_by_role,
    selector_by_text,
    selector_focused,
    settings,
    snapshot,
    subscribe_msg,
    tree_hash_msg,
    unsubscribe_msg,
    widget_op,
    window_op,
)
from plushie.types import HelloInfo

# ===================================================================
# Outbound message builders
# ===================================================================


class TestSettings:
    def test_basic(self) -> None:
        msg = settings({"default_text_size": 14})
        assert msg["type"] == "settings"
        assert msg["session"] == ""
        assert msg["settings"]["default_text_size"] == 14
        assert msg["settings"]["protocol_version"] == PROTOCOL_VERSION

    def test_protocol_version_not_overwritten(self) -> None:
        msg = settings({"protocol_version": 99})
        assert msg["settings"]["protocol_version"] == 99

    def test_custom_session(self) -> None:
        msg = settings({}, session="s1")
        assert msg["session"] == "s1"


class TestSnapshot:
    def test_structure(self) -> None:
        tree = {"id": "root", "type": "window", "props": {}, "children": []}
        msg = snapshot(tree)
        assert msg["type"] == "snapshot"
        assert msg["tree"] == tree
        assert msg["session"] == ""


class TestPatch:
    def test_structure(self) -> None:
        ops = [{"op": "update_props", "path": [0], "props": {"label": "hi"}}]
        msg = patch(ops)
        assert msg["type"] == "patch"
        assert msg["ops"] == ops


class TestSubscribe:
    def test_basic(self) -> None:
        msg = subscribe_msg("on_key_press", "kb1")
        assert msg["type"] == "subscribe"
        assert msg["kind"] == "on_key_press"
        assert msg["tag"] == "kb1"
        assert "max_rate" not in msg

    def test_with_max_rate(self) -> None:
        msg = subscribe_msg("on_mouse_move", "mm", max_rate=60)
        assert msg["max_rate"] == 60


class TestUnsubscribe:
    def test_structure(self) -> None:
        msg = unsubscribe_msg("on_key_press")
        assert msg["type"] == "unsubscribe"
        assert msg["kind"] == "on_key_press"


class TestWidgetOp:
    def test_focus(self) -> None:
        msg = widget_op("focus", {"target": "input1"})
        assert msg["type"] == "widget_op"
        assert msg["op"] == "focus"
        assert msg["payload"]["target"] == "input1"

    def test_no_payload(self) -> None:
        msg = widget_op("focus_next")
        assert msg["payload"] == {}


class TestWindowOp:
    def test_resize(self) -> None:
        msg = window_op("resize", "win1", {"width": 800, "height": 600})
        assert msg["type"] == "window_op"
        assert msg["op"] == "resize"
        assert msg["window_id"] == "win1"
        assert msg["settings"]["width"] == 800

    def test_no_settings_defaults_to_empty(self) -> None:
        msg = window_op("close", "win1")
        assert msg["settings"] == {}


class TestEffectMsg:
    def test_structure(self) -> None:
        msg = effect_msg("req1", "file_open", {"title": "Open"})
        assert msg["type"] == "effect"
        assert msg["id"] == "req1"
        assert msg["kind"] == "file_open"
        assert msg["payload"]["title"] == "Open"


class TestImageOp:
    def test_create_with_data(self) -> None:
        msg = image_op("create_image", "img1", data=b"\x89PNG")
        assert msg["type"] == "image_op"
        assert msg["op"] == "create_image"
        assert msg["handle"] == "img1"
        assert msg["data"] == b"\x89PNG"

    def test_create_with_pixels(self) -> None:
        msg = image_op("create_image", "img1", pixels=b"\x00" * 16, width=2, height=2)
        assert msg["pixels"] == b"\x00" * 16
        assert msg["width"] == 2
        assert msg["height"] == 2

    def test_delete(self) -> None:
        msg = image_op("delete_image", "img1")
        assert msg["op"] == "delete_image"
        assert "data" not in msg


class TestExtensionCommand:
    def test_structure(self) -> None:
        msg = extension_command("chart1", "append_data", {"values": [1, 2]})
        assert msg["type"] == "extension_command"
        assert msg["node_id"] == "chart1"
        assert msg["op"] == "append_data"
        assert msg["payload"]["values"] == [1, 2]


class TestExtensionCommands:
    def test_batch(self) -> None:
        cmds = [
            {"node_id": "a", "op": "x", "payload": {}},
            {"node_id": "b", "op": "y", "payload": {}},
        ]
        msg = extension_commands(cmds)
        assert msg["type"] == "extension_commands"
        assert len(msg["commands"]) == 2


class TestInteractMsg:
    def test_click(self) -> None:
        msg = interact_msg("i1", "click", {"by": "id", "value": "btn1"})
        assert msg["type"] == "interact"
        assert msg["action"] == "click"
        assert msg["selector"]["by"] == "id"

    def test_type_text(self) -> None:
        msg = interact_msg(
            "i2", "type_text", {"by": "id", "value": "inp"}, {"text": "hello"}
        )
        assert msg["payload"]["text"] == "hello"


class TestQueryMsg:
    def test_find(self) -> None:
        msg = query_msg("q1", "find", {"by": "id", "value": "btn1"})
        assert msg["type"] == "query"
        assert msg["target"] == "find"
        assert msg["selector"]["by"] == "id"

    def test_tree(self) -> None:
        msg = query_msg("q2", "tree")
        assert msg["target"] == "tree"
        assert msg["selector"] == {}


class TestTreeHashMsg:
    def test_structure(self) -> None:
        msg = tree_hash_msg("th1", "after_click")
        assert msg["type"] == "tree_hash"
        assert msg["name"] == "after_click"


class TestScreenshotMsg:
    def test_defaults(self) -> None:
        msg = screenshot_msg("sc1", "homepage")
        assert msg["type"] == "screenshot"
        assert msg["width"] == 1024
        assert msg["height"] == 768

    def test_custom_size(self) -> None:
        msg = screenshot_msg("sc1", "small", width=320, height=240)
        assert msg["width"] == 320


class TestResetMsg:
    def test_structure(self) -> None:
        msg = reset_msg("r1")
        assert msg["type"] == "reset"
        assert msg["id"] == "r1"


class TestAdvanceFrameMsg:
    def test_structure(self) -> None:
        msg = advance_frame_msg(16000)
        assert msg["type"] == "advance_frame"
        assert msg["timestamp"] == 16000


# ===================================================================
# Selector helpers
# ===================================================================


class TestSelectors:
    def test_encode_selector_id(self) -> None:
        sel = encode_selector("#btn_save")
        assert sel == {"by": "id", "value": "btn_save"}

    def test_encode_selector_text(self) -> None:
        sel = encode_selector("Hello World")
        assert sel == {"by": "text", "value": "Hello World"}

    def test_selector_by_id(self) -> None:
        assert selector_by_id("x") == {"by": "id", "value": "x"}

    def test_selector_by_text(self) -> None:
        assert selector_by_text("hello") == {"by": "text", "value": "hello"}

    def test_selector_by_role(self) -> None:
        assert selector_by_role("button") == {"by": "role", "value": "button"}

    def test_selector_by_label(self) -> None:
        assert selector_by_label("Save") == {"by": "label", "value": "Save"}

    def test_selector_focused(self) -> None:
        assert selector_focused() == {"by": "focused"}


# ===================================================================
# Response parsers
# ===================================================================


class TestParseHello:
    def test_full(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol": 1,
            "version": "0.4.0",
            "name": "plushie",
            "mode": "mock",
            "backend": "none",
            "transport": "stdio",
            "extensions": ["charts"],
        }
        info = parse_hello(raw)
        assert isinstance(info, HelloInfo)
        assert info.protocol == 1
        assert info.version == "0.4.0"
        assert info.name == "plushie"
        assert info.mode == "mock"
        assert info.backend == "none"
        assert info.transport == "stdio"
        assert info.extensions == ("charts",)

    def test_no_extensions(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol": 1,
            "version": "0.1.0",
            "name": "plushie",
            "mode": "headless",
            "backend": "tiny-skia",
        }
        info = parse_hello(raw)
        assert info.extensions == ()
        assert info.transport == "stdio"


class TestParseQueryResponse:
    def test_find(self) -> None:
        raw = {
            "type": "query_response",
            "session": "",
            "id": "q1",
            "target": "find",
            "data": {"id": "btn1", "type": "button", "props": {}, "children": []},
        }
        result = parse_query_response(raw)
        assert result["id"] == "q1"
        assert result["target"] == "find"
        assert result["data"]["id"] == "btn1"

    def test_not_found(self) -> None:
        raw = {"type": "query_response", "id": "q1", "target": "find", "data": None}
        result = parse_query_response(raw)
        assert result["data"] is None


class TestParseEffectResponse:
    def test_ok(self) -> None:
        raw = {
            "type": "effect_response",
            "id": "req1",
            "status": "ok",
            "result": {"path": "/tmp/file.txt"},
        }
        result = parse_effect_response(raw)
        assert isinstance(result, EffectResult)
        assert result.request_id == "req1"
        assert result.status == "ok"
        assert result.result == {"path": "/tmp/file.txt"}

    def test_cancelled(self) -> None:
        raw = {"type": "effect_response", "id": "req2", "status": "cancelled"}
        result = parse_effect_response(raw)
        assert result.status == "cancelled"
        assert result.result is None

    def test_error(self) -> None:
        raw = {
            "type": "effect_response",
            "id": "req3",
            "status": "error",
            "error": "permission denied",
        }
        result = parse_effect_response(raw)
        assert result.status == "error"
        assert result.error == "permission denied"


# ===================================================================
# decode_message -- event dispatch for EVERY family
# ===================================================================


class TestDecodeHello:
    def test_via_decode_message(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol": 1,
            "version": "0.3.0",
            "name": "plushie",
            "mode": "mock",
            "backend": "none",
            "transport": "stdio",
            "extensions": [],
        }
        result = decode_message(raw)
        assert isinstance(result, HelloInfo)


class TestDecodeEffectResponse:
    def test_via_decode_message(self) -> None:
        raw = {"type": "effect_response", "id": "r1", "status": "ok", "result": None}
        result = decode_message(raw)
        assert isinstance(result, EffectResult)


class TestDecodeWidgetEvents:
    def test_click(self) -> None:
        raw = {"type": "event", "family": "click", "id": "btn1"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "btn1"
        assert result.scope == ()

    def test_click_scoped(self) -> None:
        raw = {"type": "event", "family": "click", "id": "form/section/save"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("section", "form")

    def test_input(self) -> None:
        raw = {"type": "event", "family": "input", "id": "name", "value": "Alice"}
        result = decode_message(raw)
        assert isinstance(result, Input)
        assert result.value == "Alice"

    def test_submit(self) -> None:
        raw = {"type": "event", "family": "submit", "id": "search", "value": "query"}
        result = decode_message(raw)
        assert isinstance(result, Submit)
        assert result.value == "query"

    def test_toggle(self) -> None:
        raw = {"type": "event", "family": "toggle", "id": "cb", "value": True}
        result = decode_message(raw)
        assert isinstance(result, Toggle)
        assert result.value is True

    def test_select(self) -> None:
        raw = {"type": "event", "family": "select", "id": "pick", "value": "option_a"}
        result = decode_message(raw)
        assert isinstance(result, Select)
        assert result.value == "option_a"

    def test_slide(self) -> None:
        raw = {"type": "event", "family": "slide", "id": "vol", "value": 0.75}
        result = decode_message(raw)
        assert isinstance(result, Slide)
        assert result.value == 0.75

    def test_slide_release(self) -> None:
        raw = {"type": "event", "family": "slide_release", "id": "vol", "value": 0.8}
        result = decode_message(raw)
        assert isinstance(result, SlideRelease)
        assert result.value == 0.8

    def test_scroll(self) -> None:
        raw = {
            "type": "event",
            "family": "scroll",
            "id": "log",
            "data": {
                "absolute_x": 0,
                "absolute_y": 100,
                "relative_x": 0,
                "relative_y": 0.5,
                "bounds_width": 400,
                "bounds_height": 300,
                "content_width": 400,
                "content_height": 600,
            },
        }
        result = decode_message(raw)
        assert isinstance(result, Scroll)
        assert result.data.absolute_y == 100
        assert result.data.content_height == 600

    def test_paste(self) -> None:
        raw = {"type": "event", "family": "paste", "id": "ed", "value": "pasted text"}
        result = decode_message(raw)
        assert isinstance(result, Paste)
        assert result.value == "pasted text"

    def test_sort(self) -> None:
        raw = {
            "type": "event",
            "family": "sort",
            "id": "tbl",
            "data": {"column": "name"},
        }
        result = decode_message(raw)
        assert isinstance(result, Sort)
        assert result.value == "name"

    def test_open(self) -> None:
        raw = {"type": "event", "family": "open", "id": "combo"}
        result = decode_message(raw)
        assert isinstance(result, Open)

    def test_close(self) -> None:
        raw = {"type": "event", "family": "close", "id": "combo"}
        result = decode_message(raw)
        assert isinstance(result, Close)

    def test_option_hovered(self) -> None:
        raw = {
            "type": "event",
            "family": "option_hovered",
            "id": "pick",
            "value": "opt",
        }
        result = decode_message(raw)
        assert isinstance(result, OptionHovered)
        assert result.value == "opt"

    def test_key_binding_data_string(self) -> None:
        raw = {
            "type": "event",
            "family": "key_binding",
            "id": "editor",
            "data": "save",
        }
        result = decode_message(raw)
        assert isinstance(result, KeyBinding)
        assert result.value == "save"

    def test_key_binding_data_dict(self) -> None:
        raw = {
            "type": "event",
            "family": "key_binding",
            "id": "editor",
            "data": {"binding": "undo"},
        }
        result = decode_message(raw)
        assert isinstance(result, KeyBinding)
        assert result.value == "undo"


class TestDecodeMouseAreaEvents:
    def test_mouse_right_press(self) -> None:
        raw = {"type": "event", "family": "mouse_right_press", "id": "area1"}
        result = decode_message(raw)
        assert isinstance(result, MouseAreaRightPress)

    def test_mouse_right_release(self) -> None:
        raw = {"type": "event", "family": "mouse_right_release", "id": "area1"}
        assert isinstance(decode_message(raw), MouseAreaRightRelease)

    def test_mouse_middle_press(self) -> None:
        raw = {"type": "event", "family": "mouse_middle_press", "id": "area1"}
        assert isinstance(decode_message(raw), MouseAreaMiddlePress)

    def test_mouse_middle_release(self) -> None:
        raw = {"type": "event", "family": "mouse_middle_release", "id": "area1"}
        assert isinstance(decode_message(raw), MouseAreaMiddleRelease)

    def test_mouse_double_click(self) -> None:
        raw = {"type": "event", "family": "mouse_double_click", "id": "area1"}
        assert isinstance(decode_message(raw), MouseAreaDoubleClick)

    def test_mouse_enter(self) -> None:
        raw = {"type": "event", "family": "mouse_enter", "id": "area1"}
        assert isinstance(decode_message(raw), MouseAreaEnter)

    def test_mouse_exit(self) -> None:
        raw = {"type": "event", "family": "mouse_exit", "id": "area1"}
        assert isinstance(decode_message(raw), MouseAreaExit)

    def test_mouse_move(self) -> None:
        raw = {
            "type": "event",
            "family": "mouse_move",
            "id": "area1",
            "data": {"x": 10.5, "y": 20.3},
        }
        result = decode_message(raw)
        assert isinstance(result, MouseAreaMove)
        assert result.x == 10.5
        assert result.y == 20.3

    def test_mouse_scroll(self) -> None:
        raw = {
            "type": "event",
            "family": "mouse_scroll",
            "id": "area1",
            "data": {"delta_x": 0, "delta_y": -3.0},
        }
        result = decode_message(raw)
        assert isinstance(result, MouseAreaScroll)
        assert result.delta_y == -3.0


class TestDecodeCanvasEvents:
    def test_canvas_press(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_press",
            "id": "canvas1",
            "data": {"x": 50, "y": 60, "button": "left"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasPress)
        assert result.button == "left"

    def test_canvas_release(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_release",
            "id": "canvas1",
            "data": {"x": 50, "y": 60, "button": "right"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasRelease)
        assert result.button == "right"

    def test_canvas_move(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_move",
            "id": "canvas1",
            "data": {"x": 100, "y": 200},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasMove)
        assert result.x == 100

    def test_canvas_scroll(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_scroll",
            "id": "canvas1",
            "data": {"x": 50, "y": 50, "delta_x": 0, "delta_y": -5},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasScroll)
        assert result.delta_y == -5


class TestDecodeCanvasElementEvents:
    def test_element_enter(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_enter",
            "id": "canvas1",
            "data": {"element_id": "bar1", "x": 10, "y": 20},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasElementEnter)
        assert result.element_id == "bar1"

    def test_element_leave(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_leave",
            "id": "canvas1",
            "data": {"element_id": "bar1"},
        }
        assert isinstance(decode_message(raw), CanvasElementLeave)

    def test_element_click(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_click",
            "id": "canvas1",
            "data": {"element_id": "bar1", "x": 15, "y": 25, "button": "keyboard"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasElementClick)
        assert result.button == "keyboard"

    def test_element_drag(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_drag",
            "id": "canvas1",
            "data": {
                "element_id": "node1",
                "x": 100,
                "y": 200,
                "delta_x": 5,
                "delta_y": -3,
            },
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasElementDrag)
        assert result.delta_x == 5

    def test_element_drag_end(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_drag_end",
            "id": "canvas1",
            "data": {"element_id": "node1", "x": 105, "y": 197},
        }
        assert isinstance(decode_message(raw), CanvasElementDragEnd)

    def test_element_focused(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_focused",
            "id": "canvas1",
            "data": {"element_id": "bar1"},
        }
        assert isinstance(decode_message(raw), CanvasElementFocused)

    def test_element_blurred(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_blurred",
            "id": "canvas1",
            "data": {"element_id": "bar1"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasElementBlurred)
        assert result.element_id == "bar1"

    def test_element_key_press(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_key_press",
            "id": "scope1/canvas1",
            "data": {"element_id": "item1", "key": "ArrowRight"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasElementKeyPress)
        assert result.id == "canvas1"
        assert result.element_id == "item1"
        assert result.key == "ArrowRight"
        assert result.scope == ("scope1",)

    def test_element_key_release(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_element_key_release",
            "id": "canvas1",
            "data": {"element_id": "item1", "key": "Enter"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasElementKeyRelease)
        assert result.id == "canvas1"
        assert result.element_id == "item1"
        assert result.key == "Enter"
        assert result.scope == ()


class TestDecodeCanvasLifecycleEvents:
    def test_canvas_focused(self) -> None:
        raw = {"type": "event", "family": "canvas_focused", "id": "canvas1"}
        result = decode_message(raw)
        assert isinstance(result, CanvasFocused)
        assert result.id == "canvas1"

    def test_canvas_blurred(self) -> None:
        raw = {"type": "event", "family": "canvas_blurred", "id": "canvas1"}
        result = decode_message(raw)
        assert isinstance(result, CanvasBlurred)
        assert result.id == "canvas1"


class TestDecodeCanvasGroupEvents:
    def test_group_focused(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_group_focused",
            "id": "canvas1",
            "data": {"group_id": "toolbar"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasGroupFocused)
        assert result.group_id == "toolbar"

    def test_group_blurred(self) -> None:
        raw = {
            "type": "event",
            "family": "canvas_group_blurred",
            "id": "canvas1",
            "data": {"group_id": "toolbar"},
        }
        result = decode_message(raw)
        assert isinstance(result, CanvasGroupBlurred)
        assert result.group_id == "toolbar"


class TestDecodeDiagnostic:
    def test_diagnostic(self) -> None:
        raw = {
            "type": "event",
            "family": "diagnostic",
            "id": "",
            "data": {
                "level": "warning",
                "element_id": "star-0",
                "code": "MISSING_A11Y",
                "message": "Interactive element has no a11y label",
            },
        }
        result = decode_message(raw)
        assert isinstance(result, Diagnostic)
        assert result.level == "warning"
        assert result.element_id == "star-0"
        assert result.code == "MISSING_A11Y"


class TestDecodeSensorEvents:
    def test_sensor_resize(self) -> None:
        raw = {
            "type": "event",
            "family": "sensor_resize",
            "id": "sensor1",
            "data": {"width": 300, "height": 200},
        }
        result = decode_message(raw)
        assert isinstance(result, SensorResize)
        assert result.width == 300


class TestDecodePaneEvents:
    def test_pane_resized(self) -> None:
        raw = {
            "type": "event",
            "family": "pane_resized",
            "id": "grid1",
            "data": {"split": "s1", "ratio": 0.6},
        }
        result = decode_message(raw)
        assert isinstance(result, PaneResized)
        assert result.ratio == 0.6

    def test_pane_dragged(self) -> None:
        raw = {
            "type": "event",
            "family": "pane_dragged",
            "id": "grid1",
            "data": {
                "pane": "p1",
                "target": "p2",
                "action": "dropped",
                "region": "center",
                "edge": None,
            },
        }
        result = decode_message(raw)
        assert isinstance(result, PaneDragged)
        assert result.action == "dropped"

    def test_pane_clicked(self) -> None:
        raw = {
            "type": "event",
            "family": "pane_clicked",
            "id": "grid1",
            "data": {"pane": "p1"},
        }
        assert isinstance(decode_message(raw), PaneClicked)

    def test_pane_focus_cycle(self) -> None:
        raw = {
            "type": "event",
            "family": "pane_focus_cycle",
            "id": "grid1",
            "data": {"pane": "p2"},
        }
        assert isinstance(decode_message(raw), PaneFocusCycle)


class TestDecodeKeyEvents:
    def test_key_press(self) -> None:
        raw = {
            "type": "event",
            "family": "key_press",
            "id": "",
            "tag": "kb",
            "data": {
                "key": "a",
                "modified_key": "A",
                "physical_key": "KeyA",
                "location": "standard",
                "text": "A",
                "repeat": False,
            },
            "modifiers": {"shift": True, "ctrl": False, "alt": False, "logo": False},
        }
        result = decode_message(raw)
        assert isinstance(result, KeyPress)
        assert result.key == "a"
        assert result.modified_key == "A"
        assert result.modifiers.shift is True
        assert result.text == "A"

    def test_key_release(self) -> None:
        raw = {
            "type": "event",
            "family": "key_release",
            "id": "",
            "tag": "kb",
            "data": {"key": "Escape", "modified_key": "Escape"},
            "modifiers": {},
        }
        result = decode_message(raw)
        assert isinstance(result, KeyRelease)
        assert result.key == "Escape"

    def test_modifiers_changed(self) -> None:
        raw = {
            "type": "event",
            "family": "modifiers_changed",
            "id": "",
            "tag": "kb",
            "modifiers": {"shift": False, "ctrl": True, "alt": False, "logo": False},
        }
        result = decode_message(raw)
        assert isinstance(result, ModifiersChanged)
        assert result.modifiers.ctrl is True


class TestDecodeMouseEvents:
    def test_cursor_moved(self) -> None:
        raw = {
            "type": "event",
            "family": "cursor_moved",
            "id": "",
            "tag": "m",
            "data": {"x": 100.5, "y": 200.3},
        }
        result = decode_message(raw)
        assert isinstance(result, MouseMove)
        assert result.x == 100.5

    def test_cursor_entered(self) -> None:
        raw = {"type": "event", "family": "cursor_entered", "id": "", "tag": "m"}
        assert isinstance(decode_message(raw), MouseEnter)

    def test_cursor_left(self) -> None:
        raw = {"type": "event", "family": "cursor_left", "id": "", "tag": "m"}
        assert isinstance(decode_message(raw), MouseLeave)

    def test_button_pressed(self) -> None:
        raw = {
            "type": "event",
            "family": "button_pressed",
            "id": "",
            "tag": "m",
            "value": "left",
        }
        result = decode_message(raw)
        assert isinstance(result, MouseButtonPress)
        assert result.button == "left"

    def test_button_released(self) -> None:
        raw = {
            "type": "event",
            "family": "button_released",
            "id": "",
            "tag": "m",
            "value": "right",
        }
        result = decode_message(raw)
        assert isinstance(result, MouseButtonRelease)
        assert result.button == "right"

    def test_wheel_scrolled(self) -> None:
        raw = {
            "type": "event",
            "family": "wheel_scrolled",
            "id": "",
            "tag": "m",
            "data": {"delta_x": 0, "delta_y": -3, "unit": "pixel"},
        }
        result = decode_message(raw)
        assert isinstance(result, MouseWheel)
        assert result.unit == "pixel"


class TestDecodeTouchEvents:
    def test_finger_pressed(self) -> None:
        raw = {
            "type": "event",
            "family": "finger_pressed",
            "id": "",
            "tag": "t",
            "data": {"id": 1, "x": 50, "y": 60},
        }
        result = decode_message(raw)
        assert isinstance(result, TouchPress)
        assert result.finger_id == 1

    def test_finger_moved(self) -> None:
        raw = {
            "type": "event",
            "family": "finger_moved",
            "id": "",
            "tag": "t",
            "data": {"id": 2, "x": 55, "y": 65},
        }
        assert isinstance(decode_message(raw), TouchMove)

    def test_finger_lifted(self) -> None:
        raw = {
            "type": "event",
            "family": "finger_lifted",
            "id": "",
            "tag": "t",
            "data": {"id": 1, "x": 50, "y": 60},
        }
        assert isinstance(decode_message(raw), TouchLift)

    def test_finger_lost(self) -> None:
        raw = {
            "type": "event",
            "family": "finger_lost",
            "id": "",
            "tag": "t",
            "data": {"id": 3, "x": 0, "y": 0},
        }
        assert isinstance(decode_message(raw), TouchLost)


class TestDecodeImeEvents:
    def test_ime_opened(self) -> None:
        raw = {"type": "event", "family": "ime_opened", "id": "", "tag": "ime"}
        assert isinstance(decode_message(raw), ImeOpen)

    def test_ime_preedit(self) -> None:
        raw = {
            "type": "event",
            "family": "ime_preedit",
            "id": "",
            "tag": "ime",
            "data": {"text": "ni", "cursor": {"start": 0, "end": 2}},
        }
        result = decode_message(raw)
        assert isinstance(result, ImePreedit)
        assert result.text == "ni"
        assert result.cursor == (0, 2)

    def test_ime_preedit_no_cursor(self) -> None:
        raw = {
            "type": "event",
            "family": "ime_preedit",
            "id": "",
            "tag": "ime",
            "data": {"text": "abc"},
        }
        result = decode_message(raw)
        assert isinstance(result, ImePreedit)
        assert result.cursor is None

    def test_ime_commit(self) -> None:
        raw = {
            "type": "event",
            "family": "ime_commit",
            "id": "",
            "tag": "ime",
            "data": {"text": "你好"},
        }
        result = decode_message(raw)
        assert isinstance(result, ImeCommit)
        assert result.text == "你好"

    def test_ime_closed(self) -> None:
        raw = {"type": "event", "family": "ime_closed", "id": "", "tag": "ime"}
        assert isinstance(decode_message(raw), ImeClose)


class TestDecodeWindowEvents:
    def test_window_opened(self) -> None:
        raw = {
            "type": "event",
            "family": "window_opened",
            "id": "",
            "tag": "win",
            "data": {
                "window_id": "win1",
                "width": 800,
                "height": 600,
                "position": {"x": 100, "y": 50},
                "scale_factor": 2.0,
            },
        }
        result = decode_message(raw)
        assert isinstance(result, WindowOpen)
        assert result.window_id == "win1"
        assert result.width == 800
        assert result.position_x == 100
        assert result.scale_factor == 2.0

    def test_window_opened_no_position(self) -> None:
        raw = {
            "type": "event",
            "family": "window_opened",
            "id": "",
            "tag": "win",
            "data": {
                "window_id": "w",
                "width": 640,
                "height": 480,
                "scale_factor": 1.0,
            },
        }
        result = decode_message(raw)
        assert isinstance(result, WindowOpen)
        assert result.position_x is None
        assert result.position_y is None

    def test_window_closed(self) -> None:
        raw = {
            "type": "event",
            "family": "window_closed",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowClosed)

    def test_window_close_requested(self) -> None:
        raw = {
            "type": "event",
            "family": "window_close_requested",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowCloseRequested)

    def test_window_resized(self) -> None:
        raw = {
            "type": "event",
            "family": "window_resized",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "width": 1024, "height": 768},
        }
        result = decode_message(raw)
        assert isinstance(result, WindowResized)
        assert result.width == 1024

    def test_window_moved(self) -> None:
        raw = {
            "type": "event",
            "family": "window_moved",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "x": 200, "y": 100},
        }
        result = decode_message(raw)
        assert isinstance(result, WindowMoved)
        assert result.x == 200

    def test_window_focused(self) -> None:
        raw = {
            "type": "event",
            "family": "window_focused",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowFocused)

    def test_window_unfocused(self) -> None:
        raw = {
            "type": "event",
            "family": "window_unfocused",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowUnfocused)

    def test_window_rescaled(self) -> None:
        raw = {
            "type": "event",
            "family": "window_rescaled",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "scale_factor": 1.5},
        }
        result = decode_message(raw)
        assert isinstance(result, WindowRescaled)
        assert result.scale_factor == 1.5

    def test_file_hovered(self) -> None:
        raw = {
            "type": "event",
            "family": "file_hovered",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "path": "/tmp/file.txt"},
        }
        result = decode_message(raw)
        assert isinstance(result, FileHovered)
        assert result.path == "/tmp/file.txt"

    def test_file_dropped(self) -> None:
        raw = {
            "type": "event",
            "family": "file_dropped",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "path": "/tmp/dropped.txt"},
        }
        assert isinstance(decode_message(raw), FileDropped)

    def test_files_hovered_left(self) -> None:
        raw = {
            "type": "event",
            "family": "files_hovered_left",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), FilesHoveredLeft)


class TestDecodeSystemEvents:
    def test_animation_frame(self) -> None:
        raw = {
            "type": "event",
            "family": "animation_frame",
            "id": "",
            "tag": "anim",
            "data": {"timestamp": 16000},
        }
        result = decode_message(raw)
        assert isinstance(result, AnimationFrame)
        assert result.timestamp == 16000

    def test_theme_changed(self) -> None:
        raw = {
            "type": "event",
            "family": "theme_changed",
            "id": "",
            "tag": "theme",
            "value": "dark",
        }
        result = decode_message(raw)
        assert isinstance(result, ThemeChanged)
        assert result.theme == "dark"

    def test_all_windows_closed(self) -> None:
        raw = {"type": "event", "family": "all_windows_closed", "id": ""}
        result = decode_message(raw)
        assert isinstance(result, AllWindowsClosed)


class TestDecodeErrorAndAnnounce:
    def test_duplicate_node_ids(self) -> None:
        raw = {
            "type": "event",
            "family": "error",
            "id": "duplicate_node_ids",
            "data": {
                "error": "snapshot contains duplicate node IDs",
                "duplicates": ["a", "b"],
            },
        }
        result = decode_message(raw)
        assert isinstance(result, DuplicateNodeIds)
        assert "duplicates" in result.details

    def test_announce(self) -> None:
        raw = {
            "type": "event",
            "family": "announce",
            "id": "",
            "data": {"text": "Item saved"},
        }
        result = decode_message(raw)
        assert isinstance(result, Announce)
        assert result.text == "Item saved"


class TestDecodeOpQueryResponse:
    def test_tree_hash(self) -> None:
        raw = {
            "type": "op_query_response",
            "session": "",
            "kind": "tree_hash",
            "tag": "th1",
            "data": {"hash": "abc123"},
        }
        result = decode_message(raw)
        assert isinstance(result, TreeHash)
        assert result.hash == "abc123"
        assert result.tag == "th1"

    def test_find_focused(self) -> None:
        raw = {
            "type": "op_query_response",
            "session": "",
            "kind": "find_focused",
            "tag": "f1",
            "data": {"focused": "input1"},
        }
        result = decode_message(raw)
        assert isinstance(result, FocusedWidget)
        assert result.widget_id == "input1"

    def test_find_focused_none(self) -> None:
        raw = {
            "type": "op_query_response",
            "session": "",
            "kind": "find_focused",
            "tag": "f1",
            "data": {"focused": None},
        }
        result = decode_message(raw)
        assert isinstance(result, FocusedWidget)
        assert result.widget_id is None

    def test_list_images(self) -> None:
        raw = {
            "type": "op_query_response",
            "session": "",
            "kind": "list_images",
            "tag": "li",
            "data": {"handles": ["img1", "img2"]},
        }
        result = decode_message(raw)
        assert isinstance(result, ImageList)
        assert result.handles == ("img1", "img2")

    def test_system_theme(self) -> None:
        raw = {
            "type": "op_query_response",
            "session": "",
            "kind": "system_theme",
            "tag": "st",
            "data": "dark",
        }
        result = decode_message(raw)
        assert isinstance(result, SystemTheme)
        assert result.theme == "dark"

    def test_system_info(self) -> None:
        raw = {
            "type": "op_query_response",
            "session": "",
            "kind": "system_info",
            "tag": "si",
            "data": {"cpu_brand": "Intel", "memory_total": 16000000000},
        }
        result = decode_message(raw)
        assert isinstance(result, SystemInfo)
        assert result.data["cpu_brand"] == "Intel"


class TestDecodePassthrough:
    def test_query_response_passthrough(self) -> None:
        raw = {
            "type": "query_response",
            "session": "",
            "id": "q1",
            "target": "find",
            "data": {"id": "btn1"},
        }
        result = decode_message(raw)
        assert isinstance(result, dict)
        assert result["type"] == "query_response"

    def test_interact_response_passthrough(self) -> None:
        raw = {
            "type": "interact_response",
            "session": "",
            "id": "i1",
            "events": [],
        }
        result = decode_message(raw)
        assert isinstance(result, dict)

    def test_unknown_event_with_id_becomes_widget_event(self) -> None:
        raw = {
            "type": "event",
            "family": "custom_future_event",
            "id": "widget1",
            "value": "something",
        }
        result = decode_message(raw)
        assert isinstance(result, WidgetEvent)
        assert result.kind == "custom_future_event"

    def test_captured_flag_on_subscription_events(self) -> None:
        raw = {
            "type": "event",
            "family": "key_press",
            "id": "",
            "tag": "kb",
            "data": {"key": "Tab", "modified_key": "Tab"},
            "modifiers": {},
            "captured": True,
        }
        result = decode_message(raw)
        assert isinstance(result, KeyPress)
        assert result.captured is True


class TestDecodeScopedIdSplitting:
    def test_no_scope(self) -> None:
        raw = {"type": "event", "family": "click", "id": "save"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ()

    def test_single_scope(self) -> None:
        raw = {"type": "event", "family": "click", "id": "form/save"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("form",)

    def test_deep_scope(self) -> None:
        raw = {"type": "event", "family": "click", "id": "app/form/section/save"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("section", "form", "app")
