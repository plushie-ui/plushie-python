# Composition Patterns

Composition in Python is just functions. A view component is a
function that takes state and returns a node dict, the same shape
that `plushie.ui` builders emit. These patterns are recipes for
structuring ordinary `view` functions and model shapes. They are
not special framework features, just compositions of existing
builders, events, and state helpers from `plushie.state`,
`plushie.route`, `plushie.selection`, `plushie.undo`, and
`plushie.data`.

## Reusable view functions

Extract a chunk of `view` into a top-level function that takes
whatever slice of the model it needs and returns a node. The
convention is plain `def` with a `dict[str, Any]` return annotation:

```python
from typing import Any

from plushie import ui


def user_card(user: User, selected: bool) -> dict[str, Any]:
    return ui.container(
        f"user:{user.id}",
        ui.column(
            ui.text(user.name, size=16),
            ui.text(user.email, color="#666"),
            spacing=4,
        ),
        padding=12,
        background="#eef4ff" if selected else "#ffffff",
    )
```

Call it from `view`:

```python
def view(self, model: Model) -> dict[str, Any]:
    return ui.window(
        "main",
        ui.column(
            *(user_card(u, u.id in model.selected) for u in model.users),
            spacing=8,
            padding=16,
        ),
        title="Users",
    )
```

Component functions stay close to the view that uses them. Move
them into their own module only when the same component is used
from several apps.

## Master-detail

Two panes in a row. The master pane lists items, the detail pane
shows the currently focused item. Model holds the collection and
the focused ID:

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click


@dataclass(frozen=True, slots=True)
class Item:
    id: str
    name: str
    body: str


@dataclass(frozen=True, slots=True)
class Model:
    items: tuple[Item, ...] = ()
    focused: str | None = None


class MasterDetail(plushie.App[Model]):
    def update(self, model, event):
        match event:
            case Click(id=click_id) if click_id.startswith("item:"):
                return replace(model, focused=click_id.removeprefix("item:"))
            case _:
                return model

    def view(self, model):
        return ui.window(
            "main",
            ui.row(
                ui.container(
                    "list",
                    ui.keyed_column(
                        *(
                            ui.button(
                                f"item:{item.id}",
                                item.name,
                                width="fill",
                                style="primary" if item.id == model.focused else "text",
                            )
                            for item in model.items
                        ),
                        spacing=2,
                    ),
                    width=240,
                    padding=8,
                ),
                ui.container(
                    "detail",
                    _detail(model),
                    width="fill",
                    padding=16,
                ),
                width="fill",
                height="fill",
            ),
            title="Master / detail",
        )


def _detail(model: Model) -> dict[str, Any]:
    item = next((i for i in model.items if i.id == model.focused), None)
    if item is None:
        return ui.text("placeholder", "Select an item", color="#999")
    return ui.column(
        ui.text("name", item.name, size=20),
        ui.text("body", item.body),
        spacing=8,
    )
```

`ui.keyed_column` diffs the master list by child ID, so adding,
removing, or reordering items preserves widget state.

## Modal dialogs

Overlays (modals, toasts, popovers) must be placed at the **window
level** to stay visible regardless of scrolling. A `ui.stack` as
the direct child of the window layers overlay content on top of
everything else. If a modal lives inside a scrollable or a
fixed-height container, it scrolls or clips with that container.

```python
def view(self, model):
    return ui.window(
        "main",
        ui.stack(
            _main_content(model),
            *([_modal(model)] if model.show_modal else []),
        ),
        title="App",
    )


def _modal(model: Model) -> dict[str, Any]:
    return ui.container(
        "overlay",
        ui.container(
            "dialog",
            ui.column(
                ui.text("modal-title", "Confirm", size=18),
                ui.text("modal-body", "Are you sure?"),
                ui.row(
                    ui.button("modal-cancel", "Cancel"),
                    ui.button("modal-confirm", "Confirm", style="primary"),
                    spacing=8,
                ),
                spacing=12,
            ),
            padding=24,
            background="#ffffff",
            border={"radius": 8},
        ),
        width="fill",
        height="fill",
        background="#00000088",
        center=True,
    )
