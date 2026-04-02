"""Tests for plushie.commands."""

from __future__ import annotations

from plushie.commands import Command


class TestNone:
    def test_type_and_payload(self) -> None:
        cmd = Command.none()
        assert cmd.type == "none"
        assert cmd.payload == {}


class TestAsyncLifecycle:
    def test_task(self) -> None:
        def work() -> int:
            return 42

        cmd = Command.task(work, "my_tag")
        assert cmd.type == "task"
        assert cmd.payload["fn"] is work
        assert cmd.payload["tag"] == "my_tag"

    def test_stream(self) -> None:
        def work(emit: object) -> None:
            pass

        cmd = Command.stream(work, "s")
        assert cmd.type == "stream"
        assert cmd.payload["fn"] is work
        assert cmd.payload["tag"] == "s"

    def test_cancel(self) -> None:
        cmd = Command.cancel("s")
        assert cmd.type == "cancel"
        assert cmd.payload["tag"] == "s"

    def test_done(self) -> None:
        def mapper(v: object) -> object:
            return v

        cmd = Command.done(42, mapper)
        assert cmd.type == "done"
        assert cmd.payload["value"] == 42
        assert cmd.payload["mapper"] is mapper

    def test_send_after(self) -> None:
        cmd = Command.send_after(1000, "tick")
        assert cmd.type == "send_after"
        assert cmd.payload["delay"] == 1000
        assert cmd.payload["event"] == "tick"

    def test_exit(self) -> None:
        cmd = Command.exit()
        assert cmd.type == "exit"
        assert cmd.payload == {}

    def test_batch(self) -> None:
        c1 = Command.none()
        c2 = Command.exit()
        cmd = Command.batch([c1, c2])
        assert cmd.type == "batch"
        assert cmd.payload["commands"] == [c1, c2]

    def test_batch_empty(self) -> None:
        cmd = Command.batch([])
        assert cmd.type == "batch"
        assert cmd.payload["commands"] == []


