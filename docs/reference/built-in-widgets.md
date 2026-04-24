# Built-in Widgets

All built-in widgets are available as builder functions on the
`plushie.ui` module. Each function returns a plain `dict` matching the
wire protocol's node shape, so builder output and hand-written dicts
mix freely:

```python
from plushie import ui

ui.button("save", "Save", width="fill")
```

Prop names match the wire protocol exactly (snake_case). Container
widgets take children as `*args` and options as `**kwargs`.
Interactive leaf widgets take `id` as the first positional argument.
Display widgets with auto-id sugar (`text`, `markdown`, `progress_bar`)
accept either one content argument (auto-generated ID) or an explicit
`(id, content)` pair.

## Widget catalog

### Layout

| Function | Description |
|---|---|
| `ui.window` | Top-level window with title, size, position, theme |
| `ui.column` | Arranges children vertically |
| `ui.row` | Arranges children horizontally |
| `ui.container` | Single-child wrapper for styling, scoping, alignment |
| `ui.scrollable` | Scrollable viewport around child content |
| `ui.stack` | Layers children on top of each other (z-axis) |
| `ui.grid` | Fixed-column or fluid grid layout |
| `ui.keyed_column` | Vertical layout with ID-based diffing for dynamic lists |
| `ui.responsive` | Emits resize events for adaptive layouts |
| `ui.pin` | Positions child at absolute coordinates |
| `ui.floating` | Applies translate/scale transforms to child |
| `ui.space` | Invisible spacer |

Full prop tables for all layout containers are in the
[Layout reference](windows-and-layout.md).

### Input

| Function | Signature | Events |
|---|---|---|
| `ui.button` | `button(id, label, **opts)` | `Click` |
| `ui.text_input` | `text_input(id, value, **opts)` | `Input`, `Submit`, `Paste` |
| `ui.text_editor` | `text_editor(id, content, **opts)` | `Input` |
| `ui.checkbox` | `checkbox(id, checked, **opts)` | `Toggle` (bool) |
| `ui.toggler` | `toggler(id, is_toggled, **opts)` | `Toggle` (bool) |
| `ui.radio` | `radio(id, value, selected, **opts)` | `Select` |
| `ui.slider` | `slider(id, range, value, **opts)` | `Slide`, `SlideRelease` |
| `ui.vertical_slider` | `vertical_slider(id, range, value, **opts)` | `Slide`, `SlideRelease` |
| `ui.pick_list` | `pick_list(id, options, selected, **opts)` | `Select`, `Open`, `Close` |
| `ui.combo_box` | `combo_box(id, options, value, **opts)` | `Input`, `Select`, `Open`, `Close` |

Every widget-level interaction delivers an event instance whose class
matches the row in the event column. Event classes live in
`plushie.events` and are imported directly into `match` / `case`
blocks. See the [Events reference](events.md) for the full list and
pattern-matching guide.

**button** is the simplest interactive widget. The label is the
second positional argument. Emits `Click` on press.

**text_input** is a single-line editable field. Emits `Input` on
every keystroke with the full text as `value`. Emits `Submit` on
Enter when `on_submit=True` is set. `Paste` fires when the user
pastes into the field and `on_paste=True` is set.

**text_editor** is a multi-line editable area with syntax highlighting
support (`highlight_syntax="python"`). The `content` argument seeds
the initial text. Holds renderer-side state (cursor, selection,
scroll).

**checkbox** / **toggler** are boolean toggles. Both emit `Toggle`
with the new boolean on the `value` field. `checkbox` shows a box;
`toggler` shows a switch. Pass `label=` for accessible text.

**slider** / **vertical_slider** are range inputs. `range` is a
`(min, max)` tuple of floats. Emits `Slide` continuously while
dragging and `SlideRelease` when the drag ends with the final value.
Supports `circular_handle=True` for a round handle, with
`handle_radius` controlling the circle's radius.

**pick_list** is a dropdown selection. `options` is a list of
strings. `selected` is the currently selected value (or `None`).
Emits `Select` when an option is chosen.

