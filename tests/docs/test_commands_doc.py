"""Tests for code blocks in docs/commands.md.

Verifies that command construction, subscription construction, and
update return tuples work as documented.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from plushie.commands import Command
from plushie.subscriptions import Subscription

# ---------------------------------------------------------------------------
# Helpers -- minimal model dataclasses used across tests
# ---------------------------------------------------------------------------


@dataclass
class SaveModel:
    saving: bool = False
    saved: bool = False
    error: str | None = None


@dataclass
class LoadingModel:
    loading: bool = False
    data: object = None


@dataclass
class ImportModel:
    importing: bool = False
    rows_imported: int = 0
    data: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.data is None:
            self.data = []


@dataclass
class MessageModel:
    message: str | None = None


@dataclass
class StatusModel:
    status: str = "idle"


@dataclass
class PollModel:
    polling: bool = False


@dataclass
class WindowModel:
    window_width: float = 0
    window_height: float = 0
    os_theme: str = ""


# ---------------------------------------------------------------------------
# test_update_returns_bare_model
# ---------------------------------------------------------------------------


def test_update_returns_bare_model():
    """update() can return a bare model (no command)."""
    model = SaveModel()
    result = model  # simulate: return model
    assert isinstance(result, SaveModel)


# ---------------------------------------------------------------------------
# test_update_returns_model_command_tuple
# ---------------------------------------------------------------------------


def test_update_returns_model_command_tuple():
    """update() can return a (model, command) tuple."""
    model = SaveModel()
    new_model = replace(model, saving=True)
    cmd = Command.task(lambda: "saved", "save_result")
    result = (new_model, cmd)

    assert result[0].saving is True
    assert result[1].type == "task"
    assert result[1].payload["tag"] == "save_result"


# ---------------------------------------------------------------------------
# test_command_task
# ---------------------------------------------------------------------------


def test_command_task():
    """Command.task() creates an async task command."""

    def fn():
        return {"key": "value"}

    cmd = Command.task(fn, "data_fetched")

    assert cmd.type == "task"
    assert cmd.payload["tag"] == "data_fetched"
    assert cmd.payload["fn"] is fn


# ---------------------------------------------------------------------------
# test_command_stream
# ---------------------------------------------------------------------------


def test_command_stream():
    """Command.stream() creates a streaming async command."""

    def do_import(emit):
        for n in range(1, 4):
            emit(("progress", n))
        return ("complete", [1, 2, 3])

    cmd = Command.stream(do_import, "file_import")

    assert cmd.type == "stream"
    assert cmd.payload["tag"] == "file_import"
    assert cmd.payload["fn"] is do_import


# ---------------------------------------------------------------------------
# test_command_cancel
# ---------------------------------------------------------------------------


def test_command_cancel():
    """Command.cancel() creates a cancellation command."""
    cmd = Command.cancel("file_import")

    assert cmd.type == "cancel"
    assert cmd.payload["tag"] == "file_import"


# ---------------------------------------------------------------------------
# test_command_done
# ---------------------------------------------------------------------------


def test_command_done():
    """Command.done() wraps an already-resolved value."""

    def mapper(v):
        return ("config_loaded", v)

    cmd = Command.done("defaults", mapper)

    assert cmd.type == "done"
    assert cmd.payload["value"] == "defaults"
    assert cmd.payload["mapper"] is mapper


# ---------------------------------------------------------------------------
# test_command_exit
# ---------------------------------------------------------------------------


def test_command_exit():
    """Command.exit() creates an exit command."""
    cmd = Command.exit()

    assert cmd.type == "exit"
    assert cmd.payload == {}


# ---------------------------------------------------------------------------
# test_command_focus
# ---------------------------------------------------------------------------


def test_command_focus():
    """Command.focus() targets a specific widget."""
    cmd = Command.focus("todo_input")

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "focus"
    assert cmd.payload["target"] == "todo_input"


def test_command_focus_next():
    """Command.focus_next() moves to the next focusable widget."""
    cmd = Command.focus_next()

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "focus_next"


def test_command_focus_previous():
    """Command.focus_previous() moves to the previous focusable widget."""
    cmd = Command.focus_previous()

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "focus_previous"


# ---------------------------------------------------------------------------
# test_command_text_operations
# ---------------------------------------------------------------------------


def test_command_select_all():
    """Command.select_all() selects all text in a widget."""
    cmd = Command.select_all("editor")

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "select_all"
    assert cmd.payload["target"] == "editor"


def test_command_select_range():
    """Command.select_range() selects a character range."""
    cmd = Command.select_range("editor", 5, 10)

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "select_range"
    assert cmd.payload["target"] == "editor"
    assert cmd.payload["start"] == 5
    assert cmd.payload["end"] == 10


def test_command_move_cursor_to():
    """Command.move_cursor_to() positions the cursor."""
    cmd = Command.move_cursor_to("editor", 42)

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "move_cursor_to"
    assert cmd.payload["position"] == 42


def test_command_move_cursor_to_front():
    """Command.move_cursor_to_front() moves cursor to start."""
    cmd = Command.move_cursor_to_front("editor")

    assert cmd.payload["op"] == "move_cursor_to_front"


def test_command_move_cursor_to_end():
    """Command.move_cursor_to_end() moves cursor to end."""
    cmd = Command.move_cursor_to_end("editor")

    assert cmd.payload["op"] == "move_cursor_to_end"


# ---------------------------------------------------------------------------
# test_command_scroll_operations
# ---------------------------------------------------------------------------


def test_command_scroll_to():
    """Command.scroll_to() scrolls to an absolute vertical position."""
    cmd = Command.scroll_to("chat_log", 500.0)

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "scroll_to"
    assert cmd.payload["target"] == "chat_log"
    assert cmd.payload["offset_y"] == 500.0


def test_command_snap_to():
    """Command.snap_to() snaps to an absolute scroll offset."""
    cmd = Command.snap_to("scroller", 0.0, 100.0)

    assert cmd.payload["op"] == "snap_to"
    assert cmd.payload["x"] == 0.0
    assert cmd.payload["y"] == 100.0


def test_command_snap_to_end():
    """Command.snap_to_end() snaps to the end of scrollable content."""
    cmd = Command.snap_to_end("chat_log")

    assert cmd.payload["op"] == "snap_to_end"
    assert cmd.payload["target"] == "chat_log"


def test_command_scroll_by():
    """Command.scroll_by() scrolls by a relative delta."""
    cmd = Command.scroll_by("scroller", 0.0, 50.0)

    assert cmd.payload["op"] == "scroll_by"
    assert cmd.payload["x"] == 0.0
    assert cmd.payload["y"] == 50.0


# ---------------------------------------------------------------------------
# test_command_window_ops
# ---------------------------------------------------------------------------


def test_command_close_window():
    """Command.close_window() closes a window by ID."""
    cmd = Command.close_window("popup")

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "close_window"
    assert cmd.payload["window_id"] == "popup"


def test_command_resize_window():
    """Command.resize_window() resizes a window."""
    cmd = Command.resize_window("main", 800, 600)

    assert cmd.type == "window_op"
    assert cmd.payload["op"] == "resize"
    assert cmd.payload["width"] == 800
    assert cmd.payload["height"] == 600


def test_command_move_window():
    """Command.move_window() repositions a window."""
    cmd = Command.move_window("main", 100, 200)

    assert cmd.payload["op"] == "move"
    assert cmd.payload["x"] == 100
    assert cmd.payload["y"] == 200


def test_command_maximize_window():
    """Command.maximize_window() maximizes or restores a window."""
    cmd_max = Command.maximize_window("main")
    assert cmd_max.payload["maximized"] is True

    cmd_restore = Command.maximize_window("main", False)
    assert cmd_restore.payload["maximized"] is False


def test_command_minimize_window():
    """Command.minimize_window() minimizes or restores a window."""
    cmd_min = Command.minimize_window("main")
    assert cmd_min.payload["minimized"] is True

    cmd_restore = Command.minimize_window("main", False)
    assert cmd_restore.payload["minimized"] is False


def test_command_set_window_mode():
    """Command.set_window_mode() sets fullscreen/windowed."""
    cmd = Command.set_window_mode("main", "fullscreen")

    assert cmd.payload["op"] == "set_mode"
    assert cmd.payload["mode"] == "fullscreen"


def test_command_set_window_level():
    """Command.set_window_level() sets stacking level."""
    cmd = Command.set_window_level("main", "always_on_top")

    assert cmd.payload["op"] == "set_level"
    assert cmd.payload["level"] == "always_on_top"


def test_command_toggle_maximize():
    """Command.toggle_maximize() toggles maximized state."""
    cmd = Command.toggle_maximize("main")
    assert cmd.payload["op"] == "toggle_maximize"


def test_command_toggle_decorations():
    """Command.toggle_decorations() toggles title bar/borders."""
    cmd = Command.toggle_decorations("main")
    assert cmd.payload["op"] == "toggle_decorations"


def test_command_gain_focus():
    """Command.gain_focus() brings a window to front."""
    cmd = Command.gain_focus("main")
    assert cmd.payload["op"] == "gain_focus"


def test_command_drag_window():
    """Command.drag_window() initiates OS window drag."""
    cmd = Command.drag_window("main")
    assert cmd.payload["op"] == "drag"


def test_command_drag_resize_window():
    """Command.drag_resize_window() initiates drag-resize from edge."""
    cmd = Command.drag_resize_window("main", "south_east")
    assert cmd.payload["op"] == "drag_resize"
    assert cmd.payload["direction"] == "south_east"


def test_command_request_user_attention():
    """Command.request_user_attention() flashes the taskbar."""
    cmd = Command.request_user_attention("main", "critical")
    assert cmd.payload["urgency"] == "critical"


def test_command_screenshot_window():
    """Command.screenshot_window() captures window pixels."""
    cmd = Command.screenshot_window("main", "snap")
    assert cmd.payload["op"] == "screenshot"
    assert cmd.payload["tag"] == "snap"


def test_command_set_resizable():
    """Command.set_resizable() enables/disables resize."""
    cmd = Command.set_resizable("main", False)
    assert cmd.payload["resizable"] is False


def test_command_set_min_max_size():
    """Command.set_min_size/set_max_size set window size bounds."""
    cmd_min = Command.set_min_size("main", 400, 300)
    assert cmd_min.payload["width"] == 400

    cmd_max = Command.set_max_size("main", 1920, 1080)
    assert cmd_max.payload["width"] == 1920


def test_command_mouse_passthrough():
    """enable/disable_mouse_passthrough controls click-through."""
    cmd_on = Command.enable_mouse_passthrough("overlay")
    assert cmd_on.payload["enabled"] is True

    cmd_off = Command.disable_mouse_passthrough("overlay")
    assert cmd_off.payload["enabled"] is False


def test_command_show_system_menu():
    """Command.show_system_menu() shows the OS window menu."""
    cmd = Command.show_system_menu("main")
    assert cmd.payload["op"] == "show_system_menu"


def test_command_set_icon():
    """Command.set_icon() sets the window icon from raw RGBA data."""
    rgba = b"\xff" * (16 * 16 * 4)
    cmd = Command.set_icon("main", rgba, 16, 16)
    assert cmd.payload["icon_data"] == rgba
    assert cmd.payload["width"] == 16


def test_command_set_resize_increments():
    """Command.set_resize_increments() sets step increments."""
    cmd = Command.set_resize_increments("main", 8.0, 8.0)
    assert cmd.payload["width"] == 8.0


def test_command_allow_automatic_tabbing():
    """Command.allow_automatic_tabbing() controls macOS tab grouping."""
    cmd = Command.allow_automatic_tabbing(True)
    assert cmd.payload["enabled"] is True


# ---------------------------------------------------------------------------
# test_window_queries
# ---------------------------------------------------------------------------


def test_command_get_window_size():
    """Command.get_window_size() queries window dimensions."""
    cmd = Command.get_window_size("main", "got_size")

    assert cmd.type == "window_query"
    assert cmd.payload["op"] == "get_size"
    assert cmd.payload["window_id"] == "main"


def test_command_get_window_position():
    """Command.get_window_position() queries window position."""
    cmd = Command.get_window_position("main", "got_pos")
    assert cmd.payload["op"] == "get_position"


def test_command_get_mode():
    """Command.get_mode() queries the window display mode."""
    cmd = Command.get_mode("main", "got_mode")
    assert cmd.payload["op"] == "get_mode"


def test_command_get_scale_factor():
    """Command.get_scale_factor() queries DPI scale."""
    cmd = Command.get_scale_factor("main", "got_scale")
    assert cmd.payload["op"] == "get_scale_factor"


def test_command_is_maximized():
    """Command.is_maximized() queries maximized state."""
    cmd = Command.is_maximized("main", "is_max")
    assert cmd.payload["op"] == "is_maximized"


def test_command_is_minimized():
    """Command.is_minimized() queries minimized state."""
    cmd = Command.is_minimized("main", "is_min")
    assert cmd.payload["op"] == "is_minimized"


def test_command_raw_id():
    """Command.raw_id() queries the platform window handle."""
    cmd = Command.raw_id("main", "raw")
    assert cmd.payload["op"] == "raw_id"


def test_command_monitor_size():
    """Command.monitor_size() queries display dimensions."""
    cmd = Command.monitor_size("main", "mon")
    assert cmd.payload["op"] == "monitor_size"


def test_command_get_system_theme():
    """Command.get_system_theme() queries the OS light/dark preference."""
    cmd = Command.get_system_theme("theme_detected")

    assert cmd.type == "system_query"
    assert cmd.payload["op"] == "get_system_theme"
    assert cmd.payload["tag"] == "theme_detected"


def test_command_get_system_info():
    """Command.get_system_info() queries system hardware info."""
    cmd = Command.get_system_info("sysinfo")
    assert cmd.payload["op"] == "get_system_info"


# ---------------------------------------------------------------------------
# test_image_operations
# ---------------------------------------------------------------------------


def test_command_create_image():
    """Command.create_image() registers an image from encoded bytes."""
    data = b"\x89PNG"
    cmd = Command.create_image("preview", data)

    assert cmd.type == "image_op"
    assert cmd.payload["op"] == "create_image"
    assert cmd.payload["handle"] == "preview"
    assert cmd.payload["data"] is data


def test_command_create_image_rgba():
    """Command.create_image_rgba() registers from raw RGBA pixels."""
    pixels = b"\xff" * (2 * 2 * 4)
    cmd = Command.create_image_rgba("tex", 2, 2, pixels)

    assert cmd.payload["width"] == 2
    assert cmd.payload["pixels"] is pixels


def test_command_update_image():
    """Command.update_image() replaces image data."""
    cmd = Command.update_image("preview", b"new_data")
    assert cmd.payload["op"] == "update_image"


def test_command_update_image_rgba():
    """Command.update_image_rgba() replaces with raw RGBA."""
    cmd = Command.update_image_rgba("tex", 4, 4, b"\x00" * 64)
    assert cmd.payload["op"] == "update_image"
    assert cmd.payload["width"] == 4


def test_command_delete_image():
    """Command.delete_image() removes a registered image."""
    cmd = Command.delete_image("preview")

    assert cmd.payload["op"] == "delete_image"
    assert cmd.payload["handle"] == "preview"


def test_command_clear_images():
    """Command.clear_images() removes all registered images."""
    cmd = Command.clear_images()
    assert cmd.payload["op"] == "clear_images"


# ---------------------------------------------------------------------------
# test_pane_grid_operations
# ---------------------------------------------------------------------------


def test_command_pane_split():
    """Command.pane_split() splits a pane along an axis."""
    cmd = Command.pane_split("pane_grid", "editor", "horizontal", "new_editor")

    assert cmd.type == "widget_op"
    assert cmd.payload["op"] == "pane_split"
    assert cmd.payload["target"] == "pane_grid"
    assert cmd.payload["axis"] == "horizontal"
    assert cmd.payload["new_pane_id"] == "new_editor"


def test_command_pane_close():
    """Command.pane_close() removes a pane."""
    cmd = Command.pane_close("pane_grid", "editor")
    assert cmd.payload["op"] == "pane_close"


def test_command_pane_swap():
    """Command.pane_swap() exchanges two panes."""
    cmd = Command.pane_swap("pane_grid", "a", "b")
    assert cmd.payload["op"] == "pane_swap"
    assert cmd.payload["a"] == "a"
    assert cmd.payload["b"] == "b"


def test_command_pane_maximize():
    """Command.pane_maximize() fills the grid with one pane."""
    cmd = Command.pane_maximize("pane_grid", "editor")
    assert cmd.payload["op"] == "pane_maximize"


def test_command_pane_restore():
    """Command.pane_restore() restores all panes from maximized."""
    cmd = Command.pane_restore("pane_grid")
    assert cmd.payload["op"] == "pane_restore"


# ---------------------------------------------------------------------------
# test_command_send_after
# ---------------------------------------------------------------------------


def test_command_send_after():
    """Command.send_after() schedules a delayed event."""
    cmd = Command.send_after(3000, "clear_message")

    assert cmd.type == "send_after"
    assert cmd.payload["delay"] == 3000
    assert cmd.payload["event"] == "clear_message"


# ---------------------------------------------------------------------------
# test_command_batch
# ---------------------------------------------------------------------------


def test_command_batch():
    """Command.batch() groups commands for sequential dispatch."""
    cmd = Command.batch(
        [
            Command.focus("name_input"),
            Command.send_after(5000, "auto_save"),
        ]
    )

    assert cmd.type == "batch"
    cmds = cmd.payload["commands"]
    assert len(cmds) == 2
    assert cmds[0].type == "widget_op"
    assert cmds[1].type == "send_after"


# ---------------------------------------------------------------------------
# test_command_extension
# ---------------------------------------------------------------------------


def test_command_widget_command():
    """Command.widget_command() sends data to a native widget."""
    cmd = Command.widget_command("term-1", "write", {"data": "hello"})

    assert cmd.type == "extension_command"
    assert cmd.payload["node_id"] == "term-1"
    assert cmd.payload["op"] == "write"
    assert cmd.payload["payload"] == {"data": "hello"}


def test_command_widget_commands():
    """Command.widget_commands() batches widget commands."""
    cmd = Command.widget_commands(
        [
            ("term-1", "write", {"data": "line1"}),
            ("log-1", "append", {"line": "entry"}),
        ]
    )

    assert cmd.type == "extension_commands"
    assert len(cmd.payload["commands"]) == 2


# ---------------------------------------------------------------------------
# test_command_advance_frame
# ---------------------------------------------------------------------------


def test_command_advance_frame():
    """Command.advance_frame() advances the animation clock."""
    cmd = Command.advance_frame(16000)

    assert cmd.type == "advance_frame"
    assert cmd.payload["timestamp"] == 16000


# ---------------------------------------------------------------------------
# test_command_none
# ---------------------------------------------------------------------------


def test_command_none():
    """Command.none() is an explicit no-op."""
    cmd = Command.none()
    assert cmd.type == "none"
    assert cmd.payload == {}


# ---------------------------------------------------------------------------
# test_command_announce_and_load_font
# ---------------------------------------------------------------------------


def test_command_announce():
    """Command.announce() sends text to screen readers."""
    cmd = Command.announce("Item saved")
    assert cmd.payload["op"] == "announce"
    assert cmd.payload["text"] == "Item saved"


def test_command_load_font():
    """Command.load_font() loads a font from raw bytes."""
    cmd = Command.load_font(b"\x00\x01\x00\x00")
    assert cmd.payload["op"] == "load_font"


# ---------------------------------------------------------------------------
# test_renderer_queries
# ---------------------------------------------------------------------------


def test_command_tree_hash_query():
    """Command.tree_hash_query() requests the renderer's tree hash."""
    cmd = Command.tree_hash_query("hash_check")
    assert cmd.payload["op"] == "tree_hash"


