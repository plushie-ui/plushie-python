# Layout

The pad already has a three-column shape: sidebar, editor-over-preview, event log. It works, but the proportions are rough and the spacing is inconsistent. This chapter walks through the layout vocabulary you need to refine it, then applies that vocabulary to the pad.

Full container props and type shapes live in the [Windows and Layout reference](../reference/windows-and-layout.md). The leaf widgets referenced here are cataloged in [Built-in Widgets](../reference/built-in-widgets.md).

## The column and row duality

Every Plushie layout tree is built from two workhorses: `ui.column` stacks children top to bottom, `ui.row` arranges them left to right. They share almost every prop. The choice between them is a question of stacking direction.

```python
from plushie import ui

ui.column(
    ui.text("title", "Notes"),
    ui.text_input("body", ""),
    spacing=8,
    padding=16,
)

ui.row(
    ui.button("save", "Save"),
    ui.button("cancel", "Cancel"),
    spacing=8,
)
```

Both containers are anonymous: an optional `id=` kwarg is allowed, but it does not create an ID scope for descendants. `ui.container` is the single-child wrapper that does create a scope (covered below).

`ui.column` accepts `align_x`; `ui.row` accepts `align_y`. Both accept `wrap=True`, which flows children into a new column or row when they overflow. Useful for tag clouds, toolbars, and button bars that should reflow at narrower window widths.

## Length values

Every layout-sensitive widget takes `width` and `height` kwargs. The `plushie.types.Length` alias gives them a uniform type:

```python
type Length = int | float | Literal["fill", "shrink"] | dict[str, int]
```

| Value | Meaning |
|---|---|
| `240` (int or float) | Exact pixel size. Negative values raise `ValueError`. |
| `"fill"` | Take all remaining space along the parent's axis. |
| `"shrink"` | Shrink to the content's intrinsic size. Default for most widgets. |
| `{"fill_portion": n}` | Take a weighted share of the remaining space. `n` is a positive integer. |

The renderer measures fixed-pixel children first, then `"shrink"` children at their natural size, and finally divides whatever is left among the `"fill"` and `"fill_portion"` children proportionally.

`"fill"` is shorthand for `{"fill_portion": 1}`. Two `"fill"` siblings split space evenly. A `"fill"` next to a `{"fill_portion": 3}` gives a one-to-three split.

The pad already uses this. The editor claims most of the vertical space, the preview takes the rest:

```python
def _editor(model):
    return ui.text_editor(
        "editor",
        model.editor_source,
        width="fill",
        height={"fill_portion": 3},
        highlight_syntax="python",
    )


def _preview(model):
    return ui.container(
        "preview",
        ui.text("content", "..."),
        padding=12,
        width="fill",
        height={"fill_portion": 2},
    )
```

The editor and preview live inside the same `ui.column`. They share the column's height: the editor takes three parts, the preview two. Tweak those numbers to adjust the split without touching any other layout code.

Prop values flow through as kwargs. Validation happens renderer-side. The Python-side helpers in `plushie.types` do reject clearly wrong shapes (negative pixels, a `fill_portion` below one); the precise pixel meaning of a kwarg is the renderer's call.

## Padding and spacing

Padding and spacing are easy to confuse. **Padding** is the gap between a container's edges and its children. **Spacing** is the gap between sibling children. Both live on the container, but spacing only applies to the multi-child containers: `column`, `row`, `grid`, `keyed_column`.

```python
ui.column(
    ui.text("a", "First"),
    ui.text("b", "Second"),
    ui.text("c", "Third"),
    padding=16,   # 16px around the whole block
    spacing=8,    # 8px between each pair of children
)
```

The first text has 16px above and 8px below; the last has 8px above and 16px below. Spacing never adds a gap before the first child or after the last one.

Padding accepts several shapes. The `plushie.types.Padding` alias collects them:

```python
type Padding = (
    int
    | float
    | tuple[float, float]
    | tuple[float, float, float, float]
    | dict[str, float]
)
```

| Input | Meaning |
|---|---|
| `16` | Uniform: 16px on all four sides. |
| `(8, 16)` | `(vertical, horizontal)`: 8px top and bottom, 16px left and right. |
| `(4, 8, 12, 16)` | `(top, right, bottom, left)`, matching CSS order. |
| `{"top": 16, "left": 8}` | Named per-side. Missing sides default to 0. |

The pad's toolbar uses the two-tuple form:

```python
ui.row(
    ui.button("save", "Save"),
    ui.button("autosave", "Autosave"),
    padding=(8, 16),
    spacing=8,
)
```

Vertical padding of 8 keeps the toolbar compact; horizontal padding of 16 matches the editor's visual inset. Separating the two is exactly what the two-tuple form is for.

## Alignment

`align_x` controls horizontal placement. `align_y` controls vertical placement.

```python
type AlignX = Literal["left", "center", "right"]
type AlignY = Literal["top", "center", "bottom"]
```

The defaults (`"left"` and `"top"`) match the natural stacking direction. Override them when you want a child to land somewhere else within the available space. On `ui.container`, the shorthand `center=True` sets both axes at once.

```python
ui.container(
    "splash",
    ui.text("loading", "Loading..."),
    width="fill",
    height="fill",
    center=True,
)
```

## Containers

`ui.container` is the single-child wrapper. It serves several distinct jobs:

