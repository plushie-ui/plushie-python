# State Management

The pad has grown. Each feature added fields to the model and
branches to `update`. At some point the recurring patterns start
to feel like they deserve names: tracking selection, undoing an
edit, drilling into a detail view, searching a list.

Plushie ships those patterns as standalone helpers in
`plushie.state`, `plushie.selection`, `plushie.undo`,
`plushie.route`, and `plushie.data`. Each is a pure data
structure. No threads, no callbacks, no runtime coupling. You
store one in a model field and update it in `update` the same
way you update any other field. They compose freely.

This chapter adds four features to the pad: multi-select in the
sidebar, undo / redo for editor edits, a search box over the
experiment list, and a route stack that drills into a detail
view. The [Composition Patterns reference](../reference/composition-patterns.md)
documents each helper in depth.

## Selection: multi-select the sidebar

`plushie.selection.Selection` tracks which items in a list are
selected. Construct it with `Selection.new(mode=...)`. The mode
is `"single"`, `"multi"`, or `"range"`. All mutating methods
return a new `Selection`.

```python
from plushie.selection import Selection

sel = Selection.new(mode="multi")
sel = sel.toggle("alpha").toggle("beta")
sel.selected()           # frozenset({"alpha", "beta"})
sel.is_selected("alpha") # True
sel.clear().selected()   # frozenset()
```

`toggle(id)` adds if absent, removes if present. `select(id,
extend=True)` adds without removing. `select_all()` selects
everything in the `order` tuple passed at construction. In
`"single"` mode, selecting a new item replaces the previous one.
`range_select(id)` uses the anchor plus `order` to select a
contiguous slice.

The pad sidebar currently highlights one experiment. Add a
checkbox per row to pick several and batch-delete or
batch-rename. Model fields grow by one:

```python
from plushie.selection import Selection


@dataclass(frozen=True, slots=True)
class Model:
    experiments: tuple[Experiment, ...] = ()
    active: str | None = None
    selection: Selection = Selection.new(mode="multi")
```

Wire the checkbox toggle and two bulk actions into `update`:

```python
from dataclasses import replace

from plushie.events import Click, Toggle


case Toggle(id=tid, value=_) if tid.startswith("select:"):
    exp_id = tid.removeprefix("select:")
    return replace(model, selection=model.selection.toggle(exp_id))

case Click(id="delete_selected"):
    chosen = model.selection.selected()
    kept = tuple(e for e in model.experiments if e.id not in chosen)
    return replace(model, experiments=kept, selection=model.selection.clear())

case Click(id="rename_selected"):
    chosen = model.selection.selected()
    renamed = tuple(
        replace(e, name=e.name + " (batch)") if e.id in chosen else e
        for e in model.experiments
    )
    return replace(model, experiments=renamed)
```

The sidebar view gains a checkbox per row and a footer with
the bulk actions, gated on whether anything is selected. The
search section below shows the full view once query is wired in.

`selected()` returns a `frozenset`, so `len(...)` gives the
count for button labels. `is_selected(id)` is the predicate for
views.

## Undo / redo: editor source edits

`plushie.undo.UndoStack` pairs an initial value with a pair of
stacks. `UndoCommand(apply_fn, undo_fn, label=...)` describes a
reversible change. `apply_command(cmd)` runs `apply_fn` on the
current value and pushes an entry; `undo()` pops it and runs
`undo_fn`; `redo()` pushes it back and runs `apply_fn` again.

```python
from plushie.undo import UndoCommand, UndoStack

u = UndoStack.new("")
u = u.apply_command(UndoCommand(
    apply_fn=lambda _old: "hello",
    undo_fn=lambda _new: "",
    label="type hello",
))
u.current       # "hello"
u = u.undo()
u.current       # ""
u = u.redo()
u.current       # "hello"
```

The value lives in `u.current`. `u.history()` returns labels of
the undo stack, most recent first, for a history panel.

### Coalescing rapid keystrokes

Typing a word fires one `Input` event per keystroke. Without
coalescing, one Ctrl+Z undoes a single character. `UndoCommand`
takes a `coalesce` key plus a `coalesce_window_ms` window.
Commands with the same key that arrive within the window merge
into the top entry. The merged entry keeps the original
`undo_fn`, so one Ctrl+Z reverses the full burst.

