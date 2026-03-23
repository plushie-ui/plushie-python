# Composition patterns

Plushie provides primitives, not pre-built composites. There is no `TabBar`
widget, no `Modal` widget, no `Card` widget. Instead, you compose the same
building blocks -- `row`, `column`, `container`, `stack`, `button`, `text`,
`rule`, `mouse_area`, `space` -- with `StyleMap` to build any UI pattern you
need.

This guide shows how. Every pattern is copy-pasteable and produces a polished
result. All examples assume the following imports:

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click, Toggle
from plushie.types import StyleMap, Border, Shadow
```

---

## 1. Tab bar

A horizontal row of buttons where the active tab is visually distinct from
the inactive ones. Common at the top of a content area to switch between
views.

### Code

```python
@dataclass(frozen=True, slots=True)
class TabModel:
    active_tab: str = "overview"

TABS = ["overview", "details", "settings"]

class TabApp(plushie.App[TabModel]):
    def init(self):
        return TabModel()

    def update(self, model, event):
        match event:
            case Click(id=tab_id) if tab_id.startswith("tab:"):
                return replace(model, active_tab=tab_id.removeprefix("tab:"))
            case _:
                return model

    def view(self, model):
        return ui.window("main", title="Tab Demo",
            ui.column(
                ui.row(
                    *(
                        ui.button(
                            f"tab:{tab}", tab.capitalize(),
                            style=_tab_style(model.active_tab == tab),
                            padding={"top": 10, "bottom": 10, "left": 20, "right": 20},
                        )
                        for tab in TABS
                    ),
                    spacing=0,
                ),

                # Bottom border under the tab bar
                ui.rule(),

                # Content area
                ui.container("content",
                    ui.text(f"Content for {model.active_tab}"),
                    padding=20, width="fill", height="fill",
                ),
                width="fill",
            ),
        )

def _tab_style(active: bool) -> StyleMap:
    if active:
        return (
            StyleMap()
            .with_background("#ffffff")
            .with_text_color("#1a1a1a")
            .with_border(Border(color="#0066ff", width=2, radius=0))
        )
    return (
        StyleMap()
        .with_background("#f0f0f0")
        .with_text_color("#666666")
        .with_hovered({"background": "#e0e0e0"})
    )
```

### How it works

Each tab is a `button` with a `StyleMap` driven by whether it matches the
active tab. The active style uses a solid background and a blue border to
create the "selected" indicator. Inactive tabs get a flat grey look with a
hover state for feedback. The generator expression inside the `row` call
produces one button per tab.

The `rule()` below the row acts as a full-width horizontal divider, visually
anchoring the tab bar to the content below.

### What it looks like

A horizontal row of flat buttons flush against each other. The active tab
has a white background with a blue bottom border. Inactive tabs are light
grey and lighten on hover. Below the tabs, a thin horizontal line separates
the bar from the content area.

---

## 2. Sidebar navigation

A dark column on the left side of the window containing navigation items
that highlight on hover. The selected item has an accent background.

### Code

```python
@dataclass(frozen=True, slots=True)
class SidebarModel:
    page: str = "inbox"

NAV_ITEMS = [
    ("inbox", "Inbox"),
    ("sent", "Sent"),
    ("drafts", "Drafts"),
    ("trash", "Trash"),
]

class SidebarApp(plushie.App[SidebarModel]):
    def init(self):
        return SidebarModel()

    def update(self, model, event):
        match event:
            case Click(id=nav_id) if nav_id.startswith("nav:"):
                return replace(model, page=nav_id.removeprefix("nav:"))
            case _:
                return model

    def view(self, model):
        return ui.window("main", title="Sidebar Demo",
            ui.row(
                # Sidebar
                ui.container("sidebar",
                    ui.column(
                        ui.text("nav_label", "Navigation", size=12, color="#888888"),
                        ui.space(height=8),
                        *(
                            ui.button(
                                f"nav:{id}", label,
                                style=_nav_item_style(model.page == id),
                                width="fill",
                                padding={"top": 8, "bottom": 8, "left": 12, "right": 12},
                            )
                            for id, label in NAV_ITEMS
                        ),
                        spacing=4, width="fill",
                    ),
                    width=200, height="fill", background="#1e1e2e", padding=8,
                ),

                # Main content
                ui.container("main",
                    ui.text("page_title", f"{model.page.capitalize()} page", size=20),
                    width="fill", height="fill", padding=24,
                ),
                width="fill", height="fill",
            ),
        )

