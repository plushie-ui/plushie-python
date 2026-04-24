# Canvas

A canvas is a widget whose content is a collection of named layers of
drawn shapes rather than child widgets. It participates in layout like
any other widget (`width`, `height`, `background`), but inside it you
compose rectangles, circles, paths, text, images, and SVG, and wrap
them in interactive groups to receive pointer and keyboard events.

Shapes are plain dicts. Builder functions in `plushie.canvas` compose
them. The `ui.canvas` builder lives in `plushie.ui`. Pointer and drag
events are the same classes used elsewhere in the SDK.

## The canvas widget

`ui.canvas(id, **kwargs)` creates a canvas node. It takes an
explicit string `id` as its only positional argument. All other props
pass through as kwargs.

```python
from plushie import ui
from plushie import canvas as c

ui.canvas(
    "chart",
    width=400,
    height=200,
    background="#f5f5f5",
    layers=dict([
        c.layer("bars",
            c.rect(10, 50, 80, 150, fill="#3b82f6"),
            c.rect(110, 100, 80, 100, fill="#22c55e"),
        ),
        c.layer("labels",
            c.canvas_text(50, 190, "A", fill="#333", size=12),
            c.canvas_text(150, 190, "B", fill="#333", size=12),
        ),
    ]),
)
```

### Props

| Prop | Type | Purpose |
|---|---|---|
| `layers` | dict | Named layers, each a list of shapes |
| `shapes` | list | Flat list of shapes (alternative to `layers`) |
| `width` | Length | Canvas width |
| `height` | Length | Canvas height in pixels |
| `background` | Color | Fill drawn behind all layers |
| `interactive` | bool | Enable hit testing without explicit pointer props |
| `on_press` | bool | Emit `Press` for canvas-level pointer down |
| `on_release` | bool | Emit `Release` for canvas-level pointer up |
| `on_move` | bool | Emit `Move` for canvas-level pointer motion |
| `on_scroll` | bool | Emit `Scroll` for canvas-level wheel input |
| `event_rate` | int | Max canvas-level events per second |
| `role` | str | Top-level accessibility role (e.g. `"radiogroup"`) |
| `arrow_mode` | str | Keyboard arrow navigation mode between elements |
| `alt` | str | Accessible short description |
| `description` | str | Accessible long description |
| `a11y` | dict | Accessibility overrides. See [Accessibility](accessibility.md). |

Prop values are validated renderer-side, not in the Python SDK.

## Shapes

Shape builders live in `plushie.canvas`. Each returns a plain dict
with a `"type"` key matching the wire protocol. Use them inside
`layer` lists or as children of `group`.

| Function | Required args | Key kwargs |
|---|---|---|
| `rect` | `x, y, w, h` | `fill`, `stroke`, `radius`, `opacity` |
| `circle` | `x, y, r` | `fill`, `stroke`, `opacity` |
| `line` | `x1, y1, x2, y2` | `stroke`, `opacity` |
| `path` | `commands` | `fill`, `stroke`, `opacity` |
| `canvas_text` | `x, y, content` | `fill`, `size`, `font`, `align_x`, `align_y`, `opacity` |
| `canvas_image` | `source, x, y, w, h` | passed through as kwargs |
| `canvas_svg` | `source, x, y, w, h` | passed through as kwargs |

`canvas_image` takes a file path or URL as `source`. `canvas_svg`
takes the SVG source string, not a path.

The `rect` builder accepts `radius` as either a single number for
uniform corners or a dict with keys `top_left`, `top_right`,
`bottom_right`, `bottom_left` for per-corner radii.

### Strokes

`stroke(color, width, **kwargs)` builds a stroke descriptor for the
`stroke` kwarg on shapes:

```python
from plushie import canvas as c

c.rect(0, 0, 100, 50,
    fill="#3b82f6",
    stroke=c.stroke("#333", 2, cap="round", join="miter"),
)
```

Options: `cap` (`"butt"`, `"round"`, `"square"`), `join` (`"miter"`,
`"round"`, `"bevel"`), `miter_limit` (float).

### Gradients

`linear_gradient(start, end, stops)` builds a canvas-space gradient
fill. `start` and `end` are `(x, y)` tuples in canvas coordinates;
`stops` is a list of `(offset, color)` tuples with offsets in
`[0.0, 1.0]`.

```python
c.rect(0, 0, 200, 50,
    fill=c.linear_gradient(
        (0, 0), (200, 0),
        [(0.0, "#3b82f6"), (1.0, "#1d4ed8")],
    ),
)
```