```python
UndoCommand(
    apply_fn=lambda _old: new_source,
    undo_fn=lambda _new: old_source,
    coalesce="editor_typing",
    coalesce_window_ms=500,
    label="edit source",
)
```

### Wiring undo into the pad

Store the editor source inside the undo stack instead of a bare
string. The model shrinks by one field and gains one:

```python
@dataclass(frozen=True, slots=True)
class Model:
    experiments: tuple[Experiment, ...] = ()
    editor: UndoStack = UndoStack.new("")
    selection: Selection = Selection.new(mode="multi")
```

`Input` on the editor pushes a coalesced undo entry. Ctrl+Z and
Ctrl+Shift+Z are handled through `KeyEvent` from the subscription
you added in [chapter 10](10-subscriptions.md):

```python
from plushie.events import Input, KeyEvent


case Input(id="editor", value=new_source):
    old_source = model.editor.current
    cmd = UndoCommand(
        apply_fn=lambda _old, _v=new_source: _v,
        undo_fn=lambda _new, _o=old_source: _o,
        coalesce="editor_typing",
        coalesce_window_ms=500,
        label="edit source",
    )
    return replace(model, editor=model.editor.apply_command(cmd))

case KeyEvent(type="press", key="z", modifiers=mods) if mods.command and not mods.shift:
    return replace(model, editor=model.editor.undo())

case KeyEvent(type="press", key="z", modifiers=mods) if mods.command and mods.shift:
    return replace(model, editor=model.editor.redo())
```

Read the editor body from `model.editor.current`. Gate toolbar
buttons on `model.editor.can_undo` and `model.editor.can_redo`.
The default-bound closures `_v=new_source` and `_o=old_source`
matter: without them the lambdas close over the names and every
undo entry would capture the last values `update` saw.

## Route: drill into experiment detail

`plushie.route.Route` is a last-in-first-out navigation stack.
Each entry pairs a path with a params dict. `Route.new(initial_path)`
makes a single-entry stack. `push(path, params)` adds on top.
`pop()` removes the top, or returns the route unchanged if only
one entry remains (the root never pops). `replace_top(path,
params)` swaps the top entry without growing the stack.

```python
from plushie.route import Route

r = Route.new("list")
r = r.push("detail", {"id": "alpha"})
r.current()      # "detail"
r.params()       # {"id": "alpha"}
r.can_go_back    # True
r.depth          # 2
r = r.pop()
r.current()      # "list"
```

Clicking an experiment pushes a detail route with the ID in
params. Back pops. The top-level view switches on
`route.current()`:

```python
case Click(id=click_id) if click_id.startswith("open:"):
    exp_id = click_id.removeprefix("open:")
    return replace(model, route=model.route.push("detail", {"id": exp_id}))

case Click(id="back"):
    return replace(model, route=model.route.pop())


def view(self, model: Model) -> dict[str, Any]:
    match model.route.current():
        case "detail":
            exp_id = model.route.params()["id"]
            exp = next(e for e in model.experiments if e.id == exp_id)
            return detail_view(model, exp)
        case _:
            return list_view(model)
```

Add a `route: Route = Route.new("list")` field to the model.

`replace_top` is useful when the detail view has tabs: swap
params without growing the back stack.

## Data: search over the experiment list

`plushie.data.query` runs a filter / search / sort / paginate /
group pipeline over a list of dicts.

```python
from plushie.data import query

result = query(
    [{"name": "Alice", "role": "dev"}, {"name": "Bob", "role": "design"}],
    search=(["name", "role"], "dev"),
    sort=("asc", "name"),
)
result.entries   # matching dicts
result.total     # count before pagination
```

Arguments are all keyword-only:

| Argument | Type | Description |
|---|---|---|
| `filter_fn` | `(dict) -> bool` | Predicate run before search |
| `search` | `(fields, query)` | Case-insensitive substring match across listed fields |
| `sort` | `(direction, field)` or list | Direction is `"asc"` or `"desc"` |
| `group` | `str` | Dict key to group paginated entries by |
| `page` | `int` | 1-based page number (default 1) |
| `page_size` | `int` | Records per page (default 25) |

`query` takes `list[dict[str, Any]]`. Experiment records are
frozen dataclasses, so feed dicts derived from them:

```python
from plushie.data import query
from plushie.events import Input


case Input(id="search", value=q):
    return replace(model, search_query=q)


def sidebar(model: Model) -> dict[str, Any]:
    records = [
        {"id": e.id, "name": e.name, "tags": " ".join(e.tags)}
        for e in model.experiments
    ]
    visible = (
        query(
            records,
            search=(["name", "tags"], model.search_query),
            sort=("asc", "name"),
        ).entries
        if model.search_query
        else records
    )
    rows = [
        ui.row(
            ui.checkbox(f"select:{r['id']}", model.selection.is_selected(r["id"])),
            ui.button(f"open:{r['id']}", r["name"]),
            spacing=8,
        )
        for r in visible
    ]
    return ui.column(
        ui.text_input("search", model.search_query, placeholder="Search..."),
        *rows,
        padding=12,
        spacing=4,
    )
```

Selection stays keyed by experiment ID, so hidden rows remain
selected and clearing the query restores their checkboxes.

## State: grouped edits with transactions

`plushie.state.State` wraps a dict with path-based access and a
monotonically increasing revision counter. Every `put`, `update`,
or `delete` bumps the revision. `State` is mutable on purpose:
transactions wrap multiple mutations in a snapshot that can be
rolled back, and the revision counter lets views cheaply detect
change.

```python
from plushie.state import State

s = State.new({"settings": {"theme": "dark", "font_size": 14}})
s.get(["settings", "theme"])  # "dark"
s.revision                     # 0

s.put(["settings", "font_size"], 16)
s.update(["settings", "font_size"], lambda n: n + 2)
s.revision                     # 2
```

`get(path)` returns the value at the path; `get([])` returns
the whole data dict. `put(path, value)` sets; `update(path, fn)`
applies a function to the current value; `delete(path)` removes
the key.

Transactions group multiple mutations into one revision bump:

```python
s.begin_transaction()
s.put(["settings", "theme"], "light")
s.put(["settings", "font_size"], 18)
s.commit_transaction()   # revision increments once from its pre-transaction value
```

`rollback_transaction()` restores the data and revision to their
pre-transaction snapshot. `begin_transaction` while another
transaction is active raises `RuntimeError`; so do `commit` and
`rollback` with no active transaction.

Because `State` is mutable, the outer model holds it as a field
and does not need `replace(model, state=...)` for mutations.
Call methods on `model.state` directly:

```python
case Click(id="apply_theme_preset"):
    model.state.begin_transaction()
    model.state.put(["settings", "theme"], "nord")
    model.state.put(["settings", "font_size"], 13)
    model.state.put(["settings", "line_height"], 1.5)
    model.state.commit_transaction()
    return model
```

Use a non-frozen dataclass (`@dataclass(slots=True)`) for the
outer model when it holds a `State` field.

Treat `State` as the container for ambient preferences and
settings that live in deep nested dicts. Keep the experiments
list, selection, undo, and route as fields on the frozen model.
The pad can hold all of the above side by side; the helpers do
not touch each other. `examples/notes.py` in the repo combines
the same set in a smaller app.

## Verify it

Drive the new behaviour through the test fixture:

```python
def test_multi_delete(app):
    app.click("select:alpha")
    app.click("select:beta")
    app.click("delete_selected")
    assert [e.id for e in app.model.experiments] == ["gamma"]


def test_undo_redo_editor(app):
    app.type_text("editor", "hello")
    app.press("cmd+z")
    assert app.model.editor.current == ""
    app.press("cmd+shift+z")
    assert app.model.editor.current == "hello"


def test_route_back(app):
    app.click("open:alpha")
    assert app.model.route.current() == "detail"
    app.click("back")
    assert app.model.route.current() == "list"
```

All three run against the real renderer and exercise the full
update cycle: widget event, model change, tree diff, patch. The
helpers are ordinary data structures, so nothing needs mocking.

## Try it

- Add a "Select all visible" button using `select_all()` on a
  `Selection` constructed with the filtered IDs as `order=`.
- Show undo history in a dropdown using `model.editor.history()`.
  Clicking an entry calls `undo()` until that label is on top of
  the redo stack.
- Add tabs inside the detail view using `replace_top` to swap
  `{"tab": "source"}` and `{"tab": "runs"}` without growing the
  back stack.
- Sort search results by a chosen column. Store the sort tuple
  in `state.put(["ui", "sort"], ("desc", "name"))` and read it
  back when building the `query` call.

In the next chapter we turn to testing the pad: what the fixture
does, what the pool does, and how to structure a suite around
real rendering.

---

Next: [Testing](15-testing.md)
