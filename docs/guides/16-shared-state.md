# Shared State

The pad runs as a single local process talking to a single renderer window. One user, one window, one model. The wire protocol does not know or care about that arrangement. The same bytes that travel down a subprocess pipe also travel over a TCP socket, an SSH channel, or a WebSocket to a browser.

This chapter takes the pad and turns it into a shared space: one Python process running the app, any number of renderer clients connected to it, each of them seeing the same model update in real time. Along the way you will meet `python -m plushie connect`, the `IoStreamAdapter`, the `WebSocketAdapter`, session multiplexing, and the thread-safe `inject()` that lets external systems push events into a running app.

## The shape

A normal `plushie.run(App)` spawns a renderer as a subprocess and pipes wire frames over its stdin and stdout. That works beautifully for a desktop app. It does not work for two users on two laptops who want to collaborate on the same pad.

Flip the relationship. Run the Python process on a server. Let each user's renderer connect to it as a client over SSH or WebSocket. The Python app owns the authoritative model. Each renderer is just a view.

```
 client 1 (renderer) ---SSH------+
                                 |
 client 2 (renderer) ---SSH------+----> python app process
                                 |         (one model,
 client 3 (browser)  ---WS-------+          many clients)
```

The app does not change. `init`, `update`, `view`, `subscribe` all work the same way. What changes is the transport and how events route in and snapshots route out.

## Connect mode vs run mode

The CLI offers two modes for starting an app.

`python -m plushie run myapp:App` is the familiar path. The SDK resolves the renderer binary, spawns it as a subprocess, and talks to it over pipes.

`python -m plushie connect myapp:App` is the inverse. The SDK does not spawn anything. It reads wire frames from stdin and writes them to stdout, leaving the transport to whoever invoked it. The renderer is already running somewhere else, and a host process (an SSH subsystem, a socket wrapper, a container runtime) funnels bytes between them.

```bash
python -m plushie connect myapp:App
python -m plushie connect myapp:App --json
```

Flag summary:

| Flag | Description |
|---|---|
| `--json` | Use JSON wire format instead of MessagePack |

That is all. Connect mode is deliberately tiny: it does one thing, hooks the app up to whatever bidirectional byte channel is on stdio. See [CLI Commands](../reference/cli-commands.md) for the full CLI surface.

The SSH pattern that we describe later uses a subsystem configuration where every inbound connection runs `python -m plushie connect` and each session's stdio is an SSH channel. The host process multiplexes.

## IoStreamAdapter

When you control the byte channel inside Python rather than wrapping around the CLI, `plushie.transport.IoStreamAdapter` bridges any bidirectional stream to a `Connection`.

```python
import socket

from plushie.connection import Connection
from plushie.transport import IoStreamAdapter

sock = socket.create_connection(("renderer.internal", 4567))
adapter = IoStreamAdapter(
    sock.makefile("rb"),
    sock.makefile("wb"),
    format="msgpack",
)
conn = Connection.from_iostream(adapter)
```

The adapter accepts any object pair that implements `read(n)` and `write(data)` plus `flush()`. A reader thread inside the adapter pulls bytes, runs them through the framing layer, decodes the resulting messages, and posts them to the runtime as events. `send()` is thread-safe so the runtime can write back from the runtime thread.

For typical TCP or Unix socket cases, `SocketAdapter` parses the address string for you:

```python
from plushie.transport import SocketAdapter

adapter = SocketAdapter(":4567")            # TCP on localhost
adapter = SocketAdapter("10.0.0.5:4567")    # remote TCP
adapter = SocketAdapter("/tmp/plushie.sock")  # Unix domain socket
```

Pass the result to `Connection.from_iostream` the same way. The transport boundary ends there; everything above it (runtime, update, view, diff) is identical to the local case.

## WebSocketAdapter

Browsers do not speak SSH. They speak WebSocket. `WebSocketAdapter` wraps a WebSocket-like object that has `recv()` and `send(bytes)` methods:

```python
import websockets.sync.client as ws

from plushie.connection import Connection
from plushie.transport import WebSocketAdapter

with ws.connect("ws://localhost:8080/plushie") as websocket:
    adapter = WebSocketAdapter(websocket)
    conn = Connection.from_iostream(adapter)
```

