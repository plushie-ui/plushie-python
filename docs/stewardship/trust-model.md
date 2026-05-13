# Trust model

What plushie-python's role is in the wider Plushie trust model,
what it implements on its own side, and where the broader picture
lives. The authoritative trust-model doc lives in plushie-rust
(`docs/stewardship/trust-model.md`); this doc describes the host
SDK's half.

## The asymmetric model

Plushie's wire boundary is asymmetric:

- **Renderer-to-host.** Closed and typed. The renderer can only
  push the fixed enumeration of event variants and structured
  responses defined by the wire protocol. There is no opaque-blob
  path, no string-eval, no generic "run this on the host"
  instruction. The host is therefore structurally protected from
  a compromised or malicious renderer. The remote-rendering use
  case relies on this.
- **Host-to-renderer.** Broader by design. The host asks the
  renderer to load fonts and images by path, render screenshots,
  exercise effects (clipboard, file dialogs, notifications),
  spawn subprocesses through structured renderer exec args. A compromised host can
  drive the full operation set against the user's machine
  wherever the renderer runs. Bounding this is the
  capability-manifest direction in plushie-rust's roadmap, not
  current work.

plushie-python is on the trusted side of this boundary. The
runtime, the connection, the `ui` builders, and user code all
run as the host. Concerns that frame the host as adversary are
out of scope under the current model.

## What plushie-python implements on its side

Renderer-to-host integrity depends on the host SDK actually
holding up the closed-shape contract on the receiving end.
plushie-python's load-bearing pieces:

- **Typed event decoding.** `plushie.protocol.decode_message`
  parses incoming messages against the fixed event variant set.
  Known event families produce typed `@dataclass(frozen=True,
  slots=True)` instances; unknown widget event families produce
  a typed `RawEvent` with the family name preserved as a string
  field (not a callable, not a code path). The decoder never
  reaches into `eval`, `exec`, or `__import__` based on
  renderer-supplied data.
- **Effect and query response correlation.** Effect commands
  and window queries get an internal request ID and a timeout
  timer. Responses are routed back to the originating tag only
  after the request ID matches an outstanding request. A
  response with an unknown or stale ID is dropped. A spoofable
  correlation (e.g., delivering by tag without checking the
  request ID) would let a malicious renderer drive the wrong
  handler.
- **No host-side eval surface.** The runtime never `eval`s,
  `exec`s, or `getattr`s into user-supplied code paths based on
  renderer-supplied data. Strict whitelists in the codec
  (mouse buttons, named keys, length keywords) parse against a
  closed enumeration; unknown values fall through to a typed
  error or a `RawEvent`, never to a dynamic dispatch.
- **App-level hygiene is the app's choice.** An app that wires
  user-provided event content into shell-out commands or
  filesystem paths is making its own choice. The protocol
  cannot enforce app-side hygiene.

## What is not protected today

- **DoS and resource exhaustion.** A malicious renderer can
  flood typed events at the protocol rate. The runtime has
  coalescing for high-frequency event types and configurable
  per-subscription `max_rate`; a host SDK still has to handle
  the firehose gracefully (see `resilience.md`).
- **Host-to-renderer surface.** Effect dispatch, file path
  inputs, and renderer-owned child process spawn are full-trust today. Bounding
  them is the capability-manifest direction.
- **Same-access channels.** A user with shell access on the
  machine running the host can read its memory and files
  directly. plushie-python does not protect against the user
  acting on themselves.

## Channel posture

The wire protocol is byte-stream agnostic. Confidentiality and
integrity are delegated to the outer transport (OS pipe, named
pipe, SSH, mTLS, WebSocket over TLS). The wire is not its own
crypto layer, by design. Proposals to add per-message MACs or
encrypted fields to the wire format are misframed; that
responsibility belongs with the outer transport. The
`IoStreamAdapter` and `SocketAdapter` shapes exist precisely so
that the outer transport stays the user's choice.

The session token at the wire boundary binds a host to a
particular renderer instance. It is not a confidentiality
mechanism.

## Implications

- Work that loosens renderer-to-host integrity (a decoder that
  drops the closed-shape parse, an opaque-blob delivery path
  to user code, spoofable response correlation, a path that
  looks up Python attributes on renderer-supplied names) is a
  deliberate decision, not a routine refactor; default to no.
- Memory-corruption or RCE-shaped findings on either side are
  in scope today regardless of the broader capability-manifest
  direction. (Pure-Python code makes pure memory-corruption
  unlikely, but C-extension boundaries, `pickle`, and similar
  remain in scope.)
- Host-to-renderer concerns (file path inputs, effect dispatch,
  spawn surface) defer to the capability-manifest roadmap in
  plushie-rust.
- Wire-level confidentiality or integrity expectations belong
  with the outer transport.
- DoS and resource-exhaustion concerns are low priority;
  configurable knobs (per-subscription `max_rate`, runtime
  coalescing) are preferred over aggressive defaults.
