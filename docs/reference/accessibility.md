# Accessibility

Plushie integrates with platform accessibility services via
[AccessKit](https://github.com/AccessKit/accesskit): VoiceOver on
macOS, AT-SPI/Orca on Linux, UI Automation/NVDA/JAWS on Windows.
Most accessibility semantics are inferred automatically from widget
types, so correct roles, labels, and state are exposed without
extra work.

This reference covers the `a11y` prop, the `A11y` dataclass in
`plushie.types`, roles, labels, live regions, cross-references,
keyboard navigation helpers on `plushie.commands.Command`, and the
focus and announce events in `plushie.events`.

## Accessible by default

Built-in widgets expose accessibility metadata automatically: a
button announces itself as a button, a checkbox tracks its checked
state, a slider exposes its numeric value and range. Application
code does not need to add accessibility attributes for standard
widgets.

When overrides are needed (custom canvas controls, widgets with
context-dependent labels, relationship annotations), the `a11y`
kwarg is accepted by every widget builder in `plushie.ui`.

## The a11y kwarg

The `a11y` kwarg accepts either an `A11y` dataclass instance or a
plain `dict` with the same field names. Both forms go to the wire
unchanged; dataclass instances are converted via their `to_wire`
method, which strips `None` fields.

```python
from plushie import ui
from plushie.types import A11y

ui.button(
    "save", "Save",
    a11y=A11y(description="Save the current document"),
)

ui.text_input(
    "email", model.email,
    a11y={"required": True, "labelled_by": "email_label"},
)
```

Prop values are validated renderer-side. The `A11y` dataclass adds
a Python-level type check for role literals and the other enum
fields, which is the main reason to prefer it over a raw dict.

## The A11y dataclass

`plushie.types.A11y` is a frozen dataclass with `slots=True`. All
fields default to `None`, meaning "use the auto-inferred value".

```python
from plushie.types import A11y

A11y(role="button", label="Save", description="Save the document")
```

### Fields

| Field | Type | Purpose |
|---|---|---|
| `role` | `A11yRole \| None` | Override the inferred role |
| `label` | `str \| None` | Accessible name (override inferred label) |
| `description` | `str \| None` | Longer description read after the label |
| `live` | `A11yLive \| None` | Live region announcement mode |
| `hidden` | `bool \| None` | Exclude from the accessibility tree |
| `expanded` | `bool \| None` | Disclosure state (combobox, menu) |
| `required` | `bool \| None` | Form field is required |
| `level` | `int \| None` | Heading level (1-6) |
| `busy` | `bool \| None` | Suppress announcements during updates |
| `invalid` | `bool \| None` | Form validation error state |
| `modal` | `bool \| None` | Dialog is modal (traps focus) |
| `read_only` | `bool \| None` | Value is readable but not editable |
| `mnemonic` | `str \| None` | Keyboard mnemonic (single character) |
| `toggled` | `bool \| None` | Toggle / checked state |
| `selected` | `bool \| None` | Selection state |
| `value` | `str \| None` | Current value for assistive technology |
| `orientation` | `A11yOrientation \| None` | Layout orientation hint |
| `labelled_by` | `str \| None` | ID of the widget that provides this widget's label |
| `described_by` | `str \| None` | ID of the widget that provides a description |
| `error_message` | `str \| None` | ID of the widget showing the error message |
| `disabled` | `bool \| None` | Disabled state override |
| `position_in_set` | `int \| None` | 1-based position in a group |
| `size_of_set` | `int \| None` | Total items in the group |
| `has_popup` | `A11yHasPopup \| None` | Popup type indicator |
| `active_descendant` | `str \| None` | ID of the active descendant in a composite widget |
| `radio_group` | `tuple[str, ...] \| None` | IDs of the radio buttons in this group |

### Type aliases

`plushie.types` exposes three `Literal` aliases used by `A11y`:

```python
type A11yLive = Literal["polite", "assertive"]
type A11yOrientation = Literal["horizontal", "vertical"]
type A11yHasPopup = Literal["listbox", "menu", "dialog", "tree", "grid"]
```

## Roles

`A11yRole` is a `Literal` union of canonical underscore-separated
role strings. They group naturally:

**Interactive**: `button`, `check_box`, `combo_box`, `link`,
`menu_item`, `radio_button`, `slider`, `switch`, `tab`,
`text_input`, `multiline_text_input`, `tree_item`

**Structure**: `generic_container`, `group`, `heading`, `label`,
`list`, `list_item`, `column_header`, `row`, `cell`, `table`,
`tree`, `static_text`

**Landmarks**: `navigation`, `region`, `search`

**Status**: `alert`, `alert_dialog`, `dialog`, `status`, `meter`,
`progress_indicator`

**Other**: `document`, `image`, `canvas`, `menu`, `menu_bar`,
`scroll_bar`, `scroll_view`, `separator`, `tab_list`, `tab_panel`,
`toolbar`, `tooltip`, `window`

Layout containers (`column`, `row` widgets, etc.) use
`generic_container`, which is filtered from the platform
accessibility tree. Screen reader users navigate through the
semantic content (buttons, text, inputs) without encountering
intermediate layout wrappers.

### Headings

Use `role="heading"` together with `level` (1-6) to create a
heading outline that screen readers can use for document
navigation:

```python
ui.text("section", "Recent activity", a11y=A11y(role="heading", level=2))
```

### Landmarks

Landmark roles let screen readers jump between regions of a
window. Use them on top-level containers that map to logical
sections.

```python
ui.container(
    "sidebar",
    nav_links(model),
    a11y=A11y(role="navigation", label="Primary"),
)

ui.container(
    "content",
    document_view(model),
    a11y=A11y(role="region", label="Document"),
)
```

`navigation`, `region`, and `search` are the landmark roles the
renderer accepts today. The AccessKit-derived tree does not ship
dedicated `main`, `banner`, `contentinfo`, or `complementary`
roles; use `region` with a descriptive `label` for those sections
instead.

## Labels and descriptions

A screen reader announces each widget's accessible name. The name
comes from, in order:

1. An explicit `label` on the `A11y` prop.
2. The widget's auto-inferred label (`button` label, `text`
   content, `image` alt text, etc.).
