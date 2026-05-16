# Standalone Packaging

The first supported standalone shape for Python apps is a
PyInstaller host payload wrapped by the shared Rust package launcher.
PyInstaller owns the Python runtime and application files. The Rust
launcher owns the outer executable, payload extraction, cache
lifecycle, shared-launcher startup, and future update hooks.

## Shape

The packaged payload contains:

- a PyInstaller one-folder build for the Python host under `host/`
- a payload-local `bin/plushie-renderer`
- a partial `plushie-package.toml` written by the Python SDK
- the final `plushie-package.toml` completed by `cargo plushie package assemble`

The manifest is consumed by `bin/plushie package portable` for the
self-extracting artifact or by `bin/plushie package bundle` for
platform packages. Paths in the manifest are payload-relative, so the
renderer path must point inside the payload directory. A packaged app
must not depend on a downloaded renderer cache or a renderer found on
`PATH`.

## Startup

The shared launcher is host-first. It extracts the payload, sets
`PLUSHIE_BINARY_PATH` to the payload-local renderer, and starts the
Python host command from `start.command`. The Python host then starts
that renderer through the normal SDK path.

Renderer-parent startup is still available for explicit embedding and
debug flows through `python -m plushie connect`, where the renderer sets
`PLUSHIE_SOCKET` and the host sends the `PLUSHIE_TOKEN` proof as
`token_sha256`. It is not the default shared package startup path.

## PyInstaller Mode

Use PyInstaller one-folder mode as the first supported internal
payload format. The shared Rust launcher already provides the outer
single executable, so one-file PyInstaller would add nested
self-extraction, more startup cost, and less inspectable postcheck output.

One-file PyInstaller can still be evaluated later for projects that
need a Python-only artifact, but it is not the cross-SDK standalone
default.

Build the payload through the SDK-owned package command:

```bash
python -m plushie package \
  --app-id dev.example.myapp \
  --app-name "My App" \
  --pyinstaller-entry src/myapp/__main__.py \
  --pyinstaller-name MyApp \
  --add-data "assets:assets" \
  --hidden-import myapp \
  --collect-submodules plushie
```

The command resolves or builds the renderer, copies it into the
payload under `bin/`, runs PyInstaller, places the PyInstaller
one-folder output under `host/`, writes a partial manifest, then
shells out to `cargo plushie package assemble`. cargo-plushie archives
the payload, computes its hash and size, materializes platform icons,
and writes the final `plushie-package.toml`.

Pass `--renderer-path PATH` in PyInstaller mode to package a specific
renderer binary. This bypasses stock renderer resolution while keeping
the payload-local manifest path at `bin/plushie-renderer`.

Pass `--package-config PATH` to forward a `plushie-package.config.toml`
path to `cargo plushie package assemble`. cargo-plushie reads the config
for `working_dir`, `forward_env`, and `[platform]` fields.

Prepared payloads remain supported for custom assembly flows. The
caller assembles the payload directory, then the SDK writes a partial
manifest and invokes assemble:

```bash
python -m plushie package \
  --app-id dev.example.myapp \
  --renderer-path bin/plushie-renderer \
  --payload-dir dist/package/payload \
  --start-command host/MyApp/MyApp
```

## Platform metadata

Optional metadata for the package manifest is declared in
`plushie-package.config.toml` under `[platform]`. cargo-plushie reads
this file during `package assemble`:

```toml
config_version = 1

[start]
working_dir = "."
command = ["host/MyApp/MyApp"]
# forward_env = ["PATH", "HOME", ...]

# [platform]
# publisher = "Example Corp"
# copyright = "Copyright 2025 Example Corp"
# category = "Productivity"
# description = "A desktop app built with Plushie"
# bundle_id = "com.example.myapp"
#
# [platform.macos]
# bundle_version = "1"
#
# [platform.windows]
# install_scope = "perUser"  # or "perMachine"
```

All fields are optional. Set `--write-package-config` to generate a
config template:

```bash
python -m plushie package --write-package-config --pyinstaller-name MyApp
```

## Demo Proof

The current proof lives in:

```text
plushie-demos/python/data-explorer
```

The demo package script delegates PyInstaller payload assembly to
`python -m plushie package --pyinstaller-entry`. `bin/plushie package
portable` builds the self-extracting launcher from the generated
manifest, and `bin/plushie package bundle` is the platform-package path
backed by cargo-packager.

Strict artifact postcheck runs the portable launcher from a temporary
working directory with a narrowed runtime `PATH`. The artifact
postcheck checks launcher diagnostics plus process liveness or clean
host exit until a stronger host-first readiness signal exists. It writes
a report next to the portable launcher recording payload size, launcher
size, target, host SDK, runtime path, exit status, and the renderer path
reported by launcher diagnostics.
