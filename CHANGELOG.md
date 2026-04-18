# Changelog

## Unreleased

### Breaking changes

- `Command.load_font(data)` now requires a leading `family` argument:
  `Command.load_font(family, data)`. The wire payload carries both
  fields under the `load_font` widget_op.
- `Command.close_window(window_id)` is now a `window_op` with `op:
  "close"` rather than a `widget_op` with `op: "close_window"`.
  Callers that inspected `cmd.type` or `cmd.payload["op"]` must
  migrate to the new shape.
- Environment variable renamed: `PLUSHIE_SOURCE_PATH` is now
  `PLUSHIE_RUST_SOURCE_PATH`. The old name is no longer recognized.
- Python constant renamed: `plushie.binary.BINARY_VERSION` is now
  `plushie.binary.PLUSHIE_RUST_VERSION`.
- `python -m plushie build` now delegates to `cargo-plushie`. Install
  the matching tool with
  `cargo install cargo-plushie --version <PLUSHIE_RUST_VERSION> --locked`,
  or set `PLUSHIE_RUST_SOURCE_PATH` for local development. The
  `generate_cargo_toml`, `generate_main_rs`, and `validate_all`
  helpers in `plushie.native_widget` are gone; cross-widget
  collision detection moved to cargo-plushie.

### Added

- Decoder support for the new top-level `diagnostic` wire message.
  Mirrored to Python logging at the reported severity and delivered
  through the runtime as a `RendererDiagnostic` event so hosts can
  inspect it programmatically via `get_diagnostics()`.
- `plushie.cargo_plushie.resolve_cargo_plushie()` helper that returns
  the cargo-plushie invocation (either from `PLUSHIE_RUST_SOURCE_PATH`
  or from a PATH install with version check).
- `plushie.renderer_build` module orchestrating the new cargo-plushie
  build flow.

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
