# Windows and Layout

Every plushie app renders one or more windows. Inside each window,
layout containers arrange widgets by stacking, flowing, positioning,
and wrapping. This reference covers the sizing / padding / alignment
vocabulary shared across all widgets, the `window` node at the root
of every view tree, and the layout containers available from
`plushie.ui`.

Prop values flow through as `**kwargs` on builder functions. Validation
happens renderer-side: an invalid `padding` shape raises from the
encoding helpers in `plushie.types`; unknown prop names pass through to
the renderer which either applies or ignores them.

## Length

Widget sizing props (`width`, `height`, `max_width`, `max_height`,
column widths, pane sizes) take a `Length`. The alias, from
`plushie.types`, collects every accepted shape:

```python
type Length = int | float | Literal["fill", "shrink"] | dict[str, int]
```

| Value | Meaning |
|---|---|
| `int` or `float` | Exact pixel size. Negative values raise `ValueError`. |
| `"fill"` | Expand to fill available space in the parent. |
| `"shrink"` | Shrink to content size. Default for most widgets. |
| `{"fill_portion": n}` | Take a weighted share of available space. `n` is a positive integer ratio. |

`"fill"` is shorthand for `{"fill_portion": 1}`. Two `"fill"` siblings
split space equally. A `{"fill_portion": 1}` next to a
`{"fill_portion": 3}` sibling splits the available space one-to-three.

The layout engine measures fixed-pixel children first, then `"shrink"`
children at their intrinsic size, then divides the remainder among
`"fill"` / `"fill_portion"` children proportionally.

`plushie.types.encode_length` is the helper the runtime uses to convert
user input to its wire shape. It normalises the two-tuple
`("fill_portion", n)` form to `{"fill_portion": n}`, and rejects
negative pixel values or `fill_portion` values less than 1.

## Padding

Padding is the gap between a container's edges and its content. The
`Padding` alias accepts several shorthands:

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
| `16` | Uniform on all sides. |
| `(8, 16)` | `(vertical, horizontal)`: 8px top and bottom, 16px left and right. |
| `(4, 8, 12, 16)` | `(top, right, bottom, left)`. |
| `{"top": 16, "left": 8}` | Named per-side. Missing sides default to 0. |

`plushie.types.encode_padding` normalises all forms to either a single
number (when every side is equal) or a `{"top", "right", "bottom",
"left"}` dict. Tuples are a Python-side convenience; the wire message
never carries one. Negative sides raise `ValueError`.

Padding reduces the space available to children. A 200px-wide container
with `padding=16` has 168px of content space. Padding and spacing (the
gap between siblings) are independent: a column with `padding=16,
spacing=8` has 16px around the edges and 8px between each pair of
children.

## Alignment

Alignment controls how children are positioned within a container's
available space. Two type aliases cover the axes:

```python
type AlignX = Literal["left", "center", "right"]
type AlignY = Literal["top", "center", "bottom"]
```

| Prop | Container | Values | Default |
|---|---|---|---|
| `align_x` | `column`, `container` | `"left"`, `"center"`, `"right"` | `"left"` |
| `align_y` | `row`, `container` | `"top"`, `"center"`, `"bottom"` | `"top"` |

`column` aligns children horizontally (they already stack vertically).
`row` aligns children vertically (they already flow horizontally).
`container` supports both axes since it has a single child. The
`center=True` shorthand on `container` is equivalent to
`align_x="center", align_y="center"`.

Spacing on `column`, `row`, `grid`, and `keyed_column` adds a gap
between siblings, not before the first or after the last child.

## Windows

```python
ui.window(id, child, **opts)
```

Every view tree returns one or more `window` nodes. The runtime treats
windows as the root layer: adding a window node opens an OS window,
removing one closes it, and changing props on an existing window
updates the native window. Window IDs must be stable strings. A changing
ID closes and reopens the window, losing its native state.

Windows accept a single child. Return a list of window nodes from
`view` to drive multiple windows from one app:

```python
from plushie import ui

def view(self, model):
    windows = [ui.window("main", main_content(model), title="App")]
    if model.show_settings:
        windows.append(
            ui.window(
                "settings",
                settings_content(model),
                title="Settings",
                exit_on_close_request=False,
            )
        )
    return windows
```

Closing a secondary window with `exit_on_close_request=False` removes
the window without exiting the app.

### Window props

| Prop | Type | Description |
|---|---|---|
| `title` | str | Title bar text. |
| `size` | `(w, h)` | Initial size in pixels. |
| `width` | Length | Width (alternative to `size`). |
| `height` | Length | Height (alternative to `size`). |
| `position` | `(x, y)` | Initial screen position. |
| `min_size` | `(w, h)` | Minimum dimensions. |
| `max_size` | `(w, h)` | Maximum dimensions. |
| `maximized` | bool | Start maximized. |
| `fullscreen` | bool | Start fullscreen. |
| `visible` | bool | Whether the window is visible. |
| `resizable` | bool | Allow resizing. |
| `closeable` | bool | Show the close button. |
| `minimizable` | bool | Allow minimizing. |
| `decorations` | bool | Show title bar and borders. |
| `transparent` | bool | Transparent window background. |
| `blur` | bool | Blur window background. |
| `level` | WindowLevel | `"normal"`, `"always_on_top"`, `"always_on_bottom"`. |
| `exit_on_close_request` | bool | Whether closing this window exits the app. |
| `scale_factor` | number | DPI scale override. |
| `theme` | str or dict | Per-window theme (`"dark"`, `"nord"`, `"system"`, or a custom theme value). |