**combo_box** is a searchable dropdown. Combines a text input with a
filtered option list. Holds renderer-side state (search text, open
state). Emits `Input` on typing and `Select` on option selection.

**radio** is a one-of-many selection. `value` is the option this
radio represents; `selected` is the currently selected value from
the model. The radio is checked when `value == selected`. Emits
`Select` with the radio's value.

### Display

| Function | Signature | Description |
|---|---|---|
| `ui.text` | `text(content)` or `text(id, content)` | Static text display |
| `ui.rich_text` | `rich_text(id, spans=...)` | Styled text with per-span formatting |
| `ui.rule` | `rule(**opts)` | Horizontal or vertical divider |
| `ui.progress_bar` | `progress_bar(range, value)` or `progress_bar(id, range, value)` | Progress indicator |
| `ui.tooltip` | `tooltip(id, tip, child, **opts)` | Popup tip on hover |
| `ui.image` | `image(id, source, **opts)` | Raster image from file path or handle |
| `ui.svg` | `svg(id, source, **opts)` | Vector image from SVG file |
| `ui.qr_code` | `qr_code(id, data, **opts)` | QR code from a data string |
| `ui.markdown` | `markdown(content)` or `markdown(id, content)` | Rendered markdown |
| `ui.canvas` | `canvas(id, layers=..., **opts)` | Drawing surface with named layers |

**text** supports auto-ID (`ui.text("Hello")`) and explicit-ID
(`ui.text("greeting", "Hello")`). Key props: `size`, `color`, `font`,
`wrapping`, `shaping`, `align_x`, `align_y`.

**rich_text** displays styled text with individually formatted spans.
Each span is a `plushie.types.Span` instance or a plain dict with
optional keys: `text`, `size`, `color`, `font`, `link`, `underline`,
`strikethrough`, `line_height`, `padding`, `highlight`. Example:

```python
from plushie import ui
from plushie.types import Span

ui.rich_text(
    "greeting",
    spans=[
        Span(text="Hello, ", size=16),
        Span(text="world", size=16, color="#3b82f6", underline=True),
        Span(text="!", size=16),
    ],
)
```

**tooltip** wraps a child widget. The child is the anchor; `tip` is
the tooltip text. Props: `position` (`"top"`, `"bottom"`, `"left"`,
`"right"`, `"follow_cursor"`), `gap`.

**image** renders a raster image. Two source modes:

- **Path-based** (preferred): `ui.image("photo", "path/to/file.png")`.
  The renderer loads the file directly. No wire transfer.
- **Handle-based**: `ui.image("photo", {"handle": "avatar"})`.
  References an in-memory image created via `Command.create_image`.

Key props: `content_fit`, `filter_method`, `width`, `height`,
`opacity`, `rotation` (degrees), `border_radius`, `scale`, `crop`
(`{"x": ..., "y": ..., "width": ..., "height": ...}`), `alt`
(accessible label).

**In-memory image handles:**

```python
from plushie import Command

def update(self, model, event):
    return model, Command.create_image("avatar", png_bytes)

# Create from raw RGBA pixels:
Command.create_image_rgba("avatar", 512, 512, rgba_pixels)

# Reference in view:
ui.image("display", {"handle": "avatar"})

# Update pixels:
Command.update_image("avatar", new_pixels)

# Delete:
Command.delete_image("avatar")
```

Handle-based images send the entire payload over the wire in a single
message, which blocks all other protocol traffic for large images.
Prefer path-based loading when the file exists on disk. A chunked
streaming alternative for large dynamic images is planned.

**canvas** contains named layers of shapes. See the
[Canvas reference](canvas.md).

## Table

`ui.table`, `ui.table_row`, `ui.cell`

**table** displays structured data in rows and columns with sortable
headers, row selection highlighting, and optional striped backgrounds.
Rows are real tree children, so adding, removing, or reordering rows
produces minimal wire patches instead of re-sending the entire
dataset.

```python
ui.table(
    "users",
    *(
        ui.table_row(
            user.id,
            ui.cell("name", ui.text(user.name)),
            ui.cell("email", ui.text(user.email)),
            ui.cell("actions", ui.button(f"del-{user.id}", "Delete")),
        )
        for user in model.users
    ),
    columns=cols,
    selected=list(model.selection.selected()),
)
```