def _nav_item_style(selected: bool) -> StyleMap:
    if selected:
        return (
            StyleMap()
            .with_background("#3366ff")
            .with_text_color("#ffffff")
            .with_hovered({"background": "#4477ff"})
        )
    return (
        StyleMap()
        .with_background("#1e1e2e")
        .with_text_color("#cccccc")
        .with_hovered({"background": "#2a2a3e", "text_color": "#ffffff"})
    )
```

### How it works

The outer `row` splits the window into two areas: a fixed-width sidebar and
a fill-width content area. The sidebar is a `container` with a dark
background colour. Inside it, nav items are `button` widgets spanning the
full sidebar width.

The selected item uses `StyleMap` with a blue background and white text.
Unselected items match the sidebar background so they appear invisible until
hovered, when they brighten slightly. This gives the classic "highlight on
hover, solid on select" sidebar feel.

### What it looks like

A dark panel (200px wide) on the left. Four text labels stacked vertically
inside it. The active item has a blue background. Hovering over other items
reveals a subtle lighter background. The rest of the window is the content
area.

---

## 3. Toolbar

A compact horizontal bar with grouped icon-style buttons separated by
vertical rules. Toolbars typically sit at the top of an editor or document
view.

### Code

```python
@dataclass(frozen=True, slots=True)
class ToolbarModel:
    bold: bool = False
    italic: bool = False
    underline: bool = False

class ToolbarApp(plushie.App[ToolbarModel]):
    def init(self):
        return ToolbarModel()

    def update(self, model, event):
        match event:
            case Click(id="tool:bold"):
                return replace(model, bold=not model.bold)
            case Click(id="tool:italic"):
                return replace(model, italic=not model.italic)
            case Click(id="tool:underline"):
                return replace(model, underline=not model.underline)
            case _:
                return model

    def view(self, model):
        return ui.window("main", title="Toolbar Demo",
            ui.column(
                # Toolbar
                ui.container("toolbar",
                    ui.row(
                        # File group
                        ui.button("tool:new", "New", style=_tool_style(False), padding=6),
                        ui.button("tool:open", "Open", style=_tool_style(False), padding=6),
                        ui.button("tool:save", "Save", style=_tool_style(False), padding=6),

                        # Separator
                        ui.rule(direction="vertical", height=20),

                        # Format group
                        ui.button("tool:bold", "B", style=_tool_style(model.bold), padding=6),
                        ui.button("tool:italic", "I", style=_tool_style(model.italic), padding=6),
                        ui.button("tool:underline", "U", style=_tool_style(model.underline), padding=6),

                        # Separator
                        ui.rule(direction="vertical", height=20),

                        # Spacer pushes trailing items to the right
                        ui.space(width="fill"),

                        ui.button("tool:help", "?", style=_tool_style(False), padding=6),
                        spacing=2, align_y="center",
                    ),
                    width="fill", background="#f5f5f5", padding=4,
                ),

                ui.rule(),

                # Editor area
                ui.container("editor",
                    ui.text("Editor content goes here"),
                    width="fill", height="fill", padding=16,
                ),
                width="fill",
            ),
        )

def _tool_style(toggled: bool) -> StyleMap:
    if toggled:
        return (
            StyleMap()
            .with_background("#d0d0d0")
            .with_text_color("#1a1a1a")
            .with_border(Border(color="#b0b0b0", width=1, radius=3))
            .with_hovered({"background": "#c0c0c0"})
        )
    return (
        StyleMap()
        .with_background("#f5f5f5")
        .with_text_color("#333333")
        .with_hovered({"background": "#e0e0e0"})
        .with_pressed({"background": "#d0d0d0"})
    )
```

### How it works

The toolbar is a `container` with a light background wrapping a `row`. Button
groups are visually separated by vertical `rule` widgets. A `space(width="fill")`
between the main group and the help button pushes the help button to
the far right -- a common toolbar layout technique.

Toggle-style buttons (bold, italic, underline) pass their current state to
`_tool_style()`. When toggled on, they get a depressed look via a darker
background and a subtle border. The `pressed` status override on untoggled
buttons gives tactile click feedback.

### What it looks like

A light grey horizontal bar at the top. Three button groups separated by
thin vertical lines. "New | Open | Save", then "B | I | U", then a "?"
button pushed to the far right. Toggled buttons appear slightly sunken.

---

## 4. Modal dialog

A full-screen overlay with a centered dialog box on top. Uses `stack` to
layer the overlay behind the dialog. The overlay is a semi-transparent
container that dims the background.

### Code

```python
@dataclass(frozen=True, slots=True)
class ModalModel:
    show_modal: bool = False
    confirmed: bool = False

