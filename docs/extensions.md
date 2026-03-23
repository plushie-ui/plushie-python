# Writing Widget Extensions

Guide for building custom widget extensions for plushie. Extensions let you
render arbitrary Rust-native widgets (iced widgets, custom
`iced::advanced::Widget` implementations, third-party crates) while keeping
your app's state and logic in Python.

## Quick start

An extension has two halves:

1. **Python side:** define the widget's props, commands, and (for native
   widgets) the Rust crate and constructor using `ExtensionDef`.

2. **Rust side:** implement the `WidgetExtension` trait from `plushie-core`.
   This receives tree nodes from Python and returns `iced::Element`s for
   rendering.

```python
# my_sparkline/extension.py
from plushie.extension import (
    ExtensionDef, PropDef, CommandDef, ParamDef,
    build_node, build_command,
)

sparkline_def = ExtensionDef(
    kind="sparkline",
    rust_crate="native/my_sparkline",
    rust_constructor="my_sparkline::SparklineExtension::new()",
    props=[
        PropDef("data", "number"),      # sample values to plot
        PropDef("color", "color"),      # line color
        PropDef("capacity", "number"),  # max samples in the ring buffer
    ],
    commands=[
        CommandDef("push", [ParamDef("value", "number")]),
    ],
)

def sparkline(id: str, **kwargs) -> dict:
    return build_node(sparkline_def, id, kwargs)

def push_sparkline(node_id: str, value: float):
    return build_command(sparkline_def, node_id, "push", {"value": value})
```

This gives you:

- `sparkline(id, data=..., color=..., capacity=...)` -- builds a widget
  node dict with typed props
- `push_sparkline(node_id, value)` -- returns a `Command` targeting the
  Rust extension
- Validation via `validate(sparkline_def)` to catch duplicate or reserved
  prop names

```rust
// native/my_sparkline/src/lib.rs
use plushie_core::prelude::*;

pub struct SparklineExtension;

impl SparklineExtension {
    pub fn new() -> Self { Self }
}

impl WidgetExtension for SparklineExtension {
    fn type_names(&self) -> &[&str] { &["sparkline"] }
    fn config_key(&self) -> &str { "sparkline" }

    fn render<'a>(&self, node: &'a TreeNode, env: &WidgetEnv<'a>) -> Element<'a, Message> {
        let label = prop_str(node, "label").unwrap_or_default();
        text(label).into()
    }
}
```

Build with `python -m plushie build` (extensions are registered via
configuration) or run the renderer binary directly. The `PlushieAppBuilder`
chains `.extension()` calls in the generated `main.rs`:

```rust
plushie::run(
    PlushieAppBuilder::new()
        .extension(my_sparkline::SparklineExtension::new())
)
```

## Extension kinds

### Composite extensions (pure Python)

Composite extensions are plain functions that compose existing widgets.
No Rust code needed. No registration or build step. Just write a function
that returns a node dict:

```python
from plushie import ui

def labeled_input(id: str, label: str, value: str, **kwargs) -> dict:
    """A text input with a label above it."""
    return ui.column(f"{id}-group", children=[
        ui.text(f"{id}-label", label),
        ui.text_input(f"{id}-input", value, **kwargs),
    ])

def card(id: str, title: str, children: list | None = None, **kwargs) -> dict:
    """A container with a title and styled border."""
    return ui.container(id, padding=16, children=[
        ui.column(spacing=8, children=[
            ui.text(f"{id}-title", title, size=20),
            *(children or []),
        ]),
    ])
```

The result is a standard node dict that composes naturally with any other
widget builder:

```python
def view(model):
    return ui.window("main", children=[
        ui.column(children=[
            card("profile", "User Profile", children=[
                labeled_input("name", "Full Name", model.name),
                labeled_input("email", "Email", model.email),
                ui.button("save", "Save"),
            ]),
        ]),
    ])
```

### Native extensions (Rust-backed)

Use `ExtensionDef` for widgets rendered by a Rust crate. The definition
describes the Rust crate path, constructor expression, props, and commands.