```

The update side tracks `show_modal` plus whatever pending action
the dialog confirms:

```python
def update(self, model, event):
    match event:
        case Click(id="delete"):
            return replace(model, show_modal=True, pending_action="delete")
        case Click(id="modal-confirm"):
            model = _perform(model, model.pending_action)
            return replace(model, show_modal=False, pending_action=None)
        case Click(id="modal-cancel"):
            return replace(model, show_modal=False, pending_action=None)
        case _:
            return model
```

## Popover menus

`ui.overlay` positions floating content relative to an anchor. It
takes exactly two children: first the anchor, second the overlay.
`flip=True` auto-repositions when the overlay would go off screen.

```python
ui.overlay(
    "menu",
    ui.button("trigger", "Options"),
    ui.container(
        "dropdown",
        ui.column(
            ui.button("opt-edit", "Edit", style="text", width="fill"),
            ui.button("opt-delete", "Delete", style="text", width="fill"),
            spacing=2,
        ),
        padding=8,
        background="#ffffff",
        border={"width": 1, "color": "#ddd", "radius": 4},
    ),
    position="below",
    gap=4,
    flip=True,
)
```

For menus anchored at the cursor (right-click context menus), use
`ui.pin` inside the window-level stack and render conditionally
based on stored cursor coordinates.

## Tabs

Buttons in a row with conditional content. Track the active tab
in the model:

```python
from dataclasses import replace

from plushie import ui
from plushie.events import Click


TABS = ("overview", "details", "settings")


def update(self, model, event):
    match event:
        case Click(id=click_id) if click_id.startswith("tab:"):
            return replace(model, active_tab=click_id.removeprefix("tab:"))
        case _:
            return model


def view(self, model):
    return ui.window(
        "main",
        ui.column(
            ui.row(
                *(
                    ui.button(
                        f"tab:{tab}",
                        tab.capitalize(),
                        style="primary" if model.active_tab == tab else "text",
                    )
                    for tab in TABS
                ),
                spacing=0,
            ),
            ui.rule(),
            _tab_body(model),
            width="fill",
        ),
        title="Tabs",
    )


def _tab_body(model: Model) -> dict[str, Any]:
    match model.active_tab:
        case "overview":
            return _overview(model)
        case "details":
            return _details(model)
        case "settings":
            return _settings(model)
        case _:
            return _overview(model)
```

## Wizards and multi-step forms

Model the current step as an enum-like value, track the data
gathered so far, and gate the Next button on validity:

```python
from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class WizardModel:
    step: int = 0
    name: str = ""
    email: str = ""
    plan: str | None = None


def update(self, model, event):
    match event:
        case Input(id="name", value=v):
            return replace(model, name=v)
        case Input(id="email", value=v):
            return replace(model, email=v)
        case Click(id="plan-pro"):
            return replace(model, plan="pro")
        case Click(id="plan-free"):
            return replace(model, plan="free")
        case Click(id="next") if _step_valid(model):
            return replace(model, step=model.step + 1)
        case Click(id="back") if model.step > 0:
            return replace(model, step=model.step - 1)
        case _:
            return model


def _step_valid(model: WizardModel) -> bool:
    match model.step:
        case 0:
            return bool(model.name)
        case 1:
            return "@" in model.email
        case 2:
            return model.plan is not None
        case _:
            return True
```

The view dispatches on `model.step`:

```python
def view(self, model):
    body = [_step_name, _step_email, _step_plan, _step_review][model.step](model)
    return ui.window(
        "main",
        ui.column(
            body,
            ui.row(
                ui.button("back", "Back") if model.step > 0 else ui.space(),
                ui.space(width="fill"),
                ui.button("next", "Next", style="primary"),
                width="fill",
            ),
            spacing=16,
            padding=16,
        ),
        title="Sign up",
    )
```

## Forms with validation

Validate on input, store the error next to the value, and render
the error below the field:

```python
from dataclasses import dataclass, replace

from plushie import ui
from plushie.events import Input


@dataclass(frozen=True, slots=True)
class FormModel:
    email: str = ""
    email_error: str | None = None


def update(self, model, event):
    match event:
        case Input(id="email", value=email):
            error = None if "@" in email else "Must be a valid email"
            return replace(model, email=email, email_error=error)
        case _:
            return model


def email_field(model: FormModel) -> dict[str, Any]:
    return ui.column(
        ui.text_input(
            "email",
            model.email,
            placeholder="Email",
            a11y={"required": True, "invalid": model.email_error is not None},
        ),
        *(
            [ui.text("email-error", model.email_error, color="#ef4444", size=12)]
            if model.email_error
            else []
        ),
        spacing=4,
    )
