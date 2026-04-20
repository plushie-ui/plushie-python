"""Command data types returned from ``update()``.

Commands describe side effects that the runtime executes after ``update``
returns.  They are pure data: inspectable, testable, serializable.
Nothing executes inside ``update``.

The lifecycle is: ``update`` returns ``(model, command)``, the runtime
executes the command, then calls ``view`` with the new model.  For no
side effect, return the model alone or use ``Command.none()``.

Categories:

- **Async/lifecycle**: ``task``, ``stream``, ``cancel``, ``done``,
  ``send_after``, ``exit``, ``batch``, ``none``
- **Widget commands**: ``focus``, ``select_all``, ``select_range``,
  ``move_cursor_to``, ``move_cursor_to_front``,
  ``move_cursor_to_end``, ``scroll_to``,
  ``snap_to``, ``snap_to_end``, ``scroll_by``,
  ``pane_split``, ``pane_close``, ``pane_swap``, ``pane_maximize``,
  ``pane_restore``, ``widget_command``, ``widget_batch``
- **Widget ops** (global): ``focus_next``, ``focus_previous``,
  ``announce``, ``load_font``, ``tree_hash_query``,
  ``find_focused_query``, ``list_images_query``, ``clear_images``
- **Window ops**: ``close_window``, ``resize_window``, ``move_window``,
  ``maximize_window``, ``minimize_window``, ``set_window_mode``,
  ``toggle_maximize``, ``toggle_decorations``, ``focus_window``,
  ``set_window_level``, ``drag_window``, ``drag_resize_window``,
  ``request_attention``, ``set_resizable``, ``set_min_size``,
  ``set_max_size``, ``enable_mouse_passthrough``,
  ``disable_mouse_passthrough``, ``show_system_menu``, ``set_icon``,
  ``set_resize_increments``, ``allow_automatic_tabbing``,
  ``screenshot_window``, ``window_size``, ``window_position``,
  ``window_mode``, ``scale_factor``, ``is_maximized``,
  ``is_minimized``, ``raw_id``, ``monitor_size``,
  ``system_theme``, ``system_info``
- **Image ops**: ``create_image``, ``create_image_rgba``,
  ``update_image``, ``update_image_rgba``, ``delete_image``
- **Animation**: ``advance_frame``

Usage::

    from plushie.commands import Command

    def update(model, event):
        match event:
            case Click(id="save"):
                return replace(model, saving=True), Command.task(save_fn, "save")
            case AsyncResult(tag="save"):
                return replace(model, saving=False)
            case _:
                return model
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def _parse_target(widget_id: str) -> tuple[str | None, str]:
    """Parse a window-qualified widget path.

    Supports ``"window_id#widget_path"`` syntax where the ``#``
    separator splits the window scope from the widget path.

    Returns ``(window_id, target)`` where window_id is ``None``
    when no qualifier is present.
    """
    if "#" in widget_id:
        parts = widget_id.split("#", 1)
        if parts[0]:
            return parts[0], parts[1]
    return None, widget_id


@dataclass(frozen=True, slots=True)
class Command:
    """A side-effect descriptor returned from ``update()``.

    Commands are pure data.  The runtime interprets them after ``update``
    returns.  Use the static factory methods to construct commands -
    never instantiate directly in application code.

    Attributes:
        type: The command category (e.g. ``"task"``, ``"command"``,
            ``"window_op"``).
        payload: A dict of parameters specific to the command type.
    """

    type: str
    payload: dict[str, Any]

    # ------------------------------------------------------------------
    # Async / lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def none() -> Command:
        """No-op command.  Returned implicitly when ``update`` returns a bare model."""
        return Command(type="none", payload={})

    @staticmethod
    def task(fn: Callable[[], Any], tag: str) -> Command:
        """Run *fn* in a background thread.  Result arrives as ``AsyncResult(tag=tag)``.

        Only one task per tag can be active. A new task with the same
        tag cancels the running one. Use unique tags for concurrency.
        """
        return Command(type="task", payload={"fn": fn, "tag": tag})

    @staticmethod
    def stream(fn: Callable[[Callable[[Any], None]], Any], tag: str) -> Command:
        """Run *fn* with an emit callback.  Each emit produces ``StreamChunk(tag=tag)``.

        Only one stream per tag can be active. A new stream with the
        same tag cancels the running one. Use unique tags for concurrency.
        """
        return Command(type="stream", payload={"fn": fn, "tag": tag})

    @staticmethod
    def cancel(tag: str) -> Command:
        """Cancel a running task or stream identified by *tag*."""
        return Command(type="cancel", payload={"tag": tag})

    @staticmethod
    def dispatch(value: Any, mapper: Callable[[Any], Any]) -> Command:
        """Deliver an already-resolved *value* through ``update`` via *mapper*."""
        return Command(type="dispatch", payload={"value": value, "mapper": mapper})

    @staticmethod
    def send_after(delay_ms: int, event: Any) -> Command:
        """Deliver *event* to ``update`` after *delay_ms* milliseconds.

        If a timer with the same event is already pending, the previous
        timer is canceled and replaced. This prevents duplicate
        deliveries when ``send_after`` is called repeatedly.
        """
        return Command(type="send_after", payload={"delay": delay_ms, "event": event})

    @staticmethod
    def exit() -> Command:
        """Shut down the runtime and close all windows."""
        return Command(type="exit", payload={})

    @staticmethod
    def batch(commands: list[Command]) -> Command:
        """Execute multiple commands.  Commands in the list run in order."""
        return Command(type="batch", payload={"commands": commands})

    # ------------------------------------------------------------------
    # Widget commands (targeted, unified wire format)
    # ------------------------------------------------------------------

    @staticmethod
    def focus(widget_id: str) -> Command:
        """Move keyboard focus to *widget_id*.

        Supports window-qualified paths: ``"main#email"`` targets
        widget ``"email"`` in window ``"main"``. Canvas elements can
        be focused via scoped paths: ``"main#canvas/element"``.
        """
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {"family": "focus", "id": target}
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def focus_element(canvas_id: str, element_id: str) -> Command:
        """Focus a canvas element by setting focus on the canvas widget.

        The canvas widget receives focus and the renderer tracks the
        internal element selection. Use ``"window_id#canvas_id/element_id"``
        for window-qualified canvas elements.
        """
        target = f"{canvas_id}/{element_id}"
        return Command(type="command", payload={"family": "focus", "id": target})

    @staticmethod
    def select_all(widget_id: str) -> Command:
        """Select all text in *widget_id*. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {"family": "select_all", "id": target}
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def select_range(widget_id: str, start_pos: int, end_pos: int) -> Command:
        """Select text from *start_pos* to *end_pos* in *widget_id*. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {
            "family": "select_range",
            "id": target,
            "value": {"start_pos": start_pos, "end_pos": end_pos},
        }
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def move_cursor_to(widget_id: str, position: int) -> Command:
        """Move the text cursor to *position* in *widget_id*. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {
            "family": "move_cursor_to",
            "id": target,
            "value": position,
        }
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def move_cursor_to_front(widget_id: str) -> Command:
        """Move the text cursor to the beginning of *widget_id*. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {"family": "move_cursor_to_front", "id": target}
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def move_cursor_to_end(widget_id: str) -> Command:
        """Move the text cursor to the end of *widget_id*. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {"family": "move_cursor_to_end", "id": target}
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def scroll_to(widget_id: str, x: float, y: float) -> Command:
        """Scroll *widget_id* to absolute (*x*, *y*) offset. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {
            "family": "scroll_to",
            "id": target,
            "value": {"x": x, "y": y},
        }
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def snap_to(widget_id: str, x: float = 0.0, y: float = 0.0) -> Command:
        """Snap *widget_id* to absolute offset instantly. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {
            "family": "snap_to",
            "id": target,
            "value": {"x": x, "y": y},
        }
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def snap_to_end(widget_id: str) -> Command:
        """Snap *widget_id* to the end of its content. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {"family": "snap_to_end", "id": target}
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def scroll_by(widget_id: str, x: float = 0.0, y: float = 0.0) -> Command:
        """Scroll *widget_id* by a relative offset. Supports ``"window#widget"``."""
        window_id, target = _parse_target(widget_id)
        payload: dict[str, Any] = {
            "family": "scroll_by",
            "id": target,
            "value": {"x": x, "y": y},
        }
        if window_id is not None:
            payload["window_id"] = window_id
        return Command(type="command", payload=payload)

    @staticmethod
    def pane_split(
        pane_grid_id: str,
        pane_id: Any,
        axis: str,
        new_pane_id: Any,
    ) -> Command:
        """Split a pane along *axis* (``"horizontal"`` or ``"vertical"``)."""
        return Command(
            type="command",
            payload={
                "family": "pane_split",
                "id": pane_grid_id,
                "value": {"pane": pane_id, "axis": axis, "new_pane_id": new_pane_id},
            },
        )

    @staticmethod
    def pane_close(pane_grid_id: str, pane_id: Any) -> Command:
        """Close a pane in the pane grid."""
        return Command(
            type="command",
            payload={
                "family": "pane_close",
                "id": pane_grid_id,
                "value": {"pane": pane_id},
            },
        )

    @staticmethod
    def pane_swap(pane_grid_id: str, pane_a: Any, pane_b: Any) -> Command:
        """Swap two panes in the pane grid."""
        return Command(
            type="command",
            payload={
                "family": "pane_swap",
                "id": pane_grid_id,
                "value": {"a": pane_a, "b": pane_b},
            },
        )

    @staticmethod
    def pane_maximize(pane_grid_id: str, pane_id: Any) -> Command:
        """Maximize a single pane to fill the entire pane grid."""
        return Command(
            type="command",
            payload={
                "family": "pane_maximize",
                "id": pane_grid_id,
                "value": {"pane": pane_id},
            },
        )

    @staticmethod
    def pane_restore(pane_grid_id: str) -> Command:
        """Restore all panes from maximized state."""
        return Command(
            type="command",
            payload={"family": "pane_restore", "id": pane_grid_id},
        )

    # ------------------------------------------------------------------
    # Widget ops (global, not targeted at a specific widget)
    # ------------------------------------------------------------------

    @staticmethod
    def focus_next() -> Command:
        """Move focus to the next focusable widget in tab order."""
        return Command(type="widget_op", payload={"op": "focus_next"})

    @staticmethod
    def focus_previous() -> Command:
        """Move focus to the previous focusable widget in tab order."""
        return Command(type="widget_op", payload={"op": "focus_previous"})

    @staticmethod
    def focus_next_within(scope: str) -> Command:
        """Move focus to the next focusable widget within *scope*.

        Only widgets that are descendants of the scope widget are
        considered; focus wraps at the subtree boundary. Useful for
        menus, pane grids, and other keyboard containers that want a
        bounded Tab cycle.
        """
        return Command(
            type="widget_op",
            payload={"op": "focus_next_within", "scope": scope},
        )

    @staticmethod
    def focus_previous_within(scope: str) -> Command:
        """Move focus to the previous focusable widget within *scope*.

        See :py:meth:`focus_next_within` for semantics.
        """
        return Command(
            type="widget_op",
            payload={"op": "focus_previous_within", "scope": scope},
        )

    @staticmethod
    def close_window(window_id: str) -> Command:
        """Close the window identified by *window_id*."""
        return Command(
            type="window_op",
            payload={"op": "close", "window_id": window_id},
        )

    @staticmethod
    def announce(text: str, politeness: str = "polite") -> Command:
        """Announce *text* to screen readers via the accessibility system.

        ``politeness`` controls how assistive technology delivers the
        announcement. ``"polite"`` (the default) waits for a gap in the
        current announcement and is correct for most toast-style
        feedback. ``"assertive"`` interrupts the current announcement
        and should be reserved for urgent context the user must hear
        immediately.
        """
        if politeness not in ("polite", "assertive"):
            raise ValueError(
                f"politeness must be 'polite' or 'assertive', got {politeness!r}"
            )
        return Command(
            type="widget_op",
            payload={"op": "announce", "text": text, "politeness": politeness},
        )

    @staticmethod
    def load_font(family: str, data: bytes) -> Command:
        """Load a font at runtime from raw TrueType or OpenType binary data.

        Args:
            family: Font family name the app will use to reference the
                loaded font (e.g. ``"Inter"``).
            data: Raw TrueType or OpenType binary font data.
        """
        return Command(
            type="widget_op",
            payload={"op": "load_font", "family": family, "data": data},
        )

    @staticmethod
    def tree_hash_query(tag: str) -> Command:
        """Compute a SHA-256 hash of the renderer's current tree.  Result arrives as a system event."""
        return Command(type="widget_op", payload={"op": "tree_hash", "tag": tag})

    @staticmethod
    def find_focused_query(tag: str) -> Command:
        """Query which widget currently has keyboard focus.  Result arrives as a system event."""
        return Command(type="widget_op", payload={"op": "find_focused", "tag": tag})

    @staticmethod
    def list_images_query(tag: str) -> Command:
        """List all registered image handles.  Result arrives as a system event."""
        return Command(type="widget_op", payload={"op": "list_images", "tag": tag})

    @staticmethod
    def clear_images() -> Command:
        """Delete all registered in-memory images."""
        return Command(type="widget_op", payload={"op": "clear_images"})

    # ------------------------------------------------------------------
    # Window ops
    # ------------------------------------------------------------------

    @staticmethod
    def resize_window(window_id: str, width: float, height: float) -> Command:
        """Resize *window_id* to the given dimensions in logical pixels."""
        return Command(
            type="window_op",
            payload={
                "op": "resize",
                "window_id": window_id,
                "width": width,
                "height": height,
            },
        )

    @staticmethod
    def move_window(window_id: str, x: float, y: float) -> Command:
        """Move *window_id* to screen position (*x*, *y*) in logical pixels."""
        return Command(
            type="window_op",
            payload={"op": "move", "window_id": window_id, "x": x, "y": y},
        )

    @staticmethod
    def maximize_window(window_id: str, maximized: bool = True) -> Command:
        """Set whether *window_id* is maximized."""
        return Command(
            type="window_op",
            payload={"op": "maximize", "window_id": window_id, "maximized": maximized},
        )

    @staticmethod
    def minimize_window(window_id: str, minimized: bool = True) -> Command:
        """Set whether *window_id* is minimized."""
        return Command(
            type="window_op",
            payload={"op": "minimize", "window_id": window_id, "minimized": minimized},
        )

    @staticmethod
    def set_window_mode(window_id: str, mode: str) -> Command:
        """Set window mode (e.g. ``"windowed"``, ``"fullscreen"``)."""
        return Command(
            type="window_op",
            payload={"op": "set_mode", "window_id": window_id, "mode": mode},
        )

    @staticmethod
    def toggle_maximize(window_id: str) -> Command:
        """Toggle *window_id* between maximized and restored state."""
        return Command(
            type="window_op",
            payload={"op": "toggle_maximize", "window_id": window_id},
        )

    @staticmethod
    def toggle_decorations(window_id: str) -> Command:
        """Toggle window decorations (title bar, borders) on *window_id*."""
        return Command(
            type="window_op",
            payload={"op": "toggle_decorations", "window_id": window_id},
        )

    @staticmethod
    def focus_window(window_id: str) -> Command:
        """Give keyboard/input focus to *window_id*, bringing it to the front."""
        return Command(
            type="window_op",
            payload={"op": "gain_focus", "window_id": window_id},
        )

    @staticmethod
    def set_window_level(window_id: str, level: str) -> Command:
        """Set window stacking level (``"normal"``, ``"always_on_top"``, ``"always_on_bottom"``)."""
        return Command(
            type="window_op",
            payload={"op": "set_level", "window_id": window_id, "level": level},
        )

    @staticmethod
    def drag_window(window_id: str) -> Command:
        """Initiate a window drag operation on *window_id*."""
        return Command(
            type="window_op",
            payload={"op": "drag", "window_id": window_id},
        )

    @staticmethod
    def drag_resize_window(window_id: str, direction: str) -> Command:
        """Initiate a drag-resize from the given edge/corner *direction*."""
        return Command(
            type="window_op",
            payload={
                "op": "drag_resize",
                "window_id": window_id,
                "direction": direction,
            },
        )

    @staticmethod
    def request_attention(window_id: str, urgency: str | None = None) -> Command:
        """Flash the taskbar/dock icon.  *urgency* is ``"informational"`` or ``"critical"``."""
        return Command(
            type="window_op",
            payload={
                "op": "request_attention",
                "window_id": window_id,
                "urgency": urgency,
            },
        )

    @staticmethod
    def set_resizable(window_id: str, resizable: bool) -> Command:
        """Set whether *window_id* can be resized by the user."""
        return Command(
            type="window_op",
            payload={
                "op": "set_resizable",
                "window_id": window_id,
                "resizable": resizable,
            },
        )

    @staticmethod
    def set_min_size(window_id: str, width: float, height: float) -> Command:
        """Set the minimum allowed size for *window_id* in logical pixels."""
        return Command(
            type="window_op",
            payload={
                "op": "set_min_size",
                "window_id": window_id,
                "width": width,
                "height": height,
            },
        )

    @staticmethod
    def set_max_size(window_id: str, width: float, height: float) -> Command:
        """Set the maximum allowed size for *window_id* in logical pixels."""
        return Command(
            type="window_op",
            payload={
                "op": "set_max_size",
                "window_id": window_id,
                "width": width,
                "height": height,
            },
        )

    @staticmethod
    def enable_mouse_passthrough(window_id: str) -> Command:
        """Enable mouse passthrough on *window_id* (clicks pass through)."""
        return Command(
            type="window_op",
            payload={
                "op": "mouse_passthrough",
                "window_id": window_id,
                "enabled": True,
            },
        )

    @staticmethod
    def disable_mouse_passthrough(window_id: str) -> Command:
        """Disable mouse passthrough on *window_id*."""
        return Command(
            type="window_op",
            payload={
                "op": "mouse_passthrough",
                "window_id": window_id,
                "enabled": False,
            },
        )

    @staticmethod
    def show_system_menu(window_id: str) -> Command:
        """Show the native system menu (window controls) for *window_id*."""
        return Command(
            type="window_op",
            payload={"op": "show_system_menu", "window_id": window_id},
        )

    @staticmethod
    def set_icon(window_id: str, rgba_data: bytes, width: int, height: int) -> Command:
        """Set *window_id*'s icon from raw RGBA pixel data (width * height * 4 bytes)."""
        return Command(
            type="window_op",
            payload={
                "op": "set_icon",
                "window_id": window_id,
                "icon_data": rgba_data,
                "width": width,
                "height": height,
            },
        )

    @staticmethod
    def set_resize_increments(
        window_id: str, width: float | None, height: float | None
    ) -> Command:
        """Set resize increment size.  Pass ``None`` for both to clear."""
        return Command(
            type="window_op",
            payload={
                "op": "set_resize_increments",
                "window_id": window_id,
                "width": width,
                "height": height,
            },
        )

    @staticmethod
    def allow_automatic_tabbing(enabled: bool) -> Command:
        """Set whether the system can automatically organize windows into tabs (macOS)."""
        return Command(
            type="system_op",
            payload={
                "op": "allow_automatic_tabbing",
                "enabled": enabled,
            },
        )

    @staticmethod
    def screenshot_window(window_id: str, tag: str) -> Command:
        """Capture a screenshot of *window_id*.  Result arrives as a tagged system event."""
        return Command(
            type="window_op",
            payload={"op": "screenshot", "window_id": window_id, "tag": tag},
        )

    # ------------------------------------------------------------------
    # Window queries
    # ------------------------------------------------------------------

    @staticmethod
    def window_size(window_id: str, tag: str) -> Command:
        """Query the size of *window_id*.  Result arrives as a system event."""
        return Command(
            type="window_query",
            payload={"op": "get_size", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def window_position(window_id: str, tag: str) -> Command:
        """Query the position of *window_id*.  Result arrives as a system event."""
        return Command(
            type="window_query",
            payload={"op": "get_position", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def window_mode(window_id: str, tag: str) -> Command:
        """Query the current window mode.  Result arrives as a system event."""
        return Command(
            type="window_query",
            payload={"op": "get_mode", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def scale_factor(window_id: str, tag: str) -> Command:
        """Query the DPI scale factor.  Result arrives as a system event."""
        return Command(
            type="window_query",
            payload={"op": "get_scale_factor", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def is_maximized(window_id: str, tag: str) -> Command:
        """Query whether *window_id* is maximized.  Result arrives as a system event."""
        return Command(
            type="window_query",
            payload={"op": "is_maximized", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def is_minimized(window_id: str, tag: str) -> Command:
        """Query whether *window_id* is minimized.  Result arrives as a system event."""
        return Command(
            type="window_query",
            payload={"op": "is_minimized", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def raw_id(window_id: str, tag: str) -> Command:
        """Query the raw platform window ID.  Result arrives as a system event."""
        return Command(
            type="window_query",
            payload={"op": "raw_id", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def monitor_size(window_id: str, tag: str) -> Command:
        """Query the monitor size for the display containing *window_id*."""
        return Command(
            type="window_query",
            payload={"op": "monitor_size", "window_id": window_id, "tag": tag},
        )

    @staticmethod
    def system_theme(tag: str) -> Command:
        """Query the OS light/dark theme preference.  Result arrives as a system event."""
        return Command(
            type="system_query", payload={"op": "get_system_theme", "tag": tag}
        )

    @staticmethod
    def system_info(tag: str) -> Command:
        """Query system information (OS, CPU, memory, graphics)."""
        return Command(
            type="system_query", payload={"op": "get_system_info", "tag": tag}
        )

    # ------------------------------------------------------------------
    # Image ops
    # ------------------------------------------------------------------

    @staticmethod
    def create_image(handle: str, data: bytes) -> Command:
        """Register an image from encoded data (PNG, JPEG, etc.) under *handle*."""
        return Command(
            type="image_op",
            payload={"op": "create_image", "handle": handle, "data": data},
        )

    @staticmethod
    def create_image_rgba(
        handle: str, width: int, height: int, pixels: bytes
    ) -> Command:
        """Register an image from raw RGBA pixel data under *handle*.

        *pixels* must be exactly ``width * height * 4`` bytes.
        """
        expected = width * height * 4
        if len(pixels) != expected:
            raise ValueError(
                f"pixel buffer has {len(pixels)} bytes, expected {expected} "
                f"(width={width} height={height} channels=4)"
            )
        return Command(
            type="image_op",
            payload={
                "op": "create_image",
                "handle": handle,
                "width": width,
                "height": height,
                "pixels": pixels,
            },
        )

    @staticmethod
    def update_image(handle: str, data: bytes) -> Command:
        """Update an existing image *handle* with new encoded data."""
        return Command(
            type="image_op",
            payload={"op": "update_image", "handle": handle, "data": data},
        )

    @staticmethod
    def update_image_rgba(
        handle: str, width: int, height: int, pixels: bytes
    ) -> Command:
        """Update an existing image *handle* with new raw RGBA pixel data.

        *pixels* must be exactly ``width * height * 4`` bytes.
        """
        expected = width * height * 4
        if len(pixels) != expected:
            raise ValueError(
                f"pixel buffer has {len(pixels)} bytes, expected {expected} "
                f"(width={width} height={height} channels=4)"
            )
        return Command(
            type="image_op",
            payload={
                "op": "update_image",
                "handle": handle,
                "width": width,
                "height": height,
                "pixels": pixels,
            },
        )

    @staticmethod
    def delete_image(handle: str) -> Command:
        """Delete a previously registered image by its *handle*."""
        return Command(
            type="image_op",
            payload={"op": "delete_image", "handle": handle},
        )

    # ------------------------------------------------------------------
    # Widget commands (native widget extensions)
    # ------------------------------------------------------------------

    @staticmethod
    def widget_command(widget_id: str, family: str, value: Any = None) -> Command:
        """Send a command to a widget by ID.

        Uses the unified wire format matching events:
        ``{type: "command", id, family, value}``.
        """
        payload: dict[str, Any] = {"id": widget_id, "family": family}
        if value is not None:
            payload["value"] = value
        return Command(type="command", payload=payload)

    @staticmethod
    def widget_batch(
        commands: list[tuple[str, str, Any]],
    ) -> Command:
        """Send a batch of widget-targeted commands processed in one cycle.

        Each item in ``commands`` should be a ``(id, family, value)`` tuple.
        """
        wire_cmds: list[dict[str, Any]] = []
        for cid, family, value in commands:
            cmd: dict[str, Any] = {"id": cid, "family": family}
            if value is not None:
                cmd["value"] = value
            wire_cmds.append(cmd)
        return Command(
            type="commands",
            payload={"commands": wire_cmds},
        )

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    @staticmethod
    def advance_frame(timestamp: int) -> Command:
        """Advance the animation clock by one frame (test/headless only).

        *timestamp* is monotonic milliseconds.
        """
        return Command(type="advance_frame", payload={"timestamp": timestamp})


__all__ = ["Command"]