class ModalApp(plushie.App[ModalModel]):
    def init(self):
        return ModalModel()

    def update(self, model, event):
        match event:
            case Click(id="open_modal"):
                return replace(model, show_modal=True)
            case Click(id="confirm"):
                return replace(model, show_modal=False, confirmed=True)
            case Click(id="cancel"):
                return replace(model, show_modal=False)
            case _:
                return model

    def view(self, model):
        return ui.window("main", title="Modal Demo",
            ui.stack(
                # Layer 0: main content (always visible)
                ui.container("main",
                    ui.column(
                        ui.text("main_content", "Main application content", size=20),
                        *(
                            [ui.text("confirmed_msg", "Action confirmed.", color="#22aa44")]
                            if model.confirmed else []
                        ),
                        ui.button("open_modal", "Open Dialog", style="primary"),
                        spacing=12, align_x="center",
                    ),
                    width="fill", height="fill", padding=24, center=True,
                ),

                # Layer 1: modal overlay + dialog (conditionally rendered)
                *(
                    [ui.container("overlay",
                        ui.container("dialog",
                            ui.column(
                                ui.text("dialog_title", "Confirm action", size=18, color="#1a1a1a"),
                                ui.text("dialog_body",
                                    "Are you sure you want to proceed? This cannot be undone.",
                                    color="#555555", wrapping="word",
                                ),
                                ui.row(
                                    ui.button("cancel", "Cancel", style="secondary"),
                                    ui.button("confirm", "Confirm", style="primary"),
                                    spacing=8, align_x="end",
                                ),
                                spacing=16,
                            ),
                            max_width=400, padding=24, background="#ffffff",
                            border=Border(color="#dddddd", width=1, radius=8),
                            shadow=Shadow(color="#00000040", offset=(0, 4), blur_radius=16),
                        ),
                        width="fill", height="fill", background="#00000088", center=True,
                    )]
                    if model.show_modal else []
                ),
                width="fill", height="fill",
            ),
        )
```

### How it works

`stack` layers its children front-to-back. The main content is layer 0.
When `show_modal` is true, the overlay container appears as layer 1 on top.

The overlay is a full-size container with `background="#00000088"` -- the
last two hex digits (`88`) set ~53% opacity, dimming everything behind it.
Setting `center=True` on the overlay centres its single child: the dialog
card.

The dialog card is a container with a white background, rounded border, and
a drop shadow. The shadow offset `(0, 4)` with a 16px blur gives a natural
"floating above" appearance.

When `show_modal` is false, the ternary expression yields an empty list,
so the overlay and dialog simply do not exist in the tree.

### What it looks like

A centred page with a button. Clicking the button dims the entire window
behind a dark translucent overlay. A white rounded card appears in the
centre with a title, message text, and Cancel/Confirm buttons. The card has
a soft drop shadow.

---

## 5. Card

A container with rounded corners, a border, an optional shadow, and an
optional header section. The simplest composition pattern -- it is just a
styled container.

### Code

```python
@dataclass(frozen=True, slots=True)
class CardModel:
    pass

class CardApp(plushie.App[CardModel]):
    def init(self):
        return CardModel()

    def update(self, model, event):
        return model

    def view(self, model):
        return ui.window("main", title="Card Demo",
            ui.column(
                # Simple card
                card("info", "System status", [
                    ui.text("status_msg", "All services operational", color="#22aa44"),
                    ui.text("last_checked", "Last checked: 2 minutes ago", size=12, color="#888888"),
                ]),

                # Card with action and header band
                ui.container("promo",
                    ui.column(
                        # Header band
                        ui.container("promo_header",
                            ui.text("promo_title", "Upgrade available", size=14, color="#ffffff"),
                            width="fill", padding=12, background="#3366ff",
                        ),

                        # Body
                        ui.container("promo_body",
                            ui.column(
                                ui.text("Version 2.0 brings new features and performance improvements."),
                                ui.button("upgrade", "Upgrade now", style="primary"),
                                spacing=12,
                            ),
                            width="fill", padding=16,
                        ),
                        width="fill",
                    ),
                    width="fill", padding=0, clip=True,
                    border=Border(color="#e0e0e0", width=1, radius=8),
                    shadow=Shadow(color="#00000020", offset=(0, 2), blur_radius=8),
                    background="#ffffff",
                ),
                padding=24, spacing=16, width="fill",
            ),
        )

def card(id: str, title: str, body: list) -> dict:
    """Reusable card helper. Returns a container node."""
    return ui.container(id,
        ui.column(
            ui.text("card_title", title, size=16, color="#1a1a1a"),
            ui.rule(),
            *body,
            spacing=8,
        ),
        width="fill", padding=16, background="#ffffff",
        border=Border(color="#e0e0e0", width=1, radius=8),
        shadow=Shadow(color="#00000020", offset=(0, 2), blur_radius=8),
    )
