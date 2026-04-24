# Styling

With the layout in place, the pad is structured but visually flat. Plushie's styling system has three layers: themes set the overall palette for a window, named presets pick sensible accents from that palette, and `StyleMap` plus per-widget kwargs override individual elements when you need more control.

This chapter covers the parts of the surface you will reach for most. The full theme palette, every shade override key, and the exact shape of each type is catalogued in the [Themes and Styling reference](../reference/themes-and-styling.md).

## Built-in themes

Every window has a `theme` prop. Pass a string name and every widget inside picks up the matching palette.

```python
from plushie import ui


def view(self, model):
    return ui.window(
        "pad",
        _content(model),
        title="Plushie Pad",
        theme="dark",
    )
```

The renderer ships a set of ready-to-use themes. Popular picks:

| Name | Notes |
|---|---|
| `"light"`, `"dark"` | Default light and dark palettes. |
| `"nord"` | Cool pastel palette. |
| `"dracula"` | Classic dark theme. |
| `"catppuccin_mocha"` | Warm pastel dark. |
| `"tokyo_night"` | Muted night palette. |
| `"gruvbox_dark"` | Retro warm dark. |
| `"solarized_light"` | Classic light palette. |

The [Themes and Styling reference](../reference/themes-and-styling.md) lists every built-in name. Pass `"system"` to follow the operating system's light/dark preference.

### App-wide default

Set a default once via `App.settings`. It applies to every window unless a specific window overrides it:

```python
import plushie


class Pad(plushie.App[Model]):
    def settings(self):
        return {"theme": "catppuccin_mocha"}
```

`settings` runs once at startup. Per-window `theme` props win over the default, which is what lets the pad surface a theme switcher (below) without breaking the app-wide fallback.

## Preset styles

Themes cover palette; presets cover accent. The `style=` prop on interactive widgets takes a preset name and the renderer picks the right palette entry from the active theme.

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
| `"success"` | Success or confirmation. |
| `"warning"` | Warning indicator. |
| `"danger"` | Destructive action. |
| `"text"` | Text-only button (no background). Button-only. |

Containers, tooltips, progress bars, text, and checkboxes take the same presets. Prop values pass through as kwargs, so unrecognised names fall back to the widget's theme default silently. Check each widget's entry in the [Built-in Widgets reference](../reference/built-in-widgets.md) for its supported subset.

The pad's sidebar already uses `style="primary"` to highlight the selected experiment and `style="secondary"` for the new-experiment button. That one kwarg does a lot of work: it tracks whatever theme is currently active.

## Per-widget overrides

For one-off adjustments, pass styling kwargs directly to the widget. `Border`, `Shadow`, and `Gradient` instances (from `plushie.types`) are accepted anywhere the prop describes that kind of value.

```python
from plushie import ui
from plushie.types import Border, Shadow

ui.container(
    "card",
    ui.text("card-title", "Saved at 14:32", size=14),
    padding=16,
    background="#ffffff",
    border=Border(color="#e5e7eb", width=1, radius=8),
    shadow=Shadow(color="#0000001a", offset=(0, 2), blur_radius=4),
)
```

`background` takes a color string or a `Gradient`. `color` sets text color on text widgets. `border` takes a `Border` dataclass. `shadow` takes a `Shadow` dataclass. Negative widths and radii raise `ValueError` at encode time.

The `Border.radius` field accepts either a uniform number or a per-corner dict:

```python
from plushie.types import Border

Border(
    color="#ccc",
    width=1,
    radius=Border.radius_corners(top_left=8, top_right=8),
)
```

`Border.radius_corners(...)` fills in zero for the corners you omit, which is convenient when you want rounded top corners and square bottom corners on an attached panel.

## StyleMap for interaction states

Preset names cover the common case. When a widget needs specific colors for hover and press, build a `StyleMap` from `plushie.types`. `StyleMap` is a frozen dataclass with `with_*` builder methods that return new instances.

```python
from plushie.types import Border, StyleMap

save_style = (
    StyleMap()
    .with_background("#3b82f6")
    .with_text_color("#ffffff")
    .with_border(Border(color="#2563eb", width=1, radius=6))
    .with_hovered({"background": "#2563eb"})
    .with_pressed({"background": "#1d4ed8"})
    .with_disabled({"background": "#9ca3af", "text_color": "#6b7280"})
)

ui.button("save", "Save", style=save_style)
```

The status overrides are plain dicts with the keys `background`, `text_color`, `border`, and `shadow`. Only keys you set change for that status; everything else inherits from the base fields. Nested `Border`, `Shadow`, and `Gradient` values inside an override are encoded recursively on the way to the wire.

Extend a named preset instead of building from scratch by chaining `.with_base("primary")` and then overriding only the bits you want different.

## Local themes with themer

The `themer` container retints a subtree without touching the rest of the window. Useful for a dark sidebar inside a light app, or a brand-specific section, or a preview pane that deliberately renders in a different palette so experiments look distinct.

```python
from plushie import ui


def _sidebar(model):
    return ui.themer(
        "sidebar-theme",
        ui.container(
            "sidebar",
            ui.column(
                ui.text("sidebar-title", "Experiments", size=14),
                # ...experiment buttons...
                padding=12,
                spacing=8,
            ),
            width=220,
            height="fill",
        ),
        theme="dark",
    )
```

