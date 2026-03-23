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
import itertools
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

from plushie.binary import PlushieNotFoundError, resolve
from plushie.framing import MsgpackFraming
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


class ConnectionError(Exception):
    """Raised when a connection operation fails."""


class ProtocolMismatchError(ConnectionError):
    """Raised when the renderer reports an incompatible protocol version."""


# ---------------------------------------------------------------------------
# Request ID generator
# ---------------------------------------------------------------------------

_request_counter = itertools.count(1)


def _next_request_id() -> str:
    """Generate a unique request ID for request-response correlation."""
    return f"py-{next(_request_counter)}"


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
        _spawn_args: list[str] | None = None,
        _spawn_env: dict[str, str] | None = None,
    ) -> None:
        self._process = process
        self._session = session
        self._spawn_args = _spawn_args
        self._spawn_env = _spawn_env
        self._framing = MsgpackFraming()
        self._send_lock = threading.Lock()
        self._event_queue: Queue[Any] = Queue()
        self._pending: dict[str, Queue[dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        self._hello: HelloInfo | None = None
        self._hello_event = threading.Event()
        self._closed = False
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
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
        json: bool = False,
        max_sessions: int | None = None,
        session: str = "",
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> Connection:
        """Start a renderer subprocess and return a Connection.

        Args:
            binary_path: Path to the plushie binary. Resolved
                automatically if ``None``.
            mode: Renderer mode: ``"mock"``, ``"headless"``, or
                ``None`` for windowed (default).
            json: If ``True``, force JSON wire format instead of msgpack.
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
        if json:
            args.append("--json")
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

        return cls(process, session=session, _spawn_args=args, _spawn_env=proc_env)

    @classmethod
    def from_iostream(
        cls,
        adapter: Any,
        *,
        session: str = "",
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

        Returns:
            A connection-like object wrapping the adapter.
        """
        return _IoStreamConnection(adapter, session=session)

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
        assert self._hello is not None
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
        self._hello_event.clear()
        self._framing = MsgpackFraming()

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

        data = MsgpackFraming.encode(msg)
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
        msg = settings(settings_dict or {}, session=self._session)
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
    ) -> None:
        """Subscribe to a renderer event category.

        Args:
            kind: Event category (e.g. ``"on_key_press"``).
            tag: Tag for routing events.
            max_rate: Maximum events per second (omit for unlimited).
        """
        msg = subscribe_msg(kind, tag, max_rate=max_rate, session=self._session)
        self.send(msg)

    def send_unsubscribe(self, kind: str) -> None:
        """Unsubscribe from a renderer event category.

        Args:
            kind: Event category to unsubscribe from.
        """
        msg = unsubscribe_msg(kind, session=self._session)
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
        op_settings: dict[str, Any] | None = None,
    ) -> None:
        """Send a window operation to the renderer.

        Args:
            op: Operation name (e.g. ``"resize"``).
            window_id: Target window identifier.
            op_settings: Operation-specific settings.
        """
        msg = window_op(op, window_id, op_settings, session=self._session)
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

        self.send(msg)

        all_events: list[Any] = []

        while True:
            try:
                resp = q.get(timeout=timeout)
            except Empty:
                with self._pending_lock:
                    self._pending.pop(rid, None)
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

            # Unexpected message type -- treat as final
            logger.warning(
                "unexpected message during interact: type=%s",
                resp_type,
            )
            break

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

    def _reader_loop(self) -> None:
        """Background thread that reads and routes incoming messages.

        Events go to the event queue. Responses for pending requests
        go to the per-request queue. Hello is stored and signals the
        hello event.
        """
        stdout = self._process.stdout
        if stdout is None:
            return

        try:
            while not self._closed:
                chunk = stdout.read(4096)
                if not chunk:
                    break

                messages = self._framing.feed(chunk)
                for raw_msg in messages:
                    self._route_message(raw_msg)
        except OSError:
            pass
        except Exception:
            logger.exception("plushie reader thread error")
        finally:
            if not self._closed:
                # Signal that the connection is broken
                self._event_queue.put(None)

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
            decoded = decode_message(raw_msg)
            if isinstance(decoded, HelloInfo):
                if decoded.protocol != PROTOCOL_VERSION:
                    logger.error(
                        "protocol mismatch: renderer reports %d, expected %d",
                        decoded.protocol,
                        PROTOCOL_VERSION,
                    )
                self._hello = decoded
                self._hello_event.set()
                self._event_queue.put(decoded)
                return

        # Response types -- route to pending request queue
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

    def __init__(self, *, session: str = "") -> None:
        self._session = session
        self._framing = MsgpackFraming()
        self._send_lock = threading.Lock()
        self._event_queue: Queue[Any] = Queue()
        self._pending: dict[str, Queue[dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        self._hello: HelloInfo | None = None
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
        assert self._hello is not None
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
        data = MsgpackFraming.encode(msg)
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
        msg = settings(settings_dict or {}, session=self._session)
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
            decoded = decode_message(raw_msg)
            if isinstance(decoded, HelloInfo):
                self._hello = decoded
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


def _build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build the subprocess environment.

    Inherits the parent environment and whitelists display/rendering
    variables. Merges any extra vars on top.

    Args:
        extra: Additional environment variables.

    Returns:
        Complete environment dict for subprocess.Popen.
    """
    env = dict(os.environ)
    if extra:
        env.update(extra)
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


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------


class _IoStreamConnection:
    """Connection-like wrapper around an iostream adapter.

    Provides the same outbound message API as ``Connection`` but
    delegates transport to the adapter. Used by
    ``Connection.from_iostream()``.
    """

    def __init__(self, adapter: Any, *, session: str = "") -> None:
        self._adapter = adapter
        self._session = session

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
        return self._adapter.wait_hello(timeout)

    def send(self, msg: dict[str, Any]) -> None:
        self._adapter.send(msg)

    def receive_event(self, timeout: float | None = None) -> Any:
        return self._adapter.receive_event(timeout)

    def send_settings(self, settings_dict: dict[str, Any] | None = None) -> None:
        msg = settings(settings_dict or {}, session=self._session)
        self.send(msg)

    def send_snapshot(self, tree: dict[str, Any]) -> None:
        msg = snapshot(tree, session=self._session)
        self.send(msg)

    def send_patch(self, ops: list[dict[str, Any]]) -> None:
        msg = patch(ops, session=self._session)
        self.send(msg)

    def send_subscribe(
        self, kind: str, tag: str, *, max_rate: int | None = None
    ) -> None:
        msg = subscribe_msg(kind, tag, max_rate=max_rate, session=self._session)
        self.send(msg)

    def send_unsubscribe(self, kind: str) -> None:
        msg = unsubscribe_msg(kind, session=self._session)
        self.send(msg)

    def close(self) -> None:
        self._adapter.close()


__all__ = [
    "Connection",
    "ConnectionError",
    "ProtocolMismatchError",
    "StdioConnection",
]