def test_command_find_focused_query():
    """Command.find_focused_query() queries current focus."""
    cmd = Command.find_focused_query("focus_check")
    assert cmd.payload["op"] == "find_focused"


def test_command_list_images_query():
    """Command.list_images_query() lists registered image handles."""
    cmd = Command.list_images_query("img_check")
    assert cmd.payload["op"] == "list_images"


# ---------------------------------------------------------------------------
# test_update_testability -- commands are inspectable data
# ---------------------------------------------------------------------------


def test_update_returns_inspectable_command():
    """Commands are pure data that can be inspected in tests."""
    model = {"loading": False}
    # Simulate an update function
    new_model = {**model, "loading": True}
    cmd = Command.task(lambda: None, "fetch")
    result = (new_model, cmd)

    new_model, cmd = result
    assert new_model["loading"] is True
    assert cmd.type == "task"


# ---------------------------------------------------------------------------
# test_subscription_construction
# ---------------------------------------------------------------------------


def test_subscription_every():
    """Subscription.every() creates a timer subscription."""
    sub = Subscription.every(1000, "tick")

    assert sub.kind == "every"
    assert sub.tag == "tick"
    assert sub.interval_ms == 1000


def test_subscription_on_key_press():
    """Subscription.on_key_press() subscribes to key events."""
    sub = Subscription.on_key_press("key_event")

    assert sub.kind == "on_key_press"
    assert sub.tag == "key_event"


