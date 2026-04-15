"""Tests for plushie.types: all shared types, dataclasses, and helpers."""

from __future__ import annotations

import pytest

from plushie.types import (
    BUILTIN_THEMES,
    NAMED_COLORS,
    A11y,
    Border,
    Colors,
    Font,
    Gradient,
    HelloInfo,
    KeyModifiers,
    Shadow,
    StatusOverride,
    StyleMap,
    Theme,
)

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------


class TestColorsFromRgb:
    def test_black(self) -> None:
        assert Colors.from_rgb(0, 0, 0) == "#000000"

    def test_white(self) -> None:
        assert Colors.from_rgb(255, 255, 255) == "#ffffff"

    def test_mixed(self) -> None:
        assert Colors.from_rgb(255, 128, 0) == "#ff8000"

    def test_single_digit_padded(self) -> None:
        assert Colors.from_rgb(0, 1, 15) == "#00010f"


class TestColorsFromRgba:
    def test_full_alpha(self) -> None:
        assert Colors.from_rgba(255, 0, 0, 1.0) == "#ff0000ff"

    def test_zero_alpha(self) -> None:
        assert Colors.from_rgba(0, 0, 0, 0.0) == "#00000000"

    def test_half_alpha(self) -> None:
        assert Colors.from_rgba(255, 128, 0, 0.5) == "#ff800080"

    def test_alpha_clamped_high(self) -> None:
        result = Colors.from_rgba(0, 0, 0, 2.0)
        assert result == "#000000ff"

    def test_alpha_clamped_low(self) -> None:
        result = Colors.from_rgba(0, 0, 0, -1.0)
        assert result == "#00000000"


class TestColorsFromHex:
    def test_with_hash(self) -> None:
        assert Colors.from_hex("#FF8800") == "#ff8800"

    def test_without_hash(self) -> None:
        assert Colors.from_hex("ff8800") == "#ff8800"

    def test_already_lowercase(self) -> None:
        assert Colors.from_hex("#aabbcc") == "#aabbcc"

    def test_eight_char_alpha(self) -> None:
        assert Colors.from_hex("#ff880080") == "#ff880080"

    def test_short_three(self) -> None:
        assert Colors.from_hex("abc") == "#aabbcc"

    def test_short_four(self) -> None:
        assert Colors.from_hex("#abcd") == "#aabbccdd"

    def test_invalid_length(self) -> None:
        with pytest.raises(ValueError, match="invalid hex color length"):
            Colors.from_hex("abcde")

    def test_invalid_digits(self) -> None:
        with pytest.raises(ValueError, match="invalid hex color digits"):
            Colors.from_hex("gghhii")

    def test_invalid_digits_partial_hex(self) -> None:
        """Hex-like string with trailing non-hex chars must fail."""
        with pytest.raises(ValueError, match="invalid hex color digits"):
            Colors.from_hex("aabb0z")

    def test_valid_all_digits(self) -> None:
        """Pure numeric hex string without hash prefix."""
        assert Colors.from_hex("001122") == "#001122"


class TestColorsCast:
    def test_named_red(self) -> None:
        assert Colors.cast("red") == "#ff0000"

    def test_named_case_insensitive(self) -> None:
        assert Colors.cast("CornflowerBlue") == "#6495ed"

    def test_named_transparent(self) -> None:
        assert Colors.cast("transparent") == "#00000000"

    def test_hex_passthrough(self) -> None:
        assert Colors.cast("#ff0000") == "#ff0000"

    def test_hex_uppercase_normalized(self) -> None:
        assert Colors.cast("#FF0000") == "#ff0000"

    def test_unknown_name_tries_hex(self) -> None:
        # "aabbcc" is not a named color, falls through to hex
        assert Colors.cast("aabbcc") == "#aabbcc"

    def test_unknown_name_bad_hex_raises(self) -> None:
        with pytest.raises(ValueError):
            Colors.cast("notacolor")


class TestNamedColors:
    def test_count(self) -> None:
        # 148 CSS colors + transparent = 149
        assert len(NAMED_COLORS) == 149

    def test_all_start_with_hash(self) -> None:
        for name, hex_val in NAMED_COLORS.items():
            assert hex_val.startswith("#"), f"{name}: {hex_val}"

    def test_all_lowercase_keys(self) -> None:
        for name in NAMED_COLORS:
            assert name == name.lower(), f"key not lowercase: {name}"

    def test_named_colors_returns_copy(self) -> None:
        copy = Colors.named_colors()
        assert copy == NAMED_COLORS
        assert copy is not NAMED_COLORS


