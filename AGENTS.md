# plushie-python

This file is not version controlled. Do not reference it in commit
messages, pull requests, or documentation.

Python SDK for the plushie desktop GUI renderer. Communicates with
a Rust binary (plushie) over stdin/stdout using MessagePack (default)
or JSONL. Implements the Elm architecture (init/update/view) with
commands, subscriptions, and tree diffing.

This is a sister project to plushie-elixir, not a port. The wire
protocol is identical. The API is designed for Python developers,
following Python conventions, using Python's type system and
concurrency model.

## Stewardship

Direction, trust posture, goals, and explicit non-goals are captured
in `docs/stewardship/`. That directory is the authority on what work
the project takes on and what it declines. The summary below is enough
for routine work; pull the relevant doc when an axis is in play. Use
`docs/stewardship/triage.md` as the routing tool when the answer is
not self-evident.

Pre-1.0: no backcompat, right design wins, rename across SDKs is fine.
Post-1.0: stability obligations begin (Hyrum's Law). plushie-rust =
protocol authority. plushie-elixir = canonical API-shape reference;
plushie-python follows it on contested questions. Rename here = six-
SDK change. Cross-SDK parity audited in sibling `plushie-sdk-parity/`.
PyPI package is a library, never auto-starts a runtime.

### Disciplines (non-negotiable)

Tests through real renderer; cross-SDK claims verified by reading
source on each side; design before code at boundaries (public API,
`ui` builders, wire codec, App ABC, fixture contract); type checker
is part of the build (pyright in preflight, type errors are bugs);
clarity is the bar; no half-built features; local cleanup not scope
creep; no legacy shims pre-1.0.

### Goals

Wire codec fidelity on host side; cross-SDK concept parity (semantics
converge, syntax diverges per language); Elm-architecture purity
(`init/update/view`, return-shape validation, commands as pure data,
pure view, declarative subs, no `async`/`await` in user code);
lightweight runtime (no idle work, no polling, no asyncio overhead);
fault tolerance (renderer crash auto-recovers + state re-syncs, app
exception reverts to last good model, view-error tracking, neither
side takes the other down); type-checker support is real (precise
public types, `App[M]`, `@overload`, `tuple` over `list`, `Any` is a
smell).

### Non-goals (declined, not deprioritized)

Backcompat before 1.0; per-Python API ergonomics that diverge from
cross-SDK shape ("more Pythonic" alone is not justification); API
stability hardening pre-1.0 (single 1.0 sweep, not piecemeal);
coverage targets as a metric; mocking renderer for speed; asyncio in
user code (Elm loop is sync; `Command.task` covers async work);
micro-optimization at cost of readability; refactoring without a
forcing function; DSL extensions for hypothetical future widgets;
defending against speculative deployment shapes.

### Trust model

Asymmetric. Renderer-to-host = closed and typed; host structurally
protected today (typed event decoding via `decode_message`, unknowns
become `RawEvent` not opaque blobs, effect/query response correlation
by request ID, no host-side eval/exec/getattr based on renderer-
supplied data, strict whitelists for enums). Host-to-renderer = broad
by design (file paths, fonts, images, screenshots, effects, structured
renderer exec args); bounding it is the capability-manifest roadmap in
plushie-rust. Wire = byte-stream agnostic; confidentiality + integrity
delegated to outer transport (`IoStreamAdapter`, `SocketAdapter`).
Same-access (user
attacking themselves) out of scope.

### Resilience

Things-go-wrong axis, not adversary axis. App exception revert in
`init/update/view`/`subscribe`/`window_config`; view-error tracking
with frozen-UI overlay after warn threshold; renderer crash auto-
recovery via reader-thread detection + exponential backoff (100ms,
200ms, 400ms, 800ms, 1600ms) + fresh snapshot re-sync;
`handle_renderer_exit` callback can adjust model before re-sync;
`RecoveryFailed` event when attempts exhausted; daemon mode keeps
runtime alive across reconnects. Async task isolation in executor
with per-task nonces (stale results dropped). Defensive parsing
(`RawEvent` for unknown families, typed errors for malformed). Return-
shape validation in `unwrap_result` raises `TypeError` immediately;
None-return from `update` (Python footgun) is detected, logged with
event, previous model kept. Coalescable high-frequency events. Fail-
fast on programming-error invariant violations and unrecoverable
binary resolution.

### Performance

Lightweight = baseline, not optimization-after-fact. Don't do
unnecessary work in the first place; cost compounds. Worth doing
without benchmark (readability preserved/improved): consolidate
redundant traversals, right data structure (`dict` lookup over linear
scan when N large, `frozenset` for membership, `tuple` over `list`
for immutable), avoid unnecessary comprehensions/copies, move per-
frame work that doesn't depend on per-frame inputs to the edge. Need
benchmark first (readability cost real): clever encoding, big-O
without realistic N, optimization on idle paths, C-extension reaches
where pure Python with better algorithm would do. GIL realism: real
parallelism is in the renderer process; CPU-bound user work in
`Command.task` does not benefit from the executor. Numeric direction:
16.67ms frame budget at a few hundred to ~1000 nodes; idle CPU = no
measurable work; tree diff is the load-bearing piece.

### Test discipline

Integration spine: tests exercise real renderer (default `mock`
backend = real binary, real wire, real Core, no GPU). Three modes
(cross-SDK contract): mock (default, fastest), headless (tiny-skia,
pixels), windowed (full iced, real display). Pooled mock backend
multiplexes via `--max-sessions N`; `pytest_plushie` plugin provides
session-scoped `plushie_pool` fixture. Stubs acceptable only for
forced crash sim, malformed wire bytes, direct `update` shape tests,
test infra. `AppFixture` runs `update`/`view` synchronously; public
API only (`click`, `type_text`, `submit`, `toggle`, `select`, `find`,
`text`, `model`, `assert_*`); no peeking at private threads/queues/
executor. `pyright`/`ruff`/`interrogate` in preflight, errors are
bugs. Tests as documentation; slow tests = slow code; failing test
before fix.

### Simplicity

Clarity = constraint, not aspiration. Reader-cost compounds.
Readability wins ties. Abstraction earns its place: 3 similar lines
> premature abstraction; 3rd use earns consideration not commitment;
single-user abstraction = costume; "we might need this someday" =
reason not to extract. Local complexity > global. Cohesion across
file > brevity of any one file. Functional flavor inside Python
idioms: pure where possible, frozen dataclasses with slots,
`replace()` over mutation, `tuple` over `list`, pattern matching over
branching, one dataclass per event family (precise types over `Any`),
errors as values where they fit, composition over inheritance.
Comments answer why-not-what; docstrings on public surface
(`interrogate`-enforced). `# type: ignore` is a smell; fix the
underlying type.

### Elm invariants

`init`, `update` return: bare model | `(model, Command)` |
`(model, [Command])`. Anything else raises `TypeError` from
`unwrap_result`. None-return from `update` (no `match` fallthrough)
is detected: keep previous model, log warning. Commands are pure data
(`@dataclass(frozen=True, slots=True)`); runtime executes. `Command.task`
not `Command.async` (Python reserved word) is the one cross-SDK
shape deviation. `view` is pure function of model; top level must be
window node(s); tree is plain dicts in wire-format shape. Subs
declarative; runtime diffs each cycle. Widget event flow walks scope
chain; `handle_event` returns `EventAction.ignored/consumed/
update_state/emit`. Canvas-internal events auto-consumed if not
captured. Wire IDs: `window#scope/path/id`; events split into
`id`/`scope`/`window_id`; commands use forward-order path strings.

### DSL discipline (Python flavor)

User-facing surface: `plushie.ui` builder functions returning dicts;
`plushie.events` one frozen dataclass per event family; `plushie.commands`/
`plushie.subscriptions` factory methods; `plushie.types` shared value
types; `plushie.App` ABC + `create_app` decorator factory. Container
builders: children as `*args`, options as keyword-only kwargs. Named
containers: id-first positional. Anonymous (column/row/stack): no
positional id. Leaf widgets: id-first interactive, auto-id sugar
display. `@overload` for multi-signature builders; positional-only
markers (`/`) pin id/content. New pattern earns its place when:
cross-SDK answer is yes, 2+ real users, real bug class, reads as
cleanly as hand-written, type checker stays precise, errors point at
call site. Decline: "we could check this with `Literal`," "more
Pythonic," "fewer characters." Type precision is part of the API; a
change that broadens to `Any` or drops a `Generic` is suspect.

### Concurrency shape

Connection owns subprocess + wire framing; Runtime owns app loop +
model + tree. Communication via thread-safe `queue.Queue`. Threads:
runtime thread (owns model state, sole caller of `update`/`view`),
reader thread (decodes wire, posts events), `ThreadPoolExecutor` for
`Command.task` with per-task nonces, `threading.Timer` for
`Subscription.every`/`send_after`/effect timeouts. `runtime.inject` is
thread-safe for external callers. No asyncio in runtime: hot path is
sync CPU-bound work, embedding is easier with sync, GIL serializes
anyway, renderer process is where parallelism lives. No
multiprocessing, no `threading.Condition`, no daemon thread for
runtime loop, no global registry, no signal handlers in library code.
Reconnect: cancel pending effects (typed error), call
`handle_renderer_exit`, exponential backoff, replay settings + fresh
snapshot + re-subscribe + re-open windows. Test session pool wraps
production `Connection`; windowed mode does not pool.

### Common shapes -> outcomes

- "mock the renderer for speed" -> decline
- "let `update` be `async def`" -> decline; cross-SDK answer is no
- "asyncio-native runtime" -> decline; stewardship-level no
- "add deprecation warnings / API hardening" -> decline; 1.0 sweep
- "this is O(n) on a hot path" -> need realistic N
- "split this large module" -> need forcing function
- "harden against malicious renderer" -> structurally protected;
  check if proposal loosens that, otherwise misframed
- "harden against malicious host" -> defer to capability-manifest
  (plushie-rust roadmap)
- "wire should encrypt / sign" -> outer transport's job
- "consolidate N redundant traversals" -> do
- "extract this single-use Protocol/ABC" -> decline; costume
- "this exception should propagate up" -> usually no; revert + log
- "let users return None from update for no-change" -> no, bare model
  is the no-change shape; None is the footgun the runtime detects
- "rename field across SDKs" -> route through parity workflow
- "broaden this parameter to `Any` so pyright passes" -> fix the
  type, don't loosen the signature
- "add new `ui` builder for X" -> run dsl-discipline criteria; default
  no unless cross-SDK answer is yes

## Before committing

Run `just preflight`. It mirrors CI: ruff format check, ruff lint,
interrogate, pyright, pytest.

`just preflight` syncs deps and runs `./bin/preflight`. The renderer
source is controlled by `PLUSHIE_RUST_SOURCE_PATH`:

- Unset (default): auto-detected from `../plushie-rust` if it exists;
  otherwise the existing binary resolution chain is used unchanged.
- Set to a path: plushie-renderer is rebuilt from that checkout via
  `cargo build --release -p plushie-renderer` and `PLUSHIE_BINARY_PATH`
  is exported so all subsequent steps use the fresh binary. Guarantees
  tests run against current source rather than a stale artifact.
- Set to `""`: suppresses auto-detection; uses the existing binary
  resolution chain (PLUSHIE_BINARY_PATH, downloaded binary, etc.).

## Commit hygiene

Every commit should be self-contained and functional. Preflight
should pass at each commit, not just at the tip.

Commits after `origin/main` are unpublished and can be freely
amended, squashed, or reordered to keep the history clean. Run
`git fetch origin` first to ensure the boundary is current. Use
`--amend` to fold small fixes into the commit they belong to
rather than creating "fix the fix" commits. If a later commit
fixes a bug introduced by an earlier unpublished commit, squash
them together.

Never amend or rebase commits that are already on `origin/main`.

## Commit messages

Commit messages should describe what changed and why. Do not include:
- Counts of any kind (findings, files, tests, items). If the
  content is listed, the reader can count. Counts add noise.
- Ticket, review, or tracking IDs (R-001, PROJ-123, etc.)
- References to this file

More broadly, think carefully before including counts anywhere
(code comments, docs, log messages). If the count is derivable
from the surrounding content, it doesn't add value.

## Writing style

Do not use `--` (double dash) as a separator or em-dash substitute
in prose, docs, comments, or bullet lists. Use a single `-` for
list item separators and reword sentences to avoid inline dashes
(use commas, periods, colons, or parentheses instead). `--` should
only appear as part of CLI flag names (e.g. `--watch`, `--release`).

## Quick reference

```
just preflight                                           # run all CI checks locally
PLUSHIE_RUST_SOURCE_PATH=../plushie-rust just preflight  # explicit renderer source (rebuilds from checkout)
PLUSHIE_RUST_SOURCE_PATH="" just preflight               # force non-local (use downloaded binary)
just test                              # run tests (mock backend)
just fmt                               # auto-format
just fmt-check                         # check formatting (CI mode)
just lint                              # ruff check
just typecheck                         # pyright
just clean                             # remove gitignored build artifacts
ruff format src tests examples         # auto-format
ruff format --check src tests examples # check formatting (CI mode)
ruff check src tests examples          # lint
pyright src                            # type checking
pytest                                 # run tests (mock backend)
PLUSHIE_TEST_BACKEND=headless pytest   # real rendering, no display
PLUSHIE_TEST_BACKEND=windowed pytest   # real windows (needs display)
python -m plushie run myapp:Counter    # run a plushie app
python -m plushie connect myapp:App    # connect mode (stdio transport)
python -m plushie download             # download precompiled binary
python -m plushie download --wasm      # download WASM renderer
python -m plushie build                # build with extensions
python -m plushie build --wasm         # build WASM renderer from source
python -m plushie inspect myapp:App    # print UI tree as JSON
python -m plushie script tests/*.plushie  # run test scripts
python -m plushie replay test.plushie  # replay script with real windows
```

## Configuration

Environment variables:
- `PLUSHIE_BINARY_PATH`: path to the renderer binary (overrides all)
- `PLUSHIE_RUST_SOURCE_PATH`: path to the plushie-rust source checkout
- `PLUSHIE_TEST_BACKEND`: test backend: `mock` (default), `headless`, `windowed`

pyproject.toml `[tool.plushie]` keys:
- `artifacts`: list of what to download/build: `["bin"]` (default), `["wasm"]`, or `["bin", "wasm"]`
- `bin_file`: override native binary destination
- `wasm_dir`: override WASM output directory (e.g. `"static"` for web apps)
- `source_path`: Rust source checkout (alternative to env var)
- `build_name`: custom binary name (default `"plushie-custom"`)
- `extensions`: native extension definitions (TOML array of tables)

Resolution order: CLI flags > pyproject.toml > env vars > defaults.

## Project layout

```
src/
  plushie/
    __init__.py                # top-level API: App, run, start, Event, Node
    __main__.py                # CLI: python -m plushie
    py.typed                   # PEP 561 typed package marker

    # Layer 0: Wire protocol (no I/O, pure data transformation)
    protocol.py                # encode/decode all wire message types
    framing.py                 # JSON (newline-delimited) and MessagePack (4-byte length prefix)
    events.py                  # all event dataclasses (one per event family)

    # Layer 1: Connection (subprocess management, send/receive)
    connection.py              # Connection class: renderer process lifecycle
    transport.py               # IoStreamAdapter, WebSocketAdapter for custom transports
    binary.py                  # binary resolution, download (native + WASM), platform detection

    # Layer 2: App framework (Elm architecture)
    app.py                     # App ABC (init/update/view/subscribe/settings/window_config)
    runtime.py                 # event loop: update/view/diff cycle, commands, subscriptions
    commands.py                # Command dataclass + factory methods
    subscriptions.py           # Subscription specs + diffing
    effects.py                 # platform effects (file dialogs, clipboard, notifications)

    # UI
    ui.py                      # widget builder functions (returns plain dicts)
    tree.py                    # normalize, diff (4 patch ops), find, search, prop encoding
    types.py                   # Length, Padding, Color, Font, Border, Shadow, StyleMap, A11y
    canvas.py                  # canvas shape builders
    keys.py                    # key name constants matching wire protocol values

    # Custom widgets
    widget.py                  # WidgetDef base class, WidgetRegistry, event dispatch model
    canvas_widget.py           # backwards-compat re-exports from widget.py (CanvasWidgetDef alias)
    native_widget.py           # NativeWidget definitions for Rust-backed custom widget types

    # State helpers (pure data, no runtime dependency)
    data.py                    # query pipeline: filter, search, sort, group, paginate
    selection.py               # Selection state for lists/tables (single, multi, range)
    state.py                   # path-based state management with revision tracking
    route.py                   # client-side routing (navigation stack)
    undo.py                    # undo/redo stack with coalescing

    # Animation
    animation/
      __init__.py              # re-exports Transition, Spring, Sequence, Tween
      transition.py            # renderer-side timed transition descriptor
      spring.py                # renderer-side physics-based spring descriptor
      sequence.py              # renderer-side sequential animation chain
      tween.py                 # SDK-side stateful interpolator (frame-by-frame control)
      easing.py                # easing functions (named curves + cubic_bezier)

    # Dev tooling
    dev_server.py              # file watcher for live reload during development
    script.py                  # .plushie test script parser and runner

    # Testing
    testing/
      __init__.py              # re-exports AppFixture
      fixture.py               # AppFixture: pytest-native test driver
      pool.py                  # SessionPool: shared renderer for test parallelism
      plugin.py                # pytest plugin: auto pool lifecycle
      element.py               # Element wrapper for renderer query node dicts

examples/
  counter.py                   # basic counter (Elm architecture intro)
  todo.py                      # todo list (list management, text input)
  clock.py                     # subscriptions and timer events
  async_fetch.py               # Command.task for background work
  catalog.py                   # widget catalog showcase
  color_picker.py              # HSV color picker using a canvas widget
  notes.py                     # state helpers composition (State, Undo, Selection, Route, query)
  rate_plushie.py              # custom canvas widgets with styled containers
  shortcuts.py                 # keyboard event logging with scrollable log
  widgets/
    star_rating.py             # canvas-based star rating widget
    color_picker_widget.py     # canvas-based HSV color picker widget
    theme_toggle.py            # animated theme toggle with drawn face
tests/
```

## Architecture

### Layered design

The SDK has four layers. Each layer depends only on the layers
below it. Each is independently useful.

**Layer 0: Protocol.** Pure functions. No I/O. Encodes Python
dicts into wire messages (MessagePack or JSON with framing).
Decodes wire bytes into event dataclasses. This layer has one
dependency: `msgpack`.

**Layer 1: Connection.** Manages a renderer subprocess (or
stdin/stdout in connect mode). Provides send/receive with
request/response correlation. Handles the hello handshake.
Usable directly for power users, automation, or alternative
programming models.

**Layer 2: App framework.** The Elm architecture: `init`,
`update`, `view`, `subscribe`. The Runtime class runs the event
loop on a dedicated thread. Tree diffing sends patches. Commands
execute async work. Subscriptions register with the renderer.
This is what most users interact with.

**Layer 3: Testing.** A pytest fixture (`AppFixture`) that
drives apps through the real renderer binary. Session pool for
test parallelism. All interactions go through the wire protocol.
No Python-side mocks or stubs.

### Elm architecture

- `init()` returns the initial model (optionally with commands).
- `update(model, event)` returns the new model (optionally with
  commands). Pure function of model + event.
- `view(model)` returns a UI tree as a plain dict. Pure function
  of model.
- `subscribe(model)` returns active subscriptions. Diffed each
  cycle.

The runtime calls these on a single thread. No async/await in
user code. Ever.

### Tree nodes are plain dicts

UI trees use the wire protocol's node format directly:

```python
{"id": "btn", "type": "button", "props": {"label": "Save"}, "children": []}
```

The `ui` module provides builder functions that return these dicts.
Users can freely mix `ui` functions with raw dicts. No wrapper
types, no conversion layer.

Nodes with `id=None` (from auto-id widget builders like `text()`)
get assigned IDs during `normalize()` based on their position in
the tree: `auto:{type}:{parent_path}:{child_index}`. This is
deterministic; the same tree structure always produces the same
auto-IDs, which is required for stable diffing.

### Tree diffing

The runtime diffs the previous and current view trees and sends
patches. Four patch operations (matching the wire protocol):
`replace_node`, `update_props`, `insert_child`, `remove_child`.

Children are matched by ID, not position. If common children are
reordered, the differ emits `replace_node` for the parent (O(n)
simplicity over O(n^2) LCS). Patch ordering: removals descending,
updates with adjusted indices, inserts ascending.

First render and post-reconnect always send full snapshots.

### Concurrency model

One **runtime thread** owns all model state. `update()` and
`view()` are always called from this thread. No locks on model
or tree.

One **reader thread** reads wire messages from the renderer,
decodes them, and posts events to a thread-safe queue.

A **ThreadPoolExecutor** runs `Command.task()` functions. Results
are posted back to the event queue as `AsyncResult` events.
A nonce tracks task identity so cancelled tasks cannot inject
stale results.

**Timer threads** (`threading.Timer`) handle `Subscription.every()`
and `Command.send_after()`. They post events to the queue.

**External injection.** `runtime.inject(event)` is thread-safe
(queue.put). Flask routes, message queue consumers, background
threads can inject events into the app's update cycle.

### Renderer crash recovery

The reader thread detects a broken pipe, posts a `RendererExited`
event. The runtime thread handles reconnect with exponential
backoff (100ms, 200ms, 400ms, 800ms, 1600ms, 5 attempts). On
reconnect: re-sends settings, sends full snapshot (forces
`prev_tree = None`), re-syncs all subscriptions, re-opens all
windows.

### Daemon mode

`plushie.run(App, daemon=True)` keeps the runtime alive when the
renderer disconnects. Model, subscriptions, and async tasks persist.
New renderer connections get a full snapshot of the current state.

### Module dependency graph

Dependencies flow downward only. No cycles.

```
events.py  types.py  framing.py (msgpack)
    \         |         /
     protocol.py       /
           \          /
        connection.py  binary.py
              \       /
    commands.py  subscriptions.py  effects.py
         \          |             /
              app.py            /
               \               /
           runtime.py ---------
              |
    ui.py  tree.py  canvas.py   (no runtime dependency)
              |
    testing/{fixture,pool,plugin}.py
```

`ui.py`, `tree.py`, and `canvas.py` are pure utility modules that
depend only on `types.py`. They can be used without the runtime.

### Test layers

Layer 0 tests (protocol, framing, events, tree, ui) are pure
Python. No binary needed. These form the foundation and can be
written and run immediately.

Layer 1+ tests (connection, runtime, app integration) require
the plushie binary. Use `python -m plushie download` first.

## Design decisions

### Events: one dataclass per event family

Each wire event family maps to its own frozen dataclass. NOT one
generic class with a type discriminator.

```python
# YES -- each type has exactly the right fields
@dataclass(frozen=True, slots=True)
class Click:
    id: str
    scope: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class Input:
    id: str
    value: str     # always str, not Any
    scope: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class Toggle:
    id: str
    value: bool    # always bool, not Any
    scope: tuple[str, ...] = ()

# NO -- this loses type precision
@dataclass
class WidgetEvent:
    type: str      # "click", "input", "toggle" -- stringly typed
    id: str
    value: Any     # type checker can't help
```

**Why:** Click has no value. Input.value is str. Toggle.value is
bool. Slide.value is float. Separate classes give the type checker
precise information. `match` on class type is the Python-native
dispatch mechanism.

Widget events that carry scope: Click, Input, Submit, Toggle,
Select, Slide, SlideRelease, Scroll, Paste, Sort, Open, Close,
OptionHovered, KeyBinding, and all MouseArea/Canvas/Sensor/Pane
events.

Subscription events (KeyPress, KeyRelease, MouseMove, etc.) are
global (no scope).

Runtime events (AsyncResult, StreamChunk, TimerTick, EffectResult)
are generated Python-side, never on the wire.

### Model: frozen dataclasses recommended, any type accepted

The framework is generic over model type (`App[M]`). It works
with dicts, dataclasses, attrs, NamedTuples. All examples and
docs use frozen dataclasses with slots. Tuple instead of list
for collections (immutability).

```python
@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0
    items: tuple[Item, ...] = ()  # tuple, not list
```

Update via `replace()`:
```python
from dataclasses import replace
return replace(model, count=model.count + 1)
```

### UI builder: children as *args, options as **kwargs

Container widgets accept children as positional args. Options
are keyword-only.

```python
ui.column(
    ui.text("count", f"Count: {model.count}"),
    ui.button("inc", "+"),
    padding=16, spacing=8,
)
```

Named containers take id as first positional arg:
```python
ui.window("main", ui.column(...), title="Counter")
ui.container("sidebar", ui.text("nav"), width=250)
ui.scrollable("log", *(ui.text(line) for line in lines))
```

Anonymous containers (column, row, stack) have no positional id.
Optional keyword `id=` does not create scope.

Leaf widgets: id-first for interactive, auto-id sugar for display:
```python
ui.button("save", "Save")             # id, label
ui.text_input("search", model.query)  # id, value
ui.text("Hello")                      # auto-id (1 arg = content)
ui.text("count", f"Count: {n}")       # explicit id (2 args)
```

Use `@overload` decorators for type-safe multi-signature functions.
Use `/` (positional-only) for id and content args.

### App base class: ABC with self

```python
class App(ABC, Generic[M]):
    @abstractmethod
    def init(self) -> M | tuple[M, Command]: ...
    @abstractmethod
    def update(self, model: M, event: Event) -> M | tuple[M, Command]: ...
    @abstractmethod
    def view(self, model: M) -> dict: ...
    def subscribe(self, model: M) -> list[Subscription]: return []
    def settings(self) -> dict[str, Any]: return {}
    def handle_renderer_exit(self, model: M, reason: Any) -> M: return model
    def window_config(self, model: M) -> dict[str, Any]: return {}
```

`window_config()` is called when windows are opened, providing
default properties (title, size, position, theme). Per-window
props set in the view tree override these defaults.

`self` exists but is NOT for model state. The model is passed
explicitly, keeping the Elm separation. `self` is available for
per-instance configuration, helper methods, or injected
dependencies.

### Custom transports (iostream adapter)

For SSH, TCP, WebSocket, or WASM browser connections:

```python
from plushie.transport import IoStreamAdapter, WebSocketAdapter
from plushie.connection import Connection

# TCP socket
adapter = IoStreamAdapter(read_stream=sock, write_stream=sock)
conn = Connection.from_iostream(adapter)

# WebSocket (for WASM renderer in browser)
adapter = WebSocketAdapter(ws)
conn = Connection.from_iostream(adapter)
```

Equivalent to Elixir's `{:iostream, pid}` transport and Gleam's
`socket_adapter`.

### Decorator factory: alternative to class

```python
app = plushie.create_app()

@app.init
def init():
    return {"count": 0}

@app.update
def update(model, event):
    ...

@app.view
def view(model):
    ...

app.run()
```

Internally builds an App subclass. Sugar for scripts and
prototypes.

### Commands: Command.task() not Command.async()

`async` is a reserved word in Python. Use `Command.task(fn, tag)`
for async work. The function runs in the thread pool. Result
arrives as `AsyncResult(tag=tag, value=result)`.

```python
Command.task(fn, tag)           # run fn in thread pool
Command.stream(fn, tag)         # fn receives emit callback
Command.cancel(tag)             # cancel running task
Command.send_after(delay, event) # delayed event
Command.focus(widget_id)        # widget ops
Command.batch([cmd1, cmd2])     # multiple commands
Command.exit()                  # shut down
```

Commands are frozen dataclasses with `type` and `payload` fields.
They are pure data: inspectable, testable, serializable. The
runtime interprets them after `update()` returns.

### Testing: binary-only, no Python mocks

ALL testing goes through the real renderer binary. The renderer's
`--mock` mode is the mock. No Python-side simulation of widget
behavior, event synthesis, or tree queries.

The `AppFixture` drives the cycle:
1. Calls `app.init()`, processes commands, sends snapshot
2. On `click()`: sends `interact` to renderer, gets events,
   processes through `app.update()`, diffs and sends patch
3. On `find()`: sends `query` to renderer, gets node back
4. `model` property returns current model (Python-side)
5. `text()` sends `query`, extracts text prop from result

Session pool: one `plushie --mock --max-sessions N` process shared
across the test suite via pytest plugin. Each test gets a unique
session ID.

Headless mode handles `interact_step` round-trips transparently.
The test author's code is identical across all three backends.

### None return from update(): active prevention

Python's `match` returns None if no branch matches. The runtime
detects None returns from `update()`, logs a warning with the
event that fell through, and keeps the previous model. This is
the single biggest Python-specific footgun for the Elm architecture.

## Wire protocol

The canonical protocol spec is at `../plushie-rust/docs/protocol.md`.
That document is the source of truth for all message types, event
families, and interaction semantics.

## Non-obvious patterns

**Return unwrapping.** `update()` and `init()` return either a
bare model or `(model, command)` or `(model, [commands])`. The
runtime unwraps via isinstance checks. None return (no match
branch hit) is detected and warned.

**Window sync.** The runtime detects window nodes at root or
direct-child depth. Uses set differences to find opened/closed
windows, sends open/close/update ops to the renderer. Window
props are extracted and diffed separately.

**Subscription diffing.** `subscribe()` returns a list keyed by
`(type, tag)`, `(type, interval, tag)`, or `(kind, tag, window_id)`
for window-scoped subscriptions. The runtime diffs keys each cycle,
starting new subs and stopping removed ones. Timer subs use
`threading.Timer`. Renderer subs send subscribe/unsubscribe messages.

**Effect tracking.** Effects get auto-generated request IDs and
timeout timers. The runtime tracks pending effects and cancels
timers on response or renderer restart. On restart, pending
effects get `error: "renderer_restarted"`.

**Coalescable events.** High-frequency Move events are buffered in
a pending dict, keyed by source. A zero-delay timer flushes them.
Non-coalescable events flush the buffer first, preserving ordering.

**Task nonces.** Each `Command.task()` gets a unique nonce. The
`AsyncResult` carries the nonce. The runtime compares it against
the stored nonce for that tag. Stale results (from cancelled but
still-running tasks) are silently discarded.

**Canvas groups.** Interactive fields (`on_click`, `focusable`, etc.)
live on `"type": "group"` nodes, not on shapes. `interactive(shape,
id, **opts)` auto-wraps a leaf shape in a group. Transforms
(`translate`, `rotate`, `scale`) are value objects in the group's
`transforms` list.

**Native extensions.** Rust widget extensions depend on
`plushie-widget-sdk` from crates.io. They MUST implement
`clone_for_session()` for concurrent session support (without it,
tests timeout). `column` and `row` conflict with macros in the
prelude; import them explicitly from `plushie_widget_sdk::iced::widget`.

## Reference SDK

The plushie-elixir SDK (`../plushie-elixir/`) is the primary
reference for Python due to similar dynamic language conventions.
Consult it for architecture patterns when adding features, but
adapt to Python idioms rather than copying Elixir patterns directly.

## Related repositories

These are expected as sibling directories (e.g. `../plushie-rust/`):

- plushie-rust - Rust workspace (SDK, widget SDK, renderer)
- plushie-elixir - Elixir SDK (reference implementation)
- plushie-iced - vendored iced fork