def test_subscription_on_key_release():
    """Subscription.on_key_release() subscribes to key release events."""
    sub = Subscription.on_key_release("keys")
    assert sub.kind == "on_key_release"


def test_subscription_on_modifiers_changed():
    """Subscription.on_modifiers_changed() subscribes to modifier changes."""
    sub = Subscription.on_modifiers_changed("mods")
    assert sub.kind == "on_modifiers_changed"


def test_subscription_on_window_close():
    """Subscription.on_window_close() subscribes to window close events."""
    sub = Subscription.on_window_close("wclose")
    assert sub.kind == "on_window_close"


def test_subscription_on_window_open():
    """Subscription.on_window_open() subscribes to window open events."""
    sub = Subscription.on_window_open("wopen")
    assert sub.kind == "on_window_open"


def test_subscription_on_window_resize():
    """Subscription.on_window_resize() subscribes to window resize events."""
    sub = Subscription.on_window_resize("wresize")
    assert sub.kind == "on_window_resize"


def test_subscription_on_window_focus():
    """Subscription.on_window_focus() subscribes to window focus events."""
    sub = Subscription.on_window_focus("wfocus")
    assert sub.kind == "on_window_focus"


def test_subscription_on_window_unfocus():
    """Subscription.on_window_unfocus() subscribes to window unfocus events."""
    sub = Subscription.on_window_unfocus("wunfocus")
    assert sub.kind == "on_window_unfocus"


