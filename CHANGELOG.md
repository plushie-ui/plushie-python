# Changelog

## [0.6.0] - 2026-05-09

Large SDK convergence release. Breaking changes align the Python SDK with
plushie-elixir, plushie-rust, plushie-ruby, and plushie-ts on naming,
event shapes, and wire protocol.

### Breaking changes

**Commands**

- `Command.done` renamed to `Command.dispatch`.
- `Command.widget_commands` renamed to `Command.widget_batch`.
- `Command.load_font(data)` now requires a leading `family` argument:
  `Command.load_font(family, data)`.
- `Command.close_window(window_id)` is now a `window_op` (`op: "close"`)
  rather than a `widget_op` (`op: "close_window"`).
- `Command.gain_focus` renamed to `Command.focus_window`.
- `Command.request_user_attention` renamed to `Command.request_attention`.
- Query commands drop the `get_` prefix: `get_window_size` ->
  `window_size`, `get_window_position` -> `window_position`,
  `get_mode` -> `window_mode`, `get_scale_factor` -> `scale_factor`,
  `get_system_theme` -> `system_theme`, `get_system_info` -> `system_info`.
- Widget ops (`focus`, `scroll_to`, `pane_split`, etc.) move from the
  `widget_op` envelope to the unified command format. Extension commands
  move from `extension_command` / `extension_commands` to `command` /
  `commands`.
- `WidgetCommandError` renamed to `CommandError`; its fields are now
  `id` and `family` (was `node_id` and `op`).

**Effects**

- Effects now take a `tag` as first argument. Starting a new effect with
  the same tag cancels the previous one. `EffectResult` carries `tag`
  for matching; internal request IDs are no longer exposed.

**Events**

- `ImeOpen` renamed to `ImeOpened`.
- `KeyPress` and `KeyRelease` collapse into `KeyEvent(type, key,
  modifiers, window_id, id, scope)` with a `type` discriminator.
- `ImeOpened`, `ImePreedit`, `ImeCommit`, `ImeClose` collapse into
  `ImeEvent(type, ...)`.
- Ten window-lifecycle types (`WindowResized`, `WindowMoved`, etc.)
  collapse into `WindowEvent(type, ...)`.
- Fourteen canvas pointer types consolidate into `Press`, `Release`,
  `Move`, `Scroll`, `DoubleClick`, `Resize`, `Enter`, `Exit`; all carry
  full pointer metadata (device type, button, modifiers, finger_id).
  Removed: `CanvasPress`, `CanvasRelease`, `MouseAreaPress`,
  `MouseAreaMove`, `MouseAreaScroll`, `MouseAreaDoubleClick`,
  `SensorResize`, `MouseAreaEnter`, `MouseAreaExit`, and variants.
- Mouse and touch subscription events unified into pointer events.
  Removed: `MouseMove`, `MouseEnter`, `MouseLeave`, `MouseButtonPress`,
  `MouseButtonRelease`, `MouseWheel`, `TouchPress`, `TouchMove`,
  `TouchLift`, `TouchLost`. Subscription methods renamed:
  `on_mouse_move` -> `on_pointer_move`, `on_mouse_button` ->
  `on_pointer_button`, `on_mouse_scroll` -> `on_pointer_scroll`,
  `on_touch` -> `on_pointer_touch`.
- `PointerScroll` renamed to `Scroll`; old `Scroll` (viewport-scroll
  event) renamed to `Scrolled`.
- Effect stub ack event types renamed to `effect_stub_register_ack` and
  `effect_stub_unregister_ack` (was `effect_stub_registered` /
  `effect_stub_unregistered`).

**UI builders**

- `mouse_area` renamed to `pointer_area`.
- `Alignment` splits into `AlignX` (`left` / `center` / `right`) and
  `AlignY` (`top` / `center` / `bottom`). The old `start` / `end`
  vocabulary is gone.
- `grid(columns=N)` renamed to `grid(num_columns=N)`.
- `ime_purpose` property renamed to `input_purpose`.
- App views must return explicit `window` node(s) at the top level.
  Returning a bare widget tree is no longer accepted.

**Custom widgets**

