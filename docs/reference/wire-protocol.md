# Wire Protocol

The wire protocol defines the message format between the Python SDK
and the Rust renderer. The protocol is language-agnostic and shared
across every Plushie SDK. This reference describes the Python
perspective: how the SDK frames bytes, encodes outbound messages,
decodes inbound events, and manages the connection lifecycle.

For the complete message format specification (every field, every
patch operation, every event family), see the
[Renderer Protocol Spec](https://github.com/plushie-ui/plushie-rust/blob/main/docs/protocol.md).

## Wire formats

Two formats carry the same message structures. Framing lives in
`plushie.framing`; both classes expose `encode(msg)` for outbound
dicts and `feed(bytes)` for incoming data. `Connection.open(...)`
picks one via the `format=` keyword argument. The default is
`"msgpack"`.

```python
from plushie.connection import Connection

conn = Connection.open(mode="mock", format="msgpack")
```

Passing `format="json"` appends `--json` to the renderer command
line. Any other value raises `ValueError`.

### MessagePack (default)

`plushie.framing.MsgpackFraming` produces a 4-byte big-endian
unsigned integer length prefix followed by the MessagePack payload:

```
[4 bytes: payload length as u32 BE][msgpack payload bytes]
```

Binary values (`bytes`, `bytearray`) stay as native MessagePack
binary; no base64 round-trip. This is the preferred format for image
handles, pixel buffers, and high-rate updates.

### JSON (JSONL)

`plushie.framing.JsonFraming` emits one JSON object per line,
terminated by `\n`. Messages must not contain embedded newlines.
Binary values are base64-encoded on encode and decoded back on
`feed`. Non-finite floats (`NaN`, `Infinity`) are normalised to
`null` so JSON and MessagePack wire behaviour match.

JSON is human-readable, making it the format of choice for
debugging. Combine it with renderer-side logging:

```bash
RUST_LOG=plushie=debug python -m plushie run myapp:App 2>protocol.log
```

### Format detection

The renderer auto-detects the format from the first byte of stdin:
`0x7B` (`{`) means JSON, anything else means MessagePack. The SDK
passes `--json` explicitly when `format="json"`, so detection is
only a fallback for custom transports.

### Maximum message size

`plushie.framing.MAX_MESSAGE_SIZE` is 64 MiB. Frames exceeding the
cap raise `BufferOverflowError` (a subclass of `FramingError`) with
`size` and `limit` attributes. The same cap applies on both sides;
the renderer rejects oversize messages too.

## Protocol version

`plushie.protocol.PROTOCOL_VERSION` is `1`. The SDK stamps this into
every Settings message automatically (the `protocol_version` field
under `settings`), and compares it against the renderer's hello.
A mismatch raises `ProtocolVersionMismatchError` with `expected` and
`got` attributes set to the two integers.

## Startup handshake

`Connection.open(...)` fires the renderer subprocess and then the
SDK and renderer follow a fixed sequence:

1. SDK writes **Settings**. `plushie.protocol.settings()` wraps the
   app's `App.settings()` result and injects `protocol_version`.
   The subprocess is created with `stdin=PIPE`, `stdout=PIPE`,
   `stderr=PIPE` and `bufsize=0` so writes reach the renderer
   without host-side buffering.
2. Renderer auto-detects the wire format from the first byte and
   reads the Settings.
3. Renderer writes **hello**. The reader thread decodes it via
   `parse_hello()` into a `HelloInfo` dataclass with `protocol`,
   `version`, `name`, `mode`, `backend`, `transport`, `extensions`,
   `native_widgets`, and `widgets` fields.
4. `Connection.wait_hello(timeout=10.0)` blocks the caller until the
   hello arrives, validates the protocol version, and (if
   `expected_widgets` was passed to `open`) checks that every
   requested widget type appears in the renderer's capabilities.
5. SDK writes **snapshot**. The runtime calls `App.view()`,
   normalises the tree via `plushie.tree.normalize()`, and hands the
   dict to `Connection.send_snapshot()`.
6. Normal message exchange begins.

If the renderer crashes, the reader thread signals the runtime, the
runtime reconnects with exponential backoff, and the handshake
repeats from step 1 with a fresh snapshot.

## Encoding (SDK to renderer)

`plushie.protocol` exposes a pure function per outbound message
type. Each returns a plain dict ready for `MsgpackFraming.encode` or
`JsonFraming.encode`.

| Function | Wire `type` | When sent |
|---|---|---|
| `settings` | `settings` | Startup, renderer restart |
| `snapshot` | `snapshot` | First render, post-reconnect |
| `patch` | `patch` | Incremental tree updates |
| `subscribe_msg` | `subscribe` | Subscription activation |
| `unsubscribe_msg` | `unsubscribe` | Subscription removal |
| `widget_op` | `widget_op` | Non-targeted operations (`focus_next`, `focus_previous`, `announce`) |
| `window_op` | `window_op` | Window open, close, update, resize |
| `system_op` | `system_op` | System-wide operations |
| `system_query` | `system_query` | System-wide queries |
| `effect_msg` | `effect` | Platform effect requests |
| `image_op` | `image_op` | In-memory image lifecycle |
| `command` | `command` | Widget-targeted commands |
| `commands` | `commands` | Batch of widget-targeted commands |
| `interact_msg` | `interact` | Test interactions |
| `query_msg` | `query` | Tree and node queries |
| `tree_hash_msg` | `tree_hash` | Capture a deterministic tree hash |
| `screenshot_msg` | `screenshot` | Capture a rendered image |
| `reset_msg` | `reset` | Tear down a session |
| `advance_frame_msg` | `advance_frame` | Manual frame step (test / headless) |
| `register_effect_stub` | `register_effect_stub` | Install a canned effect response |
| `unregister_effect_stub` | `unregister_effect_stub` | Remove an installed stub |

Every builder accepts a `session=` keyword argument. In
single-session mode (the default), this is `""`. In multiplexed mode
(test session pool with `--max-sessions N`), each test session
passes its own ID so the renderer can route correctly.

### Settings envelope

`settings()` wraps the app-level settings dict under the wire key
`settings` and adds `protocol_version` when the caller omits it.
It also renames a user-facing `widget_config` key to the wire name
`extension_config` so app code can use the friendlier spelling.

```python
from plushie.protocol import settings

settings({"default_text_size": 14})
# -> {"type": "settings", "session": "",
#     "settings": {"default_text_size": 14, "protocol_version": 1}}
```

### Snapshot and patch

`snapshot(tree)` and `patch(ops)` both strip any `meta` keys from
their payload before encoding; those are SDK-only fields used by
`plushie.tree` during diffing and never cross the wire. The runtime
chooses between them: a snapshot is sent when there is no prior
tree (startup, reconnect), a patch is sent otherwise. If the diff
produces no operations, nothing is sent.

See [Built-in Widgets](built-in-widgets.md) for the node shape that
`snapshot.tree` carries, and `plushie.tree.diff` for the four patch
operations (`replace_node`, `update_props`, `insert_child`,
`remove_child`).

### Unified op envelope

`window_op`, `system_op`, `system_query`, and `image_op` share the
same wire shape: the op name sits flat beside `type`, the
op-specific data lives under `payload`. Addressing fields like
`window_id` stay at the top level.

```json
{
  "type": "window_op",
  "session": "",
  "op": "resize",
  "window_id": "main",
  "payload": {"width": 1024, "height": 768}
}
```

### Widget-targeted commands

`command(widget_id, family, value)` matches the shape the renderer
uses for events, which makes test traces symmetrical:

```json
{"type": "command", "session": "", "id": "editor", "family": "focus"}
```

`commands([...])` batches several of them into one wire message;
each item is a `(widget_id, family, value)` tuple. Entries with
`value=None` drop the `value` key entirely.

## Decoding (renderer to SDK)

`plushie.protocol.decode_message(msg)` turns an inbound dict (already
deserialised by the framing layer) into the appropriate dataclass
from `plushie.events` or `plushie.types`. Dispatch is by the `type`
field, then by `family` for event messages.

| Wire `type` | Returned as |
|---|---|
| `hello` | `HelloInfo` |
| `event` | The matching event class (see [Events](events.md)) |
| `effect_response` | `("_effect_response", wire_id, status, result, error)` tuple for the runtime to map tag back |
| `op_query_response` | `TreeHash`, `FocusedWidget`, `ImageList`, `SystemTheme`, `SystemInfo` |
| `diagnostic` | `DiagnosticMessage` |
| `effect_stub_register_ack` / `effect_stub_unregister_ack` | `EffectStubAck` |
| Any other response type | Original dict, for the caller to handle |

The runtime consumes `AsyncResult`, `StreamChunk`, `TimerTick`, and
`EffectResult` events that it generates Python-side. They never
cross the wire.

### Hello parsing tolerances

`parse_hello()` accepts either `protocol_version` or the legacy
`protocol` alias and rejects the message with `ValueError` if
neither is present or the value is not an integer. The
`native_widgets` list is read from `native_widgets` first, falling
back to the older `extension_widgets` key so the SDK works with
mid-migration renderer builds.

### Diagnostic mirroring

When the renderer emits a top-level `diagnostic` message, the
decoder mirrors it to the Python logging module at the matching
severity (`error`, `warn`, `info`) under the `plushie.protocol`
logger before returning the `DiagnosticMessage`. Unknown diagnostic
variant kinds raise `ValueError` at decode time so renderer version
skew fails loudly.

## Session multiplexing

Every wire message carries a `session` field. The single-session
default uses `""`. `Connection.open(max_sessions=N)` with `N > 1`
enables multiplexed mode, where each test session gets an isolated
session ID and the renderer maintains per-session trees,
subscriptions, effects, and caches.

Session lifecycle events (`session_error`, `session_closed`) are
delivered as `SessionError` and `SessionClosed` events. Test code
that shares a renderer across pytest workers uses
`plushie.testing.SessionPool` to manage IDs.

## Interact protocol

Test interactions (`click`, `type_text`, etc.) use a synchronous
request-response cycle:

1. The SDK sends an `interact` message with a selector and payload.
2. The renderer resolves the selector, simulates the interaction,
   and sends one or more `interact_step` messages with intermediate
   events.
3. The renderer sends a final `interact_response` carrying the last
   batch of events.
4. The fixture drives those events through `App.update` and returns
   to the test author.

This keeps `fixture.click("#save")` fully synchronous: the call
blocks until the full update cycle (event -> update -> view -> patch)
completes.

## Custom transports

`Connection.from_iostream(adapter)` skips the subprocess step and
drives a caller-supplied adapter instead. `plushie.transport`
provides `IoStreamAdapter` for plain readable/writable streams,
`SocketAdapter` for TCP and named-pipe addresses, and
`WebSocketAdapter` for browser-hosted WASM renderers.

```python
from plushie.connection import Connection
from plushie.transport import IoStreamAdapter

adapter = IoStreamAdapter(read_stream=sock, write_stream=sock)
conn = Connection.from_iostream(adapter)
```

The adapter is responsible for its own framing. For raw byte
streams, instantiate `MsgpackFraming` or `JsonFraming` directly and
feed bytes through.

## Resolving the binary

`Connection.open(binary_path=...)` accepts an explicit path. When
omitted, `plushie.binary.resolve()` walks a fixed search order:
the `PLUSHIE_BINARY_PATH` environment variable first, then the
project's download cache, then the built extensions directory. If
`PLUSHIE_BINARY_PATH` is set but the file is missing, resolution
raises immediately rather than silently falling back.

## See also

- [Events reference](events.md) - the event classes `decode_message` produces
- [Commands reference](commands.md) - commands the SDK encodes onto the wire
- [Subscriptions reference](subscriptions.md) - subscribe and unsubscribe messages
- [Built-in Widgets reference](built-in-widgets.md) - the node shape inside snapshot and patch
- [Renderer Protocol Spec](https://github.com/plushie-ui/plushie-rust/blob/main/docs/protocol.md) - the authoritative field-level reference
