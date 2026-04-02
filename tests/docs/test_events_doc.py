"""Tests for code examples in docs/events.md.

Each test corresponds to an HTML test marker comment in the doc.
Every code example with a ``match event:`` block has a test verifying
the match works.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from plushie.commands import Command
from plushie.events import (
    AnimationFrame,
    AsyncResult,
    Click,
    Close,
    EffectResult,
    Enter,
    FileDropped,
    FileHovered,
    FilesHoveredLeft,
    ImeCommit,
    ImePreedit,
    Input,
    KeyBinding,
    KeyPress,
    ModifiersChanged,
    Move,
    Open,
    OptionHovered,
    PaneClicked,
    PaneResized,
    Paste,
    Press,
    Resize,
    ScrollData,
    Scrolled,
    Select,
    Slide,
    SlideRelease,
    Sort,
    StreamChunk,
    Submit,
    ThemeChanged,
    TimerTick,
    Toggle,
    WindowCloseRequested,
    WindowFocused,
    WindowResized,
)
from plushie.types import KeyModifiers

# -- Helpers for match tests -------------------------------------------------


@dataclass(frozen=True, slots=True)
class Model:
    search_query: str = ""
    dark_mode: bool = False
    theme: str = "default"
    volume: float = 50.0
    notes_content: str = ""
    preview: str = ""
    picker_open: bool = False
    sort_by: str = ""
    sort_order: str = "asc"
    hovered: bool = False
    cursor: tuple[float, float] = (0.0, 0.0)
    drawing: bool = False
    last_point: tuple[float, float] = (0.0, 0.0)
    strokes: tuple[tuple[float, float], ...] = ()
    selected_bar: str = ""
    content_size: tuple[float, float] = (0.0, 0.0)
    splits: dict[str, float] | None = None
    active_pane: str = ""
    modal_open: bool = True
    composing: str | None = None
    value: str = ""
    mouse_down: bool = False
    touch_start: tuple[float, float] = (0.0, 0.0)
    shift_held: bool = False
    unsaved_changes: bool = False
    confirm_exit: bool = False
    window_size: tuple[float, float] = (0.0, 0.0)
    active_window: str = ""
    drop_target_active: bool = False
    hovered_file: str = ""
    loading: bool = False
    data: str = ""
    error: str = ""
    url: str = ""
    section: str = ""
    settings: dict[str, bool] | None = None
    auto_scroll: bool = False


def flip(order: str) -> str:
    return "desc" if order == "asc" else "asc"


# -- Widget events -----------------------------------------------------------


class TestClickConstruct:
    def test_click_construct(self) -> None:
        event = Click(id="save")
        assert event.id == "save"
        assert event.scope == ()


class TestClickMatch:
    def test_click_save_match(self) -> None:
        event = Click(id="save")
        match event:
            case Click(id="save"):
                matched = True
            case _:
                matched = False
        assert matched

    def test_click_cancel_match(self) -> None:
        event = Click(id="cancel")
        match event:
            case Click(id="cancel"):
                matched = True
            case _:
                matched = False
        assert matched


class TestInputMatch:
    def test_input_match(self) -> None:
        event = Input(id="search", value="hello")
        model = Model()
        match event:
            case Input(id="search", value=value):
                model = replace(model, search_query=value)
        assert model.search_query == "hello"


class TestSubmitMatch:
    def test_submit_match(self) -> None:
        event = Submit(id="search", value="query")
        match event:
            case Submit(id="search", value=query):
                matched_query = query
            case _:
                matched_query = ""
        assert matched_query == "query"


class TestToggleMatch:
    def test_toggle_match(self) -> None:
        event = Toggle(id="dark_mode", value=True)
        model = Model()
        match event:
            case Toggle(id="dark_mode", value=enabled):
                model = replace(model, dark_mode=enabled)
        assert model.dark_mode is True


class TestSelectMatch:
    def test_select_match(self) -> None:
        event = Select(id="theme_picker", value="nord")
        model = Model()
        match event:
            case Select(id="theme_picker", value=theme):
                model = replace(model, theme=theme)
        assert model.theme == "nord"


class TestSlideMatch:
    def test_slide_match(self) -> None:
        event = Slide(id="volume", value=75.0)
        model = Model()
        match event:
            case Slide(id="volume", value=value):
                model = replace(model, volume=value)
        assert model.volume == 75.0

    def test_slide_release_match(self) -> None:
        event = SlideRelease(id="volume", value=75.0)
        match event:
            case SlideRelease(id="volume", value=value):
                matched_value = value
            case _:
                matched_value = 0.0
        assert matched_value == 75.0


class TestKeyBindingMatch:
    def test_key_binding_save(self) -> None:
        event = KeyBinding(id="editor", value="save")
        match event:
            case KeyBinding(id="editor", value="save"):
                matched = True
            case _:
                matched = False
        assert matched

    def test_key_binding_format(self) -> None:
        event = KeyBinding(id="editor", value="format")
        match event:
            case KeyBinding(id="editor", value="format"):
                matched = True
            case _:
                matched = False
        assert matched


class TestScrollMatch:
    def test_scroll_match(self) -> None:
        data = ScrollData(
            absolute_x=0.0,
            absolute_y=150.0,
            relative_x=0.0,
            relative_y=0.75,
            bounds_width=400.0,
            bounds_height=300.0,
            content_width=400.0,
            content_height=600.0,
        )
        event = Scrolled(id="log_view", data=data)
        model = Model()
        match event:
            case Scrolled(id="log_view", data=viewport):
                at_bottom = viewport.relative_y >= 0.99
                model = replace(model, auto_scroll=at_bottom)
        assert model.auto_scroll is False  # 0.75 < 0.99


class TestPasteMatch:
    def test_paste_match(self) -> None:
        event = Paste(id="url_input", value=" text ")
        model = Model()
        match event:
            case Paste(id="url_input", value=text):
                model = replace(model, url=text.strip())
        assert model.url == "text"


class TestOptionHoveredMatch:
    def test_option_hovered_match(self) -> None:
        event = OptionHovered(id="search", value="opt1")
        model = Model()
        match event:
            case OptionHovered(id="search", value=value):
                model = replace(model, preview=value)
        assert model.preview == "opt1"


class TestOpenCloseMatch:
    def test_open_match(self) -> None:
        event = Open(id="country_picker")
        model = Model()
        match event:
            case Open(id="country_picker"):
                model = replace(model, picker_open=True)
        assert model.picker_open is True

    def test_close_match(self) -> None:
        event = Close(id="country_picker")
        model = Model(picker_open=True)
        match event:
            case Close(id="country_picker"):
                model = replace(model, picker_open=False)
        assert model.picker_open is False


class TestSortMatch:
    def test_sort_match(self) -> None:
        event = Sort(id="users", value="name")
        model = Model(sort_by="email", sort_order="asc")
        match event:
            case Sort(id="users", value=column_key):
                order = flip(model.sort_order) if model.sort_by == column_key else "asc"
                model = replace(model, sort_by=column_key, sort_order=order)
        assert model.sort_by == "name"
        assert model.sort_order == "asc"


# -- Mouse area events -------------------------------------------------------


class TestEnterMatch:
    def test_enter_match(self) -> None:
        event = Enter(id="hover_zone")
        model = Model()
        match event:
            case Enter(id="hover_zone"):
                model = replace(model, hovered=True)
        assert model.hovered is True


class TestMoveMatch:
    def test_move_match(self) -> None:
        event = Move(id="canvas_area", x=10.0, y=20.0)
        model = Model()
        match event:
            case Move(id="canvas_area", x=x, y=y):
                model = replace(model, cursor=(x, y))
        assert model.cursor == (10.0, 20.0)


# -- Pointer events ----------------------------------------------------------


class TestPressMatch:
    def test_press_left_match(self) -> None:
        event = Press(id="draw_area", x=42.0, y=100.0, button="left")
        model = Model()
        match event:
            case Press(id="draw_area", x=x, y=y, button="left"):
                model = replace(model, drawing=True, last_point=(x, y))
        assert model.drawing is True
        assert model.last_point == (42.0, 100.0)


class TestPointerMoveMatch:
    def test_move_while_drawing(self) -> None:
        event = Move(id="draw_area", x=5.0, y=10.0)
        model = Model(drawing=True, strokes=())
        match event:
            case Move(id="draw_area", x=x, y=y) if model.drawing:
                model = replace(
                    model, last_point=(x, y), strokes=(*model.strokes, (x, y))
                )
        assert model.last_point == (5.0, 10.0)
        assert model.strokes == ((5.0, 10.0),)


class TestScopedClickMatch:
    def test_element_click_match(self) -> None:
        event = Click(id="bar-jan", window_id="main", scope=("chart",))
        model = Model()
        match event:
            case Click(id=element_id, scope=("chart", *_)):
                model = replace(model, selected_bar=element_id)
        assert model.selected_bar == "bar-jan"


# -- Resize events -----------------------------------------------------------


class TestResizeMatch:
    def test_resize_match(self) -> None:
        event = Resize(id="content_area", width=800.0, height=600.0)
        model = Model()
        match event:
            case Resize(id="content_area", width=w, height=h):
                model = replace(model, content_size=(w, h))
        assert model.content_size == (800.0, 600.0)


# -- PaneGrid events ---------------------------------------------------------


class TestPaneResizedMatch:
    def test_pane_resized_match(self) -> None:
        event = PaneResized(id="editor", split="split_1", ratio=0.5)
        model = Model(splits={})
        match event:
            case PaneResized(id="editor", split=split, ratio=ratio):
                splits = {**model.splits, split: ratio}  # type: ignore[misc]
                model = replace(model, splits=splits)
        assert model.splits == {"split_1": 0.5}

    def test_pane_clicked_match(self) -> None:
        event = PaneClicked(id="editor", pane="left")
        model = Model()
        match event:
            case PaneClicked(id="editor", pane=pane):
                model = replace(model, active_pane=pane)
        assert model.active_pane == "left"


# -- Keyboard events ---------------------------------------------------------


class TestKeyPressMatch:
    def test_cmd_s_match(self) -> None:
        event = KeyPress(
            key="s",
            modified_key="s",
            modifiers=KeyModifiers(command=True),
        )
        match event:
            case KeyPress(key="s", modifiers=KeyModifiers(command=True)):
                matched = True
            case _:
                matched = False
        assert matched

    def test_escape_match(self) -> None:
        event = KeyPress(
            key="Escape",
            modified_key="Escape",
            modifiers=KeyModifiers(),
        )
        model = Model(modal_open=True)
        match event:
            case KeyPress(key="Escape"):
                model = replace(model, modal_open=False)
        assert model.modal_open is False

    def test_physical_key_match(self) -> None:
        event = KeyPress(
            key="w",
            modified_key="w",
            modifiers=KeyModifiers(),
            physical_key="KeyW",
        )
        match event:
            case KeyPress(physical_key="KeyW"):
                matched = True
            case _:
                matched = False
        assert matched

    def test_text_field_match(self) -> None:
        event = KeyPress(
            key="a",
            modified_key="a",
            modifiers=KeyModifiers(),
            text="a",
        )
        match event:
            case KeyPress(text=text) if text is not None:
                matched_text = text
            case _:
                matched_text = None
        assert matched_text == "a"


class TestKeyModifiersConstruct:
    def test_modifiers_construct(self) -> None:
        mods = KeyModifiers(shift=True)
        assert mods.shift is True
        assert mods.ctrl is False
        assert mods.command is False


# -- IME events --------------------------------------------------------------


class TestImePreeditMatch:
    def test_preedit_match(self) -> None:
        event = ImePreedit(text="compose", cursor=(0, 7))
        model = Model()
        match event:
            case ImePreedit(text=text):
                model = replace(model, composing=text)
        assert model.composing == "compose"


class TestImeCommitMatch:
    def test_commit_match(self) -> None:
        event = ImeCommit(text="final")
        model = Model(composing="draft", value="prefix")
        match event:
            case ImeCommit(text=text):
                model = replace(model, composing=None, value=model.value + text)
        assert model.composing is None
        assert model.value == "prefixfinal"


# -- Mouse events (global) --------------------------------------------------


class TestSubscriptionPointerMoveMatch:
    def test_subscription_move_match(self) -> None:
        event = Move(id="main", x=100.0, y=200.0, pointer="mouse", window_id="main")
        model = Model()
        match event:
            case Move(x=x, y=y):
                model = replace(model, cursor=(x, y))
        assert model.cursor == (100.0, 200.0)


class TestPointerPressMatch:
    def test_pointer_press_left_match(self) -> None:
        event = Press(
            id="main", x=0.0, y=0.0, button="left", pointer="mouse", window_id="main"
        )
        model = Model()
        match event:
            case Press(button="left"):
                model = replace(model, mouse_down=True)
        assert model.mouse_down is True


class TestPointerTouchPressMatch:
    def test_touch_pointer_press_match(self) -> None:
        event = Press(
            id="main",
            x=50.0,
            y=75.0,
            button="left",
            pointer="touch",
            finger=0,
            window_id="main",
        )
        model = Model()
        match event:
            case Press(pointer="touch", x=x, y=y):
                model = replace(model, touch_start=(x, y))
        assert model.touch_start == (50.0, 75.0)


# -- Modifier state events ---------------------------------------------------


class TestModifiersChangedMatch:
    def test_modifiers_changed_match(self) -> None:
        event = ModifiersChanged(modifiers=KeyModifiers(shift=True))
        model = Model()
        match event:
            case ModifiersChanged(modifiers=KeyModifiers(shift=True)):
                model = replace(model, shift_held=True)
        assert model.shift_held is True


# -- Window events -----------------------------------------------------------


class TestWindowCloseRequestedMatch:
    def test_close_requested_main(self) -> None:
        event = WindowCloseRequested(window_id="main")
        match event:
            case WindowCloseRequested(window_id="main"):
                matched = True
            case _:
                matched = False
        assert matched

    def test_close_with_unsaved_changes(self) -> None:
        model = Model(unsaved_changes=True)
        event = WindowCloseRequested(window_id="main")
        result: Any = model
        match event:
            case WindowCloseRequested(window_id="main"):
                if model.unsaved_changes:
                    result = replace(model, confirm_exit=True)
                else:
                    result = model, Command.close_window("main")
        assert isinstance(result, Model)
        assert result.confirm_exit is True


class TestWindowResizedMatch:
    def test_window_resized_match(self) -> None:
        event = WindowResized(window_id="main", width=800.0, height=600.0)
        match event:
            case WindowResized(window_id="main"):
                matched = True
            case _:
                matched = False
        assert matched


class TestWindowFocusedMatch:
    def test_window_focused_match(self) -> None:
        event = WindowFocused(window_id="editor")
        model = Model()
        match event:
            case WindowFocused(window_id=wid):
                model = replace(model, active_window=wid)
        assert model.active_window == "editor"


class TestFileDragDropMatch:
    def test_file_hovered_match(self) -> None:
        event = FileHovered(window_id="main", path="/foo.txt")
        model = Model()
        match event:
            case FileHovered(window_id="main", path=path):
                model = replace(model, drop_target_active=True, hovered_file=path)
        assert model.drop_target_active is True
        assert model.hovered_file == "/foo.txt"

    def test_file_dropped_match(self) -> None:
        event = FileDropped(window_id="main", path="/foo.txt")
        match event:
            case FileDropped(window_id="main", path=path):
                matched_path = path
            case _:
                matched_path = ""
        assert matched_path == "/foo.txt"

    def test_files_hovered_left_match(self) -> None:
        event = FilesHoveredLeft(window_id="main")
        model = Model(drop_target_active=True)
        match event:
            case FilesHoveredLeft(window_id="main"):
                model = replace(model, drop_target_active=False)
        assert model.drop_target_active is False


# -- System events -----------------------------------------------------------


class TestAnimationFrameConstruct:
    def test_animation_frame(self) -> None:
        event = AnimationFrame(timestamp=12_345)
        assert event.timestamp == 12_345


class TestThemeChangedConstruct:
    def test_theme_changed(self) -> None:
        event = ThemeChanged(theme="dark")
        assert event.theme == "dark"


# -- Timer events ------------------------------------------------------------


class TestTimerTickMatch:
    def test_timer_tick_match(self) -> None:
        event = TimerTick(tag="tick", timestamp=1_000_000)
        match event:
            case TimerTick(tag="tick"):
                matched = True
            case _:
                matched = False
        assert matched
        assert event.timestamp == 1_000_000


# -- Command result events ---------------------------------------------------


class TestAsyncResultMatch:
    def test_async_result_success(self) -> None:
        event = AsyncResult(tag="data_loaded", value="hello")
        match event:
            case AsyncResult(tag="data_loaded", value=body) if body is not None:
                matched_value = body
            case _:
                matched_value = None
        assert matched_value == "hello"

    def test_async_result_error(self) -> None:
        event = AsyncResult(tag="data_loaded", value=Exception("fail"))
        match event:
            case AsyncResult(tag="data_loaded", value=err) if isinstance(
                err, Exception
            ):
                matched_error = str(err)
            case _:
                matched_error = None
        assert matched_error == "fail"


class TestStreamChunkMatch:
    def test_stream_chunk_match(self) -> None:
        event = StreamChunk(tag="file_import", value=42)
        match event:
            case StreamChunk(tag="file_import"):
                matched = True
            case _:
                matched = False
        assert matched


# -- Effect result events ----------------------------------------------------


class TestEffectResultMatch:
    def test_effect_ok(self) -> None:
        event = EffectResult(tag="import", status="ok", result={"path": "/f.txt"})
        match event:
            case EffectResult(status="ok", result=result):
                matched_path = result["path"]
            case _:
                matched_path = ""
        assert matched_path == "/f.txt"

    def test_effect_cancelled(self) -> None:
        event = EffectResult(tag="import", status="cancelled")
        match event:
            case EffectResult(status="cancelled"):
                matched = True
            case _:
                matched = False
        assert matched

    def test_effect_error(self) -> None:
        event = EffectResult(tag="import", status="error", error="err")
        match event:
            case EffectResult(status="error", error=reason):
                matched_reason = reason
            case _:
                matched_reason = ""
        assert matched_reason == "err"


# -- Pattern matching tips ---------------------------------------------------


class TestPrefixMatch:
    def test_nav_prefix_match(self) -> None:
        event = Click(id="nav:settings")
        match event:
            case Click(id=widget_id) if widget_id.startswith("nav:"):
                section = widget_id.removeprefix("nav:")
            case _:
                section = ""
        assert section == "settings"

    def test_toggle_setting_prefix_match(self) -> None:
        event = Toggle(id="setting:theme", value=True)
        match event:
            case Toggle(id=widget_id, value=value) if widget_id.startswith("setting:"):
                key = widget_id.removeprefix("setting:")
            case _:
                key = ""
                value = None  # type: ignore[assignment]
        assert key == "theme"
        assert value is True


# -- Scope matching ----------------------------------------------------------


class TestScopeMatch:
    def test_scope_sidebar_match(self) -> None:
        event = Click(id="save", scope=("sidebar",))
        match event:
            case Click(id="save", scope=("sidebar", *_)):
                matched = "sidebar"
            case _:
                matched = ""
        assert matched == "sidebar"

    def test_scope_main_match(self) -> None:
        event = Click(id="save", scope=("main",))
        match event:
            case Click(id="save", scope=("main", *_)):
                matched = "main"
            case _:
                matched = ""
        assert matched == "main"


class TestCatchAll:
    def test_catch_all_fallback(self) -> None:
        event = Click(id="unknown")
        model = Model()
        match event:
            case Click(id="save"):
                pass
            case _:
                result = model
        assert result is model  # type: ignore[possibly-undefined]
