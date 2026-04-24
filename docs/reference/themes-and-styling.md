# Themes and Styling

Plushie's visual styling has three layers. Themes set the overall
palette for a window or subtree. Style maps override appearance on
individual widget instances. Value types (`Color`, `Border`, `Shadow`,
`Gradient`, `Font`) are the building blocks shared across both. All
of this lives in `plushie.types`, with the `themer` container exposed
from `plushie.ui` and the per-app default wired through
`App.settings`.

Style values cross the wire as plain dicts. `Border`, `Shadow`,
`Gradient`, `StyleMap`, and `Theme` are frozen dataclasses with a
`to_wire()` method that the runtime calls during tree normalization.
You work with dataclass instances in view code; encoding is deferred
to the single pass before the tree hits the wire.

## Color

Colors flow through every styling surface: widget props like
`background` and `color`, the `Border.color` field, shadow tints,
gradient stops, theme seeds, style map backgrounds. A color is always
a `str` at rest, in canonical `#rrggbb` or `#rrggbbaa` form. The
`Colors` helper class (from `plushie.types`) constructs and
normalizes them.

```python
from plushie.types import Colors

Colors.from_rgb(255, 128, 0)         # "#ff8000"
Colors.from_rgba(255, 0, 0, 0.5)     # "#ff000080"
Colors.from_hex("#FF8800")           # "#ff8800"
Colors.from_hex("abc")               # "#aabbcc"
Colors.from_hex("#abcd")             # "#aabbccdd"
Colors.cast("red")                   # "#ff0000"
Colors.cast("CornflowerBlue")        # "#6495ed"
```

| Method | Signature | Purpose |
|---|---|---|
| `Colors.from_rgb` | `(r, g, b)` with 0-255 ints | Build a canonical hex from integer channels. |
| `Colors.from_rgba` | `(r, g, b, a)` with a 0.0-1.0 alpha float | Build with alpha. Alpha is clamped to the 0.0-1.0 range. |
| `Colors.from_hex` | `"#rrggbb"` / `"rrggbb"` / `"#rgb"` / `"#rgba"` | Normalize and expand shorthand. Missing `#` is tolerated. |
| `Colors.cast` | any named CSS color or hex string | Catch-all normalizer. Runs named-color lookup first, falls back to `from_hex`. |
| `Colors.named_colors` | `()` | Returns a copy of the full named-color map. |

`Colors.cast` is what the SDK itself uses when normalizing user input
on the way to the wire. `Colors.from_hex` raises `ValueError` for
unsupported lengths or non-hex digits. Short forms (3 or 4
characters) expand by doubling each digit, matching CSS semantics.

### Named colors

