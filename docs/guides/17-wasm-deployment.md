# WASM Deployment

Plushie apps can run in the browser via WebAssembly. The renderer
compiles to WASM using `wasm-pack`, producing a JavaScript module
and a `.wasm` binary that can be served from any static file host.
The Python app itself continues to run on a server, speaking the
same wire protocol to the browser over a WebSocket.

## Prerequisites

- **Rust toolchain** with the `wasm32-unknown-unknown` target:
  `rustup target add wasm32-unknown-unknown`.
- **wasm-pack**: install via
  https://rustwasm.github.io/wasm-pack/. The `build` command
  shells out to `wasm-pack build --target web` and fails fast
  with an install hint if it is missing from `PATH`.
- **Plushie Rust source checkout**: set `PLUSHIE_RUST_SOURCE_PATH`
  to the local `plushie-rust` directory (or `source_path` in
  `[tool.plushie]`). The WASM build requires the
  `plushie-renderer-wasm` crate, which only lives in the source
  checkout.

## Building

```bash
# Build the WASM renderer (debug, for development)
PLUSHIE_RUST_SOURCE_PATH=~/projects/plushie-rust python -m plushie build --wasm

# Build with optimizations (for production)
PLUSHIE_RUST_SOURCE_PATH=~/projects/plushie-rust python -m plushie build --wasm --release

# Build both native binary and WASM in one command
PLUSHIE_RUST_SOURCE_PATH=~/projects/plushie-rust python -m plushie build --bin --wasm
```

The build produces two files:

- `plushie_renderer_wasm.js` (JavaScript glue module)
- `plushie_renderer_wasm_bg.wasm` (compiled WebAssembly binary)

