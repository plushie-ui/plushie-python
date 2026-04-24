# Running plushie

Plushie's **renderer** draws windows and handles input. Your Python
code (the **host**) manages state and builds the UI tree. They talk
over a wire protocol: locally through a pipe, remotely over SSH,
or through any transport you provide. This guide covers all the ways
to connect them.

## Local desktop

The simplest setup: the host spawns the renderer as a child process.

```bash
python -m plushie run my_app:MyApp
```

Or from code:

```python
import plushie

plushie.run(MyApp)
```

The renderer is resolved automatically. For most projects,
`python -m plushie download` fetches a precompiled renderer and you're
done. If you have native Rust extensions, `python -m plushie build`
compiles a custom renderer. You can also set `PLUSHIE_BINARY_PATH`
explicitly.

### Dev mode

`python -m plushie run` watches your source files and reloads on change.
Edit code, save, see the result instantly. The model state is preserved
across reloads.

```bash
python -m plushie run my_app:MyApp           # live reload enabled
python -m plushie run my_app:MyApp --no-watch  # disable file watching
```

### Exec mode

The renderer can spawn the host instead of the other way around. This
is useful when plushie is the entry point (a release binary or launcher)
and it is the foundation for remote rendering over SSH.

```bash
plushie --exec "python -m plushie connect my_app:MyApp"
```

The renderer controls the lifecycle. When the user closes the window,
the renderer closes stdin, and the Python process exits cleanly.

