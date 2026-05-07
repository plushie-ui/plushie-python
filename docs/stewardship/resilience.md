# Resilience

plushie-python is meant to behave predictably when things go
wrong: an exception in the user's `update`, a malformed wire
message from the renderer, the renderer process crashing, a
broken pipe, a `view` that raises, a subscription source that
explodes, an async task that throws. Resilience here is graceful
behavior under those conditions, not hardening against an
attacker; that distinction lives in `trust-model.md`.

The user-facing promise is the host SDK's half of the broader
plushie promise: a renderer crash auto-recovers with state
re-sync, an app exception reverts to the last good state, neither
side takes the other down. This doc describes how plushie-python
holds up that half.

## What resilience means here

- **App exception revert.** Exceptions in `init`, `update`, and
  `view` are caught by the runtime, logged via
  `logger.exception`, and the model reverts to its pre-call
  state. The user does not need to wrap callbacks in
  `try`/`except`. After a flood threshold the runtime
  suppresses repeated log lines; the next clean call clears
  the suppression.
- **View-error tracking with frozen-UI overlay.** Consecutive
  `view` failures are tracked. After the warn threshold the
  runtime injects a frozen-UI overlay into the tree so the
  user can see the app is degraded rather than staring at a
  stale UI. The overlay clears on the next successful render.
- **Renderer crash auto-recovery.** The reader thread detects
  a broken pipe and posts a renderer-exit event. The runtime
  reconnects with bounded exponential backoff, replays settings,
  sends a fresh full snapshot to re-sync the tree, re-syncs all
  subscriptions, and re-opens all windows. The user's
  `handle_renderer_exit(model, reason)` callback can adjust
  the model before re-sync (e.g., reset transient UI state).
  If reconnection exhausts its attempt cap, the runtime emits a
  `RecoveryFailed` event; daemon mode keeps the runtime alive
  for a fresh connection.
- **Async task isolation.** `Command.task` runs the function
  in a `ThreadPoolExecutor`; exceptions are caught at the
  task boundary and logged. The runtime's update loop is not
  affected. Stale results from cancelled tasks are silently
  discarded via per-task nonces.
- **Subscription failure isolation.** A `subscribe` call that
  raises is caught and logged; the runtime keeps the previous
  subscription set. A timer thread that fires after its
  subscription was removed posts a `TimerTick` that the
  runtime drops if the subscription is gone.
- **Defensive parsing on the wire.** The codec assumes its
  input could be wrong: malformed MessagePack, unknown event
  variants, missing required fields, type-coercion mismatches.
  Unknown widget event families surface as `RawEvent` rather
  than crashing the decoder; structurally invalid frames fail
  cleanly with a typed error.
- **Return-shape validation.** `init` and `update` must return
  a bare model, `(model, Command)`, or `(model, [Command])`.
  Anything else raises `TypeError` immediately rather than
  silently corrupting state. A `None` return from `update`
  (the most common Python footgun, where `match` falls through
  with no branch) is detected, logged with the offending
  event, and the previous model is kept. See
  `elm-invariants.md`.
- **Coalescable event handling.** High-frequency `Move` events
  are buffered in a pending dict keyed by source; a
  zero-delay timer flushes them. Non-coalescable events flush
  the buffer first, preserving ordering. A flooding renderer
  cannot overwhelm the runtime queue at the protocol rate.

## What is appropriate to fail fast on

Some conditions are not recoverable at the framework level and
should fail fast rather than degrade:

- **Programming errors that violate runtime invariants.** Wrong
  return shape from `init`/`update`, a `WidgetDef` with a
  missing required method, a `view` that returns a non-dict.
  The right behavior is a clear error, not silent fallback.
- **Unrecoverable startup.** If the renderer binary cannot be
  resolved (`PlushieNotFoundError`), the connection raises at
  startup with a clear message and a hint at
  `python -m plushie download`. Attempting to operate without
  a renderer is not a degraded mode worth supporting.
- **Wire framing corruption on the input side.** A truncated
  or unparseable frame is not a recoverable condition; the
  reader surfaces it and exits, and the runtime's reconnect
  path takes over.

The line: degrade gracefully on user-facing conditions (app
code errors, parse errors, transport hiccups, renderer
crashes). Fail fast on framework-level invariant violations.

## Patterns in the codebase

Worth maintaining as the project evolves:

- `try`/`except` around `init`, `update`, `view`, `subscribe`,
  `window_config`, and user callbacks in the runtime;
  revert-and-log on exception.
- Wire-edge validation in `plushie.protocol.decode_message`;
  typed errors and `RawEvent` for unknowns, never silent
  passthrough of malformed input.
- Effect request tracking with timeout timers; stale responses
  dropped, in-flight responses correlated by request ID.
  Effects pending across a reconnect get
  `error: "renderer_restarted"`.
- Reconnect with fresh snapshot re-sync rather than attempting
  to replay buffered events.
- Coalescable event handling for high-frequency sources (mouse
  moves, scroll, slider drags) so a flooding renderer cannot
  overwhelm the runtime's queue.
- Suppression of repeated error logs after a flood threshold,
  with auto-clear on the next clean call.
- `_STOP_SENTINEL` and `Queue`-based shutdown so threads
  exit cleanly rather than being killed mid-call.

## What resilience is not

- **Not adversarial-input hardening.** The threat model is
  "things go wrong," not "attacker is trying to crash."
  Findings framed as the latter are usually misframed; see
  `trust-model.md`.
- **Not perfectionism.** The runtime does not try to fix the
  user's logic for them; it reverts and logs. The decoder
  does not invent values for missing required fields; it
  errors.
- **Not retry-at-any-cost.** A failed command surfaces a
  structured error event; the user's `update` decides whether
  to retry. The runtime does not retry on its own. Reconnect
  is the explicit exception, with a bounded backoff.
- **Not defense against impossible states.** Adding a
  defensive branch for a condition that cannot occur given
  the surrounding invariants is accidental complexity, not
  resilience. The bar for "cannot occur" is reading the
  surrounding code and being confident in the invariant, not
  exhaustive proof.

## Implications

- A real things-go-wrong path producing an ungraceful failure
  (an unhandled exception in the runtime loop, a missing
  revert on view error, a stale effect tag delivering to the
  wrong handler, a thread that hangs instead of exiting on
  shutdown) is in scope today and earns priority.
- Inconsistency between resilience patterns (one site reverts
  on error, another swallows; one source logs and retries,
  another logs and gives up) is itself a resilience bug
  because future maintainers cannot predict behavior.
- Defensive layers for conditions that cannot occur given the
  surrounding invariants are out of scope; they add accidental
  complexity without reducing real failure modes.
- Aborting on conditions where graceful degradation is the
  right answer ("this should panic on bad event content") is
  the wrong direction; the established pattern is
  reject-and-report.
