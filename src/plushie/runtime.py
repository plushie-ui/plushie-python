"""Elm-architecture event loop for plushie applications.

The ``Runtime`` class owns the full update cycle: init -> view ->
snapshot -> main loop (receive -> update -> commands -> view -> diff ->
patch -> sync subs -> sync windows).

This module is the Python equivalent of
``toddy-elixir/lib/plushie/runtime.ex`` and its submodules
(commands.ex, subscriptions.ex, windows.ex).

Usage::

    from plushie.runtime import Runtime

    runtime = Runtime(app, connection)
    runtime.run()       # blocks until exit
    runtime.inject(ev)  # thread-safe event injection

Or via the top-level API::

    import plushie
    plushie.run(Counter)
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Empty, Queue
from typing import Any

from plushie.app import App, AppBuilder
from plushie.commands import Command
from plushie.connection import Connection
from plushie.effects import DEFAULT_TIMEOUTS
from plushie.events import (
    AllWindowsClosed,
    AsyncResult,
    EffectResult,
    MouseMove,
    SensorResize,
    StreamChunk,
    TimerTick,
)
from plushie.protocol import (
    advance_frame_msg,
    effect_msg,
    extension_command,
    extension_commands,
    image_op,
    widget_op,
    window_op,
)
from plushie.subscriptions import Subscription
from plushie.tree import Node, diff, normalize
from plushie.types import HelloInfo

logger = logging.getLogger("plushie")

# Default timeout for effect requests (milliseconds).
_EFFECT_TIMEOUT_MS: int = 30_000


# ---------------------------------------------------------------------------
# unwrap_result
# ---------------------------------------------------------------------------


def unwrap_result(result: Any) -> tuple[Any, list[Command]]:
    """Validate and normalize an init/update return value.

    Accepts:
    - Bare model (any non-tuple value)
    - ``(model, Command)``
    - ``(model, [Command, ...])``

    Returns ``(model, commands)`` where commands is always a list.

    Raises:
        TypeError: On structurally invalid returns.
    """
    if isinstance(result, tuple):
        if len(result) != 2:
            raise TypeError(
                f"init/update returned a {len(result)}-element tuple, "
                "expected a bare model or (model, command)"
            )
        model, cmds = result
        if isinstance(cmds, Command):
            return model, [cmds]
        if isinstance(cmds, list):
            for item in cmds:
                if not isinstance(item, Command):
                    raise TypeError(
                        f"init/update returned (model, commands) but the "
                        f"command list contains {item!r}, expected Command"
                    )
            return model, cmds
        raise TypeError(
            f"init/update returned (model, commands) but commands is "
            f"{cmds!r}, expected a Command or list of Commands"
        )
    return result, []


# ---------------------------------------------------------------------------
# Window detection helpers
# ---------------------------------------------------------------------------

# Window prop keys that can be specified on window nodes.
_WINDOW_PROP_KEYS = frozenset(
    {
        "title",
        "size",
        "width",
        "height",
        "position",
        "min_size",
        "max_size",
        "maximized",
        "fullscreen",
        "visible",
        "resizable",
        "closeable",
        "minimizable",
        "decorations",
        "transparent",
        "blur",
        "level",
        "exit_on_close_request",
    }
)


def detect_windows(tree: Node | None) -> set[str]:
    """Detect window node IDs from the tree.

    Only recognizes window nodes at root level or as direct children
    of the root (matching the Rust renderer's expected depth).
    """
    if tree is None:
        return set()
    if tree.get("type") == "window":
        node_id = tree.get("id")
        return {node_id} if node_id else set()
    children = tree.get("children", [])
    return {
        child["id"]
        for child in children
        if isinstance(child, dict) and child.get("type") == "window" and child.get("id")
    }


def extract_window_props(tree: Node | None, window_id: str) -> dict[str, Any]:
    """Extract window-specific props from a window node in the tree."""
    if tree is None:
        return {}
    node = _find_window_node(tree, window_id)
    if node is None:
        return {}
    props = node.get("props", {})
    return {k: v for k, v in props.items() if k in _WINDOW_PROP_KEYS}


def _find_window_node(tree: Node, window_id: str) -> Node | None:
    """Find a window node at root or direct-child level."""
    if tree.get("type") == "window" and tree.get("id") == window_id:
        return tree
    for child in tree.get("children", []):
        if (
            isinstance(child, dict)
            and child.get("type") == "window"
            and child.get("id") == window_id
        ):
            return child
    return None


# ---------------------------------------------------------------------------
# Coalescing helpers
# ---------------------------------------------------------------------------


def coalesce_key(event: Any) -> Any | None:
    """Return the coalescing key for an event, or None if not coalescable.

    High-frequency events (mouse moves, sensor resizes) are collapsed
    so only the latest value is processed per flush cycle.
    """
    if isinstance(event, MouseMove):
        return ("mouse_move",)
    if isinstance(event, SensorResize):
        return ("sensor_resize", event.id)
    return None


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


class Runtime:
    """The Elm-architecture event loop.

    Owns the model, runs update/view/diff cycles, manages commands,
    subscriptions, windows, and async tasks.

    The runtime is designed to be run on its own thread (or blocking
    the main thread). Events from the renderer arrive via a reader
    thread; external events can be injected thread-safely via
    ``inject()``.

    Args:
        app: The application instance (or an ``AppBuilder`` which will
            be ``build()``-ed).
        connection: An open ``Connection`` to the renderer.
        daemon: If ``True``, ``AllWindowsClosed`` does not stop the
            runtime.
    """

    def __init__(
        self,
        app: App[Any] | AppBuilder,
        connection: Connection,
        *,
        daemon: bool = False,
    ) -> None:
        if isinstance(app, AppBuilder):
            app = app.build()

        self._app: App[Any] = app
        self._conn: Connection = connection
        self._daemon: bool = daemon

        # Model state
        self._model: Any = None
        self._tree: Node | None = None

        # Event queue -- all events (renderer + injected + internal) flow here.
        self._queue: Queue[Any] = Queue()

        # Running flag
        self._running: bool = False

        # Subscription state
        self._subscriptions: dict[tuple[str, ...], _SubEntry] = {}
        self._subscription_keys: list[tuple[str, ...]] = []

        # Window state
        self._windows: set[str] = set()

        # Async task tracking: tag -> (future, nonce)
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="plushie-task"
        )
        self._async_tasks: dict[str, tuple[Future[Any], int]] = {}
        self._nonce_counter: int = 0

        # Pending effect requests: request_id -> Timer
        self._pending_effects: dict[str, threading.Timer] = {}

        # Pending send_after timers: event_key -> Timer
        self._pending_timers: dict[Any, threading.Timer] = {}

        # Pending coalesced events: key -> event
        self._pending_coalesce: dict[Any, Any] = {}
        self._coalesce_timer: threading.Timer | None = None

        # Consecutive error count for rate-limited logging
        self._consecutive_errors: int = 0

        # Reader thread
        self._reader_thread: threading.Thread | None = None

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def run(self) -> None:
        """Run the event loop (blocking).

        Initializes the app, sends settings and the first snapshot,
        then loops processing events until ``Command.exit()`` or
        ``AllWindowsClosed`` (non-daemon mode) or the renderer exits
        normally.
        """
        try:
            self._running = True
            self._start_reader()
            self._initialize()
            self._main_loop()
        finally:
            self._cleanup()

    def inject(self, event: Any) -> None:
        """Inject an event into the runtime from any thread.

        The event will be processed in the next iteration of the
        event loop, going through ``update()`` like any other event.

        Thread-safe.
        """
        self._queue.put(event)

    @property
    def model(self) -> Any:
        """The current application model."""
        return self._model

    @property
    def is_running(self) -> bool:
        """Whether the event loop is currently running."""
        return self._running

    # -------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------

    def _initialize(self) -> None:
        """Run the init -> settings -> view -> snapshot startup sequence."""
        # 1. Call app.init()
        try:
            raw = self._app.init()
            model, commands = unwrap_result(raw)
        except Exception:
            logger.exception("plushie runtime: app.init() raised")
            raise

        self._model = model

        # 2. Send settings
        app_settings = {}
        try:
            app_settings = self._app.settings()
        except Exception:
            logger.exception("plushie runtime: app.settings() raised")

        self._conn.send_settings(app_settings)

        # 3. Render initial view
        tree = self._safe_view(model)
        self._tree = tree

        # 4. Send full snapshot
        if tree is not None:
            self._conn.send_snapshot(tree)

        # 5. Execute initial commands
        self._execute_commands(commands)

        # 6. Sync subscriptions and windows
        self._sync_subscriptions(model)
        self._sync_windows(tree)

    # -------------------------------------------------------------------
    # Main event loop
    # -------------------------------------------------------------------

    def _main_loop(self) -> None:
        """Process events until stopped."""
        while self._running:
            try:
                event = self._queue.get(timeout=0.1)
            except Empty:
                continue

            if event is None:
                # Connection closed / reader thread finished
                if self._attempt_reconnect():
                    continue
                logger.info("plushie runtime: connection closed, stopping")
                self._running = False
                break

            # HelloInfo from the renderer -- log and continue
            if isinstance(event, HelloInfo):
                logger.info(
                    "plushie runtime: renderer connected -- %s v%s (%s, %s)",
                    event.name,
                    event.version,
                    event.backend,
                    event.transport,
                )
                continue

            # AllWindowsClosed in non-daemon mode -> dispatch then stop
            if isinstance(event, AllWindowsClosed) and not self._daemon:
                self._run_update(event)
                self._running = False
                break

            # Coalescable event -> store and defer
            c_key = coalesce_key(event)
            if c_key is not None:
                self._store_coalescable(c_key, event)
                continue

            # Internal runtime events (tuples from task/stream/coalesce)
            if isinstance(event, tuple) and event and isinstance(event[0], str):
                if event[0] == "_async_result" and len(event) == 4:
                    self._flush_coalescables()
                    self._handle_async_result(event[1], event[2], event[3])
                    continue
                if event[0] == "_stream_value" and len(event) == 4:
                    self._flush_coalescables()
                    self._handle_stream_value(event[1], event[2], event[3])
                    continue
                if event[0] == "_flush_coalescables":
                    self._flush_coalescables()
                    continue

            # Normal event -> flush coalescables first, then process
            self._flush_coalescables()
            self._run_update(event)

    # -------------------------------------------------------------------
    # Update cycle
    # -------------------------------------------------------------------

    def _run_update(self, event: Any) -> None:
        """Full update cycle: update -> commands -> view -> diff -> patch -> sync."""
        app = self._app
        model = self._model

        # Cancel effect timeout if this is an EffectResult
        if isinstance(event, EffectResult):
            self._cancel_pending_effect(event.request_id)

        result = self._safe_update(app, model, event)
        if result is None:
            self._consecutive_errors += 1
            return

        new_model, commands = result
        self._model = new_model
        self._consecutive_errors = 0

        # Execute commands
        self._execute_commands(commands)

        # Render and sync
        new_tree = self._render_and_sync(new_model)
        self._tree = new_tree

        # Sync subscriptions and windows
        self._sync_subscriptions(new_model)
        self._sync_windows(new_tree)

    def _safe_update(
        self, app: App[Any], model: Any, event: Any
    ) -> tuple[Any, list[Command]] | None:
        """Call app.update() with error handling and rate-limited logging."""
        try:
            raw = app.update(model, event)
            if raw is None:
                count = self._consecutive_errors + 1
                if count <= 10:
                    logger.error(
                        "plushie runtime: update() returned None -- "
                        "forgot a catch-all? Add 'case _: return model'"
                    )
                return None
            return unwrap_result(raw)
        except Exception:
            count = self._consecutive_errors + 1
            if count <= 10:
                logger.exception("plushie runtime: update() raised")
            elif count <= 100:
                logger.debug(
                    "plushie runtime: update() raised (repeated)", exc_info=True
                )
            elif count == 101:
                logger.warning(
                    "plushie runtime: 100+ consecutive update errors -- "
                    "suppressing further logs"
                )
            elif count % 1000 == 0:
                logger.warning(
                    "plushie runtime: %d consecutive errors",
                    count,
                )
            return None

    def _safe_view(self, model: Any) -> Node | None:
        """Call app.view() + normalize with error handling."""
        try:
            raw_tree = self._app.view(model)
            return normalize(raw_tree)
        except Exception:
            logger.exception("plushie runtime: view() raised")
            return None

    def _render_and_sync(self, model: Any) -> Node | None:
        """Render view, diff against old tree, send snapshot or patch."""
        new_tree = self._safe_view(model)
        if new_tree is None:
            return self._tree

        old_tree = self._tree
        if old_tree is None:
            # First render or after restart -> full snapshot
            self._conn.send_snapshot(new_tree)
        else:
            ops = diff(old_tree, new_tree)
            if ops:
                self._conn.send_patch(ops)

        return new_tree

    # -------------------------------------------------------------------
    # Command execution
    # -------------------------------------------------------------------

    def _execute_commands(self, commands: list[Command]) -> None:
        """Execute a list of commands."""
        for cmd in commands:
            self._execute_command(cmd)

    def _execute_command(self, cmd: Command) -> None:
        """Execute a single command."""
        t = cmd.type
        p = cmd.payload

        if t == "none":
            return

        if t == "batch":
            self._execute_commands(p.get("commands", []))
            return

        if t == "exit":
            logger.info("plushie runtime: exit command received -- stopping")
            self._running = False
            return

        if t == "done":
            mapper = p["mapper"]
            value = p["value"]
            event = mapper(value)
            self._queue.put(event)
            return

        if t == "task":
            self._start_task(p["fn"], p["tag"])
            return

        if t == "stream":
            self._start_stream(p["fn"], p["tag"])
            return

        if t == "cancel":
            self._cancel_task(p["tag"])
            return

        if t == "send_after":
            self._schedule_send_after(p["delay"], p["event"])
            return

        if t == "effect":
            self._send_effect(p["id"], p["kind"], p.get("opts", {}))
            return

        if t == "widget_op":
            op_name = p.get("op", "")
            payload_without_op = {k: v for k, v in p.items() if k != "op"}
            msg = widget_op(op_name, payload_without_op, session=self._conn.session)
            self._conn.send(msg)
            return

        if t == "window_op":
            op_name = p.get("op", "")
            win_id = p.get("window_id", "")
            op_settings = {k: v for k, v in p.items() if k not in ("op", "window_id")}
            msg = window_op(
                op_name, win_id, op_settings or None, session=self._conn.session
            )
            self._conn.send(msg)
            return

        if t == "window_query":
            op_name = p.get("op", "")
            win_id = p.get("window_id", "")
            op_settings = {k: v for k, v in p.items() if k not in ("op", "window_id")}
            msg = window_op(
                op_name, win_id, op_settings or None, session=self._conn.session
            )
            self._conn.send(msg)
            return

        if t == "image_op":
            op_name = p.get("op", "")
            handle = p.get("handle", "")
            msg = image_op(
                op_name,
                handle,
                data=p.get("data"),
                pixels=p.get("pixels"),
                width=p.get("width"),
                height=p.get("height"),
                session=self._conn.session,
            )
            self._conn.send(msg)
            return

        if t == "extension_command":
            msg = extension_command(
                p["node_id"],
                p["op"],
                p.get("payload"),
                session=self._conn.session,
            )
            self._conn.send(msg)
            return

        if t == "extension_commands":
            cmds = [
                {"node_id": c[0], "op": c[1], "payload": c[2]}
                for c in p.get("commands", [])
            ]
            msg = extension_commands(cmds, session=self._conn.session)
            self._conn.send(msg)
            return

        if t == "advance_frame":
            msg = advance_frame_msg(p.get("timestamp", 0), session=self._conn.session)
            self._conn.send(msg)
            return

        logger.warning("plushie runtime: unknown command type: %s", t)

    # -------------------------------------------------------------------
    # Task management
    # -------------------------------------------------------------------

    def _next_nonce(self) -> int:
        """Generate a monotonically increasing nonce."""
        self._nonce_counter += 1
        return self._nonce_counter

    def _start_task(self, fn: Any, tag: str) -> None:
        """Run fn in the executor.  Result delivered as AsyncResult."""
        self._cancel_task(tag)
        nonce = self._next_nonce()

        def task_wrapper() -> None:
            try:
                result = fn()
                self._queue.put(("_async_result", tag, nonce, result))
            except Exception as exc:
                self._queue.put(("_async_result", tag, nonce, ("_error", exc)))

        future = self._executor.submit(task_wrapper)
        self._async_tasks[tag] = (future, nonce)

    def _start_stream(self, fn: Any, tag: str) -> None:
        """Run fn(emit) in the executor.  emit() delivers StreamChunk events."""
        self._cancel_task(tag)
        nonce = self._next_nonce()

        def emit(value: Any) -> None:
            self._queue.put(("_stream_value", tag, nonce, value))

        def stream_wrapper() -> None:
            try:
                result = fn(emit)
                self._queue.put(("_async_result", tag, nonce, result))
            except Exception as exc:
                self._queue.put(("_async_result", tag, nonce, ("_error", exc)))

        future = self._executor.submit(stream_wrapper)
        self._async_tasks[tag] = (future, nonce)

    def _cancel_task(self, tag: str) -> None:
        """Cancel a running task by tag."""
        entry = self._async_tasks.pop(tag, None)
        if entry is not None:
            future, _nonce = entry
            future.cancel()

    def _handle_async_result(self, tag: str, nonce: int, result: Any) -> None:
        """Handle an async task completion, checking nonce for staleness."""
        entry = self._async_tasks.get(tag)
        if entry is None or entry[1] != nonce:
            return  # stale or unknown

        self._async_tasks.pop(tag, None)

        if isinstance(result, tuple) and len(result) == 2 and result[0] == "_error":
            exc = result[1]
            logger.error("plushie runtime: async task %r crashed: %s", tag, exc)
            self._run_update(AsyncResult(tag=tag, value=("error", str(exc))))
        else:
            self._run_update(AsyncResult(tag=tag, value=result))

    def _handle_stream_value(self, tag: str, nonce: int, value: Any) -> None:
        """Handle a stream chunk, checking nonce for staleness."""
        entry = self._async_tasks.get(tag)
        if entry is None or entry[1] != nonce:
            return  # stale
        self._run_update(StreamChunk(tag=tag, value=value))

    # -------------------------------------------------------------------
    # send_after
    # -------------------------------------------------------------------

    def _schedule_send_after(self, delay_ms: int, event: Any) -> None:
        """Schedule an event for delivery after delay_ms milliseconds."""
        # Cancel existing timer for same event to prevent duplicates
        old = self._pending_timers.pop(
            id(event) if not isinstance(event, str) else event, None
        )
        if old is not None:
            old.cancel()

        event_key = id(event) if not isinstance(event, str) else event

        def fire() -> None:
            self._pending_timers.pop(event_key, None)
            self._queue.put(event)

        timer = threading.Timer(delay_ms / 1000.0, fire)
        timer.daemon = True
        timer.start()
        self._pending_timers[event_key] = timer

    # -------------------------------------------------------------------
    # Effect tracking
    # -------------------------------------------------------------------

    def _send_effect(self, request_id: str, kind: str, opts: dict[str, Any]) -> None:
        """Send an effect request to the renderer with timeout tracking."""
        msg = effect_msg(request_id, kind, opts, session=self._conn.session)
        self._conn.send(msg)

        timeout_ms = DEFAULT_TIMEOUTS.get(kind, _EFFECT_TIMEOUT_MS)

        def timeout_fire() -> None:
            self._pending_effects.pop(request_id, None)
            self._queue.put(
                EffectResult(
                    request_id=request_id,
                    status="error",
                    result=None,
                    error="timeout",
                )
            )

        timer = threading.Timer(timeout_ms / 1000.0, timeout_fire)
        timer.daemon = True
        timer.start()
        self._pending_effects[request_id] = timer

    def _cancel_pending_effect(self, request_id: str) -> None:
        """Cancel the timeout timer for a resolved effect."""
        timer = self._pending_effects.pop(request_id, None)
        if timer is not None:
            timer.cancel()

    def _flush_pending_effects(self, reason: str) -> None:
        """Flush all pending effects (e.g. on renderer restart)."""
        for request_id, timer in list(self._pending_effects.items()):
            timer.cancel()
            self._run_update(
                EffectResult(
                    request_id=request_id,
                    status="error",
                    result=None,
                    error=reason,
                )
            )
        self._pending_effects.clear()

    # -------------------------------------------------------------------
    # Subscription diffing
    # -------------------------------------------------------------------

    def _sync_subscriptions(self, model: Any) -> None:
        """Synchronize subscriptions with the app's subscribe() output."""
        try:
            new_specs = self._app.subscribe(model)
            if not isinstance(new_specs, list):
                logger.error(
                    "plushie runtime: subscribe() must return a list, got: %r",
                    type(new_specs).__name__,
                )
                new_specs = []
        except Exception:
            logger.exception("plushie runtime: subscribe() raised")
            new_specs = []

        new_by_key: dict[tuple[str, ...], Subscription] = {
            spec.key: spec for spec in new_specs
        }
        new_sorted_keys = sorted(new_by_key.keys())

        if new_sorted_keys == self._subscription_keys:
            # Keys unchanged -- check for max_rate updates only
            self._update_max_rates(new_by_key)
            return

        old_key_set = set(self._subscriptions.keys())
        new_key_set = set(new_by_key.keys())

        # Stop removed subscriptions
        for key in old_key_set - new_key_set:
            self._stop_subscription(key)

        # Start new subscriptions
        new_entries: dict[tuple[str, ...], _SubEntry] = {}
        for key in new_key_set - old_key_set:
            spec = new_by_key[key]
            new_entries[key] = self._start_subscription(spec)

        # Keep existing, updating max_rate if needed
        kept: dict[tuple[str, ...], _SubEntry] = {}
        for key in new_key_set & old_key_set:
            old_entry = self._subscriptions[key]
            new_spec = new_by_key[key]
            if (
                old_entry.source == "renderer"
                and old_entry.max_rate != new_spec.max_rate
            ):
                self._conn.send_subscribe(
                    new_spec.wire_kind, new_spec.tag, max_rate=new_spec.max_rate
                )
                kept[key] = _SubEntry(
                    source=old_entry.source,
                    kind=old_entry.kind,
                    tag=old_entry.tag,
                    max_rate=new_spec.max_rate,
                    timer=old_entry.timer,
                    interval_ms=old_entry.interval_ms,
                )
            else:
                kept[key] = old_entry

        self._subscriptions = {**kept, **new_entries}
        self._subscription_keys = new_sorted_keys

    def _update_max_rates(
        self, new_by_key: dict[tuple[str, ...], Subscription]
    ) -> None:
        """Check and update max_rate on existing renderer subscriptions."""
        for key, new_spec in new_by_key.items():
            entry = self._subscriptions.get(key)
            if (
                entry is not None
                and entry.source == "renderer"
                and entry.max_rate != new_spec.max_rate
            ):
                self._conn.send_subscribe(
                    new_spec.wire_kind, new_spec.tag, max_rate=new_spec.max_rate
                )
                self._subscriptions[key] = _SubEntry(
                    source=entry.source,
                    kind=entry.kind,
                    tag=entry.tag,
                    max_rate=new_spec.max_rate,
                    timer=entry.timer,
                    interval_ms=entry.interval_ms,
                )

    def _start_subscription(self, spec: Subscription) -> _SubEntry:
        """Start a new subscription (timer or renderer)."""
        if spec.kind == "every":
            interval_ms = spec.interval_ms or 1000

            def tick() -> None:
                now_ms = int(time.monotonic() * 1000)
                self._queue.put(TimerTick(tag=spec.tag, timestamp=now_ms))
                # Re-arm if still subscribed
                if spec.key in self._subscriptions:
                    entry = self._subscriptions[spec.key]
                    if entry.timer is not None:
                        entry.timer.cancel()
                    new_timer = threading.Timer(interval_ms / 1000.0, tick)
                    new_timer.daemon = True
                    new_timer.start()
                    self._subscriptions[spec.key] = _SubEntry(
                        source="timer",
                        kind=spec.kind,
                        tag=spec.tag,
                        max_rate=None,
                        timer=new_timer,
                        interval_ms=interval_ms,
                    )

            timer = threading.Timer(interval_ms / 1000.0, tick)
            timer.daemon = True
            timer.start()
            return _SubEntry(
                source="timer",
                kind=spec.kind,
                tag=spec.tag,
                max_rate=None,
                timer=timer,
                interval_ms=interval_ms,
            )

        # Renderer subscription
        self._conn.send_subscribe(spec.wire_kind, spec.tag, max_rate=spec.max_rate)
        return _SubEntry(
            source="renderer",
            kind=spec.kind,
            tag=spec.tag,
            max_rate=spec.max_rate,
            timer=None,
            interval_ms=None,
        )

    def _stop_subscription(self, key: tuple[str, ...]) -> None:
        """Stop a subscription by key."""
        entry = self._subscriptions.pop(key, None)
        if entry is None:
            return
        if entry.source == "timer" and entry.timer is not None:
            entry.timer.cancel()
        elif entry.source == "renderer":
            self._conn.send_unsubscribe(entry.kind)

    # -------------------------------------------------------------------
    # Window sync
    # -------------------------------------------------------------------

    def _sync_windows(self, tree: Node | None) -> None:
        """Synchronize tracked windows with the current tree."""
        new_windows = detect_windows(tree)
        old_windows = self._windows

        # Open new windows
        for win_id in new_windows - old_windows:
            # Start with app-level window defaults, then overlay tree props
            try:
                defaults = self._app.window_config(self._model)
            except Exception:
                logger.exception("plushie runtime: window_config() raised")
                defaults = {}
            tree_props = extract_window_props(tree, win_id)
            props = {**defaults, **tree_props}
            msg = window_op("open", win_id, props or None, session=self._conn.session)
            self._conn.send(msg)

        # Close removed windows
        for win_id in old_windows - new_windows:
            msg = window_op("close", win_id, session=self._conn.session)
            self._conn.send(msg)

        # Update surviving windows if props changed
        for win_id in new_windows & old_windows:
            old_props = extract_window_props(self._tree, win_id)
            new_props = extract_window_props(tree, win_id)
            if old_props != new_props:
                msg = window_op(
                    "update", win_id, new_props or None, session=self._conn.session
                )
                self._conn.send(msg)

        self._windows = new_windows

    # -------------------------------------------------------------------
    # Coalescing
    # -------------------------------------------------------------------

    def _store_coalescable(self, key: Any, event: Any) -> None:
        """Store a coalescable event for deferred processing."""
        self._pending_coalesce[key] = event
        if self._coalesce_timer is None:

            def flush() -> None:
                self._coalesce_timer = None
                self._queue.put(("_flush_coalescables",))

            self._coalesce_timer = threading.Timer(0, flush)
            self._coalesce_timer.daemon = True
            self._coalesce_timer.start()

    def _flush_coalescables(self) -> None:
        """Process all pending coalescable events."""
        if not self._pending_coalesce:
            return
        if self._coalesce_timer is not None:
            self._coalesce_timer.cancel()
            self._coalesce_timer = None

        pending = dict(self._pending_coalesce)
        self._pending_coalesce.clear()

        for _key, event in pending.items():
            self._run_update(event)

    # -------------------------------------------------------------------
    # Renderer crash recovery
    # -------------------------------------------------------------------

    _MAX_RESTART_ATTEMPTS = 5
    _BASE_BACKOFF_MS = 100
    _MAX_BACKOFF_MS = 5000

    def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to the renderer after a crash.

        Uses exponential backoff: 100ms, 200ms, 400ms, 800ms, 1600ms.
        On successful reconnect, re-sends settings and a full snapshot,
        re-syncs subscriptions and windows, and flushes pending effects.

        Returns:
            ``True`` if reconnection succeeded, ``False`` if all
            attempts were exhausted.
        """
        if not hasattr(self._conn, "restart"):
            return False

        # Let the app handle the exit
        try:
            self._model = self._app.handle_renderer_exit(
                self._model, "renderer_crashed"
            )
        except Exception:
            logger.exception("app.handle_renderer_exit() raised")

        # Discard stale coalescable events from the old renderer.
        if self._coalesce_timer is not None:
            self._coalesce_timer.cancel()
            self._coalesce_timer = None
        self._pending_coalesce.clear()

        # Flush pending effects with error
        for effect_id, timer in list(self._pending_effects.items()):
            timer.cancel()
            self._queue.put(
                EffectResult(
                    request_id=effect_id,
                    status="error",
                    result=None,
                    error="renderer_restarted",
                )
            )
        self._pending_effects.clear()

        for attempt in range(self._MAX_RESTART_ATTEMPTS):
            delay_ms = min(
                self._BASE_BACKOFF_MS * (2**attempt),
                self._MAX_BACKOFF_MS,
            )
            logger.info(
                "plushie runtime: renderer exited, reconnecting "
                "(attempt %d/%d, backoff %dms)",
                attempt + 1,
                self._MAX_RESTART_ATTEMPTS,
                delay_ms,
            )
            time.sleep(delay_ms / 1000.0)

            try:
                self._conn.restart()
                self._conn.send_settings(self._app.settings())
                self._conn.wait_hello(timeout=10.0)
            except Exception:
                logger.warning(
                    "plushie runtime: reconnect attempt %d failed",
                    attempt + 1,
                    exc_info=True,
                )
                continue

            # Success -- re-send full snapshot and re-sync everything
            logger.info("plushie runtime: renderer reconnected")
            tree = self._safe_view(self._model)
            self._tree = tree
            if tree is not None:
                self._conn.send_snapshot(tree)

            # Re-sync subscriptions (force all to re-register)
            self._subscriptions.clear()
            self._subscription_keys = []
            self._sync_subscriptions(self._model)

            # Re-sync windows (force all to re-open)
            self._windows = set()
            self._sync_windows(tree)

            # Restart reader thread
            self._start_reader()
            return True

        logger.error(
            "plushie runtime: renderer restart failed after %d attempts",
            self._MAX_RESTART_ATTEMPTS,
        )
        return False

    # -------------------------------------------------------------------
    # Reader thread
    # -------------------------------------------------------------------

    def _start_reader(self) -> None:
        """Start the background reader thread."""
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="plushie-runtime-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        """Read events from the connection and post to the queue."""
        while self._running:
            event = self._conn.receive_event(timeout=0.5)
            if event is None:
                # Check if connection is still alive
                if not self._conn.is_alive:
                    self._queue.put(None)
                    break
                continue
            self._queue.put(event)

    # -------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------

    def _cleanup(self) -> None:
        """Clean up all resources."""
        self._running = False

        # Cancel all pending timers
        for timer in self._pending_timers.values():
            timer.cancel()
        self._pending_timers.clear()

        # Cancel coalesce timer
        if self._coalesce_timer is not None:
            self._coalesce_timer.cancel()
            self._coalesce_timer = None

        # Cancel all subscription timers
        for entry in self._subscriptions.values():
            if entry.timer is not None:
                entry.timer.cancel()
        self._subscriptions.clear()

        # Cancel all pending effects
        for timer in self._pending_effects.values():
            timer.cancel()
        self._pending_effects.clear()

        # Shutdown executor (don't wait for tasks)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._async_tasks.clear()


# ---------------------------------------------------------------------------
# Internal subscription entry
# ---------------------------------------------------------------------------


class _SubEntry:
    """Internal tracking for an active subscription."""

    __slots__ = ("interval_ms", "kind", "max_rate", "source", "tag", "timer")

    def __init__(
        self,
        source: str,
        kind: str,
        tag: str,
        max_rate: int | None,
        timer: threading.Timer | None,
        interval_ms: int | None,
    ) -> None:
        self.source = source
        self.kind = kind
        self.tag = tag
        self.max_rate = max_rate
        self.timer = timer
        self.interval_ms = interval_ms


# ---------------------------------------------------------------------------
# RuntimeHandle
# ---------------------------------------------------------------------------


class RuntimeHandle:
    """Handle for a runtime started on a background thread.

    Returned by ``plushie.start()``.  Provides ``stop()``, ``wait()``,
    and ``inject()`` for controlling the runtime from external code.
    """

    def __init__(self, runtime: Runtime, thread: threading.Thread) -> None:
        self._runtime = runtime
        self._thread = thread

    def stop(self) -> None:
        """Signal the runtime to stop."""
        self._runtime._running = False

    def wait(self, timeout: float | None = None) -> None:
        """Wait for the runtime thread to finish.

        Args:
            timeout: Maximum seconds to wait.  ``None`` for indefinite.
        """
        self._thread.join(timeout=timeout)

    def inject(self, event: Any) -> None:
        """Inject an event into the runtime (thread-safe).

        Equivalent to ``runtime.inject(event)``.
        """
        self._runtime.inject(event)

    @property
    def is_running(self) -> bool:
        """Whether the runtime is currently running."""
        return self._runtime.is_running

    @property
    def model(self) -> Any:
        """The current application model."""
        return self._runtime.model


__all__ = [
    "Runtime",
    "RuntimeHandle",
    "coalesce_key",
    "detect_windows",
    "extract_window_props",
    "unwrap_result",
]