```

### How it works

A card is a `container` with four visual properties: `background` for the
fill colour, `border` with a rounded radius for the outline, `shadow` for
depth, and `padding` for internal spacing. That is the entire pattern.

The `card()` helper extracts this into a reusable function. It takes an id,
a title string, and a list of child nodes. The children are unpacked with
`*body` into the card's column.

The "promo" card demonstrates a header band: a nested container with a
coloured background and `clip=True` on the outer card so the header's
background respects the rounded corners.

### What it looks like

Rounded white rectangles with subtle borders and soft shadows. The first
card has a title, a divider line, and body text. The second has a blue
header band spanning the full width, body text below, and a primary-styled
button.

---

## 6. Split panel

Two content areas side by side with a draggable divider between them. The
divider is a vertical `rule` wrapped in a `mouse_area` that changes the
cursor to a horizontal resize indicator.

### Code

```python
@dataclass(frozen=True, slots=True)
class SplitModel:
    left_width: int = 300

class SplitApp(plushie.App[SplitModel]):
    def init(self):
        return SplitModel()

    # In a real app, you would track mouse drag events to resize.
    # This example shows the static layout and cursor feedback.
    def update(self, model, event):
        return model

    def view(self, model):
        return ui.window("main", title="Split Panel Demo",
            ui.row(
                # Left panel
                ui.container("left_panel",
                    ui.column(
                        ui.text("left_title", "Left panel", size=16),
                        ui.text("left_desc", "File browser, outline, or any sidebar content.", color="#666666"),
                        spacing=8,
                    ),
                    width=model.left_width, height="fill", padding=16, background="#fafafa",
                ),

                # Draggable divider
                ui.mouse_area("divider",
                    ui.container("divider_track",
                        ui.rule(direction="vertical"),
                        width=5, height="fill", background="#e0e0e0",
                    ),
                    cursor="resizing_horizontally",
                ),

                # Right panel
                ui.container("right_panel",
                    ui.column(
                        ui.text("right_title", "Right panel", size=16),
                        ui.text("right_desc", "Main editor or content area.", color="#666666"),
                        spacing=8,
                    ),
                    width="fill", height="fill", padding=16,
                ),
                width="fill", height="fill",
            ),
        )
```

### How it works

The outer `row` holds three children: left panel, divider, right panel. The
left panel has a fixed pixel width. The right panel uses `width="fill"` to
take the remaining space.

The divider is a `mouse_area` wrapping a thin container. The
`cursor="resizing_horizontally"` prop changes the mouse cursor to the standard
horizontal resize indicator when the user hovers over the divider, giving
clear affordance that it is draggable.

In a production app you would handle press/release events along with mouse
move tracking to update `left_width` dynamically. The static layout pattern
is the same regardless.

### What it looks like

Two panels side by side filling the window. A thin grey vertical bar between
them. Hovering over the bar changes the cursor to a horizontal resize arrow.

---

## 7. Breadcrumb

A horizontal trail of clickable path segments separated by ">" characters.
The last segment is plain text (not clickable) representing the current
location.

### Code

```python
@dataclass(frozen=True, slots=True)
class BreadcrumbModel:
    path: tuple[str, ...] = ("Home", "Projects", "Plushie", "Docs")

class BreadcrumbApp(plushie.App[BreadcrumbModel]):
    def init(self):
        return BreadcrumbModel()

    def update(self, model, event):
        match event:
            case Click(id=crumb_id) if crumb_id.startswith("crumb:"):
                index = int(crumb_id.removeprefix("crumb:"))
                return replace(model, path=model.path[:index + 1])
            case _:
                return model

    def view(self, model):
        last_index = len(model.path) - 1

        crumb_nodes: list[dict] = []
        for index, segment in enumerate(model.path):
            if index == last_index:
                # Current location: plain text, not clickable
                crumb_nodes.append(
                    ui.text("crumb_current", segment, size=14, color="#1a1a1a")
                )
            else:
                crumb_nodes.append(
                    ui.button(f"crumb:{index}", segment,
                        style=_crumb_style(),
                        padding={"top": 2, "bottom": 2, "left": 4, "right": 4},
                    )
                )
                crumb_nodes.append(
                    ui.text(f"sep:{index}", ">", size=14, color="#999999")
                )

        return ui.window("main", title="Breadcrumb Demo",
            ui.column(
                ui.row(*crumb_nodes, spacing=4, align_y="center"),
                ui.rule(),
                ui.text("viewing", f"Viewing: {model.path[-1]}", size=18),
                padding=16, spacing=16, width="fill",
            ),
        )