def test_subscription_on_window_move():
    """Subscription.on_window_move() subscribes to window move events."""
    sub = Subscription.on_window_move("wmove")
    assert sub.kind == "on_window_move"


def test_subscription_on_window_event():
    """Subscription.on_window_event() is the catch-all for window events."""
    sub = Subscription.on_window_event("wall")
    assert sub.kind == "on_window_event"


def test_subscription_on_pointer_move():
    """Subscription.on_pointer_move() subscribes to mouse movement."""
    sub = Subscription.on_pointer_move("mouse")
    assert sub.kind == "on_pointer_move"


def test_subscription_on_pointer_button():
    """Subscription.on_pointer_button() subscribes to mouse clicks."""
    sub = Subscription.on_pointer_button("mbutton")
    assert sub.kind == "on_pointer_button"


def test_subscription_on_pointer_scroll():
    """Subscription.on_pointer_scroll() subscribes to scroll events."""
    sub = Subscription.on_pointer_scroll("mscroll")
    assert sub.kind == "on_pointer_scroll"


def test_subscription_on_touch():
    """Subscription.on_pointer_touch() subscribes to touch events."""
    sub = Subscription.on_pointer_touch("touch")
    assert sub.kind == "on_touch"


def test_subscription_on_ime():
    """Subscription.on_ime() subscribes to IME events."""
    sub = Subscription.on_ime("ime")
    assert sub.kind == "on_ime"


