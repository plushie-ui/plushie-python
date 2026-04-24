"""Tests for plushie.protocol: message builders and event decoder."""

from __future__ import annotations

import pytest

from plushie.events import (
    AllWindowsClosed,
    AnimationFrame,
    Blurred,
    Click,
    Close,
    Diagnostic,
    DoubleClick,
    Drag,
    DragEnd,
    DuplicateNodeIds,
    EffectStubAck,
    Enter,
    Exit,
    Focused,
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
    Press,
    RawEvent,
    Release,
    Resize,
    Scroll,
    Scrolled,
    Select,
    SessionClosed,
    SessionError,
    Slide,
    SlideRelease,
    Sort,
    Submit,
    SystemInfo,
    ThemeChanged,
    Toggle,
    WindowEvent,
)
from plushie.protocol import (
    PROTOCOL_VERSION,
    advance_frame_msg,
    command,
    commands,
    decode_message,
    effect_msg,
    encode_selector,
    image_op,
    interact_msg,
    parse_effect_response,
    parse_hello,
    parse_query_response,
    parse_selector,
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
    widget_command,
    widget_op,
    window_op,
)
from plushie.protocol import (
    register_effect_stub as register_effect_stub_msg,
)
from plushie.protocol import (
    unregister_effect_stub as unregister_effect_stub_msg,
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

    def test_required_widgets_passthrough(self) -> None:
        # When the app supplies required_widgets, the names must
        # land on the wire verbatim so the renderer can validate.
        msg = settings({"required_widgets": ["gauge", "custom_chart"]})
        assert msg["settings"]["required_widgets"] == ["gauge", "custom_chart"]

    def test_required_widgets_absent_when_unset(self) -> None:
        # The Python SDK forwards only keys the app explicitly
        # provides; required_widgets stays absent when the app's
        # settings() dict doesn't mention it.
        msg = settings({})
        assert "required_widgets" not in msg["settings"]

    def test_rejects_non_dict_settings(self) -> None:
        with pytest.raises(ValueError, match="settings must be a dict"):
            settings([])  # type: ignore[arg-type]

    def test_rejects_unknown_setting_key(self) -> None:
        with pytest.raises(ValueError, match="unknown setting key: defualt_text_size"):
            settings({"defualt_text_size": 14})

    def test_widget_config_passthrough(self) -> None:
        widget_cfg = {"sparkline": {"color": "red"}}
        msg = settings({"widget_config": widget_cfg})
        assert msg["settings"]["widget_config"] == widget_cfg

    def test_validate_props_accepted(self) -> None:
        msg = settings({"validate_props": True})
        assert msg["settings"]["validate_props"] is True

    def test_rejects_extension_config(self) -> None:
        with pytest.raises(ValueError, match="unknown setting key: extension_config"):
            settings({"extension_config": {}})


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
        assert msg["payload"]["width"] == 800

    def test_no_payload_defaults_to_empty(self) -> None:
        msg = window_op("close", "win1")
        assert msg["payload"] == {}


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
        assert msg["payload"]["handle"] == "img1"
        assert msg["payload"]["data"] == b"\x89PNG"

    def test_create_with_pixels(self) -> None:
        msg = image_op("create_image", "img1", pixels=b"\x00" * 16, width=2, height=2)
        assert msg["payload"]["pixels"] == b"\x00" * 16
        assert msg["payload"]["width"] == 2
        assert msg["payload"]["height"] == 2

    def test_delete(self) -> None:
        msg = image_op("delete_image", "img1")
        assert msg["op"] == "delete_image"
        assert "data" not in msg["payload"]


class TestCommand:
    def test_structure(self) -> None:
        msg = command("chart1", "append_data", {"values": [1, 2]})
        assert msg["type"] == "command"
        assert msg["id"] == "chart1"
        assert msg["family"] == "append_data"
        assert msg["value"] == {"values": [1, 2]}

    def test_without_value(self) -> None:
        msg = command("chart1", "reset")
        assert msg["type"] == "command"
        assert "value" not in msg

    def test_widget_command_alias(self) -> None:
        assert widget_command("chart1", "reset") == command("chart1", "reset")


class TestCommands:
    def test_batch(self) -> None:
        cmds = [("a", "x", None), ("b", "y", {"z": 1})]
        msg = commands(cmds)
        assert msg["type"] == "commands"
        assert len(msg["commands"]) == 2
        assert msg["commands"][0] == {"id": "a", "family": "x"}
        assert msg["commands"][1] == {"id": "b", "family": "y", "value": {"z": 1}}

    def test_widget_batch_alias(self) -> None:
        from plushie.protocol import widget_batch

        cmds = [("a", "x", None), ("b", "y", {"z": 1})]
        assert widget_batch(cmds) == commands(cmds)


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


class TestEffectStubMessages:
    def test_register_effect_stub(self) -> None:
        msg = register_effect_stub_msg(
            "file_open", {"status": "ok", "result": "/tmp/test.txt"}
        )
        assert msg["type"] == "register_effect_stub"
        assert msg["kind"] == "file_open"
        assert msg["response"]["status"] == "ok"
        assert msg["session"] == ""

    def test_unregister_effect_stub(self) -> None:
        msg = unregister_effect_stub_msg("file_open")
        assert msg["type"] == "unregister_effect_stub"
        assert msg["kind"] == "file_open"

    def test_decode_effect_stub_register_ack(self) -> None:
        raw = {"type": "effect_stub_register_ack", "kind": "clipboard_read"}
        result = decode_message(raw)
        from plushie.events import EffectStubAck

        assert isinstance(result, EffectStubAck)
        assert result.kind == "clipboard_read"
        assert result.registered is True

    def test_decode_effect_stub_unregister_ack(self) -> None:
        raw = {"type": "effect_stub_unregister_ack", "kind": "file_open"}
        result = decode_message(raw)
        from plushie.events import EffectStubAck

        assert isinstance(result, EffectStubAck)
        assert result.kind == "file_open"
        assert result.registered is False


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

    def test_parse_selector_bare_id(self) -> None:
        assert parse_selector("save") == {"by": "id", "value": "save"}

    def test_parse_selector_hash_id(self) -> None:
        assert parse_selector("#save") == {"by": "id", "value": "save"}

    def test_parse_selector_scoped_id(self) -> None:
        assert parse_selector("form/save") == {"by": "id", "value": "form/save"}

    def test_parse_selector_window_qualified_id(self) -> None:
        assert parse_selector("main#save") == {
            "by": "id",
            "value": "save",
            "window_id": "main",
        }

    def test_parse_selector_window_qualified_scoped(self) -> None:
        assert parse_selector("main#form/save") == {
            "by": "id",
            "value": "form/save",
            "window_id": "main",
        }

    def test_parse_selector_focused(self) -> None:
        assert parse_selector(":focused") == {"by": "focused"}

    def test_parse_selector_window_focused(self) -> None:
        assert parse_selector("main#:focused") == {
            "by": "focused",
            "window_id": "main",
        }

    def test_parse_selector_text_attr(self) -> None:
        assert parse_selector("[text=Save]") == {"by": "text", "value": "Save"}

    def test_parse_selector_role_attr(self) -> None:
        assert parse_selector("[role=button]") == {"by": "role", "value": "button"}

    def test_parse_selector_label_attr(self) -> None:
        assert parse_selector("[label=Name]") == {"by": "label", "value": "Name"}

    def test_parse_selector_window_text_attr(self) -> None:
        assert parse_selector("main#[text=Save]") == {
            "by": "text",
            "value": "Save",
            "window_id": "main",
        }

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
            "protocol_version": 1,
            "version": "0.4.0",
            "name": "plushie",
            "mode": "mock",
            "backend": "none",
            "transport": "stdio",
            "extensions": ["charts"],
            "native_widgets": ["gauge"],
            "widgets": ["button"],
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
        assert info.native_widgets == ("gauge",)
        assert info.widgets == ("button",)

    def test_legacy_protocol_field(self) -> None:
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
        assert info.protocol == 1

    def test_protocol_version_preferred_over_legacy_protocol(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol_version": 1,
            "protocol": 99,
            "version": "0.1.0",
            "name": "plushie",
            "mode": "headless",
            "backend": "tiny-skia",
        }
        info = parse_hello(raw)
        assert info.protocol == 1

    def test_no_extensions(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol_version": 1,
            "version": "0.1.0",
            "name": "plushie",
            "mode": "headless",
            "backend": "tiny-skia",
        }
        info = parse_hello(raw)
        assert info.extensions == ()
        assert info.transport == "stdio"

    def test_rejects_non_integer_protocol_version(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol_version": "1",
            "protocol": 1,
            "version": "0.1.0",
            "name": "plushie",
            "mode": "headless",
            "backend": "tiny-skia",
        }
        with pytest.raises(ValueError, match=r"protocol_version.*int"):
            parse_hello(raw)

    def test_rejects_non_integer_legacy_protocol(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol": "1",
            "version": "0.1.0",
            "name": "plushie",
            "mode": "headless",
            "backend": "tiny-skia",
        }
        with pytest.raises(ValueError, match=r"protocol.*int"):
            parse_hello(raw)

    def test_widget_sets_do_not_populate_widgets(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol_version": 1,
            "version": "0.1.0",
            "name": "plushie",
            "mode": "headless",
            "backend": "tiny-skia",
            "widget_sets": ["provider_group"],
        }
        info = parse_hello(raw)
        assert info.widgets == ()


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
    """parse_effect_response returns a tagged tuple for the runtime to resolve."""

    def test_ok(self) -> None:
        raw = {
            "type": "effect_response",
            "id": "req1",
            "status": "ok",
            "result": {"path": "/tmp/file.txt"},
        }
        marker, wire_id, status, result, error = parse_effect_response(raw)
        assert marker == "_effect_response"
        assert wire_id == "req1"
        assert status == "ok"
        assert result == {"path": "/tmp/file.txt"}
        assert error is None

    def test_cancelled(self) -> None:
        raw = {"type": "effect_response", "id": "req2", "status": "cancelled"}
        _, _, status, result, _ = parse_effect_response(raw)
        assert status == "cancelled"
        assert result is None

    def test_error(self) -> None:
        raw = {
            "type": "effect_response",
            "id": "req3",
            "status": "error",
            "error": "permission denied",
        }
        _, _, status, _, error = parse_effect_response(raw)
        assert status == "error"
        assert error == "permission denied"


# ===================================================================
# decode_message: event dispatch for EVERY family
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
        assert isinstance(result, tuple)
        assert result[0] == "_effect_response"
        assert result[1] == "r1"


class TestDecodeWidgetEvents:
    def test_click(self) -> None:
        raw = {"type": "event", "family": "click", "id": "btn1", "window_id": "main"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "btn1"
        assert result.window_id == "main"
        assert result.scope == ("main",)

    def test_click_scoped(self) -> None:
        raw = {
            "type": "event",
            "family": "click",
            "id": "form/section/save",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.window_id == "main"
        assert result.scope == ("section", "form", "main")

    def test_input(self) -> None:
        raw = {
            "type": "event",
            "family": "input",
            "id": "name",
            "value": "Alice",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Input)
        assert result.value == "Alice"

    def test_submit(self) -> None:
        raw = {
            "type": "event",
            "family": "submit",
            "id": "search",
            "value": "query",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Submit)
        assert result.value == "query"

    def test_toggle(self) -> None:
        raw = {
            "type": "event",
            "family": "toggle",
            "id": "cb",
            "value": True,
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Toggle)
        assert result.value is True

    def test_select(self) -> None:
        raw = {
            "type": "event",
            "family": "select",
            "id": "pick",
            "value": "option_a",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Select)
        assert result.value == "option_a"

    def test_slide(self) -> None:
        raw = {
            "type": "event",
            "family": "slide",
            "id": "vol",
            "value": 0.75,
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Slide)
        assert result.value == 0.75

    def test_slide_release(self) -> None:
        raw = {
            "type": "event",
            "family": "slide_release",
            "id": "vol",
            "value": 0.8,
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, SlideRelease)
        assert result.value == 0.8

    def test_scroll(self) -> None:
        raw = {
            "type": "event",
            "family": "scroll",
            "id": "log",
            "window_id": "main",
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
        assert isinstance(result, Scrolled)
        assert result.data.absolute_y == 100
        assert result.data.content_height == 600

    def test_paste(self) -> None:
        raw = {
            "type": "event",
            "family": "paste",
            "id": "ed",
            "value": "pasted text",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Paste)
        assert result.value == "pasted text"

    def test_sort(self) -> None:
        raw = {
            "type": "event",
            "family": "sort",
            "id": "tbl",
            "window_id": "main",
            "data": {"column": "name"},
        }
        result = decode_message(raw)
        assert isinstance(result, Sort)
        assert result.value == "name"

    def test_open(self) -> None:
        raw = {"type": "event", "family": "open", "id": "combo", "window_id": "main"}
        result = decode_message(raw)
        assert isinstance(result, Open)

    def test_close(self) -> None:
        raw = {"type": "event", "family": "close", "id": "combo", "window_id": "main"}
        result = decode_message(raw)
        assert isinstance(result, Close)

    def test_option_hovered(self) -> None:
        raw = {
            "type": "event",
            "family": "option_hovered",
            "id": "pick",
            "window_id": "main",
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
            "window_id": "main",
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
            "window_id": "main",
            "data": {"binding": "undo"},
        }
        result = decode_message(raw)
        assert isinstance(result, KeyBinding)
        assert result.value == "undo"

    def test_link_click(self) -> None:
        raw = {
            "type": "event",
            "family": "link_click",
            "id": "article",
            "window_id": "main",
            "data": {"link": "https://example.com/article"},
        }
        result = decode_message(raw)
        assert isinstance(result, LinkClicked)
        assert result.id == "article"
        assert result.link == "https://example.com/article"
        assert result.window_id == "main"


class TestDecodePointerEvents:
    def test_press(self) -> None:
        raw = {
            "type": "event",
            "family": "press",
            "id": "area1",
            "window_id": "main",
            "data": {"x": 50, "y": 60, "button": "left"},
        }
        result = decode_message(raw)
        assert isinstance(result, Press)
        assert result.button == "left"

    def test_press_right(self) -> None:
        raw = {
            "type": "event",
            "family": "press",
            "id": "area1",
            "window_id": "main",
            "data": {"x": 0, "y": 0, "button": "right"},
        }
        result = decode_message(raw)
        assert isinstance(result, Press)
        assert result.button == "right"

    def test_release(self) -> None:
        raw = {
            "type": "event",
            "family": "release",
            "id": "area1",
            "window_id": "main",
            "data": {"x": 50, "y": 60, "button": "right"},
        }
        result = decode_message(raw)
        assert isinstance(result, Release)
        assert result.button == "right"

    def test_move(self) -> None:
        raw = {
            "type": "event",
            "family": "move",
            "id": "area1",
            "window_id": "main",
            "data": {"x": 10.5, "y": 20.3},
        }
        result = decode_message(raw)
        assert isinstance(result, Move)
        assert result.x == 10.5
        assert result.y == 20.3

    def test_scroll(self) -> None:
        raw = {
            "type": "event",
            "family": "scroll",
            "id": "area1",
            "window_id": "main",
            "data": {"x": 0, "y": 0, "delta_x": 0, "delta_y": -3.0},
        }
        result = decode_message(raw)
        assert isinstance(result, Scroll)
        assert result.delta_y == -3.0

    def test_double_click(self) -> None:
        raw = {
            "type": "event",
            "family": "double_click",
            "id": "area1",
            "window_id": "main",
            "data": {"x": 50, "y": 50},
        }
        result = decode_message(raw)
        assert isinstance(result, DoubleClick)
        assert result.x == 50

    def test_resize(self) -> None:
        raw = {
            "type": "event",
            "family": "resize",
            "id": "content1",
            "window_id": "main",
            "data": {"width": 800, "height": 600},
        }
        result = decode_message(raw)
        assert isinstance(result, Resize)
        assert result.width == 800


class TestDecodeUnifiedEvents:
    """Test decoding the new unified event wire families."""

    def test_focused(self) -> None:
        raw = {
            "type": "event",
            "family": "focused",
            "id": "canvas1",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Focused)
        assert result.id == "canvas1"

    def test_blurred(self) -> None:
        raw = {
            "type": "event",
            "family": "blurred",
            "id": "canvas1",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Blurred)
        assert result.id == "canvas1"

    def test_drag(self) -> None:
        raw = {
            "type": "event",
            "family": "drag",
            "id": "canvas1",
            "window_id": "main",
            "data": {"x": 100, "y": 200, "delta_x": 5, "delta_y": -3, "button": "left"},
        }
        result = decode_message(raw)
        assert isinstance(result, Drag)
        assert result.delta_x == 5

    def test_drag_end(self) -> None:
        raw = {
            "type": "event",
            "family": "drag_end",
            "id": "canvas1",
            "window_id": "main",
            "data": {"x": 105, "y": 197, "button": "left"},
        }
        result = decode_message(raw)
        assert isinstance(result, DragEnd)
        assert result.x == 105

    def test_enter(self) -> None:
        raw = {
            "type": "event",
            "family": "enter",
            "id": "area1",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Enter)
        assert result.id == "area1"
        assert result.x is None
        assert result.y is None
        assert result.captured is False

    def test_exit(self) -> None:
        raw = {
            "type": "event",
            "family": "exit",
            "id": "area1",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Exit)
        assert result.id == "area1"
        assert result.x is None
        assert result.y is None
        assert result.captured is False

    def test_enter_with_canvas_coords(self) -> None:
        raw = {
            "type": "event",
            "family": "enter",
            "id": "canvas1",
            "window_id": "main",
            "data": {"x": 12.5, "y": 34.0, "captured": True},
        }
        result = decode_message(raw)
        assert isinstance(result, Enter)
        assert result.id == "canvas1"
        assert result.x == 12.5
        assert result.y == 34.0
        assert result.captured is True

    def test_exit_with_canvas_coords(self) -> None:
        raw = {
            "type": "event",
            "family": "exit",
            "id": "canvas1",
            "window_id": "main",
            "value": {"x": 100.0, "y": 200.0, "captured": False},
        }
        result = decode_message(raw)
        assert isinstance(result, Exit)
        assert result.id == "canvas1"
        assert result.x == 100.0
        assert result.y == 200.0
        assert result.captured is False

    def test_key_press_widget_scoped(self) -> None:
        raw = {
            "type": "event",
            "family": "key_press",
            "id": "scope1/canvas1",
            "window_id": "main",
            "data": {"key": "ArrowRight", "modified_key": "ArrowRight"},
        }
        result = decode_message(raw)
        assert isinstance(result, KeyEvent)
        assert result.id == "canvas1"
        assert result.key == "ArrowRight"
        assert result.scope == ("scope1", "main")

    def test_key_release_widget_scoped(self) -> None:
        raw = {
            "type": "event",
            "family": "key_release",
            "id": "canvas1",
            "window_id": "main",
            "data": {"key": "Enter", "modified_key": "Enter"},
        }
        result = decode_message(raw)
        assert isinstance(result, KeyEvent)
        assert result.id == "canvas1"
        assert result.key == "Enter"
        assert result.scope == ("main",)


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

    def test_diagnostic_with_id_and_window(self) -> None:
        raw = {
            "type": "event",
            "family": "diagnostic",
            "id": "canvas1",
            "window_id": "main",
            "data": {
                "level": "error",
                "element_id": "shape-0",
                "code": "INVALID_PROP",
                "message": "bad value",
            },
        }
        result = decode_message(raw)
        assert isinstance(result, Diagnostic)
        assert result.id == "canvas1"
        assert result.window_id == "main"
        assert result.level == "error"


class TestDecodePaneEvents:
    def test_pane_resized(self) -> None:
        raw = {
            "type": "event",
            "family": "pane_resized",
            "id": "grid1",
            "window_id": "main",
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
            "window_id": "main",
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
            "window_id": "main",
            "data": {"pane": "p1"},
        }
        assert isinstance(decode_message(raw), PaneClicked)

    def test_pane_focus_cycle(self) -> None:
        raw = {
            "type": "event",
            "family": "pane_focus_cycle",
            "id": "grid1",
            "window_id": "main",
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
        assert isinstance(result, KeyEvent)
        assert result.key == "a"
        assert result.modified_key == "A"
        assert result.modifiers.shift is True
        assert result.text == "A"
        assert result.window_id == ""

    def test_key_press_with_window_id(self) -> None:
        raw = {
            "type": "event",
            "family": "key_press",
            "id": "",
            "tag": "kb",
            "window_id": "editor",
            "data": {"key": "a", "modified_key": "a"},
            "modifiers": {},
        }
        result = decode_message(raw)
        assert isinstance(result, KeyEvent)
        assert result.window_id == "editor"

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
        assert isinstance(result, KeyEvent)
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
        assert result.window_id == ""

    def test_modifiers_changed_with_window_id(self) -> None:
        raw = {
            "type": "event",
            "family": "modifiers_changed",
            "id": "",
            "tag": "kb",
            "window_id": "main",
            "modifiers": {"shift": True},
        }
        result = decode_message(raw)
        assert isinstance(result, ModifiersChanged)
        assert result.window_id == "main"


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
        assert isinstance(result, Move)
        assert result.x == 100.5
        assert result.pointer == "mouse"

    def test_cursor_moved_with_window_id(self) -> None:
        raw = {
            "type": "event",
            "family": "cursor_moved",
            "id": "",
            "tag": "m",
            "window_id": "canvas_win",
            "data": {"x": 50.0, "y": 75.0},
        }
        result = decode_message(raw)
        assert isinstance(result, Move)
        assert result.window_id == "canvas_win"
        assert result.id == "canvas_win"

    def test_cursor_entered(self) -> None:
        raw = {"type": "event", "family": "cursor_entered", "id": "", "tag": "m"}
        assert isinstance(decode_message(raw), Enter)

    def test_cursor_left(self) -> None:
        raw = {"type": "event", "family": "cursor_left", "id": "", "tag": "m"}
        assert isinstance(decode_message(raw), Exit)

    def test_button_pressed(self) -> None:
        raw = {
            "type": "event",
            "family": "button_pressed",
            "id": "",
            "tag": "m",
            "value": "left",
        }
        result = decode_message(raw)
        assert isinstance(result, Press)
        assert result.button == "left"
        assert result.pointer == "mouse"

    def test_button_released(self) -> None:
        raw = {
            "type": "event",
            "family": "button_released",
            "id": "",
            "tag": "m",
            "value": "right",
        }
        result = decode_message(raw)
        assert isinstance(result, Release)
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
        assert isinstance(result, Scroll)
        assert result.delta_y == -3

    @pytest.mark.parametrize(
        ("family", "value", "data"),
        [
            ("cursor_entered", None, None),
            ("cursor_left", None, None),
            ("button_pressed", "left", None),
            ("button_released", "right", None),
            ("wheel_scrolled", None, {"delta_x": 1, "delta_y": -2, "unit": "line"}),
        ],
    )
    def test_pointer_subscription_events_keep_captured(
        self,
        family: str,
        value: object,
        data: dict[str, object] | None,
    ) -> None:
        raw: dict[str, object] = {
            "type": "event",
            "family": family,
            "id": "",
            "tag": "m",
            "captured": True,
        }
        if value is not None:
            raw["value"] = value
        if data is not None:
            raw["data"] = data

        result = decode_message(raw)
        assert isinstance(result, (Enter, Exit, Press, Release, Scroll))
        assert result.captured is True


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
        assert isinstance(result, Press)
        assert result.pointer == "touch"
        assert result.finger == 1

    def test_finger_moved(self) -> None:
        raw = {
            "type": "event",
            "family": "finger_moved",
            "id": "",
            "tag": "t",
            "data": {"id": 2, "x": 55, "y": 65},
        }
        result = decode_message(raw)
        assert isinstance(result, Move)
        assert result.pointer == "touch"

    def test_finger_lifted(self) -> None:
        raw = {
            "type": "event",
            "family": "finger_lifted",
            "id": "",
            "tag": "t",
            "data": {"id": 1, "x": 50, "y": 60},
        }
        result = decode_message(raw)
        assert isinstance(result, Release)
        assert result.pointer == "touch"

    def test_finger_lost(self) -> None:
        raw = {
            "type": "event",
            "family": "finger_lost",
            "id": "",
            "tag": "t",
            "data": {"id": 3, "x": 0, "y": 0},
        }
        result = decode_message(raw)
        assert isinstance(result, Release)
        assert result.pointer == "touch"

    @pytest.mark.parametrize(
        "family",
        ["finger_pressed", "finger_moved", "finger_lifted", "finger_lost"],
    )
    def test_touch_subscription_events_keep_captured(self, family: str) -> None:
        raw = {
            "type": "event",
            "family": family,
            "id": "",
            "tag": "t",
            "captured": True,
            "data": {"id": 7, "x": 10, "y": 20},
        }

        result = decode_message(raw)
        assert isinstance(result, (Press, Move, Release))
        assert result.captured is True


class TestDecodeImeEvents:
    def test_ime_opened(self) -> None:
        raw = {"type": "event", "family": "ime_opened", "id": "", "tag": "ime"}
        assert isinstance(decode_message(raw), ImeEvent)

    def test_ime_preedit(self) -> None:
        raw = {
            "type": "event",
            "family": "ime_preedit",
            "id": "",
            "tag": "ime",
            "data": {"text": "ni", "cursor": {"start": 0, "end": 2}},
        }
        result = decode_message(raw)
        assert isinstance(result, ImeEvent)
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
        assert isinstance(result, ImeEvent)
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
        assert isinstance(result, ImeEvent)
        assert result.text == "你好"

    def test_ime_closed(self) -> None:
        raw = {"type": "event", "family": "ime_closed", "id": "", "tag": "ime"}
        assert isinstance(decode_message(raw), ImeEvent)


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
        assert isinstance(result, WindowEvent)
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
        assert isinstance(result, WindowEvent)
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
        assert isinstance(decode_message(raw), WindowEvent)

    def test_window_close_requested(self) -> None:
        raw = {
            "type": "event",
            "family": "window_close_requested",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowEvent)

    def test_window_resized(self) -> None:
        raw = {
            "type": "event",
            "family": "window_resized",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "width": 1024, "height": 768},
        }
        result = decode_message(raw)
        assert isinstance(result, WindowEvent)
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
        assert isinstance(result, WindowEvent)
        assert result.x == 200

    def test_window_focused(self) -> None:
        raw = {
            "type": "event",
            "family": "window_focused",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowEvent)

    def test_window_unfocused(self) -> None:
        raw = {
            "type": "event",
            "family": "window_unfocused",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowEvent)

    def test_window_rescaled(self) -> None:
        raw = {
            "type": "event",
            "family": "window_rescaled",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "scale_factor": 1.5},
        }
        result = decode_message(raw)
        assert isinstance(result, WindowEvent)
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
        assert isinstance(result, WindowEvent)
        assert result.path == "/tmp/file.txt"

    def test_file_dropped(self) -> None:
        raw = {
            "type": "event",
            "family": "file_dropped",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1", "path": "/tmp/dropped.txt"},
        }
        assert isinstance(decode_message(raw), WindowEvent)

    def test_files_hovered_left(self) -> None:
        raw = {
            "type": "event",
            "family": "files_hovered_left",
            "id": "",
            "tag": "win",
            "data": {"window_id": "w1"},
        }
        assert isinstance(decode_message(raw), WindowEvent)


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
            "type": "op_query_response",
            "kind": "system_info",
            "tag": "si",
            "data": {"cpu_brand": "Intel", "memory_total": 16000000000},
        }
        result = decode_message(raw)
        assert isinstance(result, SystemInfo)
        assert result.value["cpu_brand"] == "Intel"


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

    def test_unknown_top_level_message_passthrough(self) -> None:
        raw = {"type": "future_response", "session": "", "payload": {"x": 1}}
        result = decode_message(raw)
        assert isinstance(result, dict)
        assert result["type"] == "future_response"
        assert result["payload"] == {"x": 1}

    def test_unknown_event_with_id_becomes_widget_event(self) -> None:
        raw = {
            "type": "event",
            "family": "custom_future_event",
            "id": "widget1",
            "window_id": "main",
            "value": "something",
        }
        result = decode_message(raw)
        assert isinstance(result, RawEvent)
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
        assert isinstance(result, KeyEvent)
        assert result.captured is True


class TestDecodeScopedIdSplitting:
    def test_no_scope(self) -> None:
        raw = {"type": "event", "family": "click", "id": "save", "window_id": "main"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("main",)

    def test_single_scope(self) -> None:
        raw = {
            "type": "event",
            "family": "click",
            "id": "form/save",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("form", "main")

    def test_deep_scope(self) -> None:
        raw = {
            "type": "event",
            "family": "click",
            "id": "app/form/section/save",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("section", "form", "app", "main")

    def test_window_hash_no_scope(self) -> None:
        raw = {"type": "event", "family": "click", "id": "main#save"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("main",)
        assert result.window_id == "main"

    def test_window_hash_with_scope(self) -> None:
        raw = {"type": "event", "family": "click", "id": "main#form/save"}
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("form", "main")
        assert result.window_id == "main"

    def test_window_hash_deep_scope(self) -> None:
        raw = {
            "type": "event",
            "family": "click",
            "id": "main#sidebar/form/save",
        }
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("form", "sidebar", "main")
        assert result.window_id == "main"

    def test_window_hash_prefers_id_over_field(self) -> None:
        raw = {
            "type": "event",
            "family": "click",
            "id": "other#save",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("other",)
        assert result.window_id == "other"

    def test_window_hash_with_separate_window_id(self) -> None:
        raw = {
            "type": "event",
            "family": "click",
            "id": "main#form/save",
            "window_id": "main",
        }
        result = decode_message(raw)
        assert isinstance(result, Click)
        assert result.id == "save"
        assert result.scope == ("form", "main")
        assert result.window_id == "main"


class TestDecodeSessionLifecycle:
    def test_session_error(self) -> None:
        raw = {
            "type": "event",
            "family": "session_error",
            "session": "pool_1",
            "value": {"code": "session_panic", "error": "widget crashed"},
        }
        result = decode_message(raw)
        assert isinstance(result, SessionError)
        assert result.session == "pool_1"
        assert result.code == "session_panic"
        assert result.error == "widget crashed"

    def test_session_closed(self) -> None:
        raw = {
            "type": "event",
            "family": "session_closed",
            "session": "pool_2",
            "value": {"reason": "user disconnect"},
        }
        result = decode_message(raw)
        assert isinstance(result, SessionClosed)
        assert result.session == "pool_2"
        assert result.reason == "user disconnect"

    def test_session_error_missing_value(self) -> None:
        raw = {
            "type": "event",
            "family": "session_error",
            "session": "pool_3",
        }
        result = decode_message(raw)
        assert isinstance(result, SessionError)
        assert result.session == "pool_3"
        assert result.code == ""
        assert result.error == ""

    def test_session_closed_missing_value(self) -> None:
        raw = {
            "type": "event",
            "family": "session_closed",
            "session": "pool_4",
        }
        result = decode_message(raw)
        assert isinstance(result, SessionClosed)
        assert result.session == "pool_4"
        assert result.reason == ""


class TestDecodeEffectStubAck:
    def test_registered(self) -> None:
        raw = {"type": "effect_stub_register_ack", "kind": "clipboard_read"}
        result = decode_message(raw)
        assert isinstance(result, EffectStubAck)
        assert result.kind == "clipboard_read"
        assert result.registered is True

    def test_unregistered(self) -> None:
        raw = {"type": "effect_stub_unregister_ack", "kind": "file_open"}
        result = decode_message(raw)
        assert isinstance(result, EffectStubAck)
        assert result.kind == "file_open"
        assert result.registered is False