This is a different construction from widget background gradients
(`Gradient.linear_from_angle` in `plushie.types`), which use an angle
instead of coordinate pairs. See the
[Styling reference](themes-and-styling.md).

### Path commands

Functions that return path command values for use inside `path`:

| Function | Arguments |
|---|---|
| `move_to` | `x, y` |
| `line_to` | `x, y` |
| `bezier_to` | `cp1x, cp1y, cp2x, cp2y, x, y` |
| `quadratic_to` | `cpx, cpy, x, y` |
| `arc` | `cx, cy, r, start_angle, end_angle` |
| `arc_to` | `x1, y1, x2, y2, radius` |
| `ellipse` | `cx, cy, rx, ry, rotation, start_angle, end_angle` |
| `rounded_rect` | `x, y, w, h, radius` |
| `close` | none |

```python
c.path(
    [
        c.move_to(10, 0),
        c.line_to(20, 20),
        c.line_to(0, 20),
        c.close(),
    ],
    fill="#22c55e",
)
```

Angle arguments on `arc` and `ellipse` accept bare numbers (degrees),
`(value, "deg")` tuples, or `(value, "rad")` tuples. Degrees are sent
on the wire; the renderer converts to radians at draw time. Helpers
`to_degrees` and `to_radians` are available in `plushie.canvas` for
application code.

## Layers

A canvas's `layers` prop is a dict mapping layer name to a list of
shapes. Each layer is cached independently on the renderer side, so
changing a dynamic layer does not re-tessellate static content.

Layers are drawn in alphabetical order by name. Name your layers to
control z-ordering: `"background"` draws before `"data"` draws before
`"labels"`.

The `layer(name, *children)` helper returns a `(name, shapes)` tuple
suitable for passing to `dict()`:

```python
ui.canvas(
    "chart",
    width=400,
    height=200,
    layers=dict([
        c.layer("background", c.rect(0, 0, 400, 200, fill="#f5f5f5")),
        c.layer("data",
            c.rect(10, 50, 80, 150, fill="#3b82f6"),
            c.rect(110, 100, 80, 100, fill="#22c55e"),
        ),
    ]),
)
```

For a flat canvas with no layer structure, use `shapes=[...]`
instead of `layers=`.

## Groups and transforms

`group(*children, **opts)` wraps shapes for transforms, clipping, or
interactivity. The first positional argument may be a string `id`
that makes the group interactive.

Transforms apply to groups, not to individual shapes. The
transforms in the `transforms` list are applied in order.

| Function | Returns |
|---|---|
| `translate(x, y)` | `{"type": "translate", ...}` |
| `rotate(angle)` | `{"type": "rotate", ...}` |
| `scale(x, y)` | `{"type": "scale", ...}` (non-uniform) |
| `scale_uniform(factor)` | `{"type": "scale", ...}` (uniform) |

```python
c.group(
    c.rect(0, 0, 40, 40, fill="#ef4444"),
    x=100, y=50,
    transforms=[c.rotate(45)],
)
```

The `x` and `y` kwargs on `group` desugar to a leading `translate`
prepended to the `transforms` list.

`clip(x, y, w, h)` builds a clip-rect value object for the group's
`clip` field. One clip per group.

```python
c.group(
    c.circle(40, 40, 60, fill="#3b82f6"),
    clip=c.clip(0, 0, 80, 80),
)
```

## Interactive elements

To receive events on a region of the canvas, wrap shapes in an
interactive group. There are two equivalent forms:

- `group("id", shape, ..., on_click=True, ...)` builds a group
  directly with interaction kwargs.
- `interactive(shape, "id", on_click=True, ...)` wraps an existing
  shape. If the shape is already a group, the interaction fields are
  merged into it; otherwise a new group is created with the shape as
  its sole child.

```python
c.interactive(
    c.svg_path,
    "save",
    on_click=True,
    focusable=True,
    cursor="pointer",
    a11y={"role": "button", "label": "Save"},
)
```

### Interaction props

| Prop | Type | Purpose |
|---|---|---|
| `on_click` | bool | Emit `Click` events |
| `on_hover` | bool | Emit `Enter` and `Exit` events |
| `draggable` | bool | Emit `Drag` and `DragEnd` events |
| `drag_axis` | `"x"` / `"y"` / `"both"` | Constrain drag direction |
| `drag_bounds` | dict | Limit drag region (`{min_x, max_x, min_y, max_y}`) |
| `focusable` | bool | Add to Tab order for keyboard navigation |
| `cursor` | str | Cursor style on hover (`"pointer"`, `"grab"`, etc.) |
| `tooltip` | str | Tooltip text on hover |
| `hit_rect` | dict | Custom hit-test rectangle (`{x, y, w, h}`) |

