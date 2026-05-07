# Concurrency shape

How plushie-python's runtime is structured under Python's
concurrency model, why the parts split the way they do, and the
discipline that holds them together. Other host SDKs have their
own concurrency shape; this is plushie-python's, and it is
downstream of Python and the GIL rather than cross-SDK
convergence.

## The runtime/connection split

Two long-lived concerns, separated by responsibility:

- **Connection** owns the renderer subprocess (or
  iostream/socket adapter). It owns wire framing, transport
  I/O, the hello handshake, and request/response correlation.
  It knows nothing about apps, models, views, or commands.
- **Runtime** owns the app's `init/update/view` loop, the
  current model and tree, the subscription set, the widget
  registry, and command execution. It knows nothing about the
  wire format or the renderer process internals.

Connection speaks wire, Runtime speaks Elm. They communicate
through a thread-safe queue: Connection's reader thread posts
decoded events, Runtime sends settings, snapshots, patches, and
effects through Connection's `send` API.

This split exists because the two responsibilities have
different lifetimes and different failure modes. Connection
crashes are renderer crashes; the recovery is reconnect and
replay state. Runtime crashes are app code crashes; the
recovery is revert to the last good model. Mixing the two
would couple recovery paths that should be independent.

## Threads in the runtime

One **runtime thread** owns all model state. `update` and
`view` are always called from this thread. No locks on model
or tree. The runtime thread reads from a `queue.Queue` and
processes events serially.

One **reader thread** in the connection reads wire frames from
the renderer, decodes them via `protocol.decode_message`, and
posts events onto the runtime's queue. A broken pipe surfaces
as a renderer-exit event posted to the same queue.

A **`ThreadPoolExecutor`** runs `Command.task(fn, tag)`
functions. Results are posted back to the event queue as
`AsyncResult(tag=tag, value=...)` events. A nonce per task
tracks identity so cancelled tasks cannot inject stale results
after `Command.cancel(tag)` ran.

**Timer threads** (`threading.Timer`) handle
`Subscription.every` ticks, `Command.send_after` delays, and
effect timeouts. They post events to the queue. Timers are
tracked so they can be cancelled cleanly on shutdown or
re-subscription.

**External injection.** `runtime.inject(event)` is thread-safe
(`queue.put`). Flask routes, message queue consumers,
background threads can inject events into the app's update
cycle without holding any runtime lock.

The mailbox is a `queue.Queue`; the runtime drains it with a
timeout-based `get` that lets the loop check for stop sentinel
and idle conditions cleanly. There is no spin loop, no busy
wait, no `time.sleep`-based polling.

## Why threads, not asyncio

The runtime is thread-based, not asyncio-based. This is
deliberate:

- **No `async` in user code.** `update` and `view` are sync.
  Forcing the user to `await` something would require their
  code to live inside an event loop, which makes embedding in
  Flask, Django, plain scripts, and notebook environments
  awkward.
- **The hot path is sync work.** Decoding a wire message,
  running `update`, computing a diff, encoding patches:
  every step is CPU-bound Python work. asyncio would add
  task-switch overhead without unlocking parallelism (the
  GIL still serializes the work).
- **External integration is easier.** A queue-based runtime
  composes with anything that can call `runtime.inject`.
  Mixing an asyncio runtime with a sync caller (or vice
  versa) is the recurring pain point of Python concurrency;
  the thread model side-steps it.
- **The renderer is where the parallelism is.** The renderer
  is a separate process with its own GIL-free Rust
  parallelism. Adding asyncio on the SDK side does not change
  that; the SDK side is supposed to be a small slice of the
  frame budget.

`Command.task` exists for the user's I/O-bound work, scheduled
on the executor and surfaced as events. Adding an
`async def`-friendly variant is a real question (see
`dsl-discipline.md`); replacing the runtime with asyncio is
not.

## Reconnect lifecycle

The connection's reader thread detects a broken pipe and posts
a renderer-exit event. The runtime thread handles it:

1. Cancel pending effect timers; emit
   `EffectResult(error="renderer_restarted")` for in-flight
   effects.
2. Call `app.handle_renderer_exit(model, reason)` (default:
   identity).
3. Try to reconnect with bounded exponential backoff.
4. On success: replay settings, send a fresh full snapshot,
   re-subscribe, re-open windows.
5. On failure: emit `RecoveryFailed`. In daemon mode, the
   runtime stays alive for a fresh connection; otherwise it
   exits.

State that survives a reconnect: the model, the subscription
set, async tasks (still running in the executor). State that
does not survive: in-flight effects (cancelled with the typed
error), pending widget ops (the renderer is gone), the
renderer's view of the tree (replaced by the fresh snapshot).

## Test session pool

The test framework runs sessions through
`plushie.testing.SessionPool`:

- One `plushie-renderer --mock --max-sessions N` process is
  started by the pool and shared across the test suite via
  the `pytest_plushie` plugin's session-scoped fixture.
- Each test gets a unique session ID; wire messages are
  tagged, the renderer routes to per-session state
  internally. Session startup is microseconds; renderer
  startup is amortized across the suite.
- `AppFixture(AppClass, plushie_pool)` runs `update` and
  `view` synchronously on the test thread (no runtime thread,
  no executor). The fixture's command processor handles
  `task`, `stream`, `done`, and `batch` inline; side-effecting
  commands that need a live renderer are no-ops in the
  fixture and exercised by integration tests directly.

The pool wraps the production `Connection`; it is not a
separate transport. Tests exercise the real wire path.

Windowed mode does not pool: each test gets its own renderer
because real iced windows do not multiplex cleanly across
sessions.

## What is not used

- **No asyncio in the runtime.** See above. User
  `Command.task` functions are sync; an asyncio-friendly
  variant is a possible future addition discussed under
  `dsl-discipline.md`.
- **No `multiprocessing`.** The renderer is the parallelism
  story; spawning extra Python processes from the runtime
  adds startup cost, IPC complexity, and pickle constraints
  for negligible win in the typical app.
- **No `threading.Condition` for signaling between threads.**
  The queue is the single signaling primitive. Adding
  conditions creates pairings that have to stay in sync; the
  queue handles both signaling and data.
- **No daemon threads for the runtime loop.** The runtime
  thread is non-daemon so a clean shutdown actually waits for
  it. Reader, executor, and timer threads can be daemon
  because their work is bounded by the runtime's lifetime.
- **No global runtime registry.** A program that wants
  multiple plushie apps creates multiple `Runtime` instances.
  There is no use case for hundreds of dynamically-spawned
  instances; if one appears, the shape can be revisited.
- **No `signal` handlers in library code.** Signal handling
  is the embedding application's choice. The runtime exposes
  `runtime.stop()` and exits cleanly when called.

## Implications

- A change that introduces a new long-lived thread gets a
  shape-level question first: which existing thread owns
  this work, what is the queue path, what is the shutdown
  posture, how is its crash surfaced.
- A change that makes Connection do something the Runtime
  already does is suspect. Wire framing in Runtime is wrong;
  app state in Connection is wrong.
- A change that calls `update` or `view` from a non-runtime
  thread is wrong. The fixture's synchronous mode is the
  documented exception (no runtime thread exists in that
  mode).
- A change that adds asyncio to the runtime path is
  stewardship-level; default to no, route through the
  posture documented here.
- Tests that rely on internal thread structure (peeking at
  the executor, the queue, timer state) are brittle and get
  rewritten to use the public test API.