```

For forms with several fields, keep one `<name>_error` field per
input and compute a `form_valid` property from the model to gate
the submit button.

## Selection and batch actions

`plushie.selection.Selection` is a pure data structure supporting
single, multi, and range selection. Construct it with
`Selection.new(mode="multi")` and update it via `toggle`,
`select`, `range_select`, and `clear`.

```python
from dataclasses import dataclass, replace

from plushie import ui
from plushie.events import Click, Toggle
from plushie.selection import Selection


@dataclass(frozen=True, slots=True)
class ListModel:
    items: tuple[Item, ...] = ()
    selection: Selection = Selection.new(mode="multi")


def update(self, model, event):
    match event:
        case Toggle(id=tid, value=checked) if tid.startswith("row:"):
            item_id = tid.removeprefix("row:")
            sel = (
                model.selection.select(item_id, extend=True)
                if checked
                else model.selection.deselect(item_id)
            )
            return replace(model, selection=sel)
        case Click(id="delete-selected"):
            ids = model.selection.selected()
            return replace(
                model,
                items=tuple(i for i in model.items if i.id not in ids),
                selection=model.selection.clear(),
            )
        case _:
            return model


def view(self, model):
    return ui.window(
        "main",
        ui.column(
            ui.keyed_column(
                *(
                    ui.row(
                        ui.checkbox(
                            f"row:{item.id}",
                            model.selection.is_selected(item.id),
                            label=item.name,
                        ),
                        spacing=8,
                    )
                    for item in model.items
                ),
                spacing=4,
            ),
            ui.button(
                "delete-selected",
                f"Delete {len(model.selection.selected())}",
                disabled=len(model.selection.selected()) == 0,
            ),
            spacing=12,
            padding=16,
        ),
        title="List",
    )
```

For range selection, pass `order=` at construction time so
`range_select(id)` knows how to slice between the anchor and the
target.

## Routing and navigation stacks

`plushie.route.Route` is a LIFO navigation stack. Each entry pairs
a path with a params dict. `push`, `pop`, and `replace_top` return
new `Route` instances; `current()` and `params()` read the top.

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click
from plushie.route import Route


@dataclass(frozen=True, slots=True)
class Model:
    route: Route = Route.new("list")


class Nav(plushie.App[Model]):
    def update(self, model, event):
        match event:
            case Click(id=click_id) if click_id.startswith("show-detail:"):
                item_id = click_id.removeprefix("show-detail:")
                return replace(
                    model,
                    route=model.route.push("detail", {"id": item_id}),
                )
            case Click(id="back") if model.route.can_go_back:
                return replace(model, route=model.route.pop())
            case _:
                return model

    def view(self, model):
        match model.route.current():
            case "list":
                return _list_view(model)
            case "detail":
                return _detail_view(model, model.route.params())
            case _:
                return _list_view(model)
```

`Route.can_go_back` is a boolean property; `Route.depth` reports
the stack size; `Route.history()` returns every path, top first.

## Undo and redo

`plushie.undo.UndoStack` pairs an initial model with reversible
`UndoCommand` entries. Each command provides `apply_fn` and
`undo_fn` callables. Rapid successive edits with the same
`coalesce` key merge into a single entry within
`coalesce_window_ms`.

```python
from dataclasses import replace

from plushie import ui, Command
from plushie.events import Input, KeyEvent
from plushie.undo import UndoCommand, UndoStack


def update(self, model, event):
    match event:
        case Input(id="editor", value=text):
            old = model.undo.current
            cmd = UndoCommand(
                apply_fn=lambda _cur, _v=text: _v,
                undo_fn=lambda _cur, _o=old: _o,
                label="edit",
                coalesce="typing",
                coalesce_window_ms=500,
            )
            return replace(model, undo=model.undo.apply_command(cmd))
        case KeyEvent(type="press", key="z", modifiers=m) if m.command and not m.shift:
            return replace(model, undo=model.undo.undo())
        case KeyEvent(type="press", key="z", modifiers=m) if m.command and m.shift:
            return replace(model, undo=model.undo.redo())
        case _:
            return model
```

Read the current value with `model.undo.current`, and gate Undo
/ Redo buttons on `model.undo.can_undo` and `model.undo.can_redo`.