Everything inside `ui.themer` sees the supplied theme. Siblings and ancestors are unaffected. The id on `themer` (`"sidebar-theme"`) is required for stable diffing across renders.

## Colors

Colors appear everywhere: widget props, `Border.color`, shadow tints, gradient stops, theme seeds, style-map backgrounds. A color is always a `str` in canonical `#rrggbb` or `#rrggbbaa` form. The `Colors` helper in `plushie.types` constructs and normalises them.

```python
from plushie.types import Colors

Colors.from_rgb(255, 128, 0)        # "#ff8000"
Colors.from_rgba(255, 0, 0, 0.5)    # "#ff000080"
Colors.from_hex("#FF8800")          # "#ff8800"
Colors.from_hex("abc")              # "#aabbcc" (expanded shorthand)
Colors.cast("red")                  # "#ff0000"
Colors.cast("CornflowerBlue")       # "#6495ed"
```

Every CSS Color Module Level 4 named color works, plus `"transparent"`. Lookups are case-insensitive. Pass the raw name string anywhere a color is accepted and the SDK runs it through `Colors.cast` during encoding:

```python
ui.container("card", ui.text("hi"), background="cornflowerblue")
ui.text("error", message, color="firebrick")
```

`Colors.named_colors()` returns the full map if you want to enumerate them.

## Fonts

Three forms of font value are accepted everywhere a `font` prop lives:

- `"default"` for the system proportional font
- `"monospace"` for the system monospace font
- A `Font` dataclass for a specific family, weight, style, or stretch

```python
from plushie import ui
from plushie.types import Font

ui.text("code", source, font="monospace", size=13)
ui.text("title", "Plushie Pad", font=Font(family="Inter", weight="semi_bold"))
ui.text("body", body, font=Font(family="JetBrains Mono", style="italic"))
```

`Font` fields (`family`, `weight`, `style`, `stretch`) all default to `None`, meaning "use the widget default". Weight, style, and stretch are lowercase string literals (`"semi_bold"`, `"italic"`, `"ultra_condensed"`). The full enumerations live in `plushie.types` as `FontWeight`, `FontStyle`, and `FontStretch`.

### Loading custom fonts

App-wide font loading happens in `App.settings`. The `fonts` key takes a list of paths to font files; once loaded, the family name is available to any widget's `font` prop.

```python
import plushie


class Pad(plushie.App[Model]):
    def settings(self):
        return {
            "default_text_size": 14,
            "fonts": ["assets/fonts/Inter.ttf", "assets/fonts/JetBrainsMono.ttf"],
        }
```

`default_text_size` sets a pixel default for every text widget that does not pass its own `size`. See the [Configuration reference](../reference/configuration.md) for the full list of `settings` keys.

## A theme switcher in the pad

Put the pieces together. Add a `theme` field to the model, a pick_list in the toolbar, and thread the selection into the window's `theme` prop.

```python
from dataclasses import dataclass, replace

from plushie import ui
from plushie.events import Select
from plushie.types import BUILTIN_THEMES


@dataclass(frozen=True, slots=True)
class Model:
    # ...existing fields...
    theme: str = "dark"


class Pad(plushie.App[Model]):
    def update(self, model, event):
        match event:
            case Select(id="theme-picker", value=name):
                return replace(model, theme=name)
            # ...existing cases...
            case _:
                return model

    def view(self, model):
        return ui.window(
            "pad",
            ui.row(
                _sidebar(model),
                _main_pane(model),
                _event_log(model),
                spacing=0,
                width="fill",
                height="fill",
            ),
            title="Plushie Pad",
            size=(1100, 700),
            theme=model.theme,
        )
```

The toolbar gains a pick_list alongside Save and Autosave:

```python
def _toolbar(model):
    return ui.row(
        ui.button("save", "Save" + (" *" if model.dirty else "")),
        ui.button(
            "autosave",
            "Autosave: On" if model.autosave else "Autosave: Off",
        ),
        ui.pick_list("theme-picker", list(BUILTIN_THEMES), model.theme),
        padding=8,
        spacing=8,
    )
```

`BUILTIN_THEMES` is the canonical tuple of every built-in name, so the picker stays in sync if the renderer adds more. Selecting a theme swaps the whole window palette in one cycle: buttons, text inputs, scrollbars, and the editor all pick up the new colors without further changes.

If you want the sidebar to keep its own distinctive palette regardless of the window theme, wrap it in a `themer` with a fixed theme name. The switcher only affects widgets that inherit from the window.

## Try it

- Wrap the preview pane in a `ui.themer("preview", ..., theme="light")` so experiments always render on a neutral palette.
- Build a `StyleMap` for the save button with a distinct hover and press background, and swap `style="primary"` on the button for your new map.
- Define a small `Design` module with spacing, radius, and reusable `StyleMap` helpers. Plain Python modules are enough; there is no framework magic.
- Add a custom theme via `Theme.custom(base="nord", primary="#88c0d0")` and feed it to the picker as an additional option.

In the next chapter, we add animations and transitions so the pad feels alive when state changes.

---

Next: Animation and Transitions
