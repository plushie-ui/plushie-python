# Canvas

The pad has a sidebar list, an editor, a preview, and an event log. Every pixel so far has come from a built-in widget. Some things do not fit that mold: a line chart of save activity, a mini-map of the experiment tree, a bespoke toolbar icon. For those you drop into a canvas: a 2D drawing surface where you compose shapes instead of widgets.

This chapter covers the canvas vocabulary and then adds two canvas panels to the pad. A sparkline visualizes save counts over time. A mini-map renders a clickable dot per experiment so the sidebar can stay compact when the list grows.

The full shape catalog, path command list, and interaction props live in the [Canvas reference](../reference/canvas.md). Pointer event fields live in the [Events reference](../reference/events.md).

## The canvas widget

`ui.canvas(id, **kwargs)` creates a canvas node. The first positional arg is the canvas ID. Content goes in either `layers=` (a dict of named shape lists) or `shapes=` (a flat list). Size comes from `width` and `height`, using the same `Length` values as any other widget.

```python
from plushie import ui
from plushie import canvas as c

ui.canvas(
    "demo",
    width=200,
    height=100,
    background="#f5f5f5",
    layers=dict([
        c.layer("bg", c.rect(0, 0, 200, 100, fill="#f0f0f0")),
        c.layer("fg", c.circle(100, 50, 20, fill="#3b82f6")),
    ]),
)
```

Shape builders in `plushie.canvas` return plain dicts that the renderer reads directly. There is no canvas DSL. You assemble lists of dicts, and the builder names exist so you never have to type the wire keys by hand.

## Shapes

Every shape accepts a `fill` (color, gradient, or pattern), a `stroke` (built with `c.stroke`), and an `opacity` in `[0.0, 1.0]`.

```python
from plushie import canvas as c

c.rect(0, 0, 100, 50, fill="#3b82f6", radius=6)
c.circle(50, 50, 20, fill="#22c55e", stroke=c.stroke("#0a0", 2))
c.line(0, 0, 100, 100, stroke=c.stroke("#333", 1))
c.canvas_text(50, 11, "Save", fill="#ffffff", size=14)
```

`rect` accepts `radius` as a number for uniform corners or a per-corner dict with `top_left`, `top_right`, `bottom_right`, `bottom_left`. `c.stroke(color, width, cap=..., join=...)` builds the stroke descriptor.

Paths use a list of commands for arbitrary geometry:

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

The reference documents `bezier_to`, `quadratic_to`, `arc`, `arc_to`, `ellipse`, and `rounded_rect` for curved segments.

## Layers and z-order

Canvas layers name groups of shapes. The renderer caches each layer independently, so a dynamic layer can redraw without re-tessellating the static content behind it. Layers draw in alphabetical order by name, which is why the color picker widget in the catalog uses `a_ring`, `b_sv_hue`, `c_sv_dark`, `d_cursors`. The prefix makes intent obvious at the call site.

```python
ui.canvas(
    "chart",
    width=400,
    height=200,
    layers=dict([
        c.layer("a_background", c.rect(0, 0, 400, 200, fill="#0f172a")),
        c.layer("b_grid", *_grid_lines()),
        c.layer("c_data", *_bars(data)),
        c.layer("d_labels", *_axis_labels(data)),
    ]),
)
```

Keep static content on its own layer. Interactive cursors and hover highlights belong on top so they always paint over the data.

## Transforms and grouping

Transforms apply to groups, not to individual shapes. `c.group(*children, **opts)` wraps shapes for positioning, rotation, scaling, or clipping. The `x` and `y` kwargs desugar to a leading `translate`; anything else in the `transforms` list applies in order.

```python
c.group(
    c.rect(0, 0, 40, 40, fill="#ef4444"),
    x=100, y=50,
    transforms=[c.rotate(45)],
)
```

`c.rotate(45)` takes degrees by default. For explicit units, pass a tuple: `c.rotate((0.785, "rad"))`. `c.scale(x, y)` takes separate x and y factors; `c.scale_uniform(factor)` takes one.

`c.clip(x, y, w, h)` restricts a group's drawing to a rectangle. One clip per group:

```python
c.group(
    c.circle(40, 40, 60, fill="#3b82f6"),
    clip=c.clip(0, 0, 80, 80),
)
```