For simple text-only tables, the `rows=` shorthand avoids passing
children entirely:

```python
ui.table("users", columns=cols, rows=model.users)
```

Both forms are mutually exclusive. The `rows=` shorthand expands to
`table_row` / `cell` children during normalization.

### Columns

Column definitions are dicts passed via the `columns=` prop. Every
column needs a `key` (matching the row data field) and a `label`
(header text):

```python
columns = [
    {"key": "name", "label": "Name", "sortable": True, "width": "fill"},
    {"key": "email", "label": "Email"},
    {"key": "role", "label": "Role", "align": "center", "width": 120},
]
```

| Key | Type | Default | Description |
|---|---|---|---|
| `key` | str | required | Row data lookup key |
| `label` | str | required | Header display text |
| `sortable` | bool | `False` | Header clickable for sort |
| `width` | Length | `"fill"` | Column width |
| `align` | `"left"` / `"center"` / `"right"` | `"left"` | Cell alignment |

### Rich cells

Inside a `table_row`, each `cell` maps to a column by key. Cells can
contain any widget, not just text:

```python
ui.table_row(
    user.id,
    ui.cell("name", ui.text(user.name, font=Font(weight="bold"))),
    ui.cell("status", ui.progress_bar("prog", (0, 100), user.progress)),
    ui.cell(
        "actions",
        ui.button(f"edit-{user.id}", "Edit"),
        ui.button(f"del-{user.id}", "Delete"),
    ),
)
```

### Sorting

Mark columns as `sortable=True`. Clicking a sortable header emits a
`Sort` event with the column key as `value`. The table displays the
sort indicator but does not reorder rows; sort in your model:

```python
def update(self, model, event):
    match event:
        case Sort(id="users", value=col):
            order = "desc" if model.sort_by == col and model.sort_order == "asc" else "asc"
            rows = sorted(model.users, key=lambda u: u[col], reverse=order == "desc")
            return replace(model, users=tuple(rows), sort_by=col, sort_order=order)
```

### Selection

Selection is app-managed. Pass selected row IDs via the `selected=`
prop; the renderer highlights those rows. Handle row click events to
update selection state using `plushie.selection.Selection`:

```python
from plushie.selection import Selection

def update(self, model, event):
    match event:
        case Click(id=row_id) if row_id.startswith("row-"):
            return replace(model, selection=model.selection.toggle(row_id))
```

### Props

| Prop | Type | Default | Description |
|---|---|---|---|
| `columns` | `list[dict]` | | Column definitions (see above) |
| `rows` | `list[dict]` | | Data shorthand: text-only rows |
| `header` | bool | `True` | Show header row |
| `selected` | `list[str]` | | Row IDs to highlight |
| `striped` | bool | `False` | Alternate row backgrounds |
| `separator` | float | `1.0` | Divider thickness (0.0 to hide) |
| `separator_color` | Color | | Divider colour |
| `sort_by` | str | | Currently sorted column key |
| `sort_order` | `"asc"` / `"desc"` | | Sort direction |
| `width` | Length | `"fill"` | Table width |
| `height` | Length | | Table height (scrollable when set) |
| `padding` | Padding | | Cell internal padding |
| `header_text_size` | number | | Header font size |
| `row_text_size` | number | | Body font size (data shorthand) |

## Pane grid

`ui.pane_grid`

Resizable tiled pane layout. Children are keyed by their node ID and
rendered as individual panes. The renderer manages internal pane
sizes and arrangement, persisted across re-renders by the widget's
ID.

```python
ui.pane_grid(
    "editor",
    ui.text_editor("left", model.left_source),
    ui.text_editor("right", model.right_source),
    panes=["left", "right"],
    spacing=2,
)
```

### Pane grid props

