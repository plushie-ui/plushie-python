"""Shared types for the plushie SDK.

Type aliases, dataclasses, and helper functions used across the entire
framework. All dataclasses use ``frozen=True, slots=True`` for
immutability and memory efficiency.

Covers: Length, Padding, Color, Alignment, Border, Shadow, Gradient,
Font, StyleMap, Theme, A11y, HelloInfo, KeyModifiers, and various
string-literal type aliases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

type Length = int | float | Literal["fill", "shrink"] | dict[str, int]
"""Widget size value.

Accepted forms:
- Numeric pixel value (``int`` or ``float``)
- ``"fill"`` -- expand to fill available space
- ``"shrink"`` -- shrink to content size
- ``{"fill_portion": n}`` -- fill a weighted portion of available space
"""

type Padding = int | float | tuple[float, float] | tuple[float, float, float, float]
"""Padding specification.

Accepted forms:
- Uniform: single number applied to all sides
- Vertical/horizontal: ``(vertical, horizontal)``
- Per-side: ``(top, right, bottom, left)``
"""

type Color = str
"""Canonical hex color string (``#rrggbb`` or ``#rrggbbaa``).

Use the ``Colors`` helper class for constructors and named color lookup.
"""

type Alignment = Literal["start", "center", "end"]
"""Alignment value for ``align_x`` and ``align_y`` widget props."""

type WindowLevel = Literal["normal", "always_on_top", "always_on_bottom"]
"""Window stacking level."""

type WindowMode = Literal["windowed", "fullscreen", "hidden"]
"""Window display mode."""

type ContentFit = Literal["contain", "cover", "fill", "none", "scale_down"]
"""Image/SVG content fitting strategy."""

type Direction = Literal["horizontal", "vertical"]
"""Layout direction."""

type FilterMethod = Literal["linear", "nearest"]
"""Image filter method."""

type Shaping = Literal["basic", "advanced"]
"""Text shaping strategy."""

type Wrapping = Literal["none", "word", "glyph", "word_or_glyph"]
"""Text wrapping strategy."""

type Position = Literal["top", "bottom", "left", "right", "follow_cursor"]
"""Tooltip/overlay position."""

type Anchor = Literal["start", "end"]
"""Scrollable anchor position."""

# ---------------------------------------------------------------------------
# KeyModifiers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeyModifiers:
    """Keyboard modifier state accompanying key and mouse events.

    All fields default to ``False``.
    """

    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    logo: bool = False
    command: bool = False


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

# All 148 CSS Color Module Level 4 named colors plus transparent.
# Sorted alphabetically.
NAMED_COLORS: dict[str, str] = {
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgreen": "#006400",
    "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "grey": "#808080",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90",
    "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "rebeccapurple": "#663399",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "transparent": "#00000000",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}

_HEX_RE = re.compile(r"\A[0-9a-fA-F]+\z")


class Colors:
    """Color construction and normalization utilities.

    All methods return canonical hex strings (``#rrggbb`` or ``#rrggbbaa``).
    """

    @staticmethod
    def from_rgb(r: int, g: int, b: int, /) -> str:
        """Create a color from 0-255 RGB integer values.

        >>> Colors.from_rgb(255, 128, 0)
        '#ff8000'
        """
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def from_rgba(r: int, g: int, b: int, a: float, /) -> str:
        """Create a color from 0-255 RGB integers and a 0.0-1.0 alpha float.

        >>> Colors.from_rgba(255, 0, 0, 1.0)
        '#ff0000ff'
        >>> Colors.from_rgba(0, 0, 0, 0.0)
        '#00000000'
        """
        alpha_byte = round(max(0.0, min(1.0, a)) * 255)
        return f"#{r:02x}{g:02x}{b:02x}{alpha_byte:02x}"

    @staticmethod
    def from_hex(hex_str: str, /) -> str:
        """Normalize a hex string (with or without leading ``#``) to canonical form.

        Supports 3, 4, 6, and 8 character hex strings. Short forms (3/4 chars)
        are expanded by doubling each digit.

        >>> Colors.from_hex("#FF8800")
        '#ff8800'
        >>> Colors.from_hex("abc")
        '#aabbcc'
        >>> Colors.from_hex("#abcd")
        '#aabbccdd'
        """
        raw = hex_str.lstrip("#")
        if len(raw) == 3:
            raw = raw[0] * 2 + raw[1] * 2 + raw[2] * 2
        elif len(raw) == 4:
            raw = raw[0] * 2 + raw[1] * 2 + raw[2] * 2 + raw[3] * 2
        if len(raw) not in (6, 8):
            raise ValueError(f"invalid hex color length: {hex_str!r}")
        if not _HEX_RE.match(raw):
            raise ValueError(f"invalid hex color digits: {hex_str!r}")
        return f"#{raw.lower()}"

    @staticmethod
    def cast(value: str, /) -> str:
        """Normalize any supported color input to a canonical hex string.

        Accepts:
        - Named CSS colors (case-insensitive): ``"red"``, ``"CornflowerBlue"``
        - Hex strings: ``"#rrggbb"``, ``"#rrggbbaa"``, ``"#rgb"``, ``"#rgba"``
        - Bare hex: ``"ff8800"``

        Raises ``ValueError`` for unrecognized color names or invalid hex.

        >>> Colors.cast("red")
        '#ff0000'
        >>> Colors.cast("#FF0000")
        '#ff0000'
        >>> Colors.cast("cornflowerblue")
        '#6495ed'
        """
        lowered = value.lower()
        named = NAMED_COLORS.get(lowered)
        if named is not None:
            return named
        # Try as hex
        return Colors.from_hex(value)

    @staticmethod
    def named_colors() -> dict[str, str]:
        """Return a copy of all supported named colors.

        Keys are lowercase names, values are canonical hex strings.
        """
        return dict(NAMED_COLORS)


# ---------------------------------------------------------------------------
# Border
# ---------------------------------------------------------------------------

type RadiusCorners = dict[str, float]
"""Per-corner radius: ``{"top_left", "top_right", "bottom_right", "bottom_left"}``."""


@dataclass(frozen=True, slots=True)
class Border:
    """Border specification for container and widget styling.

    All fields are optional with sensible defaults. Construct directly
    or use ``replace()`` to derive new instances (the dataclass is frozen).

    The ``radius`` field accepts a uniform number or a per-corner dict
    with keys ``top_left``, ``top_right``, ``bottom_right``, ``bottom_left``.
    """

    color: str | None = None
    width: float = 0
    radius: float | dict[str, float] = 0

    @staticmethod
    def radius_corners(
        top_left: float = 0,
        top_right: float = 0,
        bottom_right: float = 0,
        bottom_left: float = 0,
    ) -> dict[str, float]:
        """Create a per-corner radius dict.

        >>> Border.radius_corners(8, 8, 0, 0)
        {'top_left': 8, 'top_right': 8, 'bottom_right': 0, 'bottom_left': 0}
        """
        return {
            "top_left": top_left,
            "top_right": top_right,
            "bottom_right": bottom_right,
            "bottom_left": bottom_left,
        }


# ---------------------------------------------------------------------------
# Shadow
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Shadow:
    """Shadow specification for widget styling.

    The ``offset`` is an ``(x, y)`` tuple. Color defaults to black.
    """

    color: str = "#000000"
    offset: tuple[float, float] = (0, 0)
    blur_radius: float = 0


# ---------------------------------------------------------------------------
# Gradient
# ---------------------------------------------------------------------------

type GradientStop = tuple[float, str]
"""A gradient color stop: ``(offset, color)`` where offset is 0.0-1.0."""


@dataclass(frozen=True, slots=True)
class Gradient:
    """Linear gradient background.

    Use the ``linear`` factory for convenient construction. Stops are
    ``(offset, color)`` tuples where offset ranges from 0.0 to 1.0.

    Wire format produces a dict with ``type``, ``angle``, and ``stops`` keys.
    """

    angle: float
    stops: tuple[tuple[float, str], ...]

    @staticmethod
    def linear(
        angle: float,
        stops: list[tuple[float, str]] | tuple[tuple[float, str], ...],
    ) -> Gradient:
        """Create a linear gradient.

        Colors in stops are cast through ``Colors.cast`` for named color
        support.

        >>> g = Gradient.linear(90, [(0.0, "#ff0000"), (1.0, "#0000ff")])
        >>> g.angle
        90
        >>> len(g.stops)
        2
        """
        normalized: list[tuple[float, str]] = []
        for offset, color in stops:
            normalized.append((offset, Colors.cast(color)))
        return Gradient(angle=angle, stops=tuple(normalized))


# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------

type FontWeight = Literal[
    "thin",
    "extra_light",
    "light",
    "normal",
    "medium",
    "semi_bold",
    "bold",
    "extra_bold",
    "black",
]
"""Font weight as a lowercase string matching iced's ``font::Weight`` variants."""

type FontStyle = Literal["normal", "italic", "oblique"]
"""Font style."""

type FontStretch = Literal[
    "ultra_condensed",
    "extra_condensed",
    "condensed",
    "semi_condensed",
    "normal",
    "semi_expanded",
    "expanded",
    "extra_expanded",
    "ultra_expanded",
]
"""Font stretch/width."""


@dataclass(frozen=True, slots=True)
class Font:
    """Font specification with family, weight, style, and stretch.

    All fields are optional. ``None`` means "use the widget default".

    The wire format encodes weight/style/stretch as PascalCase strings
    (e.g. ``"SemiBold"``, ``"UltraCondensed"``).
    """

    family: str | None = None
    weight: FontWeight | None = None
    style: FontStyle | None = None
    stretch: FontStretch | None = None


# ---------------------------------------------------------------------------
# StyleMap
# ---------------------------------------------------------------------------

type StatusOverride = dict[str, str | Border | Shadow | Gradient | None]
"""Partial style override for an interaction state.

Supported keys: ``background``, ``text_color``, ``border``, ``shadow``.
"""


@dataclass(frozen=True, slots=True)
class StyleMap:
    """Per-instance widget styling that crosses the wire as a plain map.

    Allows overriding visual properties on individual widget instances.
    Status overrides (``hovered``, ``pressed``, ``disabled``, ``focused``)
    apply partial changes for those interaction states.

    Since StyleMap is frozen, use ``with_*`` builder methods which return
    new instances via ``dataclasses.replace()``.
    """

    base: str | None = None
    background: str | Gradient | None = None
    text_color: str | None = None
    border: Border | None = None
    shadow: Shadow | None = None
    hovered: dict[str, str | Border | Shadow | Gradient | None] | None = None
    pressed: dict[str, str | Border | Shadow | Gradient | None] | None = None
    disabled: dict[str, str | Border | Shadow | Gradient | None] | None = None
    focused: dict[str, str | Border | Shadow | Gradient | None] | None = None

    def with_base(self, preset: str) -> StyleMap:
        """Return a new StyleMap extending from the given base preset."""
        return replace(self, base=preset)

    def with_background(self, background: str | Gradient) -> StyleMap:
        """Return a new StyleMap with the given background.

        Accepts a hex color string, named color, or a ``Gradient``.
        """
        if isinstance(background, Gradient):
            return replace(self, background=background)
        return replace(self, background=Colors.cast(background))

    def with_text_color(self, color: str) -> StyleMap:
        """Return a new StyleMap with the given text color."""
        return replace(self, text_color=Colors.cast(color))

    def with_border(self, border: Border) -> StyleMap:
        """Return a new StyleMap with the given border."""
        return replace(self, border=border)

    def with_shadow(self, shadow: Shadow) -> StyleMap:
        """Return a new StyleMap with the given shadow."""
        return replace(self, shadow=shadow)

    def with_hovered(
        self, override: dict[str, str | Border | Shadow | Gradient | None]
    ) -> StyleMap:
        """Return a new StyleMap with the given hovered state override."""
        return replace(self, hovered=override)

    def with_pressed(
        self, override: dict[str, str | Border | Shadow | Gradient | None]
    ) -> StyleMap:
        """Return a new StyleMap with the given pressed state override."""
        return replace(self, pressed=override)

    def with_disabled(
        self, override: dict[str, str | Border | Shadow | Gradient | None]
    ) -> StyleMap:
        """Return a new StyleMap with the given disabled state override."""
        return replace(self, disabled=override)

    def with_focused(
        self, override: dict[str, str | Border | Shadow | Gradient | None]
    ) -> StyleMap:
        """Return a new StyleMap with the given focused state override."""
        return replace(self, focused=override)


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

# All 22 built-in iced theme names.
THEME_LIGHT: str = "light"
THEME_DARK: str = "dark"
THEME_DRACULA: str = "dracula"
THEME_NORD: str = "nord"
THEME_SOLARIZED_LIGHT: str = "solarized_light"
THEME_SOLARIZED_DARK: str = "solarized_dark"
THEME_GRUVBOX_LIGHT: str = "gruvbox_light"
THEME_GRUVBOX_DARK: str = "gruvbox_dark"
THEME_CATPPUCCIN_LATTE: str = "catppuccin_latte"
THEME_CATPPUCCIN_FRAPPE: str = "catppuccin_frappe"
THEME_CATPPUCCIN_MACCHIATO: str = "catppuccin_macchiato"
THEME_CATPPUCCIN_MOCHA: str = "catppuccin_mocha"
THEME_TOKYO_NIGHT: str = "tokyo_night"
THEME_TOKYO_NIGHT_STORM: str = "tokyo_night_storm"
THEME_TOKYO_NIGHT_LIGHT: str = "tokyo_night_light"
THEME_KANAGAWA_WAVE: str = "kanagawa_wave"
THEME_KANAGAWA_DRAGON: str = "kanagawa_dragon"
THEME_KANAGAWA_LOTUS: str = "kanagawa_lotus"
THEME_MOONFLY: str = "moonfly"
THEME_NIGHTFLY: str = "nightfly"
THEME_OXOCARBON: str = "oxocarbon"
THEME_FERRA: str = "ferra"

BUILTIN_THEMES: tuple[str, ...] = (
    THEME_LIGHT,
    THEME_DARK,
    THEME_DRACULA,
    THEME_NORD,
    THEME_SOLARIZED_LIGHT,
    THEME_SOLARIZED_DARK,
    THEME_GRUVBOX_LIGHT,
    THEME_GRUVBOX_DARK,
    THEME_CATPPUCCIN_LATTE,
    THEME_CATPPUCCIN_FRAPPE,
    THEME_CATPPUCCIN_MACCHIATO,
    THEME_CATPPUCCIN_MOCHA,
    THEME_TOKYO_NIGHT,
    THEME_TOKYO_NIGHT_STORM,
    THEME_TOKYO_NIGHT_LIGHT,
    THEME_KANAGAWA_WAVE,
    THEME_KANAGAWA_DRAGON,
    THEME_KANAGAWA_LOTUS,
    THEME_MOONFLY,
    THEME_NIGHTFLY,
    THEME_OXOCARBON,
    THEME_FERRA,
)
"""All built-in theme names recognized by the renderer."""


@dataclass(frozen=True, slots=True)
class Theme:
    """Theme specification: either a built-in name or a custom palette.

    For built-in themes, just pass the name string. For custom themes,
    use the ``custom`` factory method which accepts a name and palette
    colors.

    The ``palette`` dict, when present, holds the custom palette colors
    and shade overrides. When ``None``, this is a built-in theme.
    """

    name: str
    palette: dict[str, str] | None = None

    @staticmethod
    def builtin(name: str) -> Theme:
        """Create a built-in theme reference.

        >>> Theme.builtin("dark")
        Theme(name='dark', palette=None)
        """
        return Theme(name=name)

    @staticmethod
    def custom(
        name: str,
        *,
        base: str | None = None,
        background: str | None = None,
        text: str | None = None,
        primary: str | None = None,
        success: str | None = None,
        danger: str | None = None,
        warning: str | None = None,
        **shade_overrides: str,
    ) -> Theme:
        """Create a custom theme with palette colors and optional shade overrides.

        Core palette colors (``background``, ``text``, ``primary``, ``success``,
        ``danger``, ``warning``) and any shade override keys (e.g.
        ``primary_strong``, ``background_weakest``, ``primary_strong_text``)
        are normalized to canonical hex via ``Colors.cast``.

        The ``base`` parameter specifies a built-in theme to extend from
        instead of starting from scratch.

        >>> t = Theme.custom("My Theme", primary="#7aa2f7", danger="red")
        >>> t.name
        'My Theme'
        >>> t.palette is not None
        True
        """
        palette: dict[str, str] = {}
        if base is not None:
            palette["base"] = base
        core_fields = {
            "background": background,
            "text": text,
            "primary": primary,
            "success": success,
            "danger": danger,
            "warning": warning,
        }
        for key, value in core_fields.items():
            if value is not None:
                palette[key] = Colors.cast(value)
        for key, value in shade_overrides.items():
            palette[key] = Colors.cast(value)
        return Theme(name=name, palette=palette if palette else None)


# ---------------------------------------------------------------------------
# A11y
# ---------------------------------------------------------------------------

type A11yRole = Literal[
    "alert",
    "alert_dialog",
    "button",
    "canvas",
    "check_box",
    "combo_box",
    "dialog",
    "document",
    "generic_container",
    "group",
    "heading",
    "image",
    "label",
    "link",
    "list",
    "list_item",
    "menu",
    "menu_bar",
    "menu_item",
    "meter",
    "multiline_text_input",
    "navigation",
    "progress_indicator",
    "radio_button",
    "region",
    "scroll_bar",
    "scroll_view",
    "search",
    "separator",
    "slider",
    "static_text",
    "status",
    "switch",
    "tab",
    "tab_list",
    "tab_panel",
    "table",
    "text_input",
    "toolbar",
    "tooltip",
    "tree",
    "tree_item",
    "window",
]
"""Accessibility role overriding the widget's auto-inferred role."""

type A11yLive = Literal["polite", "assertive"]
"""Live region announcement urgency."""

type A11yOrientation = Literal["horizontal", "vertical"]
"""Widget orientation for assistive technology."""

type A11yHasPopup = Literal["listbox", "menu", "dialog", "tree", "grid"]
"""Popup type indicator for assistive technology."""


@dataclass(frozen=True, slots=True)
class A11y:
    """Accessibility annotation for widget nodes.

    Overrides the auto-inferred accessibility semantics on the renderer
    side. Most widgets need no explicit annotation -- the renderer derives
    roles and labels from widget types and props automatically.

    All fields default to ``None`` (unset = use auto-inferred value).
    """

    role: A11yRole | None = None
    label: str | None = None
    description: str | None = None
    live: A11yLive | None = None
    hidden: bool | None = None
    expanded: bool | None = None
    required: bool | None = None
    level: int | None = None
    busy: bool | None = None
    invalid: bool | None = None
    modal: bool | None = None
    read_only: bool | None = None
    mnemonic: str | None = None
    toggled: bool | None = None
    selected: bool | None = None
    value: str | None = None
    orientation: A11yOrientation | None = None
    labelled_by: str | None = None
    described_by: str | None = None
    error_message: str | None = None
    disabled: bool | None = None
    position_in_set: int | None = None
    size_of_set: int | None = None
    has_popup: A11yHasPopup | None = None


# ---------------------------------------------------------------------------
# HelloInfo
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HelloInfo:
    """Information from the renderer's hello handshake message.

    Sent by the renderer immediately after receiving Settings. Contains
    protocol version, renderer capabilities, and registered extensions.
    """

    protocol: int
    version: str
    name: str
    mode: str
    backend: str
    transport: str
    extensions: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "BUILTIN_THEMES",
    "NAMED_COLORS",
    "THEME_CATPPUCCIN_FRAPPE",
    "THEME_CATPPUCCIN_LATTE",
    "THEME_CATPPUCCIN_MACCHIATO",
    "THEME_CATPPUCCIN_MOCHA",
    "THEME_DARK",
    "THEME_DRACULA",
    "THEME_FERRA",
    "THEME_GRUVBOX_DARK",
    "THEME_GRUVBOX_LIGHT",
    "THEME_KANAGAWA_DRAGON",
    "THEME_KANAGAWA_LOTUS",
    "THEME_KANAGAWA_WAVE",
    "THEME_LIGHT",
    "THEME_MOONFLY",
    "THEME_NIGHTFLY",
    "THEME_NORD",
    "THEME_OXOCARBON",
    "THEME_SOLARIZED_DARK",
    "THEME_SOLARIZED_LIGHT",
    "THEME_TOKYO_NIGHT",
    "THEME_TOKYO_NIGHT_LIGHT",
    "THEME_TOKYO_NIGHT_STORM",
    "A11y",
    "A11yHasPopup",
    "A11yLive",
    "A11yOrientation",
    "A11yRole",
    "Alignment",
    "Anchor",
    "Border",
    "Color",
    "Colors",
    "ContentFit",
    "Direction",
    "FilterMethod",
    "Font",
    "FontStretch",
    "FontStyle",
    "FontWeight",
    "Gradient",
    "GradientStop",
    "HelloInfo",
    "KeyModifiers",
    "Length",
    "Padding",
    "Position",
    "RadiusCorners",
    "Shadow",
    "Shaping",
    "StatusOverride",
    "StyleMap",
    "Theme",
    "WindowLevel",
    "WindowMode",
    "Wrapping",
]