def test_subscription_on_theme_change():
    """Subscription.on_theme_change() subscribes to OS theme changes."""
    sub = Subscription.on_theme_change("theme_changed")
    assert sub.kind == "on_theme_change"


def test_subscription_on_animation_frame():
    """Subscription.on_animation_frame() subscribes to vsync ticks."""
    sub = Subscription.on_animation_frame("frame")
    assert sub.kind == "on_animation_frame"


def test_subscription_on_file_drop():
    """Subscription.on_file_drop() subscribes to file drop events."""
    sub = Subscription.on_file_drop("fdrop")
    assert sub.kind == "on_file_drop"


def test_subscription_on_event():
    """Subscription.on_event() is the catch-all subscription."""
    sub = Subscription.on_event("everything")
    assert sub.kind == "on_event"


# ---------------------------------------------------------------------------
# test_subscription_max_rate
# ---------------------------------------------------------------------------


def test_subscription_max_rate():
    """Renderer subscriptions accept a max_rate keyword."""
    sub = Subscription.on_pointer_move("mouse", max_rate=30)

    assert sub.max_rate == 30

    sub_frame = Subscription.on_animation_frame("frame", max_rate=60)
    assert sub_frame.max_rate == 60

    sub_zero = Subscription.on_pointer_move("mouse", max_rate=0)
    assert sub_zero.max_rate == 0


