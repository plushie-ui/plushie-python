"""Connection to the plushie renderer subprocess.

Manages subprocess lifecycle, hello handshake, reader thread, message
routing, and request-response correlation.

Two connection modes:

- **Connection** (default): spawns the renderer binary as a subprocess
  with stdin/stdout pipes. Used by the runtime and testing framework.

- **StdioConnection**: reads/writes the process's own fd 0 and fd 1.
  Used when the renderer spawns the Python process (``plushie --exec``).

Both modes support context manager protocol (``with`` blocks) for
automatic cleanup.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import secrets
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping
from queue import Empty, Queue
from typing import Any

from plushie.binary import PlushieNotFoundError, resolve
from plushie.framing import JsonFraming, MsgpackFraming
from plushie.native_widget import NativeWidget
from plushie.protocol import (
    PROTOCOL_VERSION,
    advance_frame_msg,
    decode_message,
    effect_msg,
    encode_selector,
    interact_msg,
    patch,
    query_msg,
    reset_msg,
    screenshot_msg,
    settings,
    snapshot,
    subscribe_msg,
    tree_hash_msg,
    unsubscribe_msg,
    widget_op,
    window_op,
)
from plushie.types import HelloInfo

logger = logging.getLogger("plushie")


def _framing_for(format: str) -> MsgpackFraming | JsonFraming:
    """Return a framing instance for the given wire format.

    Matches the ``format`` option the other plushie SDKs take
    (Elixir's ``:format``, Gleam's ``format:``, Ruby's ``format:``).
    Defaults are resolved at the call site, not here.
    """
    if format == "msgpack":
        return MsgpackFraming()
    if format == "json":
        return JsonFraming()
    raise ValueError(f"unknown wire format: {format!r} (expected 'msgpack' or 'json')")


class ConnectionError(Exception):
    """Raised when a connection operation fails."""


class ProtocolMismatchError(ConnectionError):
    """Raised when the renderer reports an incompatible protocol version."""


class ProtocolVersionMismatchError(ProtocolMismatchError):
    """Raised when the renderer's advertised protocol version does not match the SDK's.

    Attributes:
        expected: Protocol version this SDK was built for.
        got: Protocol version the renderer advertised.
    """

    __slots__ = ("expected", "got")

    def __init__(self, *, expected: int, got: int) -> None:
        super().__init__(f"protocol version mismatch: expected {expected}, got {got!r}")
        self.expected = expected
        self.got = got


# ---------------------------------------------------------------------------
# Request ID generator
# ---------------------------------------------------------------------------


def _next_request_id() -> str:
    """Generate a unique request ID for request-response correlation."""
    return f"py-r{secrets.token_hex(16)}"


def _normalize_expected_widgets(
    expected: list[str | NativeWidget] | tuple[str | NativeWidget, ...] | None,
) -> tuple[str, ...]:
    if not expected:
        return ()
    return tuple(
        ext.kind if isinstance(ext, NativeWidget) else str(ext) for ext in expected
    )


def _validate_required_widgets(hello: HelloInfo, expected: tuple[str, ...]) -> None:
    if not expected:
        return
    capabilities = (
        set(hello.native_widgets) | set(hello.widgets) | set(hello.extensions)
    )
    missing = sorted(set(expected) - capabilities)
    if missing:
        raise ConnectionError(
            f"renderer is missing required widgets/capabilities {missing!r}. "
            f"Renderer reported {sorted(capabilities)!r}"
        )


_validate_required_extensions = _validate_required_widgets


def _validate_hello_protocol(hello: HelloInfo) -> None:
    if hello.protocol != PROTOCOL_VERSION:
        raise ProtocolVersionMismatchError(
            expected=PROTOCOL_VERSION,
            got=hello.protocol,
        )


def _parse_hello_for_handshake(raw_msg: dict[str, Any]) -> HelloInfo:
    try:
        decoded = decode_message(raw_msg)
    except ValueError as exc:
        raise ProtocolMismatchError(str(exc)) from exc
    if not isinstance(decoded, HelloInfo):
        raise ProtocolMismatchError("renderer sent invalid hello message")
    return decoded


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class Connection:
    """Manages a renderer subprocess and wire protocol communication.

    The connection handles:

    - Subprocess spawning with appropriate CLI flags
    - Hello handshake and protocol version verification
    - A reader thread that decodes incoming messages and routes them
    - Event queue for asynchronous event delivery
    - Request-response correlation with per-request queues
    - Thread-safe send via a lock

    Usage::

        conn = Connection.open(mode="mock")
        conn.send_settings({})
        hello = conn.hello
        conn.send_snapshot(tree)
        events = conn.interact("click", "#button")
        conn.close()

    Or as a context manager::

        with Connection.open(mode="mock") as conn:
            conn.send_settings({})
            ...
    """

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        *,
        session: str = "",
        format: str = "msgpack",
        expected_widgets: list[str | NativeWidget]
        | tuple[str | NativeWidget, ...]
        | None = None,
        _spawn_args: list[str] | None = None,
        _spawn_env: dict[str, str] | None = None,
    ) -> None:
        self._process = process
        self._session = session
        self._format = format
        self._spawn_args = _spawn_args
        self._spawn_env = _spawn_env
        self._framing = _framing_for(format)
        self._send_lock = threading.Lock()
        self._event_queue: Queue[Any] = Queue()
        self._pending: dict[str, Queue[dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        self._hello: HelloInfo | None = None
        self._hello_error: ProtocolMismatchError | None = None
        self._expected_widgets = _normalize_expected_widgets(expected_widgets)
        self._hello_event = threading.Event()
        self._closed = False
        self._reader_generation = 0
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(self._reader_generation,),
            name="plushie-reader",
            daemon=True,
        )
        self._reader_thread.start()

    @classmethod
    def open(
        cls,
        *,
        binary_path: str | None = None,
        mode: str | None = None,
        format: str = "msgpack",
        max_sessions: int | None = None,
        session: str = "",
        expected_widgets: list[str | NativeWidget]
        | tuple[str | NativeWidget, ...]
        | None = None,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> Connection:
        """Start a renderer subprocess and return a Connection.

        Args:
            binary_path: Path to the plushie binary. Resolved
                automatically if ``None``.
            mode: Renderer mode: ``"mock"``, ``"headless"``, or
                ``None`` for windowed (default).
            format: Wire format: ``"msgpack"`` (default) or ``"json"``.
                Matches the ``format`` option other plushie SDKs take.
            max_sessions: Maximum concurrent sessions for multiplexed
                mode. Omit for single-session.
            session: Default session identifier for messages.
            extra_args: Additional CLI arguments passed to the renderer.
            env: Extra environment variables for the subprocess.

        Returns:
            Connected ``Connection`` instance.

        Raises:
            PlushieNotFoundError: If the binary cannot be found.
            ConnectionError: If the subprocess fails to start.
        """
        path = binary_path or resolve()

        args: list[str] = [path]
        if mode == "mock":
            args.append("--mock")
        elif mode == "headless":
            args.append("--headless")
        if format == "json":
            args.append("--json")
        elif format != "msgpack":
            raise ValueError(
                f"unknown wire format: {format!r} (expected 'msgpack' or 'json')"
            )
        if max_sessions is not None:
            args.extend(["--max-sessions", str(max_sessions)])
        if extra_args:
            args.extend(extra_args)

        proc_env = _build_env(env)

        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=proc_env,
                bufsize=0,  # unbuffered I/O for real-time message delivery
            )
        except FileNotFoundError as exc:
            raise PlushieNotFoundError(
                f"failed to start renderer: {path!r} not found"
            ) from exc
        except OSError as exc:
            raise ConnectionError(f"failed to start renderer: {exc}") from exc

        return cls(
            process,
            session=session,
            format=format,
            expected_widgets=expected_widgets,
            _spawn_args=args,
            _spawn_env=proc_env,
        )

    @classmethod
    def from_iostream(
        cls,
        adapter: Any,
        *,
        session: str = "",
        expected_widgets: list[str | NativeWidget]
        | tuple[str | NativeWidget, ...]
        | None = None,
        token: str | None = None,
        token_sha256: str | None = None,
    ) -> _IoStreamConnection:
        """Create a Connection-like object backed by an iostream adapter.

        The adapter (e.g. ``IoStreamAdapter``) handles the underlying
        transport. The returned object exposes the same public API as
        ``Connection`` for sending messages and receiving events.

        Args:
            adapter: An ``IoStreamAdapter`` instance (or any object with
                ``send()``, ``receive_event()``, ``close()``, ``hello``,
                and ``wait_hello()`` methods).
            session: Default session identifier for outbound messages.
            token: Optional shared secret for renderer authentication.
                The connection sends only the SHA-256 digest in Settings.
            token_sha256: Optional precomputed token digest for callers
                that do not keep the plaintext token.

        Returns:
            A connection-like object wrapping the adapter.
        """
        if token is not None and token_sha256 is not None:
            raise ValueError("pass either token or token_sha256, not both")

        return _IoStreamConnection(
            adapter,
            session=session,
            expected_widgets=expected_widgets,
            token=token,
            token_sha256=token_sha256,
        )

    @property
    def hello(self) -> HelloInfo | None:
        """The hello info received from the renderer, or ``None`` if not yet received."""
        return self._hello

    @property
    def session(self) -> str:
        """The default session identifier for outbound messages."""
        return self._session

    @session.setter
    def session(self, value: str) -> None:
        """Set the default session identifier for outbound messages."""
        self._session = value

    @property
    def process(self) -> subprocess.Popen[bytes]:
        """The underlying subprocess."""
        return self._process

    # -------------------------------------------------------------------
    # Context manager
    # -------------------------------------------------------------------

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    def wait_hello(self, timeout: float = 10.0) -> HelloInfo:
        """Wait for the renderer hello handshake to complete.

        Args:
            timeout: Maximum seconds to wait for the hello message.

        Returns:
            The ``HelloInfo`` from the renderer.

        Raises:
            ConnectionError: If the hello is not received within the
                timeout or the protocol version does not match.
        """
        if not self._hello_event.wait(timeout):
            raise ConnectionError(f"renderer did not send hello within {timeout}s")
        if self._hello_error is not None:
            raise self._hello_error
        assert self._hello is not None
        _validate_required_widgets(self._hello, self._expected_widgets)
        return self._hello

    def close(self) -> None:
        """Shut down the connection and clean up the subprocess.

        Sends SIGTERM, waits briefly, then SIGKILL if still running.
        Safe to call multiple times.
        """
        if self._closed:
            return
        self._closed = True

        proc = self._process
        if proc.stdin:
            with contextlib.suppress(OSError):
                proc.stdin.close()

        with contextlib.suppress(OSError):
            proc.terminate()

        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):
                proc.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=2.0)

        if proc.stdout:
            with contextlib.suppress(OSError):
                proc.stdout.close()
        if proc.stderr:
            with contextlib.suppress(OSError):
                proc.stderr.close()

    def restart(self) -> None:
        """Restart the renderer subprocess after a crash.

        Closes the old process (if still alive), starts a new one with
        the same arguments, and starts a new reader thread. The caller
        must re-send settings and a snapshot after restarting.

        Raises:
            ConnectionError: If the subprocess cannot be restarted.
            RuntimeError: If spawn args are not available (e.g. for
                connections not created via ``open()``).
        """
        if self._spawn_args is None:
            raise RuntimeError("cannot restart: no spawn args available")

        # Clean up old process
        self._closed = True
        self._reader_generation += 1
        old_reader = self._reader_thread
        proc = self._process
        if proc.stdin:
            with contextlib.suppress(OSError):
                proc.stdin.close()
        with contextlib.suppress(OSError):
            proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):
                proc.kill()

        if proc.stdout:
            with contextlib.suppress(OSError):
                proc.stdout.close()
        if proc.stderr:
            with contextlib.suppress(OSError):
                proc.stderr.close()
        old_reader.join(timeout=2.0)

        # Start new process
        try:
            new_proc = subprocess.Popen(
                self._spawn_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._spawn_env,
                bufsize=0,
            )
        except OSError as exc:
            raise ConnectionError(f"failed to restart renderer: {exc}") from exc

        self._process = new_proc
        self._closed = False
        self._hello = None
        self._hello_error = None
        self._hello_event.clear()
        self._framing = _framing_for(self._format)
        generation = self._reader_generation

        # Drain queues
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except Empty:
                break
        with self._pending_lock:
            self._pending.clear()

        # Start new reader thread
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(generation,),
            name="plushie-reader",
            daemon=True,
        )
        self._reader_thread.start()

    @property
    def is_alive(self) -> bool:
        """Whether the subprocess is still running."""
        return self._process.poll() is None

    # -------------------------------------------------------------------
    # Low-level send/receive
    # -------------------------------------------------------------------

    def send(self, msg: dict[str, Any]) -> None:
        """Send a message to the renderer.

        Thread-safe (uses an internal lock).

        Args:
            msg: Message dict to encode and send.

        Raises:
            ConnectionError: If the connection is closed or broken.
        """
        if self._closed:
            raise ConnectionError("connection is closed")

        data = type(self._framing).encode(msg)
        with self._send_lock:
            stdin = self._process.stdin
            if stdin is None:
                raise ConnectionError("stdin pipe is not available")
            try:
                stdin.write(data)
                stdin.flush()
            except (OSError, BrokenPipeError) as exc:
                raise ConnectionError(f"send failed: {exc}") from exc

    def receive_event(self, timeout: float | None = None) -> Any:
        """Receive the next event from the event queue.

        Blocks until an event is available or the timeout expires.

        Args:
            timeout: Maximum seconds to wait. ``None`` for indefinite.

        Returns:
            The next decoded event, or ``None`` on timeout.
        """
        try:
            return self._event_queue.get(timeout=timeout)
        except Empty:
            return None

    # -------------------------------------------------------------------
    # Request-response helpers
    # -------------------------------------------------------------------

    def _send_request(self, msg: dict[str, Any], request_id: str) -> None:
        """Send a request message and register a pending response queue.

        Args:
            msg: The request message dict.
            request_id: The request ID for correlation.
        """
        q: Queue[dict[str, Any]] = Queue(maxsize=1)
        with self._pending_lock:
            self._pending[request_id] = q
        self.send(msg)

    def _wait_response(
        self,
        request_id: str,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Wait for a response to a previously sent request.

        Args:
            request_id: The request ID to wait on.
            timeout: Maximum seconds to wait.

        Returns:
            The response dict.

        Raises:
            ConnectionError: On timeout.
        """
        with self._pending_lock:
            q = self._pending.get(request_id)
        if q is None:
            raise ConnectionError(f"no pending request for id {request_id!r}")
        try:
            result = q.get(timeout=timeout)
        except Empty:
            raise ConnectionError(
                f"timeout waiting for response to request {request_id!r}"
            ) from None
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)
        return result

    # -------------------------------------------------------------------
    # Convenience: outbound messages
    # -------------------------------------------------------------------

    def send_settings(
        self,
        settings_dict: dict[str, Any] | None = None,
    ) -> None:
        """Send a Settings message to the renderer.

        Args:
            settings_dict: Application settings (all fields optional).
                Defaults to empty dict.
        """
        msg = settings(
            {} if settings_dict is None else settings_dict, session=self._session
        )
        self.send(msg)

    def send_snapshot(self, tree: dict[str, Any]) -> None:
        """Send a Snapshot message (full tree replacement).

        Args:
            tree: The complete UI tree as a node dict.
        """
        msg = snapshot(tree, session=self._session)
        self.send(msg)

    def send_patch(self, ops: list[dict[str, Any]]) -> None:
        """Send a Patch message (incremental tree update).

        Args:
            ops: List of patch operations.
        """
        msg = patch(ops, session=self._session)
        self.send(msg)

    def send_subscribe(
        self,
        kind: str,
        tag: str,
        *,
        max_rate: int | None = None,
        window_id: str | None = None,
    ) -> None:
        """Subscribe to a renderer event category.

        Args:
            kind: Event category (e.g. ``"on_key_press"``).
            tag: Tag for routing events.
            max_rate: Maximum events per second (omit for unlimited).
            window_id: Optional window to scope events to.
        """
        msg = subscribe_msg(
            kind, tag, max_rate=max_rate, window_id=window_id, session=self._session
        )
        self.send(msg)

    def send_unsubscribe(self, kind: str, *, tag: str | None = None) -> None:
        """Unsubscribe from a renderer event category.

        Args:
            kind: Event category to unsubscribe from.
            tag: Optional tag for targeted removal when multiple
                subscriptions of the same kind coexist.
        """
        msg = unsubscribe_msg(kind, tag=tag, session=self._session)
        self.send(msg)

    def send_widget_op(
        self,
        op: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Send a widget operation to the renderer.

        Args:
            op: Operation name (e.g. ``"focus"``).
            payload: Operation-specific payload.
        """
        msg = widget_op(op, payload, session=self._session)
        self.send(msg)

    def send_window_op(
        self,
        op: str,
        window_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Send a window operation to the renderer.

        Uses the unified ``_op`` envelope: op-specific data lives under
        ``payload``.

        Args:
            op: Operation name (e.g. ``"resize"``).
            window_id: Target window identifier.
            payload: Operation-specific payload.
        """
        msg = window_op(op, window_id, payload, session=self._session)
        self.send(msg)

    def send_advance_frame(self, timestamp: int) -> None:
        """Send an AdvanceFrame message.

        Args:
            timestamp: Frame timestamp in milliseconds.
        """
        msg = advance_frame_msg(timestamp, session=self._session)
        self.send(msg)

    # -------------------------------------------------------------------
    # Convenience: request-response
    # -------------------------------------------------------------------

    def query_find(
        self,
        selector: str | dict[str, str],
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any] | None:
        """Query the renderer for a widget by selector.

        Args:
            selector: Selector string (``"#id"`` or ``"text content"``)
                or a raw selector dict (``{"by": "role", "value": "button"}``).
            timeout: Maximum seconds to wait for the response.

        Returns:
            The node dict if found, or ``None``.
        """
        rid = _next_request_id()
        sel = selector if isinstance(selector, dict) else encode_selector(selector)
        msg = query_msg(rid, "find", sel, session=self._session)
        self._send_request(msg, rid)
        resp = self._wait_response(rid, timeout=timeout)
        return resp.get("data")

    def query_tree(self, *, timeout: float = 10.0) -> dict[str, Any] | None:
        """Query the renderer for the full tree.

        Args:
            timeout: Maximum seconds to wait for the response.

        Returns:
            The full tree dict, or ``None`` if no tree has been sent.
        """
        rid = _next_request_id()
        msg = query_msg(rid, "tree", session=self._session)
        self._send_request(msg, rid)
        resp = self._wait_response(rid, timeout=timeout)
        return resp.get("data")

    def interact(
        self,
        action: str,
        selector: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        on_step: Callable[[list[Any]], dict[str, Any]] | None = None,
        timeout: float = 30.0,
    ) -> list[Any]:
        """Simulate a user interaction and collect resulting events.

        In headless mode, the renderer may emit ``interact_step``
        messages requiring a snapshot round-trip. The ``on_step``
        callback is called with the step's events and must return the
        updated tree (snapshot) to send back.

        In mock mode, no steps are emitted and all events are in the
        final ``interact_response``.

        Args:
            action: Interaction type (e.g. ``"click"``, ``"type_text"``).
            selector: Target selector string. Required for widget-specific
                actions, optional for global actions.
            payload: Action-specific parameters.
            on_step: Callback for headless interact steps. Receives the
                step's event list and must return the updated tree dict.
                If ``None`` and a step arrives, the step events are
                collected but no snapshot is sent (useful for mock mode
                or when the caller handles steps externally).
            timeout: Maximum seconds to wait for the interaction to
                complete.

        Returns:
            List of decoded events from the interaction.
        """
        rid = _next_request_id()
        sel = encode_selector(selector) if selector else None
        msg = interact_msg(rid, action, sel, payload, session=self._session)

        q: Queue[dict[str, Any]] = Queue()
        with self._pending_lock:
            self._pending[rid] = q

        all_events: list[Any] = []

        try:
            self.send(msg)

            while True:
                try:
                    resp = q.get(timeout=timeout)
                except Empty:
                    raise ConnectionError(
                        f"timeout waiting for interact response (id={rid!r})"
                    ) from None

                resp_type = resp.get("type", "")

                if resp_type == "interact_step":
                    step_events = _decode_events_list(resp.get("events", []))
                    all_events.extend(step_events)
                    if on_step is not None:
                        updated_tree = on_step(step_events)
                        self.send_snapshot(updated_tree)
                    continue

                if resp_type == "interact_response":
                    final_events = _decode_events_list(resp.get("events", []))
                    all_events.extend(final_events)
                    break

                # Unexpected message type; treat as final
                logger.warning(
                    "unexpected message during interact: type=%s",
                    resp_type,
                )
                break
        finally:
            with self._pending_lock:
                self._pending.pop(rid, None)

        return all_events

    def request_effect(
        self,
        request_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send an effect request and wait for the response.

        Args:
            request_id: Unique request ID for correlation.
            kind: Effect kind (e.g. ``"clipboard_read"``).
            payload: Effect-specific payload.
            timeout: Maximum seconds to wait.

        Returns:
            The effect response dict.
        """
        msg = effect_msg(request_id, kind, payload, session=self._session)
        self._send_request(msg, request_id)
        return self._wait_response(request_id, timeout=timeout)

    def take_screenshot(
        self,
        name: str,
        *,
        width: int = 1024,
        height: int = 768,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Request a screenshot and wait for the response.

        Args:
            name: Label for this screenshot capture.
            width: Viewport width in pixels.
            height: Viewport height in pixels.
            timeout: Maximum seconds to wait.

        Returns:
            The screenshot response dict.
        """
        rid = _next_request_id()
        msg = screenshot_msg(
            rid, name, width=width, height=height, session=self._session
        )
        self._send_request(msg, rid)
        return self._wait_response(rid, timeout=timeout)

    def compute_tree_hash(
        self,
        name: str,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Request a tree hash and wait for the response.

        Args:
            name: Label for this hash capture.
            timeout: Maximum seconds to wait.

        Returns:
            The tree hash response dict.
        """
        rid = _next_request_id()
        msg = tree_hash_msg(rid, name, session=self._session)
        self._send_request(msg, rid)
        return self._wait_response(rid, timeout=timeout)

    def reset_session(
        self,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Reset all session state and wait for confirmation.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            The reset response dict.
        """
        rid = _next_request_id()
        msg = reset_msg(rid, session=self._session)
        self._send_request(msg, rid)
        return self._wait_response(rid, timeout=timeout)

    # -------------------------------------------------------------------
    # Reader thread
    # -------------------------------------------------------------------

    def _reader_loop(self, generation: int) -> None:
        """Background thread that reads and routes incoming messages.

        Events go to the event queue. Responses for pending requests
        go to the per-request queue. Hello is stored and signals the
        hello event.
        """
        stdout = self._process.stdout
        if stdout is None:
            return

        try:
            while self._reader_is_current(generation):
                chunk = stdout.read(4096)
                if not chunk:
                    break
                if not self._reader_is_current(generation):
                    break

                messages = self._framing.feed(chunk)
                for raw_msg in messages:
                    if not self._reader_is_current(generation):
                        break
                    self._route_message(raw_msg)
        except OSError:
            pass
        except Exception:
            logger.exception("plushie reader thread error")
        finally:
            if self._reader_is_current(generation):
                # Signal that the connection is broken
                self._event_queue.put(None)

    def _reader_is_current(self, generation: int) -> bool:
        return not self._closed and generation == self._reader_generation

    def _route_message(self, raw_msg: dict[str, Any]) -> None:
        """Route a decoded message to the appropriate destination.

        - ``hello`` -> stored and signals hello event
        - Response types with an ``id`` field matching a pending
          request -> routed to the per-request queue
        - Events -> routed to the event queue
        """
        msg_type = raw_msg.get("type", "")
        msg_id = raw_msg.get("id", "")

        # Hello message
        if msg_type == "hello":
            try:
                decoded = _parse_hello_for_handshake(raw_msg)
                _validate_hello_protocol(decoded)
            except ProtocolMismatchError as err:
                logger.error("plushie connection: %s", err)
                self._hello_error = err
                self._hello_event.set()
                return
            self._hello = decoded
            self._hello_error = None
            self._hello_event.set()
            self._event_queue.put(decoded)
            return

        # Response types: route to pending request queue
        response_types = (
            "query_response",
            "interact_response",
            "interact_step",
            "tree_hash_response",
            "screenshot_response",
            "reset_response",
            "effect_response",
        )
        if msg_type in response_types and msg_id:
            with self._pending_lock:
                q = self._pending.get(msg_id)
            if q is not None:
                q.put(raw_msg)
                return

        # Everything else: decode and route to event queue
        decoded = decode_message(raw_msg)
        self._event_queue.put(decoded)


# ---------------------------------------------------------------------------
# StdioConnection
# ---------------------------------------------------------------------------


class StdioConnection:
    """Connection using the process's own stdin/stdout (fd 0/1).

    Used when the renderer spawns the Python process via
    ``plushie --exec``. The renderer writes to our stdin and reads
    from our stdout.

    The same interface as ``Connection`` but without subprocess
    management.
    """

    def __init__(self, *, session: str = "", format: str = "msgpack") -> None:
        self._session = session
        self._format = format
        self._framing = _framing_for(format)
        self._send_lock = threading.Lock()
        self._event_queue: Queue[Any] = Queue()
        self._pending: dict[str, Queue[dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        self._hello: HelloInfo | None = None
        self._hello_error: ProtocolMismatchError | None = None
        self._expected_widgets: tuple[str, ...] = ()
        self._hello_event = threading.Event()
        self._closed = False

        # Open raw binary file objects for fd 0 and 1
        self._stdin_fd = os.fdopen(os.dup(0), "rb", buffering=0)
        self._stdout_fd = os.fdopen(os.dup(1), "wb", buffering=0)

        # Redirect Python's stdout to stderr so print() doesn't
        # corrupt the wire protocol
        sys.stdout = sys.stderr  # type: ignore[assignment]

        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="plushie-stdio-reader",
            daemon=True,
        )
        self._reader_thread.start()

    @property
    def hello(self) -> HelloInfo | None:
        """The hello info received from the renderer."""
        return self._hello

    @property
    def session(self) -> str:
        """The default session identifier."""
        return self._session

    @session.setter
    def session(self, value: str) -> None:
        """Set the default session identifier."""
        self._session = value

    def __enter__(self) -> StdioConnection:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def wait_hello(self, timeout: float = 10.0) -> HelloInfo:
        """Wait for the renderer hello handshake to complete.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            The ``HelloInfo`` from the renderer.

        Raises:
            ConnectionError: If the hello is not received within the timeout.
        """
        if not self._hello_event.wait(timeout):
            raise ConnectionError(f"renderer did not send hello within {timeout}s")
        if self._hello_error is not None:
            raise self._hello_error
        assert self._hello is not None
        _validate_required_widgets(self._hello, self._expected_widgets)
        return self._hello

    def send(self, msg: dict[str, Any]) -> None:
        """Send a message to the renderer via stdout.

        Thread-safe (uses an internal lock).

        Args:
            msg: Message dict to encode and send.

        Raises:
            ConnectionError: If the connection is closed or broken.
        """
        if self._closed:
            raise ConnectionError("connection is closed")
        data = type(self._framing).encode(msg)
        with self._send_lock:
            try:
                self._stdout_fd.write(data)
                self._stdout_fd.flush()
            except (OSError, BrokenPipeError) as exc:
                raise ConnectionError(f"send failed: {exc}") from exc

    def receive_event(self, timeout: float | None = None) -> Any:
        """Receive the next event from the event queue.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            The next decoded event, or ``None`` on timeout.
        """
        try:
            return self._event_queue.get(timeout=timeout)
        except Empty:
            return None

    def send_settings(self, settings_dict: dict[str, Any] | None = None) -> None:
        """Send a Settings message."""
        msg = settings(
            {} if settings_dict is None else settings_dict, session=self._session
        )
        self.send(msg)

    def send_snapshot(self, tree: dict[str, Any]) -> None:
        """Send a Snapshot message."""
        msg = snapshot(tree, session=self._session)
        self.send(msg)

    def send_patch(self, ops: list[dict[str, Any]]) -> None:
        """Send a Patch message."""
        msg = patch(ops, session=self._session)
        self.send(msg)

    def close(self) -> None:
        """Close the stdio connection.

        Safe to call multiple times.
        """
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(OSError):
            self._stdin_fd.close()
        with contextlib.suppress(OSError):
            self._stdout_fd.close()

    def _reader_loop(self) -> None:
        """Background thread reading from stdin."""
        try:
            while not self._closed:
                chunk = self._stdin_fd.read(4096)
                if not chunk:
                    break
                messages = self._framing.feed(chunk)
                for raw_msg in messages:
                    self._route_message(raw_msg)
        except OSError:
            pass
        except Exception:
            logger.exception("plushie stdio reader thread error")
        finally:
            if not self._closed:
                self._event_queue.put(None)

    def _route_message(self, raw_msg: dict[str, Any]) -> None:
        """Route an incoming message (same logic as Connection)."""
        msg_type = raw_msg.get("type", "")
        msg_id = raw_msg.get("id", "")

        if msg_type == "hello":
            try:
                decoded = _parse_hello_for_handshake(raw_msg)
                _validate_hello_protocol(decoded)
            except ProtocolMismatchError as err:
                logger.error("plushie stdio connection: %s", err)
                self._hello_error = err
                self._hello_event.set()
                return
            self._hello = decoded
            self._hello_error = None
            self._hello_event.set()
            self._event_queue.put(decoded)
            return

        response_types = (
            "query_response",
            "interact_response",
            "interact_step",
            "tree_hash_response",
            "screenshot_response",
            "reset_response",
            "effect_response",
        )
        if msg_type in response_types and msg_id:
            with self._pending_lock:
                q = self._pending.get(msg_id)
            if q is not None:
                q.put(raw_msg)
                return

        decoded = decode_message(raw_msg)
        self._event_queue.put(decoded)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Exact variable names to forward to the renderer subprocess.
# Prevents leaking sensitive variables (API keys, tokens, DB URLs).
# Matches the canonical whitelist shared across every host SDK.
_ENV_WHITELIST_EXACT = frozenset(
    {
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "WAYLAND_SOCKET",
        "WINIT_UNIX_BACKEND",
        "XDG_CURRENT_DESKTOP",
        "XDG_RUNTIME_DIR",
        "XDG_SESSION_TYPE",
        "XDG_DATA_DIRS",
        "XDG_DATA_HOME",
        "PATH",
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
        "LANG",
        "LANGUAGE",
        "DBUS_SESSION_BUS_ADDRESS",
        "GTK_MODULES",
        "GDK_BACKEND",
        "GSK_RENDERER",
        "CLUTTER_BACKEND",
        "SDL_VIDEO_wayland",
        "QT_QPA_PLATFORM",
        "NO_AT_BRIDGE",
        "SWAYSOCK",
        "WGPU_BACKEND",
        "RUST_LOG",
        "RUST_BACKTRACE",
        "HOME",
        "USER",
    }
)

# Prefixes: any variable starting with one of these is forwarded.
# "PLUSHIE_" catches all plushie-reserved debug toggles (e.g.
# PLUSHIE_NO_CATCH_UNWIND) without per-var maintenance.
_ENV_WHITELIST_PREFIXES = (
    "LC_",
    "MESA_",
    "LIBGL_",
    "__GLX_",
    "VK_",
    "GALLIUM_",
    "AT_SPI_",
    "FONTCONFIG_",
    "PLUSHIE_",
)


def _build_env(extra: Mapping[str, object] | None = None) -> dict[str, str]:
    """Build a safe, whitelisted environment for the renderer subprocess.

    Only forwards display, rendering, locale, accessibility, font, and
    renderer-specific variables. Prevents leaking sensitive variables
    (API keys, database credentials, tokens) to the renderer process.

    Args:
        extra: Additional environment variables to include (always
            forwarded regardless of whitelist).

    Returns:
        Filtered environment dict for subprocess.Popen.
    """
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in _ENV_WHITELIST_EXACT or any(
            key.startswith(p) for p in _ENV_WHITELIST_PREFIXES
        ):
            env[key] = str(value)
    if extra:
        env.update({key: str(value) for key, value in extra.items()})
    return env


def _decode_events_list(raw_events: list[dict[str, Any]]) -> list[Any]:
    """Decode a list of raw event dicts into event dataclasses.

    Args:
        raw_events: List of wire-format event dicts.

    Returns:
        List of decoded event objects.
    """
    decoded = []
    for raw in raw_events:
        decoded.append(decode_message(raw))
    return decoded


def _token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------


class _IoStreamConnection:
    """Connection-like wrapper around an iostream adapter.

    Provides the same outbound message API as ``Connection`` but
    delegates transport to the adapter. Used by
    ``Connection.from_iostream()``.
    """

    def __init__(
        self,
        adapter: Any,
        *,
        session: str = "",
        expected_widgets: list[str | NativeWidget]
        | tuple[str | NativeWidget, ...]
        | None = None,
        token: str | None = None,
        token_sha256: str | None = None,
    ) -> None:
        self._adapter = adapter
        self._session = session
        self._expected_widgets = _normalize_expected_widgets(expected_widgets)
        self._token_sha256 = (
            token_sha256
            if token_sha256 is not None
            else _token_sha256(token)
            if token is not None
            else None
        )
        self._sent_initial_settings = False
        self._pending: dict[str, Queue[dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        if self._supports_request_response:
            adapter.set_message_handler(self._route_message)

    @property
    def hello(self) -> HelloInfo | None:
        return self._adapter.hello

    @property
    def session(self) -> str:
        return self._session

    @session.setter
    def session(self, value: str) -> None:
        self._session = value

    @property
    def is_alive(self) -> bool:
        return not self._adapter.is_closed

    def __enter__(self) -> _IoStreamConnection:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def wait_hello(self, timeout: float = 10.0) -> HelloInfo:
        hello = self._adapter.wait_hello(timeout)
        _validate_required_widgets(hello, self._expected_widgets)
        return hello

    def send(self, msg: dict[str, Any]) -> None:
        self._adapter.send(msg)

    def receive_event(self, timeout: float | None = None) -> Any:
        return self._adapter.receive_event(timeout)

    @property
    def _supports_request_response(self) -> bool:
        return callable(getattr(self._adapter, "set_message_handler", None))

    def _send_request(self, msg: dict[str, Any], request_id: str) -> None:
        if not self._supports_request_response:
            raise ConnectionError(
                "request-response methods require an adapter with "
                "set_message_handler() support"
            )
        q: Queue[dict[str, Any]] = Queue(maxsize=1)
        with self._pending_lock:
            self._pending[request_id] = q
        self.send(msg)

    _wait_response = Connection._wait_response

    def send_settings(self, settings_dict: dict[str, Any] | None = None) -> None:
        merged = {} if settings_dict is None else dict(settings_dict)
        if (
            self._token_sha256 is not None
            and "token_sha256" in merged
            and merged["token_sha256"] != self._token_sha256
        ):
            raise ValueError("settings token_sha256 conflicts with connection token")
        if self._token_sha256 is not None and not self._sent_initial_settings:
            merged["token_sha256"] = self._token_sha256
        msg = settings(merged, session=self._session)
        self.send(msg)
        self._sent_initial_settings = True

    def send_snapshot(self, tree: dict[str, Any]) -> None:
        msg = snapshot(tree, session=self._session)
        self.send(msg)

    def send_patch(self, ops: list[dict[str, Any]]) -> None:
        msg = patch(ops, session=self._session)
        self.send(msg)

    def send_subscribe(
        self,
        kind: str,
        tag: str,
        *,
        max_rate: int | None = None,
        window_id: str | None = None,
    ) -> None:
        msg = subscribe_msg(
            kind, tag, max_rate=max_rate, window_id=window_id, session=self._session
        )
        self.send(msg)

    def send_unsubscribe(self, kind: str, *, tag: str | None = None) -> None:
        msg = unsubscribe_msg(kind, tag=tag, session=self._session)
        self.send(msg)

    send_widget_op = Connection.send_widget_op
    send_window_op = Connection.send_window_op
    send_advance_frame = Connection.send_advance_frame
    query_find = Connection.query_find
    query_tree = Connection.query_tree
    request_effect = Connection.request_effect
    take_screenshot = Connection.take_screenshot
    compute_tree_hash = Connection.compute_tree_hash
    reset_session = Connection.reset_session

    def interact(
        self,
        action: str,
        selector: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        on_step: Callable[[list[Any]], dict[str, Any]] | None = None,
        timeout: float = 30.0,
    ) -> list[Any]:
        if not self._supports_request_response:
            raise ConnectionError(
                "request-response methods require an adapter with "
                "set_message_handler() support"
            )
        connection_interact: Any = Connection.interact
        return connection_interact(
            self,
            action,
            selector,
            payload,
            on_step=on_step,
            timeout=timeout,
        )

    def _route_message(self, raw_msg: dict[str, Any]) -> bool:
        msg_type = raw_msg.get("type", "")
        msg_id = raw_msg.get("id", "")
        response_types = (
            "query_response",
            "interact_response",
            "interact_step",
            "tree_hash_response",
            "screenshot_response",
            "reset_response",
            "effect_response",
        )
        if msg_type in response_types and msg_id:
            with self._pending_lock:
                q = self._pending.get(msg_id)
            if q is not None:
                q.put(raw_msg)
                return True
        return False

    def close(self) -> None:
        if self._supports_request_response:
            self._adapter.set_message_handler(None)
        self._adapter.close()


__all__ = [
    "Connection",
    "ConnectionError",
    "ProtocolMismatchError",
    "ProtocolVersionMismatchError",
    "StdioConnection",
]
