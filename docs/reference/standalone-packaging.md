# Standalone Packaging

The first supported standalone shape for Python apps is a
PyInstaller host payload wrapped by the shared Rust package launcher.
PyInstaller owns the Python runtime and application files. The Rust
launcher owns the outer executable, payload extraction, cache
lifecycle, renderer-parent startup, and future update hooks.

## Shape

The packaged payload should contain:

- a PyInstaller one-folder build for the Python host
- a payload-local `bin/plushie-renderer`
- a `bin/connect` entry point or equivalent host command
- `payload.tar.zst`
- `plushie-package.toml`

The manifest is consumed by `cargo plushie package`. Paths in the
manifest are payload-relative, so the renderer path must point inside
the archived payload. A packaged app must not depend on a downloaded
renderer cache or a renderer found on `PATH`.

## Startup

The launcher starts the payload-local renderer with renderer-parent
socket mode, then starts the Python host through structured exec args.
The host should run:

```bash
python -m plushie connect myapp:App
```

When `PLUSHIE_SOCKET` is present, `python -m plushie connect` connects
to that socket and sends the `PLUSHIE_TOKEN` proof as `token_sha256`.
It does not spawn or discover another renderer.

## PyInstaller Mode

Use PyInstaller one-folder mode as the first supported internal
payload format. The shared Rust launcher already provides the outer
single executable, so one-file PyInstaller would add nested
self-extraction, more startup cost, and less inspectable smoke output.

One-file PyInstaller can still be evaluated later for projects that
need a Python-only artifact, but it is not the cross-SDK standalone
default.

## Demo Proof

The current proof lives in:

```text
plushie-demos/python/data-explorer
```

The demo package script builds the PyInstaller payload, adds the
payload-local renderer, then calls `python -m plushie package` to write
`plushie-package.toml`. `cargo plushie package` builds the outer
launcher from that manifest.

Strict artifact smoke runs the generated launcher from a temporary
working directory with a narrowed runtime `PATH`. The smoke requires
the shared renderer-parent ready marker and writes a report next to
the generated launcher recording payload size, launcher size, target,
host SDK, runtime path, exit status, and the renderer path reported by
launcher diagnostics.