def _crumb_style() -> StyleMap:
    return (
        StyleMap()
        .with_background("#00000000")
        .with_text_color("#3366ff")
        .with_hovered({"text_color": "#1144cc", "background": "#f0f0ff"})
        .with_pressed({"text_color": "#0033aa"})
    )
```

### How it works

The breadcrumb is a `row` containing an interleaved sequence of buttons and
separator text nodes. The loop iterates over the path segments with their
index. For every segment except the last, it appends a clickable button and
a ">" separator to the list. The list is then unpacked into the `row` call.

The last segment is rendered as plain `text` -- no click handler, no hover
state. This signals "you are here" without needing a disabled button.

The crumb buttons use a fully transparent background (`#00000000`) so they
look like plain text links. The hover state adds a subtle blue tint and
changes the text colour, mimicking a hyperlink.

Clicking a breadcrumb truncates the path to that index, navigating "up".

### What it looks like

A horizontal line of text: "Home > Projects > Plushie > Docs". Everything
except "Docs" is blue and clickable. Hovering over a segment highlights it
with a light blue background. "Docs" is plain dark text.

---

## 8. Badge / chip

A small container with a coloured background and fully rounded corners. Used
for tags, counts, status indicators, or filter chips.

### Code

```python
@dataclass(frozen=True, slots=True)
class BadgeModel:
    selected: frozenset[str] = frozenset(["elixir"])

TAGS = ["elixir", "rust", "iced", "desktop"]

class BadgeApp(plushie.App[BadgeModel]):
    def init(self):
        return BadgeModel()

    def update(self, model, event):
        match event:
            case Click(id=tag_id) if tag_id.startswith("tag:"):
                name = tag_id.removeprefix("tag:")
                if name in model.selected:
                    return replace(model, selected=model.selected - {name})
                return replace(model, selected=model.selected | {name})
            case _:
                return model

    def view(self, model):
        return ui.window("main", title="Badge Demo",
            ui.column(
                # Status badges (display only)
                ui.row(
                    ui.text("status_label", "Status:", size=14),
                    badge("online", "Online", "#22aa44", "#ffffff"),
                    badge("count", "3 new", "#3366ff", "#ffffff"),
                    badge("warn", "Deprecated", "#ff8800", "#ffffff"),
                    spacing=8, align_y="center",
                ),

                ui.rule(),

                # Filter chips (clickable)
                ui.text("filter_label", "Filter by tag:", size=14),
                ui.row(
                    *(
                        ui.button(f"tag:{tag}", tag,
                            style=_chip_style(tag in model.selected),
                            padding={"top": 4, "bottom": 4, "left": 10, "right": 10},
                        )
                        for tag in TAGS
                    ),
                    spacing=6,
                ),

                ui.text(
                    f"Selected: {', '.join(sorted(model.selected))}",
                    color="#666666",
                ),
                padding=24, spacing=16, width="fill",
            ),
        )

def badge(id: str, label: str, bg_color: str, text_color: str) -> dict:
    """Display-only badge: a small container with pill shape."""
    return ui.container(id,
        ui.text("badge_text", label, size=11, color=text_color),
        padding={"top": 2, "bottom": 2, "left": 8, "right": 8},
        background=bg_color,
        border=Border(radius=999),
    )

def _chip_style(selected: bool) -> StyleMap:
    if selected:
        return (
            StyleMap()
            .with_background("#3366ff")
            .with_text_color("#ffffff")
            .with_border(Border(color="#3366ff", width=1, radius=999))
            .with_hovered({"background": "#4477ff"})
        )
    return (
        StyleMap()
        .with_background("#f0f0f0")
        .with_text_color("#333333")
        .with_border(Border(color="#cccccc", width=1, radius=999))
        .with_hovered({"background": "#e4e4e4"})
    )
```

### How it works

A badge is a `container` with a high `border` radius (999 creates a pill
shape by ensuring the radius exceeds the container height) and a coloured
background. The text inside is small and tightly padded.

The `badge()` helper encapsulates this as a display-only element. It returns
a container node with the given background colour, text colour, and label.

Filter chips reuse the same pill-shape concept but as clickable `button`
widgets. The `_chip_style()` function returns a `StyleMap` with rounded
borders. Selected chips have a solid blue fill; unselected chips have a
grey outline. Clicking toggles the tag in a `frozenset`.

### What it looks like