```python
from plushie.extension import ExtensionDef, PropDef

hex_view_def = ExtensionDef(
    kind="hex_view",
    rust_crate="native/hex_view",
    rust_constructor="hex_view::HexViewExtension::new()",
    props=[
        PropDef("data", "string"),    # binary data (base64)
        PropDef("columns", "number"), # columns per row
    ],
)
```


## Data definitions reference

### ExtensionDef

The top-level definition for a native extension widget.

| Field | Required | Description |
|---|---|---|
| `kind` | yes | Widget type string (must match Rust `type_names()`) |
| `rust_crate` | yes | Path to the Rust crate relative to the project root |
| `rust_constructor` | yes | Rust expression to construct the extension instance |
| `props` | no | List of `PropDef` property declarations |
| `commands` | no | List of `CommandDef` command declarations |

### PropDef

Declares a single property on an extension widget.

| Field | Description |
|---|---|
| `name` | Property name as it appears on the wire |
| `prop_type` | One of the supported prop type strings |

### CommandDef

Declares a command that can be sent to the Rust extension.

| Field | Description |
|---|---|
| `name` | Command operation name |
| `params` | List of `ParamDef` typed parameters |

### ParamDef

Declares a single parameter in an extension command.

| Field | Description |
|---|---|
| `name` | Parameter name as it appears on the wire |
| `param_type` | One of: `"string"`, `"number"`, `"bool"` |

### Supported prop types

`"string"`, `"number"`, `"bool"`, `"color"`, `"length"`, `"padding"`,
`"alignment"`, `"font"`, `"style"`, `"atom"`, `"map"`, `"any"`

The `a11y` and `event_rate` props are available on all extension widgets
automatically. You do not need to declare them.

### Reserved prop names

The following names are reserved by the framework and cannot be used in
extension definitions: `id`, `type`, `children`, `a11y`, `event_rate`.


## Runtime helpers

### build_node

Build a wire-compatible node dict for a native extension widget:

```python
from plushie.extension import build_node

node = build_node(sparkline_def, "spark-1", {"data": [1, 2, 3], "color": "#ff0000"})
# => {"id": "spark-1", "type": "sparkline", "props": {"data": [1, 2, 3], "color": "#ff0000"}, "children": []}
```

The returned dict can be included directly in a view tree alongside
standard widget nodes.

### build_command

Build an extension command targeting a specific widget instance:

```python
from plushie.extension import build_command

cmd = build_command(sparkline_def, "spark-1", "push", {"value": 42.0})
# Returns Command(type="extension_command", payload={...})
```

### validate

Check an extension definition for errors:

```python
from plushie.extension import validate

errors = validate(sparkline_def)
if errors:
    for err in errors:
        print(f"Error: {err}")
```

Checks: non-empty `kind`, no duplicate prop names, no reserved prop names.

### prop_names / command_names

Introspect the declared properties and commands:

```python
from plushie.extension import prop_names, command_names

prop_names(sparkline_def)     # => ["data", "color", "capacity"]
command_names(sparkline_def)  # => ["push"]
```


## Extension tiers (Rust side)

Not every extension needs the full trait. The `WidgetExtension` trait has
sensible defaults for all methods except `type_names`, `config_key`, and
`render`. Choose the tier that fits your widget:

### Tier A: render-only (~200 lines)

Implement `type_names`, `config_key`, and `render`. Everything else uses
defaults. Good for widgets that compose existing iced widgets with no
Rust-side interaction state.

```rust
impl WidgetExtension for HexViewExtension {
    fn type_names(&self) -> &[&str] { &["hex_view"] }
    fn config_key(&self) -> &str { "hex_view" }

    fn render<'a>(&self, node: &'a TreeNode, env: &WidgetEnv<'a>) -> Element<'a, Message> {
        let data = prop_str(node, "data").unwrap_or_default();
        // ... build column/row/text layout ...
        container(content).into()
    }
}
```

### Tier B: interactive (+handle_event)

Add `handle_event` to intercept events from your widgets before they reach
Python. Use this when the extension needs to process mouse/keyboard input
internally (pan, zoom, hover tracking) or transform events before
forwarding.

