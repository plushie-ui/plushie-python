# Layout

Plushie's layout model mirrors iced's. Understanding it is essential for
building UIs that size and position correctly.

## Length

Length controls how a widget claims space along an axis.

| Plushie value | Iced equivalent | Meaning |
|---|---|---|
| `"fill"` | `Length::Fill` | Take all remaining space |
| `("fill_portion", n)` | `Length::FillPortion(n)` | Proportional share of remaining space |
| `"shrink"` | `Length::Shrink` | Use minimum/intrinsic size |
| `200` or `200.0` | `Length::Fixed(200.0)` | Exact pixel size |

```python
from plushie import ui

# Fill available width
ui.column(..., width="fill")

# Fixed width
ui.container("sidebar", ..., width=250)

# Proportional: left takes 2/3, right takes 1/3
ui.row(
    ui.container("left", ..., width=("fill_portion", 2)),
    ui.container("right", ..., width=("fill_portion", 1)),
)

# Shrink to content
ui.button("save", "Save", width="shrink")
```

### Default lengths

Most widgets default to `"shrink"` for both width and height. Layout
containers (`column`, `row`) typically default to `"shrink"` but grow to
accommodate their children.

## Padding

Padding is the space between a widget's boundary and its content.

| Plushie value | Meaning |
|---|---|
| `10` | Uniform: 10px on all sides |
| `(10, 20)` | Axis: 10px vertical, 20px horizontal |
| `{"top": 5, "right": 10, "bottom": 5, "left": 10}` | Per-side |
| `0` | No padding |

```python
ui.container("box", ..., padding=16)
ui.container("box", ..., padding=(8, 16))
ui.container("box", ..., padding={"top": 0, "right": 16, "bottom": 8, "left": 16})
```

Padding is accepted by `container`, `column`, `row`, `scrollable`,
`button`, `text_input`, and `text_editor`.

## Spacing

Spacing is the gap between children in a layout container.

```python
ui.column(
    ui.text("First"),
    ui.text("Second"),   # 8px gap between First and Second
    ui.text("Third"),    # 8px gap between Second and Third
    spacing=8,
)
```

Spacing is accepted by `column`, `row`, and `scrollable`.

## Alignment

Alignment controls how children are positioned within their parent along
the cross axis.

### align_x (horizontal alignment in a column)

| Value | Meaning |
|---|---|
| `"start"` or `"left"` | Left-aligned |
| `"center"` | Centered |
| `"end"` or `"right"` | Right-aligned |

### align_y (vertical alignment in a row)

| Value | Meaning |
|---|---|
| `"start"` or `"top"` | Top-aligned |
| `"center"` | Centered |
| `"end"` or `"bottom"` | Bottom-aligned |

```python
# Center children horizontally in a column
ui.column(
    ui.text("Centered"),
    ui.button("ok", "OK"),
    align_x="center",
)

# Center a single child in a container
ui.container(
    "page",
    ui.text("Dead center"),
    width="fill",
    height="fill",
    center=True,
)
```

The `center=True` shorthand on `container` sets both `align_x="center"`
and `align_y="center"`.

## Layout containers

### column

Arranges children vertically (top to bottom).

```python
ui.column(
    ui.text("title", "Title", size=24),
    ui.text("subtitle", "Subtitle", size=14),
    id="main",
    spacing=16,
    padding=20,
    width="fill",
    align_x="center",
)
```

Props: `spacing`, `padding`, `width`, `height`, `align_x`.

### row

Arranges children horizontally (left to right).

```python
ui.row(
    ui.button("back", "<"),
    ui.text("Page 1 of 5"),
    ui.button("next", ">"),
    spacing=8,
    align_y="center",
)
```

Props: `spacing`, `padding`, `width`, `height`, `align_y`, `wrap` (wraps
children to next line when they overflow).

### container

Wraps a single child with padding, alignment, and styling.

```python
ui.container(
    "card",
    ui.column(
        ui.text("Card title"),
        ui.text("Card content"),
    ),
    padding=16,
    style="rounded_box",
    width="fill",
)
```

Props: `padding`, `width`, `height`, `align_x`, `align_y`, `center`,
`style`, `clip`.

### scrollable

Wraps content in a scrollable region.

```python
ui.scrollable(
    "list",
    ui.column(
        *(ui.text(f"item:{item.id}", item.name) for item in items),
        spacing=4,
    ),
    height=400,
    width="fill",
)
```

Props: `width`, `height`, `direction` (`"vertical"`, `"horizontal"`,
`"both"`), `spacing`.

### stack

Overlays children on top of each other (z-stacking). Later children
are on top.

```python
ui.stack(
    ui.image("bg", "background.png", width="fill", height="fill"),
    ui.container(
        "overlay",
        ui.text("overlay_text", "Overlaid text", size=48),
        width="fill",
        height="fill",
        center=True,
    ),
)
```

### space

Empty spacer. Takes up space without rendering anything.

```python
ui.row(
    ui.text("Left"),
    ui.space(width="fill"),  # pushes Right to the far right
    ui.text("Right"),
)
```

### grid

Arranges children in a grid layout.

```python
ui.grid(
    *(ui.image(f"img:{item.id}", item.url, width="fill") for item in items),
    id="gallery",
    columns=3,
    spacing=8,
)
```

## Common layout patterns

### Centered page

```python
ui.container(
    "page",
    ui.column(
        ui.text("welcome", "Welcome", size=32),
        ui.button("start", "Get Started"),
        spacing=16,
        align_x="center",
    ),
    width="fill",
    height="fill",
    center=True,
)
```

### Sidebar + content

```python
ui.row(
    ui.container(
        "sidebar",
        nav_items(model),
        width=250,
        height="fill",
        padding=16,
    ),
    ui.container(
        "content",
        main_content(model),
        width="fill",
        height="fill",
        padding=16,
    ),
    width="fill",
    height="fill",
)
```

### Header + body + footer

```python
ui.column(
    ui.container("header", header(model), width="fill", padding=(8, 16)),
    ui.scrollable(
        "body",
        body_content(model),
        width="fill",
        height="fill",
    ),
    ui.container("footer", footer(model), width="fill", padding=(8, 16)),
    width="fill",
    height="fill",
)
```
