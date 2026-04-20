"""Tests for plushie.events: event dataclasses and helpers."""

from __future__ import annotations

import pytest

from plushie.events import (
    AllWindowsClosed,
    AnimationFrame,
    Announce,
    AsyncResult,
    Blurred,
    Click,
    Close,
    Diagnostic,
    DoubleClick,
    Drag,
    DragEnd,
    DuplicateNodeIds,
    EffectResult,
    Enter,
    Exit,
    FileDropped,
    FileHovered,
    FilesHoveredLeft,
    Focused,
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
    RecoveryFailed,
    Release,
    Resize,
    Scroll,
    ScrollData,
    Scrolled,
    Select,
    Slide,
    SlideRelease,
    Sort,
    StreamChunk,
    Submit,
    SystemInfo,
    SystemTheme,
    ThemeChanged,
    TimerTick,
    Toggle,
    TreeHash,
    WindowClosed,
    WindowCloseRequested,
    WindowFocused,
    WindowMoved,
    WindowOpen,
    WindowRescaled,
    WindowResized,
    WindowUnfocused,
    build_renderer_exit,
    split_scoped_id,
    target,
)
from plushie.types import KeyModifiers

# ---------------------------------------------------------------------------
# Frozen enforcement
# ---------------------------------------------------------------------------


class TestFrozen:
    """All event dataclasses must be immutable."""

    def test_click_frozen(self) -> None:
        e = Click(id="btn")
        with pytest.raises(AttributeError):
            e.id = "other"  # type: ignore[misc]

    def test_input_frozen(self) -> None:
        e = Input(id="txt", value="hello")
        with pytest.raises(AttributeError):
            e.value = "world"  # type: ignore[misc]

    def test_key_press_frozen(self) -> None:
        e = KeyPress(key="a", modified_key="a", modifiers=KeyModifiers())
        with pytest.raises(AttributeError):
            e.key = "b"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Scope is tuple
# ---------------------------------------------------------------------------


class TestScope:
    """Widget events must use tuple for scope, not list."""

    def test_click_scope_default(self) -> None:
        e = Click(id="btn")
        assert e.scope == ()
        assert isinstance(e.scope, tuple)

    def test_click_scope_explicit(self) -> None:
        e = Click(id="btn", scope=("form", "app"))
        assert e.scope == ("form", "app")

    def test_input_scope(self) -> None:
        e = Input(id="txt", value="hi", scope=("section",))
        assert e.scope == ("section",)


# ---------------------------------------------------------------------------
# Widget event construction
# ---------------------------------------------------------------------------


class TestWidgetEvents:
    """Construct every scoped widget event type and verify fields."""

    def test_click(self) -> None:
        e = Click(id="save")
        assert e.id == "save"
        assert e.scope == ()

    def test_input(self) -> None:
        e = Input(id="name", value="Arthur")
        assert e.value == "Arthur"

    def test_submit(self) -> None:
        e = Submit(id="search", value="query text")
        assert e.value == "query text"

    def test_toggle(self) -> None:
        e = Toggle(id="dark_mode", value=True)
        assert e.value is True

    def test_select(self) -> None:
        e = Select(id="lang", value="python")
        assert e.value == "python"

    def test_slide(self) -> None:
        e = Slide(id="volume", value=0.75)
        assert e.value == 0.75

    def test_slide_release(self) -> None:
        e = SlideRelease(id="volume", value=0.8)
        assert e.value == 0.8

    def test_scroll(self) -> None:
        sd = ScrollData(
            absolute_x=10.0,
            absolute_y=20.0,
            relative_x=0.1,
            relative_y=0.2,
            bounds_width=400.0,
            bounds_height=300.0,
            content_width=800.0,
            content_height=1200.0,
        )
        e = Scrolled(id="log", data=sd)
        assert e.data.absolute_x == 10.0
        assert e.data.content_height == 1200.0

    def test_paste(self) -> None:
        e = Paste(id="editor", value="pasted text")
        assert e.value == "pasted text"

    def test_sort(self) -> None:
        e = Sort(id="table", value="name")
        assert e.value == "name"

    def test_open(self) -> None:
        e = Open(id="dropdown")
        assert e.id == "dropdown"

    def test_close(self) -> None:
        e = Close(id="dropdown")
        assert e.id == "dropdown"

    def test_option_hovered(self) -> None:
        e = OptionHovered(id="combo", value="option_a")
        assert e.value == "option_a"

    def test_key_binding(self) -> None:
        e = KeyBinding(id="editor", value="ctrl+s")
        assert e.value == "ctrl+s"

    def test_widget_event_catchall(self) -> None:
        e = RawEvent(
            kind="custom_event",
            id="widget",
            value="some_val",
            data={"extra": True},
            scope=("parent",),
        )
        assert e.kind == "custom_event"
        assert e.data == {"extra": True}