`WindowLevel` and the related `WindowMode` (`"windowed"`,
`"fullscreen"`, `"hidden"`) aliases live in `plushie.types`.

### Default window props

Override `App.window_config(model)` to supply defaults applied to every
window opened by the app. Per-window props set in the view tree take
precedence over the defaults returned here:

```python
class MyApp(plushie.App[Model]):
    def window_config(self, model):
        return {
            "size": (1024, 768),
            "theme": model.theme,
            "min_size": (640, 480),
        }

    def view(self, model):
        return ui.window("main", content(model), title="My App")
```

Window lifecycle events arrive as `WindowEvent` instances. See the
[Events reference](events.md) for the full shape.

## Layout containers

### column

Arranges children vertically, top to bottom. Anonymous container:
optional `id=` kwarg does not create a scope.

| Prop | Type | Default | Description |
|---|---|---|---|
| `spacing` | number | `0` | Vertical gap between children. |
| `padding` | Padding | `0` | Inner padding. |
| `width` | Length | `"shrink"` | Column width. |
| `height` | Length | `"shrink"` | Column height. |
| `max_width` | number | | Maximum width in pixels. |
| `align_x` | AlignX | `"left"` | Horizontal alignment of children. |
| `clip` | bool | `False` | Clip children that overflow. |
| `wrap` | bool | `False` | Wrap children to the next column on overflow. |
| `a11y` | dict | | Accessibility overrides. |

`wrap=True` enables multi-column flow. When children exceed the column
height, they wrap into a new column to the right.

### row

Arranges children horizontally, left to right.

| Prop | Type | Default | Description |
|---|---|---|---|
| `spacing` | number | `0` | Horizontal gap between children. |
| `padding` | Padding | `0` | Inner padding. |
| `width` | Length | `"shrink"` | Row width. |
| `height` | Length | `"shrink"` | Row height. |
| `max_width` | number | | Maximum width in pixels. |
| `align_y` | AlignY | `"top"` | Vertical alignment of children. |
| `clip` | bool | `False` | Clip children that overflow. |
| `wrap` | bool | `False` | Wrap children to the next row on overflow. |
| `a11y` | dict | | Accessibility overrides. |

`wrap=True` is useful for tag clouds, toolbars, and any content that
should reflow at narrower widths.

### container

Single-child wrapper for styling, scoping, and alignment. Named
containers create ID scopes for descendant widgets (see
[Scoped IDs](scoped-ids.md)).

| Prop | Type | Default | Description |
|---|---|---|---|
| `padding` | Padding | `0` | Inner padding. |
| `width` | Length | `"shrink"` | Container width. |
| `height` | Length | `"shrink"` | Container height. |
| `max_width` | number | | Maximum width. |
| `max_height` | number | | Maximum height. |
| `align_x` | AlignX | `"left"` | Horizontal child alignment. |
| `align_y` | AlignY | `"top"` | Vertical child alignment. |
| `center` | bool | `False` | Center child in both axes. |
| `clip` | bool | `False` | Clip child that overflows. |
| `background` | Color or Gradient | | Background fill. |
| `color` | Color | | Text colour override. |
| `border` | Border | | Border specification. |
| `shadow` | Shadow | | Drop shadow. |
| `style` | str or StyleMap | | Named preset or full style map. |
| `a11y` | dict | | Accessibility overrides. |

Container serves three roles: styling (background, border, shadow),
scoping (named containers prefix descendant IDs), and alignment
(positioning a single child within available space). See the
[Styling reference](themes-and-styling.md) for `Color`, `Border`,
`Shadow`, and `StyleMap`.

### scrollable

Adds scroll bars when content overflows. Requires an explicit string ID
because the renderer tracks scroll position as internal state; a
changing ID resets the scroll position.

| Prop | Type | Default | Description |
|---|---|---|---|
| `width` | Length | `"shrink"` | Scrollable area width. |
| `height` | Length | `"shrink"` | Scrollable area height. |
| `direction` | `"vertical"` / `"horizontal"` / `"both"` | `"vertical"` | Scroll direction. |
| `spacing` | number | | Gap between scrollbar and content. |
| `scrollbar_width` | number | | Scrollbar track width. |
| `scrollbar_margin` | number | | Margin around scrollbar. |
| `scroller_width` | number | | Scroller handle width. |
| `scrollbar_color` | Color | | Scrollbar track colour. |
| `scroller_color` | Color | | Scroller thumb colour. |
| `anchor` | `"start"` / `"end"` | `"start"` | Scroll anchor position. |
| `on_scroll` | bool | `False` | Emit `Scrolled` events with viewport data. |
| `auto_scroll` | bool | `False` | Auto-scroll to reveal new content at the anchor. |
| `a11y` | dict | | Accessibility overrides. |