```rust
fn handle_event(
    &mut self,
    node_id: &str,
    family: &str,
    data: &Value,
    caches: &mut ExtensionCaches,
) -> EventResult {
    match family {
        "canvas_press" => {
            let x = data.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let y = data.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let plot_event = OutgoingEvent::extension_event(
                "plot_click".to_string(),
                node_id.to_string(),
                Some(serde_json::json!({"plot_x": x, "plot_y": y})),
            );
            EventResult::Consumed(vec![plot_event])
        }
        _ => EventResult::PassThrough,
    }
}
```

#### Throttling high-frequency extension events

Mark events with a `CoalesceHint` to control buffering. Events without a
hint are always delivered immediately.

```rust
// Latest value wins -- position tracking, state snapshots
let event = OutgoingEvent::extension_event("cursor_pos", node_id, data)
    .with_coalesce(CoalesceHint::Replace);

// Deltas sum -- scroll, velocity, counters
let event = OutgoingEvent::extension_event("pan_scroll", node_id, data)
    .with_coalesce(CoalesceHint::Accumulate(
        vec!["delta_x".into(), "delta_y".into()]
    ));
```

Set `event_rate` from Python:

```python
node = build_node(plot_def, "plot1", {"data": chart_data, "event_rate": 30})
```

### Tier C: full lifecycle (+prepare, handle_command, cleanup)

Add `prepare` for mutable state synchronization before each render pass,
`handle_command` for commands sent from Python to the extension, and
`cleanup` for resource teardown when nodes are removed.

```rust
fn prepare(&mut self, node: &TreeNode, caches: &mut ExtensionCaches, theme: &Theme) {
    let state = caches.get_or_insert::<SparklineState>(self.config_key(), &node.id, || {
        SparklineState::new(prop_usize(node, "capacity").unwrap_or(100))
    });
    state.color = prop_color(node, "color");
}

fn handle_command(
    &mut self,
    node_id: &str,
    op: &str,
    payload: &Value,
    caches: &mut ExtensionCaches,
) -> Vec<OutgoingEvent> {
    match op {
        "push" => {
            if let Some(state) = caches.get_mut::<SparklineState>(self.config_key(), node_id) {
                if let Some(value) = payload.as_f64() {
                    state.push(value as f32);
                    state.generation.bump();
                }
            }
            vec![]
        }
        _ => vec![],
    }
}

fn cleanup(&mut self, node_id: &str, caches: &mut ExtensionCaches) {
    caches.remove(self.config_key(), node_id);
}
```

The full list of trait methods:

| Method | Required | Phase | Receives | Returns |
|---|---|---|---|---|
| `type_names` | yes | registration | -- | `&[&str]` |
| `config_key` | yes | registration | -- | `&str` |
| `init` | no | startup | `&InitCtx<'_>` | -- |
| `prepare` | no | mutable (pre-view) | `&TreeNode`, `&mut ExtensionCaches`, `&Theme` | -- |
| `render` | yes | immutable (view) | `&TreeNode`, `&WidgetEnv` | `Element<Message>` |
| `handle_event` | no | update | node_id, family, data, `&mut ExtensionCaches` | `EventResult` |
| `handle_command` | no | update | node_id, op, payload, `&mut ExtensionCaches` | `Vec<OutgoingEvent>` |
| `cleanup` | no | tree diff | node_id, `&mut ExtensionCaches` | -- |


## EventResult guide

`handle_event` returns one of three variants that control event flow:

### PassThrough

"I don't care about this event. Forward it to Python as-is." This is the
default.

### Consumed(events)

"I handled this event. Do NOT forward the original to Python. Optionally
emit different events instead."

```rust
// Pan/zoom: handle internally, emit nothing to Python
EventResult::Consumed(vec![])

// Transform: swallow the raw canvas event, emit a semantic one
EventResult::Consumed(vec![
    OutgoingEvent::extension_event(
        "plot_click".to_string(),
        node_id.to_string(),
        Some(json!({"series": "cpu", "index": 42})),
    )
])
```

### Observed(events)

"I handled this event AND forward the original to Python. Also emit
additional events." The original event is sent first, then the additional
events in order.