3. A `labelled_by` reference to another widget's ID.

Interactive widgets without an accessible name announce only their
role ("button", "checkbox") and give no context. Always give
interactive widgets either a label prop or a `labelled_by`
reference.

```python
ui.text("email_label", "Email address")
ui.text_input(
    "email", model.email,
    a11y=A11y(labelled_by="email_label"),
)

ui.text_input(
    "password", model.password,
    a11y=A11y(label="Password", described_by="password_hint"),
)
ui.text("password_hint", "Must be at least 8 characters", size=11)
```

## Live regions

`A11yLive` controls how screen readers announce dynamic content
updates on widgets that stay mounted while their content changes:

| Value | Behaviour | Use for |
|---|---|---|
| `"polite"` | Announced after current speech finishes | Status messages, counters, progress updates |
| `"assertive"` | Interrupts current speech immediately | Error messages, critical alerts |

```python
ui.text("status", model.status, a11y=A11y(live="polite"))
ui.text("error", model.error, a11y=A11y(live="assertive", role="alert"))
```

Use `"assertive"` sparingly. Rapid updates cause announcement
storms. Prefer `"polite"` for anything that updates more than once
per user action. Do not set `live` on static content; the screen
reader will re-announce it on every tree rebuild even when the
content has not changed.

## Relationships

Cross-reference fields carry widget IDs. They are resolved during
tree normalization, so bare IDs inside a scope resolve against
that scope.

| Field | Purpose |
|---|---|
| `labelled_by` | The widget whose content names this one |
| `described_by` | The widget that provides extended description |
| `error_message` | The widget showing this field's validation error |
| `active_descendant` | The active item in a composite widget |
| `radio_group` | IDs of the peers in this radio's group |

```python
ui.text_input(
    "quantity", str(model.quantity),
    a11y=A11y(
        label="Quantity",
        described_by="quantity_hint",
        error_message="quantity_error" if model.error else None,
        invalid=bool(model.error),
    ),
)
```

## Hidden and decorative content

Set `hidden=True` on content that should not appear in the
accessibility tree at all. Use this for pure ornamentation or for
duplicate visual-only content that would noisily re-announce.

```python
ui.container(
    "decoration",
    ui.image("stripes", "stripes.png"),
    a11y=A11y(hidden=True),
)
```

Image widgets also accept a `decorative` kwarg that achieves the
same effect for single images without wrapping them.

## Keyboard navigation

Plushie ships built-in keyboard navigation. Tab and Shift+Tab
cycle focusable widgets, Space and Enter activate the focused
widget, arrow keys drive sliders and lists, F6 cycles panes in a
`pane_grid`, and Escape dismisses popups.

Programmatic focus lives on `Command`:

| Factory | Purpose |
|---|---|
| `Command.focus(widget_id)` | Focus a specific widget |
| `Command.focus_next()` | Move focus to the next focusable widget |
| `Command.focus_previous()` | Move focus to the previous focusable widget |
| `Command.focus_next_within(scope)` | Next focus bounded by a scope widget |
| `Command.focus_previous_within(scope)` | Previous focus bounded by a scope widget |

The `*_within` variants limit the Tab cycle to descendants of the
given scope widget. Useful for menus, pane grids, and other
keyboard containers that should not leak focus to their siblings.

```python
from plushie import Command
from plushie.events import KeyEvent

def update(self, model, event):
    match event:
        case KeyEvent(type="press", key="Tab", modifiers={"ctrl": True}):
            return model, Command.focus_next_within("sidebar")
        case _:
            return model
```

### Focus events

The renderer emits `Focused` and `Blurred` events when a widget
gains or loses keyboard focus. Both carry `id`, `window_id`, and
`scope`.

```python
from plushie.events import Focused, Blurred

def update(self, model, event):
    match event:
        case Focused(id=widget_id):
            return replace(model, focused=widget_id)
        case Blurred(id=widget_id) if model.focused == widget_id:
            return replace(model, focused=None)
        case _:
            return model
```

### Canvas accessibility

Canvas is a raw drawing surface. The renderer cannot know that a
group of shapes is meant to be a button; supply `a11y` annotations
on the `interactive` group that wraps the shapes, and set
`focusable=True` to put the element in the Tab order.

```python
from plushie import canvas
from plushie.types import A11y

canvas.interactive(
    canvas.rect(0, 0, 100, 36, fill="#3b82f6"),
    id="save_btn",
    on_click=True,
    focusable=True,
    a11y=A11y(role="button", label="Save experiment"),
)
```

Without `focusable=True`, the element still responds to mouse
clicks but is invisible to keyboard navigation and screen readers.

## Live announcements

`Command.announce(text, politeness="polite")` asks the system
screen reader to speak `text` immediately, without routing it
through any widget. Use it for transient feedback that has no
visual counterpart.

```python
return model, Command.announce("Draft saved", politeness="polite")
```

`politeness` accepts `"polite"` (the default, queued after the
current utterance) or `"assertive"` (interrupts the current
utterance). The factory raises `ValueError` on any other value.

The renderer also emits an `Announce` event when an announcement
is requested externally; it carries a `text` field and is
delivered to `update` like any other event.

## Disabled versus read-only

These two states are semantically different.

| State | Meaning | Screen reader behaviour |
|---|---|---|
| `disabled=True` | Not currently usable | Often skipped in Tab navigation, announced as unavailable |
| `read_only=True` | Has a value that can be read but not changed | Fully navigable and announced, editing blocked |

Use `disabled` for controls that become active based on other
state (a Submit button that waits for required fields). Use
`read_only` for values the user can select and copy but not edit.

## Disabled and busy containers

`busy=True` suppresses child announcements during bulk updates,
useful while a pane's content is being swapped out. `modal=True`
marks a container as a modal dialog so the screen reader traps
focus inside it.

## Grouping related controls

Wrap logically related controls in a container with `role="group"`
when the grouping carries meaning the user should hear:

```python
ui.container(
    "shipping_options",
    ui.radio("standard", "standard", model.shipping, label="Standard (5-7 days)"),
    ui.radio("express", "express", model.shipping, label="Express (1-2 days)"),
    a11y=A11y(role="group", label="Shipping options"),
)
```

Do not wrap things in groups unless the grouping adds semantic
value. Layout containers already use `generic_container` and are
invisible to screen readers.

## Platform notes

| Platform | AT service | Integration |
|---|---|---|
| macOS | VoiceOver | AccessKit to NSAccessibility |
| Linux | Orca (AT-SPI) | AccessKit to AT-SPI2 |
| Windows | NVDA / JAWS | AccessKit to UI Automation |

Assistive-technology actions (for example VoiceOver's "activate"
gesture) produce the same widget events as direct interaction. No
special handling is needed in `update`.

## See also

- [Built-in Widgets](built-in-widgets.md) for the widgets that
  accept the `a11y` kwarg and the label, description, and
  decorative props they infer from.
- [Events](events.md) for `Focused`, `Blurred`, and `Announce`
  event shapes.
- [Commands](commands.md) for focus management and
  `Command.announce`.
- [Subscriptions](subscriptions.md) for global keyboard
  subscriptions that complement built-in Tab navigation.
- [AccessKit](https://github.com/AccessKit/accesskit) for the
  cross-platform accessibility library Plushie builds on.