| Prop | Type | Default | Purpose |
|---|---|---|---|
| `panes` | `list[str]` | required | Pane identifiers |
| `spacing` | number | `2` | Space between panes in pixels |
| `width` | Length | `"fill"` | Grid width |
| `height` | Length | `"fill"` | Grid height |
| `min_size` | number | `10` | Minimum pane size in pixels |
| `divider_color` | Color | | Color for the split divider |
| `divider_width` | number | | Divider thickness in pixels |
| `leeway` | number | | Grabbable area around dividers in pixels |
| `split_axis` | `"horizontal"` / `"vertical"` | | Initial split direction |

### Pane grid events

| Event | Data | Description |
|---|---|---|
| `Click` | | Emitted when a pane is selected |
| `Slide` | `value` is ratio float | Emitted when a split divider is moved |
| `Drag` | | Emitted during pane drag operations |
| `KeyBinding` | | Emitted on F6 / Shift+F6 focus cycling |

The pane grid holds renderer-side state (pane sizes and arrangement).
If the widget's ID changes, this state resets. An explicit string ID
is required.

For accessibility, wrap the pane grid in a container with an explicit
role and label:

```python
ui.container(
    "editor-panes",
    ui.pane_grid(
        "grid",
        ui.text_editor("left", model.left),
        ui.text_editor("right", model.right),
        panes=["left", "right"],
    ),
    a11y={"role": "group", "label": "Editor panes"},
)
```

## Interaction wrappers

### pointer_area

Wraps a single child and captures pointer events from mouse, touch,
and pen input. Use for right-click menus, hover detection, drag
tracking, scroll capture, and custom cursor styles. All events use
the unified pointer model: the `pointer` field (`"mouse"`, `"touch"`,
`"pen"`) identifies the device, and `modifiers` carries the current
modifier key state for shift-click, ctrl-drag, and similar patterns.

| Prop | Type | Purpose |
|---|---|---|
| `cursor` | str | Mouse cursor on hover |
| `on_press` | bool | Enable left button press |
| `on_release` | bool | Enable left button release |
| `on_right_press` | bool | Enable right button press |
| `on_right_release` | bool | Enable right button release |
| `on_middle_press` | bool | Enable middle button press |
| `on_middle_release` | bool | Enable middle button release |
| `on_double_click` | bool | Enable double-click |
| `on_enter` | bool | Enable cursor enter |
| `on_exit` | bool | Enable cursor exit |
| `on_move` | bool | Enable cursor move (coalescable) |
| `on_scroll` | bool | Enable scroll wheel (coalescable) |
| `event_rate` | int | Max events/sec for move and scroll |
| `a11y` | dict | Accessibility overrides |

Cursor values: `"pointer"`, `"grab"`, `"grabbing"`, `"crosshair"`,
`"text"`, `"move"`, `"not_allowed"`, `"progress"`, `"wait"`,
`"help"`, `"resizing_horizontally"`, `"resizing_vertically"`, and
others.

Move, press, and scroll events carry `pointer` (device type) and
`modifiers` (current modifier key state):

```python
from plushie.events import Move, Press, Scroll

ui.pointer_area(
    "canvas-area",
    ui.canvas("drawing", width=400, height=300),
    on_move=True,
    on_press=True,
    on_scroll=True,
    cursor="crosshair",
)

def update(self, model, event):
    match event:
        case Press(id="canvas-area", pointer="mouse", modifiers=m) if m.shift:
            return add_to_selection(model)
        case Move(id="canvas-area", x=x, y=y, modifiers=m) if m.ctrl:
            return pan_canvas(model, x, y)
        case Scroll(id="canvas-area", delta_y=dy, pointer="mouse"):
            return zoom(model, dy)
        case _:
            return model
```

### sensor

Wraps a single child and emits events when the child's size changes
or when it enters / exits visibility. Useful for responsive layouts,
lazy loading, and intersection observation.

| Prop | Type | Purpose |
|---|---|---|
| `delay` | int | Delay (ms) before emitting events |
| `anticipate` | number | Distance (px) to anticipate visibility |
| `on_resize` | bool | Enable resize events |
| `event_rate` | int | Max events/sec for resize |
| `a11y` | dict | Accessibility overrides |