class TestWidgetOps:
    def test_focus(self) -> None:
        cmd = Command.focus("email")
        assert cmd.type == "widget_op"
        assert cmd.payload["op"] == "focus"
        assert cmd.payload["target"] == "email"

    def test_focus_next(self) -> None:
        cmd = Command.focus_next()
        assert cmd.type == "widget_op"
        assert cmd.payload["op"] == "focus_next"

    def test_focus_previous(self) -> None:
        cmd = Command.focus_previous()
        assert cmd.type == "widget_op"
        assert cmd.payload["op"] == "focus_previous"

    def test_select_all(self) -> None:
        cmd = Command.select_all("editor")
        assert cmd.payload["op"] == "select_all"
        assert cmd.payload["target"] == "editor"

    def test_select_range(self) -> None:
        cmd = Command.select_range("editor", 5, 10)
        assert cmd.payload["op"] == "select_range"
        assert cmd.payload["start"] == 5
        assert cmd.payload["end"] == 10

    def test_move_cursor_to(self) -> None:
        cmd = Command.move_cursor_to("input", 7)
        assert cmd.payload["op"] == "move_cursor_to"
        assert cmd.payload["position"] == 7

    def test_move_cursor_to_front(self) -> None:
        cmd = Command.move_cursor_to_front("input")
        assert cmd.payload["op"] == "move_cursor_to_front"
        assert cmd.payload["target"] == "input"

    def test_move_cursor_to_end(self) -> None:
        cmd = Command.move_cursor_to_end("input")
        assert cmd.payload["op"] == "move_cursor_to_end"

    def test_scroll_to(self) -> None:
        cmd = Command.scroll_to("log", 100.0)
        assert cmd.payload["op"] == "scroll_to"
        assert cmd.payload["offset_y"] == 100.0

    def test_snap_to(self) -> None:
        cmd = Command.snap_to("log", x=10.0, y=20.0)
        assert cmd.payload["op"] == "snap_to"
        assert cmd.payload["x"] == 10.0
        assert cmd.payload["y"] == 20.0

    def test_snap_to_defaults(self) -> None:
        cmd = Command.snap_to("log")
        assert cmd.payload["x"] == 0.0
        assert cmd.payload["y"] == 0.0

    def test_snap_to_end(self) -> None:
        cmd = Command.snap_to_end("log")
        assert cmd.payload["op"] == "snap_to_end"

    def test_scroll_by(self) -> None:
        cmd = Command.scroll_by("log", x=0.0, y=50.0)
        assert cmd.payload["op"] == "scroll_by"
        assert cmd.payload["y"] == 50.0

    def test_close_window(self) -> None:
        cmd = Command.close_window("main")
        assert cmd.type == "widget_op"
        assert cmd.payload["op"] == "close_window"
        assert cmd.payload["window_id"] == "main"

    def test_announce(self) -> None:
        cmd = Command.announce("Saved")
        assert cmd.payload["op"] == "announce"
        assert cmd.payload["text"] == "Saved"

    def test_load_font(self) -> None:
        cmd = Command.load_font(b"\x00\x01")
        assert cmd.payload["op"] == "load_font"
        assert cmd.payload["data"] == b"\x00\x01"

    def test_tree_hash_query(self) -> None:
        cmd = Command.tree_hash_query("t1")
        assert cmd.payload["op"] == "tree_hash"
        assert cmd.payload["tag"] == "t1"

    def test_find_focused_query(self) -> None:
        cmd = Command.find_focused_query("f1")
        assert cmd.payload["op"] == "find_focused"
        assert cmd.payload["tag"] == "f1"

    def test_list_images_query(self) -> None:
        cmd = Command.list_images_query("img")
        assert cmd.payload["op"] == "list_images"
        assert cmd.payload["tag"] == "img"

    def test_clear_images(self) -> None:
        cmd = Command.clear_images()
        assert cmd.payload["op"] == "clear_images"

    def test_pane_split(self) -> None:
        cmd = Command.pane_split("grid", "p1", "horizontal", "p2")
        assert cmd.payload["op"] == "pane_split"
        assert cmd.payload["target"] == "grid"
        assert cmd.payload["pane"] == "p1"
        assert cmd.payload["axis"] == "horizontal"
        assert cmd.payload["new_pane_id"] == "p2"

    def test_pane_close(self) -> None:
        cmd = Command.pane_close("grid", "p1")
        assert cmd.payload["op"] == "pane_close"
        assert cmd.payload["pane"] == "p1"

    def test_pane_swap(self) -> None:
        cmd = Command.pane_swap("grid", "a", "b")
        assert cmd.payload["op"] == "pane_swap"
        assert cmd.payload["a"] == "a"
        assert cmd.payload["b"] == "b"

    def test_pane_maximize(self) -> None:
        cmd = Command.pane_maximize("grid", "p1")
        assert cmd.payload["op"] == "pane_maximize"
        assert cmd.payload["pane"] == "p1"

    def test_pane_restore(self) -> None:
        cmd = Command.pane_restore("grid")
        assert cmd.payload["op"] == "pane_restore"
        assert cmd.payload["target"] == "grid"


