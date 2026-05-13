# Python Typing

The `plushie` package ships a `py.typed` marker, so pyright and mypy
read inline annotations directly from the installed source. Type
checkers see frozen event dataclasses, the `App` generic over model
type, the `Length` / `Padding` / `Color` aliases in `plushie.types`,
and overloaded builders like `ui.text`, `ui.markdown`, and
`ui.progress_bar`. Widget props pass through as `**kwargs: Any`, so
kwarg names and values are not checked at author time; invalid props
surface as renderer diagnostics at runtime.

## py.typed and distribution

`src/plushie/py.typed` is the PEP 561 marker. The wheel builds with
hatchling and includes the file, so any downstream installation
inherits inline types. The project is classified `Typing :: Typed` in
`pyproject.toml` and requires Python 3.12 or newer because the SDK
uses PEP 695 syntax (`type` statements, `class App[M]`).

## The App generic

`App` in `plushie.app` is declared with PEP 695 type parameter
syntax:

```python
from abc import ABC, abstractmethod
from typing import Any

from plushie.commands import Command


class App[M](ABC):
    @abstractmethod
    def init(self) -> M | tuple[M, Command]: ...

    @abstractmethod
    def update(self, model: M, event: Any) -> M | tuple[M, Command]: ...

    @abstractmethod
    def view(self, model: M) -> dict[str, Any] | list[dict[str, Any]]: ...
```

The model type parameter `M` flows through every method, so
subclasses that bind `M` get precise `model` types in `init`,
`update`, `view`, `subscribe`, `window_config`, and
`handle_renderer_exit` without extra annotations:

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0


class Counter(plushie.App[Model]):
    def init(self) -> Model:
        return Model()

    def update(self, model: Model, event: object) -> Model:
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case _:
                return model

    def view(self, model: Model) -> dict:
        return ui.window("main", ui.text(f"Count: {model.count}"))
```

The `event` parameter is typed `Any` in the ABC. Annotate it as
`object` (or the `Event` union) in subclasses to force a match-based
dispatch; `object` works with `match` / `case` patterns and keeps
attribute access off the table.

## The Event union

`plushie.events.Event` is a PEP 695 type alias union over every
dataclass the runtime can hand to `update`:

```python
type Event = (
    ScopedWidgetEvent
    | Diagnostic
    | DiagnosticMessage
    | PaneEvent
    | KeyboardEvent
    | ImeEvent
    | WindowEvent
    | SystemEvent
    | DuplicateNodeIds
    | Announce
    | EffectResult
    | RuntimeEvent
    | SessionError
    | SessionClosed
)
```

Pattern matching narrows inside each `case` arm. The type checker
sees `Click` as `Click` once the class pattern matches, and binds
named subpatterns to the field types declared on the dataclass:

```python
from plushie.events import Click, Input, Slide

match event:
    case Click(id=widget_id):
        reveal_type(widget_id)  # str
    case Input(id="search", value=query):
        reveal_type(query)      # str
    case Slide(id="volume", value=level):
        reveal_type(level)      # float
```

### Exhaustiveness

Neither pyright nor mypy treats the union as closed automatically,
because new dataclasses land in `plushie.events` across releases.
Use a `typing.assert_never` fallthrough to make the checker flag
forgotten arms when the union grows:

```python
from typing import assert_never

from plushie.events import Click, Input


def handle(event: object) -> str:
    match event:
        case Click(id=widget_id):
            return f"click:{widget_id}"
        case Input(id=widget_id, value=value):
            return f"input:{widget_id}={value}"
        case _:
            assert_never(event)
```

`assert_never` forces the checker to prove the default arm is
unreachable. Keep a real runtime fallback (`return model`) in
application code; `assert_never` is a design-time aid, and the
runtime logs a warning when `update` returns `None` regardless.

## Typed prop values

The dataclasses and aliases in `plushie.types` are fully typed and
carry through to widget kwargs when you pass them:

| Name | Shape | Purpose |
|---|---|---|
| `Length` | `int \| float \| Literal["fill", "shrink"] \| dict[str, int]` | Widget size value |
| `Padding` | number, 2-tuple, 4-tuple, or dict | Padding spec |
| `Color` | `str` | Canonical hex color string |
| `FontWeight`, `FontStyle`, `FontStretch` | `Literal[...]` | Font axis values |
| `AlignX`, `AlignY`, `Alignment` | `Literal[...]` | Alignment values |
| `TextDirection` | `Literal["auto", "ltr", "rtl"]` | Direction hint for `text`, `text_input`, and `text_editor` |
| `Ellipsis` | `Literal["none", "start", "middle", "end"]` | Closed text truncation modes |
| `A11yRole`, `A11yLive`, `A11yHasPopup` | `Literal[...]` | Accessibility enums |
| `Border`, `Shadow`, `Gradient`, `Font`, `StyleMap`, `A11y`, `Span` | frozen dataclasses | Structured style / a11y values |

Color is a plain `str` alias, so the checker will not complain about
arbitrary strings passed where a color is expected. `Colors.cast`
normalises at runtime and raises `ValueError` on bad input.

Widget builder signatures in `plushie.ui` declare kwargs as
`**kwargs: Any`, so the type checker does not validate prop names or
values at the call site. Positional args (id, content, label, value)
are typed precisely.

## TypedDict for structured props

When you pass a dict to a kwarg that the renderer treats as a
structured value (table columns, rich-text spans, menu entries, pane
splits), wrap it in a `TypedDict` to get checker help:

```python
from typing import Literal, NotRequired, TypedDict