# ---------------------------------------------------------------------------
# MouseArea events
# ---------------------------------------------------------------------------


class TestPointerEvents:
    """Construct every unified pointer event type."""

    def test_press(self) -> None:
        e = Press(id="area", x=100.0, y=200.0, button="left")
        assert e.button == "left"
        assert e.pointer == "mouse"

    def test_press_right(self) -> None:
        e = Press(id="area", x=0.0, y=0.0, button="right", scope=("panel",))
        assert e.button == "right"
        assert e.scope == ("panel",)

    def test_release(self) -> None:
        e = Release(id="area", x=100.0, y=200.0, button="right")
        assert e.button == "right"

    def test_move(self) -> None:
        e = Move(id="area", x=10.5, y=20.5)
        assert e.x == 10.5
        assert e.y == 20.5

    def test_pointer_scroll(self) -> None:
        e = Scroll(id="area", x=0.0, y=0.0, delta_x=1.0, delta_y=-2.0)
        assert e.delta_x == 1.0
        assert e.delta_y == -2.0

    def test_double_click(self) -> None:
        e = DoubleClick(id="area", x=50.0, y=50.0)
        assert e.id == "area"
        assert e.pointer == "mouse"

    def test_resize(self) -> None:
        e = Resize(id="content", width=800.0, height=600.0, scope=("panel",))
        assert e.width == 800.0
        assert e.height == 600.0
        assert e.scope == ("panel",)

    def test_touch_press(self) -> None:
        e = Press(id="canvas", x=100.0, y=200.0, pointer="touch", finger=1)
        assert e.pointer == "touch"
        assert e.finger == 1


# ---------------------------------------------------------------------------
# Unified focus/drag/enter/exit events
# ---------------------------------------------------------------------------


class TestUnifiedCanvasEvents:
    """Test the unified event types that replace canvas element events."""

    def test_focused(self) -> None:
        e = Focused(id="bar-1", scope=("canvas",))
        assert e.id == "bar-1"
        assert e.scope == ("canvas",)

    def test_blurred(self) -> None:
        e = Blurred(id="bar-1", scope=("canvas",))
        assert e.id == "bar-1"

    def test_drag(self) -> None:
        e = Drag(id="handle", x=100.0, y=200.0, delta_x=5.0, delta_y=-3.0)
        assert e.delta_x == 5.0
        assert e.delta_y == -3.0
        assert e.button == "left"

    def test_drag_end(self) -> None:
        e = DragEnd(id="handle", x=105.0, y=197.0)
        assert e.x == 105.0
        assert e.button == "left"

    def test_enter(self) -> None:
        e = Enter(id="area", scope=("panel",))
        assert e.id == "area"
        assert e.scope == ("panel",)

    def test_exit(self) -> None:
        e = Exit(id="area", scope=("panel",))
        assert e.id == "area"

    def test_key_press_widget_scoped(self) -> None:
        e = KeyPress(
            key="ArrowRight",
            modified_key="ArrowRight",
            modifiers=KeyModifiers(),
            id="item1",
            scope=("canvas", "form"),
        )
        assert e.id == "item1"
        assert e.key == "ArrowRight"
        assert e.scope == ("canvas", "form")

    def test_key_press_subscription(self) -> None:
        e = KeyPress(
            key="Enter",
            modified_key="Enter",
            modifiers=KeyModifiers(),
        )
        assert e.id is None
        assert e.scope == ()

    def test_key_release_widget_scoped(self) -> None:
        e = KeyRelease(
            key="Enter",
            modified_key="Enter",
            modifiers=KeyModifiers(),
            id="item1",
            scope=("canvas",),
        )
        assert e.id == "item1"
        assert e.scope == ("canvas",)


# ---------------------------------------------------------------------------
# Diagnostic event
# ---------------------------------------------------------------------------


