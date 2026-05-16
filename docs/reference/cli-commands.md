# CLI Commands

Plushie ships a single CLI entry point invoked as
`python -m plushie <command>`. It covers running apps, connecting to
a remote renderer, fetching or building the renderer binary,
inspecting view trees, and running test scripts. The implementation
lives in `plushie.__main__` with subcommand dispatch via `argparse`.

A repo-local `./preflight` script mirrors CI locally. It is not part
of the Python CLI; it is a bash script in the project root.

| Command | Purpose |
|---|---|
| [`run`](#python--m-plushie-run) | Run a Plushie app |
| [`connect`](#python--m-plushie-connect) | Standalone host entry point for packaged or socket startup |
| [`download`](#python--m-plushie-download) | Fetch a precompiled renderer binary or WASM bundle |
| [`build`](#python--m-plushie-build) | Build the renderer binary from source with extensions |
| [`package`](#python--m-plushie-package) | Assemble a package payload or write a manifest for a prepared payload |
| [`inspect`](#python--m-plushie-inspect) | Print the initial UI tree as JSON |
| [`script`](#python--m-plushie-script) | Run `.plushie` test scripts headlessly |
| [`replay`](#python--m-plushie-replay) | Replay a script with real windows |
| [`./preflight`](#preflight) | Run all CI checks locally |

App specifiers use the `module.path:ClassName` convention. The
segment before the colon is a dotted module path, the segment after
is an `App` subclass exported from that module. Example:
`myapp:Counter` or `myapp.screens.settings:SettingsApp`.

A `-v` / `--verbose` flag on the top-level parser raises the log
level to `DEBUG` for any subcommand.

## python -m plushie run

Runs a Plushie application. Resolves the renderer binary, spawns it
as a child process, starts the runtime, and blocks until the app
exits.

```bash
python -m plushie run myapp:Counter
python -m plushie run myapp:Counter --watch
python -m plushie run myapp:Counter --daemon
```

### Flags

| Flag | Description |
|---|---|
| `--mode {mock,headless}` | Renderer mode. Omit for a real windowed renderer |
| `--json` | Use JSON wire format instead of MessagePack |
| `--watch` | Enable file watching for live reload |
| `--daemon` | Keep running after all windows close |

### Daemon mode

Without `--daemon`, the runtime shuts down after the last window
closes. With `--daemon`, it keeps running so the app can open new
windows, show a tray menu, or react to `WindowEvent(type="closed")`
events without terminating. See [Events reference](events.md) for the
window event family.

### Live reload

`--watch` starts `plushie.dev_server.DevServer` instead of the
standard `plushie.run` entry point. The dev server spawns the
renderer, runs the app, and watches source directories (`src/`,
`lib/`, `.` in priority order, whichever exist) for `.py` file
changes. On change it reimports the app module, reinstantiates the
`App` class against the preserved model, calls `view`, and sends a
fresh snapshot.

The dev server prefers the `watchfiles` library if installed and
falls back to a polling watcher (1-second scan interval) otherwise.
A fixed 300 ms debounce coalesces rapid successive saves.

Model state is preserved across reloads. Widget state that lives in
the renderer (scroll offsets, focus, cursor position) resets because
the snapshot replaces the whole tree.

### JSON wire format

`--json` switches the wire protocol from MessagePack (the default) to
newline-delimited JSON. Each frame is a complete JSON object on its
own line, useful for piping into `jq` or tailing with `less`:

```bash
python -m plushie run myapp:Counter --json 2>protocol.log
```

For renderer-side tracing, set `RUST_LOG`:

```bash
RUST_LOG=plushie=debug python -m plushie run myapp:Counter --json
```

## python -m plushie connect

Runs a Plushie app from a standalone entry point. When `--socket` or
`PLUSHIE_SOCKET` is present, it connects to that renderer. Otherwise it
starts the renderer through normal binary resolution, including
`PLUSHIE_BINARY_PATH`.

```bash
plushie \
  --exec-bin python \
  --exec-arg -m \
  --exec-arg plushie \
  --exec-arg connect \
  --exec-arg myapp:Counter
```

### Flags

| Flag | Description |
|---|---|
| `--json` | Use JSON wire format instead of MessagePack |
| `--socket PATH_OR_ADDR` | Connect to an existing renderer socket |
| `--token TOKEN` | Authentication token for socket-mode startup |

In socket mode, stdout remains available to the caller and protocol
traffic goes through the socket. In spawn mode, the SDK starts the
renderer as a child process.

### Token resolution in socket mode

When `--socket` is set, the connect command resolves the negotiation
token using this precedence:

1. `--token` flag
2. `PLUSHIE_TOKEN` environment variable
3. A single JSON line read from stdin with a 1-second timeout

The stdin fallback covers launch environments where environment
variables cannot be forwarded (SSH exec, sandboxed process launches).
The renderer-parent writes `{"token": "..."}` on the child's stdin
before any other I/O.

If all three sources fail (stdin times out or is empty), the command
exits with:

```
renderer-parent token not provided: pass --token, set PLUSHIE_TOKEN, or write a JSON token line on stdin
```

If stdin data arrives but cannot be parsed as a JSON object with a
`"token"` string key, the command exits with:

```
renderer-parent token stdin must be JSON object with 'token' string
```

## python -m plushie download

Downloads a precompiled renderer binary or WASM bundle from GitHub
releases. The binary is platform-specific (OS and architecture) and
version-matched to the SDK via the `PLUSHIE_RUST_VERSION` constant in
`plushie.binary`.

```bash
python -m plushie download                 # native binary (default)
python -m plushie download --wasm          # WASM renderer
python -m plushie download --bin --wasm    # both
python -m plushie download --force         # re-download
```

### Flags

| Flag | Description |
|---|---|
| `--version VERSION` | Release version tag. Defaults to the pinned `PLUSHIE_RUST_VERSION` |
| `--bin` | Download the native binary (default when no selector is given) |
| `--wasm` | Download the WASM renderer tarball |
| `--force` | Re-download even if the files already exist |
| `--bin-file PATH` | Override the native binary destination path |
| `--wasm-dir PATH` | Override the WASM output directory |

When neither `--bin` nor `--wasm` is given, the command falls back to
the `artifacts` key in `[tool.plushie]` in `pyproject.toml`,
defaulting to `["bin"]`.

### Destinations

The managed native tool set lands in `bin/` under the current project:
`plushie`, `plushie-renderer`, and `plushie-launcher` (with `.exe` on
Windows). Release assets still use platform-specific filenames, but
local projects use stable names. `bin/plushie` owns renderer and
launcher sync.

The WASM bundle extracts to `_build/plushie-renderer/wasm/` and
produces `plushie_renderer_wasm.js` and
`plushie_renderer_wasm_bg.wasm`.

Both destinations are overridable via `--bin-file` / `--wasm-dir` on
the CLI, or via `bin_file` / `wasm_dir` in `[tool.plushie]` in
`pyproject.toml`.

### Checksum verification

Every download is verified against a `.sha256` sidecar fetched from
the same release. On mismatch or if the checksum file cannot be
fetched, the downloaded artifact is deleted and the command exits
with an error. There is no flag to skip verification.

### Release mirrors

By default downloads come from GitHub releases. Set
`PLUSHIE_RELEASE_BASE_URL` to verify the same flow against another
release mirror. The mirror must expose assets as
`BASE/vVERSION/ARTIFACT` with checksum sidecars at
`BASE/vVERSION/ARTIFACT.sha256`.

Remote mirrors must use HTTPS. `file://` mirrors and loopback HTTP are
for local release verification before assets are uploaded.

### Native extension refusal

When `[tool.plushie].extensions` is populated, `download --bin`
refuses to proceed and prints the configured widget kinds. A
precompiled binary cannot include project-specific native widgets;
use `python -m plushie build` instead. WASM download is unaffected.

## python -m plushie build

Builds the renderer binary (and optionally the WASM bundle) from a
local `plushie-rust` checkout or from crates.io via the
`cargo-plushie` subcommand. Required whenever the project declares
native widgets in `[tool.plushie].extensions` or whenever you work
against a local renderer checkout.

```bash
python -m plushie build              # debug build
python -m plushie build --release    # optimised
python -m plushie build --wasm       # WASM renderer
python -m plushie build --verbose    # print full cargo output on success
```

### Flags

| Flag | Description |
|---|---|
| `--bin` | Build the native binary (default when no selector is given) |
| `--wasm` | Build the WASM renderer via `wasm-pack` |
| `--release` | Build with optimisations |
| `--verbose` | Print full Cargo output on successful builds |
| `--config PATH` | Path to an extensions JSON config. Defaults to `plushie_extensions.json` |
| `--name NAME` | Output binary name. Defaults to `plushie-renderer` |

`--bin` and `--wasm` can be combined to build both artifacts in one
pass. When neither selector is given, the command honours
`artifacts` in `[tool.plushie]`, defaulting to `["bin"]`.

### Extension discovery

Native widgets are read from `[tool.plushie].extensions` in
`pyproject.toml`. Each entry has `kind`, `rust_crate`,
`rust_constructor`, and optional `props` and `commands` tables. The
build step injects `[package.metadata.plushie.widget]` into each
widget crate's own `Cargo.toml` so `cargo-plushie` can discover them
via `cargo metadata`, then writes a virtual app `Cargo.toml` under
`build/plushie-renderer-spec/` listing each widget crate as a path
dependency.

If `[tool.plushie].extensions` is empty, the command falls back to
`--config` (a JSON file, defaulting to `plushie_extensions.json`).

### Local source versus crates.io

By default, Rust dependencies come from crates.io at the pinned
`PLUSHIE_RUST_VERSION`. For work against a local plushie-rust
checkout, set `PLUSHIE_RUST_SOURCE_PATH` or `[tool.plushie].source_path`:

```bash
git clone https://github.com/plushie-ui/plushie-rust ../plushie-rust
PLUSHIE_RUST_SOURCE_PATH=../plushie-rust python -m plushie build
```

Equivalent `pyproject.toml`:

```toml
[tool.plushie]
source_path = "../plushie-rust"
```

With `PLUSHIE_RUST_SOURCE_PATH` set, the build emits
`[patch.crates-io]` redirecting plushie crates to the local checkout.

### WASM builds

```bash
python -m plushie build --wasm
python -m plushie build --wasm --release
```

WASM builds always run against a local plushie-rust checkout.
`PLUSHIE_RUST_SOURCE_PATH` (or `[tool.plushie].source_path`) must
point at one, and `wasm-pack` must be on `PATH`. The output files
(`plushie_renderer_wasm.js` and `plushie_renderer_wasm_bg.wasm`) copy
from the WASM crate's `pkg/` directory into the project-local WASM
directory, or `--wasm-dir` / `[tool.plushie].wasm_dir` when
overridden.

### Requirements

- Rust 1.92 or newer on `PATH` (checked via `rustc --version`).
- `cargo-plushie` at the matching `PLUSHIE_RUST_VERSION`, installed
  with `cargo install cargo-plushie --version <version> --locked`,
  or `PLUSHIE_RUST_SOURCE_PATH` set to a local plushie-rust checkout.
- For WASM: `wasm-pack` on `PATH` and a local plushie-rust checkout.

## python -m plushie package

Assembles a standalone Python package payload and delegates final
archiving and manifest completion to `cargo plushie package assemble`.
PyInstaller mode is the first-class SDK-owned path. The SDK resolves
or builds the renderer, copies it into the payload, runs PyInstaller,
writes a partial `plushie-package.toml`, and shells out to
`cargo plushie package assemble`. cargo-plushie handles archiving,
hashing, platform icon materialisation, and writing the final manifest.

```bash
python -m plushie package \
  --app-id dev.example.my_app \
  --app-name "My App" \
  --pyinstaller-entry src/my_app/__main__.py \
  --pyinstaller-name MyApp \
  --add-data "assets:assets" \
  --collect-submodules plushie
```

Prepared payload mode remains available for custom assembly flows. In
that mode the caller owns the payload directory and provides the start
command explicitly:

```bash
python -m plushie package \
  --app-id dev.example.my_app \
  --app-name "My App" \
  --renderer-path bin/plushie-renderer \
  --payload-dir dist/package/payload \
  --start-command host/MyApp/MyApp
```

### Flags

| Flag | Description |
|---|---|
| `--app-id ID` | Package app identifier. Required |
| `--app-name NAME` | Display app name |
| `--app-version VERSION` | App version. Defaults to `[project].version` or `0.1.0` |
| `--target TARGET` | Package target. Defaults to the current OS and architecture |
| `--renderer-kind stock|custom` | Renderer provenance kind. Defaults to `stock` |
| `--pyinstaller-entry PATH` | Build and assemble a PyInstaller payload from this entry script |
| `--pyinstaller-name NAME` | PyInstaller app name. Defaults to `--app-name` |
| `--app-icon PATH` | Icon file to pass to PyInstaller |
| `--add-data SOURCE:DEST` | Data mapping passed to PyInstaller. Repeatable |
| `--hidden-import MODULE` | Hidden import passed to PyInstaller. Repeatable |
| `--collect-submodules MODULE` | Module package whose submodules PyInstaller should collect. Repeatable |
| `--pyinstaller-arg ARG` | Extra argument passed through to PyInstaller. Repeatable |
| `--package-dir PATH` | Directory for payload and manifest. Defaults to `dist` |
| `--dist-dir PATH` | PyInstaller dist directory. Defaults to `dist` |
| `--spec-dir PATH` | PyInstaller spec output directory. Defaults to `build/pyinstaller-spec` |
| `--work-dir PATH` | PyInstaller work directory. Defaults to `build/pyinstaller` |
| `--renderer-path PATH` | Explicit renderer binary path in PyInstaller mode. Payload-relative renderer path in prepared mode, where it is required |
| `--payload-dir PATH` | Payload directory for prepared payloads. Required in prepared mode |
| `--start-command CMD...` | Start command for prepared payloads. Required in prepared mode |
| `--manifest-out PATH` | Manifest output file path in prepared payload mode |
| `--package-config PATH` | Config file forwarded to `cargo plushie package assemble`. cargo-plushie reads `working_dir`, `forward_env`, and `[platform]` from it |
| `--write-package-config` | Write a package config template and exit |

In PyInstaller mode, pass `--renderer-path PATH` to package a specific
renderer binary without going through stock renderer resolution.
Without that flag, `--renderer-kind custom` requires an explicit custom
renderer from `PLUSHIE_BINARY_PATH` or an earlier `python -m plushie
build`. Stock renderer resolution is not used for a custom package
manifest.

When `PLUSHIE_RUST_SOURCE_PATH` is set for stock renderer packaging,
the package command uses the same managed native-tool sync path as
`python -m plushie download`, so `bin/plushie`, `bin/plushie-renderer`,
and `bin/plushie-launcher` are prepared together from the checkout.

## python -m plushie inspect

Prints a Plushie app's initial UI tree as pretty-printed JSON,
without starting a renderer.

```bash
python -m plushie inspect myapp:Counter
```

The command imports the app class, calls `init`, unwraps the result
(discarding any initial commands), calls `view` against the initial
model, runs `plushie.tree.normalize` to assign auto-IDs and convert
prop values to wire-ready primitives, and prints the result via
`json.dumps(..., indent=2, default=str)`.

Useful for debugging layout nesting, verifying prop values without
opening a window, sanity-checking `view` with a fresh model, and
quick inspection in CI. No renderer binary is needed; everything
runs in Python.

## python -m plushie script

Runs `.plushie` automation scripts headlessly against the mock
backend. Each script starts a fresh app session, executes the
instructions, and reports pass or fail.

```bash
python -m plushie script                            # all scripts under test/scripts/ or tests/scripts/
python -m plushie script path/to/test.plushie       # specific script
python -m plushie script tests/smoke.plushie tests/api.plushie
```

Without arguments, the command globs `test/scripts/**/*.plushie`,
then `tests/scripts/**/*.plushie` as a fallback. If neither produces
matches, it prints an error and exits with status 1.

Each `.plushie` script carries a header naming the app, viewport,
theme, and backend. The script runner launches a shared
`SessionPool` (one per backend), opens an `AppFixture` per script,
runs the instruction list, and prints a `PASS` or `FAIL` marker.
Exit code is 0 when all scripts pass, 1 if any fail.

## python -m plushie replay

Replays a single `.plushie` script with the windowed backend. Real
windows appear on screen, GPU rendering is active, and `wait`
directives in the script are honoured in real time.

```bash
python -m plushie replay path/to/test.plushie
```

Useful for visually verifying automation, producing demo recordings,
and debugging interaction sequences that behave differently under
real rendering (timing, animation, focus transitions). Unlike
`script`, the backend is always `windowed`; the script's header
backend setting is ignored for replay.

## preflight

`./preflight` runs the full CI check suite locally, stopping at the
first failure.

```bash
./preflight
```

Steps, in order:

1. `ruff format --check src tests examples` - formatting.
2. `ruff check src tests examples` - lint.
3. `interrogate src/plushie/` - docstring coverage.
4. `pyright src tests examples` - static type checking.
5. `pytest` - test suite against the mock backend.

Each step streams its output directly to the terminal. On success
the script prints `All checks passed.` and exits 0. Running
`pytest --cov` afterwards produces an optional coverage report.

If preflight passes locally, CI will pass.

## Binary resolution

`plushie.binary.resolve` resolves the renderer binary in priority
order:

1. `PLUSHIE_BINARY_PATH` environment variable. If set but pointing at
   a missing file, raises immediately with a clear error; explicit
   config does not silently fall through.
2. Bundled binary in a packaged app (PyInstaller's `sys._MEIPASS`,
   adjacent to the installed `plushie` package, or adjacent to the
   frozen executable).
3. Custom extension build under `build/*/target/release/` then
   `build/*/target/debug/`, auto-detected after `python -m plushie
   build` as long as the binary is a native executable (not a
   Python script).
4. Downloaded binary at `bin/plushie-renderer` under the current
   project.

If nothing is found, the call raises `PlushieNotFoundError` with an
install hint listing the download and environment-variable options.

WASM resolution (`plushie.binary.resolve_wasm`) checks the standard
WASM directory for both `plushie_renderer_wasm.js` and
`plushie_renderer_wasm_bg.wasm`. Missing either file raises
`WasmNotFoundError`.

## Environment variables

| Variable | Effect |
|---|---|
| `PLUSHIE_BINARY_PATH` | Explicit path to the renderer binary. Errors if set but missing |
| `PLUSHIE_RUST_SOURCE_PATH` | Path to a local plushie-rust checkout. Switches builds to source mode, pins `cargo-plushie` to the checkout, and enables WASM builds |
| `PLUSHIE_TEST_BACKEND` | Selects the pytest test backend: `mock` (default), `headless`, or `windowed` |
| `RUST_LOG` | Passed through to the renderer for tracing-based logging |

## pyproject.toml keys

All keys live under `[tool.plushie]`:

```toml
[tool.plushie]
artifacts = ["bin", "wasm"]
bin_file = "dist/my-renderer"
wasm_dir = "static"
source_path = "../plushie-rust"
build_name = "my-renderer"

[[tool.plushie.extensions]]
kind = "star_rating"
rust_crate = "../crates/star-rating"
rust_constructor = "star_rating::StarRating::new"
```

Resolution order for any overlapping setting: CLI flags win, then
`pyproject.toml`, then environment variables, then defaults.

## See also

- [Events reference](events.md) - window, system, and widget event
  families referenced by `run --daemon`
- [Commands reference](commands.md) - commands returned from `init`
  and `update` that the runtime executes
- [Subscriptions reference](subscriptions.md) - the recurring timer
  model used by running apps
- [Versioning reference](versioning.md) - the relationship between
  the SDK version, `PLUSHIE_RUST_VERSION`, and the renderer binary
- [Built-in Widgets reference](built-in-widgets.md) - widgets
  available without a custom `build`