### Visual feedback props

| Prop | Type | Purpose |
|---|---|---|
| `hover_style` | dict | Override `fill`, `stroke`, `opacity` on hover |
| `pressed_style` | dict | Override while pressed |
| `focus_style` | dict | Override when keyboard-focused |
| `show_focus_ring` | bool | Show or hide the default focus indicator |
| `focus_ring_radius` | float | Corner radius for the focus ring |

Only the fields present in a style override are applied; others
inherit from the shape's base values.

### Default a11y

`interactive()` fills in a sensible default `a11y` role when none is
passed:

- `on_click=True` defaults to `role="button"`.
- `draggable=True` defaults to `role="slider"`.
- `focusable=True` (without click or drag) defaults to
  `role="group"`, with `label` taken from `tooltip` when set.

Pass an explicit `a11y` dict to override these.

## Canvas events

Events on interactive canvas elements are the same classes delivered
elsewhere in the SDK. They arrive with the element's local ID as
`id`, and the canvas ID plus window ID in `scope`.

Element-level events:

| Class | Trigger | Payload |
|---|---|---|
| `Click` | `on_click=True` | scoped under canvas ID |
| `Enter` | `on_hover=True` | `x`, `y`, `captured` |
| `Exit` | `on_hover=True` | `x`, `y`, `captured` |
| `Drag` | `draggable=True` | `x`, `y`, `delta_x`, `delta_y`, `button` |
| `DragEnd` | `draggable=True` | `x`, `y`, `button` |
| `Focused` | `focusable=True` | none |
| `Blurred` | `focusable=True` | none |

Canvas-level events (require the matching `on_*` prop on the canvas
widget itself):

| Class | Fields |
|---|---|
| `Press` | `x`, `y`, `button`, `pointer`, `modifiers`, `finger`, `captured` |
| `Release` | `x`, `y`, `button`, `pointer`, `modifiers`, `finger`, `lost`, `captured` |
| `Move` | `x`, `y`, `pointer`, `modifiers`, `finger`, `captured` |
| `Scroll` | `x`, `y`, `delta_x`, `delta_y`, `unit`, `pointer`, `modifiers`, `captured` |
| `DoubleClick` | `x`, `y`, `pointer`, `modifiers` |

`pointer` is `"mouse"`, `"touch"`, or `"pen"`. `finger` carries the
touch finger identifier, `None` for mouse and pen input. See the
[Events reference](events.md) for the full pointer model.

### Pattern matching

Match element clicks by `id` and the canvas ID in `scope`:

```python
from plushie.events import Click, Drag, Press, Scroll

def update(self, model, event):
    match event:
        case Click(id="save", scope=("toolbar", *_)):
            return save(model)
        case Drag(id=bar_id, x=x, y=y) if bar_id.startswith("bar-"):
            return move_bar(model, bar_id, x, y)
        case Press(id="drawing", pointer="touch", finger=f, x=x, y=y):
            return start_stroke(model, f, x, y)
        case Scroll(id="drawing", delta_y=dy, modifiers=m) if m.ctrl:
            return zoom(model, dy)
        case _:
            return model
```

## Focus and keyboard

`focusable=True` adds an interactive element to the window's Tab
order. `Focused` and `Blurred` events fire on focus transitions, and
keyboard input scoped to the focused element is delivered as the
usual `KeyEvent` with the element's ID in `scope`. Keyboard matching
patterns are identical to widget keyboard handling; see the
[Events reference](events.md).

For canvases that act as radio groups or slider rails, set the
canvas's top-level `role` and `arrow_mode` props so the renderer
routes arrow keys between elements without a round-trip.

## See also

- [Events reference](events.md) - pointer, drag, and key event classes
- [Built-in widgets reference](built-in-widgets.md) - `ui.canvas` in
  the widget catalog
- [Styling reference](themes-and-styling.md) - widget-background
  `Gradient` values (distinct from canvas `linear_gradient`)
- [Windows and layout reference](windows-and-layout.md) - `Length`
  values for canvas `width` and `height`
- [Accessibility reference](accessibility.md) - roles and labels for
  interactive canvas elements
