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

    import socket
    from plushie.transport import IoStreamAdapter

    sock = socket.create_connection(("127.0.0.1", 4567))
    adapter = IoStreamAdapter(sock.makefile("rb"), sock.makefile("wb"))
    conn = Connection.from_iostream(adapter)
"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any, Protocol, runtime_checkable

from plushie.framing import MsgpackFraming
from plushie.protocol import decode_message
from plushie.types import HelloInfo

logger = logging.getLogger("plushie")


@runtime_checkable
class ReadableStream(Protocol):
    """Any object that supports blocking reads of raw bytes."""

    def read(self, n: int = ..., /) -> bytes: ...


@runtime_checkable
class WritableStream(Protocol):
    """Any object that supports writing raw bytes."""

    def write(self, data: bytes, /) -> int | None: ...

    def flush(self) -> None: ...


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
        on_event: Callable[[Any], None] | None = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._framing = MsgpackFraming()
        self._send_lock = threading.Lock()
        self._event_queue: Queue[Any] = Queue()
        self._on_event = on_event
        self._hello: HelloInfo | None = None
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
        data = MsgpackFraming.encode(msg)
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
        msg_type = raw_msg.get("type", "")

        if msg_type == "hello":
            decoded = decode_message(raw_msg)
            if isinstance(decoded, HelloInfo):
                self._hello = decoded
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
            conn = Connection.from_iostream(adapter)

    The WebSocket object must support:
    - ``recv()`` -> bytes (blocking receive of a complete message)
    - ``send(data: bytes)`` -> None (send a complete message)
    - Optionally ``close()`` for cleanup.
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
        while len(self._buffer) < n:
            try:
                data = self._ws.recv()
            except Exception:
                return bytes(0)
            if isinstance(data, str):
                data = data.encode("utf-8")
            if not data:
                break
            self._buffer.extend(data)
            # WebSocket messages are complete frames, return what we have
            break
        result = bytes(self._buffer[:n])
        del self._buffer[:n]
        return result

    def close(self) -> None:
        """No-op -- WebSocket lifecycle managed by WebSocketAdapter."""


class _WebSocketWriter:
    """Adapts a WebSocket's send() into the WritableStream interface."""

    def __init__(self, websocket: Any) -> None:
        self._ws = websocket

    def write(self, data: bytes) -> int:
        """Send data over the WebSocket."""
        self._ws.send(data)
        return len(data)

    def flush(self) -> None:
        """No-op -- WebSocket messages are sent immediately."""

    def close(self) -> None:
        """No-op -- WebSocket lifecycle managed by WebSocketAdapter."""


__all__ = [
    "IoStreamAdapter",
    "ReadableStream",
    "WebSocketAdapter",
    "WritableStream",
]