## Build system

### generate_cargo_toml

Generate a Cargo workspace manifest for a custom binary build:

```python
from plushie.extension import generate_cargo_toml

cargo_content = generate_cargo_toml([sparkline_def, gauge_def], binary_name="my-plushie")
```

### generate_main_rs

Generate the Rust entry point that registers all extensions:

```python
from plushie.extension import generate_main_rs

main_content = generate_main_rs([sparkline_def, gauge_def])
```

The generated `main.rs` creates a `PlushieAppBuilder`, registers each
extension via `.extension()`, and calls `run()`.


## Testing extensions

### Python-side tests

Test your extension's node building and command generation:

```python
from plushie.extension import build_node, build_command, validate

def test_validate_catches_duplicate_props():
    bad_def = ExtensionDef(
        kind="bad",
        rust_crate="native/bad",
        rust_constructor="bad::new()",
        props=[PropDef("x", "number"), PropDef("x", "number")],
    )
    errors = validate(bad_def)
    assert any("duplicate" in e for e in errors)

def test_build_node_creates_correct_type():
    node = build_node(sparkline_def, "s1", {"data": [1, 2, 3]})
    assert node["type"] == "sparkline"
    assert node["props"]["data"] == [1, 2, 3]

def test_build_command_creates_extension_command():
    cmd = build_command(sparkline_def, "s1", "push", {"value": 42.0})
    assert cmd.type == "extension_command"
```

### Rust-side tests

Test pure logic functions using `plushie_core::testing`:

```rust
#[cfg(test)]
mod tests {
    use plushie_core::testing::*;
    use super::*;

    #[test]
    fn handle_command_push_adds_sample() {
        let mut ext = SparklineExtension::new();
        let mut caches = ext_caches();

        let n = node_with_props("s-1", "sparkline", json!({"capacity": 10}));
        ext.prepare(&n, &mut caches, &iced::Theme::Dark);

        let events = ext.handle_command("s-1", "push", &json!(42.0), &mut caches);
        assert!(events.is_empty());

        let state = caches.get::<SparklineState>("sparkline", "s-1").unwrap();
        assert_eq!(state.samples.len(), 1);
    }
}
```

### End-to-end tests

Build a custom renderer and run through the real rendering path:

```bash
python -m plushie build
PLUSHIE_TEST_BACKEND=headless pytest
```

Write end-to-end tests with `AppFixture`:

```python
def test_sparkline_appears(plushie_pool):
    with AppFixture(SparklineDemo, plushie_pool) as app:
        app.assert_exists("#my-sparkline")

def test_push_updates_sparkline(plushie_pool):
    with AppFixture(SparklineDemo, plushie_pool) as app:
        app.click("#push-value")
        app.assert_text("#sample-count", "1")
```


## Panic isolation

The `ExtensionDispatcher` wraps all mutable extension calls in
`catch_unwind`. If your extension panics:

1. The panic is logged via `log::error!`.
2. The extension is marked as "poisoned".
3. All subsequent calls to the poisoned extension are skipped.
4. `render()` returns a red error placeholder text.
5. Poisoned state is cleared on the next `Snapshot` message.

A bug in one extension cannot crash the renderer or affect other extensions.

**Note:** `render()` panics ARE caught via `catch_unwind` in
`widgets::render()`. When a render panic is caught, the extension is
marked as "poisoned" and subsequent renders skip it, returning a red
error placeholder text until `clear_poisoned()` is called (typically on
the next `Snapshot` message).


## ExtensionCaches

`ExtensionCaches` is type-erased storage keyed by `(namespace, key)` pairs.
The namespace is typically your extension's `config_key()`, and the key is
the node ID. This is the primary mechanism for persisting state between
`prepare`/`render`/`handle_event`/`handle_command` calls.

Key methods:

| Method | Signature | Notes |
|---|---|---|
| `get::<T>(ns, key)` | `-> Option<&T>` | Immutable access |
| `get_mut::<T>(ns, key)` | `-> Option<&mut T>` | Mutable access |
| `get_or_insert::<T>(ns, key, default_fn)` | `-> &mut T` | Initialize if absent. Replaces on type mismatch. |
| `insert::<T>(ns, key, value)` | `-> ()` | Overwrites existing |
| `remove(ns, key)` | `-> bool` | Returns whether key existed |
| `contains(ns, key)` | `-> bool` | |
| `remove_namespace(ns)` | `-> ()` | Remove all entries for a namespace |

Common keying patterns:

- **Per-node state:** `caches.get::<MyState>(self.config_key(), &node.id)`
- **Per-node sub-keys:** `caches.get::<GenerationCounter>(self.config_key(), &format!("{}:gen", node.id))`
- **Global extension state:** `caches.get::<GlobalConfig>(self.config_key(), "_global")`

The type parameter `T` must be `Send + Sync + 'static`. This is why
`canvas::Cache` (which is `!Send + !Sync`) cannot be stored here.


## canvas::Cache and GenerationCounter

`iced::widget::canvas::Cache` is `!Send + !Sync`. This means it cannot be
stored in `ExtensionCaches` (which requires `Send + Sync + 'static`). This
is a fundamental constraint of iced's rendering architecture, not a bug.

### The pattern

Instead of storing `canvas::Cache` in `ExtensionCaches`, use iced's built-in
tree state mechanism. The cache lives in your `Program::State` (initialized
via `Widget::state()` or `canvas::Program`), and a `GenerationCounter` in
`ExtensionCaches` tracks when your data changes.

```rust
use plushie_core::prelude::*;
use iced::widget::canvas;

/// Stored in ExtensionCaches (Send + Sync).
struct SparklineData {
    samples: Vec<f32>,
    generation: GenerationCounter,
}

/// Stored in canvas Program::State (not Send, not Sync -- iced manages it).
struct SparklineState {
    last_generation: u64,
    cache: canvas::Cache,
}
```

In `prepare` or `handle_command`, bump the generation when data changes:

```rust
fn handle_command(&mut self, node_id: &str, op: &str, payload: &Value, caches: &mut ExtensionCaches) -> Vec<OutgoingEvent> {
    if op == "push" {
        if let Some(data) = caches.get_mut::<SparklineData>(self.config_key(), node_id) {
            data.samples.push(payload.as_f64().unwrap_or(0.0) as f32);
            data.generation.bump();  // signal that a redraw is needed
        }
    }
    vec![]
}
```

In `draw`, compare generations to decide whether to clear the cache:

```rust
impl canvas::Program<Message> for SparklineProgram<'_> {
    type State = SparklineState;

    fn draw(
        &self,
        state: &Self::State,
        renderer: &iced::Renderer,
        _theme: &Theme,
        bounds: iced::Rectangle,
        _cursor: iced::mouse::Cursor,
    ) -> Vec<canvas::Geometry> {
        if state.last_generation != self.current_generation {
            state.cache.clear();
        }

        let geometry = state.cache.draw(renderer, bounds.size(), |frame| {
            // Draw your content here
        });

        vec![geometry]
    }
}
```

### Why GenerationCounter instead of content hashing

`GenerationCounter` is a simple `u64` counter. Incrementing it is O(1) and
comparing two values is a single integer comparison. Content hashing is
more expensive and harder to get right. The counter approach is the
recommended pattern.

`GenerationCounter` implements `Send + Sync + Clone` and stores cleanly in
`ExtensionCaches`. Create it with `GenerationCounter::new()` (starts at 0),
call `.bump()` to increment, and `.get()` to read the current value.


## WidgetEnv fields

`WidgetEnv` (and the underlying `RenderCtx`) provides access to:

- `env.theme` -- the current iced `Theme`
- `env.window_id` -- the window ID (`&str`) this render pass is for
- `env.scale_factor` -- DPI scale factor (`f32`) for the current window

Extensions doing DPI-aware rendering or per-window adaptation can use
`window_id` and `scale_factor` directly.


## Event family reference

Every event sent over the wire carries a `family` string that identifies
what kind of interaction produced it. Extension authors need to know these
strings when implementing `handle_event` -- the `family` parameter tells
you what happened.

### Widget events (node ID in `id` field)