## Interactive elements

To receive events from a canvas region, wrap shapes in a group with an ID and interaction kwargs. The first positional arg to `c.group` is the optional string ID. Presence of an ID combined with an interaction kwarg makes the group hit-testable.

```python
c.group(
    c.rect(0, 0, 120, 36, fill="#3b82f6", radius=6),
    c.canvas_text(60, 11, "Save", fill="#ffffff", size=14),
    "save",
    on_click=True,
    focusable=True,
    cursor="pointer",
    hover_style={"fill": "#2563eb"},
    pressed_style={"fill": "#1d4ed8"},
    a11y={"role": "button", "label": "Save experiment"},
)
```

`c.interactive(shape, "id", ...)` is a sugar that wraps a single shape in an interactive group, merging the interaction kwargs in. Use it when you have one shape; use `c.group` when you have several.

Interaction kwargs and visual feedback props (`hover_style`, `pressed_style`, `focus_style`) are validated renderer-side. The [Canvas reference](../reference/canvas.md) lists every prop.

### Event delivery

Element-level events arrive as the same classes used elsewhere in the SDK. The element's group ID is in `event.id`; the canvas ID plus window ID are in `event.scope`. Match both to disambiguate canvas clicks from plain widget clicks that happen to share an ID.

```python
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="save", scope=("save_canvas", *_)):
            return _save(model)
        case _:
            return model
```

Canvas-level events (`Press`, `Release`, `Move`, `Scroll`) fire when the corresponding `on_press`, `on_release`, `on_move`, `on_scroll` prop is set on the canvas widget itself. They carry `x`, `y`, `pointer`, `modifiers`, and for touch input a `finger` ID. Use these when you are driving freehand drawing, panning, or custom drag behavior that spans the whole canvas.

```python
from plushie.events import Move, Scroll

case Move(id="sketch", pointer="touch", finger=f, x=x, y=y):
    return _extend_stroke(model, f, x, y)

case Scroll(id="sketch", delta_y=dy, modifiers=m) if m.ctrl:
    return _zoom(model, dy)
```

High-frequency `Move` events are coalesced by the runtime. You do not need to throttle them in application code.

## Gradients and shadows

Canvas fills accept gradient values built with `c.linear_gradient`. The signature takes a start point, an end point (both in canvas coordinates), and a list of `(offset, color)` stops:

```python
c.rect(
    0, 0, 200, 50,
    fill=c.linear_gradient(
        (0, 0), (200, 0),
        [(0.0, "#3b82f6"), (1.0, "#1d4ed8")],
    ),
)
```

This is distinct from widget-background gradients built with `Gradient.linear_from_angle` in `plushie.types`, which take an angle instead of coordinate pairs. The [Themes and Styling reference](../reference/themes-and-styling.md) covers widget-background gradients and the `Shadow` value used for widget drop shadows. Canvas shapes do not take a `Shadow` value directly; for a drop shadow under a shape, draw a blurred offset copy on a lower layer.

## A sparkline for the pad

The pad's `_log` helper already tracks save events. Derive a per-experiment save count from `model.event_log`, draw a connected line at the top of the event log panel, and you have a quick visual of which experiments you have iterated on today.

```python
from plushie import ui
from plushie import canvas as c


def _sparkline(model) -> dict:
    counts_by_index = _save_counts(model.event_log)
    if not counts_by_index:
        return ui.text("spark-empty", "No saves yet", size=12)

    width, height = 220, 48
    max_count = max(counts_by_index) or 1
    step = width / max(len(counts_by_index) - 1, 1)

    points = [
        c.move_to(0, _y(counts_by_index[0], max_count, height)),
        *(
            c.line_to(i * step, _y(v, max_count, height))
            for i, v in enumerate(counts_by_index[1:], start=1)
        ),
    ]

    return ui.canvas(
        "spark",
        width=width,
        height=height,
        layers=dict([
            c.layer("a_bg", c.rect(0, 0, width, height, fill="#0f172a", radius=4)),
            c.layer(
                "b_line",
                c.path(points, stroke=c.stroke("#38bdf8", 2)),
            ),
        ]),
    )


def _y(value: int, max_count: int, height: int) -> float:
    return height - 4 - (value / max_count) * (height - 8)


def _save_counts(log) -> tuple[int, ...]:
    saves = tuple(entry for entry in reversed(log) if entry.kind == "saved")
    if not saves:
        return ()
    return tuple(i + 1 for i, _ in enumerate(saves))
```

