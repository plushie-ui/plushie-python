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
```

| Flag | Description |
|---|---|
| `app` | App specifier as `module:Class` (required) |

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
python -m plushie download --version 0.4.1    # specific version
python -m plushie download --force            # re-download if exists
```

| Flag | Description |
|---|---|
| `--bin` | Download the native binary. Default when no target specified. |
| `--wasm` | Download the WASM renderer bundle (`plushie_wasm.js` + `plushie_wasm_bg.wasm`). |
| `--version VERSION` | Version to download (e.g. `0.4.1`). Defaults to latest. |
| `--force` | Re-download even if the file already exists. |

Downloads are verified against SHA-256 checksums from the release.
The binary is saved to `~/.local/share/plushie/bin/` (Linux/macOS)
or `%LOCALAPPDATA%\plushie\bin\` (Windows). WASM files go to the
`wasm/` subdirectory.


## build

Build the plushie binary from source, optionally with native Rust
extensions.

```bash
python -m plushie build                       # stock binary from source
python -m plushie build --release             # optimized build
python -m plushie build --wasm                # WASM renderer
python -m plushie build --bin --wasm          # both
python -m plushie build --config ext.json     # with extensions
python -m plushie build --verbose             # show cargo output
```

| Flag | Description |
|---|---|
| `--bin` | Build the native binary. Default when no target specified. |
| `--wasm` | Build the WASM renderer via wasm-pack. |
| `--release` | Build with optimizations (default is debug). |
| `--verbose` | Print full cargo output on successful builds. |
| `--config CONFIG` | Path to extensions config JSON (default: `plushie_extensions.json`). |
| `--name NAME` | Output binary name (default: `plushie-custom`). |

### Prerequisites

- **Rust** 1.92+ (install via [rustup](https://rustup.rs/))
- **PLUSHIE_SOURCE_PATH** environment variable pointing to the
  plushie Rust source checkout (for stock builds)
- **wasm-pack** (for `--wasm` only) -- install via
  [wasm-pack.rustwasm.github.io](https://rustwasm.github.io/wasm-pack/)

### Stock build (no extensions)

When no extensions config is found, builds the vanilla plushie binary
from the Rust source at `PLUSHIE_SOURCE_PATH`:

```bash
export PLUSHIE_SOURCE_PATH=~/projects/plushie
python -m plushie build --release
```

The built binary is installed to the standard download location.

### Extension build

Extensions can be configured in `pyproject.toml` (preferred) or a
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

The build validates extensions (no duplicate widget types or crate
names), generates a Cargo workspace, runs `cargo build`, and
installs the built binary to the standard download location so
`resolve()` finds it automatically.

Configuration resolution:
- `--name` flag > `build_name` from pyproject.toml > `"plushie-custom"`
- `PLUSHIE_SOURCE_PATH` env > `source_path` from pyproject.toml

See [Extensions](extensions.md) for the full guide.


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