- `ExtensionDef` renamed to `NativeWidgetDef`; `CanvasWidgetDef`
  consolidated into `WidgetDef`. Both old names are re-exported as
  compatibility shims but will be removed in a future release.
- `WidgetDef.render()` callback renamed to `WidgetDef.view()`.
- `Command.extension_command()` renamed to `Command.widget_command()`.
- `ExtensionCommandError` renamed to `WidgetCommandError` (distinct from
  the command-level `CommandError` above).
- `extension_config` settings key renamed to `widget_config`.
- `connection(expected_extensions=...)` parameter renamed to
  `expected_widgets`.
- `generate_cargo_toml`, `generate_main_rs`, and `validate_all` helpers
  in `plushie.native_widget` removed; cross-widget collision detection
  moved to `cargo-plushie`.

**Wire / connection**

- Wire format auto-detection removed. `Connection.open()`,
  `StdioConnection.__init__`, and `IoStreamAdapter.__init__` now take an
  explicit `format="json" | "msgpack"` parameter.
- Op-specific fields in `window_op`, `system_op`, `system_query`, and
  `image_op` messages now nest under a `payload` key alongside `op`.
- Environment variable renamed: `PLUSHIE_SOURCE_PATH` is now
  `PLUSHIE_RUST_SOURCE_PATH`. The old name is no longer recognized.
- Python constant renamed: `plushie.binary.BINARY_VERSION` is now
  `plushie.binary.PLUSHIE_RUST_VERSION`.
- `python -m plushie build` now delegates to `cargo-plushie`. Install
  with `cargo install cargo-plushie --version <PLUSHIE_RUST_VERSION>
  --locked`, or set `PLUSHIE_RUST_SOURCE_PATH` for local development.

### Added

**Events**

- `LinkClicked(id, link, window_id, scope)` typed event for rich text and
  markdown hyperlink clicks.
- `RendererExitInfo` dataclass (`type`, `message`, `details`) and
  `RecoveryFailed` event dispatched when `handle_renderer_exit` raises.
- `SessionError` and `SessionClosed` typed events for multiplexed mode.
  `EffectStubAck` replaces the raw dict previously delivered for stub ack
  messages.
- `CanvasElementKeyPress` and `CanvasElementKeyRelease` events (carry
  `modifiers` field matching the unified key event shape).
- `Span` and `SpanHighlight` frozen dataclasses for rich text; instances
  auto-encoded alongside plain dicts in `rich_text` spans lists.
- `SessionError.code` field exposed on the typed dataclass.
- Typed diagnostic variants: `DiagnosticMessage` wraps session, level,
  and a structured variant. Includes `BufferOverflowError` and
  `ProtocolVersionMismatchError`.
- `TransitionComplete(tag, prop)` event delivered at end of
  renderer-side animations.
- Pointer `Enter` and `Exit` events now carry `x`, `y`, and `captured`.
  `Press`, `Release`, `Move`, and `Scroll` carry `captured`; `Scroll`
  also carries `unit`; `Release` carries `lost`.

**UI builders**

- `table_row()` and `cell()` container builders for children-based table
  rows; `expand_rows(data, row_fn)` converts a data sequence into
  `table_row` / `table_cell` children.
- `Angle(degrees)` or `Angle(value, "rad")` type for canvas rotation and
  arc operations.
- `LineHeight` type with relative multiplier and explicit pixel forms.
- Per-corner radius support in the canvas `rect` shape.

**Types and protocol**

- `WireEncodable` runtime-checkable protocol: any type with a `to_wire()`
  method is automatically recognized during tree normalization. Replaces
  the internal `_WIRE_TYPES` registration; third-party types can satisfy
  the protocol without SDK changes.
- `ScopedId` type and window-qualified `window_id#widget_path` selector
  syntax across commands, test helpers, and subscriptions.
- `AlignX` and `AlignY` axis-split alignment types.

**Animation**

- Renderer-side animation system: `Transition` (timed easing),
  `Spring` (physics-based, with `gentle` / `snappy` / `bouncy` /
  `stiff` / `molasses` presets), `Sequence` (chained animations). Set
  these as prop values; the renderer drives them frame-by-frame.
- `Tween.repeat(n)`, `Tween.auto_reverse`, and `Tween.looping()` for
  SDK-side interpolators.
