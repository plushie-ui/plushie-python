# Packaging and Distribution

`python -m plushie package` turns a Plushie app into a self-contained
artifact that ships with its own Python runtime and Plushie renderer.
The output is either a portable single-file executable or an OS-native
installer (AppImage, `.dmg`, `.msi`). The recipient does not need
Python, a virtualenv, or anything else installed.

When the artifact runs, the launcher extracts the payload, starts the
PyInstaller-built host executable, and the host starts its renderer
from inside the payload. The flow is the same as `python -m plushie
run`, just running from an extracted directory instead of your
project.

| Section | Topic |
|---|---|
| [Quickstart](#quickstart) | Three commands from a working app to a portable artifact |
| [The packaging pipeline](#the-packaging-pipeline) | How the SDK, cargo-plushie, and the launcher hand off |
| [python -m plushie package](#python--m-plushie-package) | Command flags and what the SDK owns |
| [The payload](#the-payload) | What goes in `dist/payload/` |
| [Source layout](#source-layout) | What to commit and what to gitignore |
| [Renderer selection](#renderer-selection) | Stock versus custom |
| [Bundled assets](#bundled-assets) | Icons, fonts, and other payload files |
| [Runtime bundling with PyInstaller](#runtime-bundling-with-pyinstaller) | One-folder mode, asset resolution, slimming |
| [The managed tool set](#the-managed-tool-set) | `bin/plushie`, renderer, launcher |
| [The partial manifest](#the-partial-manifest) | TOML the SDK writes |
| [Package config](#package-config) | `plushie-package.config.toml` schema |
| [Forwarded environment](#forwarded-environment) | Host process environment policy |
| [Building artifacts](#building-artifacts) | Portable executable and OS installers |
| [Distribution](#distribution) | Release asset layout |
| [Continuous integration](#continuous-integration) | GitHub Actions workflow |
| [Signing](#signing) | Developer-driven signing hooks |
| [Updates](#updates) | `[updates]` schema |
| [Host-first versus renderer-parent](#host-first-versus-renderer-parent) | Default launch model and the alternative |

## Quickstart

Three commands take a working app to a portable artifact:

```bash
python -m plushie download                                                  # install Plushie tool set
python -m plushie package \
  --app-id dev.example.my_app \
  --pyinstaller-entry src/my_app/__main__.py \
  --pyinstaller-name MyApp                                                  # build payload + manifest
bin/plushie package portable --manifest dist/plushie-package.toml           # produce the artifact
```

Output lands under `target/plushie/package/`. `--app-id` is the only
strictly required flag; PyInstaller mode also needs an entry script
and a name.

## The packaging pipeline

A packaged app moves through three stages:

1. **SDK build.** `python -m plushie package` resolves or builds the
   renderer, copies it into `dist/payload/bin/`, runs
   PyInstaller in one-folder mode to produce the Python host under
   `dist/payload/host/<name>/`, and emits a partial
   `dist/plushie-package.toml` carrying SDK identity, version
   pins, target triple, the start command, and the renderer
   descriptor.
2. **Manifest assembly.** `python -m plushie package` then shells out
   to `bin/plushie package assemble`. cargo-plushie validates the
   payload, reads `plushie-package.config.toml` for `[start]`
   defaults and `[platform]` metadata, copies bundled assets into the
   payload, materializes the icon, archives the payload, computes
   its SHA-256 and size, and fills in the rest of
   `plushie-package.toml`.
3. **Artifact build.** `bin/plushie package portable` produces a
   self-extracting single-file executable. `bin/plushie package
   bundle` produces OS-native installers via
   [cargo-packager](https://github.com/crabnebula-dev/cargo-packager).
   Both consume the same completed manifest.

Stage 1 is Python-specific. Stages 2 and 3 are language-agnostic and
shared across every Plushie SDK; the same `bin/plushie` tool that
assembles a Python payload assembles an Elixir or Ruby payload.

## python -m plushie package

Stage 1 of the pipeline. The command resolves or builds the
renderer, builds the PyInstaller payload, writes the partial
manifest, and shells to `bin/plushie package assemble` to complete
it.

| Flag | Description |
|---|---|
| `--app-id ID` | Package app identifier. Required. |
| `--app-name NAME` | Display app name. Used by cargo-plushie for OS-native bundles. |
| `--app-version VERSION` | App version. Defaults to `[project].version` from `pyproject.toml` or `0.1.0`. |
| `--target TARGET` | Package target. Defaults to the current OS and architecture. |
| `--renderer-kind stock\|custom` | Renderer provenance kind. Defaults to `stock`. |
| `--pyinstaller-entry PATH` | Build a PyInstaller payload from this entry script. |
| `--pyinstaller-name NAME` | PyInstaller app name. Defaults to `--app-name`. |
| `--app-icon PATH` | Icon file passed to PyInstaller. |
| `--add-data SOURCE:DEST` | Data mapping forwarded to PyInstaller. Repeatable. |
| `--hidden-import MODULE` | Hidden import forwarded to PyInstaller. Repeatable. |
| `--collect-submodules MODULE` | Module whose submodules PyInstaller should collect. Repeatable. |
| `--pyinstaller-arg ARG` | Extra argument forwarded to PyInstaller. Repeatable. |
| `--package-dir PATH` | Directory for payload and manifest. Defaults to `dist`. |
| `--dist-dir PATH` | PyInstaller dist directory. Defaults to `dist`. |
| `--spec-dir PATH` | PyInstaller spec output directory. Defaults to `build/pyinstaller-spec`. |
| `--work-dir PATH` | PyInstaller work directory. Defaults to `build/pyinstaller`. |
| `--renderer-path PATH` | Use a specific renderer binary. Skips stock resolution in PyInstaller mode; required in prepared mode. |
| `--payload-dir PATH` | Caller-assembled payload directory. Switches to prepared payload mode. |
| `--start-command CMD...` | Start command for prepared payloads. Required in prepared mode. |
| `--manifest-out PATH` | Manifest output path in prepared payload mode. |
| `--package-config PATH` | `plushie-package.config.toml` path forwarded to `package assemble`. |
| `--write-package-config` | Write a package config template and exit. |

`--app-id` is a reverse-DNS identifier in the
`namespace.[subnamespace.]app` form (`dev.example.my_app`,
`com.acme.invoice`). cargo-plushie validates the format during
assembly.

The output directory is rebuilt from scratch on every run. Anything
under `dist/payload/` from a previous run is removed before
the new payload is assembled.

There are two operating modes:

- **PyInstaller mode** (default for SDK-owned packaging). Triggered
  by `--pyinstaller-entry`. The SDK drives PyInstaller end to end.
- **Prepared payload mode**. Triggered by `--payload-dir`. The caller
  assembles the payload directory and supplies a `--start-command`;
  the SDK only writes the partial manifest and runs assemble. Use
  this for custom build flows where PyInstaller is not the right
  internal payload format.

## The payload

`dist/payload/` is the directory that gets archived into the
artifact:

```
dist/
  plushie-package.toml             # manifest (partial then completed)
  payload/
    bin/
      plushie-renderer             # payload-local renderer copy
    host/
      MyApp/                       # PyInstaller one-folder output
        MyApp                      # frozen host executable (MyApp.exe on Windows)
        _internal/                 # Python runtime, libs, hidden imports, --add-data
    assets/                        # icon and other files from package_assets/
                                   #   (see Bundled assets below)
```

There is no separate entry-script wrapper. PyInstaller bakes the
Python interpreter and the app entry into the host executable
directly, so `[start].command` points straight at
`host/MyApp/MyApp`. The shared package launcher runs this executable
with `PLUSHIE_BINARY_PATH` set to the payload-local renderer, and
the host starts that renderer through the normal binary resolution
path in `plushie.binary.resolve`. The packaged app never reaches out
to the system `PATH` or a download cache; everything it needs is
inside the extracted payload.

## Source layout

Packaging adds project-owned files that belong in version control
and generated files that do not. Knowing which is which avoids
accidentally committing platform-specific binaries or losing
project-owned config.

| Path | What it is | Commit or gitignore |
|---|---|---|
| `plushie-package.config.toml` | Package config: start command, forward_env, platform metadata. Like `pyproject.toml`. | Commit. |
| `package_assets/` | Project-owned icon, fonts, and other files copied verbatim into the payload. | Commit. |
| `PLUSHIE_RUST_VERSION` | Carried as a constant in `plushie.binary`, not a file at the project root. | n/a |
| `bin/` | Plushie tool set installed by `python -m plushie download`: `plushie`, `plushie-renderer`, `plushie-launcher`. Platform-specific binaries. | Gitignore. |
| `dist/` | Package output: payload directory and manifest. Rebuilt by every `python -m plushie package` run. | Gitignore. |
| `build/` | PyInstaller spec and work directories, custom renderer build trees. | Gitignore. |
| `target/plushie/` | Portable and bundle artifacts produced by `bin/plushie package portable` / `bundle`. | Gitignore. |

A minimum `.gitignore` for a packaging-enabled project looks like:

```
/bin/
/build/
/dist/
/target/
```

`python -m plushie download`, `python -m plushie package`, and
`bin/plushie package portable` each check whether their output path
is gitignored when run inside a git repository. If it is not, they
print a one-paragraph warning naming the directory and the line to
add. The command still succeeds; the warning is just a nudge.

## Renderer selection

The command picks a renderer based on the `--renderer-kind` flag
(`stock` by default) and on `[tool.plushie].extensions` in
`pyproject.toml`:

- **Stock renderer.** Resolved through the managed tool set installed
  by `python -m plushie download`. If `PLUSHIE_RUST_SOURCE_PATH` is
  set, the same managed-tool sync path is used and the renderer is
  built from the local checkout.
- **Custom renderer.** Requires an explicit binary via
  `PLUSHIE_BINARY_PATH` or `--renderer-path`. Build it first with
  `python -m plushie build`; the package command does not invoke the
  build step itself when `--renderer-kind custom` is set.
  `PLUSHIE_RUST_SOURCE_PATH` is not consulted in custom mode; the
  custom renderer must be a fully built binary already.

Use `--renderer-path PATH` in PyInstaller mode to package a specific
binary regardless of kind. The payload-local path is always
`bin/plushie-renderer` (or `bin/plushie-renderer.exe` on Windows).

Native widgets are declared in `[tool.plushie].extensions` and
compiled into a custom renderer by `python -m plushie build`. See
the [Custom Widgets reference](custom-widgets.md) for the widget
definition model and the [CLI Commands reference](cli-commands.md)
for the build flags.

## Bundled assets

A packaged app needs two kinds of files beyond the runtime itself:
the icon and other OS-bundle metadata that cargo-plushie reads from
the manifest, and runtime assets that your app loads at startup
(fonts, images, data files). Each has a different home.

### App-loaded assets (PyInstaller `--add-data`)

Anything your app reads at runtime through `importlib.resources` or
direct filesystem paths needs to ship inside the PyInstaller bundle.
Pass each mapping with `--add-data SOURCE:DEST` (the separator is
`:` on POSIX and `;` on Windows; PyInstaller normalizes it):

```bash
python -m plushie package \
  --app-id dev.example.my_app \
  --pyinstaller-entry src/my_app/__main__.py \
  --pyinstaller-name MyApp \
  --add-data "src/my_app/assets:my_app/assets" \
  --collect-submodules plushie
```

PyInstaller copies `src/my_app/assets` into the frozen
`_internal/my_app/assets/` directory. The idiomatic way to resolve
these paths at runtime is through `importlib.resources`:

```python
from importlib.resources import files

font_path = files("my_app.assets").joinpath("fonts/inter.ttf")
icon_path = files("my_app.assets").joinpath("window-icon.png")
```

This works the same packaged or unpackaged, because `importlib.resources`
resolves through the import system in both cases.

For files that need a real filesystem path (some C libraries cannot
read from a zip importer), PyInstaller exposes the extraction root
via `sys._MEIPASS`. In one-folder mode this is the `_internal/`
directory next to the host executable:

```python
import sys
from pathlib import Path

base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
font_path = base / "my_app" / "assets" / "fonts" / "inter.ttf"
```

`--collect-submodules` is the usual escape hatch when PyInstaller's
static analysis misses dynamic imports. The example above collects
`plushie` so widget modules loaded lazily by the runtime are
included.

### Package-level assets (package_assets/)

Files that need to live inside the payload at a known location,
such as the OS bundle icon referenced from `[platform].icon`, go in
a `package_assets/` directory next to `plushie-package.config.toml`.
cargo-plushie copies the contents verbatim into the payload root
during `bin/plushie package assemble`:

```
my_app/
├── pyproject.toml
├── plushie-package.config.toml
└── package_assets/
    ├── icon.png                # ends up at payload/icon.png
    └── fonts/
        └── extra.ttf           # ends up at payload/fonts/extra.ttf
```

The convention is zero-config: if `package_assets/` exists, it is
used. To use a different directory name, set `[assets].dir` in the
package config:

```toml
[assets]
dir = "branding"
```

Asset files overwrite SDK-generated payload files when names
collide. Use this for overrides, not by accident; the default
layout has no overlap.

`package_assets/` is the right home for files the **launcher** or
**OS bundle** needs to see at known paths (icons, license text,
update channel manifests). Files the **Python host** loads at
runtime should go through PyInstaller `--add-data` instead, so they
end up inside the frozen host executable's resource tree.

### Icon

cargo-plushie looks for an icon at the path named in
`[platform].icon` inside the payload. If no path is set and a file
already exists at `assets/default-app-icon-512.png`, that path is
recorded. If nothing exists at either location, cargo-plushie writes
the built-in default icon to `assets/default-app-icon-512.png` and
records that path.

**Format:** PNG with RGBA alpha channel for transparency.

**Dimensions:** square aspect ratio, 512x512 minimum. cargo-packager
scales this single source down for `.ico` (16/32/48/64/128/256) and
up or down for `.icns` (16/32/64/128/256/512/1024). Provide
1024x1024 or larger if the same icon will be used for retina
displays or high-DPI Windows installers.

To use a custom icon, put a PNG in `package_assets/` and reference
it from `[platform].icon`:

```toml
[platform]
icon = "icon.png"               # payload-relative; resolves to payload/icon.png
                                # after package_assets/icon.png is copied
```

The schema accepts a single icon path. Multi-size sources and
per-platform `.icns`/`.ico` overrides are not yet supported.

## Runtime bundling with PyInstaller

`python -m plushie package` uses [PyInstaller](https://pyinstaller.org/)
one-folder mode as the internal payload format. PyInstaller owns the
Python runtime, the standard library, the app source, third-party
dependencies, and any data files passed with `--add-data`. The
shared Rust launcher owns the outer executable, payload extraction,
cache lifecycle, and update hooks. Nested self-extraction
(PyInstaller one-file inside the shared launcher) would add startup
cost and obscure postcheck output for no benefit, so it is not the
default.

The SDK calls PyInstaller with these flags, in this order:

```
python -m PyInstaller \
  --name <pyinstaller-name> \
  --specpath build/pyinstaller-spec \
  --distpath dist \
  --workpath build/pyinstaller \
  --add-binary <resolved-renderer>:. \
  --noconfirm \
  [--icon <app-icon>] \
  [--add-data ... --hidden-import ... --collect-submodules ...] \
  [--pyinstaller-arg ...] \
  <entry>
```

Anything else is up to the project. `--pyinstaller-arg` is the
escape hatch for flags the SDK does not surface directly
(`--onedir` vs `--onefile`, `--windowed`, `--osx-bundle-identifier`,
analysis hooks, and so on). PyInstaller flag semantics are
unchanged; consult the [PyInstaller manual](https://pyinstaller.org/en/stable/usage.html)
for the full set.

The renderer that the SDK resolves is added as `--add-binary` so
PyInstaller knows about it during analysis. After PyInstaller
finishes, the SDK removes the nested copy from the host tree and
places the canonical renderer at `payload/bin/plushie-renderer`.
This avoids two copies of a multi-megabyte binary in the final
artifact.

### Slimming the runtime

Hand-pruning PyInstaller output is brittle and not recommended.
Three levers cover most cases:

- **Trim imports.** PyInstaller's static analysis errs on the side
  of inclusion. If your app does not need an optional dependency,
  do not import it at module load time. Move it behind a lazy
  helper, and PyInstaller will skip it.
- **Use UPX selectively.** Pass `--pyinstaller-arg --upx-dir=PATH`
  with a UPX install to compress binaries. UPX trades startup time
  for size and breaks codesigning on macOS, so it is opt-in.
- **Drop large data files.** `--exclude-module MODULENAME`
  (forwarded via `--pyinstaller-arg --exclude-module ...`) removes
  modules PyInstaller would otherwise include.

The packaged artifact is also compressed by cargo-plushie when it
archives the payload, which absorbs another chunk of size. For most
apps, the standard PyInstaller output is fine.

## The managed tool set

`python -m plushie download` installs three executables under
`bin/`:

| File | Role |
|---|---|
| `plushie` | Orchestration tool. Owns `tools sync`, `package assemble`, `package portable`, `package bundle`. |
| `plushie-renderer` | The renderer binary used at runtime. Resolved by `plushie.binary.resolve`. |
| `plushie-launcher` | The substrate that `bin/plushie package portable` wraps with the archived payload to produce the self-extracting artifact. |

The version of each file matches the `PLUSHIE_RUST_VERSION` pin in
`plushie.binary`. `python -m plushie download` downloads `plushie`
first, then invokes `bin/plushie tools sync --required-version
VERSION` to fetch the matching renderer and launcher.

`python -m plushie package` requires all three files. The renderer
is copied into the payload, `bin/plushie` runs the assemble step,
and `bin/plushie package portable` later wraps `plushie-launcher`
around the archived payload to produce the artifact. The command
raises early if any are missing and prints a `python -m plushie
download` hint.

The Windows variants of these files carry an `.exe` suffix. The
tool name (`plushie` versus `plushie.exe`) is platform-specific;
the role is the same.

## The partial manifest

`python -m plushie package` writes a TOML document with everything
the SDK knows: identity, versions, target, and the renderer
descriptor. A minimal partial manifest looks like:

```toml
schema_version = 1
app_id = "dev.example.my_app"
app_name = "My App"
app_version = "0.1.0"
target = "linux-x86_64"
host_sdk = "python"
host_sdk_version = "0.6.0"
plushie_rust_version = "0.7.0"
protocol_version = 1

[start]
command = ["host/MyApp/MyApp"]

[renderer]
path = "bin/plushie-renderer"
kind = "stock"
```

`bin/plushie package assemble` reads this file plus the payload
directory and writes the completed manifest in place. The completed
manifest adds:

- A `[payload]` section with the archive hash, size, and
  compression format.
- `[start].working_dir` and `[start].forward_env` defaults from the
  package config.
- A `[platform]` block if one is set in the package config, with
  `[platform].icon` resolved to the materialized icon image's
  payload-relative path.

The split exists so that cargo-plushie owns the cross-SDK schema
once. Every Plushie SDK writes a partial manifest in this shape and
hands the rest to the same `package assemble` step. The only
host-side field that varies is `host_sdk`, which the Python SDK
sets to `"python"`.

## Package config

Optional defaults for the assemble step live in
`plushie-package.config.toml` at the project root. Generate a
template with:

```bash
python -m plushie package --write-package-config
```

The template includes all supported fields commented out:

```toml
config_version = 1

[start]
working_dir = "."
command = ["host/MyApp/MyApp"]
# forward_env = ["PATH", "HOME", "LANG", "LC_ALL", ...]

# [assets]
# # Project-relative directory copied verbatim into the payload root
# # during package assembly. When this section is absent, a directory
# # named `package_assets/` next to this config file is used by
# # convention if it exists.
# dir = "package_assets"

# [platform]
# publisher = "Your Name"
# copyright = "Copyright 2026 Your Name"
# category = "productivity"
# description = "Short app description"
# bundle_id = "com.example.app"

# [platform.macos]
# bundle_version = "1"

# [platform.windows]
# install_scope = "perUser"
```

`[start].working_dir` is relative to the extracted payload root.
`[start].command` is a structured argv; the first element is the
PyInstaller host executable. The SDK writes
`host/<name>/<name>.exe` automatically on `windows-*` targets.

`[start].forward_env` is the list of environment variable **names**
copied from the parent process into the host process at launch
time. Names only; values are never logged or recorded. Add entries
when your app reads additional environment, for example `RUST_LOG`
during development or `XDG_RUNTIME_DIR` and `WAYLAND_DISPLAY` on
Wayland targets.

The `[platform]` block populates OS-native bundle metadata. All
fields are optional. `bundle_id` defaults to `app_id`. The
`[platform.macos]` and `[platform.windows]` subtables carry
OS-specific fields and are also optional. `install_scope` accepts
`perUser` or `perMachine`.

Use `--package-config PATH` to point at a config file outside the
project root.

## Forwarded environment

The package launcher does not blanket-inherit the user's
environment. It builds the host process environment from two closed
sources:

- The Plushie reserved namespace (`PLUSHIE_BINARY_PATH`, plus a
  small set of internal coordination variables that the launcher
  sets itself).
- The names listed in `[start].forward_env`.

Variables outside both sets are dropped. This gives packaged apps a
predictable, narrow runtime environment regardless of where the
launcher is invoked from. The same allowlist principle is used by
the SDK to bound the renderer subprocess environment at runtime.

## Building artifacts

Once the manifest is complete, the same payload feeds two artifact
shapes.

### Portable single-file launcher

```bash
bin/plushie package portable --manifest dist/plushie-package.toml
```

Produces a self-extracting executable wrapping `plushie-launcher`
and the archived payload. Output lands under
`target/plushie/package/` by default; pass `--out PATH` to override.
The artifact is content-addressed by the payload hash, so two
builds of the same inputs produce a byte-identical executable.

The launcher extracts the payload to a per-user cache directory
keyed by the payload hash. Repeated runs of the same artifact reuse
the extraction.

### OS-native installers

```bash
bin/plushie package bundle --manifest dist/plushie-package.toml --format appimage
bin/plushie package bundle --manifest dist/plushie-package.toml --format dmg --format app
bin/plushie package bundle --manifest dist/plushie-package.toml --format nsis
```

`--format` is singular and repeatable; pass it once per format.

Delegates to
[cargo-packager](https://github.com/crabnebula-dev/cargo-packager)
for AppImage (Linux), `app` and `dmg` (macOS), and `nsis` and
`wix` (Windows). Format availability depends on the runner: Apple
formats need a macOS runner, Windows formats need a Windows runner.

Both commands default to a strict-tools check: they verify that the
launcher, renderer, and `plushie` itself match the SDK-pinned
version. Pass `--lax-tools` to bypass the check; this is intended
for local experimentation, not for release builds.

## Distribution

Artifacts are version-named and shipped with SHA-256 sidecars in
the same layout the SDK uses to fetch its own managed tools:

```
BASE/vVERSION/ARTIFACT
BASE/vVERSION/ARTIFACT.sha256
```

GitHub releases match this layout naturally. Other hosting works
the same way: any HTTPS endpoint that serves
`vVERSION/ARTIFACT` and `vVERSION/ARTIFACT.sha256` is usable.

For local release verification, point `PLUSHIE_RELEASE_BASE_URL` at
a `file://` directory or a loopback HTTP server before assets are
uploaded. The download flow accepts both schemes alongside the
default HTTPS.

## Continuous integration

The following GitHub Actions workflow builds a portable artifact
per target on a `v*` tag push and uploads everything to a GitHub
release with SHA-256 sidecars. Drop it in at
`.github/workflows/release.yml` and edit the marked lines for your
app:

```yaml
name: Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write          # for uploading release assets

jobs:
  package:
    name: Package (${{ matrix.target }})
    runs-on: ${{ matrix.runner }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - target: linux-x86_64
            runner: ubuntu-latest
          - target: darwin-x86_64
            runner: macos-13
          - target: darwin-aarch64
            runner: macos-14
          - target: windows-x86_64
            runner: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install project
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"
          python -m pip install pyinstaller

      - name: Install Plushie tools
        run: python -m plushie download

      # EDIT: replace src/my_app/__main__.py, MyApp, and dev.example.my_app.
      - name: Build the package payload
        run: |
          python -m plushie package \
            --app-id dev.example.my_app \
            --app-name "My App" \
            --pyinstaller-entry src/my_app/__main__.py \
            --pyinstaller-name MyApp \
            --collect-submodules plushie

      - name: Build the portable artifact
        run: bin/plushie package portable --manifest dist/plushie-package.toml

      - name: Compute SHA-256 sidecar
        shell: bash
        run: |
          cd target/plushie/package
          for f in *; do
            if [ -f "$f" ] && [[ "$f" != *.sha256 ]]; then
              shasum -a 256 "$f" | awk '{print $1}' > "$f.sha256"
            fi
          done

      - name: Upload to release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            target/plushie/package/*
          generate_release_notes: true
```

The workflow runs four parallel jobs, one per supported target.
Each sets up Python, installs the project and PyInstaller,
installs the Plushie tool set, builds the PyInstaller payload,
produces the portable artifact, computes a SHA-256 sidecar, and
uploads both files to the release that the tag push creates.

Lines to tweak for your project:

- The matrix runner labels (`macos-13` for Intel macOS, `macos-14`
  for Apple Silicon). GitHub-hosted runner labels change over time;
  pin or update as needed. Add `ubuntu-24.04-arm` (or use a
  self-hosted runner) for Linux aarch64.
- The Python version in `setup-python`. Match
  `requires-python` in your `pyproject.toml`.
- The `python -m plushie package` arguments: `--app-id`,
  `--pyinstaller-entry`, `--pyinstaller-name`, and any
  `--add-data` / `--hidden-import` / `--collect-submodules` your
  app needs.
- Release notes: set `generate_release_notes` to `false` and add
  `body` (or `body_path`) if you write release notes by hand.

To also build OS-native installers, add a second matrix entry that
calls `bin/plushie package bundle --format <name>` (repeat the flag per format) instead of
`package portable`, and adjust the upload glob accordingly. Apple
formats need a macOS runner with valid signing identities; Windows
formats need a Windows runner with the appropriate SDKs.

For private hosting, replace the upload step with whatever pushes
the artifact and sidecar to your release endpoint. Any service
that exposes the assets at `BASE/vVERSION/ARTIFACT` plus
`BASE/vVERSION/ARTIFACT.sha256` works with the download flow.

## Signing

`plushie-package.toml` carries a `[[signing.hooks]]` block: a list
of commands that run after the artifact is built. Pass
`--run-signing-hooks` to `package portable` or `package bundle` to
invoke them. Hooks are opt-in so release builds run them and local
experimentation does not.

Each hook is a structured argv. Use them for macOS notarization,
Windows code signing, Linux checksum attestation, or whatever else
the target platform needs. Plushie does not hold signing keys; the
hook commands do.

## Updates

`plushie-package.toml` reserves an `[updates]` block for update
channel metadata. The schema is in place. The runtime side that
consumes it, planned around
[cargo-packager-updater](https://github.com/crabnebula-dev/cargo-packager),
is not yet shipped.

## Host-first versus renderer-parent

Packaging is host-first. The launcher starts the Python host and
the host starts its own renderer.

A separate renderer-parent flow exists for development and
embedding hosts. The renderer starts first, binds a Unix socket,
and spawns the Python command with `PLUSHIE_SOCKET` pointing at it
and a `PLUSHIE_TOKEN` proof:

```bash
plushie-renderer --listen \
  --exec-bin python \
  --exec-arg -m \
  --exec-arg plushie \
  --exec-arg connect \
  --exec-arg my_app:Counter
```

`python -m plushie connect` reads the socket and connects, resolving
the token from `--token`, `PLUSHIE_TOKEN`, or a single JSON line on
stdin (see the [CLI Commands reference](cli-commands.md#token-resolution-in-socket-mode)).

Driving a packaged PyInstaller app from an external renderer is
possible but requires adding `PLUSHIE_SOCKET` and `PLUSHIE_TOKEN`
to `[start].forward_env` so the launcher passes the variables
through. This is not a default-on configuration. The PyInstaller
payload's frozen host executable embeds the same `connect` entry
point and behaves the same way when those variables are forwarded.

## See also

- [CLI Commands reference](cli-commands.md) - all subcommands
  including `package`, `download`, `build`, and `connect`
- [Configuration reference](configuration.md) - environment
  variables, `[tool.plushie]` keys, and the `App.settings` callback
- [Versioning reference](versioning.md) - SDK and renderer version
  coupling, `PLUSHIE_RUST_VERSION`, and protocol compatibility
- [Custom Widgets reference](custom-widgets.md) - native widget
  declarations consumed by `python -m plushie build`
- [Wire Protocol reference](wire-protocol.md) - message format,
  token handling, and renderer-parent startup
- [PyInstaller manual](https://pyinstaller.org/en/stable/usage.html)
  - configuring `--add-data`, `--hidden-import`, and the analysis
  pipeline
