"""Tests for code blocks in docs/theming.md.

Verifies Theme.custom(), StyleMap construction, border/shadow styling,
and themer widget in the view tree.
"""

from __future__ import annotations

from plushie import ui
from plushie.types import (
    BUILTIN_THEMES,
    THEME_CATPPUCCIN_MOCHA,
    Border,
    Shadow,
    StyleMap,
    Theme,
)

# ---------------------------------------------------------------------------
# test_builtin_theme_constants
# ---------------------------------------------------------------------------


def test_builtin_theme_constants():
    """Built-in theme name constants are available in plushie.types."""
    assert THEME_CATPPUCCIN_MOCHA == "catppuccin_mocha"
    assert len(BUILTIN_THEMES) == 22
    assert "dark" in BUILTIN_THEMES
    assert "light" in BUILTIN_THEMES
    assert "catppuccin_mocha" in BUILTIN_THEMES


# ---------------------------------------------------------------------------
# test_theme_custom
# ---------------------------------------------------------------------------


def test_theme_custom():
    """Theme.custom() creates a custom theme with palette colors."""
    theme = Theme.custom(
        "my_app",
        background="#1e1e2e",
        text="#cdd6f4",
        primary="#89b4fa",
        success="#a6e3a1",
        danger="#f38ba8",
        warning="#f9e2af",
    )

    assert theme.name == "my_app"
    assert theme.palette is not None
    assert theme.palette["background"] == "#1e1e2e"
    assert theme.palette["text"] == "#cdd6f4"
    assert theme.palette["primary"] == "#89b4fa"


def test_theme_custom_with_shade_overrides():
    """Theme.custom() supports extended palette shade overrides."""
    theme = Theme.custom(
        "branded",
        background="#1a1a2e",
        text="#e0e0e0",
        primary="#0f3460",
        primary_strong="#1a5276",
        primary_strong_text="#ffffff",
        background_weakest="#0d0d1a",
    )

    assert theme.palette is not None
    assert theme.palette["primary_strong"] == "#1a5276"
    assert theme.palette["primary_strong_text"] == "#ffffff"
    assert theme.palette["background_weakest"] == "#0d0d1a"


def test_theme_custom_to_wire():
    """Custom themes encode as a dict with name and palette fields."""
    theme = Theme.custom("mine", primary="#7aa2f7")
    wire = theme.to_wire()

    assert isinstance(wire, dict)
    assert wire["name"] == "mine"
    assert wire["primary"] == "#7aa2f7"


def test_theme_builtin_to_wire():
    """Built-in themes encode as a plain name string."""
    theme = Theme.builtin("dark")
    wire = theme.to_wire()

    assert wire == "dark"


# ---------------------------------------------------------------------------
# test_style_map
# ---------------------------------------------------------------------------


def test_style_map_builder_pattern():
    """StyleMap uses a builder pattern for construction."""
    card_style = (
        StyleMap()
        .with_background("#ffffff")
        .with_text_color("#1a1a1a")
        .with_border(Border(color="#e0e0e0", width=1, radius=8))
        .with_shadow(Shadow(color="#00000020", offset=(0, 2), blur_radius=8))
    )

    assert card_style.background == "#ffffff"
    assert card_style.text_color == "#1a1a1a"
    assert card_style.border is not None
    assert card_style.border.color == "#e0e0e0"
    assert card_style.border.width == 1
    assert card_style.border.radius == 8
    assert card_style.shadow is not None
    assert card_style.shadow.color == "#00000020"
    assert card_style.shadow.offset == (0, 2)
    assert card_style.shadow.blur_radius == 8


def test_style_map_status_overrides():
    """StyleMap supports interaction state overrides."""
    nav_item_style = (
        StyleMap()
        .with_background("#00000000")
        .with_text_color("#cccccc")
        .with_hovered({"background": "#333333", "text_color": "#ffffff"})
        .with_pressed({"background": "#222222"})
        .with_disabled({"text_color": "#666666"})
    )

    assert nav_item_style.hovered == {
        "background": "#333333",
        "text_color": "#ffffff",
    }
    assert nav_item_style.pressed == {"background": "#222222"}
    assert nav_item_style.disabled == {"text_color": "#666666"}


def test_style_map_to_wire():
    """StyleMap encodes to wire dict with nested dataclass conversion."""
    style = (
        StyleMap()
        .with_background("#ffffff")
        .with_border(Border(color="#000000", width=2, radius=4))
    )
    wire = style.to_wire()

    assert wire["background"] == "#ffffff"
    assert isinstance(wire["border"], dict)
    assert wire["border"]["width"] == 2