A row of small coloured pills: green "Online", blue "3 new", orange
"Deprecated". Below that, a row of rounded filter buttons. Selected filters
are solid blue; others are grey-outlined. Clicking a chip toggles its
selection state.

---

## 9. Canvas interactive shapes

Canvas handles custom visuals and hit testing. Built-in widgets handle
text editing, scrolling, and popup positioning. Complex components compose
both -- the canvas draws what iced's widget set cannot, and built-in widgets
handle what canvas cannot.

### Canvas-only: custom toggle switch

A single canvas with one interactive group. The renderer handles hover
feedback and focus ring locally. The host only sees click events.

#### Code

```python
from plushie.events import CanvasShapeClick

@dataclass(frozen=True, slots=True)
class ToggleModel:
    dark_mode: bool = False

class ToggleApp(plushie.App[ToggleModel]):
    def init(self):
        return ToggleModel()

    def update(self, model, event):
        match event:
            case CanvasShapeClick(id="toggle", shape_id="switch"):
                return replace(model, dark_mode=not model.dark_mode)
            case _:
                return model

    def view(self, model):
        on = model.dark_mode
        knob_x = 36 if on else 16

        return ui.window("main", title="Toggle Demo",
            ui.column(
                ui.canvas("toggle", width=52, height=28, layers={
                    "switch": [
                        {
                            "type": "group",
                            "interactive": {
                                "id": "switch",
                                "on_click": True,
                                "cursor": "pointer",
                                "a11y": {"role": "switch", "label": "Dark mode", "toggled": on},
                            },
                            "children": [
                                {"type": "rect", "x": 0, "y": 0, "w": 52, "h": 28,
                                 "fill": "#4CAF50" if on else "#ccc", "radius": 14},
                                {"type": "circle", "cx": knob_x, "cy": 14, "r": 10, "fill": "#fff"},
                            ],
                        },
                    ],
                }),
                padding=24, spacing=16,
            ),
        )
```

#### How it works

The canvas accepts a `layers` dict mapping layer names to lists of shapes.
Each layer contains shapes -- here a single group with a rounded rect
background and a circle knob. The `interactive` dict inside the
group enables click events, sets the pointer cursor, and provides a11y
metadata. On click, the host toggles `dark_mode` and the view
re-renders with new positions and colours.

Screen reader: "Dark mode, switch, on." Keyboard: Tab focuses the
canvas, Enter/Space toggles.

### Canvas-only: chart with clickable data points

Multiple interactive groups inside a canvas. Each bar is focusable,
has a tooltip, and announces its position in the set.

#### Code

```python
from plushie.events import CanvasShapeClick

@dataclass(frozen=True, slots=True)
class ChartModel:
    selected: str | None = None

DATA = [
    {"month": "Jan", "value": 120, "color": "#3498db"},
    {"month": "Feb", "value": 85, "color": "#2ecc71"},
    {"month": "Mar", "value": 200, "color": "#e74c3c"},
    {"month": "Apr", "value": 150, "color": "#f39c12"},
]

class ChartApp(plushie.App[ChartModel]):
    def init(self):
        return ChartModel()

    def update(self, model, event):
        match event:
            case CanvasShapeClick(id="chart", shape_id=shape_id):
                return replace(model, selected=shape_id)
            case _:
                return model

    def view(self, model):
        bar_w = 60
        chart_h = 220
        count = len(DATA)

        bars = []
        for i, bar in enumerate(DATA):
            bar_h = bar["value"]
            bar_x = i * (bar_w + 20)
            bar_y = chart_h - bar_h

            bars.append({
                "type": "group",
                "x": bar_x, "y": bar_y,
                "interactive": {
                    "id": f"bar-{i}",
                    "on_click": True,
                    "on_hover": True,
                    "cursor": "pointer",
                    "tooltip": f"{bar['month']}: {bar['value']} units",
                    "a11y": {
                        "role": "button",
                        "label": f"{bar['month']}: {bar['value']} units",
                        "position_in_set": i + 1,
                        "size_of_set": count,
                    },
                },
                "children": [
                    {"type": "rect", "x": 0, "y": 0, "w": bar_w, "h": bar_h,
                     "fill": bar["color"]},
                    {"type": "text", "x": bar_w // 2, "y": -12,
                     "content": str(bar["value"]), "fill": "#666",
                     "align_x": "center"},
                ],
            })

        return ui.window("main", title="Chart Demo",
            ui.column(
                ui.canvas("chart",
                    width=count * (bar_w + 20), height=chart_h,
                    event_rate=30,
                    layers={"bars": bars},
                ),
                *(
                    [ui.text("selection", f"Selected: {model.selected}")]
                    if model.selected else []
                ),
                padding=24, spacing=16,
            ),
        )
```