The WASM build of the renderer (`python -m plushie build --wasm`) produces a JavaScript module and a WebAssembly file. Host both from a small web server, wire the browser's WebSocket to the Python process, and the same app runs in the browser.

Chapter 17 covers the browser scenario end to end: building the WASM bundle, serving it, and the origin and rate-limiting considerations that matter for public endpoints. This chapter sticks to the shape of the connection.

## Session identification

So far we have talked about one Python process per client. A simpler pattern for test fixtures and some server shapes runs one renderer that hosts multiple sessions.

```bash
plushie --mock --max-sessions 8
```

In multiplexed mode, every wire message carries a `session` field that identifies which logical session it belongs to. `Connection.open(max_sessions=N)` with `N > 1` enables the mode on the SDK side, and each session gets its own isolated view tree, subscription set, and effect inbox inside the renderer.

Two lifecycle events exist for this mode. They arrive through `update` like any other event.

| Event | Meaning |
|---|---|
| `SessionError(session, code, error)` | A session failed. `code` is a stable token, `error` is human prose. |
| `SessionClosed(session, reason)` | The renderer closed the session cleanly. |

Stable `code` values for `SessionError` include `session_panic`, `max_sessions_reached`, `session_channel_closed`, `writer_dead`, `font_cap_exceeded`, and `session_backpressure_overflow`. Match on the code when you need programmatic branching:

```python
from plushie.events import SessionClosed, SessionError


def update(self, model, event):
    match event:
        case SessionError(session=sid, code="max_sessions_reached"):
            return self._reject_session(model, sid)
        case SessionError(session=sid, code=code, error=msg):
            return self._mark_session_failed(model, sid, code, msg)
        case SessionClosed(session=sid):
            return self._forget_session(model, sid)
        case _:
            return model
```

The bulk of server deployments, including the SSH pattern below, use one renderer per client and therefore never see session lifecycle events. They matter for the pool-based test runner and for custom multiplexed setups.

## Per-session vs shared state

With many clients hitting one model, every field is either shared or per-session. Decide per field. Keep the split visible in the type.

```python
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SessionState:
    dark_mode: bool = False
    selected: str | None = None
    cursor: int = 0


@dataclass(frozen=True, slots=True)
class Model:
    counter: int = 0
    experiments: tuple["Experiment", ...] = ()
    sessions: dict[str, SessionState] = field(default_factory=dict)
```

`counter` and `experiments` are shared: every client sees the same values and a change from any client reaches all of them. `sessions` is a map keyed by a session identifier; each entry holds fields nobody else needs to see.

When routing an event, your update function needs to know which session it came from. Wrap events in your own type at the transport layer:

```python
@dataclass(frozen=True, slots=True)
class FromClient:
    client_id: str
    event: object
```

The handler that owns the transport injects `FromClient` values. `update` unwraps them and threads the `client_id` through to whatever per-session logic needs it.

## A broadcast pattern

The simplest collaboration pattern: any client's event runs through `update` once, and the resulting model is broadcast to every connected renderer. No originator tracking, no conflict resolution; the model is the source of truth.

```python
from dataclasses import replace

from plushie.events import Click


def update(self, model, event):
    match event:
        case FromClient(client_id=cid, event=Click(id="inc")):
            new_model = replace(model, counter=model.counter + 1)
            self._broadcast_snapshot(new_model)
            return new_model
        case _:
            return model
```

`_broadcast_snapshot` is a method on the App instance that walks the list of connected clients and pushes a fresh snapshot down each one's connection. Because `view` is a pure function of the model, every client renders the same tree, diffs against its own previous tree, and shows the change.

For high-frequency events (typing in a shared editor, dragging a shared cursor), do the rendering and diffing once per connection. The runtime already handles that per client; your broadcast loop just needs to call into each runtime handle's snapshot path.

### Preserving per-session fields

A pure broadcast overwrites the full model, which is wrong for the per-session fields discussed earlier. The fix is to keep shared and per-session state as separate sub-structures and merge only the shared portion on the receiving side:

```python
@dataclass(frozen=True, slots=True)
class SharedState:
    counter: int = 0
    experiments: tuple["Experiment", ...] = ()


@dataclass(frozen=True, slots=True)
class Model:
    shared: SharedState = field(default_factory=SharedState)
    session: SessionState = field(default_factory=SessionState)


def apply_shared(model: Model, shared: SharedState) -> Model:
    return replace(model, shared=shared)
```