class TestDiagnosticEvent:
    def test_construction(self) -> None:
        e = Diagnostic(
            level="warning",
            element_id="star-0",
            code="MISSING_A11Y",
            message="Interactive element has no a11y label",
        )
        assert e.level == "warning"
        assert e.element_id == "star-0"
        assert e.code == "MISSING_A11Y"
        assert e.message == "Interactive element has no a11y label"


# ---------------------------------------------------------------------------
# Pane events
# ---------------------------------------------------------------------------


class TestPaneEvents:
    def test_pane_resized(self) -> None:
        e = PaneResized(id="grid", split=42, ratio=0.5)
        assert e.ratio == 0.5

    def test_pane_dragged(self) -> None:
        e = PaneDragged(
            id="grid",
            pane=1,
            target=2,
            action="dropped",
            region="center",
            edge=None,
        )
        assert e.action == "dropped"
        assert e.region == "center"

    def test_pane_clicked(self) -> None:
        e = PaneClicked(id="grid", pane=0)
        assert e.pane == 0

    def test_pane_focus_cycle(self) -> None:
        e = PaneFocusCycle(id="grid", pane=1)
        assert e.pane == 1


# ---------------------------------------------------------------------------
# Key events
# ---------------------------------------------------------------------------


class TestKeyEvents:
    def test_key_press_minimal(self) -> None:
        mods = KeyModifiers()
        e = KeyPress(key="a", modified_key="a", modifiers=mods)
        assert e.key == "a"
        assert e.repeat is False
        assert e.captured is False
        assert e.location == "standard"
        assert e.physical_key is None
        assert e.text is None

    def test_key_press_full(self) -> None:
        mods = KeyModifiers(shift=True)
        e = KeyPress(
            key="a",
            modified_key="A",
            modifiers=mods,
            physical_key="KeyA",
            location="left",
            text="A",
            repeat=False,
            captured=True,
        )
        assert e.modified_key == "A"
        assert e.modifiers.shift is True
        assert e.location == "left"
        assert e.text == "A"
        assert e.captured is True

    def test_key_release(self) -> None:
        mods = KeyModifiers()
        e = KeyRelease(key="Enter", modified_key="Enter", modifiers=mods)
        assert e.key == "Enter"
        assert e.captured is False

    def test_modifiers_changed(self) -> None:
        mods = KeyModifiers(ctrl=True, alt=True)
        e = ModifiersChanged(modifiers=mods)
        assert e.modifiers.ctrl is True
        assert e.modifiers.alt is True


# ---------------------------------------------------------------------------
# Mouse events (global subscription)
# ---------------------------------------------------------------------------


class TestSubscriptionPointerEvents:
    """Subscription pointer events use unified types with id=window_id."""

    def test_move_as_subscription(self) -> None:
        e = Move(id="main", x=100.0, y=200.0, pointer="mouse", window_id="main")
        assert e.pointer == "mouse"
        assert e.scope == ()

    def test_press_as_subscription(self) -> None:
        e = Press(
            id="main", x=0.0, y=0.0, button="left", pointer="mouse", window_id="main"
        )
        assert e.button == "left"
        assert e.scope == ()

    def test_touch_press_as_subscription(self) -> None:
        e = Press(
            id="main",
            x=100.0,
            y=200.0,
            button="left",
            pointer="touch",
            finger=0,
            window_id="main",
        )
        assert e.pointer == "touch"
        assert e.finger == 0


# ---------------------------------------------------------------------------
# IME events
# ---------------------------------------------------------------------------


class TestImeEvents:
    def test_ime_open(self) -> None:
        e = ImeOpen()
        assert e.captured is False

    def test_ime_preedit(self) -> None:
        e = ImePreedit(text="ni", cursor=(0, 2))
        assert e.text == "ni"
        assert e.cursor == (0, 2)

    def test_ime_preedit_no_cursor(self) -> None:
        e = ImePreedit(text="test")
        assert e.cursor is None

    def test_ime_commit(self) -> None:
        e = ImeCommit(text="hello")
        assert e.text == "hello"

    def test_ime_close(self) -> None:
        e = ImeClose(captured=True)
        assert e.captured is True


# ---------------------------------------------------------------------------
# Window events
# ---------------------------------------------------------------------------