# ---------------------------------------------------------------------------
# KeyModifiers
# ---------------------------------------------------------------------------


class TestKeyModifiers:
    def test_defaults(self) -> None:
        m = KeyModifiers()
        assert not m.shift
        assert not m.ctrl
        assert not m.alt
        assert not m.logo
        assert not m.command

    def test_frozen(self) -> None:
        m = KeyModifiers(shift=True)
        with pytest.raises(AttributeError):
            m.shift = False  # type: ignore[misc]

    def test_fields(self) -> None:
        m = KeyModifiers(shift=True, ctrl=True, alt=False, logo=True, command=False)
        assert m.shift is True
        assert m.ctrl is True
        assert m.alt is False
        assert m.logo is True
        assert m.command is False


# ---------------------------------------------------------------------------
# Border
# ---------------------------------------------------------------------------


class TestBorder:
    def test_defaults(self) -> None:
        b = Border()
        assert b.color is None
        assert b.width == 0
        assert b.radius == 0

    def test_construction(self) -> None:
        b = Border(color="#ff0000", width=2, radius=8)
        assert b.color == "#ff0000"
        assert b.width == 2
        assert b.radius == 8

    def test_frozen(self) -> None:
        b = Border()
        with pytest.raises(AttributeError):
            b.width = 5  # type: ignore[misc]

    def test_per_corner_radius(self) -> None:
        corners = Border.radius_corners(8, 8, 0, 0)
        assert corners == {
            "top_left": 8,
            "top_right": 8,
            "bottom_right": 0,
            "bottom_left": 0,
        }

    def test_border_with_corner_radius(self) -> None:
        corners = Border.radius_corners(4, 4, 4, 4)
        b = Border(radius=corners)
        assert isinstance(b.radius, dict)
        assert b.radius["top_left"] == 4


# ---------------------------------------------------------------------------
# Shadow
# ---------------------------------------------------------------------------


class TestShadow:
    def test_defaults(self) -> None:
        s = Shadow()
        assert s.color == "#000000"
        assert s.offset == (0, 0)
        assert s.blur_radius == 0

    def test_construction(self) -> None:
        s = Shadow(color="#00000080", offset=(4.0, 4.0), blur_radius=8.0)
        assert s.color == "#00000080"
        assert s.offset == (4.0, 4.0)
        assert s.blur_radius == 8.0

    def test_frozen(self) -> None:
        s = Shadow()
        with pytest.raises(AttributeError):
            s.blur_radius = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Gradient
# ---------------------------------------------------------------------------


class TestGradient:
    def test_linear_factory(self) -> None:
        g = Gradient.linear(90, [(0.0, "#ff0000"), (1.0, "#0000ff")])
        assert g.angle == 90
        assert len(g.stops) == 2
        assert g.stops[0] == (0.0, "#ff0000")
        assert g.stops[1] == (1.0, "#0000ff")

    def test_stops_are_tuple(self) -> None:
        g = Gradient.linear(45, [(0.0, "#000000"), (1.0, "#ffffff")])
        assert isinstance(g.stops, tuple)

    def test_named_color_in_stops(self) -> None:
        g = Gradient.linear(0, [(0.0, "red"), (1.0, "blue")])
        assert g.stops[0] == (0.0, "#ff0000")
        assert g.stops[1] == (1.0, "#0000ff")

    def test_frozen(self) -> None:
        g = Gradient.linear(90, [(0.0, "#000000")])
        with pytest.raises(AttributeError):
            g.angle = 45  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------


class TestFont:
    def test_defaults(self) -> None:
        f = Font()
        assert f.family is None
        assert f.weight is None
        assert f.style is None
        assert f.stretch is None

    def test_construction(self) -> None:
        f = Font(family="Inter", weight="bold", style="italic", stretch="condensed")
        assert f.family == "Inter"
        assert f.weight == "bold"
        assert f.style == "italic"
        assert f.stretch == "condensed"

    def test_frozen(self) -> None:
        f = Font()
        with pytest.raises(AttributeError):
            f.family = "Arial"  # type: ignore[misc]

    def test_partial(self) -> None:
        f = Font(weight="semi_bold")
        assert f.weight == "semi_bold"
        assert f.family is None


