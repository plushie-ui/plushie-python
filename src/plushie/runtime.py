"""Elm-architecture event loop for plushie applications.

The ``Runtime`` class owns the full update cycle: init -> view ->
snapshot -> main loop (receive -> update -> commands -> view -> diff ->
patch -> sync subs -> sync windows).

This module is the Python equivalent of
``plushie-elixir/lib/plushie/runtime.ex`` and its submodules
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

import contextlib
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Empty, Queue
from typing import Any

from plushie.app import App, AppBuilder
from plushie.binary import PLUSHIE_RUST_VERSION
from plushie.commands import Command
from plushie.connection import Connection
from plushie.effects import DEFAULT_TIMEOUTS
from plushie.events import (
    AllWindowsClosed,
    AsyncResult,
    Blurred,
    EffectResult,
    EffectStubAck,
    Focused,
    Move,
    RecoveryFailed,
    StreamChunk,
    TimerTick,
    WidgetStatus,
    build_renderer_exit,
)
from plushie.events import Diagnostic as _Diagnostic
from plushie.events import DiagnosticMessage as _DiagnosticMessage
from plushie.protocol import (
    advance_frame_msg,
    command,
    commands,
    effect_msg,
    image_op,
    system_op,
    system_query,
    widget_op,
    window_op,
)
from plushie.subscriptions import Subscription
from plushie.tree import Node, diff, normalize_view
from plushie.types import HelloInfo
from plushie.widget import WidgetRegistry

logger = logging.getLogger("plushie")


DISPATCH_DEPTH_LIMIT: int = 100
"""Maximum synchronous ``Command.dispatch`` chain depth.

``Command.dispatch`` schedules a follow-up event back through the
runtime queue. A pathological ``update`` that keeps returning another
dispatch would fill the queue indefinitely; past this cap the runtime
drops the command and emits a typed
:class:`plushie.diagnostics.DispatchLoopExceeded` diagnostic so the
loop is visible.
"""

_EFFECT_TIMEOUT_MS: int = 30_000

_DEV_PREFIX = "__plushie_dev__"
_STOP_SENTINEL = object()


def _build_frozen_overlay_bar() -> dict[str, Any]:
    """Build the frozen UI overlay bar node tree."""
    return {
        "id": f"{_DEV_PREFIX}/anchor",
        "type": "container",
        "props": {"width": "fill", "align_y": "top"},
        "children": [
            {
                "id": f"{_DEV_PREFIX}/column",
                "type": "column",
                "props": {
                    "padding": {"top": 8, "right": 8, "bottom": 0, "left": 8},
                    "width": "shrink",
                    "max_width": 600,
                },
                "children": [
                    {
                        "id": f"{_DEV_PREFIX}/bar",
                        "type": "container",
                        "props": {
                            "background": "rgba(180, 40, 40, 0.85)",
                            "padding": 6,
                            "border": {"radius": 4},
                        },
                        "children": [
                            {
                                "id": f"{_DEV_PREFIX}/bar_row",
                                "type": "row",
                                "props": {"spacing": 8, "align_y": "center"},
                                "children": [
                                    {
                                        "id": f"{_DEV_PREFIX}/icon",
                                        "type": "text",
                                        "props": {
                                            "content": "[!!]",
                                            "color": "#ffaaaa",
                                            "size": 14,
                                        },
                                        "children": [],
                                    },
                                    {
                                        "id": f"{_DEV_PREFIX}/status",
                                        "type": "text",
                                        "props": {
                                            "content": "UI frozen: view() is failing repeatedly.",
                                            "color": "#ffaaaa",
                                            "size": 14,
                                        },
                                        "children": [],
                                    },
                                    {
                                        "id": f"{_DEV_PREFIX}/dismiss",
                                        "type": "button",
                                        "props": {"label": "x"},
                                        "children": [],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _inject_frozen_overlay(tree: Node) -> Node:
    """Inject the frozen UI overlay into the tree's window(s).

    Wraps each window's content in a stack with the overlay bar on top.
    """
    if tree["type"] == "window":
        return _inject_overlay_into_window(tree)

    children = tree.get("children", [])
    if not children:
        return tree

    new_children = [
        (_inject_overlay_into_window(child) if child.get("type") == "window" else child)
        for child in children
    ]

    return {**tree, "children": new_children}


def _inject_overlay_into_window(window_node: Node) -> Node:
    """Wrap a window's content in a stack with the frozen overlay bar."""
    children = window_node.get("children", [])
    if not children:
        return window_node

    content = children[0]
    overlay = _build_frozen_overlay_bar()

    stack_node: dict[str, Any] = {
        "id": f"{_DEV_PREFIX}/stack",
        "type": "stack",
        "props": {"width": "fill", "height": "fill"},
        "children": [content, overlay],
    }

    return {**window_node, "children": [stack_node]}


def _is_overlay_event(event: Any) -> bool:
    """Check if an event targets the dev overlay."""
    event_id = getattr(event, "id", None)
    if isinstance(event_id, str):
        return event_id.startswith(_DEV_PREFIX + "/")
    return False


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
        "scale_factor",
        "theme",
    }
)


def detect_windows(tree: Node | None) -> set[str]:
    """Detect window node IDs from the tree.

    Searches the entire tree recursively, matching the renderer's
    behavior.  Window nodes at any depth are detected and tracked.
    """
    if tree is None:
        return set()
    found: set[str] = set()
    _collect_windows(tree, found)
    return found


def _collect_windows(node: Node, found: set[str]) -> None:
    """Recursively collect window IDs from a tree node."""
    if node.get("type") == "window":
        node_id = node.get("id")
        if node_id:
            found.add(node_id)
    for child in node.get("children", []):
        if isinstance(child, dict):
            _collect_windows(child, found)


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
    """Find a window node anywhere in the tree by ID."""
    if tree.get("type") == "window" and tree.get("id") == window_id:
        return tree
    for child in tree.get("children", []):
        if isinstance(child, dict):
            found = _find_window_node(child, window_id)
            if found is not None:
                return found
    return None


# ---------------------------------------------------------------------------
# Coalescing helpers
# ---------------------------------------------------------------------------