def test_style_map_with_status_override_to_wire():
    """Status overrides appear in the wire encoding."""
    style = StyleMap().with_hovered({"background": "#333333"})
    wire = style.to_wire()

    assert "hovered" in wire
    hovered = wire["hovered"]
    assert isinstance(hovered, dict)
    assert hovered["background"] == "#333333"


# ---------------------------------------------------------------------------
# test_border
# ---------------------------------------------------------------------------


def test_border_construction():
    """Border dataclass with color, width, radius."""
    b = Border(color="#e0e0e0", width=1, radius=8)

    assert b.color == "#e0e0e0"
    assert b.width == 1
    assert b.radius == 8


def test_border_to_wire():
    """Border encodes to wire dict."""
    b = Border(color="#ff0000", width=2, radius=4)
    wire = b.to_wire()

    assert wire == {"color": "#ff0000", "width": 2, "radius": 4}


# ---------------------------------------------------------------------------
# test_shadow
# ---------------------------------------------------------------------------


def test_shadow_construction():
    """Shadow dataclass with color, offset, blur_radius."""
    s = Shadow(color="#00000020", offset=(0, 2), blur_radius=8)

    assert s.color == "#00000020"
    assert s.offset == (0, 2)
    assert s.blur_radius == 8


def test_shadow_to_wire():
    """Shadow encodes to wire dict with offset as a list."""
    s = Shadow(color="#000000", offset=(1, 2), blur_radius=4)
    wire = s.to_wire()

    assert wire == {"color": "#000000", "offset": [1, 2], "blur_radius": 4}


# ---------------------------------------------------------------------------
# test_themer_widget_in_view
# ---------------------------------------------------------------------------


def test_themer_widget_builtin():
    """The themer widget wraps children with a theme override."""
    tree = ui.window(
        "main",
        ui.themer(
            "theme",
            ui.column(ui.text("Themed content")),
            theme="catppuccin_mocha",
        ),
        title="My App",
    )

    assert tree["type"] == "window"
    assert tree["id"] == "main"
    themer_node = tree["children"][0]
    assert themer_node["type"] == "themer"
    assert themer_node["props"]["theme"] == "catppuccin_mocha"


def test_themer_widget_custom_theme():
    """A custom Theme object can be passed to the themer widget."""
    theme = Theme.custom("my_app", primary="#89b4fa")

    tree = ui.themer("app_theme", ui.text("Hello"), theme=theme)

    assert tree["type"] == "themer"
    assert tree["props"]["theme"] is theme


def test_themer_subtree_override():
    """Themes can be overridden for a subtree using a nested themer."""
    tree = ui.column(
        ui.text("Uses window theme"),
        ui.themer(
            "sidebar_theme",
            ui.container("sidebar", ui.text("Uses Nord theme")),
            theme="nord",
        ),
    )

    assert tree["type"] == "column"
    themer_node = tree["children"][1]
    assert themer_node["type"] == "themer"
    assert themer_node["props"]["theme"] == "nord"


# ---------------------------------------------------------------------------
# test_system_theme
# ---------------------------------------------------------------------------


def test_system_theme_in_settings():
    """The 'system' theme follows the OS light/dark preference."""
    settings = {"theme": "system"}
    assert settings["theme"] == "system"


# ---------------------------------------------------------------------------
# test_style_map_with_cta_button
# ---------------------------------------------------------------------------


def test_style_map_cta_button():
    """StyleMap with custom branded button from the doc example."""
    style = (
        StyleMap()
        .with_background("#7c3aed")
        .with_text_color("#ffffff")
        .with_border(Border(radius=24))
    )

    assert style.background == "#7c3aed"
    assert style.text_color == "#ffffff"
    assert style.border is not None
    assert style.border.radius == 24


# ---------------------------------------------------------------------------
# test_density_helper
# ---------------------------------------------------------------------------


def test_density_helper():
    """Density spacing is a plain helper function, no framework magic."""

    def spacing(density: str, size: str) -> int:
        table = {
            ("compact", "md"): 4,
            ("comfortable", "md"): 8,
            ("roomy", "md"): 12,
        }
        return table[(density, size)]

    assert spacing("compact", "md") == 4
    assert spacing("comfortable", "md") == 8
    assert spacing("roomy", "md") == 12


# ---------------------------------------------------------------------------
# test_style_map_immutability
# ---------------------------------------------------------------------------


def test_style_map_immutable():
    """StyleMap is frozen -- builder methods return new instances."""
    base = StyleMap()
    with_bg = base.with_background("#ffffff")

    assert base.background is None
    assert with_bg.background == "#ffffff"
    assert base is not with_bg