# ---------------------------------------------------------------------------
# StyleMap
# ---------------------------------------------------------------------------


class TestStyleMap:
    def test_empty(self) -> None:
        s = StyleMap()
        assert s.base is None
        assert s.background is None
        assert s.text_color is None
        assert s.border is None
        assert s.shadow is None
        assert s.hovered is None
        assert s.pressed is None
        assert s.disabled is None
        assert s.focused is None

    def test_with_background_hex(self) -> None:
        s = StyleMap().with_background("#ff0000")
        assert s.background == "#ff0000"

    def test_with_background_named(self) -> None:
        s = StyleMap().with_background("red")
        assert s.background == "#ff0000"

    def test_with_background_gradient(self) -> None:
        g = Gradient.linear(90, [(0.0, "#000000"), (1.0, "#ffffff")])
        s = StyleMap().with_background(g)
        assert isinstance(s.background, Gradient)

    def test_with_text_color(self) -> None:
        s = StyleMap().with_text_color("white")
        assert s.text_color == "#ffffff"

    def test_with_border(self) -> None:
        b = Border(color="#000000", width=1, radius=4)
        s = StyleMap().with_border(b)
        assert s.border is b

    def test_with_shadow(self) -> None:
        sh = Shadow(offset=(2.0, 2.0), blur_radius=6.0)
        s = StyleMap().with_shadow(sh)
        assert s.shadow is sh

    def test_with_hovered(self) -> None:
        override: StatusOverride = {"background": "#cc0000"}
        s = StyleMap().with_hovered(override)
        assert s.hovered == {"background": "#cc0000"}

    def test_with_pressed(self) -> None:
        s = StyleMap().with_pressed({"background": "#990000"})
        assert s.pressed is not None

    def test_with_disabled(self) -> None:
        s = StyleMap().with_disabled({"text_color": "#888888"})
        assert s.disabled == {"text_color": "#888888"}

    def test_with_focused(self) -> None:
        b = Border(color="#0000ff", width=2)
        s = StyleMap().with_focused({"border": b})
        assert s.focused is not None
        assert s.focused["border"] is b

    def test_with_base(self) -> None:
        s = StyleMap().with_base("primary")
        assert s.base == "primary"

    def test_chaining(self) -> None:
        s = (
            StyleMap()
            .with_background("#3366ff")
            .with_text_color("white")
            .with_hovered({"background": "#5588ff"})
        )
        assert s.background == "#3366ff"
        assert s.text_color == "#ffffff"
        assert s.hovered is not None

    def test_frozen(self) -> None:
        s = StyleMap()
        with pytest.raises(AttributeError):
            s.background = "#000000"  # type: ignore[misc]

    def test_original_unchanged_after_with(self) -> None:
        original = StyleMap()
        modified = original.with_background("#ff0000")
        assert original.background is None
        assert modified.background == "#ff0000"


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


class TestTheme:
    def test_builtin(self) -> None:
        t = Theme.builtin("dark")
        assert t.name == "dark"
        assert t.palette is None

    def test_custom_basic(self) -> None:
        t = Theme.custom("My Theme", primary="#7aa2f7")
        assert t.name == "My Theme"
        assert t.palette is not None
        assert t.palette["primary"] == "#7aa2f7"

    def test_custom_with_base(self) -> None:
        t = Theme.custom("Nord+", base="nord", primary="#88c0d0")
        assert t.palette is not None
        assert t.palette["base"] == "nord"
        assert t.palette["primary"] == "#88c0d0"

    def test_custom_named_color(self) -> None:
        t = Theme.custom("Red Theme", danger="red")
        assert t.palette is not None
        assert t.palette["danger"] == "#ff0000"

    def test_custom_shade_overrides(self) -> None:
        t = Theme.custom(
            "Shade Test",
            primary="#0f3460",
            primary_strong="#1a5276",
            primary_strong_text="#ffffff",
        )
        assert t.palette is not None
        assert t.palette["primary_strong"] == "#1a5276"
        assert t.palette["primary_strong_text"] == "#ffffff"

    def test_custom_no_options_gives_none_palette(self) -> None:
        t = Theme.custom("Empty")
        assert t.palette is None

    def test_frozen(self) -> None:
        t = Theme.builtin("dark")
        with pytest.raises(AttributeError):
            t.name = "light"  # type: ignore[misc]

    def test_builtin_themes_tuple(self) -> None:
        assert len(BUILTIN_THEMES) == 22
        assert "light" in BUILTIN_THEMES
        assert "dark" in BUILTIN_THEMES
        assert "dracula" in BUILTIN_THEMES
        assert "ferra" in BUILTIN_THEMES