class TestWindowEvents:
    def test_window_open(self) -> None:
        e = WindowOpen(
            window_id="main",
            width=1024.0,
            height=768.0,
            scale_factor=2.0,
            position_x=100.0,
            position_y=200.0,
        )
        assert e.width == 1024.0
        assert e.scale_factor == 2.0
        assert e.position_x == 100.0

    def test_window_open_no_position(self) -> None:
        e = WindowOpen(window_id="main", width=800.0, height=600.0, scale_factor=1.0)
        assert e.position_x is None
        assert e.position_y is None

    def test_window_closed(self) -> None:
        e = WindowClosed(window_id="popup")
        assert e.window_id == "popup"

    def test_window_close_requested(self) -> None:
        e = WindowCloseRequested(window_id="main")
        assert e.window_id == "main"

    def test_window_resized(self) -> None:
        e = WindowResized(window_id="main", width=1920.0, height=1080.0)
        assert e.width == 1920.0

    def test_window_moved(self) -> None:
        e = WindowMoved(window_id="main", x=50.0, y=100.0)
        assert e.x == 50.0

    def test_window_focused(self) -> None:
        e = WindowFocused(window_id="main")
        assert e.window_id == "main"

    def test_window_unfocused(self) -> None:
        e = WindowUnfocused(window_id="main")
        assert e.window_id == "main"

    def test_window_rescaled(self) -> None:
        e = WindowRescaled(window_id="main", scale_factor=1.5)
        assert e.scale_factor == 1.5

    def test_file_hovered(self) -> None:
        e = FileHovered(window_id="main", path="/tmp/test.txt")
        assert e.path == "/tmp/test.txt"

    def test_file_dropped(self) -> None:
        e = FileDropped(window_id="main", path="/tmp/test.txt")
        assert e.path == "/tmp/test.txt"

    def test_files_hovered_left(self) -> None:
        e = FilesHoveredLeft(window_id="main")
        assert e.window_id == "main"


# ---------------------------------------------------------------------------
# System / query events
# ---------------------------------------------------------------------------


class TestSystemEvents:
    def test_animation_frame(self) -> None:
        e = AnimationFrame(timestamp=16000)
        assert e.timestamp == 16000

    def test_theme_changed(self) -> None:
        e = ThemeChanged(theme="dark")
        assert e.theme == "dark"

    def test_all_windows_closed(self) -> None:
        e = AllWindowsClosed()
        assert isinstance(e, AllWindowsClosed)

    def test_system_info(self) -> None:
        e = SystemInfo(tag="q1", value={"cpu_brand": "AMD Ryzen"})
        assert e.tag == "q1"
        assert e.value["cpu_brand"] == "AMD Ryzen"

    def test_system_theme(self) -> None:
        e = SystemTheme(tag="q2", theme="light")
        assert e.theme == "light"

    def test_image_list(self) -> None:
        e = ImageList(tag="q3", handles=("img1", "img2"))
        assert len(e.handles) == 2

    def test_focused_widget(self) -> None:
        e = FocusedWidget(tag="q4", widget_id="input1")
        assert e.widget_id == "input1"

    def test_focused_widget_none(self) -> None:
        e = FocusedWidget(tag="q4", widget_id=None)
        assert e.widget_id is None

    def test_tree_hash(self) -> None:
        e = TreeHash(tag="q5", hash="abc123")
        assert e.hash == "abc123"


# ---------------------------------------------------------------------------
# Error / announce events
# ---------------------------------------------------------------------------


class TestErrorEvents:
    def test_duplicate_node_ids(self) -> None:
        e = DuplicateNodeIds(details=["btn1", "btn1"])
        assert "btn1" in e.details

    def test_announce(self) -> None:
        e = Announce(text="Item saved")
        assert e.text == "Item saved"


# ---------------------------------------------------------------------------
# Effect result
# ---------------------------------------------------------------------------