By default these are installed to the standard WASM directory
(`~/.local/share/plushie/wasm/` on Linux and macOS,
`%LOCALAPPDATA%\plushie\wasm\` on Windows). Override the
destination via `wasm_dir` in `[tool.plushie]` or the
`--wasm-dir` CLI flag.

To have `build` (and `download`) install both artifacts by
default, declare it in `pyproject.toml`:

```toml
[tool.plushie]
artifacts = ["bin", "wasm"]
wasm_dir = "static"
```

With `artifacts = ["bin", "wasm"]` the bare `python -m plushie
build` and `python -m plushie download` commands install both.
Explicit `--bin` or `--wasm` flags override the config and are
authoritative: `--wasm` alone installs only the WASM bundle even
when `artifacts` lists both.

## Configuration

The `wasm_dir` key points at the directory the build copies
`plushie_renderer_wasm.js` and `plushie_renderer_wasm_bg.wasm`
into. For a typical web project, point it at whatever static
directory your server already serves:

```toml
[tool.plushie]
artifacts = ["bin", "wasm"]
wasm_dir = "static/wasm"
```

CLI flags win over `pyproject.toml`:

```bash
python -m plushie build --wasm --wasm-dir assets/wasm
```

Resolution order for every WASM setting is the same as for the
native binary: CLI flags first, then `[tool.plushie]`, then
environment variables, then defaults.

## Serving the output

The WASM files are static assets. Serve them from any web server
or CDN. The `.wasm` file should be served with the
`application/wasm` MIME type for optimal browser loading; most
modern static servers handle this correctly out of the box.

A quick local check with the stdlib server:

```bash
cd static
python -m http.server 8080
```

For production, put the files behind a CDN or a reverse proxy
and enable `gzip` or `brotli` compression on the `.wasm` file.
The compiled binary compresses well and the savings on first
load are significant.

## Web page integration

The JavaScript module exports an initialization function. Load
it from an HTML page:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>My Plushie App</title>
  <style>
    body { margin: 0; overflow: hidden; }
    canvas { width: 100vw; height: 100vh; }
  </style>
</head>
<body>
  <canvas id="plushie-canvas"></canvas>
  <script type="module">
    import init from "./plushie_renderer_wasm.js";
    await init();
  </script>
</body>
</html>
```

The WASM renderer connects back to the Python backend over a
WebSocket to receive wire protocol messages (snapshots, patches)
and send events. The Python app runs on the server; the WASM
renderer runs in the browser.

## WebSocket backend

On the server side, accept a WebSocket connection and hand its
bytes to a `Connection` via `WebSocketAdapter`. The runtime does
not care that the transport is a browser socket; it speaks the
same wire protocol it would over a subprocess pipe.

A minimal server using the `websockets` library:

```python
from websockets.sync.server import serve

import plushie
from plushie.connection import Connection
from plushie.runtime import Runtime
from plushie.transport import WebSocketAdapter

from myapp import Counter


def handle(websocket):
    adapter = WebSocketAdapter(websocket)
    conn = Connection.from_iostream(adapter)
    runtime = Runtime(Counter(), conn)
    runtime.run()


def main():
    with serve(handle, "0.0.0.0", 8080) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
```

One `Runtime` per WebSocket connection gives each browser tab an
isolated model. If several browsers should share state, that is
the shared-state topic from the previous chapter: a single
`Runtime` driven by events injected from all connected sockets.

`WebSocketAdapter` accepts any object with `recv()` and `send()`
methods, so the same pattern works with Flask-SocketIO, FastAPI
(wrap the `starlette` WebSocket), or a raw `asyncio` bridge.
Drop the adapter in wherever the transport already lives.

## Limitations vs native

The WASM renderer has several differences from the native
renderer:

- **No native file dialogs.** Platform effects like
  `Effect.file_open` are not available. File operations must use
  browser APIs (for example `<input type="file">` via JavaScript
  interop) or be handled server-side.
- **No clipboard access** without user gesture. Browser security
  policies restrict clipboard operations to user-initiated
  events.
- **No system notifications.** The Web Notifications API can be
  used as an alternative via JavaScript interop.
- **No multi-window.** WASM apps render into a single canvas
  element. Multiple windows are not supported.
- **Performance.** The WASM renderer uses software rendering.
  Complex scenes with many animated elements may be slower than
  the native GPU-accelerated renderer.
- **Startup time.** The `.wasm` binary must be downloaded and
  compiled by the browser on first load. Use `--release` builds
  and enable `gzip` or `brotli` compression on your server to
  minimize this.
- **No native widgets.** Native widget crates that compile Rust
  code for the renderer are not currently supported in WASM
  builds. Only pure Python widgets and the built-in widget set
  work.

## Development workflow

During development, use the native renderer (`python -m plushie
run myapp:App`) for fast iteration. Build and test the WASM
version periodically to catch browser-specific issues:

```bash
# Develop with native renderer
python -m plushie run myapp:App --watch

# Periodically verify the WASM build
python -m plushie build --wasm
# Then serve the static directory and test in a browser
```

The Python side of the app is identical across both transports.
The only thing that changes is who opens the connection: the
native CLI spawns a renderer subprocess, the WASM deployment
waits for a browser to open a WebSocket.

## Download vs build

`python -m plushie download --wasm` downloads a precompiled WASM
renderer for released versions. It skips the Rust toolchain
requirement entirely but does not support native widgets (which
require a custom build). For most apps using only built-in and
pure Python widgets, the precompiled download is sufficient:

```bash
python -m plushie download --wasm
python -m plushie download --wasm --wasm-dir static/wasm
```

The download path verifies the archive's SHA-256 against a
sidecar `.sha256` file, extracts `plushie_renderer_wasm.js` and
`plushie_renderer_wasm_bg.wasm` into the target directory, then
deletes the tarball. If the renderer is unreachable or the
checksum fails, the error message points at `python -m plushie
build --wasm` as the fallback.

That rounds out the guide series. For the full reference set,
jump back to the [documentation index](../README.md) or return
to [Introduction](01-introduction.md) for a fresh read through
the architecture now that you have seen it end to end.
