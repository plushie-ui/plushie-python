"""iostream/custom transport adapters for plushie connections.

Bridges any bidirectional byte stream to the Connection protocol,
allowing plushie to communicate over sockets, pipes, WebSockets,
or any custom transport.

The iostream protocol (matching the Elixir Bridge's iostream mode):

- The adapter reads frames from the underlying stream and forwards
  decoded events to a callback.
- The adapter provides a ``send()`` method for writing frames.
- The adapter can be passed to ``Connection.from_iostream()`` to
  create a full Connection instance.

Usage::

    from plushie.transport import IoStreamAdapter, SocketAdapter

    # Manual socket
    import socket
    sock = socket.create_connection(("127.0.0.1", 4567))
    adapter = IoStreamAdapter(sock.makefile("rb"), sock.makefile("wb"))
    conn = Connection.from_iostream(adapter)

    # SocketAdapter convenience (TCP or Unix domain socket)
    adapter = SocketAdapter("127.0.0.1:4567")
    conn = Connection.from_iostream(adapter)

    adapter = SocketAdapter("/tmp/plushie.sock")
    conn = Connection.from_iostream(adapter)
"""

from __future__ import annotations

import contextlib
import logging
import socket
import threading
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any, Literal, Protocol, runtime_checkable

from plushie.connection import (
    ProtocolMismatchError,
    _parse_hello_for_handshake,
    _validate_hello_protocol,
)
from plushie.framing import JsonFraming, MsgpackFraming
from plushie.protocol import decode_message
from plushie.types import HelloInfo

logger = logging.getLogger("plushie")


@runtime_checkable
class ReadableStream(Protocol):
    """Any object that supports blocking reads of raw bytes."""

    def read(self, n: int = ..., /) -> bytes:
        """Read up to *n* bytes, blocking until data is available."""
        ...


@runtime_checkable
class WritableStream(Protocol):
    """Any object that supports writing raw bytes."""

    def write(self, data: bytes, /) -> int | None:
        """Write *data* bytes to the stream."""
        ...

    def flush(self) -> None:
        """Flush any buffered output."""
        ...