class TestEffectResult:
    def test_file_opened(self) -> None:
        from plushie.events import FileOpened

        e = EffectResult(tag="import", result=FileOpened(path="/tmp/file.txt"))
        assert isinstance(e.result, FileOpened)
        assert e.result.path == "/tmp/file.txt"

    def test_cancelled(self) -> None:
        from plushie.events import EffectCancelled

        e = EffectResult(tag="save", result=EffectCancelled())
        assert isinstance(e.result, EffectCancelled)

    def test_error(self) -> None:
        from plushie.events import EffectError

        e = EffectResult(tag="read", result=EffectError(message="permission denied"))
        assert isinstance(e.result, EffectError)
        assert e.result.message == "permission denied"

    def test_decode_file_open(self) -> None:
        from plushie.events import FileOpened, decode_effect_result

        out = decode_effect_result("file_open", "ok", {"path": "/tmp/x.txt"}, None)
        assert out == FileOpened(path="/tmp/x.txt")

    def test_decode_clipboard_read(self) -> None:
        from plushie.events import ClipboardText, decode_effect_result

        out = decode_effect_result("clipboard_read", "ok", {"text": "hi"}, None)
        assert out == ClipboardText(text="hi")

    def test_decode_cancelled(self) -> None:
        from plushie.events import EffectCancelled, decode_effect_result

        out = decode_effect_result("file_open", "cancelled", None, None)
        assert out == EffectCancelled()

    def test_decode_error(self) -> None:
        from plushie.events import EffectError, decode_effect_result

        out = decode_effect_result("file_open", "error", None, "no disk")
        assert out == EffectError(message="no disk")


# ---------------------------------------------------------------------------
# Runtime events
# ---------------------------------------------------------------------------


class TestRuntimeEvents:
    def test_async_result(self) -> None:
        e = AsyncResult(tag="fetch", value={"data": [1, 2, 3]})
        assert e.tag == "fetch"

    def test_stream_chunk(self) -> None:
        e = StreamChunk(tag="download", value=b"chunk")
        assert e.tag == "download"

    def test_timer_tick(self) -> None:
        e = TimerTick(tag="clock", timestamp=1000)
        assert e.timestamp == 1000


# ---------------------------------------------------------------------------
# split_scoped_id
# ---------------------------------------------------------------------------


class TestSplitScopedId:
    """Test wire ID splitting into local ID, reversed scope, and window."""

    def test_no_scope(self) -> None:
        local_id, scope, window = split_scoped_id("save")
        assert local_id == "save"
        assert scope == ()
        assert window is None

    def test_single_scope(self) -> None:
        local_id, scope, window = split_scoped_id("form/save")
        assert local_id == "save"
        assert scope == ("form",)
        assert window is None

    def test_deep_scope(self) -> None:
        local_id, scope, window = split_scoped_id("app/form/section/save")
        assert local_id == "save"
        assert scope == ("section", "form", "app")
        assert window is None

    def test_two_levels(self) -> None:
        local_id, scope, window = split_scoped_id("panel/input")
        assert local_id == "input"
        assert scope == ("panel",)
        assert window is None

    def test_window_direct_child(self) -> None:
        local_id, scope, window = split_scoped_id("main#save")
        assert local_id == "save"
        assert scope == ()
        assert window == "main"

    def test_window_nested_scope(self) -> None:
        local_id, scope, window = split_scoped_id("main#form/save")
        assert local_id == "save"
        assert scope == ("form",)
        assert window == "main"

    def test_window_deep_scope(self) -> None:
        local_id, scope, window = split_scoped_id("main#sidebar/form/save")
        assert local_id == "save"
        assert scope == ("form", "sidebar")
        assert window == "main"

    def test_empty_string(self) -> None:
        local_id, scope, window = split_scoped_id("")
        assert local_id == ""
        assert scope == ()
        assert window is None


# ---------------------------------------------------------------------------
# target()
# ---------------------------------------------------------------------------


class TestTarget:
    """Test full path reconstruction from scoped events."""

    def test_no_scope(self) -> None:
        e = Click(id="save")
        assert target(e) == "save"

    def test_single_scope(self) -> None:
        e = Click(id="save", window_id="main", scope=("form", "main"))
        assert target(e) == "form/save"

    def test_deep_scope(self) -> None:
        e = Click(
            id="save",
            window_id="main",
            scope=("section", "form", "app", "main"),
        )
        assert target(e) == "app/form/section/save"

    def test_roundtrip(self) -> None:
        wire_id = "app/form/section/save"
        local_id, scope, _window = split_scoped_id(wire_id)
        e = Click(id=local_id, scope=scope)
        assert target(e) == wire_id

    def test_with_input_event(self) -> None:
        e = Input(
            id="email",
            value="test@example.com",
            window_id="main",
            scope=("form", "main"),
        )
        assert target(e) == "form/email"

    def test_with_resize(self) -> None:
        e = Resize(
            id="content",
            width=800.0,
            height=600.0,
            window_id="main",
            scope=("panel", "main"),
        )
        assert target(e) == "panel/content"

    def test_with_press(self) -> None:
        e = Press(
            id="draw",
            x=10.0,
            y=20.0,
            button="left",
            window_id="main",
            scope=("editor", "main"),
        )
        assert target(e) == "editor/draw"

    def test_no_window_id_no_stripping(self) -> None:
        """Without window_id, scope passes through unchanged."""
        e = Click(id="save", scope=("form",))
        assert target(e) == "form/save"


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