| Family | Source widget | Data fields |
|---|---|---|
| `click` | button | -- |
| `input` | text_input, text_editor | `value`: new text |
| `submit` | text_input | `value`: current text |
| `toggle` | checkbox, toggler | `value`: bool |
| `slide` | slider, vertical_slider | `value`: f64 |
| `slide_release` | slider, vertical_slider | `value`: f64 |
| `select` | pick_list, combo_box, radio | `value`: selected string |
| `open` | pick_list, combo_box | -- |
| `close` | pick_list, combo_box | -- |
| `paste` | text_input | `value`: pasted text |
| `option_hovered` | combo_box | `value`: hovered option |
| `sort` | table | `data.column`: column key |
| `scroll` | scrollable | `data`: absolute/relative offsets, bounds, content size |

### Canvas events (node ID in `id` field)

| Family | Data fields |
|---|---|
| `canvas_press` | `data.x`, `data.y`, `data.button` |
| `canvas_release` | `data.x`, `data.y`, `data.button` |
| `canvas_move` | `data.x`, `data.y` |
| `canvas_scroll` | `data.x`, `data.y`, `data.delta_x`, `data.delta_y` |
| `canvas_shape_enter` | `data.shape_id`, `data.x`, `data.y` |
| `canvas_shape_leave` | `data.shape_id` |
| `canvas_shape_click` | `data.shape_id`, `data.x`, `data.y`, `data.button` |
| `canvas_shape_drag` | `data.shape_id`, `data.x`, `data.y`, `data.delta_x`, `data.delta_y` |
| `canvas_shape_drag_end` | `data.shape_id`, `data.x`, `data.y` |
| `canvas_shape_focused` | `data.shape_id` |

### MouseArea events (node ID in `id` field)

| Family | Data fields |
|---|---|
| `mouse_right_press` | -- |
| `mouse_right_release` | -- |
| `mouse_middle_press` | -- |
| `mouse_middle_release` | -- |
| `mouse_double_click` | -- |
| `mouse_enter` | -- |
| `mouse_exit` | -- |
| `mouse_move` | `data.x`, `data.y` |
| `mouse_scroll` | `data.delta_x`, `data.delta_y` |

### Sensor events (node ID in `id` field)

| Family | Data fields |
|---|---|
| `sensor_resize` | `data.width`, `data.height` |

### PaneGrid events (grid ID in `id` field)

| Family | Data fields |
|---|---|
| `pane_resized` | `data.split`, `data.ratio` |
| `pane_dragged` | `data.pane`, `data.target` |
| `pane_clicked` | `data.pane` |

### Subscription events (subscription tag in `tag` field, empty `id`)

| Family | Data fields |
|---|---|
| `key_press` | `modifiers`, `data.key`, `data.modified_key`, `data.physical_key`, `data.location`, `data.text`, `data.repeat` |
| `key_release` | `modifiers`, `data.key`, `data.modified_key`, `data.physical_key`, `data.location` |
| `modifiers_changed` | `data.shift`, `data.ctrl`, `data.alt`, `data.logo`, `data.command` |
| `cursor_moved` | `data.x`, `data.y` |
| `cursor_entered` | -- |
| `cursor_left` | -- |
| `button_pressed` | `data.button` |
| `button_released` | `data.button` |
| `wheel_scrolled` | `data.delta_x`, `data.delta_y`, `data.unit` |
| `finger_pressed` | `data.id`, `data.x`, `data.y` |
| `finger_moved` | `data.id`, `data.x`, `data.y` |
| `finger_lifted` | `data.id`, `data.x`, `data.y` |
| `finger_lost` | `data.id`, `data.x`, `data.y` |
| `ime_opened` | -- |
| `ime_preedit` | `data.text`, `data.cursor` |
| `ime_commit` | `data.text` |
| `ime_closed` | -- |
| `animation_frame` | `data.timestamp_millis` |
| `theme_changed` | `data.mode` |

### Window events (subscription tag in `tag` field)