def coalesce_key(event: Any) -> Any | None:
    """Return the coalescing key for an event, or None if not coalescable.

    High-frequency events (pointer moves, pointer scroll) are collapsed
    so only the latest value is processed per flush cycle.
    """
    if isinstance(event, Move):
        return ("move", event.window_id, event.id)
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
        heartbeat_interval_ms: int | None = 30000,
    ) -> None:
        if isinstance(app, AppBuilder):
            app = app.build()

        self._app: App[Any] = app
        self._conn: Connection = connection
        self._daemon: bool = daemon

        # Model state
        self._model: Any = None
        self._tree: Node | None = None

        # Event queue: all events (renderer + injected + internal) flow here.
        self._queue: Queue[Any] = Queue()

        # Running flag
        self._running: bool = False
        self._control_lock = threading.Lock()

        # Subscription state
        self._subscriptions: dict[tuple[str, ...], _SubEntry] = {}
        self._subscriptions_lock = threading.Lock()
        self._subscription_keys: list[tuple[str, ...]] = []

        # Window state
        self._windows: set[str] = set()

        # Async task tracking: tag -> (future, nonce)
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="plushie-task"
        )
        self._async_tasks: dict[str, tuple[Future[Any], int]] = {}
        self._nonce_counter: int = 0

        # Pending effect requests: wire_id -> {"tag": str, "timer": Timer}
        self._pending_effects: dict[str, dict[str, Any]] = {}

        # Pending send_after timers: event_key -> Timer
        self._pending_timers: dict[Any, threading.Timer] = {}

        # Pending coalesced events: key -> event
        self._pending_coalesce: dict[Any, Any] = {}
        self._coalesce_timer: threading.Timer | None = None

        # Consecutive error count for rate-limited logging
        self._consecutive_errors: int = 0

        # Effect stub ack tracking: kind -> waiter shared between the
        # caller thread and the runtime loop.
        self._pending_stub_acks: dict[str, _StubAckWaiter] = {}

        # Diagnostic accumulation
        self._diagnostics: list[Any] = []
        self._diagnostics_lock: threading.Lock = threading.Lock()

        # Chain-position counter for the `Command.dispatch` guard. Set
        # by the main loop before each `_run_update` so a chained
        # dispatch tracks its position and the guard in
        # `_execute_command` can cap the chain.
        self._current_dispatch_depth: int = 0

        # Pending await_async callers: tag -> Event
        self._pending_await_async: dict[str, threading.Event] = {}

        # Pending interact slot (see _InteractSlot below)
        self._pending_interact: _InteractSlot | None = None

        # Custom widget registry (canvas widgets + composites)
        self._widget_registry: WidgetRegistry = {}

        # Memo cache and widget view cache. Passed through to
        # normalize_view to skip re-evaluation of ``memo(...)``
        # subtrees and widget ``view()`` calls when their inputs
        # are unchanged. The "new" dicts are populated during each
        # render and then swap into "prev" for the next one.
        self._memo_cache_prev: dict[Any, Any] = {}
        self._widget_cache_prev: dict[Any, Any] = {}

        # Widget status tracking (focus, hover, etc.): widget_id -> status string
        self._widget_statuses: dict[str, str] = {}
        self._focused_widget_id: str | None = None

        # Heartbeat watchdog: detects unresponsive renderer
        self._heartbeat_interval_ms: int | None = heartbeat_interval_ms
        self._heartbeat_timer: threading.Timer | None = None
        self._exit_reason: Any = None

        # Consecutive view failure counter
        self._consecutive_view_errors: int = 0

        # Dev overlay state: None or "frozen_ui"
        self._dev_overlay: str | None = None

        # Reader thread
        self._reader_thread: threading.Thread | None = None

        # Subscription identity for timer rearm ownership.
        self._subscription_token_counter: int = 0

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
            with self._control_lock:
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

    def stop(self) -> None:
        """Request a clean runtime stop from any thread."""
        with self._control_lock:
            self._running = False
        self._queue.put(_STOP_SENTINEL)

    @property
    def model(self) -> Any:
        """The current application model."""
        return self._model

    @property
    def is_running(self) -> bool:
        """Whether the event loop is currently running."""
        with self._control_lock:
            return self._running

    def register_effect_stub(
        self, kind: str, response: Any, *, timeout: float = 5.0
    ) -> None:
        """Register an effect stub with the renderer.

        The renderer will return ``response`` immediately for any effect
        of the given ``kind``. Blocks until the renderer confirms.

        Raises:
            RuntimeError: If a register or unregister for the same kind
                is already awaiting confirmation.

        Args:
            kind: Effect kind (e.g. ``"file_open"``).
            response: Canned response the renderer returns.
            timeout: Maximum seconds to wait for ack.
        """
        from plushie.protocol import register_effect_stub

        if kind in self._pending_stub_acks:
            raise RuntimeError(
                f"register_effect_stub({kind!r}): another stub ack is already pending"
            )
        ack = _StubAckWaiter()
        self._pending_stub_acks[kind] = ack
        msg = register_effect_stub(kind, response, session=self._conn.session)
        self._conn.send(msg)
        if not ack.done.wait(timeout):
            self._pending_stub_acks.pop(kind, None)
            logger.warning("register_effect_stub(%r) timed out", kind)
        elif not ack.acknowledged:
            logger.warning(
                "register_effect_stub(%r) cancelled during renderer reconnect", kind
            )

    def unregister_effect_stub(self, kind: str, *, timeout: float = 5.0) -> None:
        """Remove a previously registered effect stub.

        Blocks until the renderer confirms removal.

        Raises:
            RuntimeError: If a register or unregister for the same kind
                is already awaiting confirmation.

        Args:
            kind: Effect kind to remove.
            timeout: Maximum seconds to wait for ack.
        """
        from plushie.protocol import unregister_effect_stub

        if kind in self._pending_stub_acks:
            raise RuntimeError(
                f"unregister_effect_stub({kind!r}): another stub ack is already pending"
            )
        ack = _StubAckWaiter()
        self._pending_stub_acks[kind] = ack
        msg = unregister_effect_stub(kind, session=self._conn.session)
        self._conn.send(msg)
        if not ack.done.wait(timeout):
            self._pending_stub_acks.pop(kind, None)
            logger.warning("unregister_effect_stub(%r) timed out", kind)
        elif not ack.acknowledged:
            logger.warning(
                "unregister_effect_stub(%r) cancelled during renderer reconnect", kind
            )

    def get_diagnostics(self) -> list[Any]:
        """Return and clear accumulated prop validation diagnostics.

        The renderer emits diagnostic events when ``validate_props`` is
        enabled. These are intercepted by the runtime (never delivered
        to ``update()``) and accumulated. This atomically retrieves and
        clears the list.
        """
        with self._diagnostics_lock:
            result = list(self._diagnostics)
            self._diagnostics.clear()
        return result

    def await_async(self, tag: str, *, timeout: float = 30.0) -> bool:
        """Block until an async task with the given tag completes.

        If the task is still running, blocks until it finishes (up to
        ``timeout``). If the task has already completed or was never
        started, returns immediately.

        Raises:
            RuntimeError: If another caller is already waiting for the
                same tag.

        Args:
            tag: The async task tag to wait for.
            timeout: Maximum seconds to wait.

        Returns:
            ``True`` if the task completed, ``False`` if timed out.
        """
        if tag not in self._async_tasks:
            return True

        if tag in self._pending_await_async:
            raise RuntimeError(
                f"await_async({tag!r}): another caller is already waiting"
            )
        done = threading.Event()
        self._pending_await_async[tag] = done
        return done.wait(timeout)

    def interact(
        self,
        action: str,
        selector: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        """Simulate a user interaction through the runtime.

        Sends an interact message to the renderer, then blocks until
        the interact_response arrives. interact_step messages are
        handled in the event loop using apply_event (update + commands,
        no render per-step) followed by a single snapshot.

        Can be called from any thread, but only one interact may be
        in progress at a time.

        Raises:
            RuntimeError: If another interact is already in progress,
                or if the renderer exits before the interaction
                completes.
            TimeoutError: If the renderer doesn't respond within
                *timeout* seconds.

        Args:
            action: Interaction type (e.g. ``"click"``, ``"type_text"``).
            selector: Target selector string.
            payload: Action parameters.
            timeout: Max seconds to wait for completion.
        """
        from plushie.protocol import encode_selector, interact_msg

        rid = f"interact_{self._next_nonce()}"
        sel: dict[str, str] | None = None
        if selector is not None:
            sel = encode_selector(selector)

        slot = _InteractSlot(request_id=rid)
        with self._control_lock:
            if self._pending_interact is not None:
                raise RuntimeError(
                    "interact already in progress, concurrent calls are not supported"
                )
            self._pending_interact = slot

        msg = interact_msg(rid, action, sel, payload, session=self._conn.session)
        self._conn.send(msg)

        if not slot.done.wait(timeout):
            with self._control_lock:
                if self._pending_interact is slot:
                    self._pending_interact = None
            raise TimeoutError(f"interact({action!r}) timed out after {timeout:.1f}s")

        if not slot.succeeded:
            raise RuntimeError(f"renderer exited during interact({action!r})")

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
        self._conn.wait_hello(timeout=10.0)

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
        while self.is_running:
            try:
                event = self._queue.get(timeout=0.1)
            except Empty:
                continue

            if event is _STOP_SENTINEL:
                logger.info("plushie runtime: stop requested, stopping")
                break

            if event is None:
                if not self.is_running:
                    logger.info("plushie runtime: connection closed after stop request")
                    break
                # Connection closed / reader thread finished / heartbeat timeout
                self._cancel_heartbeat()
                reason = self._exit_reason
                self._exit_reason = None
                if self._attempt_reconnect(reason):
                    continue
                self._fail_pending_interact()
                logger.info("plushie runtime: connection closed, stopping")
                with self._control_lock:
                    self._running = False
                break

            # HelloInfo from the renderer; log and continue
            if isinstance(event, HelloInfo):
                logger.info(
                    "plushie runtime: renderer connected, %s v%s (%s, %s)",
                    event.name,
                    event.version,
                    event.backend,
                    event.transport,
                )
                if event.version != PLUSHIE_RUST_VERSION:
                    logger.warning(
                        "plushie runtime: renderer version %s does not "
                        "match SDK expected version %s",
                        event.version,
                        PLUSHIE_RUST_VERSION,
                    )
                self._reset_heartbeat()
                continue

            # Diagnostic events: intercept, never deliver to update()
            if isinstance(event, _Diagnostic):
                logger.warning(
                    "plushie runtime: prop validation diagnostic: %s", event.message
                )
                with self._diagnostics_lock:
                    self._diagnostics.append(event)
                continue

            # Renderer diagnostic wire messages: intercept for programmatic
            # observation. Logging already happened in protocol.decode_message.
            if isinstance(event, _DiagnosticMessage):
                with self._diagnostics_lock:
                    self._diagnostics.append(event)
                continue

            # WidgetStatus events: intercept for focus tracking, derive
            # Focused/Blurred events from status transitions.
            if isinstance(event, WidgetStatus):
                self._handle_widget_status(event)
                continue

            # Effect stub ack; unblock the waiting caller
            if isinstance(event, EffectStubAck):
                ack = self._pending_stub_acks.pop(event.kind, None)
                if ack is not None:
                    ack.acknowledged = True
                    ack.done.set()
                continue

            # Interact step: batch events with apply_event, then snapshot
            if isinstance(event, dict) and event.get("type") == "interact_step":
                self._flush_coalescables()
                self._handle_interact_step(event.get("events", []))
                continue

            # Interact response: final events, full update cycle, unblock caller
            if isinstance(event, dict) and event.get("type") == "interact_response":
                self._flush_coalescables()
                self._handle_interact_response(event)
                continue

            # AllWindowsClosed in non-daemon mode -> dispatch then stop
            if isinstance(event, AllWindowsClosed) and not self._daemon:
                self._run_update(event)
                with self._control_lock:
                    self._running = False
                break

            # Coalescable event -> store and defer
            c_key = coalesce_key(event)
            if c_key is not None:
                self._store_coalescable(c_key, event)
                self._reset_heartbeat()
                continue

            # Internal runtime events (tuples from task/stream/coalesce/effect).
            # Dispatched tuples carry their chain position; everything
            # else is a fresh entry, so the depth resets to 0.
            if isinstance(event, tuple) and event and isinstance(event[0], str):
                if event[0] == "_dispatched" and len(event) == 3:
                    # A `Command.dispatch` follow-up. Set the counter
                    # to the stored chain position so the guard in
                    # `_execute_command` caps the chain.
                    self._flush_coalescables()
                    self._reset_heartbeat()
                    self._current_dispatch_depth = event[1]
                    try:
                        self._run_update(event[2])
                    finally:
                        self._current_dispatch_depth = 0
                    continue

                # Other internal tuples start a fresh chain.
                self._current_dispatch_depth = 0

                if event[0] == "_effect_response" and len(event) == 5:
                    self._flush_coalescables()
                    resolved = self._resolve_effect_response(
                        event[1], event[2], event[3], event[4]
                    )
                    if resolved is not None:
                        self._run_update(resolved)
                    continue
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

            # Normal event: fresh entry, reset depth.
            self._flush_coalescables()
            self._reset_heartbeat()
            self._current_dispatch_depth = 0
            self._run_update(event)

    # -------------------------------------------------------------------
    # Update cycle
    # -------------------------------------------------------------------

    def _run_update(self, event: Any) -> None:
        """Full update cycle: update -> commands -> view -> diff -> patch -> sync."""
        # Intercept dev overlay events before normal dispatch
        if _is_overlay_event(event):
            self._handle_overlay_event(event)
            return

        app = self._app
        model = self._model

        # Effect results are handled as _effect_response tuples in the
        # event loop, before reaching _run_update.

        # Route canvas widget timer events to the widget handler
        if isinstance(event, TimerTick) and self._widget_registry:
            from plushie.widget import maybe_handle_timer

            handled, routed_event, self._widget_registry = maybe_handle_timer(
                self._widget_registry, event.tag
            )
            if handled:
                if routed_event is not None:
                    event = routed_event
                else:
                    # Widget handled internally; re-render for state changes
                    self._rerender_after_widget_state_change(self._widget_registry)
                    return
            # If not handled, fall through to normal dispatch

        # Dispatch through widget handlers
        old_registry = self._widget_registry
        event, self._widget_registry, state_changed = self._route_through_widgets(event)
        if event is None:
            # Event consumed. If widget state changed, re-render.
            if state_changed:
                self._rerender_after_widget_state_change(old_registry)
            return

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
        prev_tree = self._tree
        self._tree = new_tree

        # Derive canvas widget registry from the new tree
        from plushie.widget import collect_subscriptions, derive_registry

        self._widget_registry = derive_registry(new_tree)
        widget_subs = collect_subscriptions(self._widget_registry)

        # Sync subscriptions (merge widget subs) and windows
        self._sync_subscriptions(new_model, extra_subs=widget_subs)
        self._sync_windows(new_tree, prev_tree=prev_tree)

    def _route_through_widgets(
        self, event: Any
    ) -> tuple[Any | None, WidgetRegistry, bool]:
        """Dispatch event through widget handler chain.

        Returns ``(event_or_none, registry, state_changed)``.
        """
        if not self._widget_registry:
            return event, self._widget_registry, False
        from plushie.widget import dispatch_through_widgets

        return dispatch_through_widgets(self._widget_registry, event)

    def _rerender_after_widget_state_change(self, old_registry: WidgetRegistry) -> None:
        """Re-render after a widget's handle_event updated state without emitting.

        On view error, reverts the widget registry to the pre-update state
        to prevent a desync between the handler registry and the rendered tree.
        """
        from plushie.widget import collect_subscriptions, derive_registry

        new_tree = self._safe_view(self._model)
        if new_tree is None:
            # View failed: revert widget state to avoid state-tree desync
            self._widget_registry = old_registry
            return

        old_tree = self._tree
        if old_tree is None:
            self._conn.send_snapshot(new_tree)
        else:
            from plushie.tree import diff

            ops = diff(old_tree, new_tree)
            if ops:
                self._conn.send_patch(ops)

        self._tree = new_tree
        self._widget_registry = derive_registry(new_tree)
        widget_subs = collect_subscriptions(self._widget_registry)
        self._sync_subscriptions(self._model, extra_subs=widget_subs)
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
                        "plushie runtime: update() returned None. "
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
                    "plushie runtime: 100+ consecutive update errors. "
                    "suppressing further logs"
                )
            elif count % 1000 == 0:
                logger.warning(
                    "plushie runtime: %d consecutive errors",
                    count,
                )
            return None

    _VIEW_ERROR_WARN_THRESHOLD = 5

    def _safe_view(self, model: Any) -> Node | None:
        """Call app.view() + normalize with error handling."""
        try:
            raw_tree = self._app.view(model)
            memo_new: dict[Any, Any] = {}
            widget_new: dict[Any, Any] = {}
            result = normalize_view(
                raw_tree,
                registry=self._widget_registry or None,
                memo_cache_prev=self._memo_cache_prev,
                memo_cache_new=memo_new,
                widget_cache_prev=self._widget_cache_prev,
                widget_cache_new=widget_new,
            )
            self._memo_cache_prev = memo_new
            self._widget_cache_prev = widget_new
            self._consecutive_view_errors = 0
            return result
        except Exception:
            logger.exception("plushie runtime: view() raised")
            self._consecutive_view_errors += 1
            if self._consecutive_view_errors == self._VIEW_ERROR_WARN_THRESHOLD:
                logger.warning(
                    "plushie runtime: view() has failed %d consecutive times, "
                    "the UI is stale",
                    self._consecutive_view_errors,
                )
            return None

    def _render_and_sync(self, model: Any) -> Node | None:
        """Render view, diff against old tree, send snapshot or patch."""
        new_tree = self._safe_view(model)
        if new_tree is not None:
            if self._dev_overlay is not None:
                self._dev_overlay = None
            old_tree = self._tree
            if old_tree is None:
                self._conn.send_snapshot(new_tree)
            else:
                ops = diff(old_tree, new_tree)
                if ops:
                    self._conn.send_patch(ops)
            return new_tree

        if (
            self._consecutive_view_errors >= self._VIEW_ERROR_WARN_THRESHOLD
            and self._dev_overlay is None
            and self._tree is not None
        ):
            self._dev_overlay = "frozen_ui"
            overlay_tree = _inject_frozen_overlay(self._tree)
            if overlay_tree is not self._tree:
                ops = diff(self._tree, overlay_tree)
                if ops:
                    self._conn.send_patch(ops)
                return overlay_tree

        return self._tree

    def _handle_overlay_event(self, event: Any) -> None:
        """Handle dev overlay events (dismiss)."""
        event_id = getattr(event, "id", "")
        if event_id == f"{_DEV_PREFIX}/dismiss" and self._dev_overlay is not None:
            self._dev_overlay = None
            new_tree = self._safe_view(self._model)
            if new_tree is not None:
                old_tree = self._tree
                self._tree = new_tree
                ops = diff(old_tree, new_tree)
                if ops:
                    self._conn.send_patch(ops)

    # -------------------------------------------------------------------
    # Interact protocol
    # -------------------------------------------------------------------

    def _apply_event(self, event: Any) -> None:
        """Update + commands only, no re-render.

        Used by interact_step where events are batched and a single
        snapshot follows after all events are processed.
        """
        event, self._widget_registry, _state_changed = self._route_through_widgets(
            event
        )
        if event is None:
            return

        result = self._safe_update(self._app, self._model, event)
        if result is None:
            self._consecutive_errors += 1
            return

        new_model, commands = result
        self._model = new_model
        self._consecutive_errors = 0
        self._execute_commands(commands)

    def _decode_interact_event(self, event_map: dict[str, Any]) -> Any:
        """Decode a wire-format event from an interact_step/interact_response."""
        from plushie.protocol import decode_message

        # Wrap bare event data as a proper event message for the decoder
        wrapped = {"type": "event", **event_map}
        decoded = decode_message(wrapped)
        if isinstance(decoded, dict):
            self._record_unknown_interact_event(decoded)
            return None
        return decoded

    def _record_unknown_interact_event(self, raw_msg: dict[str, Any]) -> None:
        from plushie.diagnostics import DiagnosticMessage, UnknownMessageType

        family = raw_msg.get("family")
        msg_type = raw_msg.get("type")
        if isinstance(family, str) and family:
            kind = f"event/{family}"
        elif isinstance(msg_type, str) and msg_type:
            kind = msg_type
        else:
            kind = "embedded_event"

        logger.error("plushie runtime: unknown embedded interact event: %r", raw_msg)
        with self._diagnostics_lock:
            self._diagnostics.append(
                DiagnosticMessage(
                    session=self._conn.session,
                    level="error",
                    diagnostic=UnknownMessageType(msg_type=kind),
                )
            )

    def _handle_interact_step(self, events: list[dict[str, Any]]) -> None:
        """Process an interact_step batch.

        Applies each event through update + commands without rendering,
        then sends a single full snapshot back to the renderer.
        """
        for event_map in events:
            decoded = self._decode_interact_event(event_map)
            if decoded is not None:
                self._apply_event(decoded)

        # Re-render and send a full snapshot (not a patch)
        new_tree = self._safe_view(self._model)
        if new_tree is None:
            new_tree = self._tree
        self._tree = new_tree
        if new_tree is not None:
            self._conn.send_snapshot(new_tree)

        self._sync_subscriptions(self._model)
        self._sync_windows(new_tree)

    def _handle_interact_response(self, msg: dict[str, Any]) -> None:
        """Process an interact_response.

        Final events get a full update cycle (update + render). Then
        unblock the caller.
        """
        events = msg.get("events", [])
        for event_map in events:
            decoded = self._decode_interact_event(event_map)
            if decoded is not None:
                self._run_update(decoded)

        # Unblock the waiting caller
        rid = msg.get("id", "")
        with self._control_lock:
            slot = self._pending_interact
            if slot is not None and slot.request_id == rid:
                self._pending_interact = None
                slot.succeeded = True
                slot.done.set()

    def _fail_pending_interact(self) -> None:
        """Unblock a waiting interact caller when the renderer is gone.

        Signals failure so the caller can raise instead of silently
        returning as if the interaction succeeded.
        """
        with self._control_lock:
            slot = self._pending_interact
            if slot is not None:
                self._pending_interact = None
                slot.succeeded = False
                slot.done.set()

    def _next_subscription_token(self) -> int:
        """Allocate a new identity token for a subscription entry."""
        with self._control_lock:
            self._subscription_token_counter += 1
            return self._subscription_token_counter

    # -------------------------------------------------------------------
    # Command execution
    # -------------------------------------------------------------------

    def _execute_commands(self, commands: list[Command]) -> None:
        """Execute a list of commands at the current dispatch depth."""
        for cmd in commands:
            self._execute_command(cmd)

    def _execute_command(self, cmd: Command) -> None:
        """Execute a single command.

        `Command.dispatch` follow-ups queue a ``("_dispatched", depth,
        event)`` tuple; the main loop reads the depth off the tuple
        and passes it through so
        :data:`plushie.diagnostics.DispatchLoopExceeded` fires when a
        pathological update loop keeps re-dispatching.
        """
        t = cmd.type
        p = cmd.payload

        if t == "none":
            return

        if t == "batch":
            self._execute_commands(p.get("commands", []))
            return

        if t == "exit":
            logger.info("plushie runtime: exit command received, stopping")
            with self._control_lock:
                self._running = False
            return

        if t == "dispatch":
            mapper = p["mapper"]
            value = p["value"]
            event = mapper(value)
            next_depth = self._current_dispatch_depth + 1
            if next_depth > DISPATCH_DEPTH_LIMIT:
                # Drop the dispatched command and emit the typed
                # diagnostic so a pathological update loop is visible
                # instead of unboundedly filling the event queue.
                from plushie.diagnostics import DiagnosticMessage, DispatchLoopExceeded

                diag = DiagnosticMessage(
                    session=self._conn.session,
                    level="error",
                    diagnostic=DispatchLoopExceeded(
                        depth=next_depth, limit=DISPATCH_DEPTH_LIMIT
                    ),
                )
                logger.error(
                    "plushie runtime: dispatch_loop_exceeded: "
                    "command chain reached depth %d (limit %d); "
                    "dropping command to break the loop",
                    next_depth,
                    DISPATCH_DEPTH_LIMIT,
                )
                with self._diagnostics_lock:
                    self._diagnostics.append(diag)
                return
            self._queue.put(("_dispatched", next_depth, event))
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
            self._send_effect(p["id"], p["tag"], p["kind"], p.get("opts", {}))
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

        if t == "system_op":
            op_name = p.get("op", "")
            op_settings = {k: v for k, v in p.items() if k != "op"}
            self._conn.send(
                system_op(op_name, op_settings or None, session=self._conn.session)
            )
            return

        if t == "system_query":
            op_name = p.get("op", "")
            op_settings = {k: v for k, v in p.items() if k != "op"}
            self._conn.send(
                system_query(op_name, op_settings or None, session=self._conn.session)
            )
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

        if t == "command":
            msg = command(
                p["id"],
                p["family"],
                p.get("value"),
                session=self._conn.session,
            )
            self._conn.send(msg)
            return

        if t == "commands":
            raw_cmds = p.get("commands", [])
            cmds = [(c["id"], c["family"], c.get("value")) for c in raw_cmds]
            msg = commands(cmds, session=self._conn.session)
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
        with self._control_lock:
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

        # Notify any await_async callers
        waiter = self._pending_await_async.pop(tag, None)
        if waiter is not None:
            waiter.set()

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
        # Use the event value itself as the dedup key so that two
        # send_after calls with equal events cancel the first timer
        # (matching Elixir's value-keyed Map).  Fall back to id() for
        # unhashable events (dicts, lists) where dedup isn't possible.
        try:
            hash(event)
            event_key = event
        except TypeError:
            event_key = id(event)

        # Cancel existing timer for same event to prevent duplicates
        old = self._pending_timers.pop(event_key, None)
        if old is not None:
            old.cancel()

        def fire() -> None:
            self._queue.put(event)

        timer = threading.Timer(delay_ms / 1000.0, fire)
        timer.daemon = True
        timer.start()
        self._pending_timers[event_key] = timer

    # -------------------------------------------------------------------
    # Effect tracking
    # -------------------------------------------------------------------

    def _send_effect(
        self, wire_id: str, tag: str, kind: str, opts: dict[str, Any]
    ) -> None:
        """Send an effect request to the renderer with timeout tracking."""
        # One-per-tag enforcement: cancel existing effect with same tag
        self._cancel_pending_effect_by_tag(tag)

        msg = effect_msg(wire_id, kind, opts, session=self._conn.session)
        self._conn.send(msg)

        timeout_ms = DEFAULT_TIMEOUTS.get(kind, _EFFECT_TIMEOUT_MS)

        def timeout_fire() -> None:
            from plushie.events import EffectTimeout

            entry = self._pending_effects.pop(wire_id, None)
            if entry is not None:
                self._queue.put(EffectResult(tag=entry["tag"], result=EffectTimeout()))

        timer = threading.Timer(timeout_ms / 1000.0, timeout_fire)
        timer.daemon = True
        timer.start()
        # Track kind alongside tag so the response decoder can produce
        # the right per-kind dataclass when the renderer replies.
        self._pending_effects[wire_id] = {"tag": tag, "kind": kind, "timer": timer}

    def _resolve_effect_response(
        self, wire_id: str, status: str, result: Any, error: str | None
    ) -> EffectResult | None:
        """Map a wire effect response to an EffectResult with the user's tag."""
        from plushie.events import decode_effect_result

        entry = self._pending_effects.pop(wire_id, None)
        if entry is None:
            return None
        entry["timer"].cancel()
        typed_result = decode_effect_result(entry["kind"], status, result, error)
        return EffectResult(tag=entry["tag"], result=typed_result)

    def _cancel_pending_effect_by_tag(self, tag: str) -> None:
        """Cancel a pending effect by tag (one-per-tag enforcement)."""
        for wire_id, entry in list(self._pending_effects.items()):
            if entry["tag"] == tag:
                entry["timer"].cancel()
                del self._pending_effects[wire_id]
                return

    def _take_pending_effect_results(self, reason: str) -> list[EffectResult]:
        """Drain pending effects into EffectResult events.

        Takes a snapshot before processing so new effects added later
        are not silently discarded.
        """
        from plushie.events import EffectError, RendererRestarted

        snapshot = dict(self._pending_effects)
        self._pending_effects.clear()
        flush_result: Any = (
            RendererRestarted()
            if reason == "renderer_restarted"
            else EffectError(message=reason)
        )
        events: list[EffectResult] = []
        for _wire_id, entry in snapshot.items():
            entry["timer"].cancel()
            events.append(EffectResult(tag=entry["tag"], result=flush_result))
        return events

    def _flush_pending_stub_acks(self) -> None:
        """Release stub-ack waiters tied to the dead renderer."""
        snapshot = dict(self._pending_stub_acks)
        self._pending_stub_acks.clear()
        for waiter in snapshot.values():
            waiter.done.set()

    # -------------------------------------------------------------------
    # Widget status tracking
    # -------------------------------------------------------------------

    def _handle_widget_status(self, event: WidgetStatus) -> None:
        """Track widget interaction state and derive focus events."""
        wid = event.id
        status = event.value
        prev_status = self._widget_statuses.get(wid)
        self._widget_statuses[wid] = status

        # Track focused_widget_id
        if status == "focused":
            self._focused_widget_id = wid
        elif prev_status == "focused" and self._focused_widget_id == wid:
            self._focused_widget_id = None

        # Derive focused/blurred events from status transitions
        if prev_status != "focused" and status == "focused":
            self._run_update(
                Focused(
                    id=wid,
                    window_id=event.window_id,
                    scope=event.scope,
                )
            )
        elif prev_status == "focused" and status != "focused":
            self._run_update(
                Blurred(
                    id=wid,
                    window_id=event.window_id,
                    scope=event.scope,
                )
            )

    # -------------------------------------------------------------------
    # Heartbeat watchdog
    # -------------------------------------------------------------------

    def _reset_heartbeat(self) -> None:
        """Reset the heartbeat timer after receiving a message."""
        if self._heartbeat_interval_ms is None:
            return
        if self._heartbeat_timer is not None:
            self._heartbeat_timer.cancel()
        self._heartbeat_timer = threading.Timer(
            self._heartbeat_interval_ms / 1000.0, self._on_heartbeat_timeout
        )
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _cancel_heartbeat(self) -> None:
        """Cancel the heartbeat timer."""
        if self._heartbeat_timer is not None:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None

    def _on_heartbeat_timeout(self) -> None:
        """Handle heartbeat timeout: inject a reconnect trigger."""
        logger.warning(
            "plushie runtime: renderer unresponsive "
            "(no message in %dms), triggering restart",
            self._heartbeat_interval_ms,
        )
        self._exit_reason = "heartbeat_timeout"
        self._queue.put(None)

    # -------------------------------------------------------------------
    # Subscription diffing
    # -------------------------------------------------------------------

    def _sync_subscriptions(
        self,
        model: Any,
        *,
        extra_subs: list[Subscription] | None = None,
    ) -> None:
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

        if extra_subs:
            new_specs = [*new_specs, *extra_subs]

        # Filter out non-Subscription items and warn
        filtered: list[Subscription] = []
        for spec in new_specs:
            if isinstance(spec, Subscription):
                filtered.append(spec)
            else:
                logger.warning(
                    "plushie runtime: subscribe() returned non-Subscription item: %r",
                    spec,
                )
        new_specs = filtered

        new_by_key: dict[tuple[str, ...], Subscription] = {
            spec.key: spec for spec in new_specs
        }
        new_sorted_keys = sorted(new_by_key.keys())
        removed_entries: list[_SubEntry] = []
        subscribe_specs: list[Subscription] = []
        timers_to_start: list[threading.Timer] = []

        with self._subscriptions_lock:
            old_key_set = set(self._subscriptions.keys())
            new_key_set = set(new_by_key.keys())

            for key in old_key_set - new_key_set:
                entry = self._subscriptions.pop(key, None)
                if entry is not None:
                    removed_entries.append(entry)

            for key in new_key_set - old_key_set:
                spec = new_by_key[key]
                entry = self._start_subscription(spec)
                self._subscriptions[key] = entry
                if entry.source == "timer":
                    if entry.timer is not None:
                        timers_to_start.append(entry.timer)
                else:
                    subscribe_specs.append(spec)

            for key in new_key_set & old_key_set:
                entry = self._subscriptions[key]
                spec = new_by_key[key]
                if entry.source == "renderer" and entry.max_rate != spec.max_rate:
                    self._subscriptions[key] = _SubEntry(
                        source=entry.source,
                        kind=entry.kind,
                        tag=entry.tag,
                        max_rate=spec.max_rate,
                        timer=entry.timer,
                        interval_ms=entry.interval_ms,
                        token=entry.token,
                    )
                    subscribe_specs.append(spec)

            self._subscription_keys = new_sorted_keys

        for entry in removed_entries:
            if entry.source == "timer" and entry.timer is not None:
                entry.timer.cancel()
            elif entry.source == "renderer":
                self._conn.send_unsubscribe(entry.kind, tag=entry.tag)

        for spec in subscribe_specs:
            self._conn.send_subscribe(
                spec.wire_kind,
                spec.wire_tag,
                max_rate=spec.max_rate,
                window_id=spec.window_id,
            )

        for timer in timers_to_start:
            timer.start()

    def _start_subscription(self, spec: Subscription) -> _SubEntry:
        """Start a new subscription (timer or renderer)."""
        token = self._next_subscription_token()
        if spec.kind == "every":
            interval_ms = spec.interval_ms or 1000
            tag = spec.tag if spec.tag is not None else ""
            return self._make_timer_entry(
                key=spec.key,
                kind=spec.kind,
                tag=tag,
                interval_ms=interval_ms,
                token=token,
            )

        return _SubEntry(
            source="renderer",
            kind=spec.kind,
            tag=spec.wire_tag,
            max_rate=spec.max_rate,
            timer=None,
            interval_ms=None,
            token=token,
        )

    def _make_timer_entry(
        self,
        *,
        key: tuple[str, ...],
        kind: str,
        tag: str,
        interval_ms: int,
        token: int,
    ) -> _SubEntry:
        """Build a timer subscription entry owned by a stable token."""

        def tick() -> None:
            with self._subscriptions_lock:
                entry = self._subscriptions.get(key)
                if entry is None or entry.token != token:
                    return
                now_ms = int(time.monotonic() * 1000)
                self._queue.put(TimerTick(tag=tag, timestamp=now_ms))
                new_timer = threading.Timer(interval_ms / 1000.0, tick)
                new_timer.daemon = True
                entry.timer = new_timer
            new_timer.start()

        timer = threading.Timer(interval_ms / 1000.0, tick)
        timer.daemon = True
        return _SubEntry(
            source="timer",
            kind=kind,
            tag=tag,
            max_rate=None,
            timer=timer,
            interval_ms=interval_ms,
            token=token,
        )

    def _stop_subscription(self, key: tuple[str, ...]) -> None:
        """Stop a subscription by key."""
        with self._subscriptions_lock:
            entry = self._subscriptions.pop(key, None)
        if entry is None:
            return
        if entry.source == "timer" and entry.timer is not None:
            entry.timer.cancel()
        elif entry.source == "renderer":
            self._conn.send_unsubscribe(entry.kind, tag=entry.tag)

    # -------------------------------------------------------------------
    # Window sync
    # -------------------------------------------------------------------

    def _sync_windows(
        self,
        tree: Node | None,
        *,
        prev_tree: Node | None = None,
    ) -> None:
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
        compare_tree = prev_tree if prev_tree is not None else self._tree
        for win_id in new_windows & old_windows:
            old_props = extract_window_props(compare_tree, win_id)
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

    def _attempt_reconnect(self, reason: Any = None) -> bool:
        """Attempt to reconnect to the renderer after a crash.

        Uses exponential backoff: 100ms, 200ms, 400ms, 800ms, 1600ms.
        On successful reconnect, re-sends settings and a full snapshot,
        re-syncs subscriptions and windows, and flushes pending effects.

        Args:
            reason: Raw exit reason (``None``, ``"heartbeat_timeout"``,
                ``{"exit_status": N}``, etc.). Used to build a typed
                ``RendererExitInfo`` for ``handle_renderer_exit()``.

        Returns:
            ``True`` if reconnection succeeded, ``False`` if all
            attempts were exhausted.
        """
        self._cancel_heartbeat()
        if not hasattr(self._conn, "restart"):
            return False

        exit_info = build_renderer_exit(reason)
        candidate_model = self._model

        recovery_event: RecoveryFailed | None = None
        try:
            candidate_model = self._app.handle_renderer_exit(self._model, exit_info)
        except Exception as exc:
            logger.exception("app.handle_renderer_exit() raised")
            recovery_event = RecoveryFailed(
                kind=type(exc).__name__,
                error=str(exc),
                renderer_exit=exit_info,
            )

        deferred_effects = self._take_pending_effect_results("renderer_restarted")

        # Discard stale coalescable events from the old renderer.
        if self._coalesce_timer is not None:
            self._coalesce_timer.cancel()
            self._coalesce_timer = None
        self._pending_coalesce.clear()

        # Release blocked effect-stub callers before we try to talk to
        # the replacement renderer. Their acks died with the old one.
        self._flush_pending_stub_acks()

        # Fail any in-flight interact so the caller doesn't hang until
        # timeout waiting for a response from a dead renderer.
        self._fail_pending_interact()

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

            old_model = self._model
            old_tree = self._tree
            old_subscriptions = dict(self._subscriptions)
            old_subscription_keys = list(self._subscription_keys)
            old_windows = set(self._windows)
            old_widget_registry = dict(self._widget_registry)
            old_memo_cache_prev = dict(self._memo_cache_prev)
            old_widget_cache_prev = dict(self._widget_cache_prev)
            old_widget_statuses = dict(self._widget_statuses)
            old_focused_widget_id = self._focused_widget_id
            old_consecutive_errors = self._consecutive_errors
            old_consecutive_view_errors = self._consecutive_view_errors
            old_dev_overlay = self._dev_overlay

            try:
                logger.info("plushie runtime: renderer reconnected")
                tree = self._safe_view(candidate_model)
                if tree is None:
                    # view() failed; keep the previous tree so window
                    # sync still has something to work with (matches Elixir
                    # which falls back to state.tree on safe_view error).
                    tree = old_tree

                self._model = candidate_model
                self._tree = tree
                if tree is not None:
                    self._conn.send_snapshot(tree)

                from plushie.widget import collect_subscriptions, derive_registry

                self._widget_registry = (
                    derive_registry(tree) if tree is not None else {}
                )
                widget_subs = collect_subscriptions(self._widget_registry)

                # Re-sync subscriptions (force renderer subscriptions to re-register).
                self._subscriptions.clear()
                self._subscription_keys = []
                self._sync_subscriptions(self._model, extra_subs=widget_subs)

                # Re-sync windows (force all to re-open)
                self._windows = set()
                self._sync_windows(tree)

                # Old renderer focus/hover state is stale once replay succeeds.
                self._widget_statuses.clear()
                self._focused_widget_id = None

                # Reset error counters (stale renderer may have accumulated them)
                self._consecutive_errors = 0
                self._consecutive_view_errors = 0
                self._dev_overlay = None

                # Retire timer handles from the old subscription table now
                # that the new state is fully installed.
                for entry in old_subscriptions.values():
                    if entry.source == "timer" and entry.timer is not None:
                        entry.timer.cancel()

            except Exception:
                for entry in self._subscriptions.values():
                    if entry.source == "timer" and entry.timer is not None:
                        entry.timer.cancel()
                self._model = old_model
                self._tree = old_tree
                restored_subscriptions: dict[tuple[str, ...], _SubEntry] = {}
                for key, entry in old_subscriptions.items():
                    if entry.source == "timer" and entry.interval_ms is not None:
                        if entry.timer is not None:
                            entry.timer.cancel()
                        restored = self._make_timer_entry(
                            key=key,
                            kind=entry.kind,
                            tag=entry.tag,
                            interval_ms=entry.interval_ms,
                            token=entry.token,
                        )
                        if restored.timer is not None:
                            restored.timer.start()
                        restored_subscriptions[key] = restored
                    else:
                        restored_subscriptions[key] = entry
                self._subscriptions = restored_subscriptions
                self._subscription_keys = old_subscription_keys
                self._windows = old_windows
                self._widget_registry = old_widget_registry
                self._memo_cache_prev = old_memo_cache_prev
                self._widget_cache_prev = old_widget_cache_prev
                self._widget_statuses = old_widget_statuses
                self._focused_widget_id = old_focused_widget_id
                self._consecutive_errors = old_consecutive_errors
                self._consecutive_view_errors = old_consecutive_view_errors
                self._dev_overlay = old_dev_overlay
                logger.warning(
                    "plushie runtime: reconnect replay attempt %d failed",
                    attempt + 1,
                    exc_info=True,
                )
                continue

            if recovery_event is not None:
                self._run_update(recovery_event)
            for event in deferred_effects:
                self._run_update(event)

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
        old = self._reader_thread
        if old is not None and old.is_alive():
            old.join(timeout=2.0)
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="plushie-runtime-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        """Read events from the connection and post to the queue."""
        while self.is_running:
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
        with self._control_lock:
            self._running = False
        self._cancel_heartbeat()

        # Close the connection to unblock the reader thread, then join it.
        if hasattr(self._conn, "close") and callable(self._conn.close):
            with contextlib.suppress(Exception):
                self._conn.close()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None

        # Cancel all pending timers
        for timer in list(self._pending_timers.values()):
            timer.cancel()
        self._pending_timers.clear()

        # Cancel coalesce timer
        if self._coalesce_timer is not None:
            self._coalesce_timer.cancel()
            self._coalesce_timer = None

        # Cancel all subscription timers
        for entry in list(self._subscriptions.values()):
            if entry.timer is not None:
                entry.timer.cancel()
        self._subscriptions.clear()

        # Cancel all pending effects
        for entry in list(self._pending_effects.values()):
            entry["timer"].cancel()
        self._pending_effects.clear()

        # Shutdown executor (don't wait for tasks)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._async_tasks.clear()


# ---------------------------------------------------------------------------
# Internal interact tracking
# ---------------------------------------------------------------------------


class _InteractSlot:
    """Mutable state for a pending interact call.

    Created by ``interact()`` on the caller thread, mutated by the
    event loop thread when the response arrives or the renderer dies.
    The ``done`` event is set to unblock the caller; ``succeeded``
    tells the caller whether the interaction completed normally.
    """

    __slots__ = ("done", "request_id", "succeeded")

    def __init__(self, request_id: str) -> None:
        self.done: threading.Event = threading.Event()
        self.request_id: str = request_id
        self.succeeded: bool = True


class _StubAckWaiter:
    """Shared state for a pending effect-stub ack."""

    __slots__ = ("acknowledged", "done")

    def __init__(self) -> None:
        self.done: threading.Event = threading.Event()
        self.acknowledged: bool = False


# ---------------------------------------------------------------------------
# Internal subscription entry
# ---------------------------------------------------------------------------


class _SubEntry:
    """Internal tracking for an active subscription."""

    __slots__ = ("interval_ms", "kind", "max_rate", "source", "tag", "timer", "token")

    def __init__(
        self,
        source: str,
        kind: str,
        tag: str,
        max_rate: int | None,
        timer: threading.Timer | None,
        interval_ms: int | None,
        token: int,
    ) -> None:
        self.source = source
        self.kind = kind
        self.tag = tag
        self.max_rate = max_rate
        self.timer = timer
        self.interval_ms = interval_ms
        self.token = token


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
        self._runtime.stop()

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
