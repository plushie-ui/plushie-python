# Standalone Packaging

The first supported standalone shape for Python apps is a
PyInstaller host payload wrapped by the shared Rust package launcher.
PyInstaller owns the Python runtime and application files. The Rust
launcher owns the outer executable, payload extraction, cache
lifecycle, shared-launcher startup, and future update hooks.

## Shape

The packaged payload should contain:

- a PyInstaller one-folder build for the Python host
- a payload-local `bin/plushie-renderer`
- a host command pointing at the PyInstaller executable
- `payload.tar.zst`
- `plushie-package.toml`

The manifest is consumed by `bin/plushie package portable` for the
self-extracting artifact or by `bin/plushie package bundle` for
platform packages. Paths in the manifest are payload-relative, so the
renderer path must point inside the archived payload. A packaged app
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
one-folder output under `host/`, materializes platform icons, writes
`payload.tar.zst`, then writes `plushie-package.toml` with the final
archive hash and size. If `--app-icon` is provided, that file is
copied into the payload and recorded in the manifest. Otherwise the
command asks `bin/plushie default-icons` to export Plushie's
bundled default icons into the payload.

Pass `--renderer-path PATH` in PyInstaller mode to package a specific
renderer binary. This bypasses stock renderer resolution while keeping
the payload-local manifest path at `bin/plushie-renderer`.

After writing the manifest the command prints the handoff:

```
Build launcher with:
  bin/plushie package portable --manifest dist/package/plushie-package.toml
```

Run the handoff command to build the portable launcher. For release
builds that require the strict tool gate:

```bash
bin/plushie package check --manifest dist/package/plushie-package.toml --strict-tools
bin/plushie package portable --manifest dist/package/plushie-package.toml --strict-tools
```

Prepared payloads remain supported for custom assembly flows. Start
command and working directory come from `plushie-package.config.toml`:

```bash
python -m plushie package --write-package-config --pyinstaller-name MyApp
# edit plushie-package.config.toml as needed

python -m plushie package \
  --app-id dev.example.myapp \
  --renderer-path bin/plushie-renderer \
  --payload-archive dist/package/payload.tar.zst
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