| Family | Data fields |
|---|---|
| `window_opened` | `data.window_id`, `data.position` |
| `window_closed` | `data.window_id` |
| `window_close_requested` | `data.window_id` |
| `window_moved` | `data.window_id`, `data.x`, `data.y` |
| `window_resized` | `data.window_id`, `data.width`, `data.height` |
| `window_focused` | `data.window_id` |
| `window_unfocused` | `data.window_id` |
| `window_rescaled` | `data.window_id`, `data.scale_factor` |
| `file_hovered` | `data.window_id`, `data.path` |
| `file_dropped` | `data.window_id`, `data.path` |
| `files_hovered_left` | `data.window_id` |


## Prop helpers reference

The `plushie_core::prop_helpers` module (re-exported via `prelude::*`) provides
typed accessors for reading props from `TreeNode`. Use these instead of
manually traversing `serde_json::Value`:

| Helper | Return type | Notes |
|---|---|---|
| `prop_str(node, key)` | `Option<String>` | |
| `prop_f32(node, key)` | `Option<f32>` | Accepts numbers and numeric strings |
| `prop_f64(node, key)` | `Option<f64>` | Accepts numbers and numeric strings |
| `prop_u32(node, key)` | `Option<u32>` | Rejects negative values |
| `prop_u64(node, key)` | `Option<u64>` | Rejects negative values |
| `prop_usize(node, key)` | `Option<usize>` | Via `prop_u64` |
| `prop_i64(node, key)` | `Option<i64>` | Signed integers |
| `prop_bool(node, key)` | `Option<bool>` | |
| `prop_bool_default(node, key, default)` | `bool` | Returns default when absent |
| `prop_length(node, key, fallback)` | `Length` | Parses "fill", "shrink", numbers, `{fill_portion: n}` |
| `prop_range_f32(node)` | `RangeInclusive<f32>` | Reads `range` prop as `[min, max]`, defaults to `0.0..=100.0` |
| `prop_range_f64(node)` | `RangeInclusive<f64>` | Same as above, f64 |
| `prop_color(node, key)` | `Option<iced::Color>` | Parses `#RRGGBB` / `#RRGGBBAA` hex strings |
| `prop_f32_array(node, key)` | `Option<Vec<f32>>` | Array of numbers |
| `prop_horizontal_alignment(node, key)` | `alignment::Horizontal` | "left"/"center"/"right", defaults Left |
| `prop_vertical_alignment(node, key)` | `alignment::Vertical` | "top"/"center"/"bottom", defaults Top |
| `prop_content_fit(node)` | `Option<ContentFit>` | Reads `content_fit` prop |
| `prop_padding(node, key)` | `Padding` | Public padding prop helper |
| `node.prop_str(key)` | `Option<String>` | Method on `TreeNode` |
| `node.prop_f32(key)` | `Option<f32>` | Method on `TreeNode` |
| `node.prop_bool(key)` | `Option<bool>` | Method on `TreeNode` |
| `node.prop_color(key)` | `Option<Color>` | Method on `TreeNode` |
| `node.prop_padding(key)` | `Padding` | Method on `TreeNode` |
| `node.props()` | `Option<&Map>` | Access the props object directly |


## Publishing widget packages

### Pure Python packages

Pure Python widget packages compose existing primitives (canvas, column,
container, etc.) into higher-level widgets. They work with prebuilt renderer
binaries. No Rust toolchain needed.

#### When pure Python is enough

Canvas + shape builders cover custom 2D rendering: charts, diagrams,
gauges, sparklines, colour pickers. Composition of layout primitives
covers cards, tab bars, sidebars, toolbars, and other structural patterns.

Pure Python falls short when you need: custom text layout engines, GPU
shaders, platform-native controls, or performance-critical rendering that
canvas cannot handle efficiently.

#### Package structure

A plushie widget package is a standard Python package:

```
my_widget/
    src/
        my_widget/
            __init__.py         # public API
            donut_chart.py      # widget builder functions
    tests/
        test_donut_chart.py
    pyproject.toml
```

### Native packages (Python + Rust)

Native packages include both Python definitions (`ExtensionDef`) and a Rust
crate. Consumers need a Rust toolchain to build the custom renderer binary.
Document this in your package README.