The host side uses `StdioConnection`, which reads from fd 0 and writes
to fd 1 (the process's own stdin/stdout). Python's `sys.stdout` is
redirected to `sys.stderr` so `print()` does not corrupt the wire
protocol.


## Remote rendering

Your host runs on a server. You want to see its UI on your laptop.
The renderer runs locally (where your display is), the host runs
remotely (where the data is), and SSH connects them:

```
[your laptop]                    [server]
renderer        <--- SSH --->    host
  draws windows                    init/update/view
  handles input                    business logic
```

Your `init`/`update`/`view` code does not change at all.

### Prerequisites

- **Your laptop**: the `plushie-renderer` binary installed and on your
  PATH. Download with `python -m plushie download`, or build from
  source with `python -m plushie build` via
  [cargo-plushie](versioning.md) if you have a Rust toolchain.
- **The server**: your Python project deployed with its dependencies.
  The server does NOT need the renderer or a display server.
- **SSH access**: you can `ssh user@server` from your laptop.

### Quick start

```bash
plushie --exec "ssh user@server 'cd /app && python -m plushie connect my_app:MyApp'"
```

The renderer on your laptop spawns an SSH session, which starts the
host on the server. The wire protocol flows through the SSH tunnel.
Each connection starts a fresh Python process on the server.

### Binary distribution

The renderer always runs on the **display machine** (your laptop,
not the server). How you get it there depends on your project:

| Your project uses | Renderer needed | How to get it |
|---|---|---|
| Built-in widgets only | Precompiled | `python -m plushie download` or GitHub release |
| Pure Python extensions | Precompiled | Same (composites don't need a custom build) |
| Native Rust extensions | Custom build | `python -m plushie build` targeting your laptop's architecture |

The server does not need the renderer at all. It only needs your Python
project and its dependencies.


## Daemon mode

Daemon mode is available for the default spawned renderer mode. It keeps the
Python runtime alive after all windows close, with the model preserved. This
is useful for apps that continue background work and may open windows again
later.

```python
import plushie

plushie.run(MyApp, daemon=True)
```
<!-- test: test_running_doc_does_not_use_transport_kwarg_for_run -- keep this section in sync with the test -->

The same mode is available from the CLI:

```bash
python -m plushie run my_app:MyApp --daemon
```

Exec/stdio mode is still started with `connect`:

```bash
plushie --exec "python -m plushie connect my_app:MyApp"
```

The `connect` command currently supports `--json`, but does not expose a
daemon option. When the stdio renderer disconnects, the host exits. Starting
another SSH session starts a fresh host process.


## Resiliency

Things go wrong. Renderers crash, code has bugs, networks drop. In default
spawned renderer mode, Plushie can restart a crashed renderer without losing
your model state. Callback exceptions also preserve the previous model. In
exec/stdio `connect` mode, a broken stdio stream ends the host process, so
persist app state yourself if it must survive a new connection.

### Renderer crashes

If the renderer crashes (segfault, GPU error, out of memory), the
host detects it and restarts automatically with exponential backoff.
Your model state is preserved. The new renderer receives fresh
settings, a full snapshot of the current UI, and re-synced
subscriptions and windows. The user sees a brief flicker, then the
UI is back.

The host retries up to 5 times (100ms, 200ms, 400ms, 800ms, 1.6s).
If all retries fail, it logs troubleshooting steps and the runtime
stops. A successful connection resets the retry counter, so
intermittent crashes get a fresh budget each time.

The `Connection.restart()` method handles the subprocess cleanup and
re-creation. The caller must re-send settings and a snapshot after
restarting.

### Exceptions in your code

If `update()` or `view()` raises, the runtime catches it, logs the
error with a full traceback, and keeps the previous model state. The
window stays open and continues responding to events. You do not need
try/except in your callbacks.

### Network drops

When an SSH connection drops, both sides detect the broken pipe:

- **The renderer** sees the host's stdout close. It can display an
  error or retry the connection.
- **The host** sees stdin close. In `python -m plushie connect` mode,
  the plushie process exits. Persist state in your app if it must
  survive a new SSH session.

Starting another SSH session starts a fresh host process.

### Window close

When the user closes the last window, your `update()` receives the
event. You can save state, persist data, or show a confirmation
dialog. In default spawned renderer mode, `daemon=True` keeps the
runtime alive after all windows close. In exec/stdio `connect` mode,
the last window sends `AllWindowsClosed`; because `connect` runs the
runtime in non-daemon mode, the host exits, which closes stdio.

### Demo: crash-test

The [crash-test demo](https://github.com/plushie-ui/plushie-demos/tree/main/python/crash-test)
exercises both failure paths: Python exceptions in `update()`/`view()`
and Rust panics in `render()`/`handle_command()`. A working counter
proves the app keeps functioning through all crashes.


## Event rate limiting

Over a network, continuous events like mouse moves, scroll, and
slider drags can overwhelm the connection. Rate limiting tells the
renderer to buffer these and deliver at a controlled frequency.
Discrete events like clicks and key presses are never rate-limited.

### Global default

Set `default_event_rate` in your app's `settings()` method:

<!-- test: test_settings_returns_event_rate -- keep this code block in sync with the test -->
```python
class MyApp(App):
    def settings(self):
        return {"default_event_rate": 60}  # 60 events/sec
```

For a monitoring dashboard:

<!-- test: test_dashboard_lower_rate -- keep this code block in sync with the test -->
```python
class Dashboard(App):
    def settings(self):
        return {"default_event_rate": 15}
```

### Per-subscription

Override the global rate for specific event sources:

<!-- test: test_mouse_move_rate, test_animation_frame_rate, test_capture_only_zero_rate -- keep this code block in sync with the test -->
```python
from plushie.subscriptions import Subscription


def subscribe(self, model):
    return [
        Subscription.on_mouse_move("mouse", max_rate=30),
        Subscription.on_animation_frame("frame", max_rate=60),
        Subscription.on_mouse_move("capture", max_rate=0),  # capture only, no events
    ]
```

### Per-widget

Override the rate on individual widgets:

<!-- test: test_slider_event_rate, test_slider_different_rates -- keep this code block in sync with the test -->
```python
ui.slider("volume", (0, 100), model.volume, event_rate=15)
ui.slider("seek", (0, model.duration), model.position, event_rate=60)
```

### Latency and animations

| Transport | Localhost | LAN | WAN |
|---|---|---|---|
| Port (local) | < 1ms | -- | -- |
| SSH | -- | 1-5ms | 20-150ms |

On a LAN, animations are smooth and interactions feel instant. Over a
WAN (50ms+), user interactions have a visible round-trip delay. Design
for this by keeping UI responsive to local input (hover effects, focus
states) and accepting that model updates lag by the round-trip time.


## Custom transports

For advanced use cases, the iostream transport lets you bridge any
I/O mechanism to plushie. Write an adapter that wraps a pair of byte
streams, and plushie handles the rest. Most projects don't need this --
the built-in local and SSH transports cover the common cases.

### IoStreamAdapter

`IoStreamAdapter` bridges any bidirectional byte stream to the plushie
wire protocol. It accepts any pair of objects with `read()` and `write()`
methods (socket file wrappers, pipes, custom stream objects). It runs a
reader thread that decodes frames and provides a thread-safe `send()` for
outbound messages.

<!-- test: test_adapter_accepts_file_like_objects -- keep this code block in sync with the test -->
```python
import socket
from plushie.transport import IoStreamAdapter
from plushie.connection import Connection

sock = socket.create_connection(("127.0.0.1", 4567))
adapter = IoStreamAdapter(sock.makefile("rb"), sock.makefile("wb"))
conn = Connection.from_iostream(adapter)

conn.send_settings({})
conn.send_snapshot(tree)
```

The adapter implements the same concept as the Elixir Bridge's
`{:iostream, pid}` transport, adapted for Python's threading model.

### WebSocketAdapter

`WebSocketAdapter` wraps a WebSocket connection for use with the WASM
renderer or any WebSocket-based transport:

```python
import websockets.sync.client as ws
from plushie.transport import WebSocketAdapter
from plushie.connection import Connection

with ws.connect("wss://example.com/plushie") as websocket:
    adapter = WebSocketAdapter(websocket)
    conn = Connection.from_iostream(adapter, token="shared-secret")
    # Use conn as normal...
```

The WebSocket object must support `recv()` (blocking receive) and
`send(data: bytes)`. The adapter handles framing internally.
Because `WebSocketAdapter` wraps a WebSocket that is already connected,
it cannot add authentication headers. Pass `token=...` to
`Connection.from_iostream()` to authenticate through the renderer's
Settings handshake. Python sends only the SHA-256 digest as
`token_sha256`, not the plaintext token. The digest is still a bearer
credential if someone can observe the connection, so use `wss://` for
remote WebSockets. Plain `ws://` is only reasonable on localhost or a
trusted private link.

### Custom adapter example: TCP

A minimal example showing how to bridge a raw TCP socket:

```python
import socket
import threading
from plushie.transport import IoStreamAdapter
from plushie.connection import Connection


def accept_renderer(host: str, port: int, app_class):
    """Accept a renderer connection over TCP and run a plushie app."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(1)

    client, addr = server.accept()
    print(f"Renderer connected from {addr}")

    reader = client.makefile("rb", buffering=0)
    writer = client.makefile("wb", buffering=0)

    adapter = IoStreamAdapter(reader, writer)
    conn = Connection.from_iostream(adapter)

    # Now use conn with Runtime or manually send messages
    conn.wait_hello()
    conn.send_settings({})
    # ...
```

### Stream protocol requirements

Any object implementing `ReadableStream` (has `read(n) -> bytes`) and
`WritableStream` (has `write(data) -> int | None` and `flush()`) can be
used with `IoStreamAdapter`. The adapter handles msgpack framing
(4-byte length prefix) internally.


## WASM renderer

The WASM renderer runs plushie in the browser. The Python host communicates
with it over a WebSocket using the `WebSocketAdapter`:

```python
from plushie.transport import WebSocketAdapter
from plushie.connection import Connection

# The WASM renderer connects to this WebSocket endpoint
adapter = WebSocketAdapter(websocket)
conn = Connection.from_iostream(adapter, token="shared-secret")
```

If a gateway in front of the WebSocket also needs HTTP-level
authentication, pass the gateway headers when creating the WebSocket.
`WebSocketAdapter` only handles the already-open socket and renderer
Settings authentication.

Build the WASM renderer:

```bash
python -m plushie download --wasm
# or from source:
python -m plushie build --wasm
```


### Framing

Raw byte streams (SSH channels, raw sockets) need message boundaries.
The `plushie.framing` module handles this:

<!-- test: test_encode_decode_round_trip, TestJsonFraming, TestMsgpackFraming -- keep this code block in sync with the test -->
```python
from plushie.framing import MsgpackFraming, JsonFraming

# MessagePack: 4-byte big-endian length prefix
framing = MsgpackFraming()
encoded = MsgpackFraming.encode(msg_dict)  # -> bytes with length prefix
messages = framing.feed(raw_bytes)  # -> list of decoded dicts

# JSON: newline-delimited
framing = JsonFraming()
encoded = JsonFraming.encode(msg_dict)  # -> bytes with newline
messages = framing.feed(raw_bytes)  # -> list of decoded dicts
```

The `IoStreamAdapter` handles framing automatically. You only need
these directly if building a custom adapter from scratch.


## Connection modes summary

| Mode | Class | How it works |
|---|---|---|
| Spawn (default) | `Connection` | Python spawns the renderer as a subprocess |
| Exec / stdio | `StdioConnection` | Renderer spawns Python via `plushie --exec` |
| Custom I/O | `IoStreamAdapter` + `Connection.from_iostream()` | Any byte stream pair |
| WebSocket | `WebSocketAdapter` + `Connection.from_iostream()` | Browser/WASM renderer |


## Testing

See [Testing](testing.md) for the full guide. Quick summary:

```bash
pytest                                      # pooled mock (fast, no display)
PLUSHIE_TEST_BACKEND=headless pytest        # real rendering, no display
PLUSHIE_TEST_BACKEND=windowed pytest        # real windows (needs display)
```


## Demo: collab

The [collab demo](https://github.com/plushie-ui/plushie-demos/tree/main/python/collab)
demonstrates all transport modes in one app: native desktop, exec mode,
shared-state WebSocket, and SSH. Multiple clients share a single counter
and notes in real time.

## Next steps

- [Getting started](getting-started.md) - setup, first app
- [Testing](testing.md) - three-backend test framework
- [Extensions](extensions.md) - custom widgets
- [Accessibility](accessibility.md) - a11y props and patterns