## Query pipelines

`plushie.data.query` filters, searches, sorts, groups, and
paginates in-memory record collections. Operations apply in a
fixed order: filter, search, sort, paginate. Grouping applies to
the paginated page.

```python
from plushie.data import query


def filtered(model: Model) -> QueryResult:
    return query(
        model.users,
        filter_fn=lambda u: not u["archived"] if model.hide_archived else None,
        search=(["name", "email"], model.search_query) if model.search_query else None,
        sort=(model.sort_dir, model.sort_field),
        page=model.page,
        page_size=25,
    )
```

The returned `QueryResult` carries `entries` (the current page),
`total` (count before pagination), `page`, `page_size`, and
optional `groups`. Sortable column headers emit `Sort` events
from `ui.table`, or plain `Click` events with IDs like
`sort:name`; toggle direction in `update`:

```python
def update(self, model, event):
    match event:
        case Click(id=click_id) if click_id.startswith("sort:"):
            field = click_id.removeprefix("sort:")
            direction = (
                "desc"
                if model.sort_field == field and model.sort_dir == "asc"
                else "asc"
            )
            return replace(model, sort_field=field, sort_dir=direction)
        case _:
            return model
```

## Path-based state

`plushie.state.State` wraps a plain dict with revision tracking
and transactions. Useful when the model has many loosely related
fields and `dataclasses.replace` becomes noisy. `State` mutates
in place and returns `self` for chaining, so the outer model can
stay a frozen dataclass that holds the `State` as one field.

```python
from dataclasses import dataclass

from plushie.state import State


@dataclass(slots=True)
class Model:
    state: State


def init(self):
    return Model(state=State.new({"tab": "overview", "filters": {"role": None}}))


def update(self, model, event):
    match event:
        case Click(id=tid) if tid.startswith("tab:"):
            model.state.put(["tab"], tid.removeprefix("tab:"))
            return model
        case Input(id="role", value=v):
            model.state.put(["filters", "role"], v or None)
            return model
        case _:
            return model
```

`State.begin_transaction`, `State.commit_transaction`, and
`State.rollback_transaction` stage a batch of mutations and commit
or discard them atomically. `State.revision` is a monotonic
counter handy for memoization and optimistic concurrency.

## Keyed lists

`ui.keyed_column` diffs children by ID rather than by position.
Use it whenever the list changes shape at runtime (items added,
removed, reordered). Widget state attached to row-internal IDs
survives across the change:

```python
ui.keyed_column(
    *(
        ui.container(
            note.id,
            ui.row(
                ui.text_input(f"title:{note.id}", note.title),
                ui.button(f"del:{note.id}", "Delete"),
                spacing=8,
            ),
        )
        for note in model.notes
    ),
    spacing=4,
)
```

The cursor, selection, and scroll state of each `text_input`
persists across reorders because the IDs are stable. With a plain
`ui.column`, those IDs would still be stable but positional diffs
produce more wire churn on reorders.

## Memoization

`ui.memo(key, deps, body)` caches a subtree by a stable key plus
a tuple of hashable dependencies. `body` is a zero-argument
callable that is only evaluated on cache miss:

```python
ui.column(
    ui.memo(
        "header",
        (model.user_id, model.revision),
        lambda: _expensive_header(model),
    ),
    ui.text(model.dynamic_text),
)
```

Good candidates: static content that only depends on a few model
fields, long lists where the items themselves rarely change, and
expensive formatting work (markdown rendering, syntax
highlighting). The `State.revision` counter is a convenient
dependency when the subtree reads through a `State`.

Any `deps` value that supports equality works: tuples, strings,
ints, or frozen dataclasses. Avoid unhashable or non-equal types
(sets of mutable objects, `NaN`), since those defeat the cache
comparison.

## See also

- [Built-in Widgets reference](built-in-widgets.md) - widget
  catalog and prop tables
- [Windows and Layout reference](windows-and-layout.md) - sizing,
  alignment, stack, and containers
- [Events reference](events.md) - pattern matching for `Click`,
  `Input`, `Toggle`, and other event classes
- [Commands reference](commands.md) - `Command.focus`,
  `Command.send_after`, `Command.task`
- [App Lifecycle reference](app-lifecycle.md) - `init`, `update`,
  `view`, and return-shape validation