Emits `Resize` with `width` and `height` fields.

### overlay

Positions the second child as a floating overlay relative to the
first child (anchor). Exactly two children required.

| Prop | Type | Default | Purpose |
|---|---|---|---|
| `position` | `"below"` / `"above"` / `"left"` / `"right"` | `"below"` | Overlay position |
| `gap` | number | `0` | Space between anchor and overlay |
| `offset_x` | number | `0` | Horizontal offset after positioning |
| `offset_y` | number | `0` | Vertical offset after positioning |
| `flip` | bool | `False` | Auto-flip when overlay overflows viewport |
| `align` | `"start"` / `"center"` / `"end"` | `"center"` | Cross-axis alignment |
| `width` | Length | | Overlay container width |
| `a11y` | dict | | Accessibility overrides |

The overlay renders above all other content at the positioned
location. See the
[Composition Patterns reference](composition-patterns.md) for a
popover menu example.

### themer

Applies a different theme to its children. Single child, single prop:

```python
ui.themer(
    "dark-section",
    ui.container(
        "inner",
        ui.text("info", "This section uses the dark theme"),
        padding=12,
    ),
    theme="dark",
)
```

## Common props

Most widgets support a subset of these cross-cutting props:

- **`style`** - visual appearance. Accepts a preset string (e.g.
  `"primary"`, `"danger"`) or a `StyleMap` instance. See the
  [Styling reference](themes-and-styling.md).
- **`a11y`** - accessibility attributes. Accepts a dict or a
  `plushie.types.A11y` instance. See the
  [Accessibility reference](accessibility.md).
- **`width`** / **`height`** - sizing. Accepts `"fill"`, `"shrink"`,
  `{"fill_portion": n}`, or a pixel number. See the
  [Layout reference](windows-and-layout.md).
- **`event_rate`** - max events per second for high-frequency events.
  Supported on `slider`, `vertical_slider`, `pointer_area`, `sensor`,
  `canvas`, and `pane_grid`.

## Renderer-side state

Some widgets hold state in the renderer that persists across
re-renders. If their ID changes, this state resets:

- **`text_input`** - cursor position, selection, undo history
- **`text_editor`** - cursor, selection, scroll position, undo
- **`combo_box`** - search text, open / closed state
- **`scrollable`** - scroll position
- **`pane_grid`** - pane sizes and arrangement

These widgets require explicit string IDs.

## keyed_column vs column

Use `column` for static layouts. Use `keyed_column` when children are
dynamic (added, removed, reordered). It diffs by child ID instead of
position, preserving widget state across list changes. Same props as
column minus `align_x`, `clip`, and `wrap`.

## Auto-ID vs explicit ID

Layout containers (`column`, `row`, `stack`, `grid`, `keyed_column`,
`responsive`) and a few display widgets (`text`, `markdown`, `rule`,
`space`, `progress_bar`) support auto-generated IDs. Omit the ID
(pass only the content for display widgets, or only children for
containers) and one is generated from the position in the tree.

All interactive and stateful widgets require explicit string IDs for
event routing and state persistence. See the
[Scoped IDs reference](scoped-ids.md) for how IDs flow through nested
scopes.

## Animatable props

Numeric props support renderer-side transitions via
`plushie.animation.Transition`, `Spring`, and `Sequence`. Commonly
animated: `max_width`, `max_height`, `opacity`, `translate_x`,
`translate_y`, `scale`. See the
[Animation reference](animation.md).

## Prop value types

These prop types are used across multiple widgets. The full styling
types (Color, Theme, StyleMap, Border, Shadow, Gradient) are in the
[Styling reference](themes-and-styling.md). Layout types (Length,
Padding, Alignment) are in the
[Layout reference](windows-and-layout.md).

### Font

Used by: `text`, `rich_text`, `text_input`, `text_editor`.

| Value | Meaning |
|---|---|
| `"default"` | System default proportional font |
| `"monospace"` | System monospace font |
| `"Family Name"` | Specific font family (must be loaded via `settings()`) |
| `Font(...)` | Full font spec with `family`, `weight`, `style`, `stretch` |