`anchor="end"` with `auto_scroll=True` is the chat-log pattern: the
viewport starts pinned to the bottom and follows new content until the
user scrolls away.

### stack

Layers children on top of each other along the z-axis. The first child
is at the back, the last child is at the front. Anonymous container.

| Prop | Type | Default | Description |
|---|---|---|---|
| `width` | Length | `"shrink"` | Stack width. |
| `height` | Length | `"shrink"` | Stack height. |
| `clip` | bool | `False` | Clip children that overflow. |
| `a11y` | dict | | Accessibility overrides. |

Use for overlays, badges, loading spinners, or anywhere elements need
to visually layer.

### grid

Arranges children in a grid. Anonymous container.

| Prop | Type | Default | Description |
|---|---|---|---|
| `columns` | int | `1` | Number of columns (fixed-column mode). |
| `spacing` | number | `0` | Gap between cells. |
| `width` | number | | Grid width in pixels. |
| `height` | number | | Grid height in pixels. |
| `column_width` | Length | | Width of each column. |
| `row_height` | Length | | Height of each row. |
| `fluid` | number | | Max cell width for fluid auto-wrap mode. |
| `a11y` | dict | | Accessibility overrides. |

Two modes: **fixed columns** (`columns=3`) and **fluid** (`fluid=200`).
In fluid mode, the number of columns adjusts to fit as many cells of
the specified maximum width as possible at the current container width.

### keyed_column

Like `column`, but children are matched by ID instead of position when
diffing. Use for dynamic lists where items are added, removed, or
reordered: a plain `column` would shift widget state (cursor, focus,
scroll) by one every time an item appears at the top.

| Prop | Type | Default | Description |
|---|---|---|---|
| `spacing` | number | `0` | Vertical gap between children. |
| `padding` | Padding | `0` | Inner padding. |
| `width` | Length | `"shrink"` | Column width. |
| `height` | Length | `"shrink"` | Column height. |
| `max_width` | number | | Maximum width in pixels. |
| `align_x` | AlignX | `"left"` | Horizontal alignment of children. |
| `a11y` | dict | | Accessibility overrides. |

Unlike `column`, `keyed_column` has no `clip` or `wrap`.

### responsive

Adapts layout based on available size. Accepts at most one child.

| Prop | Type | Default | Description |
|---|---|---|---|
| `width` | Length | `"fill"` | Container width. |
| `height` | Length | `"fill"` | Container height. |
| `a11y` | dict | | Accessibility overrides. |

When the container's size changes, the renderer emits a `Resize` event
with `width` and `height` fields. Store the measured size in the model
and branch the view on it to switch between layouts at breakpoints.

### pin

Positions a child at absolute pixel coordinates within the container.
The child is taken out of flow layout.

| Prop | Type | Default | Description |
|---|---|---|---|
| `x` | number | `0` | X position in pixels. |
| `y` | number | `0` | Y position in pixels. |
| `width` | Length | `"shrink"` | Pin container width. |
| `height` | Length | `"shrink"` | Pin container height. |
| `a11y` | dict | | Accessibility overrides. |

Useful for tooltips, popovers, or custom-positioned overlays above a
`stack` base.

### floating

Applies translate and scale transforms to a child. Unlike `pin`, the
child still occupies its original space in flow layout; the transform
is visual only.

| Prop | Type | Default | Description |
|---|---|---|---|
| `translate_x` | number | `0` | Horizontal translation in pixels. |
| `translate_y` | number | `0` | Vertical translation in pixels. |
| `scale` | number | | Scale factor. |
| `width` | Length | | Container width. |
| `height` | Length | | Container height. |
| `a11y` | dict | | Accessibility overrides. |

Combine with `plushie.animation.Transition` or `Spring` on
`translate_x`, `translate_y`, and `scale` for renderer-side animated
motion.

### space

Invisible spacer widget. No children, no visual output. Auto-ID.

| Prop | Type | Default | Description |
|---|---|---|---|
| `width` | Length | `"shrink"` | Space width. |
| `height` | Length | `"shrink"` | Space height. |
| `a11y` | dict | | Accessibility overrides. |

Use for explicit gaps, alignment tricks, or pushing siblings apart in
a row or column (for example, a `space(width="fill")` between two
groups of buttons).

## See also

- [Built-in Widgets reference](built-in-widgets.md) - full widget
  catalog including leaf widgets and interaction wrappers
- [Styling reference](themes-and-styling.md) - Color, Border, Shadow,
  Gradient, StyleMap for styled containers
- [Scoped IDs reference](scoped-ids.md) - how named containers create
  ID scopes
- [Accessibility reference](accessibility.md) - the `a11y` prop, roles,
  and keyboard navigation
- [Events reference](events.md) - `Resize`, `Scrolled`, and
  `WindowEvent` payloads