Each client's local model carries its own `session` block. Broadcasts replace `shared` and leave `session` intact. A dark-mode toggle fired by one client updates only that client's `session.dark_mode`. An experiment edit fired by any client updates `shared.experiments` for everyone.

## SSH scaffold

SSH gives authenticated transport, key-based identity, and a stable subsystem protocol. Configure OpenSSH (or an in-process Erlang-style SSH daemon, or a Python library like `asyncssh`) with a subsystem handler that runs `python -m plushie connect myapp:App` for every accepted channel.

```
# sshd_config excerpt
Subsystem plushie /usr/bin/env python -m plushie connect myapp:App
```

On the server, one Python process supervises the app and accepts inbound SSH sessions. Each session's stdio gets bridged to a per-client `IoStreamAdapter` that feeds events into the shared runtime through `Runtime.inject()`. The runtime stays the single owner of the model; the SSH layer is just a way to multiplex bytes.

A minimal sketch of the per-session handler:

```python
from plushie.connection import Connection
from plushie.transport import IoStreamAdapter


def handle_ssh_channel(channel, runtime_handle, client_id):
    def on_event(ev):
        runtime_handle.inject(FromClient(client_id, ev))

    adapter = IoStreamAdapter(
        channel.makefile("rb"),
        channel.makefile("wb"),
        on_event=on_event,
    )
    conn = Connection.from_iostream(adapter)
    # Send the initial snapshot, then let update drive the rest.
```

Client connect:

```bash
plushie --exec "ssh -p 2222 server.example -s plushie"
```

Chapter 17 walks through a full browser scaffold with the WASM renderer; SSH follows the same pattern with a different transport.

## Threading and Flask

The runtime already runs on its own thread. `runtime.inject(event)` (or `handle.inject(event)` on a `RuntimeHandle`) posts an event onto the queue from any thread. This is how you wire HTTP webhooks, message queue consumers, or scheduled jobs into the app.

```python
import plushie
from flask import Flask, request

from myapp import App, WebhookReceived

handle = plushie.start(App)
web = Flask(__name__)


@web.post("/webhook")
def webhook():
    payload = request.get_json()
    handle.inject(WebhookReceived(payload=payload))
    return {"ok": True}
```

`plushie.start` returns a `RuntimeHandle` that lives alongside Flask's blocking `web.run()`. Requests land on Flask's thread pool, hand the payload to `inject`, and return. The runtime picks it up on the next queue pop and runs `update` exactly like any other event.

The same pattern covers scheduled tasks (post a custom event from a `threading.Timer`), Kafka consumers (post events from the consumer thread), and internal RPC endpoints. Anything that can call a Python function can inject events.

## Security considerations

The SDK does not authenticate anything. It accepts bytes from whatever transport you hand it and assumes any sender is authorised. Authentication and authorisation belong at the transport layer.

For SSH: configure the daemon's `AuthorizedKeysFile` and key algorithms the way you would for any subsystem. The Erlang `:ssh` daemon supports `authorized_keys` out of the box, `asyncssh` and OpenSSH equally so. Restrict the subsystem so only authorised users reach the Python process.

For WebSocket: terminate TLS at the edge, enforce origin checks in the handshake handler, validate session tokens before upgrading, and rate-limit inbound messages. The browser can lie about its `Origin` header; anything running in the browser can be tampered with. Treat every frame as untrusted input.

For TCP or Unix sockets: bind to `127.0.0.1` or a Unix path with restrictive permissions. If you have to expose a raw TCP port, front it with a reverse proxy that handles TLS and authentication.

None of these checks live in the SDK. Add them at the SSH daemon, the WebSocket framework, or the reverse proxy. The SDK's job starts after the bytes are trusted.

## Pointer to chapter 17

The next chapter builds the concrete WASM scenario: compiling the renderer to WebAssembly, serving it alongside a WebSocket endpoint, and connecting a browser client to a Python app over `WebSocketAdapter`. It reuses everything you have seen here: `connect` mode semantics, per-session state, `runtime.inject`, and the security boundary. The only new parts are the build commands and the browser glue.

Next: [Browser and WASM](17-browser-and-wasm.md).
