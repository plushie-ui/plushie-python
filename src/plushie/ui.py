"""Widget builder functions for plushie UI trees.

Every function returns a plain dict with the wire protocol's node shape::

    {"id": ..., "type": ..., "props": {...}, "children": [...]}

Containers accept children as ``*args`` and options as ``**kwargs``.
Named containers take ``id`` as the first positional argument.
Interactive leaves take ``id`` as the first positional argument.
Display widgets with auto-id sugar accept one-arg (content only) or
two-arg (id + content) forms via ``@overload``.

Children lists are flattened one level (generators produce lists)
and ``None`` values are filtered out.
"""

from __future__ import annotations

from typing import Any, overload

# ---------------------------------------------------------------------------
# Node type alias
# ---------------------------------------------------------------------------

type Node = dict[str, Any]
"""A UI tree node: ``{"id": ..., "type": ..., "props": {}, "children": []}``."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flatten_children(children: tuple[Any, ...]) -> list[Node]:
    """Flatten one level of nesting and filter out None values."""
    result: list[Node] = []
    for child in children:
        if child is None:
            continue
        if isinstance(child, dict):
            result.append(child)
        elif isinstance(child, (list, tuple)):
            for item in child:
                if item is not None:
                    result.append(item)
        else:
            # generators and other iterables
            try:
                for item in child:
                    if item is not None:
                        result.append(item)
            except TypeError:
                result.append(child)
    return result


def _node(
    id: str | None,
    type_name: str,
    props: dict[str, Any],
    children: list[Node] | None = None,
) -> Node:
    """Build a node dict, stripping None-valued props."""
    clean_props = {k: v for k, v in props.items() if v is not None}
    return {
        "id": id,
        "type": type_name,
        "props": clean_props,
        "children": children if children is not None else [],
    }


def _named_container(type_name: str, id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Build a named container node (id-first positional)."""
    return _node(id, type_name, kwargs, _flatten_children(children))


def _anon_container(type_name: str, /, *children: Any, **kwargs: Any) -> Node:
    """Build an anonymous container node (no positional id)."""
    id = kwargs.pop("id", None)
    return _node(id, type_name, kwargs, _flatten_children(children))


# ---------------------------------------------------------------------------
# Named containers (12) -- id is first positional arg, creates scope
# ---------------------------------------------------------------------------


