"""Native widget definitions for Rust-backed custom widget types.

Native widgets are backed by a Rust crate implementing the
``WidgetExtension`` trait.  The Rust crate is compiled into a custom
plushie binary, and the widget communicates via the standard wire
protocol.  Use :class:`NativeWidget` to describe the widget, then
:func:`build_node` and :func:`build_command` to produce wire-compatible
nodes and commands at runtime.

Example::

    from plushie.native_widget import (
        NativeWidget, PropDef, CommandDef, ParamDef,
        build_node, build_command,
    )

    gauge_def = NativeWidget(
        kind="gauge",
        rust_crate="native/my_gauge",
        rust_constructor="my_gauge::GaugeExtension::new()",
        props=[
            PropDef("value", "number"),
            PropDef("min", "number"),
            PropDef("max", "number"),
            PropDef("color", "color"),
        ],
        commands=[
            CommandDef("set_value", [ParamDef("value", "number")]),
        ],
    )

    def gauge(id: str, value: float, **kwargs: object) -> dict:
        return build_node(gauge_def, id, {"value": value, **kwargs})

    def set_gauge_value(node_id: str, value: float) -> Command:
        return build_command(gauge_def, node_id, "set_value", {"value": value})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from plushie.commands import Command

# -- Prop types ---------------------------------------------------------------

#: Valid prop type strings for native widget property definitions.
PropType = Literal[
    "string",
    "number",
    "bool",
    "color",
    "length",
    "padding",
    "alignment",
    "font",
    "style",
    "atom",
    "map",
    "any",
]

#: Valid param type strings for native widget command parameters.
ParamType = Literal["string", "number", "bool"]

# -- Data definitions ---------------------------------------------------------

#: Property names that are reserved by the framework and cannot be used
#: in native widget definitions.
RESERVED_PROP_NAMES: frozenset[str] = frozenset(
    {"id", "type", "children", "a11y", "event_rate"}
)

BUILTIN_WIDGET_TYPES: frozenset[str] = frozenset(
    {
        "column",
        "row",
        "container",
        "stack",
        "grid",
        "pin",
        "keyed_column",
        "float",
        "responsive",
        "scrollable",
        "pane_grid",
        "text",
        "rich_text",
        "rich",
        "space",
        "rule",
        "progress_bar",
        "image",
        "svg",
        "markdown",
        "qr_code",
        "text_input",
        "text_editor",
        "checkbox",
        "toggler",
        "radio",
        "slider",
        "vertical_slider",
        "pick_list",
        "combo_box",
        "button",
        "pointer_area",
        "sensor",
        "tooltip",
        "themer",
        "window",
        "overlay",
        "canvas",
        "table",
    }
)


@dataclass(frozen=True, slots=True)
class PropDef:
    """Definition of a single property on an native widget.

    Attributes:
        name: The property name as it appears on the wire.
        prop_type: One of the supported prop type strings.
    """

    name: str
    prop_type: PropType


@dataclass(frozen=True, slots=True)
class ParamDef:
    """Definition of a single parameter in a native widget command.

    Attributes:
        name: The parameter name as it appears on the wire.
        param_type: One of the supported param type strings.
    """

    name: str
    param_type: ParamType


@dataclass(frozen=True, slots=True)
class CommandDef:
    """Definition of a command that can be sent to a native native widget.

    Attributes:
        name: The command operation name.
        params: The typed parameters this command accepts.
    """

    name: str
    params: list[ParamDef] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class NativeWidget:
    """Definition of a Rust-backed native widget.

    Describes the Rust crate, constructor, props, and commands that a
    native widget supports.  Used at build time to configure the plushie
    binary and at runtime to construct nodes and commands.

    Attributes:
        kind: Widget type string (e.g. ``"gauge"``).  Must match the Rust
            crate's registered widget type name.
        rust_crate: Path to the Rust crate relative to the project root
            (e.g. ``"native/my_gauge"``).
        rust_constructor: Rust expression to construct the extension
            instance (e.g. ``"my_gauge::GaugeExtension::new()"``).
        props: Declared properties with their types.
        commands: Declared commands that can be sent to this widget type.
    """

    kind: str
    rust_crate: str
    rust_constructor: str
    props: list[PropDef] = field(default_factory=list)
    commands: list[CommandDef] = field(default_factory=list)


# -- Validation ---------------------------------------------------------------


def validate(ext_def: NativeWidget) -> list[str]:
    """Validate an native widget definition.

    Returns an empty list when valid, or a list of human-readable error
    messages describing what is wrong.

    Checks performed:

    - ``kind`` must be non-empty.
    - No duplicate prop names.
    - No duplicate command names.
    - No reserved prop names (id, type, children, a11y, event_rate).
    """
    errors: list[str] = []

    if not ext_def.kind:
        errors.append("kind must not be empty")

    if ext_def.kind in BUILTIN_WIDGET_TYPES:
        errors.append(f'widget type "{ext_def.kind}" shadows a built-in widget')

    seen: set[str] = set()
    for prop in ext_def.props:
        if prop.name in seen:
            errors.append(f'duplicate prop name "{prop.name}"')
        seen.add(prop.name)

        if prop.name in RESERVED_PROP_NAMES:
            errors.append(f'prop name "{prop.name}" is reserved')

    seen_commands: set[str] = set()
    for command in ext_def.commands:
        if command.name in seen_commands:
            errors.append(f'duplicate command name "{command.name}"')
        seen_commands.add(command.name)

    return errors


# -- Runtime helpers ----------------------------------------------------------


def prop_names(ext_def: NativeWidget) -> list[str]:
    """Return the declared property names from a native widget definition."""
    return [p.name for p in ext_def.props]


def command_names(ext_def: NativeWidget) -> list[str]:
    """Return the declared command names from a native widget definition."""
    return [c.name for c in ext_def.commands]


def build_node(
    ext_def: NativeWidget,
    id: str,
    props: dict[str, Any] | None = None,
    *,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a node dict for a native widget.

    Creates a node with the widget's ``kind`` as the type and the
    given props.  The node dict is wire-compatible and can be included
    directly in a view tree.

    Args:
        ext_def: The native widget definition.
        id: Unique node ID.
        props: Property key-value pairs.
        children: Optional child nodes (for container widgets).

    Returns:
        A node dict with ``id``, ``type``, ``props``, and ``children``.
    """
    return {
        "id": id,
        "type": ext_def.kind,
        "props": dict(props) if props else {},
        "children": list(children) if children else [],
    }