class IoStreamAdapter:
    """Bridges a bidirectional byte stream to the plushie wire protocol.

    Accepts any pair of objects with ``read()`` and ``write()`` methods
    (socket file wrappers, pipes, custom stream objects). Runs a reader
    thread that decodes frames and posts events to the queue, and
    provides a thread-safe ``send()`` for outbound messages.

    The same iostream concept as the Elixir Bridge's
    ``{:iostream, pid}`` transport and the Gleam socket_adapter,
    adapted for Python's threading model.

    Args:
        reader: A readable byte stream (must support ``read(n)``).
        writer: A writable byte stream (must support ``write(data)``
            and ``flush()``).
        on_event: Optional callback invoked for each decoded event.
            If not provided, events are queued internally and can be
            retrieved via ``receive_event()``.
    """

    def __init__(
        self,
        reader: ReadableStream,
        writer: WritableStream,
        *,
        format: str = "msgpack",
        on_event: Callable[[Any], None] | None = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        if format == "msgpack":
            self._framing: MsgpackFraming | JsonFraming = MsgpackFraming()
        elif format == "json":
            self._framing = JsonFraming()
        else:
            raise ValueError(
                f"unknown wire format: {format!r} (expected 'msgpack' or 'json')"
            )
        self._send_lock = threading.Lock()
        self._event_queue: Queue[Any] = Queue()
        self._on_event = on_event
        self._on_message: Callable[[dict[str, Any]], bool] | None = None
        self._hello: HelloInfo | None = None
        self._hello_error: ProtocolMismatchError | None = None
        self._hello_event = threading.Event()
        self._closed = False

        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="plushie-iostream-reader",
            daemon=True,
        )
        self._reader_thread.start()

    @property
    def hello(self) -> HelloInfo | None:
        """The hello info received from the renderer, or None."""
        return self._hello

    def wait_hello(self, timeout: float = 10.0) -> HelloInfo:
        """Wait for the renderer hello handshake.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            The HelloInfo from the renderer.

        Raises:
            TimeoutError: If the hello is not received in time.
        """
        if not self._hello_event.wait(timeout):
            raise TimeoutError(f"renderer did not send hello within {timeout}s")
        if self._hello_error is not None:
            raise self._hello_error
        assert self._hello is not None
        return self._hello

    def send(self, msg: dict[str, Any]) -> None:
        """Encode and write a message to the underlying stream.

        Thread-safe.

        Args:
            msg: Message dict to encode and send.

        Raises:
            ConnectionError: If the adapter is closed or the write fails.
        """
        if self._closed:
            raise ConnectionError("iostream adapter is closed")
        data = type(self._framing).encode(msg)
        with self._send_lock:
            try:
                self._writer.write(data)
                self._writer.flush()
            except (OSError, BrokenPipeError) as exc:
                raise ConnectionError(f"iostream send failed: {exc}") from exc

    def receive_event(self, timeout: float | None = None) -> Any:
        """Receive the next event from the internal queue.

        Only useful when no ``on_event`` callback was provided.

        Args:
            timeout: Maximum seconds to wait. None for indefinite.

        Returns:
            The next decoded event, or None on timeout.
        """
        try:
            return self._event_queue.get(timeout=timeout)
        except Empty:
            return None

    def set_message_handler(
        self,
        on_message: Callable[[dict[str, Any]], bool] | None,
    ) -> None:
        """Set an optional raw-message interceptor.

        The interceptor returns True when it consumed the message. Messages
        it does not consume continue through normal hello and event routing.
        """
        self._on_message = on_message

    def close(self) -> None:
        """Close the adapter and underlying streams.

        Safe to call multiple times.
        """
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(OSError):
            if hasattr(self._reader, "close"):
                self._reader.close()  # type: ignore[union-attr]
        with contextlib.suppress(OSError):
            if hasattr(self._writer, "close"):
                self._writer.close()  # type: ignore[union-attr]

    @property
    def is_closed(self) -> bool:
        """Whether the adapter has been closed."""
        return self._closed

    def __enter__(self) -> IoStreamAdapter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _reader_loop(self) -> None:
        """Background thread: read from the stream, decode frames, route events."""
        try:
            while not self._closed:
                chunk = self._reader.read(4096)
                if not chunk:
                    break
                messages = self._framing.feed(chunk)
                for raw_msg in messages:
                    self._route_message(raw_msg)
        except OSError:
            pass
        except Exception:
            logger.exception("plushie iostream reader thread error")
        finally:
            if not self._closed:
                self._post_event(None)

    def _route_message(self, raw_msg: dict[str, Any]) -> None:
        """Decode and route an incoming message."""
        if self._on_message is not None and self._on_message(raw_msg):
            return

        msg_type = raw_msg.get("type", "")

        if msg_type == "hello":
            try:
                decoded = _parse_hello_for_handshake(raw_msg)
                _validate_hello_protocol(decoded)
            except ProtocolMismatchError as err:
                logger.error("plushie iostream adapter: %s", err)
                self._hello_error = err
                self._hello_event.set()
                return
            self._hello = decoded
            self._hello_error = None
            self._hello_event.set()
            self._post_event(decoded)
            return

        decoded = decode_message(raw_msg)
        self._post_event(decoded)

    def _post_event(self, event: Any) -> None:
        """Post an event to the callback or internal queue."""
        if self._on_event is not None:
            self._on_event(event)
        else:
            self._event_queue.put(event)


class WebSocketAdapter(IoStreamAdapter):
    """Adapter for WebSocket connections (e.g. WASM renderer).

    Wraps a WebSocket-like object that has ``recv()`` and
    ``send(bytes)`` methods into the ReadableStream/WritableStream
    interface that IoStreamAdapter expects.

    Usage::

        import websockets.sync.client as ws
        from plushie.transport import WebSocketAdapter

        with ws.connect("ws://localhost:8080") as websocket:
            adapter = WebSocketAdapter(websocket)
            conn = Connection.from_iostream(adapter, token="shared-secret")

    The WebSocket object must support:
    - ``recv()`` -> bytes (blocking receive of a complete message)
    - ``send(data: bytes)`` -> None (send a complete message)
    - Optionally ``close()`` for cleanup.

    WebSocketAdapter wraps an already-connected socket, so it does not
    add authentication headers. Pass ``token=...`` to
    ``Connection.from_iostream()`` to authenticate through the Settings
    handshake without sending the plaintext token.
    """

    def __init__(
        self,
        websocket: Any,
        *,
        on_event: Callable[[Any], None] | None = None,
    ) -> None:
        self._websocket = websocket
        wrapper_reader = _WebSocketReader(websocket)
        wrapper_writer = _WebSocketWriter(websocket)
        super().__init__(wrapper_reader, wrapper_writer, on_event=on_event)

    def close(self) -> None:
        """Close the adapter and the underlying WebSocket."""
        if self._closed:
            return
        super().close()
        with contextlib.suppress(Exception):
            if hasattr(self._websocket, "close"):
                self._websocket.close()