def window(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Window container.

    Args:
        id: Window identifier.
        *children: Child widgets.
        **kwargs: Window props (title, size, width, height, position,
            min_size, max_size, maximized, fullscreen, visible, resizable,
            closeable, minimizable, decorations, transparent, blur, level,
            exit_on_close_request, scale_factor, theme).
    """
    return _named_container("window", id, *children, **kwargs)


def container(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Container layout -- wraps children with padding, sizing, and styling.

    Args:
        id: Container identifier.
        *children: Child widgets.
        **kwargs: Container props (padding, width, height, max_width,
            max_height, center, clip, align_x, align_y, background,
            color, border, shadow, style, a11y).
    """
    return _named_container("container", id, *children, **kwargs)


def scrollable(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Scrollable container -- wraps children in a scrollable viewport.

    Args:
        id: Scrollable identifier (for programmatic scroll control).
        *children: Child widgets.
        **kwargs: Scrollable props (width, height, direction, spacing,
            scrollbar_width, scrollbar_margin, scroller_width,
            scrollbar_color, scroller_color, anchor, on_scroll,
            auto_scroll, a11y).
    """
    return _named_container("scrollable", id, *children, **kwargs)


def overlay(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Overlay container -- renders children on top of each other.

    Args:
        id: Overlay identifier.
        *children: Child widgets.
        **kwargs: Overlay props.
    """
    return _named_container("overlay", id, *children, **kwargs)


def pin(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Pin container -- positions children at absolute coordinates.

    Args:
        id: Pin identifier.
        *children: Child widgets.
        **kwargs: Pin props.
    """
    return _named_container("pin", id, *children, **kwargs)


def floating(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Floating container -- positions children relative to the viewport.

    Args:
        id: Floating identifier.
        *children: Child widgets.
        **kwargs: Floating props.
    """
    return _named_container("float", id, *children, **kwargs)


def pointer_area(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Pointer area container -- captures pointer events for children.

    Args:
        id: Pointer area identifier.
        *children: Child widgets.
        **kwargs: Pointer area props.
    """
    return _named_container("pointer_area", id, *children, **kwargs)


def sensor(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Sensor container -- reports size/position changes.

    Args:
        id: Sensor identifier.
        *children: Child widgets.
        **kwargs: Sensor props.
    """
    return _named_container("sensor", id, *children, **kwargs)


def themer(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Themer container -- applies a local theme to children.

    Args:
        id: Themer identifier.
        *children: Child widgets.
        **kwargs: Themer props (theme).
    """
    return _named_container("themer", id, *children, **kwargs)


def tooltip(id: str, tip: str, /, *children: Any, **kwargs: Any) -> Node:
    """Tooltip container -- shows a popup tip on hover.

    Args:
        id: Tooltip identifier.
        tip: Tooltip text.
        *children: Child widgets.
        **kwargs: Tooltip props (position, gap, padding,
            snap_within_viewport, delay, style, a11y).
    """
    return _node(id, "tooltip", {"tip": tip, **kwargs}, _flatten_children(children))


def pane_grid(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Pane grid container -- resizable split panes.

    Args:
        id: Pane grid identifier.
        *children: Child widgets.
        **kwargs: Pane grid props.
    """
    return _named_container("pane_grid", id, *children, **kwargs)


def table(id: str, /, *children: Any, **kwargs: Any) -> Node:
    """Table container -- tabular layout with sortable columns.

    Args:
        id: Table identifier.
        *children: Child widgets.
        **kwargs: Table props.
    """
    return _named_container("table", id, *children, **kwargs)


# ---------------------------------------------------------------------------
# Anonymous containers (6) -- no positional id, keyword id= optional
# ---------------------------------------------------------------------------


def column(*children: Any, **kwargs: Any) -> Node:
    """Column layout -- arranges children vertically.

    Args:
        *children: Child widgets.
        **kwargs: Column props (spacing, padding, width, height,
            max_width, align_x, clip, wrap, a11y). Optional ``id=``.
    """
    return _anon_container("column", *children, **kwargs)


def row(*children: Any, **kwargs: Any) -> Node:
    """Row layout -- arranges children horizontally.

    Args:
        *children: Child widgets.
        **kwargs: Row props (spacing, padding, width, height,
            align_y, max_width, clip, wrap, a11y). Optional ``id=``.
    """
    return _anon_container("row", *children, **kwargs)


def stack(*children: Any, **kwargs: Any) -> Node:
    """Stack layout -- overlays children on top of each other.

    Args:
        *children: Child widgets.
        **kwargs: Stack props. Optional ``id=``.
    """
    return _anon_container("stack", *children, **kwargs)


def grid(*children: Any, **kwargs: Any) -> Node:
    """Grid layout -- arranges children in a grid.

    Args:
        *children: Child widgets.
        **kwargs: Grid props. Optional ``id=``.
    """
    return _anon_container("grid", *children, **kwargs)


def keyed_column(*children: Any, **kwargs: Any) -> Node:
    """Keyed column -- like column but children are matched by key.

    Args:
        *children: Child widgets.
        **kwargs: Keyed column props. Optional ``id=``.
    """
    return _anon_container("keyed_column", *children, **kwargs)


def responsive(*children: Any, **kwargs: Any) -> Node:
    """Responsive container -- adapts layout to available space.

    Args:
        *children: Child widgets.
        **kwargs: Responsive props. Optional ``id=``.
    """
    return _anon_container("responsive", *children, **kwargs)


# ---------------------------------------------------------------------------
# Layout primitives (2) -- auto-id
# ---------------------------------------------------------------------------


def space(**kwargs: Any) -> Node:
    """Empty space -- invisible spacer widget.

    Args:
        **kwargs: Space props (width, height, a11y).
    """
    return _node(None, "space", kwargs)


def rule(**kwargs: Any) -> Node:
    """Horizontal or vertical rule (divider line).

    Args:
        **kwargs: Rule props (height, width, direction, style, a11y).
    """
    return _node(None, "rule", kwargs)


# ---------------------------------------------------------------------------
# Interactive leaf widgets (10) -- id is first positional arg
# ---------------------------------------------------------------------------


def button(id: str, label: str, /, **kwargs: Any) -> Node:
    """Clickable button.

    Args:
        id: Button identifier.
        label: Button text label.
        **kwargs: Button props (style, width, height, padding, clip,
            disabled, enabled, a11y).
    """
    return _node(id, "button", {"label": label, **kwargs})


def text_input(id: str, value: str, /, **kwargs: Any) -> Node:
    """Single-line text input field.

    Args:
        id: Text input identifier.
        value: Current text content.
        **kwargs: Text input props (placeholder, padding, width, size,
            font, line_height, align_x, on_submit, on_paste, secure,
            ime_purpose, style, icon, placeholder_color, selection_color,
            a11y).
    """
    return _node(id, "text_input", {"value": value, **kwargs})


def checkbox(id: str, checked: bool, /, **kwargs: Any) -> Node:
    """Toggleable checkbox.

    Args:
        id: Checkbox identifier.
        checked: Whether the checkbox is checked.
        **kwargs: Checkbox props (label, spacing, width, size, text_size,
            font, line_height, shaping, wrapping, style, icon, disabled,
            a11y).
    """
    return _node(id, "checkbox", {"checked": checked, **kwargs})


def toggler(id: str, is_toggled: bool, /, **kwargs: Any) -> Node:
    """On/off toggle switch.

    Args:
        id: Toggler identifier.
        is_toggled: Whether the toggler is on.
        **kwargs: Toggler props (label, spacing, width, size, text_size,
            font, line_height, shaping, wrapping, text_alignment, style,
            disabled, a11y).
    """
    return _node(id, "toggler", {"is_toggled": is_toggled, **kwargs})


def radio(id: str, value: str, selected: str | None, /, **kwargs: Any) -> Node:
    """Radio button -- one-of-many selection.

    Args:
        id: Radio identifier.
        value: The value this radio represents.
        selected: The currently selected value in the group (or None).
        **kwargs: Radio props (label, group, spacing, width, size,
            text_size, font, line_height, shaping, wrapping, style, a11y).
    """
    return _node(id, "radio", {"value": value, "selected": selected, **kwargs})


def slider(
    id: str,
    range: tuple[float, float],
    value: float,
    /,
    **kwargs: Any,
) -> Node:
    """Horizontal range slider.

    Args:
        id: Slider identifier.
        range: ``(min, max)`` tuple.
        value: Current slider value.
        **kwargs: Slider props (step, width, height, default, shift_step,
            circular_handle, rail_color, rail_width, style, label,
            event_rate, a11y).
    """
    return _node(id, "slider", {"range": list(range), "value": value, **kwargs})


def vertical_slider(
    id: str,
    range: tuple[float, float],
    value: float,
    /,
    **kwargs: Any,
) -> Node:
    """Vertical range slider.

    Args:
        id: Vertical slider identifier.
        range: ``(min, max)`` tuple.
        value: Current slider value.
        **kwargs: Vertical slider props (step, height, default,
            shift_step, rail_color, rail_width, style, label, a11y).
    """
    return _node(
        id,
        "vertical_slider",
        {"range": list(range), "value": value, **kwargs},
    )


def pick_list(
    id: str,
    options: list[str],
    selected: str | None,
    /,
    **kwargs: Any,
) -> Node:
    """Dropdown selection.

    Args:
        id: Pick list identifier.
        options: Available choices.
        selected: Currently selected value (or None).
        **kwargs: Pick list props (placeholder, width, padding, text_size,
            font, line_height, menu_height, shaping, handle, ellipsis,
            menu_style, style, a11y).
    """
    return _node(
        id,
        "pick_list",
        {"options": options, "selected": selected, **kwargs},
    )


def combo_box(
    id: str,
    options: list[str],
    value: str | None,
    /,
    **kwargs: Any,
) -> Node:
    """Searchable dropdown with free-form text input.

    Args:
        id: Combo box identifier.
        options: Available choices.
        value: Current text value (or None).
        **kwargs: Combo box props (placeholder, width, padding, size,
            font, line_height, menu_height, icon, on_option_hovered,
            shaping, ellipsis, menu_style, style, a11y).
    """
    return _node(id, "combo_box", {"options": options, "selected": value, **kwargs})


def text_editor(id: str, content: str, /, **kwargs: Any) -> Node:
    """Multi-line text editor.

    Args:
        id: Text editor identifier.
        content: Initial text content.
        **kwargs: Text editor props (placeholder, width, height,
            min_height, max_height, font, size, line_height, padding,
            wrapping, ime_purpose, highlight_syntax, highlight_theme,
            style, key_bindings, placeholder_color, selection_color, a11y).
    """
    return _node(id, "text_editor", {"content": content, **kwargs})


# ---------------------------------------------------------------------------
# Display with auto-id sugar (3) -- @overload for 1-arg vs 2-arg forms
# ---------------------------------------------------------------------------


@overload
def text(content: str, /, **kwargs: Any) -> Node:
    """Create a text widget with auto-generated ID."""
    ...


@overload
def text(id: str, content: str, /, **kwargs: Any) -> Node:
    """Create a text widget with an explicit ID."""
    ...


def text(*args: Any, **kwargs: Any) -> Node:
    """Text display widget.

    One-arg form auto-generates an ID::

        text("Hello, world!")

    Two-arg form takes explicit ID::

        text("greeting", "Hello, world!")

    Args:
        content: Text string to display.
        **kwargs: Text props (size, color, font, width, height,
            line_height, align_x, align_y, wrapping, ellipsis,
            shaping, style, a11y).
    """
    if len(args) == 1:
        return _node(None, "text", {"content": args[0], **kwargs})
    elif len(args) == 2:
        return _node(args[0], "text", {"content": args[1], **kwargs})
    else:
        msg = f"text() takes 1 or 2 positional arguments, got {len(args)}"
        raise TypeError(msg)


@overload
def markdown(content: str, /, **kwargs: Any) -> Node:
    """Create a markdown widget with auto-generated ID."""
    ...


@overload
def markdown(id: str, content: str, /, **kwargs: Any) -> Node:
    """Create a markdown widget with an explicit ID."""
    ...


def markdown(*args: Any, **kwargs: Any) -> Node:
    """Markdown display widget.

    One-arg form auto-generates an ID::

        markdown("# Hello")

    Two-arg form takes explicit ID::

        markdown("docs", "# Hello")

    Args:
        content: Raw markdown text.
        **kwargs: Markdown props (width, text_size, h1_size, h2_size,
            h3_size, code_size, spacing, link_color, code_theme, a11y).
    """
    if len(args) == 1:
        return _node(None, "markdown", {"content": args[0], **kwargs})
    elif len(args) == 2:
        return _node(args[0], "markdown", {"content": args[1], **kwargs})
    else:
        msg = f"markdown() takes 1 or 2 positional arguments, got {len(args)}"
        raise TypeError(msg)


@overload
def progress_bar(range: tuple[float, float], value: float, /, **kwargs: Any) -> Node:
    """Create a progress bar with auto-generated ID."""
    ...


@overload
def progress_bar(
    id: str, range: tuple[float, float], value: float, /, **kwargs: Any
) -> Node:
    """Create a progress bar with an explicit ID."""
    ...


def progress_bar(*args: Any, **kwargs: Any) -> Node:
    """Progress bar display widget.

    Two-arg form auto-generates an ID::

        progress_bar((0, 100), 50)

    Three-arg form takes explicit ID::

        progress_bar("loading", (0, 100), 50)

    Args:
        range: ``(min, max)`` tuple.
        value: Current progress value.
        **kwargs: Progress bar props (width, height, style, vertical,
            label, a11y).
    """
    if len(args) == 2:
        return _node(
            None,
            "progress_bar",
            {"range": list(args[0]), "value": args[1], **kwargs},
        )
    elif len(args) == 3:
        return _node(
            args[0],
            "progress_bar",
            {"range": list(args[1]), "value": args[2], **kwargs},
        )
    else:
        msg = f"progress_bar() takes 2 or 3 positional arguments, got {len(args)}"
        raise TypeError(msg)


# ---------------------------------------------------------------------------
# Display leaf widgets (5) -- id required
# ---------------------------------------------------------------------------


def image(id: str, source: str | dict[str, str], /, **kwargs: Any) -> Node:
    """Image display -- raster image from file path or in-memory handle.

    Args:
        id: Image identifier.
        source: Path to image file or ``{"handle": name}`` for in-memory.
        **kwargs: Image props (width, height, content_fit, rotation,
            opacity, border_radius, filter_method, expand, scale, crop,
            alt, description, decorative, a11y).
    """
    return _node(id, "image", {"source": source, **kwargs})


def svg(id: str, source: str, /, **kwargs: Any) -> Node:
    """SVG display -- vector image from file path.

    Args:
        id: SVG identifier.
        source: Path to SVG file.
        **kwargs: SVG props (width, height, content_fit, rotation,
            opacity, color, alt, description, decorative, a11y).
    """
    return _node(id, "svg", {"source": source, **kwargs})


def rich_text(id: str, /, **kwargs: Any) -> Node:
    """Rich text display with individually styled spans.

    Args:
        id: Rich text identifier.
        **kwargs: Rich text props (spans, width, height, size, font,
            color, line_height, wrapping, ellipsis, a11y).
    """
    return _node(id, "rich_text", kwargs)


def qr_code(id: str, data: str, /, **kwargs: Any) -> Node:
    """QR code display.

    Args:
        id: QR code identifier.
        data: Data string to encode.
        **kwargs: QR code props (cell_size, cell_color, background,
            error_correction, alt, description, a11y).
    """
    return _node(id, "qr_code", {"data": data, **kwargs})


def canvas(id: str, /, **kwargs: Any) -> Node:
    """Canvas for drawing shapes organized into named layers.

    Args:
        id: Canvas identifier.
        **kwargs: Canvas props (layers, shapes, width, height, background,
            interactive, on_press, on_release, on_move, on_scroll, role,
            arrow_mode, alt, description, a11y).
    """
    return _node(id, "canvas", kwargs)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    # Type
    "Node",
    # Interactive leaves
    "button",
    "canvas",
    "checkbox",
    # Anonymous containers
    "column",
    "combo_box",
    "container",
    "floating",
    "grid",
    # Display
    "image",
    "keyed_column",
    "markdown",
    "overlay",
    "pane_grid",
    "pick_list",
    "pin",
    "pointer_area",
    "progress_bar",
    "qr_code",
    "radio",
    "responsive",
    "rich_text",
    "row",
    "rule",
    "scrollable",
    "sensor",
    "slider",
    # Layout primitives
    "space",
    "stack",
    "svg",
    "table",
    # Display with auto-id
    "text",
    "text_editor",
    "text_input",
    "themer",
    "toggler",
    "tooltip",
    "vertical_slider",
    # Named containers
    "window",
]