# ---------------------------------------------------------------------------
# A11y
# ---------------------------------------------------------------------------


class TestA11y:
    def test_defaults_all_none(self) -> None:
        a = A11y()
        assert a.role is None
        assert a.label is None
        assert a.description is None
        assert a.live is None
        assert a.hidden is None
        assert a.expanded is None
        assert a.required is None
        assert a.level is None
        assert a.busy is None
        assert a.invalid is None
        assert a.modal is None
        assert a.read_only is None
        assert a.mnemonic is None
        assert a.toggled is None
        assert a.selected is None
        assert a.value is None
        assert a.orientation is None
        assert a.labelled_by is None
        assert a.described_by is None
        assert a.error_message is None
        assert a.disabled is None
        assert a.position_in_set is None
        assert a.size_of_set is None
        assert a.has_popup is None

    def test_all_fields(self) -> None:
        a = A11y(
            role="heading",
            label="Main heading",
            description="The main heading of the page",
            live="polite",
            hidden=False,
            expanded=True,
            required=True,
            level=1,
            busy=False,
            invalid=True,
            modal=False,
            read_only=True,
            mnemonic="H",
            toggled=True,
            selected=False,
            value="42",
            orientation="horizontal",
            labelled_by="title",
            described_by="desc",
            error_message="err",
            disabled=False,
            position_in_set=1,
            size_of_set=10,
            has_popup="menu",
        )
        assert a.role == "heading"
        assert a.label == "Main heading"
        assert a.level == 1
        assert a.has_popup == "menu"
        assert a.position_in_set == 1
        assert a.size_of_set == 10

    def test_frozen(self) -> None:
        a = A11y(label="test")
        with pytest.raises(AttributeError):
            a.label = "changed"  # type: ignore[misc]

    def test_field_count(self) -> None:
        import dataclasses

        fields = dataclasses.fields(A11y)
        assert len(fields) == 24

    def test_table_context_roles(self) -> None:
        """Table-context roles (row, cell, column_header) are valid A11y roles."""
        a_row = A11y(role="row")
        assert a_row.role == "row"
        a_cell = A11y(role="cell")
        assert a_cell.role == "cell"
        a_col = A11y(role="column_header")
        assert a_col.role == "column_header"


# ---------------------------------------------------------------------------
# HelloInfo
# ---------------------------------------------------------------------------


class TestHelloInfo:
    def test_construction(self) -> None:
        h = HelloInfo(
            protocol=1,
            version="0.3.0",
            name="plushie",
            mode="headless",
            backend="tiny-skia",
            transport="stdio",
            extensions=("charts", "editor"),
        )
        assert h.protocol == 1
        assert h.version == "0.3.0"
        assert h.name == "plushie"
        assert h.mode == "headless"
        assert h.backend == "tiny-skia"
        assert h.transport == "stdio"
        assert h.extensions == ("charts", "editor")

    def test_extensions_default(self) -> None:
        h = HelloInfo(
            protocol=1,
            version="0.3.0",
            name="plushie",
            mode="mock",
            backend="none",
            transport="stdio",
        )
        assert h.extensions == ()

    def test_frozen(self) -> None:
        h = HelloInfo(
            protocol=1,
            version="0.3.0",
            name="plushie",
            mode="mock",
            backend="none",
            transport="stdio",
        )
        with pytest.raises(AttributeError):
            h.protocol = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Wire encoding: to_wire()
# ---------------------------------------------------------------------------


class TestBorderToWire:
    def test_defaults(self) -> None:
        assert Border().to_wire() == {"color": None, "width": 0, "radius": 0}

    def test_full(self) -> None:
        b = Border(color="#ff0000", width=2, radius=8)
        assert b.to_wire() == {"color": "#ff0000", "width": 2, "radius": 8}

    def test_per_corner_radius(self) -> None:
        corners = Border.radius_corners(8, 8, 0, 0)
        b = Border(radius=corners)
        wire = b.to_wire()
        assert wire["radius"] == corners


