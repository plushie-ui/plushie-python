# Changelog

## v0.1.0 -- 2026-03-23

Initial release of the plushie Python SDK.

### Added

- Elm architecture framework: `App` base class with `init`, `update`,
  `view`, and `subscribe` callbacks
- Decorator-based app builder via `create_app()`
- Wire protocol: MessagePack (length-prefixed) and JSON (newline-delimited)
  with auto-detection
- Connection management with renderer crash recovery and exponential backoff
- Tree normalization with auto-IDs, scoped IDs, and a11y reference resolution
- Tree diffing with four patch operations: `replace_node`, `update_props`,
  `insert_child`, `remove_child`
- Command system: `task`, `stream`, `cancel`, `send_after`, `focus`,
  `scroll`, `batch`, `exit`, and more
- Subscription lifecycle diffing (timers, key/mouse/window events)
- Effect system: file dialogs, clipboard, notifications with request tracking
- Type system: `Border`, `Shadow`, `Gradient`, `Font`, `StyleMap`, `Theme`,
  `A11y` with wire serialization via `to_wire()` methods
- Widget builder functions for all widget types (containers, interactive,
  display) via `plushie.ui`
- Canvas shape builders via `plushie.canvas`
- Event dataclasses for all event families (widget, key, mouse, touch,
  IME, window, canvas, timer, async, stream, effect, system)
- Testing framework: `AppFixture` with synchronous command processing,
  `SessionPool` for test parallelism, pytest plugin
- Three test backends: mock, headless, windowed
- Extension system for custom widgets (pure Python and native Rust)
- State management utilities: path-based state, animation, routing,
  selection, undo/redo, data query pipeline
- Binary resolution, download, and platform detection
- Dev server with file watching and live reload
- CLI: `run`, `connect`, `download`, `build`, `inspect`, `script`, `replay`
- Script-based testing with `.plushie` test scripts
