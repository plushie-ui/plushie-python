# Versioning

Plushie has three version numbers that evolve independently: the
Python SDK, the plushie-rust release it targets, and the wire
protocol spoken between the SDK and the renderer. All three live
in `plushie` modules and are read at handshake time.

## SDK version

The Python package's own semver, declared as `version` in
`pyproject.toml` and exposed as `plushie.__version__`. It is
published to PyPI as the `plushie` distribution. Bumps cover
Python-side changes: bug fixes, new widget builders, type
improvements, docs, test helpers, and so on.

Pre-1.0, breaking changes may land in any minor bump (`0.X.0`).
Patch releases (`0.X.Y`) stay backwards-compatible within the SDK.
Pin applications accordingly in `pyproject.toml`:

```toml
[project]
dependencies = [
    "plushie==0.6.0",         # exact pin, safest pre-1.0
    # or
    "plushie>=0.6,<0.7",      # allow patch bumps, reject minor
]
```

The [CHANGELOG](../../CHANGELOG.md) lists every release's changes
with breaking items called out first.

## `PLUSHIE_RUST_VERSION`

`plushie.binary.PLUSHIE_RUST_VERSION` is a string constant that
pins the exact plushie-rust release this SDK targets. Every
plushie-rust artifact the SDK touches comes from that release:

- The `plushie-renderer` binary downloaded by
  `python -m plushie download`.
- The `cargo-plushie` tool invoked by
  `python -m plushie build`. The build fails if the tool on
  `PATH` does not match this version exactly, and prints a
  `cargo install cargo-plushie --version X.Y.Z --locked` command.
- The WASM renderer bundle fetched by
  `python -m plushie download --wasm`.
- The version string embedded in the virtual app crate generated
  during native extension builds.

Bumping this constant is how the SDK opts in to a newer renderer.
The version axes move independently:

- SDK-only fixes bump the SDK version only; `PLUSHIE_RUST_VERSION`
  stays put.
- plushie-rust upgrades bump `PLUSHIE_RUST_VERSION` (and usually
  the SDK version too, to cut a release that ships the upgrade).

`PLUSHIE_RUST_VERSION` must match a plushie-rust release exactly:
no semver ranges, no fuzzy pins. Exact match is the only way to
guarantee the renderer binary, the generated dependencies, and
the wire protocol travel together. This is why applications pin
the Python SDK rather than pinning the renderer binary separately:
the SDK carries the right target version, and `python -m plushie
download` resolves it.

## Wire protocol version

`plushie.protocol.PROTOCOL_VERSION` is a constant integer embedded
in the `settings` message the runtime sends to the renderer on
startup. The renderer advertises its own protocol number in the
`hello` message it sends back. The Python SDK compares the two
during the handshake in `plushie.connection`:

```python
from plushie.connection import Connection

conn = Connection.spawn()
hello = conn.wait_hello(timeout=10.0)
# hello.protocol matches PROTOCOL_VERSION, or wait_hello raises
# ProtocolVersionMismatchError.
```

On mismatch the handshake raises `ProtocolVersionMismatchError`
(a subclass of `ProtocolMismatchError`) carrying the `expected`
and `got` version numbers. A mismatched protocol is not safe to
continue on: the SDK tears the connection down.

Mismatches are a symptom, not the root cause. They indicate the
SDK and the renderer binary came from different plushie-rust
releases. Realigning `PLUSHIE_RUST_VERSION` with the installed
renderer, or re-running `python -m plushie download`, restores
compatibility.

## Upgrade guidance

To take a newer Python SDK release (which may bring a newer
renderer):

1. Update the `plushie` pin in `pyproject.toml` and reinstall
   (`pip install -U plushie` or your resolver's equivalent).
2. Run `python -m plushie download` to fetch the matching
   `plushie-renderer` binary, or `python -m plushie build` to
   rebuild from source. The build tool expects `cargo-plushie`
   on `PATH` at the same version; install it with the
   `cargo install cargo-plushie --version X.Y.Z --locked` command
   the build prints on mismatch.
3. Restart any running apps. The handshake at startup validates
   the protocol version before the runtime dispatches any
   events.

Applications that bundle the renderer for distribution (for
example PyInstaller, Nuitka, or Briefcase builds) pick up the
binary from the bundled location, which must also be refreshed
when the SDK is upgraded.

The CHANGELOG for each SDK release calls out whether it bumps
`PLUSHIE_RUST_VERSION` and what plushie-rust changes come with
it.

See
[plushie-rust's versioning policy](https://github.com/plushie-ui/plushie-rust/blob/main/docs/versioning.md)
for the canonical rules covering the full Rust workspace, the
wire protocol version, and cross-SDK compatibility.

## See also

- [Commands reference](commands.md) - `Command.exit` and related
  lifecycle commands the runtime issues on handshake failure
- [Events reference](events.md) - diagnostic and error event
  shapes surfaced when the renderer rejects a connection
- [Subscriptions reference](subscriptions.md) - renderer
  subscriptions that depend on a successful handshake