class TestShadowToWire:
    def test_defaults(self) -> None:
        wire = Shadow().to_wire()
        assert wire == {"color": "#000000", "offset": [0, 0], "blur_radius": 0}

    def test_offset_is_list(self) -> None:
        s = Shadow(offset=(4.0, 2.0))
        wire = s.to_wire()
        assert wire["offset"] == [4.0, 2.0]
        assert isinstance(wire["offset"], list)


class TestGradientToWire:
    def test_linear(self) -> None:
        g = Gradient.linear(90, [(0.0, "#ff0000"), (1.0, "#0000ff")])
        wire = g.to_wire()
        assert wire["type"] == "linear"
        assert wire["angle"] == 90
        assert wire["stops"] == [
            {"offset": 0.0, "color": "#ff0000"},
            {"offset": 1.0, "color": "#0000ff"},
        ]


class TestFontToWire:
    def test_empty(self) -> None:
        assert Font().to_wire() == {}

    def test_family_only(self) -> None:
        assert Font(family="Inter").to_wire() == {"family": "Inter"}

    def test_weight_snake_case(self) -> None:
        f = Font(weight="semi_bold")
        assert f.to_wire() == {"weight": "semi_bold"}

    def test_all_fields(self) -> None:
        f = Font(
            family="Fira Code",
            weight="bold",
            style="italic",
            stretch="ultra_condensed",
        )
        wire = f.to_wire()
        assert wire == {
            "family": "Fira Code",
            "weight": "bold",
            "style": "italic",
            "stretch": "ultra_condensed",
        }


class TestStyleMapToWire:
    def test_empty(self) -> None:
        assert StyleMap().to_wire() == {}

    def test_background_color(self) -> None:
        s = StyleMap().with_background("#ff0000")
        assert s.to_wire() == {"background": "#ff0000"}

    def test_background_gradient(self) -> None:
        g = Gradient.linear(90, [(0.0, "#000000"), (1.0, "#ffffff")])
        s = StyleMap().with_background(g)
        wire = s.to_wire()
        bg = wire["background"]
        assert isinstance(bg, dict)
        assert bg["type"] == "linear"

    def test_nested_border_shadow(self) -> None:
        b = Border(color="#000000", width=1, radius=4)
        sh = Shadow(offset=(2.0, 2.0), blur_radius=6.0)
        s = StyleMap().with_border(b).with_shadow(sh)
        wire = s.to_wire()
        assert wire["border"] == {"color": "#000000", "width": 1, "radius": 4}
        shadow = wire["shadow"]
        assert isinstance(shadow, dict)
        assert shadow["offset"] == [2.0, 2.0]

    def test_status_override_with_border(self) -> None:
        b = Border(color="#0000ff", width=2)
        s = StyleMap().with_focused({"border": b})
        wire = s.to_wire()
        focused = wire["focused"]
        assert isinstance(focused, dict)
        assert focused["border"] == {
            "color": "#0000ff",
            "width": 2,
            "radius": 0,
        }

    def test_status_override_plain_values(self) -> None:
        s = StyleMap().with_hovered({"background": "#cc0000"})
        wire = s.to_wire()
        assert wire["hovered"] == {"background": "#cc0000"}

    def test_base_field(self) -> None:
        s = StyleMap().with_base("primary")
        wire = s.to_wire()
        assert wire["base"] == "primary"


class TestThemeToWire:
    def test_builtin(self) -> None:
        assert Theme.builtin("dark").to_wire() == "dark"

    def test_custom(self) -> None:
        t = Theme.custom("My Theme", primary="#7aa2f7")
        wire = t.to_wire()
        assert isinstance(wire, dict)
        assert wire["name"] == "My Theme"
        assert wire["primary"] == "#7aa2f7"

    def test_custom_with_base(self) -> None:
        t = Theme.custom("Nord+", base="nord", primary="#88c0d0")
        wire = t.to_wire()
        assert isinstance(wire, dict)
        assert wire["base"] == "nord"


class TestA11yToWire:
    def test_empty(self) -> None:
        assert A11y().to_wire() == {}

    def test_partial(self) -> None:
        a = A11y(role="button", label="Submit")
        wire = a.to_wire()
        assert wire == {"role": "button", "label": "Submit"}

    def test_excludes_none(self) -> None:
        a = A11y(label="test")
        wire = a.to_wire()
        assert "role" not in wire
        assert "hidden" not in wire
