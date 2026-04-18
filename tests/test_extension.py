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
    generate_cargo_toml,
    generate_main_rs,
    prop_names,
    validate,
    validate_all,
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


def _sparkline_def() -> NativeWidget:
    return NativeWidget(
        kind="sparkline",
        rust_crate="native/my_sparkline",
        rust_constructor="my_sparkline::SparklineExtension::new()",
        props=[
            PropDef("data", "number"),
            PropDef("color", "color"),
            PropDef("capacity", "number"),
        ],
        commands=[
            CommandDef("push", [ParamDef("value", "number")]),
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


class TestValidateAll:
    def test_valid_pair(self) -> None:
        assert validate_all([_gauge_def(), _sparkline_def()]) == []

    def test_empty_list(self) -> None:
        assert validate_all([]) == []

    def test_single_valid(self) -> None:
        assert validate_all([_gauge_def()]) == []

    def test_kind_collision(self) -> None:
        a = _gauge_def()
        b = NativeWidget(
            kind="gauge",
            rust_crate="native/other_gauge",
            rust_constructor="other::Gauge::new()",
        )
        errors = validate_all([a, b])
        assert any("gauge" in e and "claimed by both" in e for e in errors)

    def test_crate_name_collision(self) -> None:
        a = NativeWidget(
            kind="foo",
            rust_crate="native/shared",
            rust_constructor="shared::Foo::new()",
        )
        b = NativeWidget(
            kind="bar",
            rust_crate="vendor/shared",
            rust_constructor="shared::Bar::new()",
        )
        errors = validate_all([a, b])
        assert any("crate name" in e and "shared" in e for e in errors)

    def test_per_extension_errors_propagated(self) -> None:
        bad = NativeWidget(
            kind="",
            rust_crate="native/bad",
            rust_constructor="bad::B::new()",
            props=[PropDef("id", "string")],
        )
        errors = validate_all([bad])
        assert any("kind must not be empty" in e for e in errors)
        assert any("reserved" in e for e in errors)

    def test_both_collisions_reported(self) -> None:
        """Two extensions with the same kind AND same crate name."""
        a = NativeWidget(
            kind="widget",
            rust_crate="native/same_crate",
            rust_constructor="same_crate::A::new()",
        )
        b = NativeWidget(
            kind="widget",
            rust_crate="vendor/same_crate",
            rust_constructor="same_crate::B::new()",
        )
        errors = validate_all([a, b])
        kind_errors = [e for e in errors if "claimed by both" in e]
        crate_errors = [e for e in errors if "crate name" in e]
        assert len(kind_errors) >= 1
        assert len(crate_errors) >= 1


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
        """build_command should produce the same result as Command.widget_command."""
        ext = _gauge_def()
        via_ext = build_command(ext, "g1", "set_value", {"value": 50})
        via_cmd = Command.widget_command("g1", "set_value", {"value": 50})
        assert via_ext == via_cmd


# -- Cargo generation ---------------------------------------------------------


class TestGenerateCargoToml:
    def test_single_extension(self) -> None:
        toml = generate_cargo_toml([_gauge_def()])
        assert '"native/my_gauge"' in toml
        assert 'name = "plushie-renderer"' in toml
        assert 'my_gauge = { path = "native/my_gauge" }' in toml

    def test_custom_binary_name(self) -> None:
        toml = generate_cargo_toml([_gauge_def()], binary_name="my-app")
        assert 'name = "my-app"' in toml

    def test_multiple_extensions(self) -> None:
        toml = generate_cargo_toml([_gauge_def(), _sparkline_def()])
        assert '"native/my_gauge"' in toml
        assert '"native/my_sparkline"' in toml
        assert "my_gauge" in toml
        assert "my_sparkline" in toml

    def test_package_structure(self) -> None:
        toml = generate_cargo_toml([_gauge_def()])
        assert "[package]" in toml
        assert "src/main.rs" in toml
        assert "plushie-widget-sdk" in toml
        assert "plushie-renderer =" in toml  # runner crate dep

    def test_source_path_local_deps(self) -> None:
        toml = generate_cargo_toml(
            [_gauge_def()], source_path="/tmp/plushie", build_dir="/tmp/build"
        )
        assert "plushie-widget-sdk = { path =" in toml
        assert "plushie-renderer = { path =" in toml
        assert "git" not in toml

    def test_no_source_path_crates_io_deps(self) -> None:
        from plushie.binary import PLUSHIE_RUST_VERSION

        toml = generate_cargo_toml([_gauge_def()])
        assert f'plushie-widget-sdk = "{PLUSHIE_RUST_VERSION}"' in toml
        assert f'plushie-renderer = "{PLUSHIE_RUST_VERSION}"' in toml


# -- main.rs generation ------------------------------------------------------


class TestGenerateMainRs:
    def test_single_extension(self) -> None:
        rs = generate_main_rs([_gauge_def()])
        assert "my_gauge::GaugeExtension::new()" in rs
        assert "PlushieAppBuilder::new()" in rs
        assert ".widget(" in rs
        assert "fn main() -> plushie_widget_sdk::iced::Result" in rs

    def test_multiple_extensions(self) -> None:
        rs = generate_main_rs([_gauge_def(), _sparkline_def()])
        assert "my_gauge::GaugeExtension::new()" in rs
        assert "my_sparkline::SparklineExtension::new()" in rs
        # Both widgets registered via .widget().
        assert rs.count(".widget(") == 2

    def test_empty_extensions(self) -> None:
        rs = generate_main_rs([])
        assert "PlushieAppBuilder::new()" in rs
        assert ".widget(" not in rs