def build_command(
    ext_def: NativeWidget,
    node_id: str,
    op: str,
    payload: dict[str, Any] | None = None,
) -> Command:
    """Build a native widget command targeting a specific widget instance.

    The command is sent via the wire protocol's unified ``command``
    message type and delivered to the Rust widget by node ID.

    Args:
        ext_def: The native widget definition (used for documentation; the
            ``kind`` is not sent on the wire since commands target by
            node ID).
        node_id: The target widget's node ID.
        op: The command operation name (must match a declared command).
        payload: Parameter key-value pairs for the command.

    Returns:
        A :class:`~plushie.commands.Command` of type
        ``"command"``.

    Raises:
        ValueError: If ``op`` is not declared by ``ext_def.commands``.
    """
    declared_commands = command_names(ext_def)
    if op not in declared_commands:
        detail = (
            f"declared commands: {', '.join(declared_commands)}"
            if declared_commands
            else "no commands declared"
        )
        raise ValueError(
            f'native widget "{ext_def.kind}" does not declare command "{op}" ({detail})'
        )

    if payload:
        return Command.command(node_id, op, payload)
    return Command.command(node_id, op)


__all__ = [
    "BUILTIN_WIDGET_TYPES",
    "RESERVED_PROP_NAMES",
    "CommandDef",
    "NativeWidget",
    "ParamDef",
    "ParamType",
    "PropDef",
    "PropType",
    "build_command",
    "build_node",
    "command_names",
    "prop_names",
    "validate",
]