- 31 named easing curves and `cubic_bezier` with solver.

**Subscriptions**

- Window-scoped subscriptions: `Subscription.on_key_press("tag",
  window="editor")` and `Subscription.for_window("editor", [...])`
  grouped scoping. Renderer filters events by window scope.
- All key, pointer, touch, IME, and modifier-changed events now carry a
  `window_id` field.

**Runtime**

- `await_async(tag, timeout)` method on `Runtime` for blocking until an
  async task completes.
- `interact()` method on the production `Runtime` for scripted
  interaction outside tests.
- Heartbeat watchdog: detects an unresponsive renderer and triggers the
  recovery path.
- `Command.dispatch` chain depth capped; `DispatchLoopExceeded`
  diagnostic emitted when exceeded.
- Frozen-UI dev overlay: after five consecutive `view()` failures a red
  status bar is injected; clears on success or reconnect.
- Max tree depth validation: warn at depth 200, raise at depth 256
  (prevents infinite recursion in composite widgets).

**Custom widgets**

- `WidgetDef.handle_event` is now optional; default returns
  `EventAction.ignored()`.
- Canvas-internal events are auto-consumed after widget dispatch unless
  explicitly captured by the handler.
- `WidgetDef` supports composition of built-in widgets in addition to
  canvas rendering. `handle_event` presence signals interactivity;
  `subscribe` enables scoped subscriptions.
- Typed event declarations: `event_specs: ClassVar[dict[str, EventSpec]]`
  with emit-time validation (undeclared events, missing required fields,
  wrong types).
- Typed widget event routing: built-in families (`click`, `select`,
  `toggle`, `input`) produce typed dataclasses; custom event names still
  produce `WidgetEvent(kind, data)`.

**Accessibility**

- `resolved_a11y()` test helper and `AppFixture.resolved_a11y` pipeline
  for inspecting inferred a11y annotations.
- `Command.focus_next_within(scope)`, `focus_previous_within(scope)`.
- `Command.announce(message, politeness="polite" | "assertive")`.
- Scope-rewritten cross-widget refs; dangling refs emit warnings.
- Per-widget a11y defaults (role, has_popup) applied during normalize.
- `active_descendant` and `radio_group` fields on `A11y` dataclass.
- Implicit `radio_group` positions inferred from the `group` prop.

**Connection**

- `SocketAdapter` for TCP (`host:port` or `:port`) and Unix domain
  socket (`/path`) connections via `Connection.from_iostream()`.
- `preflight` rebuilds `plushie-renderer` from source when
  `PLUSHIE_RUST_SOURCE_PATH` is set, then exports `PLUSHIE_BINARY_PATH`
  so the test run uses the fresh binary.
- `resolve_cargo_plushie()` helper in `plushie.cargo_plushie`.
- `plushie.renderer_build` module orchestrating the cargo-plushie build
  flow.

**Testing**

- `assert_tree_hash` and `assert_screenshot` golden-file assertion
  helpers.
- `AppFixture.assert_a11y`, `assert_role`, `assert_no_diagnostics`,
  `resolved_a11y`.
- Diagnostic events captured automatically in `AppFixture`.
- `WidgetFixture` for isolated canvas widget testing.
- `case-insensitive` key resolution in test helpers.
- ID selectors validated before interact; unresolved `#id` raises
  `ValueError` listing available IDs.
- `interact()` raises `RuntimeError` on concurrent calls or renderer exit
  during interaction, `TimeoutError` on renderer timeout.
- Unified selector string syntax: ID, pseudo-class, and attribute
  selectors (`[text=Save]`, `[role=button]`, `[label=Name]`).
- Per-field required/optional control in `EventSpec`.

**Documentation**

- Full reference documentation set (events, commands, subscriptions,
  effects, built-in widgets, canvas, animation, windows and layout,
  themes and styling, testing, composition patterns, custom widgets,
  Python typing, app lifecycle).
- 16 guide chapters covering the full SDK surface.

### Fixed

- `window_opened` events parse `x` and `y` from top-level fields;
  previous decoder read from a nested `position` key the renderer no
  longer emits.
- `default_font` sent as canonical `{"family": ...}` object; bare
  strings rewritten before the wire.
