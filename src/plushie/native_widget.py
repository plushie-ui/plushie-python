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

    return errors


def validate_all(widgets: list[NativeWidget]) -> list[str]:
    """Validate a list of native widget definitions, including cross-widget checks.

    Runs :func:`validate` on each widget individually, then checks
    for collisions across the full list:

    - No two widgets may claim the same ``kind`` (widget type name).
    - No two widgets may share the same crate name (last segment of
      ``rust_crate`` path).

    Returns an empty list when valid, or a list of human-readable error
    messages.
    """
    errors: list[str] = []

    # Per-widget validation
    for ext in widgets:
        for err in validate(ext):
            errors.append(f"[{ext.kind or '?'}] {err}")

    # Kind collisions
    seen_kinds: dict[str, str] = {}
    for ext in widgets:
        if ext.kind in seen_kinds:
            errors.append(
                f'widget type "{ext.kind}" claimed by both '
                f'"{seen_kinds[ext.kind]}" and "{ext.rust_crate}"'
            )
        seen_kinds[ext.kind] = ext.rust_crate

    # Crate name collisions
    seen_crates: dict[str, str] = {}
    for ext in widgets:
        crate_name = ext.rust_crate.rsplit("/", maxsplit=1)[-1]
        if crate_name in seen_crates:
            errors.append(
                f'crate name "{crate_name}" used by both '
                f'"{seen_crates[crate_name]}" and "{ext.kind}"'
            )
        seen_crates[crate_name] = ext.kind

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
    """
    _ = ext_def
    if payload:
        return Command.widget_command(node_id, op, payload)
    return Command.widget_command(node_id, op)


# -- Build system integration -------------------------------------------------


def generate_cargo_toml(
    widgets: list[NativeWidget],
    binary_name: str = "plushie-renderer",
    *,
    build_dir: str = ".",
    source_path: str | None = None,
) -> str:
    """Generate a Cargo.toml workspace for a custom binary build.

    Produces the Cargo workspace manifest that includes plushie-ext
    and all native widget crates as path dependencies.  This is the
    Python equivalent of ``mix plushie.build``'s Cargo generation.

    Crate paths are made relative to ``build_dir`` so the generated
    Cargo.toml works from the build output directory.

    Args:
        widgets: Native widget definitions to include.
        binary_name: Name for the output binary.
        build_dir: The directory where the Cargo.toml will be written.
            Crate paths are resolved relative to this.
        source_path: Path to the plushie Rust source checkout. If
            provided, plushie-ext is referenced as a local path
            dependency. Otherwise uses the git repository.

    Returns:
        The Cargo.toml content as a string.
    """
    import os

    deps = []
    for ext in widgets:
        # Make crate path relative to build_dir
        abs_crate = os.path.abspath(ext.rust_crate)
        rel_crate = os.path.relpath(abs_crate, os.path.abspath(build_dir))
        crate_name = ext.rust_crate.rsplit("/", maxsplit=1)[-1]
        deps.append(f'{crate_name} = {{ path = "{rel_crate}" }}')

    deps_block = "\n".join(deps)

    # plushie dependencies: plushie-ext (extensions API) + plushie-renderer (run fn)
    if source_path:
        abs_src = os.path.abspath(source_path)
        abs_build = os.path.abspath(build_dir)
        core_rel = os.path.relpath(os.path.join(abs_src, "plushie-ext"), abs_build)
        runner_rel = os.path.relpath(
            os.path.join(abs_src, "plushie-renderer"), abs_build
        )
        core_dep = f'plushie-ext = {{ path = "{core_rel}" }}'
        runner_dep = f'plushie-renderer = {{ path = "{runner_rel}" }}'
    else:
        core_dep = 'plushie-ext = "0.5"'
        runner_dep = 'plushie-renderer = "0.5"'

    # Use underscores for the Cargo package name (Cargo convention)
    package_name = binary_name.replace("-", "_")

    return f"""\
[package]
name = "{package_name}"
version = "0.1.0"
edition = "2024"

[[bin]]
name = "{binary_name}"
path = "src/main.rs"

[dependencies]
{core_dep}
{runner_dep}
{deps_block}
"""


def generate_main_rs(widgets: list[NativeWidget]) -> str:
    """Generate main.rs registering all native widgets.

    Produces the Rust entry point that creates a ``PlushieAppBuilder``,
    registers each widget via ``.extension()``, and calls ``run()``.

    Args:
        widgets: Native widget definitions to register.

    Returns:
        The main.rs content as a string.
    """
    registrations = []
    for ext in widgets:
        registrations.append(f"        .extension({ext.rust_constructor})")
    registrations_block = "\n".join(registrations)

    return f"""\
use plushie_ext::app::PlushieAppBuilder;

fn main() -> plushie_ext::iced::Result {{
    let builder = PlushieAppBuilder::new()
{registrations_block};
    plushie_renderer::run(builder)
}}
"""


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
    "generate_cargo_toml",
    "generate_main_rs",
    "prop_names",
    "validate",
    "validate_all",
]
