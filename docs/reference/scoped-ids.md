# Scoped IDs

Named containers automatically scope their children's IDs, producing
unique hierarchical paths without manual prefixing. This is how you
distinguish the delete button in file A from the delete button in
file B: the container's ID becomes part of the path. Scoping is
performed by `plushie.tree.normalize` and the results flow back to
`update` on every scoped event in `plushie.events`.

## Scoping rules

| Node type | Creates scope? | Notes |
|---|---|---|
| Named container (explicit `id=`) | Yes | ID pushed onto the scope chain |
| Auto-ID container (`auto:` prefix) | No | Transparent, no scope effect |
| Window node (`type="window"`) | Yes | Uses `#` separator instead of `/` |
| Custom widget (`WidgetDef` subclass) | No | Children inherit the enclosing scope |

User-provided IDs must be non-empty printable ASCII and may not
contain `/` or `#`. The slash is reserved for the scope separator
and `#` is reserved for window-qualified paths (e.g.
`"main#form/email"`). `normalize` raises `ValueError` on violation.
The length is capped at 1024 bytes.

## ID resolution

During normalization, the scope chain builds canonical wire IDs.
Window nodes use `#` as the separator; containers within a window
use `/`:

```
main (window)               ->  "main"
  sidebar (container)       ->  "main#sidebar"
    form (container)        ->  "main#sidebar/form"
      email (text_input)    ->  "main#sidebar/form/email"
      save (button)         ->  "main#sidebar/form/save"
```

The `#` appears once, at the window boundary. Deeper nesting uses
`/`. The canonical format is `window#scope/path/id`.

Resolution is recursive; nesting depth is unlimited up to the
`normalize` safety cap. The scope is tracked as a forward-order
string and prepended to each child's ID during the single-pass walk.

### Auto-ID containers are transparent

Layout containers without an explicit ID (`ui.column`, `ui.row`,
`ui.stack`, `ui.grid`, `ui.keyed_column`, `ui.responsive`) get an
auto-generated ID of the form `auto:{type}:{index}`, where `index`
is the position of the node within its parent's children. Auto-ID
nodes do not create a scope, so you can wrap content in layout
containers freely without changing the ID hierarchy:

```python
from plushie import ui

ui.container(
    "form",
    ui.column(
        ui.text_input("email", ""),   # scoped as "form/email"
        ui.button("save", "Save"),    # scoped as "form/save"
        spacing=8,
    ),
)
```

Intermediate layout containers exist for visual arrangement, not
semantic grouping. Only containers with an explicit positional
`id` argument create scope boundaries.

### Custom widgets are transparent

Custom widgets (subclasses of `WidgetDef` in `plushie.widget`) do
not create scopes. When a widget's `view()` renders children,
those children inherit the enclosing parent's scope, not the
widget's own ID. The widget's `handle_event()` callback intercepts
scoped events before they reach `update()`, providing the
encapsulation layer instead.

## Duplicate ID detection

Normalization detects duplicate sibling IDs (two children of the
same parent with the same ID) and raises `ValueError`:

```
duplicate sibling IDs detected during normalize: 'save'
```

Detection is sibling-scoped. The same local ID can exist in
different scopes safely, since the scope prefix ensures global
uniqueness:

```python
ui.column(
    ui.container("form_a", ui.button("save", "Save")),  # "form_a/save"
    ui.container("form_b", ui.button("save", "Save")),  # "form_b/save"
)
```

## Dynamic IDs

IDs can be any string, including values built from your model.
This is how you scope list items:

```python
def view(self, model):
    return ui.window(
        "main",
        ui.column(
            *(
                ui.container(
                    file.id,
                    ui.button("select", file.name),
                    ui.button("delete", "x"),
                )
                for file in model.files
            ),
        ),
    )
```

Each file becomes a scope. The delete button for `"hello.py"` gets
the wire ID `"main#hello.py/delete"`. In `update`, you bind the
filename from the scope tuple:

```python
from plushie.events import Click

def update(self, model, event):
    match event:
        case Click(id="delete", scope=(file_id, *_)):
            return remove_file(model, file_id)
        case _:
            return model
```

Dynamic IDs follow the same rules as static IDs: printable ASCII,
no `/` or `#`, and no duplicates among siblings.

## Event scope field