class TestWindowOps:
    def test_resize_window(self) -> None:
        cmd = Command.resize_window("main", 800.0, 600.0)
        assert cmd.type == "window_op"
        assert cmd.payload["op"] == "resize"
        assert cmd.payload["width"] == 800.0
        assert cmd.payload["height"] == 600.0

    def test_move_window(self) -> None:
        cmd = Command.move_window("main", 100.0, 200.0)
        assert cmd.payload["op"] == "move"
        assert cmd.payload["x"] == 100.0

    def test_maximize_window(self) -> None:
        cmd = Command.maximize_window("main")
        assert cmd.payload["op"] == "maximize"
        assert cmd.payload["maximized"] is True

    def test_maximize_window_restore(self) -> None:
        cmd = Command.maximize_window("main", maximized=False)
        assert cmd.payload["maximized"] is False

    def test_minimize_window(self) -> None:
        cmd = Command.minimize_window("main")
        assert cmd.payload["op"] == "minimize"
        assert cmd.payload["minimized"] is True

    def test_set_window_mode(self) -> None:
        cmd = Command.set_window_mode("main", "fullscreen")
        assert cmd.payload["op"] == "set_mode"
        assert cmd.payload["mode"] == "fullscreen"

    def test_toggle_maximize(self) -> None:
        cmd = Command.toggle_maximize("main")
        assert cmd.payload["op"] == "toggle_maximize"

    def test_toggle_decorations(self) -> None:
        cmd = Command.toggle_decorations("main")
        assert cmd.payload["op"] == "toggle_decorations"

    def test_gain_focus(self) -> None:
        cmd = Command.gain_focus("main")
        assert cmd.payload["op"] == "gain_focus"

    def test_set_window_level(self) -> None:
        cmd = Command.set_window_level("main", "always_on_top")
        assert cmd.payload["op"] == "set_level"
        assert cmd.payload["level"] == "always_on_top"

    def test_drag_window(self) -> None:
        cmd = Command.drag_window("main")
        assert cmd.payload["op"] == "drag"

    def test_drag_resize_window(self) -> None:
        cmd = Command.drag_resize_window("main", "south_east")
        assert cmd.payload["op"] == "drag_resize"
        assert cmd.payload["direction"] == "south_east"

    def test_request_user_attention(self) -> None:
        cmd = Command.request_user_attention("main", "critical")
        assert cmd.payload["op"] == "request_attention"
        assert cmd.payload["urgency"] == "critical"

    def test_request_user_attention_none(self) -> None:
        cmd = Command.request_user_attention("main")
        assert cmd.payload["urgency"] is None

    def test_set_resizable(self) -> None:
        cmd = Command.set_resizable("main", False)
        assert cmd.payload["resizable"] is False

    def test_set_min_size(self) -> None:
        cmd = Command.set_min_size("main", 400.0, 300.0)
        assert cmd.payload["op"] == "set_min_size"
        assert cmd.payload["width"] == 400.0

    def test_set_max_size(self) -> None:
        cmd = Command.set_max_size("main", 1920.0, 1080.0)
        assert cmd.payload["op"] == "set_max_size"

    def test_enable_mouse_passthrough(self) -> None:
        cmd = Command.enable_mouse_passthrough("main")
        assert cmd.payload["op"] == "mouse_passthrough"
        assert cmd.payload["enabled"] is True

    def test_disable_mouse_passthrough(self) -> None:
        cmd = Command.disable_mouse_passthrough("main")
        assert cmd.payload["enabled"] is False

    def test_show_system_menu(self) -> None:
        cmd = Command.show_system_menu("main")
        assert cmd.payload["op"] == "show_system_menu"

    def test_set_icon(self) -> None:
        pixels = b"\xff" * 16
        cmd = Command.set_icon("main", pixels, 2, 2)
        assert cmd.payload["op"] == "set_icon"
        assert cmd.payload["icon_data"] == pixels
        assert cmd.payload["width"] == 2
        assert cmd.payload["height"] == 2

    def test_set_resize_increments(self) -> None:
        cmd = Command.set_resize_increments("main", 8.0, 16.0)
        assert cmd.payload["op"] == "set_resize_increments"
        assert cmd.payload["width"] == 8.0

    def test_set_resize_increments_clear(self) -> None:
        cmd = Command.set_resize_increments("main", None, None)
        assert cmd.payload["width"] is None
        assert cmd.payload["height"] is None

    def test_allow_automatic_tabbing(self) -> None:
        cmd = Command.allow_automatic_tabbing(True)
        assert cmd.type == "system_op"
        assert cmd.payload["op"] == "allow_automatic_tabbing"
        assert cmd.payload["enabled"] is True

    def test_screenshot_window(self) -> None:
        cmd = Command.screenshot_window("main", "snap")
        assert cmd.payload["op"] == "screenshot"
        assert cmd.payload["tag"] == "snap"