#### How it works

Each bar is a `group` containing a rect and a label. The `interactive`
field enables click and hover events, sets a pointer cursor, and
provides a tooltip. The `position_in_set` and `size_of_set` fields
let screen readers announce "Jan: 120 units, button, 1 of 4." Arrow
keys navigate between bars. `event_rate=30` throttles hover events
to 30fps.

### Canvas + built-in: custom styled text input

Stack a canvas behind a `text_input` to draw a custom background. The
canvas is purely decorative -- the text_input handles cursor, selection,
IME, and clipboard.

#### Code

```python
from plushie.events import Input

@dataclass(frozen=True, slots=True)
class SearchModel:
    query: str = ""

class SearchApp(plushie.App[SearchModel]):
    def init(self):
        return SearchModel()

    def update(self, model, event):
        match event:
            case Input(id="search", value=value):
                return replace(model, query=value)
            case _:
                return model

    def view(self, model):
        return ui.window("main", title="Search Demo",
            ui.column(
                ui.stack(
                    ui.canvas("search-bg", width=300, height=36, layers={
                        "bg": [
                            {"type": "rect", "x": 0, "y": 0, "w": 300, "h": 36,
                             "fill": "#f5f5f5", "radius": 8,
                             "stroke": "#ddd", "stroke_width": 1},
                            {"type": "image", "src": "priv/icons/search.svg",
                             "x": 8, "y": 8, "w": 20, "h": 20},
                        ],
                    }),
                    ui.container("search-wrap",
                        ui.text_input("search", model.query, style="borderless", width="fill"),
                        padding={"left": 36, "top": 0, "right": 8, "bottom": 0}, height=36,
                    ),
                    width=300, height=36,
                ),
                padding=24, spacing=16,
            ),
        )
```

#### How it works

The `stack` layers the canvas background behind the text_input. The
canvas draws the rounded rect and search icon -- purely visual, no
interactive field needed. The `text_input` sits on top in a padded
container so it clears the icon area. Clicks in the text area hit the
text_input (it is on top in the stack).

Canvas = visuals. text_input = editing and IME.

---

## General techniques

These patterns share a few recurring techniques worth calling out:

**Style functions over style constants.** Most patterns define a function
like `_tab_style(active)` or `_chip_style(selected)` that returns
a `StyleMap`. This keeps style logic next to the view, makes it easy to
derive styles from model state, and avoids module-level constants for
something that varies per render.

**`space(width="fill")` as a flex pusher.** Inserting a space with
`width="fill"` inside a row pushes everything after it to the right edge.
This is the flexbox `margin-left: auto` equivalent and is used in toolbars,
headers, and nav bars.

**`border` radius 999 for pills.** Setting a border radius larger than the
element can possibly be tall creates a perfect pill shape. The renderer
clamps the radius to the available space.

**Transparent backgrounds for link-style buttons.** Using `#00000000` (fully
transparent) as a button background makes it look like a text link. Add a
hover state with a subtle background tint for affordance.

**Conditional rendering with ternary unpacking.** To conditionally include
children, use ternary expressions with list unpacking:

```python
ui.column(
    ui.text("Always visible"),
    *(
        [ui.text("Only when active")]
        if is_active else []
    ),
)
```

The `*` unpacks an empty list to nothing, or a single-element list to one
child. This is the Python equivalent of `if` without `else` in Elixir
do-blocks.

**Generator expressions for repeated children.** Use generator expressions
with `*` unpacking to produce multiple children:

```python
ui.row(
    *(ui.button(f"tab:{t}", t.capitalize()) for t in tabs),
    spacing=4,
)
```

**Helper functions for repeated compositions.** Extract common patterns into
functions (like `card()` or `badge()`) that return node dicts. Keep
them in the same module or a dedicated view helpers module. They are plain
functions returning plain dicts.

---

## State helpers

Plushie provides optional state management modules for common UI patterns.
None of these are required -- your model can be any type. They exist because
these patterns come up repeatedly in desktop apps and getting them right from
scratch is tedious.

All helpers are pure data structures with no threads or side effects.

### plushie.state.State

Path-based access to nested model data with revision tracking and
transactions.