When the renderer emits a scoped event, the wire ID is the canonical
`window#scope/path/id` (e.g. `"main#sidebar/form/save"`). The
protocol decoder splits it into three fields on the event dataclass:

- `id`: the local ID (last path segment).
- `scope`: a `tuple[str, ...]` of ancestor IDs, nearest parent
  first, with the window ID appended as the final element.
- `window_id`: the owning window.

```python
from plushie.events import Click

Click(id="save", scope=("form", "sidebar", "main"), window_id="main")
```

Scope is reversed so you can pattern match on the immediate parent
with `scope=(parent, *_)` without knowing the full ancestry. The
window ID is always the last element in the scope tuple, giving
you the full hierarchy from innermost container out to the window.

### Pattern matching examples

```python
from plushie.events import Click, Toggle

def update(self, model, event):
    match event:
        # Local ID only, any scope
        case Click(id="save"):
            return save(model)

        # Immediate parent match
        case Click(id="save", scope=("form", *_)):
            return save_form(model)

        # Bind a dynamic parent from a list item
        case Toggle(id="done", scope=(item_id, *_), value=done):
            return mark_done(model, item_id, done)

        # Match window via window_id
        case Click(id="save", window_id="settings"):
            return save_settings(model)

        # Top-level widget: only the window is in scope
        case Click(id="save", scope=(window_id,)):
            return save_in_window(model, window_id)

        case _:
            return model
```

Only widget events carry scope. Global subscription events
(`KeyEvent` with `id=None`, mouse move subscriptions, timer ticks)
have an empty `scope` tuple and no `window_id`. Pointer
subscription events targeted at a window surface are delivered as
widget events with `id` set to the window ID and `scope=()`.

## Path reconstruction

`plushie.events.target(event)` reconstructs the forward-slash path
from an event's `id` and `scope` fields. The window ID is stripped
from the end of the scope tuple since it is not part of the
container path:

```python
from plushie.events import Click, target

target(Click(id="save", scope=("form", "sidebar", "main"), window_id="main"))
# "sidebar/form/save"

target(Click(id="save"))
# "save"
```

The `plushie.tree.ScopedId` dataclass is the structured form. Use
`ScopedId.parse("main#sidebar/form/email")` when you need to
inspect or manipulate a canonical wire ID programmatically.

## Command paths

Commands that target a widget by path use the forward-slash scoped
format:

```python
from plushie import Command

Command.focus("form/email")
```

In multi-window apps, target a specific window using the
`window_id#path` syntax:

```python
Command.focus("settings#email")
```

Without a window qualifier, the command targets whatever window
contains the widget.

## Multi-window scoping

The window ID is part of the scope chain (always the last element
in `scope`). Each window creates a separate namespace. A widget
in window `"main"` has wire ID `"main#form/save"`, distinct from
`"settings#form/save"` in window `"settings"`. Events from one
window never trigger handlers meant for another unless you match
on `id` alone.

Pattern match on the window via `window_id`:

```python
case Click(id="save", window_id="settings"):
    save_settings(model)
```

## Test selectors

Test helpers on `plushie.testing.AppFixture` (`find`, `click`,
`text`, etc.) accept `#`-prefixed ID selectors with scoped paths:

```python
app.find("#save")                  # local ID, any window
app.click("#sidebar/form/save")    # full scoped path
app.text("#form/email")            # scoped assertion
```

In multi-window apps, selectors can include a window qualifier
using the `window_id#widget_path` syntax:

```python
app.click("main#save")             # "save" in window "main"
app.find("settings#form/email")    # scoped path in window "settings"
```

Without a window qualifier (`"#save"`), the selector searches all
windows. An ambiguous match across windows raises an error. Use
the window qualifier to disambiguate.

## Accessibility cross-references

A11y props (`labelled_by`, `described_by`, `error_message`) that
reference widget IDs are resolved relative to the current scope
during normalization. A bare local ID is prefixed with the
containing scope; an ID already containing `/` or `#` passes
through unchanged:

```python
ui.container(
    "form",
    ui.text("email_label", "Email"),
    ui.text_input(
        "email",
        model.email,
        a11y={"labelled_by": "email_label"},  # resolves to "form/email_label"
    ),
)
```

## See also

- [Events reference](events.md)
- [Built-in widgets reference](built-in-widgets.md)
- [Commands reference](commands.md)
- [Subscriptions reference](subscriptions.md)