def test_subscription_every_no_max_rate():
    """Timer subscriptions do not support max_rate (it stays None)."""
    sub = Subscription.every(1000, "tick")
    assert sub.max_rate is None


# ---------------------------------------------------------------------------
# test_subscription_lifecycle -- declarative start/stop
# ---------------------------------------------------------------------------


def test_subscription_lifecycle_declarative():
    """Subscriptions are driven by the list returned from subscribe()."""
    model = PollModel(polling=True)

    def subscribe(model: PollModel) -> list[Subscription]:
        if model.polling:
            return [Subscription.every(5000, "poll")]
        return []

    subs_on = subscribe(model)
    assert len(subs_on) == 1
    assert subs_on[0].kind == "every"

    subs_off = subscribe(replace(model, polling=False))
    assert len(subs_off) == 0


# ---------------------------------------------------------------------------
# test_subscription_key_identity
# ---------------------------------------------------------------------------


def test_subscription_key_identity():
    """Same spec produces the same key for diffing."""
    a = Subscription.every(1000, "tick")
    b = Subscription.every(1000, "tick")
    assert a.key == b.key

    c = Subscription.on_key_press("keys")
    d = Subscription.on_key_press("keys")
    assert c.key == d.key

    # Different interval = different key
    e = Subscription.every(500, "tick")
    assert a.key != e.key


# ---------------------------------------------------------------------------
# test_chaining_pattern -- update cycle provides natural chaining
# ---------------------------------------------------------------------------


def test_chaining_via_update_cycle():
    """Commands chain naturally through the update cycle."""
    model = StatusModel(status="idle")

    # Step 1: user clicks deploy
    new_model = replace(model, status="validating")
    cmd1 = Command.task(lambda: "ok", "validated")
    assert new_model.status == "validating"
    assert cmd1.payload["tag"] == "validated"

    # Step 2: validation ok -> start build
    new_model2 = replace(new_model, status="building")
    cmd2 = Command.task(lambda: ("ok", "artifact"), "built")
    assert new_model2.status == "building"
    assert cmd2.payload["tag"] == "built"

    # Step 3: build ok -> deploy
    new_model3 = replace(new_model2, status="deploying")
    cmd3 = Command.task(lambda: "ok", "deployed")
    assert new_model3.status == "deploying"
    assert cmd3.payload["tag"] == "deployed"

    # Step 4: done
    final = replace(new_model3, status="live")
    assert final.status == "live"