class TestPatternMatching:
    """Verify events work naturally with Python match statements."""

    def test_match_click(self) -> None:
        event: Click | Input = Click(id="save")
        result = None
        match event:
            case Click(id="save"):
                result = "saved"
            case _:
                result = "other"
        assert result == "saved"

    def test_match_click_with_scope(self) -> None:
        event = Click(id="delete", scope=("item_3", "list"))
        item_id = None
        match event:
            case Click(id="delete", scope=(iid, *_)):
                item_id = iid
        assert item_id == "item_3"

    def test_match_input_value(self) -> None:
        event = Input(id="search", value="hello world")
        captured_value = None
        match event:
            case Input(id="search", value=v):
                captured_value = v
        assert captured_value == "hello world"

    def test_match_key_press(self) -> None:
        event = KeyPress(
            key="Escape",
            modified_key="Escape",
            modifiers=KeyModifiers(),
        )
        matched = False
        match event:
            case KeyPress(key="Escape"):
                matched = True
        assert matched is True

    def test_match_toggle_bool(self) -> None:
        event = Toggle(id="dark", value=True)
        is_on = None
        match event:
            case Toggle(id="dark", value=v):
                is_on = v
        assert is_on is True


# ---------------------------------------------------------------------------
# ScrollData
# ---------------------------------------------------------------------------


class TestScrollData:
    def test_construction(self) -> None:
        sd = ScrollData(
            absolute_x=0.0,
            absolute_y=50.0,
            relative_x=0.0,
            relative_y=0.5,
            bounds_width=200.0,
            bounds_height=400.0,
            content_width=200.0,
            content_height=800.0,
        )
        assert sd.relative_y == 0.5
        assert sd.content_height == 800.0

    def test_frozen(self) -> None:
        sd = ScrollData(
            absolute_x=0.0,
            absolute_y=0.0,
            relative_x=0.0,
            relative_y=0.0,
            bounds_width=100.0,
            bounds_height=100.0,
            content_width=100.0,
            content_height=100.0,
        )
        with pytest.raises(AttributeError):
            sd.absolute_x = 10.0  # type: ignore[misc]


class TestBuildRendererExit:
    def test_normal(self) -> None:
        info = build_renderer_exit("normal")
        assert info.type == "shutdown"
        assert info.message == "renderer shut down normally"
        assert info.details is None

    def test_shutdown(self) -> None:
        info = build_renderer_exit("shutdown")
        assert info.type == "shutdown"
        assert info.message == "renderer shut down"

    def test_heartbeat_timeout(self) -> None:
        info = build_renderer_exit("heartbeat_timeout")
        assert info.type == "heartbeat_timeout"
        assert "heartbeat" in info.message

    def test_exit_status_dict(self) -> None:
        info = build_renderer_exit({"exit_status": 1})
        assert info.type == "crash"
        assert info.details == 1

    def test_unknown_reason(self) -> None:
        info = build_renderer_exit("something_else")
        assert info.type == "crash"
        assert info.details == "something_else"

    def test_none_reason(self) -> None:
        info = build_renderer_exit(None)
        assert info.type == "crash"

    def test_frozen(self) -> None:
        info = build_renderer_exit("normal")
        with pytest.raises(AttributeError):
            info.type = "crash"  # type: ignore[misc]


class TestRecoveryFailed:
    def test_construction(self) -> None:
        exit_info = build_renderer_exit({"exit_status": 1})
        event = RecoveryFailed(
            kind="RuntimeError",
            error="something broke",
            renderer_exit=exit_info,
        )
        assert event.kind == "RuntimeError"
        assert event.error == "something broke"
        assert event.renderer_exit is exit_info

    def test_frozen(self) -> None:
        exit_info = build_renderer_exit("normal")
        event = RecoveryFailed(kind="E", error="msg", renderer_exit=exit_info)
        with pytest.raises(AttributeError):
            event.kind = "other"  # type: ignore[misc]