```python
from plushie.state import State

state = State.new({"user": {"name": "Alice", "prefs": {"theme": "dark"}}})

# Read
state.get(["user", "name"])
# => "Alice"

# Write
state = state.put(["user", "prefs", "theme"], "light")
state.revision
# => 1

# Transaction (atomic multi-step update with rollback)
state = state.begin_transaction()
state = state.put(["user", "name"], "Bob")
state = state.put(["user", "prefs", "theme"], "dark")
state = state.commit_transaction()
# Both changes applied atomically. Revision incremented once.

# Or roll back:
state = state.rollback_transaction()
# All changes since begin_transaction discarded.
```

The revision counter is useful for determining whether a re-render is
needed. If the revision has not changed, the tree has not changed.

Use `State` when your model has deeply nested data that you update
from multiple event handlers. Skip it when your model is flat or simple
enough that plain `replace()` calls read clearly.

### plushie.undo.UndoStack

Undo/redo stack for commands.

```python
from plushie.undo import UndoStack, UndoCommand

undo = UndoStack.new(model)

# Apply a command (records it for undo)
undo = undo.apply_command(UndoCommand(
    apply_fn=lambda m: replace(m, name="Bob"),
    undo_fn=lambda m: replace(m, name="Alice"),
    label="Rename to Bob",
))

undo.current.name
# => "Bob"

# Undo
undo = undo.undo()
undo.current.name
# => "Alice"

# Redo
undo = undo.redo()
undo.current.name
# => "Bob"

# Coalescing (group rapid changes, like typing)
undo = undo.apply_command(UndoCommand(
    apply_fn=lambda m: replace(m, text=m.text + "a"),
    undo_fn=lambda m: replace(m, text=m.text[:-1]),
    coalesce=("typing", "editor"),
    coalesce_window_ms=500,
))
# Multiple applies with the same coalesce key within the time window
# are merged into a single undo entry.
```

Use `UndoStack` when your app has user actions that should be reversible
(text editing, form filling, drawing, configuration changes). Skip it for
apps where undo does not make sense (dashboards, monitoring).

### plushie.selection.Selection

Selection state for lists and tables.

```python
from plushie.selection import Selection

sel = Selection.new(mode="multi")

sel = sel.select("item_1")
sel = sel.select("item_3", extend=True)

sel.selected()
# => frozenset({"item_1", "item_3"})

sel = sel.toggle("item_1")
sel.selected()
# => frozenset({"item_3"})

# Range select (shift-click pattern)
sel = Selection.new(mode="range", order=["a", "b", "c", "d", "e"])
sel = sel.select("b")
sel = sel.range_select("d")
sel.selected()
# => frozenset({"b", "c", "d"})
```

Use `Selection` when you have selectable lists, tables, or tree
views. It handles single, multi (ctrl-click), and range (shift-click)
selection modes correctly. Skip it for simple cases where a single
`selected_id` in your model is sufficient.

### plushie.route.Route

Client-side routing for multi-view apps.

```python
from plushie.route import Route

route = Route.new("home")

route = route.push("settings", {"tab": "general"})
route.current()
# => "settings"
route.params()
# => {"tab": "general"}

route = route.pop()
route.current()
# => "home"
```

Routes are just data. There is no URL bar, no browser history API. This
is for apps that have multiple "screens" and want back/forward navigation
with history tracking. Use it for apps with distinct screens (settings,
detail views, wizards). Skip it for single-screen apps.

### plushie.data.query

Query pipeline for in-memory record collections.

```python
from plushie.data import query

records = [
    {"id": 1, "name": "Alice", "role": "admin", "active": True},
    {"id": 2, "name": "Bob", "role": "user", "active": False},
    {"id": 3, "name": "Carol", "role": "admin", "active": True},
]

result = query(records,
    filter_fn=lambda r: r["active"],
    sort=("asc", "name"),
    page=1,
    page_size=10,
)
# result.entries => [{"id": 1, ...}, {"id": 3, ...}]
# result.total => 2
# result.page => 1
# result.page_size => 10
```

Use `query()` when you have tabular data that needs filtering, sorting,
grouping, or pagination in the UI. It is a query pipeline over lists, not a
database -- keep data sets small enough to fit in memory.

### General philosophy

These helpers share a few properties:

- **Pure data.** No threads, no processes, no side effects. They are
  just dataclasses/objects and functions.
- **Optional.** You can use zero, one, or all of them. They do not depend
  on each other.
- **Composable.** They work with your model, not instead of it. Embed them
  as fields in your model dataclass.

```python
@dataclass(frozen=True, slots=True)
class AppModel:
    state: State
    undo: UndoStack
    selection: Selection
    route: Route
    todos: list = ()

def init(self):
    return AppModel(
        state=State.new({...}),
        undo=UndoStack.new({...}),
        selection=Selection.new(mode="single"),
        route=Route.new("home"),
    )
```
