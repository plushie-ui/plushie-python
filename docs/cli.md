# CLI reference

The `plushie` command-line interface provides commands for running apps,
downloading binaries, building custom renderers, and testing.

```bash
python -m plushie <command> [options]
```

Or if installed via pip:

```bash
plushie <command> [options]
```

Global options:

| Flag | Description |
|---|---|
| `-v`, `--verbose` | Enable verbose logging |
| `-h`, `--help` | Show help |


## run

Start a plushie application.

```bash
python -m plushie run myapp:Counter
python -m plushie run myapp:Counter --json
python -m plushie run myapp:Counter --watch
python -m plushie run myapp:Counter --daemon
python -m plushie run myapp:Counter --mode headless
```

| Flag | Description |
|---|---|
| `app` | App specifier as `module:Class` (required) |
| `--mode {mock,headless}` | Renderer mode. Omit for windowed (default). |
| `--json` | Use JSON wire format instead of MessagePack (useful for debugging). |
| `--watch` | Enable file watching for live reload. Reimports the app module on `.py` file changes, preserving the model state. Uses [watchfiles](https://pypi.org/project/watchfiles/) when available, falls back to polling. |
| `--daemon` | Keep the runtime alive after all windows close. Useful for server-side apps that accept reconnections. |

The app specifier uses `module:Class` format. The module is imported
via Python's standard import machinery, so it must be on the Python
path:

```bash
# From the project directory
python -m plushie run myapp.counter:Counter

# With PYTHONPATH
PYTHONPATH=src python -m plushie run myapp.counter:Counter
```


## connect

Start an app in stdio transport mode. Used when the renderer spawns
the Python process via `plushie --exec`.

```bash
plushie --exec "python -m plushie connect myapp:Dashboard"
plushie --json --exec "python -m plushie connect --json myapp:Dashboard"
```

| Flag | Description |
|---|---|
| `app` | App specifier as `module:Class` (required) |
| `--json` | Use JSON wire format instead of msgpack |

The Python process reads from stdin and writes to stdout using the
wire protocol. Stderr is available for logging. This is the
foundation for remote rendering over SSH:

```bash
plushie --exec "ssh server 'cd /app && python -m plushie connect dashboard:App'"
```


## download

Download precompiled plushie binaries from GitHub releases.

```bash
python -m plushie download                    # native binary (default)
python -m plushie download --wasm             # WASM renderer only
python -m plushie download --bin --wasm       # both
python -m plushie download --version 0.5.1    # specific version
python -m plushie download --force            # re-download if exists
```

| Flag | Description |
|---|---|
| `--bin` | Download the native binary. Default when no target specified. |
| `--wasm` | Download the WASM renderer bundle (`plushie_renderer_wasm.js` + `plushie_renderer_wasm_bg.wasm`). |
| `--version VERSION` | Version to download (e.g. `0.5.1`). Defaults to pinned version. |
| `--force` | Re-download even if the file already exists. |
| `--bin-file PATH` | Override native binary destination (default: `~/.local/share/plushie/bin/`). |
| `--wasm-dir PATH` | Override WASM output directory (default: `~/.local/share/plushie/wasm/`). |

Downloads are verified against SHA-256 checksums from the release.
The binary is saved to `~/.local/share/plushie/bin/` (Linux/macOS)
or `%LOCALAPPDATA%\plushie\bin\` (Windows). WASM files go to the
`wasm/` subdirectory.

Both `download` and `build` respect artifact configuration from
`pyproject.toml`. See [Project configuration](#project-configuration)
below.


## build

Build a custom plushie renderer binary wired to your native widgets.
The command delegates workspace generation and the underlying
`cargo build` to `cargo-plushie`; see
[Versioning](versioning.md) for how to install the matching
build tool.

```bash
python -m plushie build                       # build with extensions
python -m plushie build --release             # optimized build
python -m plushie build --wasm                # WASM renderer
python -m plushie build --bin --wasm          # both
python -m plushie build --config ext.json     # JSON-configured extensions
python -m plushie build --verbose             # stream cargo output
```

| Flag | Description |
|---|---|
| `--bin` | Build the native binary. Default when no target specified. |
| `--wasm` | Build the WASM renderer via wasm-pack. |
| `--release` | Build with optimizations (default is debug). |
| `--verbose` | Print full cargo output on successful builds. |
| `--config CONFIG` | Path to extensions config JSON (default: `plushie_extensions.json`). |
| `--name NAME` | Output binary name (default: `plushie-renderer`). |

### Prerequisites

- **Rust** 1.92+ (install via [rustup](https://rustup.rs/))
- **cargo-plushie**, installed at the matching `PLUSHIE_RUST_VERSION`
  (`cargo install cargo-plushie --version <PLUSHIE_RUST_VERSION> --locked`).
  Alternatively, set `PLUSHIE_RUST_SOURCE_PATH` to a plushie-rust
  checkout; the SDK then invokes `cargo run -p cargo-plushie`.
- **wasm-pack** (for `--wasm` only), install via
  [wasm-pack.rustwasm.github.io](https://rustwasm.github.io/wasm-pack/)

### Extension build

Extensions are configured in `pyproject.toml` (preferred) or a
JSON file:

**pyproject.toml** (recommended):

```toml
[tool.plushie]
source_path = "~/projects/plushie"
build_name = "my-app-plushie"

[[tool.plushie.extensions]]
kind = "gauge"
rust_crate = "native/my_gauge"
rust_constructor = "my_gauge::GaugeExtension::new()"
```

**JSON** (alternative):

```json
{
  "extensions": [
    {
      "kind": "gauge",
      "rust_crate": "native/my_gauge",
      "rust_constructor": "my_gauge::GaugeExtension::new()"
    }
  ]
}
```

Then build:

```bash
python -m plushie build --release
```

The SDK injects a `[package.metadata.plushie.widget]` block into each
widget crate's `Cargo.toml`, writes a virtual app `Cargo.toml` under
`build/plushie-renderer-spec/`, and shells out to
`cargo plushie build --manifest-path <spec>/Cargo.toml`. The
resulting binary is copied into the standard download location so
`resolve()` finds it automatically.

Configuration resolution:

- `--name` flag > `build_name` from pyproject.toml > `"plushie-renderer"`
- `PLUSHIE_RUST_SOURCE_PATH` env > `source_path` from pyproject.toml

See [Extensions](extensions.md) for the full guide and
[Versioning](versioning.md) for how SDK versions relate to
plushie-rust releases.


## Project configuration

The `download` and `build` commands read artifact settings from
`[tool.plushie]` in `pyproject.toml`. This lets you configure what
gets downloaded or built, and where it goes, without CLI flags.

```toml
[tool.plushie]
# What artifacts to install (replaces --bin / --wasm flags)
# Default: ["bin"]. Options: "bin", "wasm"
artifacts = ["bin", "wasm"]

# Where to put the native binary (replaces --bin-file flag)
# Default: standard download location (~/.local/share/plushie/bin/)
bin_file = "bin/plushie-renderer"

# Where to put WASM files (replaces --wasm-dir flag)
# Default: standard WASM location (~/.local/share/plushie/wasm/)
wasm_dir = "static/wasm"
```

**Resolution order** (matching the Elixir SDK pattern):

| Setting | CLI flag | pyproject.toml | Default |
|---|---|---|---|
| What to download/build | `--bin` / `--wasm` | `artifacts` | `["bin"]` |
| Binary destination | `--bin-file` | `bin_file` | standard location |
| WASM destination | `--wasm-dir` | `wasm_dir` | standard location |

CLI flags always win. If no CLI flags are given, `artifacts`
determines what to download or build. If `artifacts` is also absent,
the default is `["bin"]` only.

For example, a collaborative web app could use:

```toml
[tool.plushie]
artifacts = ["bin", "wasm"]
wasm_dir = "static"
```

Then a bare `python -m plushie download` fetches both the native
binary (to the standard location) and WASM files (to `static/`).

For the `build` command, `bin_file` controls an additional install
location. The binary is always installed to the standard download
directory, and also copied to `bin_file` if set.


## inspect

Print the initial UI tree as JSON without starting the renderer.
Useful for debugging view functions.

```bash
python -m plushie inspect myapp:Counter
```

| Flag | Description |
|---|---|
| `app` | App specifier as `module:Class` (required) |

Calls `init()`, then `view(model)`, normalizes the tree, and prints
it as formatted JSON to stdout.


## script

Run `.plushie` test scripts.

```bash
python -m plushie script tests/scripts/*.plushie
python -m plushie script test_counter.plushie test_todo.plushie
```

| Flag | Description |
|---|---|
| `files` | One or more `.plushie` script files to run. |

Scripts provide a declarative format for describing interaction
sequences. See [Testing](testing.md) for the `.plushie` format
reference.


## replay

Replay a `.plushie` script with real windows, honouring `wait`
timings so interactions are visible in real time.

```bash
python -m plushie replay test_counter.plushie
```

| Flag | Description |
|---|---|
| `file` | A single `.plushie` script file to replay. |

Forces windowed backend regardless of the script's `backend` header.
Useful for debugging visual issues, demos, and onboarding.
