# Versioning

The Python SDK and the underlying plushie-rust release have
independent version numbers. The key vocabulary:

- **SDK version**: `plushie.__version__` (and the `version` field in
  `pyproject.toml`). Bumps for SDK-only changes: bug fixes, Python
  refactors, docs, new high-level APIs built on the existing
  protocol.
- **plushie-rust version**: `plushie.binary.PLUSHIE_RUST_VERSION`.
  Pins the matching renderer binary, the matching `cargo-plushie`
  build tool, and the generated Cargo.toml dependency versions.
  Bumps when we opt into a new plushie-rust release (new widgets,
  protocol additions, renderer bug fixes).

Two axes, two bumps:

- SDK-only fixes bump the SDK version only. `PLUSHIE_RUST_VERSION`
  stays the same.
- plushie-rust upgrades bump `PLUSHIE_RUST_VERSION` inside this SDK,
  and typically bump the SDK version too.

## Compatibility rule

An SDK release's `PLUSHIE_RUST_VERSION` must match the plushie-rust
release it targets exactly. No semver ranges. The renderer binary,
the generated Cargo.toml deps, and the wire protocol travel
together, so a single mismatched version takes the SDK out of sync
with itself. Exact-match removes that class of bug.

## cargo-plushie

`cargo-plushie` ships at the same version as `PLUSHIE_RUST_VERSION`.
Install the matching build tool with:

```bash
cargo install cargo-plushie --version <PLUSHIE_RUST_VERSION> --locked
```

For local development against an in-flight plushie-rust checkout,
set `PLUSHIE_RUST_SOURCE_PATH` instead. The SDK runs cargo-plushie
directly from the workspace via `cargo run -p cargo-plushie`.

## Version skew detection

At connection time the runtime compares the renderer's reported
version against `PLUSHIE_RUST_VERSION` and logs a warning on
mismatch. Because the pin is exact, a warning indicates that either
the SDK has been bumped but the installed binary hasn't, or vice
versa. Re-run `python -m plushie download` or `python -m plushie
build` to realign.