- `Command.load_font` sends as a typed top-level message with `{family,
  data}` payload instead of a `widget_op` envelope.
- `Command.list_images_query` and `Command.clear_images` emit the typed
  `image_op` envelope (`op: "list"` / `op: "clear"`) instead of the
  `widget_op` form the renderer no longer accepts.
- Padding encoding: tuples were silently dropped; now properly encoded
  through `encode_padding`.
- Gradient wire format redesigned from angle-based to coordinate-based,
  matching the renderer.
- Font weight, style, and stretch encoded as snake_case on the wire.
- Text command wire format aligned with renderer expectations.
- Widget ID validation: empty strings, non-printable ASCII, and IDs
  exceeding the max length now raise at build time.
- Pixel buffer size validated in `create_image_rgba` and
  `update_image_rgba`.
- `flush_pending_effects` preserves effects registered during flush;
  subscription spec filtering corrected.
- Strict `hello` decoder validates all required fields.
- Widget state changes now trigger a re-render; registry reverts on view
  error during state re-render.
- Theme prop on `window` widget properly tracked and diffed.
- Renderer reconnect resets the consecutive view-error counter.
- Renderer binary version mismatch logged as a warning during handshake.
- Native widget type names that shadow built-in widgets are rejected.
- Pending `interact` fails cleanly when the renderer exits or restarts.
- Concurrent stub ack / `await_async` for the same key raises
  `RuntimeError` instead of silently dropping one caller.
- Protocol parity gaps closed: `captured`, `unit`, `lost` fields added;
  `AnimationFrame.timestamp` widened to `float`; `Subscription.batch()`
  validated.
- Non-finite floats normalized at framing layer rather than silently
  producing invalid JSON.
- JSON feed loop guards partial tail to prevent buffer overflow from
  unterminated lines.
- Canvas key events carry `modifiers` field.
- A11y cross-widget refs rewritten through scope-prefix logic; missing
  accessible names detected.
- Timer subscription and runtime control operations synchronized.

### Changed

- Pinned renderer advanced to plushie-rust 0.7.1. Run
  `python -m plushie download --force` to pull the updated binary.
- `SessionPool` default session count lowered from 32 to 8 (aligns with
  all other SDKs).
- `HelloInfo` now includes `native_widgets` and `widgets` fields from the
  renderer hello.
- Memo body meta key renamed to `__memo_fun__` for cross-SDK parity.
- Memo subtrees now cached by dependency key; widget view expansion and
  ID-keyed list diffs enabled in the tree differ.
- Coalescing keyed by `(window_id, target_id)` for correct per-widget
  deduplication across windows.
- `WidgetDef` consolidates `CanvasWidgetDef`; `canvas_widget.py` is now
  a compatibility re-export shim.
- `NativeWidgetDef` replaces `ExtensionDef`; `native_widget.py` shim
  preserved for one release cycle.
- `plushie.tree` split into `normalize`, `diff`, `search`, and `a11y`
  submodules; public imports unchanged.

## v0.5.0 - 2026-03-23

Initial release of the plushie Python SDK. Full feature parity with
the plushie-elixir and plushie-gleam SDKs, verified by cross-SDK audit.

### Framework

- Elm architecture: `App` base class with `init`, `update`, `view`,
  `subscribe`, `settings`, `window_config`, and `handle_renderer_exit`
- Decorator-based app builder via `create_app()` for quick prototypes
- Runtime event loop with tree diffing, command processing,
  subscription lifecycle management, and window sync
- Renderer crash recovery with exponential backoff (5 attempts)
- Daemon mode for persistent server-side apps
- Event coalescing for high-frequency events
- Thread-safe external event injection via `runtime.inject()`
- `run()` (blocking) and `start()` (background thread) entry points

### Wire protocol

- MessagePack (4-byte length-prefixed) and JSON (newline-delimited)
- Auto-detection from first byte
- All 17 outbound and 9 inbound message types
- SHA-256 checksum verification on all downloads

### Widgets and UI

- 38 widget builder functions via `plushie.ui`
- Canvas shape builders via `plushie.canvas` (rect, circle, line,
  path, text, image, svg, group, layer, interactive)