class TestWindowQueries:
    def test_get_window_size(self) -> None:
        cmd = Command.get_window_size("main", "sz")
        assert cmd.type == "window_query"
        assert cmd.payload["op"] == "get_size"
        assert cmd.payload["tag"] == "sz"

    def test_get_window_position(self) -> None:
        cmd = Command.get_window_position("main", "pos")
        assert cmd.payload["op"] == "get_position"

    def test_get_mode(self) -> None:
        cmd = Command.get_mode("main", "m")
        assert cmd.payload["op"] == "get_mode"

    def test_get_scale_factor(self) -> None:
        cmd = Command.get_scale_factor("main", "sf")
        assert cmd.payload["op"] == "get_scale_factor"

    def test_is_maximized(self) -> None:
        cmd = Command.is_maximized("main", "mx")
        assert cmd.payload["op"] == "is_maximized"

    def test_is_minimized(self) -> None:
        cmd = Command.is_minimized("main", "mn")
        assert cmd.payload["op"] == "is_minimized"

    def test_raw_id(self) -> None:
        cmd = Command.raw_id("main", "rid")
        assert cmd.payload["op"] == "raw_id"

    def test_monitor_size(self) -> None:
        cmd = Command.monitor_size("main", "mon")
        assert cmd.payload["op"] == "monitor_size"

    def test_get_system_theme(self) -> None:
        cmd = Command.get_system_theme("theme")
        assert cmd.type == "system_query"
        assert cmd.payload["op"] == "get_system_theme"
        assert cmd.payload["tag"] == "theme"

    def test_get_system_info(self) -> None:
        cmd = Command.get_system_info("info")
        assert cmd.type == "system_query"
        assert cmd.payload["op"] == "get_system_info"
        assert cmd.payload["tag"] == "info"


class TestImageOps:
    def test_create_image(self) -> None:
        cmd = Command.create_image("logo", b"\x89PNG")
        assert cmd.type == "image_op"
        assert cmd.payload["op"] == "create_image"
        assert cmd.payload["handle"] == "logo"
        assert cmd.payload["data"] == b"\x89PNG"

    def test_create_image_rgba(self) -> None:
        pixels = b"\xff" * 16
        cmd = Command.create_image_rgba("tex", 2, 2, pixels)
        assert cmd.payload["op"] == "create_image"
        assert cmd.payload["width"] == 2
        assert cmd.payload["pixels"] == pixels

    def test_update_image(self) -> None:
        cmd = Command.update_image("logo", b"\x89PNG")
        assert cmd.payload["op"] == "update_image"

    def test_update_image_rgba(self) -> None:
        cmd = Command.update_image_rgba("tex", 2, 2, b"\xff" * 16)
        assert cmd.payload["op"] == "update_image"
        assert cmd.payload["width"] == 2

    def test_delete_image(self) -> None:
        cmd = Command.delete_image("logo")
        assert cmd.payload["op"] == "delete_image"
        assert cmd.payload["handle"] == "logo"


class TestExtension:
    def test_widget_command(self) -> None:
        cmd = Command.widget_command("chart", "set_data", {"values": [1, 2]})
        assert cmd.type == "extension_command"
        assert cmd.payload["node_id"] == "chart"
        assert cmd.payload["op"] == "set_data"
        assert cmd.payload["payload"] == {"values": [1, 2]}

    def test_widget_command_default_payload(self) -> None:
        cmd = Command.widget_command("chart", "reset")
        assert cmd.payload["payload"] == {}

    def test_widget_commands(self) -> None:
        cmds = [("a", "op1", {}), ("b", "op2", {"x": 1})]
        cmd = Command.widget_commands(cmds)
        assert cmd.type == "extension_commands"
        assert cmd.payload["commands"] == cmds


class TestAdvanceFrame:
    def test_advance_frame(self) -> None:
        cmd = Command.advance_frame(16)
        assert cmd.type == "advance_frame"
        assert cmd.payload["timestamp"] == 16


class TestFrozen:
    def test_command_is_frozen(self) -> None:
        cmd = Command.none()
        try:
            cmd.type = "bad"  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass
