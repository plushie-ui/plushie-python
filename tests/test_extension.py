"""Tests for the native widget definition system."""

from __future__ import annotations

from plushie.commands import Command
from plushie.native_widget import (
    CommandDef,
    NativeWidget,
    ParamDef,
    PropDef,
    build_command,
    build_node,
    command_names,
    prop_names,
    validate,
)

# -- Fixtures ----------------------------------------------------------------


def _gauge_def() -> NativeWidget:
    return NativeWidget(
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
            CommandDef("reset"),
        ],
    )


# -- Dataclass construction --------------------------------------------------


class TestPropDef:
    def test_construction(self) -> None:
        p = PropDef("value", "number")
        assert p.name == "value"
        assert p.prop_type == "number"

    def test_frozen(self) -> None:
        p = PropDef("value", "number")
        try:
            p.name = "other"  # type: ignore[misc]
            raise AssertionError("expected FrozenInstanceError")
        except AttributeError:
            pass


class TestParamDef:
    def test_construction(self) -> None:
        p = ParamDef("amount", "number")
        assert p.name == "amount"
        assert p.param_type == "number"

    def test_frozen(self) -> None:
        p = ParamDef("amount", "number")
        try:
            p.name = "other"  # type: ignore[misc]
            raise AssertionError("expected FrozenInstanceError")
        except AttributeError:
            pass


class TestCommandDef:
    def test_with_params(self) -> None:
        c = CommandDef("set_value", [ParamDef("value", "number")])
        assert c.name == "set_value"
        assert len(c.params) == 1
        assert c.params[0].name == "value"

    def test_default_empty_params(self) -> None:
        c = CommandDef("reset")
        assert c.params == []


class TestNativeWidgetDef:
    def test_full_construction(self) -> None:
        ext = _gauge_def()
        assert ext.kind == "gauge"
        assert ext.rust_crate == "native/my_gauge"
        assert ext.rust_constructor == "my_gauge::GaugeExtension::new()"
        assert len(ext.props) == 4
        assert len(ext.commands) == 2

    def test_defaults(self) -> None:
        ext = NativeWidget(
            kind="minimal",
            rust_crate="native/minimal",
            rust_constructor="minimal::Ext::new()",
        )
        assert ext.props == []
        assert ext.commands == []

    def test_frozen(self) -> None:
        ext = _gauge_def()
        try:
            ext.kind = "other"  # type: ignore[misc]
            raise AssertionError("expected FrozenInstanceError")
        except AttributeError:
            pass


# -- Validation ---------------------------------------------------------------


class TestValidate:
    def test_valid_definition(self) -> None:
        assert validate(_gauge_def()) == []

    def test_empty_kind(self) -> None:
        ext = NativeWidget(
            kind="",
            rust_crate="native/x",
            rust_constructor="x::X::new()",
        )
        errors = validate(ext)
        assert any("kind must not be empty" in e for e in errors)

    def test_duplicate_prop_names(self) -> None:
        ext = NativeWidget(
            kind="dupe",
            rust_crate="native/dupe",
            rust_constructor="dupe::D::new()",
            props=[PropDef("value", "number"), PropDef("value", "number")],
        )
        errors = validate(ext)
        assert any("duplicate" in e and "value" in e for e in errors)

    def test_reserved_prop_name(self) -> None:
        ext = NativeWidget(
            kind="bad",
            rust_crate="native/bad",
            rust_constructor="bad::B::new()",
            props=[PropDef("id", "string")],
        )
        errors = validate(ext)
        assert any("reserved" in e and "id" in e for e in errors)

    def test_reserved_children(self) -> None:
        ext = NativeWidget(
            kind="bad",
            rust_crate="native/bad",
            rust_constructor="bad::B::new()",
            props=[PropDef("children", "string")],
        )
        errors = validate(ext)
        assert any("reserved" in e and "children" in e for e in errors)

    def test_builtin_widget_type_name(self) -> None:
        ext = NativeWidget(
            kind="button",
            rust_crate="native/button",
            rust_constructor="button::B::new()",
        )
        errors = validate(ext)
        assert any("shadows a built-in" in e for e in errors)

    def test_canvas_type_name_rejected(self) -> None:
        ext = NativeWidget(
            kind="canvas",
            rust_crate="native/canvas",
            rust_constructor="canvas::C::new()",
        )
        errors = validate(ext)
        assert any("shadows a built-in" in e for e in errors)

    def test_multiple_errors(self) -> None:
        ext = NativeWidget(
            kind="",
            rust_crate="native/bad",
            rust_constructor="bad::B::new()",
            props=[
                PropDef("id", "string"),
                PropDef("x", "number"),
                PropDef("x", "number"),
            ],
        )
        errors = validate(ext)
        # Should report: empty kind, reserved "id", duplicate "x"
        assert len(errors) == 3


# Cross-widget collision checks (duplicate kinds, duplicate crate
# basenames) live in cargo-plushie now. The Python SDK only retains
# per-widget sanity checks in ``validate``.


# -- Helper functions ---------------------------------------------------------


class TestPropNames:
    def test_returns_names(self) -> None:
        assert prop_names(_gauge_def()) == ["value", "min", "max", "color"]

    def test_empty(self) -> None:
        ext = NativeWidget(
            kind="x", rust_crate="native/x", rust_constructor="x::X::new()"
        )
        assert prop_names(ext) == []


class TestCommandNames:
    def test_returns_names(self) -> None:
        assert command_names(_gauge_def()) == ["set_value", "reset"]

    def test_empty(self) -> None:
        ext = NativeWidget(
            kind="x", rust_crate="native/x", rust_constructor="x::X::new()"
        )
        assert command_names(ext) == []


# -- build_node ---------------------------------------------------------------


class TestBuildNode:
    def test_basic_node(self) -> None:
        ext = _gauge_def()
        node = build_node(ext, "g1", {"value": 42, "color": "#ff0000"})
        assert node["id"] == "g1"
        assert node["type"] == "gauge"
        assert node["props"]["value"] == 42
        assert node["props"]["color"] == "#ff0000"
        assert node["children"] == []

    def test_no_props(self) -> None:
        ext = _gauge_def()
        node = build_node(ext, "g2")
        assert node["props"] == {}
        assert node["children"] == []

    def test_with_children(self) -> None:
        ext = _gauge_def()
        child = {"id": "c1", "type": "text", "props": {}, "children": []}
        node = build_node(ext, "g3", {"value": 1}, children=[child])
        assert len(node["children"]) == 1
        assert node["children"][0]["id"] == "c1"

    def test_props_are_copied(self) -> None:
        """Mutating the input dict after build_node should not affect the node."""
        ext = _gauge_def()
        original = {"value": 10}
        node = build_node(ext, "g4", original)
        original["value"] = 999
        assert node["props"]["value"] == 10

    def test_children_are_copied(self) -> None:
        """Mutating the input list after build_node should not affect the node."""
        ext = _gauge_def()
        kids: list[dict[str, object]] = []
        node = build_node(ext, "g5", children=kids)
        kids.append({"id": "late", "type": "text", "props": {}, "children": []})
        assert node["children"] == []


# -- build_command ------------------------------------------------------------


class TestBuildCommand:
    def test_basic_command(self) -> None:
        ext = _gauge_def()
        cmd = build_command(ext, "g1", "set_value", {"value": 75})
        assert isinstance(cmd, Command)
        assert cmd.type == "command"
        assert cmd.payload["id"] == "g1"
        assert cmd.payload["family"] == "set_value"
        assert cmd.payload["value"] == {"value": 75}

    def test_no_payload(self) -> None:
        ext = _gauge_def()
        cmd = build_command(ext, "g1", "reset")
        assert "value" not in cmd.payload

    def test_matches_command_factory(self) -> None:
        """build_command should produce the same result as Command.command."""
        ext = _gauge_def()
        via_ext = build_command(ext, "g1", "set_value", {"value": 50})
        via_cmd = Command.command("g1", "set_value", {"value": 50})
        assert via_ext == via_cmd


# Workspace Cargo.toml and main.rs generation moved to cargo-plushie.
# Renderer spec generation on the Python side is covered by
# tests/test_renderer_build.py.
