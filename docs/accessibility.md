# Accessibility

Plushie provides built-in accessibility support via
[accesskit](https://github.com/AccessKit/accesskit), a cross-platform
accessibility toolkit. The default renderer build includes accessibility,
activating native platform APIs automatically: VoiceOver on macOS,
AT-SPI/Orca on Linux, and UI Automation/NVDA/JAWS on Windows.

Screen reader users, keyboard-only users, and other AT users interact with
the same widgets and receive the same events as mouse users. No special
event handling is needed in your `update()`. AT actions produce the same
`Click(id=id)`, `Input(id=id, value=val)`, etc. events as direct
interaction.


## How it works

Iced's fork (`v0.14.0-a11y-accesskit` branch) provides native accessibility
support. Three pieces work together:

1. **iced widgets report `Accessible` metadata** - each widget implements
   the `Accessible` trait via iced's `operate()` mechanism. Widgets declare
   their role, label, and state to the accessibility system automatically.

2. **TreeBuilder assembles the accesskit tree** - `iced_winit::a11y`
   contains a `TreeBuilder` that walks the widget tree during `operate()`,
   collecting `Accessible` metadata and building an accesskit `TreeUpdate`.
   This happens natively inside iced; plushie does not build the tree.

3. **AT actions become native iced events** - when an AT triggers an action
   (e.g. a screen reader user activates a button), iced translates it to a
   native event. The renderer maps it to a standard plushie event and sends
   it to Python over the wire protocol.

```
Host (Python)             Renderer (iced)               Platform AT
   |                         |                              |
   |--- UI tree (a11y) ----->|                              |
   |                         |-- operate() + TreeBuilder -->|
   |                         |-- TreeUpdate --------------->|
   |                         |                              |
   |                         |<-- AT Action (Click) --------|
   |                         |   (native iced event)        |
   |<-- Click(id=...) -------|                              |
```

### plushie's role

plushie does not build its own accesskit tree. Iced handles tree building,
AT actions, and platform integration natively. plushie's contribution is the
`A11yOverride` wrapper widget (`a11y_widget.rs` in plushie) that
intercepts `operate()` to apply Python-side overrides from the `a11y` prop.

This means:

- **Standard widgets** get correct accessibility semantics automatically
  from iced's own `Accessible` implementations.
- **Extension widgets** get free a11y support without any code. They are
  already iced `Element`s that participate in `operate()`.
- **The `a11y` prop** lets Python override or augment the inferred semantics
  when auto-inference is insufficient.
- **`HiddenInterceptor`** is a companion wrapper that excludes widgets from
  the AT tree when `hidden: True` is set.

Accessibility is compiled unconditionally. There are no feature flags to
toggle it.


## Auto-inference

Most widgets get correct accessibility semantics without any annotation.
Iced automatically reports roles, labels, and state from widget types and
existing props via the `Accessible` trait.

### Role mapping

Every widget type maps to an accesskit role:

| Widget type | Role | Notes |
|---|---|---|
| `button` | Button | |
| `text`, `rich_text` | Label | |
| `text_input` | TextInput | |
| `text_editor` | MultilineTextInput | |
| `checkbox` | CheckBox | |
| `toggler` | Switch | |
| `radio` | RadioButton | |
| `slider`, `vertical_slider` | Slider | |
| `pick_list`, `combo_box` | ComboBox | |
| `progress_bar` | ProgressIndicator | |
| `scrollable` | ScrollView | |
| `container`, `column`, `row`, `stack` | GenericContainer | Also: `keyed_column`, `grid`, `float`, `pin`, `responsive`, `space`, `themer`, `mouse_area`, `sensor`, `overlay` |
| `window` | Window | |
| `image`, `svg`, `qr_code` | Image | |
| `canvas` | Canvas | |
| `table` | Table | |
| `tooltip` | Tooltip | |
| `markdown` | Document | |
| `pane_grid` | Group | |
| `rule` | Splitter | |

### Labels

Labels are the accessible name announced by screen readers. They are
extracted from the prop that makes sense for each widget type:

| Widget type | Label source |
|---|---|
| `button`, `checkbox`, `toggler`, `radio` | `label` prop |
| `text`, `rich_text` | `content` prop |
| `image`, `svg` | `alt` prop |
| `text_input` | `placeholder` prop (as description, not label) |

If a widget has no auto-inferred label and no `a11y` label override, the
screen reader sees the role with no name. This is fine for structural
containers but not for interactive widgets. Always give buttons, inputs,
and toggles either a visible label or an `a11y` label.

### State

Widget state is extracted from existing props automatically:

| State | Source | Widgets |
|---|---|---|
| Disabled | `disabled: True` | Any widget |
| Toggled | `checked` prop | `checkbox` |
| Toggled | `is_toggled` prop | `toggler` |
| Toggled | `selected` prop (boolean) | `radio` |
| Numeric value | `value` prop (number) | `slider`, `progress_bar` |
| Min/max | `range` prop (`[min, max]`) | `slider`, `progress_bar` |
| String value | `value` prop (string) | `text_input` |
| Selected item | `selected` prop (string) | `pick_list` |


## The a11y prop

For cases where auto-inference is insufficient, every widget accepts an
`a11y` prop, a dict of fields that override or augment the inferred
semantics.

### Fields

| Field | Type | Description |
|---|---|---|
| `role` | `str` | Override the inferred role (see [available roles](#available-roles)) |
| `label` | `str` | Accessible name (what the screen reader announces) |
| `description` | `str` | Longer description (secondary announcement) |
| `live` | `"off"` / `"polite"` / `"assertive"` | Live region (AT announces content changes) |
| `hidden` | `bool` | Exclude from accessibility tree entirely |
| `expanded` | `bool` | Expanded/collapsed state (menus, disclosures) |
| `required` | `bool` | Mark form field as required |
| `level` | `int` | Heading level (1-6, only meaningful with `"heading"` role) |
| `busy` | `bool` | Suppresses AT announcements until cleared (auto-managed by sliders during drag; set explicitly for custom continuous interactions) |
| `invalid` | `bool` | Form validation failure |
| `modal` | `bool` | Dialog is modal (AT restricts navigation to this container) |
| `read_only` | `bool` | Can be read but not edited |
| `mnemonic` | `str` | Alt+letter keyboard shortcut (single character) |
| `toggled` | `bool` | Toggled/checked state (for custom toggle widgets) |
| `selected` | `bool` | Selected state (for custom selectable widgets) |
| `value` | `str` | Current value as a string (for custom value-displaying widgets) |
| `orientation` | `"horizontal"` / `"vertical"` | Orientation hint for AT navigation |
| `labelled_by` | `str` | ID of the widget that labels this one |
| `described_by` | `str` | ID of the widget that describes this one |
| `error_message` | `str` | ID of the widget showing the error message |
| `disabled` | `bool` | Override disabled state for AT |
| `position_in_set` | `int` | 1-based position in a set ("Item 3 of 7") |
| `size_of_set` | `int` | Total items in the set |
| `has_popup` | `str` | Popup type: `"listbox"`, `"menu"`, `"dialog"`, `"tree"`, `"grid"` |

All fields are optional. Only include what you need.

### Using the a11y prop

<!-- test: test_heading_with_level, test_heading_level_2, test_icon_button_label, test_landmark_region, test_live_region_polite, test_hidden_from_at, test_expanded_state, test_required_form_field -- keep this code block in sync with the test -->
```python
from plushie import ui

# Headings
ui.text("title", "Welcome to MyApp", a11y={"role": "heading", "level": 1})
ui.text("settings_heading", "Settings", a11y={"role": "heading", "level": 2})

# Icon buttons that need a label for screen readers
ui.button("close", "X", a11y={"label": "Close dialog"})

# Landmark regions
ui.container("search_results", a11y={"role": "region", "label": "Search results"},
    children=[...])

# Live regions: AT announces changes automatically
ui.text("save_status", f"{model.saved_count} items saved", a11y={"live": "polite"})

# Decorative elements hidden from AT
ui.rule(a11y={"hidden": True})
ui.image("divider", "/images/decorative-line.png", a11y={"hidden": True})

# Disclosure / expandable sections
ui.container("details",
    a11y={"expanded": model.expanded, "role": "group", "label": "Advanced options"},
    children=[...] if model.expanded else [])

# Required form fields
ui.text_input("email", model.email, a11y={"required": True, "label": "Email address"})
```

### Available roles

The `role` field accepts strings. Use them to override the auto-inferred role
when a widget is semantically different from its type (e.g. a `text` that is
actually a heading, or a `container` that is a navigation landmark).

**Interactive:**
`"button"`, `"checkbox"` / `"check_box"`, `"combo_box"` / `"combobox"`,
`"link"`, `"menu_item"`, `"radio"` / `"radio_button"`, `"slider"`,
`"switch"`, `"tab"`, `"text_input"`, `"multiline_text_input"` /
`"text_editor"`, `"tree_item"`

**Structure:**
`"generic_container"` / `"generic"` / `"container"`, `"group"`,
`"heading"`, `"label"`, `"list"`, `"list_item"`, `"row"`,
`"cell"`, `"column_header"`, `"row_header"`, `"table"`, `"tree"`

**Landmarks:**
`"navigation"`, `"region"`, `"search"`

**Status:**
`"alert"`, `"alert_dialog"` / `"alertdialog"`, `"dialog"`, `"status"`,
`"timer"`, `"meter"`, `"progress_indicator"` / `"progressbar"`

**Other:**
`"document"`, `"image"`, `"menu"`, `"menu_bar"`, `"scroll_view"`,
`"separator"`, `"tab_list"`, `"tab_panel"`, `"toolbar"`, `"tooltip"`,
`"window"`

Unknown role strings are accepted but mapped to `Unknown`.


## Patterns and best practices

### Every interactive widget needs a name

Screen readers announce a widget's role and its label. A button with no
label is announced as just "button", which is useless. Make sure every button,
input, checkbox, and toggle has either:

- A visible label prop that auto-inference picks up, or
- An `a11y={"label": "..."}` override

```python
# Good: label is auto-inferred from the button's label prop
ui.button("save", "Save document")

# Good: terse label with explicit a11y override for clarity
ui.button("close", "X", a11y={"label": "Close dialog"})

# Bad: screen reader just announces "button" with no name
ui.button("do_thing", "")
```

### Use headings to create structure

Screen reader users navigate by headings. Use the `a11y` prop to mark
section titles:

<!-- test: test_heading_hierarchy_in_view -- keep this code block in sync with the test -->
```python
def view(model):
    return ui.window("main", title="MyApp", children=[
        ui.column(children=[
            ui.text("page_title", "Dashboard",
                    a11y={"role": "heading", "level": 1}),

            ui.text("h_recent", "Recent activity",
                    a11y={"role": "heading", "level": 2}),
            # ... activity list ...

            ui.text("h_actions", "Quick actions",
                    a11y={"role": "heading", "level": 2}),
            # ... action buttons ...
        ])
    ])
```

### Use landmarks for page regions

Landmarks let screen reader users jump between major sections. Wrap
significant regions in containers with landmark roles:

<!-- test: test_navigation_landmark, test_region_landmark, test_search_landmark -- keep this code block in sync with the test -->
```python
ui.column(children=[
    ui.container("nav", a11y={"role": "navigation", "label": "Main navigation"},
        children=[
            ui.row(children=[
                ui.button("home", "Home"),
                ui.button("settings", "Settings"),
                ui.button("help", "Help"),
            ])
        ]),

    ui.container("main_content",
        a11y={"role": "region", "label": "Main content"},
        children=[...]),

    ui.container("search_area", a11y={"role": "search", "label": "Search"},
        children=[
            ui.text_input("query", model.query, placeholder="Search..."),
            ui.button("go", "Search"),
        ]),
])
```

### Live regions for dynamic content

When content changes and you want the screen reader to announce it
without the user navigating to it, use live regions:

- `"polite"` - announced after the current speech finishes (status
  messages, save confirmations, non-urgent updates)
- `"assertive"` - interrupts current speech (errors, urgent alerts)

```python
# Status bar that announces changes
ui.text("status", model.status_message, a11y={"live": "polite"})

# Error message that interrupts
if model.error:
    ui.text("error", model.error,
            a11y={"live": "assertive", "role": "alert"})

# Counter value announced on change
ui.text("counter", f"Count: {model.count}", a11y={"live": "polite"})
```

**Tip:** Only mark the element that changes as live, not its parent
container. Marking a large container as live causes the entire container's
text to be re-announced on every change.

### Busy state and continuous interactions

When a value changes rapidly (e.g. during a slider drag or canvas
interaction), setting `busy=True` on the node suppresses AT
announcements until `busy` clears. AT then announces the final
value once, avoiding a flood of intermediate announcements. This
maps to WAI-ARIA `aria-busy`.

**Built-in widgets handle this automatically.** Sliders set
`busy=True` during drag and clear it on release. No SDK code
needed.

**For app-managed live regions** that reflect values from a
continuous interaction (e.g. a text display showing a hex color
while the user drags a canvas), set `busy` explicitly:

```python
text("hex", hex_value, a11y={"live": "polite", "busy": model.drag is not None})
```

When the drag ends, `busy` clears and the screen reader announces
the final hex value.

### Forms

Label your inputs, mark required fields, and provide clear error feedback:

```python
ui.column(spacing=12, children=[
    ui.text("form_heading", "Create account",
            a11y={"role": "heading", "level": 1}),

    ui.column(spacing=4, children=[
        ui.text("username_label", "Username"),
        ui.text_input("username", model.username,
                      a11y={"required": True, "label": "Username"}),
    ]),

    ui.column(spacing=4, children=[
        ui.text("email_label", "Email"),
        ui.text_input("email", model.email,
                      a11y={"required": True, "label": "Email address"}),
        *(
            [ui.text("email_error", model.email_error,
                     a11y={"live": "assertive", "role": "alert"})]
            if model.email_error else []
        ),
    ]),

    ui.button("submit", "Create account"),
])
```

**Why the explicit `a11y={"label": "Username"}` when there is a visible
`text("username_label", "Username")` above?** Because plushie does not
automatically associate a text label with the input below it. The visible
text and the input are separate widgets in the tree. The `a11y` label
connects them for AT users.

#### Cross-widget relationships

Instead of duplicating label text in the `a11y` prop, you can point to
another widget by ID using `labelled_by`, `described_by`, and
`error_message`. The renderer resolves these to accesskit node references
so the screen reader follows the relationship automatically.

<!-- test: test_labelled_by, test_normalize_resolves_a11y_refs_in_scope -- keep this code block in sync with the test -->
```python
ui.column(spacing=12, children=[
    ui.text("form_heading", "Create account",
            a11y={"role": "heading", "level": 1}),

    ui.column(spacing=4, children=[
        ui.text("email-label", "Email"),
        ui.text("email-help", "We'll send a confirmation link"),
        ui.text_input("email", model.email,
                      a11y={
                          "labelled_by": "email-label",
                          "described_by": "email-help",
                          "error_message": "email-error",
                      }),
        *(
            [ui.text("email-error", model.email_error,
                     a11y={"role": "alert", "live": "assertive"})]
            if model.email_error else []
        ),
    ]),

    ui.button("submit", "Create account"),
])
```

When the user focuses the email input, the screen reader announces the
label text from the `email-label` widget and the description from
`email-help`. If the field is invalid, it also announces the error text
from `email-error`.

Use `labelled_by` instead of `label` when a visible text widget already
provides the label. This avoids duplicating the string and keeps the
label in sync if you change the visible text.

### Hiding decorative content

Decorative elements that add no information should be hidden from AT:

<!-- test: test_rule_hidden, test_image_hidden, test_image_alt_text -- keep this code block in sync with the test -->
```python
# Decorative dividers
ui.rule(a11y={"hidden": True})

# Decorative images
ui.image("hero", "/images/banner.png", a11y={"hidden": True})

# Spacing elements
ui.space(a11y={"hidden": True})
```

Do not hide functional elements. If an image conveys information, give it
an `alt` prop instead:

```python
ui.image("status_icon", icon_path, alt="Status: online")
```

### Canvas widgets

Canvas draws arbitrary shapes, and accesskit cannot infer anything from raw
geometry. Always provide alternative text:

```python
# Static chart: describe the content
ui.canvas("chart",
    layers={"data": chart_shapes},
    a11y={"role": "image", "label": "Sales chart: Q1 revenue up 15%, Q2 flat"})

# Interactive canvas: describe the interaction model
ui.canvas("drawing",
    layers={"shapes": shapes},
    a11y={"role": "image", "label": f"Drawing canvas, {len(shapes)} shapes"})
```

### Interactive canvas shapes

When a canvas contains shapes with the `interactive` field, each
shape becomes a separate accessible node. The canvas widget itself
is the container; individual shapes are focusable children. Tab and
Arrow keys navigate between shapes. Enter/Space activates the focused
shape.

This is how you build accessible custom widgets from canvas
primitives. Without interactive shapes, a canvas is a single opaque
"image" node to screen readers.

```python
ui.canvas("color-picker", width=200, height=100,
    layers={"options": [
        {
            "type": "group",
            "transforms": [{"type": "translate", "x": 0, "y": i * 32}],
            "id": f"color-{i}",
            "on_click": True,
            "a11y": {
                "role": "radio",
                "label": color.name,
                "selected": color == model.selected,
                "position_in_set": i + 1,
                "size_of_set": len(colors),
            },
            "children": [
                {"type": "rect", "x": 0, "y": 0, "w": 200, "h": 32,
                 "fill": color.hex},
            ],
        }
        for i, color in enumerate(colors)
    ]},
)
```

Screen reader: "Red, radio button, 1 of 5, selected."

The `position_in_set` and `size_of_set` fields tell screen readers
where each shape sits in the group. Without them, the reader
announces each shape individually with no positional context.

### Custom widgets with state

When building custom widgets with canvas or other primitives, use `toggled`,
`selected`, `value`, and `orientation` to expose their state to AT users:

<!-- test: test_switch_a11y, test_meter_a11y -- keep this code block in sync with the test -->
```python
# Custom toggle switch built with canvas
ui.canvas("dark-mode-switch", layers={...},
    a11y={
        "role": "switch",
        "label": "Dark mode",
        "toggled": model.dark_mode,
    })

# Custom gauge showing percentage
ui.canvas("cpu-gauge", layers={...},
    a11y={
        "role": "meter",
        "label": "CPU usage",
        "value": f"{model.cpu_percent}%",
        "orientation": "horizontal",
    })
```

`toggled` and `selected` are booleans. Use `toggled` for on/off controls
(switches, checkboxes) and `selected` for selection state (list items, tabs).
`value` is a string describing the current value in human-readable form.
`orientation` tells AT users whether a control is horizontal or vertical.

### Set position and popup hints

Use `position_in_set` / `size_of_set` when building composite widgets
from primitives (custom lists, tab bars, radio groups). Without these,
screen readers cannot announce position context like "Item 3 of 7".

<!-- test: test_tab_position_in_set, test_has_popup_menu, test_disabled_override -- keep this code block in sync with the test -->
```python
# Custom tab bar
ui.row(children=[
    ui.button(f"tab_{tab.id}", tab.label,
              a11y={
                  "role": "tab",
                  "selected": tab.id == model.active_tab,
                  "position_in_set": idx,
                  "size_of_set": len(model.tabs),
              })
    for idx, tab in enumerate(model.tabs, 1)
])
```

Use `has_popup` to tell screen readers that activating a widget opens
a popup of a specific type:

```python
# Dropdown button
ui.button("menu_btn", "Options",
    a11y={"has_popup": "menu", "expanded": model.menu_open})

# Combo box with listbox popup
ui.text_input("search", model.query,
    a11y={"has_popup": "listbox", "expanded": model.suggestions_visible})
```

Use `disabled` to override the disabled state for AT when a widget
is visually disabled via custom styling but does not use the standard
`disabled` prop:

```python
ui.button("submit", "Submit",
    a11y={"disabled": not model.form_valid})
```

### Expanded/collapsed state

For disclosure widgets, toggleable panels, and dropdown menus:

<!-- test: test_expanded_button, test_collapsed_button -- keep this code block in sync with the test -->
```python
def view(model):
    return ui.column(children=[
        ui.button("toggle_details",
            "Hide details" if model.show_details else "Show details",
            a11y={"expanded": model.show_details}),

        *(
            [ui.container("details",
                a11y={"role": "region", "label": "Details"},
                children=[...])]
            if model.show_details else []
        ),
    ])
```


## Widget-specific accessibility props

Some widgets accept accessibility props directly as top-level fields,
outside the `a11y` dict. The Rust renderer reads these and maps them
to the appropriate accesskit node properties.

### alt

An accessible label string for visual content widgets.

| Widget | Prop | Type |
|---|---|---|
| `image` | `alt` | `str` |
| `svg` | `alt` | `str` |
| `qr_code` | `alt` | `str` |
| `canvas` | `alt` | `str` |

<!-- test: test_image_alt, test_svg_alt -- keep this code block in sync with the test -->
```python
ui.image("logo", "/images/logo.png", alt="Company logo")
ui.svg("icon", "/icons/search.svg", alt="Search")
ui.qr_code("invite", invite_url, alt="QR code for invite link")
ui.canvas("chart", layers={"data": shapes}, alt="Revenue chart")
```

### label

An accessible label for interactive widgets without a visible text label.

| Widget | Prop | Type |
|---|---|---|
| `slider` | `label` | `str` |
| `vertical_slider` | `label` | `str` |
| `progress_bar` | `label` | `str` |

<!-- test: test_slider_label, test_progress_bar_label -- keep this code block in sync with the test -->
```python
ui.slider("volume", (0, 100), model.volume, label="Volume")
ui.vertical_slider("brightness", (0, 100), model.brightness, label="Brightness")
ui.progress_bar("upload", (0, 100), model.progress, label="Upload progress")
```

### description

An extended accessible description string, announced as secondary
information after the label.

| Widget | Prop | Type |
|---|---|---|
| `image` | `description` | `str` |
| `svg` | `description` | `str` |
| `qr_code` | `description` | `str` |
| `canvas` | `description` | `str` |

<!-- test: test_image_description -- keep this code block in sync with the test -->
```python
ui.image("photo", path, alt="Team photo",
         description="The engineering team at the 2025 offsite")
ui.canvas("chart", layers=layers, alt="Sales chart",
          description="Q1 up 15%, Q2 flat, Q3 down 8%")
```

### decorative

A boolean that hides visual content from AT entirely. Shorthand for
`a11y={"hidden": True}`.

| Widget | Prop | Type |
|---|---|---|
| `image` | `decorative` | `bool` |
| `svg` | `decorative` | `bool` |

<!-- test: test_image_decorative_prop, test_svg_decorative_prop -- keep this code block in sync with the test -->
```python
ui.image("divider", "/images/decorative-line.png", decorative=True)
ui.svg("flourish", "/icons/flourish.svg", decorative=True)
```

### Relationship to the a11y prop

These widget-specific props and the `a11y` prop are complementary. The
widget-specific props are read directly by the Rust renderer as top-level
node properties. The `a11y` prop provides the full set of accesskit
overrides via the `A11yOverride` wrapper widget.

If both are set (e.g. `alt="Photo"` and `a11y={"label": "Team photo"}`),
the `a11y` override takes precedence for the accesskit label since
`A11yOverride` runs after the widget's own `Accessible` implementation.


## Action handling

When an AT triggers an action, iced translates it to a native event. The
renderer maps it to a standard plushie event:

| AT action | Plushie event | Notes |
|---|---|---|
| Click | `Click(id=id)` | Screen reader activate, switch press |
| SetValue | `Input(id=id, value=val)` | AT sets an input value directly |
| Focus | (internal) | Focus tracking, no event emitted |
| Other | `A11yAction(id=id, action=name)` | Scroll, dismiss, etc. |

Your `update()` already handles `Click(...)` and `Input(...)`.
AT actions produce identical events. Handle `A11yAction` for the catch-all:

```python
def update(model, event):
    if isinstance(event, A11yAction):
        if event.action == "scroll_down":
            return scroll(model, "down")
        if event.action == "dismiss":
            return close_dialog(model)
        return model
    ...
```


## Testing accessibility

The test framework provides methods for verifying accessibility semantics
without running a screen reader.

### find_by_role

Find an element by its accessible role:

```python
def test_heading_has_correct_role(plushie_pool):
    with AppFixture(MyApp, plushie_pool) as app:
        el = app.find_by_role("heading")
        assert el is not None
```

### find_by_label

Find an element by its accessible label:

```python
def test_input_has_label(plushie_pool):
    with AppFixture(MyApp, plushie_pool) as app:
        el = app.find_by_label("Email address")
        assert el is not None
```

### Element helpers

`Element` provides lower-level accessors:

```python
def test_element_accessors(plushie_pool):
    with AppFixture(MyApp, plushie_pool) as app:
        el = app.find("#heading")

        # Get the raw a11y prop dict
        assert el.a11y() == {"role": "heading", "level": 1}

        # Get the inferred role (checks a11y override, then widget type)
        assert el.inferred_role() == "heading"
```

### Testing patterns

**Test the semantics, not the implementation.** Focus on what AT users
experience:

```python
def test_todo_app_is_accessible(plushie_pool):
    with AppFixture(TodoApp, plushie_pool) as app:
        # Interactive widgets are labelled
        el = app.find_by_label("New todo")
        assert el is not None

        # Status updates are announced
        app.type_text("#new_todo", "Buy milk")
        app.submit("#new_todo")
        status = app.find("#todo_count")
        assert status is not None
        assert status.a11y().get("live") == "polite"
```


## Building

Accessibility is included by default in both precompiled binaries
(`python -m plushie download`) and source builds (`python -m plushie build`).


## Platform support

| Platform | AT | API | Status |
|---|---|---|---|
| Linux | Orca | AT-SPI2 | Supported |
| macOS | VoiceOver | NSAccessibility | Supported |
| Windows | NVDA, JAWS, Narrator | UI Automation | Supported |

All three platforms are supported via accesskit.


## Testing with a screen reader

### Linux (Orca)

```bash
# Build the renderer (a11y is included by default)
python -m plushie build

# Start Orca (usually Super+Alt+S, or from accessibility settings)
orca &

# Run your app
python -m plushie run my_app:MyApp
```

### macOS (VoiceOver)

```bash
python -m plushie build

# Toggle VoiceOver: Cmd+F5
python -m plushie run my_app:MyApp
```

### Windows (NVDA)

```bash
python -m plushie build

# Start NVDA
python -m plushie run my_app:MyApp
```

Tab between widgets. The screen reader should announce roles, labels, and
state (checked, disabled, expanded, etc.).


## Architecture details

For contributors working on the accessibility internals:

### iced fork (`v0.14.0-a11y-accesskit` branch)

The iced fork adds native accessibility support. Key additions:

- **`Accessible` trait** - widgets implement this to report their role,
  label, and state to accesskit. Most built-in widgets already implement it.
- **`TreeBuilder`** in `iced_winit` - walks the widget tree via `operate()`,
  collecting `Accessible` metadata and building an accesskit `TreeUpdate`.
- **Per-window adapters** - each window gets an accesskit adapter connecting
  to the platform's AT layer.
- **AT action routing** - AT actions are translated to native iced events,
  which the renderer maps to plushie wire events.

### A11yOverride wrapper widget

`a11y_widget.rs` in plushie contains two wrapper widgets:

- **`A11yOverride`** - wraps any iced `Element` and intercepts `operate()`
  to apply Python-side overrides from the `a11y` prop (role, label,
  description, live, expanded, required, level, busy, invalid, modal,
  read_only, mnemonic, toggled, selected, value, orientation, labelled_by,
  described_by, error_message).
- **`HiddenInterceptor`** - wraps an `Element` and suppresses it from the
  accessibility tree when `hidden: True` is set.

These wrappers are applied automatically by the renderer when building the
iced widget tree from plushie's UI tree. No manual wrapping is needed from
Python.

### Renderer integration

When the renderer builds the iced widget tree from a plushie snapshot or
patch, it checks each node's `a11y` prop. If present (and not just
`hidden: True`), the rendered widget is wrapped in `A11yOverride`. If
`hidden: True`, it is wrapped in `HiddenInterceptor`. Nodes without an
`a11y` prop are rendered as-is; iced's native `Accessible` trait provides
their baseline accessibility semantics.