- **Styling.** Background fill, borders, shadows, text colour. The [Styling guide](08-styling.md) covers the style props in detail; `background`, `border`, and `shadow` all live on `ui.container`.
- **Scoping.** A named container creates an ID scope for descendants. Inside `ui.container("sidebar", ...)`, a `ui.button("save", "Save")` is addressable as `"sidebar/save"` from test selectors and patch operations. See the [Scoped IDs reference](../reference/scoped-ids.md).
- **Alignment and padding for a single child.** Wrapping a text widget in a container with `padding=12, align_x="center"` is cheaper than a one-child column or row.

```python
ui.container(
    "card",
    ui.column(
        ui.text("name", "Jane"),
        ui.text("role", "Engineer"),
        spacing=4,
    ),
    padding=16,
    background="#ffffff",
    border={"width": 1, "color": "#e0e0e0", "radius": 8},
)
```

`ui.scrollable` adds scroll bars when content overflows. It needs a string ID because the renderer tracks scroll position as internal state.

```python
ui.scrollable(
    "log",
    ui.column(
        *(ui.text(f"entry-{i}", line) for i, line in enumerate(lines)),
        spacing=2,
    ),
    height=120,
    direction="vertical",
)
```

`direction` is `"vertical"` (default), `"horizontal"`, or `"both"`. `anchor="end"` combined with `auto_scroll=True` is the chat-log pattern: the viewport pins to the bottom and follows new content until the user scrolls away.

`ui.stack` layers children along the z-axis. The first child is at the back, the last at the front. Use it for overlays, badges, loading spinners, or modal dimming.

```python
ui.stack(
    _main_content(model),
    ui.container(
        "toast",
        ui.text("msg", "Saved."),
        padding=12,
        background="#323232",
        color="#ffffff",
    ),
    width="fill",
    height="fill",
)
```

## Responsive sizing

A layout that reads well at 1200px often falls apart at 640px. `ui.responsive` measures the space its child actually receives and emits a `Resize` event whenever that space changes. Store the measurement in the model, branch the view on it, and you have a breakpoint-aware layout.

```python
from dataclasses import replace

from plushie import ui
from plushie.events import Resize


def update(self, model, event):
    match event:
        case Resize(id="viewport", width=w):
            return replace(model, viewport_width=w)
        case _:
            return model


def view(self, model):
    body = _narrow(model) if model.viewport_width < 720 else _wide(model)
    return ui.window(
        "main",
        ui.responsive(body, id="viewport"),
        title="Adaptive",
    )
```

The `Resize` event carries `width` and `height` in logical pixels along with the widget `id`. Pick a handful of breakpoints (600, 900, 1200 is a common set) and branch on them. Avoid branching on every pixel: the event fires whenever the measured size changes, so a `view` that varies continuously re-renders on every drag.

`ui.responsive` defaults both `width` and `height` to `"fill"`, so dropping one in at the root of a window measures the window's content area directly.

## A refined pad layout

With this vocabulary in hand, the pad's main view becomes easier to tune. The sidebar locks to 220px because it is a list, not a resizable pane. The event log locks to 240px on the right. The editor claims everything in between with `width="fill"`, and the editor and preview keep the vertical three-to-two split. Pull the widths into named constants so future tuning touches one place:

```python
from plushie import ui

SIDEBAR_WIDTH = 220
LOG_WIDTH = 240


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
    )


def _sidebar(model):
    return ui.container(
        "sidebar",
        ui.column(
            ui.text("sidebar-title", "Experiments", size=14),
            *(ui.button(f"select-{e.name}", e.name) for e in model.experiments),
            padding=12,
            spacing=8,
        ),
        width=SIDEBAR_WIDTH,
        height="fill",
    )


def _main_pane(model):
    return ui.column(
        _toolbar(model),
        _editor(model),
        _preview(model),
        spacing=0,
        width="fill",
        height="fill",
    )


def _event_log(model):
    entries = (
        ui.text(f"log-{i}", f"{e.kind}: {e.detail}")
        for i, e in enumerate(model.event_log)
    )
    return ui.container(
        "log",
        ui.scrollable(
            "log-scroll",
            ui.column(*entries, spacing=4, padding=8),
            height="fill",
        ),
        width=LOG_WIDTH,
        height="fill",
    )
```

The outer `ui.row` uses `spacing=0`: the three panes are visually distinct because of their backgrounds and borders (added in the next chapter), not because of a gap between them. `width="fill", height="fill"` lets the row consume the window's full content area.

Inside the main pane, the toolbar takes its natural height (`"shrink"` by default), the editor keeps `height={"fill_portion": 3}`, and the preview keeps `height={"fill_portion": 2}`.

The event log pane wraps a `ui.scrollable` in the named `"log"` container. The container gives the pane its fixed 240px width and a styling anchor; the scrollable handles overflow when the log grows past the viewport. Without the scrollable, a long log would push the column taller than the window.

## Overflow handling

Overflow is handled two ways. `clip=True` on `column`, `row`, `container`, or `stack` hides children that extend past the container's bounds. `ui.scrollable` adds scroll bars, preserving access to the clipped content.

Pick `clip` when overflow is a visual glitch you want to hide (a hover scale, a long label leaking outside a card). Pick `ui.scrollable` when overflow is actual content the user needs to reach.

```python
ui.container(
    "card",
    ui.text("preview", long_text),
    width=240,
    height=120,
    clip=True,
    padding=12,
)
```

## What's next

The pad now has proportions. It still looks like plain widgets on a plain background. In [chapter 8](08-styling.md) we add themes, colours, and per-widget styling to give the pad a finished look.

---

Next: [Styling](08-styling.md)
