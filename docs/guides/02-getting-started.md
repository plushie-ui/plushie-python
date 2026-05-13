# Getting Started

This chapter covers the prerequisites: installing the Plushie Python
SDK, downloading the renderer binary, and running a minimal app.
Chapter 3 picks up from here and starts building Plushie Pad, the
running example for the rest of the guide.

## Prerequisites

Plushie requires **Python 3.12 or newer**. The SDK uses features that
landed in 3.12 (PEP 695 type alias syntax, `type` statement) and pins
`requires-python = ">=3.12"` in its project metadata. Earlier
interpreters will refuse to install the package.

Plushie works on Linux, macOS, and Windows. The renderer is a
precompiled Rust binary, so you do **not** need a Rust toolchain to
build apps. You only need Rust if you are compiling the renderer
yourself or adding native widget extensions.

## Installing the SDK

Install from PyPI with your package manager of choice:

```bash
pip install plushie
```

```bash
uv pip install plushie
```

```bash
poetry add plushie
```

The package name is `plushie`. The only runtime dependency is
`msgpack`, used for the wire protocol. Pin to an exact version
pre-1.0: the API is still evolving and minor bumps may contain
breaking changes.

```toml
# pyproject.toml
[project]
dependencies = [
    "plushie==0.6.0",
]
```

See the [Versioning reference](../reference/versioning.md) for the
relationship between the SDK version, the plushie-rust release it
targets, and the wire protocol.

## Downloading the renderer

Plushie apps talk to a renderer process (built on
[Iced](https://github.com/iced-rs/iced)) that draws native windows and
handles platform input. Fetch the precompiled renderer with:

```bash
python -m plushie download
```

The binary lands under the current project's `_build/plushie/bin/`
directory. Each app keeps its own renderer copy unless you explicitly
point `PLUSHIE_BINARY_PATH` somewhere else.

Every download is verified against the `.sha256` sidecar on GitHub
releases. A mismatch deletes the artifact and exits with an error;
there is no flag to skip verification. The version that downloads is
pinned by the SDK via `plushie.binary.PLUSHIE_RUST_VERSION`, so
`python -m plushie download` always fetches the renderer that matches
the installed SDK.

To use a binary you already have, export `PLUSHIE_BINARY_PATH`:

```bash
export PLUSHIE_BINARY_PATH=/path/to/plushie-renderer
```

For the full resolution chain (env var, bundled binary, custom build,
project-local download) see the
[CLI Commands reference](../reference/cli-commands.md).

### Building from source

If you want to build the renderer yourself, for example to track a
local plushie-rust checkout or to bundle native widget extensions:

```bash
git clone https://github.com/plushie-ui/plushie-rust ../plushie-rust
export PLUSHIE_RUST_SOURCE_PATH=../plushie-rust
python -m plushie build
```

This requires a Rust toolchain (1.92 or newer). The output binary
lands in `build/plushie-renderer/target/`, and `plushie.binary.resolve`
picks it up automatically. See the
[`build` subcommand](../reference/cli-commands.md#python--m-plushie-build)
for flags, extension discovery, and the relationship to
`cargo-plushie`.

## Your first app

Create a new project directory and add a file named `counter.py`:

```python
from dataclasses import dataclass, replace

import plushie
from plushie import ui
from plushie.events import Click


@dataclass(frozen=True, slots=True)
class Model:
    count: int = 0


class Counter(plushie.App[Model]):
    def init(self):
        return Model()

    def update(self, model, event):
        match event:
            case Click(id="inc"):
                return replace(model, count=model.count + 1)
            case Click(id="dec"):
                return replace(model, count=model.count - 1)
            case _:
                return model

    def view(self, model):
        return ui.window(
            "main",
            ui.column(
                ui.text("count", f"Count: {model.count}"),
                ui.row(
                    ui.button("inc", "+"),
                    ui.button("dec", "-"),
                    spacing=8,
                ),
                padding=16,
                spacing=8,
            ),
            title="Counter",
        )


if __name__ == "__main__":
    plushie.run(Counter)
```

A few things to notice:

- `Model` is a frozen dataclass with `slots=True`. The framework is
  generic over model type, and any type works, but frozen dataclasses
  are the recommended shape. Updates go through `dataclasses.replace`
  so each step produces a new value.
- `Counter` subclasses `plushie.App[Model]`, generic over the model
  type. The type parameter flows through `init`, `update`, and `view`,
  giving the type checker enough information to catch shape mismatches.
- `update` pattern-matches on the event class. The `Click` event
  carries an `id` field naming the widget that emitted it. Each event
  family is its own class (see the [Events reference](../reference/events.md)
  for the full taxonomy). No type discriminators, no stringly-typed
  dispatch.
- `view` returns a plain `dict`. The `ui` module exposes builder
  functions that return these dicts, but you can freely mix in raw
  dicts if you prefer. Container widgets take children as positional
  args and options as keyword args.
- The fallthrough `case _: return model` is deliberate. A missing
  branch returns `None`, and the runtime warns on `None` returns and
  keeps the previous model. See the
  [App lifecycle reference](../reference/app-lifecycle.md) for the
  full return-value contract.

## Running it

Point the CLI at the app class:

```bash
python -m plushie run counter:Counter
```

The specifier is `module:Class`. Everything before the colon is a
dotted module path resolved through the usual Python import machinery;
everything after is the `App` subclass to instantiate. You can use the
same form for packaged modules, for example
`myapp.screens.settings:SettingsApp`.

A native window appears with the count and two buttons. Click `+` and
`-` to see the count change. Close the window (or press Ctrl+C in the
terminal) to stop.

For the complete flag list (`--watch`, `--daemon`, `--mode`,
`--json`), see the
[`run` subcommand](../reference/cli-commands.md#python--m-plushie-run).

## Troubleshooting

A few errors are common on first install.

**`PlushieNotFoundError: plushie-renderer binary not found`.** The SDK
could not resolve a renderer. Run `python -m plushie download`, or
point `PLUSHIE_BINARY_PATH` at an existing binary. The error message
lists every path that was checked.

**`ProtocolVersionMismatchError`.** The installed renderer binary was
built against a different protocol version than the SDK expects. This
usually means the SDK was upgraded without re-downloading the
renderer. Run `python -m plushie download` to fetch the matching
version, or rebuild from source if you maintain a local checkout.
See the [Versioning reference](../reference/versioning.md) for the
full story.

**`ERROR: Package 'plushie' requires a different Python: ...`.** Your
interpreter is older than 3.12. Upgrade Python, or use a version
manager (pyenv, asdf, uv) to install 3.12 side-by-side:

```bash
uv python install 3.12
uv venv --python 3.12
```

**`ChecksumError`** during `download`. The renderer download failed
its SHA-256 verification and the artifact was deleted. This is almost
always a corrupted download; retry the command. If it happens
repeatedly, file an issue with the reported expected-versus-actual
digests.

**`ModuleNotFoundError: No module named 'counter'`.** The `run`
command resolves the module relative to your current directory (and
`PYTHONPATH`). Run the command from the directory containing
`counter.py`, or add that directory to `PYTHONPATH`.

---

Next: [Your First App](03-your-first-app.md) starts building Plushie
Pad, the example app the rest of the guide is built around.