class _WebSocketReader:
    """Adapts a WebSocket's recv() into the ReadableStream interface."""

    def __init__(self, websocket: Any) -> None:
        self._ws = websocket
        self._buffer = bytearray()

    def read(self, n: int = 4096) -> bytes:
        """Read up to n bytes, fetching a new message if buffer is empty."""
        if n <= 0:
            return bytes(0)
        if not self._buffer:
            try:
                data = self._ws.recv()
            except Exception:
                logger.exception(
                    "plushie websocket recv failed; treating %s as EOF",
                    type(self._ws).__name__,
                )
                return bytes(0)
            if not data:
                return bytes(0)
            if isinstance(data, str):
                data = data.encode("utf-8")
            self._buffer.extend(data)
        result = bytes(self._buffer[:n])
        del self._buffer[:n]
        return result

    def close(self) -> None:
        """No-op: WebSocket lifecycle managed by WebSocketAdapter."""


class _WebSocketWriter:
    """Adapts a WebSocket's send() into the WritableStream interface."""

    def __init__(self, websocket: Any) -> None:
        self._ws = websocket

    def write(self, data: bytes) -> int:
        """Send data over the WebSocket."""
        self._ws.send(data)
        return len(data)

    def flush(self) -> None:
        """No-op: WebSocket messages are sent immediately."""

    def close(self) -> None:
        """No-op: WebSocket lifecycle managed by WebSocketAdapter."""


class SocketAdapter(IoStreamAdapter):
    """Connect to a plushie renderer over TCP or Unix domain socket.

    Parses the address string to determine the transport:
    - ``":4567"``: TCP on localhost
    - ``"localhost:4567"`` or ``"127.0.0.1:4567"``: TCP
    - ``"[::1]:4567"``: TCP over IPv6
    - ``"/path/to/sock"`` or ``"path/to/sock"``: Unix domain socket

    Usage::

        from plushie.transport import SocketAdapter
        from plushie.connection import Connection

        adapter = SocketAdapter(":4567")
        conn = Connection.from_iostream(adapter)

        adapter = SocketAdapter("/tmp/plushie.sock")
        conn = Connection.from_iostream(adapter)
    """

    def __init__(
        self,
        address: str,
        *,
        on_event: Callable[[Any], None] | None = None,
    ) -> None:
        self._socket: socket.socket
        parsed = _parse_socket_address(address)
        if parsed[0] == "unix":
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.connect(parsed[1])
        else:
            self._socket = socket.create_connection(parsed[1])

        super().__init__(
            self._socket.makefile("rb"),
            self._socket.makefile("wb"),
            on_event=on_event,
        )

    def close(self) -> None:
        """Close the adapter and the underlying socket."""
        if self._closed:
            return
        super().close()
        with contextlib.suppress(OSError):
            self._socket.close()


def _parse_socket_address(
    address: str,
) -> tuple[Literal["unix"], str] | tuple[Literal["tcp"], tuple[str, int]]:
    """Parse a SocketAdapter address into an explicit Unix or TCP target."""
    if _is_windows_named_pipe_address(address):
        raise ValueError("Windows named pipe transport is not supported yet")

    if address.startswith("/"):
        return ("unix", address)

    if address.startswith("["):
        closing = address.find("]")
        if closing <= 1 or closing + 1 >= len(address) or address[closing + 1] != ":":
            raise ValueError(
                "invalid socket address, expected [IPv6]:PORT for IPv6 TCP addresses"
            )
        host = address[1:closing]
        port = _parse_socket_port(address[closing + 2 :])
        return ("tcp", (host, port))

    if ":" not in address:
        return ("unix", address)

    if address.startswith(":"):
        return ("tcp", ("127.0.0.1", _parse_socket_port(address[1:])))

    if address.count(":") > 1:
        raise ValueError(
            "invalid socket address, use [IPv6]:PORT for IPv6 TCP addresses"
        )

    host, port_str = address.split(":", 1)
    if not host:
        raise ValueError("invalid socket address, expected HOST:PORT or :PORT")
    return ("tcp", (host, _parse_socket_port(port_str)))


def _is_windows_named_pipe_address(address: str) -> bool:
    r"""Return True for Windows pipe paths like ``\\.\pipe\plushie``."""
    normalized = address.replace("\\", "/").lower()
    return normalized.startswith("//./pipe/")


def _parse_socket_port(port_str: str) -> int:
    """Parse and validate a TCP port number."""
    try:
        port = int(port_str)
    except ValueError as exc:
        raise ValueError(f"invalid socket port: {port_str!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid socket port: {port_str!r}")
    return port


__all__ = [
    "IoStreamAdapter",
    "ReadableStream",
    "SocketAdapter",
    "WebSocketAdapter",
    "WritableStream",
]