The sparkline is a layout leaf like any other. Drop it into the event log panel above the list of entries:

```python
def _event_log(model):
    return ui.container(
        "log",
        ui.column(
            ui.text("log-title", "Event log", size=14),
            _sparkline(model),
            *(
                ui.text(f"log-{i}", f"{e.kind}: {e.detail}")
                for i, e in enumerate(model.event_log)
            ),
            padding=8,
            spacing=4,
        ),
        width=240,
        height="fill",
    )
```

No events. No interaction. Just a derived view of the model, drawn as shapes.

## A mini-map of experiments

The sidebar lists experiments as named buttons. For a larger collection that is fine on paper, less fine on a narrow screen. A mini-map at the top of the sidebar renders one dot per experiment and highlights the selected one. Clicking a dot selects that experiment, identical to clicking the list button below.

```python
def _minimap(model) -> dict:
    if not model.experiments:
        return ui.text("minimap-empty", "No experiments", size=12)

    width, height = 200, 60
    radius = 6
    gap = 18
    origin_x = radius + 4
    origin_y = height // 2

    dots = [
        c.interactive(
            c.circle(
                origin_x + i * gap,
                origin_y,
                radius,
                fill="#38bdf8" if exp.name == model.selected else "#64748b",
                stroke=c.stroke("#0f172a", 2),
            ),
            f"minimap-{exp.name}",
            on_click=True,
            cursor="pointer",
            tooltip=exp.name,
            a11y={"role": "button", "label": f"Select {exp.name}"},
        )
        for i, exp in enumerate(model.experiments)
    ]

    return ui.canvas(
        "minimap",
        width=width,
        height=height,
        layers=dict([
            c.layer("a_bg", c.rect(0, 0, width, height, fill="#0b1120", radius=6)),
            c.layer("b_dots", *dots),
        ]),
    )
```

The click handler in `update` matches the canvas ID in `scope` and the element ID prefix, then reuses the existing selection path:

```python
from plushie.events import Click

case Click(id=eid, scope=("minimap", *_)) if eid.startswith("minimap-"):
    name = eid.removeprefix("minimap-")
    return _select(model, name)
```

Wire the mini-map into the sidebar above the experiment list:

```python
def _sidebar(model):
    return ui.container(
        "sidebar",
        ui.column(
            ui.text("sidebar-title", "Experiments", size=14),
            _minimap(model),
            *(
                ui.button(
                    f"select-{exp.name}",
                    exp.name,
                    style="primary" if exp.name == model.selected else None,
                )
                for exp in model.experiments
            ),
            ui.rule(),
            ui.button("new", "+ New", style="secondary"),
            padding=12,
            spacing=8,
            width=220,
        ),
        width=220,
        height="fill",
    )
```

Two visualizations share the model without sharing any code with the widgets that read the same fields. The canvas sits in the tree next to `ui.column` and `ui.button`, takes events through the same dispatch, and participates in layout like any other widget.

## Verify it

Canvas element clicks behave like widget clicks through the test fixture. Match on the scoped ID:

```python
def test_minimap_selects(app):
    app.click("#minimap/minimap-hello")
    assert app.model.selected == "hello"
```

The first path segment is the canvas ID, the second is the interactive group ID. `assert_role` and `assert_a11y` check the annotations you passed through `a11y=`.

## Try it

Keep the sparkline and mini-map around as reference, and experiment with the vocabulary:

- Draw a bar chart of save counts per experiment. One `rect` per bar, height proportional to the count. Add `tooltip=` on the group for hover labels.
- Replace the sparkline line with a path that fills the area under the curve using `c.path` plus `c.linear_gradient`.
- Clip a canvas panel into a rounded rectangle using `c.clip` on a top-level group.
- Rotate the mini-map dots into a vertical arrangement using `c.rotate` on each group.

Canvas is a different paradigm from the widget tree, but everything else you have learned still applies. Events dispatch the same way. The model stays the single source of truth. The view is still a pure function, it just happens to render shapes instead of containers.

Next: [Custom Widgets](13-custom-widgets.md)