`plushie.types.Font` is a frozen dataclass. `weight` accepts
`"thin"` through `"black"`, `style` accepts `"normal"`, `"italic"`,
`"oblique"`, and `stretch` accepts `"ultra_condensed"` through
`"ultra_expanded"`.

### Shaping

Used by: `text`, `rich_text`, `text_input`, `text_editor`.

| Value | Meaning |
|---|---|
| `"basic"` | Simple left-to-right shaping (fastest) |
| `"advanced"` | Full Unicode shaping (ligatures, RTL, complex scripts) |

### Wrapping

Used by: `text`, `rich_text`.

| Value | Meaning |
|---|---|
| `"none"` | No wrapping (text overflows) |
| `"word"` | Break at word boundaries |
| `"glyph"` | Break at any character |
| `"word_or_glyph"` | Try word boundaries first, fall back to glyph |

### Content fit

Used by: `image`, `svg`.

| Value | Meaning |
|---|---|
| `"contain"` | Scale to fit within bounds, preserving aspect ratio |
| `"cover"` | Scale to fill bounds, cropping if needed |
| `"fill"` | Stretch to fill bounds exactly (may distort) |
| `"none"` | No scaling (original size) |
| `"scale_down"` | Like `"contain"` but never scales up |

### Filter method

Used by: `image`.

| Value | Meaning |
|---|---|
| `"nearest"` | Pixel-perfect interpolation (blocky, good for pixel art) |
| `"linear"` | Smooth interpolation (good for photos) |

### Tooltip position

Used by: `tooltip`.

| Value | Meaning |
|---|---|
| `"top"` | Above the widget |
| `"bottom"` | Below the widget |
| `"left"` | Left of the widget |
| `"right"` | Right of the widget |
| `"follow_cursor"` | Follows the mouse cursor |

### Scroll direction

Used by: `scrollable`.

| Value | Meaning |
|---|---|
| `"vertical"` | Vertical scrolling (default) |
| `"horizontal"` | Horizontal scrolling |
| `"both"` | Bidirectional scrolling |

### Scroll anchor

Used by: `scrollable`.

| Value | Meaning |
|---|---|
| `"start"` | Anchor at the top / left (default) |
| `"end"` | Anchor at the bottom / right |

### Auto scroll

Used by: `scrollable`.

When `auto_scroll=True` is set, the scrollable automatically scrolls
to reveal new content appended at the anchor end. Useful for chat
logs, terminal output, and other append-only content where the user
expects to see the latest entries without manual scrolling.

```python
ui.scrollable(
    "log",
    ui.column(
        *(ui.text(entry.id, entry.text) for entry in model.log_entries),
        spacing=4,
    ),
    direction="vertical",
    anchor="end",
    auto_scroll=True,
)
```

When the user manually scrolls away from the anchor, auto-scroll
pauses to avoid fighting the user's position. It resumes when the
user scrolls back to the anchor end.

## Memoization

`ui.memo(key, deps, body)` caches a view subtree by a stable key plus
a tuple of hashable dependencies. `body` is a zero-argument callable
that returns a node or list of nodes; it is only evaluated on cache
miss.

```python
ui.column(
    ui.memo(
        "header",
        (model.user_id, model.revision),
        lambda: expensive_header(model),
    ),
    ui.text(model.dynamic_text),
)
```

Any `deps` value that supports equality works: tuples, strings,
ints, or frozen dataclasses. Avoid unhashable or non-equal types
(sets of mutable objects, `NaN`) since they defeat the cache
comparison.

## See also

- [Layout reference](windows-and-layout.md) - sizing, alignment, and
  all layout containers with full prop tables
- [Styling reference](themes-and-styling.md) - Color, Theme,
  StyleMap, Border, Shadow, Gradient
- [Canvas reference](canvas.md) - shapes, layers, interactive
  elements
- [Accessibility reference](accessibility.md) - the `a11y` prop,
  roles, and keyboard navigation
- [Events reference](events.md) - all event classes delivered by
  widgets
- [Animation reference](animation.md) - transition, spring, sequence
  descriptors
