# Configuration

Plushie is configured at four levels: CLI flags on `python -m plushie`
commands, a `[tool.plushie]` table in `pyproject.toml`, environment
variables, and app-level callbacks (`App.settings`, `App.window_config`)
that ship defaults to the renderer at handshake and window-open time.
Most projects need minimal configuration: download the binary and go.

## Resolution order

Where multiple layers can supply the same value, more specific layers
win:

1. CLI flags passed to `python -m plushie <command>`
2. `[tool.plushie]` keys in `pyproject.toml`
3. Environment variables
4. Built-in defaults

`PLUSHIE_BINARY_PATH` is the single exception. When set, it overrides
every other source for binary resolution (including a custom build in
`build/`) and raises immediately if the file is missing. Explicit
config is not silently ignored.

## Environment variables

| Variable | Purpose |
|---|---|
| `PLUSHIE_BINARY_PATH` | Explicit path to the renderer binary. Overrides all other binary resolution. Raises if the file is missing. |
| `PLUSHIE_RUST_SOURCE_PATH` | Path to a local [plushie-rust](https://github.com/plushie-ui/plushie-rust) checkout for source builds and the WASM build. |
| `PLUSHIE_TEST_BACKEND` | Test backend: `mock` (default), `headless`, or `windowed`. |

### PLUSHIE_BINARY_PATH

Forces a specific renderer binary. Useful in CI where the binary is
pre-built at a known path, or in production deployments where the
binary ships alongside the Python package. Checked first in
`plushie.binary.resolve()`. If set but pointing to a missing file,
resolution raises `PlushieNotFoundError` rather than falling through
to other lookup paths.

### PLUSHIE_RUST_SOURCE_PATH

Points to a local checkout of the plushie-rust repository. Read by
`python -m plushie build` (via `_cmd_build`) and by
`plushie.binary.build_wasm` when building the WASM renderer from
source. The typical setup is a sibling directory:

```bash
git clone https://github.com/plushie-ui/plushie-rust ../plushie-rust
PLUSHIE_RUST_SOURCE_PATH=../plushie-rust python -m plushie build
```

When both the env var and `[tool.plushie]` `source_path` are set, the
env var wins.

### PLUSHIE_TEST_BACKEND

Selects the renderer backend used by the pytest fixture and session
pool. Read by `plushie.testing.plugin` at test collection time.

| Value | Behavior |
|---|---|
| `mock` (default) | `plushie --mock` backend, no rendering, pure message exchange |
| `headless` | real rendering pipeline, no display output |
| `windowed` | real windows, requires a display |

## pyproject.toml

Plushie reads an optional `[tool.plushie]` table from the project's
`pyproject.toml`. `python -m plushie download` and `python -m plushie
build` consume it via `_load_pyproject_config`. A malformed or
missing file silently yields an empty config: no error, no warning.

```toml
[tool.plushie]
artifacts = ["bin", "wasm"]
bin_file = "bin/plushie-renderer"
wasm_dir = "static"
source_path = "../plushie-rust"
build_name = "acme-plushie"

[[tool.plushie.extensions]]
kind = "sparkline"
rust_crate = "native/sparkline"
rust_constructor = "sparkline::new()"
```

### Keys

| Key | Type | Default | Purpose |
|---|---|---|---|
| `artifacts` | `list[str]` | `["bin"]` | Which artifacts `download` and `build` install. Accepts `"bin"`, `"wasm"`, or both. An explicit empty list installs nothing. |
| `bin_file` | `str` | `None` | Override the destination path for the native binary. Without it, downloads land under `bin/` in the project. |
| `wasm_dir` | `str` | `None` | Override the output directory for WASM artifacts. Without it, downloads land under `_build/plushie-renderer/wasm/` in the project. |
| `source_path` | `str` | `None` | Rust source checkout path for source builds. The `PLUSHIE_RUST_SOURCE_PATH` env var takes precedence. |
| `build_name` | `str` | `"plushie-custom"` | Name for the binary produced by `python -m plushie build`. Overridden by the `--name` CLI flag. |
| `extensions` | array of tables | `[]` | Native widget definitions compiled into the binary. See [Native extensions](#native-extensions). |

When `[tool.plushie.extensions]` is present, `python -m plushie
download` refuses to fetch a precompiled binary: the extensions would
not be baked in. Use `python -m plushie build` instead.

### CLI flag overrides

| CLI flag | Overrides pyproject key |
|---|---|
| `--bin` | `artifacts` |
| `--wasm` | `artifacts` |
| `--bin-file` | `bin_file` |
| `--wasm-dir` | `wasm_dir` |
| `--name` | `build_name` |
| `--config` | `extensions` source file (falls back to `plushie_extensions.json`) |

Passing `--wasm` alone installs the WASM bundle only, even if
`artifacts = ["bin", "wasm"]` is set. CLI flags are authoritative for
the invocation.

## Native extensions

The `extensions` array declares Rust-backed custom widgets that
`cargo-plushie` compiles into a custom renderer binary. Each entry is
a TOML table with `kind`, `rust_crate`, `rust_constructor`, and
optional `props` and `commands` lists:

```toml
[[tool.plushie.extensions]]
kind = "gauge"
rust_crate = "native/gauge"
rust_constructor = "gauge::new()"

  [[tool.plushie.extensions.props]]
  name = "value"
  prop_type = "number"

  [[tool.plushie.extensions.props]]
  name = "label"
  prop_type = "string"

  [[tool.plushie.extensions.commands]]
  name = "set_value"

    [[tool.plushie.extensions.commands.params]]
    name = "value"
    param_type = "number"
```

`_parse_extensions` turns each table into a `plushie.native_widget.NativeWidget`.
The fields map to its constructor arguments. See the
[Custom Widgets reference](custom-widgets.md) for the full widget
definition model, including `clone_for_session` requirements.

## App.settings() callback

The optional `App.settings` callback provides application-level
defaults to the renderer at handshake time. The returned dict is sent
once during the initial `settings` message (see
`plushie.protocol.settings`) and applies to every window.

```python
from typing import Any

import plushie
from plushie import ui


class MyApp(plushie.App[dict]):
    def settings(self) -> dict[str, Any]:
        return {
            "default_text_size": 16,
            "theme": "dark",
            "fonts": ["priv/fonts/inter.ttf"],
            "default_event_rate": 60,
        }

    def init(self) -> dict:
        return {}

    def update(self, model, event):
        return model

    def view(self, model):
        return ui.window("main", ui.text("Hello"), title="MyApp")
```

### Recognized keys

| Key | Type | Purpose |
|---|---|---|
| `default_font` | `dict` | Default font specification. Same shape as font props on widgets. |
| `default_text_size` | `float` | Default text size in pixels for every text widget. |
| `antialiasing` | `bool` | Enable font antialiasing. |
| `vsync` | `bool` | Synchronize frame presentation with the display refresh rate. |
| `scale_factor` | `float` | Multiplier applied on top of OS DPI scaling. Per-window `scale_factor` props override this. |
| `theme` | `str \| dict` | Built-in theme name (`"dark"`, `"light"`, `"nord"`, `"system"`, etc.) or a custom palette dict. |
| `fonts` | `list[str]` | Paths to font files to load. Loaded fonts become available to any widget's `font` prop by family name. |
| `default_event_rate` | `int` | Maximum events per second for coalescable event types (pointer moves, scroll, slider drags, animation frames). Per-subscription `max_rate` and per-widget `event_rate` override this. See the [Subscriptions reference](subscriptions.md#rate-limiting). |
| `widget_config` | `dict` | Per-kind config for native widgets. Keyed by widget `kind`; values are forwarded to the widget on the Rust side. Transparently renamed to `extension_config` on the wire by `protocol.settings`. |
| `required_widgets` | `list[str]` | Widget kinds the renderer must recognize. The renderer validates the list during handshake and emits a `required_widgets_missing` diagnostic for any names it does not know. Non-fatal. |

All keys are optional. An empty dict (the default) uses the renderer's
own defaults.

## App.window_config(model) callback

`App.window_config(model)` returns default properties for every window
opened during the session. The runtime merges the result with the
per-window props in the view tree; tree props win on conflict.

```python
class MyApp(plushie.App[Model]):
    def window_config(self, model: Model) -> dict[str, Any]:
        return {
            "title": "MyApp",
            "width": 1024,
            "height": 768,
            "theme": model.theme,
        }

    def view(self, model):
        return ui.window("main", ui.text("content"))
```

Because `window_config` receives the current model, defaults can
depend on app state (theme, locale, user preferences). If it raises,
the runtime logs the exception and opens the window with the view
tree's props alone.

## Runtime options

`plushie.run` and `plushie.start` accept a handful of keyword arguments
that apply at runtime:

| Argument | Type | Default | Purpose |
|---|---|---|---|
| `binary_path` | `str \| None` | auto-resolved | Explicit binary path. Equivalent to setting `PLUSHIE_BINARY_PATH` for this invocation. |
| `mode` | `str \| None` | `None` (windowed) | Renderer mode: `"mock"`, `"headless"`, or `None` for windowed. |
| `daemon` | `bool` | `False` | When `True`, `AllWindowsClosed` does not stop the runtime. New windows can be opened later. |
| `format` | `str` | `"msgpack"` | Wire format: `"msgpack"` or `"json"`. JSON is slower but human-readable for debugging. Forwarded to `Connection.open` via `**connection_opts`. |
| `max_sessions` | `int \| None` | `None` | Enables multiplexed mode (`--max-sessions` on the renderer). Used by the testing pool. |
| `expected_widgets` | `list[str \| NativeWidget]` | `None` | Widget kinds the app expects. The SDK validates them against the renderer's `hello` reply before the runtime starts. |

```python
import plushie

plushie.run(MyApp, daemon=True, format="json")
```

`python -m plushie run` maps `--json` to `format="json"` and `--mode`
to `mode=`.

## See also

- [Commands reference](commands.md)
- [Events reference](events.md)
- [Subscriptions reference](subscriptions.md)
- [Built-in Widgets reference](built-in-widgets.md)
- [Versioning reference](versioning.md)