from plushie import ui


class Column(TypedDict):
    key: str
    header: str
    width: NotRequired[int]
    align: NotRequired[Literal["left", "center", "right"]]


columns: list[Column] = [
    {"key": "name", "header": "Name"},
    {"key": "email", "header": "Email", "width": 240},
]

ui.table("users", columns=columns, rows=rows)
```

The `TypedDict` does not constrain the widget builder itself (the
kwarg is still `Any`), but it forces the caller to build the dict
correctly. Use `NotRequired` from `typing` (Python 3.11+) for
optional keys, and `Literal` for enumerated values.

## Protocol for callbacks

`Command.task` and `Command.stream` take plain callables:

```python
@staticmethod
def task(fn: Callable[[], Any], tag: str) -> Command: ...

@staticmethod
def stream(fn: Callable[[Callable[[Any], None]], Any], tag: str) -> Command: ...
```

When a helper wants a more specific signature, use `Protocol` for
structural subtyping:

```python
from typing import Protocol

from plushie import Command


class Fetcher[T](Protocol):
    def __call__(self) -> T: ...


def fetch_cmd[T](fetcher: Fetcher[T], tag: str) -> Command:
    return Command.task(fetcher, tag)
```

Any zero-argument callable that returns `T` satisfies `Fetcher[T]`,
including functions, bound methods, `functools.partial` instances,
and callable class instances. The result still arrives as
`AsyncResult(tag=tag, value=...)`, where `value` is `Any`; cast or
`isinstance`-check at the receiving end if you want narrowing.

## Frozen dataclasses for models

Models are conventionally `frozen=True, slots=True` dataclasses with
tuple collections:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Item:
    id: str
    text: str
    done: bool = False


@dataclass(frozen=True, slots=True)
class Model:
    items: tuple[Item, ...] = ()
    filter: str = "all"
```

`frozen=True` makes mutation raise `FrozenInstanceError` at runtime
and makes the instance hashable. `slots=True` drops the per-instance
`__dict__`, which saves memory and catches typos in field access.
Update state with `dataclasses.replace`:

```python
from dataclasses import replace

new_model = replace(model, filter="active")
```

The checker infers the result type as `Model`. `replace` rejects
unknown field names at runtime, but not at check time; relying on
field names to match is your job.

## Overload resolution

`ui.text`, `ui.markdown`, and `ui.progress_bar` use `@overload` to
express the auto-id vs explicit-id signatures. The runtime
implementation accepts `*args: Any`, but the checker sees the
overloads:

```python
from typing import Any, overload


@overload
def text(content: str, /, **kwargs: Any) -> Node: ...
@overload
def text(id: str, content: str, /, **kwargs: Any) -> Node: ...
def text(*args: Any, **kwargs: Any) -> Node: ...
```

Both arities resolve to `Node`, so call sites read naturally:

```python
ui.text("Hello")                   # auto-id form
ui.text("greeting", "Hello")       # explicit id form
ui.progress_bar((0.0, 100.0), 42.0)
ui.progress_bar("load", (0.0, 100.0), 42.0)
```

The `/` marker makes id and content positional-only, so keyword
forms like `ui.text(id="x", content="y")` do not compile. Stick with
positional.

## pyright and mypy

Both checkers are supported. The project ships a pyright config in
`pyproject.toml`:

```toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
venvPath = "."
venv = ".venv"
include = ["src", "tests", "examples"]
exclude = ["**/__pycache__"]
```

Standard mode flags obvious mistakes without the churn of strict
mode on dynamic kwarg-heavy code. Move to `strict` when your own
code is ready; expect `reportUnknownArgumentType` noise on widget
builders because props flow through as `Any`. Silence those with
narrow suppressions rather than turning the rule off globally.

For mypy, enable inference-friendly flags without `--strict`:

```toml
[tool.mypy]
python_version = "3.12"
warn_unused_ignores = true
warn_redundant_casts = true
check_untyped_defs = true
```

Both checkers understand PEP 695 type parameter syntax on 3.12; mypy
needs a recent release (1.11+) for full support.

## Stub gaps to be aware of

A few places pass through as `Any` by design:

- Widget kwargs: `ui.button(id, label, **kwargs: Any)` accepts any
  prop name. Wrong names reach the renderer and come back as
  `Diagnostic` events at runtime.
- Event payload escapes: `EffectResult.result` and a few `data`
  fields are typed loosely so new effect shapes do not break
  existing signatures. Match on the inner class to narrow.
- `Command.payload` is `dict[str, Any]`. Use the `Command.*` factory
  methods; never construct the dataclass directly.
- `App.update` takes `event: Any`. Override the signature in your
  subclass with `event: object` or `event: Event` to enforce pattern
  matching.
- Decorator-based apps (`create_app`) erase the model type. The
  builder stores callbacks as `Any`, so the decorator form is best
  for small scripts and prototypes; reach for `App[Model]` when you
  want type coverage.

When you want prop checking on a specific widget, wrap the builder:

```python
from typing import NotRequired, TypedDict

from plushie import ui


class ButtonProps(TypedDict):
    width: NotRequired[int]
    on_press: NotRequired[str]


def save_button(label: str, **props: ButtonProps) -> dict:
    return ui.button("save", label, **props)
```

The wrapper confines the untyped surface to a single call site and
pushes type checking out to callers.

## See also

- [App Lifecycle](app-lifecycle.md)
- [Events](events.md)
- [Commands](commands.md)
- [Composition Patterns](composition-patterns.md)
- [Testing](testing.md)