- Canvas groups with `transforms`, `clip`, and top-level interactive
  fields (`on_click`, `on_hover`, `focusable`, `focus_style`, etc.)
- Canvas widget `role` and `arrow_mode` props
- Type system: `Border`, `Shadow`, `Gradient`, `Font`, `StyleMap`,
  `Theme` (22 built-in), `A11y` (24 fields), `Color` (148 CSS names)
- Automatic wire serialization via `to_wire()` during tree normalization

### Events

- ~80 frozen dataclasses (one per wire event family)
- Canvas element events: `CanvasElementEnter`, `CanvasElementLeave`,
  `CanvasElementClick`, `CanvasElementDrag`, `CanvasElementDragEnd`,
  `CanvasElementFocused`, `CanvasElementBlurred`
- Canvas lifecycle: `CanvasFocused`, `CanvasBlurred`,
  `CanvasGroupFocused`, `CanvasGroupBlurred`
- `Diagnostic` event for renderer validation warnings
- ~200 key name constants
- Scoped ID splitting with tuple-based scope matching
- Union types for pattern matching

### Commands and subscriptions

- All command types: task, stream, cancel, done, send_after, focus,
  focus_element, scroll, select, window ops, window queries, image ops,
  extension commands, pane operations, batch, exit
- 20 subscription types with key-based diffing and max_rate support

### Effects

- All 13 platform effects: file dialogs (open, save, directory),
  clipboard (read, write, HTML, primary, clear), notifications

### State helpers

- Animation (8 easing curves, interpolation, lifecycle)
- Selection (single, multi, range modes)
- UndoStack (with time-window coalescing)
- Data query pipeline (filter, search, sort, paginate, group)
- Route (navigation stack)
- State (revision tracking with transactions)

### Testing

- `AppFixture` with all 17 interact actions and synchronous command
  processing through the real plushie binary
- `SessionPool` for test session multiplexing
- Three backends: mock, headless, windowed
- Assertion helpers: `assert_text`, `assert_exists`, `assert_not_exists`,
  `assert_model`
- Accessibility queries: `find_by_role`, `find_by_label`, `find_focused`
- Golden file regression: `assert_tree_hash`, `assert_screenshot`,
  `save_screenshot`
- Interaction type validation with helpful error messages
- pytest plugin with auto pool lifecycle

### Extensions

- Composite extensions (pure Python functions, no Rust)
- Native extensions: `ExtensionDef`, `PropDef`, `CommandDef`, `ParamDef`
- `build_node()` and `build_command()` for wire-compatible output
- `validate()` and `validate_all()` with collision detection
- Cargo workspace and main.rs generation
- `pyproject.toml` `[tool.plushie]` configuration

### Transports

- Spawn mode (default, Python manages renderer subprocess)
- Stdio mode (`StdioConnection` for `plushie --exec`)
- Custom transports: `IoStreamAdapter`, `WebSocketAdapter`
- `Connection.from_iostream()` for SSH, TCP, WebSocket bridges
- Env var whitelisting for renderer subprocess security

### Binary management

- 5-step resolution: env var, custom build, downloaded, bundled, PATH
- Platform detection (linux/darwin/windows, x86_64/aarch64)
- Download with SHA-256 checksum verification and `--force` flag
- WASM renderer download and build support
- Stock and extension binary builds from source
- Rust version check (>= 1.92.0)
- Bundled binary support for PyInstaller, Nuitka, Briefcase

### CLI

- `run` - run apps with `--mode`, `--json`, `--watch`, `--daemon`
- `connect` - stdio transport for remote rendering
- `download` - native binary and WASM with `--force`, `--bin`, `--wasm`
- `build` - stock and extension builds with `--release`, `--verbose`
- `inspect` - print initial UI tree as JSON
- `script` - run `.plushie` test scripts
- `replay` - replay scripts with real windows

### Documentation

- 16 guides matching plushie-elixir coverage
- CLI reference
- 164 HTML test markers linking doc code blocks to 354 tests

### Examples

- 9 example apps: counter, clock, todo, notes, shortcuts, async_fetch,
  color_picker, catalog, rate_plushie
- 3 reusable widget modules: color_picker_widget, star_rating,
  theme_toggle
- Integration tests for all examples