Plushie recognizes every color from the
[CSS Color Module Level 4](https://www.w3.org/TR/css-color-4/#named-colors)
named-color list plus `"transparent"`. Lookups are case-insensitive,
so `"cornflowerblue"` and `"CornflowerBlue"` resolve identically.
Grey/gray aliases are both supported (`"darkgray"` and `"darkgrey"`
both return `#a9a9a9`).

Everywhere a color is accepted you can pass the raw name string:

```python
ui.container("card", ui.text("hello"), background="cornflowerblue")
```

The string passes through `Colors.cast` during encoding. Pick any of:
`"red"`, `"royalblue"`, `"seagreen"`, `"tomato"`, `"rebeccapurple"`,
`"transparent"`. Use `Colors.named_colors()` to enumerate them
programmatically.

## Border

```python
from plushie.types import Border

Border(color="#e5e7eb", width=1, radius=8)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `color` | `str \| None` | `None` | Border color in any `Colors.cast` form. `None` means no border color. |
| `width` | `float` | `0` | Border width in pixels. Negative values raise `ValueError` at encode time. |
| `radius` | `float \| dict[str, float]` | `0` | Uniform corner radius or a per-corner dict. |

### Per-corner radius

The `radius` field accepts a `RadiusCorners` dict with keys
`top_left`, `top_right`, `bottom_right`, `bottom_left`:

```python
from plushie.types import Border

Border(
    color="#ccc",
    width=1,
    radius=Border.radius_corners(top_left=8, top_right=8),
)
```

`Border.radius_corners(...)` is a small convenience that returns the
dict with explicit zeros for the corners you omit. The wire shape for
the `radius` field is either a number (uniform) or a full corners
dict, and the encoder rejects negative values on any corner.

## Shadow

```python
from plushie.types import Shadow

Shadow(color="#0000001a", offset=(0, 4), blur_radius=8)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `color` | `str` | `"#000000"` | Shadow color. |
| `offset` | `(float, float)` | `(0, 0)` | X and Y offset in pixels. |
| `blur_radius` | `float` | `0` | Blur radius in pixels. |

The wire shape encodes `offset` as a two-element list. `Shadow` is a
frozen dataclass; derive new instances with
`dataclasses.replace(existing, blur_radius=12)`.

## Gradient

`Gradient` describes a linear gradient in normalized coordinates on
the unit square (`(0, 0)` top-left to `(1, 1)` bottom-right). Use it
anywhere a background is accepted: `container(background=...)`,
`StyleMap.background`, canvas fills.

```python
from plushie.types import Gradient

Gradient.linear(
    start=(0, 0),
    end=(1, 1),
    stops=[(0.0, "#3b82f6"), (1.0, "#1d4ed8")],
)
```

| Factory | Signature | Purpose |
|---|---|---|
| `Gradient.linear` | `(start, end, stops)` | Explicit unit-square coordinates. |
| `Gradient.linear_from_angle` | `(angle_degrees, stops)` | Angle-based construction. 0 points right, 90 points down. |

A stop is a `(offset, color)` tuple where `offset` is in the
0.0-1.0 range and `color` is any `Colors.cast` input. The factory
normalizes every stop color to canonical hex.

```python
from plushie import ui
from plushie.types import Gradient

ui.container(
    "hero",
    ui.text("title", "Welcome"),
    background=Gradient.linear_from_angle(
        135, [(0.0, "#667eea"), (1.0, "#764ba2")]
    ),
    padding=24,
)
```

The wire form is `{"type": "linear", "start": [x, y], "end": [x, y],
"stops": [[offset, color], ...]}`.

## Font

```python
from plushie.types import Font

Font(family="Inter", weight="semi_bold", style="italic")
```

Font is documented in full in the
[Built-in Widgets reference](built-in-widgets.md) under the text
widgets. In the styling context, note only that `Font` accepts
optional `family`, `weight`, `style`, and `stretch` fields, each
defaulting to `None` (widget default). Weight, style, and stretch
are lowercase string literals; the full enumerations live in
`plushie.types` as `FontWeight`, `FontStyle`, and `FontStretch`.

## StyleMap

`StyleMap` overrides the visual properties of a single widget
instance. Themes set the baseline palette; style maps customise one
button, one container, one tooltip.

```python
from plushie.types import Border, Shadow, StyleMap

style = (
    StyleMap()
    .with_base("primary")
    .with_background("#3b82f6")
    .with_text_color("#ffffff")
    .with_border(Border(color="#2563eb", width=1, radius=6))
    .with_shadow(Shadow(color="#0000001a", offset=(0, 4), blur_radius=4))
    .with_hovered({"background": "#2563eb"})
    .with_pressed({"background": "#1d4ed8"})
    .with_disabled({"background": "#9ca3af", "text_color": "#6b7280"})
    .with_focused({"border": Border(color="#3b82f6", width=2)})
)
```

The `with_*` methods return new instances (the dataclass is frozen).
You can also construct a `StyleMap(...)` directly by passing the
fields as kwargs.

| Field | Type | Purpose |
|---|---|---|
| `base` | `str \| None` | Named preset to extend (`"primary"`, `"danger"`, etc.). |
| `background` | `str \| Gradient \| None` | Background fill. |
| `text_color` | `str \| None` | Foreground text color. |
| `border` | `Border \| None` | Border specification. |
| `shadow` | `Shadow \| None` | Drop shadow. |
| `hovered` | `StatusOverride \| None` | Overrides applied when the widget is hovered. |
| `pressed` | `StatusOverride \| None` | Overrides applied while pressed. |
| `disabled` | `StatusOverride \| None` | Overrides when disabled. |
| `focused` | `StatusOverride \| None` | Overrides when focused. |

### Status overrides

A `StatusOverride` is a `dict[str, str | Border | Shadow | Gradient |
None]` accepting the keys `background`, `text_color`, `border`, and
`shadow`. Only keys you specify change for that status; everything
else inherits from the base fields.

```python
StyleMap().with_hovered({"background": "#2563eb"})
StyleMap().with_pressed({"background": "#1d4ed8", "text_color": "#ffffff"})
```

Nested `Border`, `Shadow`, and `Gradient` dataclasses inside an
override are encoded recursively on the way to the wire.

### Named presets

The renderer ships a handful of named presets that pick sensible
values from the active theme. Pass a preset name directly to the
widget's `style=` prop:

```python
from plushie import ui

ui.button("save", "Save", style="primary")
ui.button("cancel", "Cancel", style="secondary")
ui.button("delete", "Delete", style="danger")
```

Available preset names (support varies by widget):

| Preset | Typical use |
|---|---|
| `"primary"` | Primary action accent. |
| `"secondary"` | Neutral secondary action. |
| `"success"` | Success / confirmation state. |
| `"warning"` | Warning indicator. |
| `"danger"` | Destructive action. |
| `"text"` | Text-style button (no background). Button-only. |

Different widget types expose different subsets. `button` supports
the full list plus `"text"`. `container`, `tooltip`, `progress_bar`,
`text`, and `checkbox` support `"primary"` through `"danger"` (and
`"warning"` for most of them). The renderer silently falls back to
the widget's theme-default style when a name is not recognized.

Extend a preset with `StyleMap.with_base`:

```python
StyleMap().with_base("primary").with_hovered({"background": "#1d4ed8"})
```

## Theme

A theme sets the palette every widget inside a window or subtree
inherits. Pass the theme as a string (built-in name) or a `Theme`
instance (custom palette) to the window's `theme` prop, the
`themer` container, or `App.settings`.

### Built-in themes

```python
from plushie import ui

ui.window("main", content, title="App", theme="dark")
```

Built-in names (available as `THEME_*` constants and collected in
`plushie.types.BUILTIN_THEMES`):

| Theme | Notes |
|---|---|
| `"light"`, `"dark"` | Default light and dark palettes. |
| `"nord"` | [Nord](https://www.nordtheme.com/). |
| `"dracula"` | [Dracula](https://draculatheme.com/). |
| `"solarized_light"`, `"solarized_dark"` | [Solarized](https://ethanschoonover.com/solarized/). |
| `"gruvbox_light"`, `"gruvbox_dark"` | [Gruvbox](https://github.com/morhetz/gruvbox). |
| `"catppuccin_latte"`, `"catppuccin_frappe"`, `"catppuccin_macchiato"`, `"catppuccin_mocha"` | [Catppuccin](https://catppuccin.com/). |
| `"tokyo_night"`, `"tokyo_night_storm"`, `"tokyo_night_light"` | [Tokyo Night](https://github.com/enkia/tokyo-night-vscode-theme). |
| `"kanagawa_wave"`, `"kanagawa_dragon"`, `"kanagawa_lotus"` | [Kanagawa](https://github.com/rebelot/kanagawa.nvim). |
| `"moonfly"`, `"nightfly"` | [moonfly](https://github.com/bluz71/vim-moonfly-colors) and [nightfly](https://github.com/bluz71/vim-nightfly-colors). |
| `"oxocarbon"` | [Oxocarbon](https://github.com/nyoom-engineering/oxocarbon.nvim). |
| `"ferra"` | [Ferra](https://github.com/casperstorm/ferra). |

Pass `"system"` to follow the OS light/dark preference.

### App default and per-window override

Set a default for every window through `App.settings`:

```python
import plushie
from plushie import ui

class MyApp(plushie.App[Model]):
    def settings(self):
        return {"theme": "nord"}

    def view(self, model):
        return ui.window("main", content(model), title="My App")
```

`settings()` runs once at startup. Per-window `theme` props override
it. `App.window_config(model)` can also return a `theme` key that
feeds every window opened by the app; values set in the view tree
still win.

### Subtree theming with `ui.themer`

```python
ui.themer(
    "sidebar-theme",
    ui.column(
        ui.text("Dark sidebar"),
        ui.button("nav", "Navigate"),
        padding=12,
    ),
    theme="dark",
)
```

Everything inside the `themer` container renders with the supplied
theme. The rest of the window is unaffected.

### Custom palettes

`Theme.custom` constructs a palette from seed colors:

```python
from plushie.types import Theme

my_theme = Theme.custom(
    "My Brand",
    primary="#3b82f6",
    danger="#ef4444",
    background="#1a1a2e",
    text="#e0e0e8",
)
```

| Seed | Purpose |
|---|---|
| `background` | Window / page background. |
| `text` | Default text color. |
| `primary` | Primary accent (buttons, links, focus rings). |
| `success` | Success indicators. |
| `danger` | Error and destructive actions. |
| `warning` | Warning indicators. |

Every seed value runs through `Colors.cast`, so any color input form
works.

Pass `base="nord"` (or any built-in theme name) to start from an
existing palette and override only specific seeds:

```python
Theme.custom("Nord+", base="nord", primary="#88c0d0")
```

Apply a `Theme` instance the same way as a built-in name string:

```python
ui.window("main", content, theme=my_theme)
```

### Shade overrides

`Theme.custom` accepts shade override kwargs alongside the seeds.
These target individual steps in the generated palette ramp rather
than the seed itself.

Color families (each with `_base`, `_weak`, `_strong` and matching
`_text` variants): `primary`, `secondary`, `success`, `warning`,
`danger`. For example, `primary_base`, `primary_weak`,
`primary_strong`, `primary_base_text`, `primary_weak_text`,
`primary_strong_text`.

Background family (fine-grained shades, each with a `_text` variant):
`background_base`, `background_weakest`, `background_weaker`,
`background_weak`, `background_neutral`, `background_strong`,
`background_stronger`, `background_strongest`.

```python
Theme.custom(
    "Custom",
    base="dark",
    primary="#3b82f6",
    primary_strong="#1d4ed8",
    background_weakest="#0f0f1a",
)
```

Unknown shade keys raise `ValueError` listing the valid set.

The secondary family has no core seed; it is auto-derived from
`background` and `text`. To customize it, use the
`secondary_base` / `secondary_weak` / `secondary_strong` shade keys
(plus the `_text` variants).

## See also

- [Built-in Widgets reference](built-in-widgets.md) - which widgets
  accept `style=`, `background=`, `border=`, and `shadow=` props
- [Windows and Layout reference](windows-and-layout.md) - the
  `container` widget and its styling props
- [Accessibility reference](accessibility.md) - the `a11y` annotation
  type and how it composes with styling
- [Animation reference](animation.md) - animating color, border, and
  shadow values over time
- [Configuration reference](configuration.md) - `App.settings` and
  renderer-wide defaults
