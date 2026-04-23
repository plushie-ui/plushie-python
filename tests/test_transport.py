"""Tests for plushie.transport: iostream adapter tests.

Tests the IoStreamAdapter with in-memory pipe-like streams, verifying
frame encoding/decoding, event routing, and lifecycle management.
"""

from __future__ import annotations

import logging
import socket
import struct
import threading
import time
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any
from unittest.mock import MagicMock

import msgpack
import pytest

from plushie.connection import (
    Connection,
    ProtocolMismatchError,
)
from plushie.connection import (
    ConnectionError as PlushieConnectionError,
)
from plushie.events import Input
from plushie.protocol import PROTOCOL_VERSION
from plushie.transport import IoStreamAdapter, SocketAdapter, WebSocketAdapter
from plushie.types import HelloInfo


def _encode_msg(msg: dict[str, Any]) -> bytes:
    """Encode a message as a length-prefixed msgpack frame."""
    payload: bytes = msgpack.packb(msg, use_bin_type=True)  # type: ignore[assignment]
    return struct.pack(">I", len(payload)) + payload


def _decode_msg(data: bytes) -> dict[str, Any]:
    """Decode one length-prefixed msgpack frame."""
    (payload_len,) = struct.unpack(">I", data[:4])
    payload = data[4:]
    assert len(payload) == payload_len
    return msgpack.unpackb(payload, raw=False)  # type: ignore[no-any-return]


def _wait_for_written(writer: _PipeWriter, index: int) -> dict[str, Any]:
    deadline = time.monotonic() + 2.0
    while len(writer.chunks) <= index:
        if time.monotonic() > deadline:
            pytest.fail("timed out waiting for iostream request")
        time.sleep(0.01)
    return _decode_msg(writer.chunks[index])


class _PipeReader:
    """In-memory readable stream backed by a threading event for blocking reads."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._data_ready = threading.Event()
        self._closed = False

    def feed(self, data: bytes) -> None:
        """Push data into the pipe (simulates the remote end writing)."""
        with self._lock:
            self._buffer.extend(data)
            self._data_ready.set()

    def read(self, n: int = 4096) -> bytes:
        """Blocking read: waits for data or close."""
        while True:
            with self._lock:
                if self._buffer:
                    result = bytes(self._buffer[:n])
                    del self._buffer[:n]
                    if not self._buffer:
                        self._data_ready.clear()
                    return result
                if self._closed:
                    return b""
            self._data_ready.wait(timeout=1.0)

    def close(self) -> None:
        self._closed = True
        self._data_ready.set()


class _PipeWriter:
    """In-memory writable stream that captures written data."""

    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.chunks.append(data)
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


def _call_with_response(
    reader: _PipeReader,
    writer: _PipeWriter,
    index: int,
    call: Any,
    response: Any,
) -> tuple[dict[str, Any], Any]:
    results: Queue[Any] = Queue()
    errors: Queue[BaseException] = Queue()

    def run() -> None:
        try:
            results.put(call())
        except BaseException as exc:
            errors.put(exc)

    thread = threading.Thread(target=run)
    thread.start()
    request = _wait_for_written(writer, index)
    reader.feed(_encode_msg(response(request)))
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    if not errors.empty():
        raise errors.get()
    return request, results.get_nowait()


def _valid_hello_msg() -> dict[str, Any]:
    return {
        "type": "hello",
        "name": "plushie",
        "version": "0.4.0",
        "protocol": PROTOCOL_VERSION,
        "mode": "mock",
        "backend": "mock",
        "transport": "iostream",
    }


def _wait_until(assertion: Callable[[], None]) -> None:
    deadline = time.monotonic() + 2.0
    while True:
        try:
            assertion()
            return
        except AssertionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.01)


class _GenericAdapter:
    def __init__(self) -> None:
        self.hello = HelloInfo(
            name="plushie",
            version="0.4.0",
            protocol=PROTOCOL_VERSION,
            mode="mock",
            backend="mock",
            transport="generic",
        )
        self.is_closed = False
        self.sent: list[dict[str, Any]] = []
        self.events: Queue[Any] = Queue()

    def wait_hello(self, timeout: float = 10.0) -> HelloInfo:
        return self.hello

    def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)

    def receive_event(self, timeout: float | None = None) -> Any:
        try:
            return self.events.get(timeout=timeout)
        except Empty:
            return None

    def close(self) -> None:
        self.is_closed = True


class TestIoStreamAdapter:
    """IoStreamAdapter with in-memory pipes."""

    def test_receives_hello(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)

        hello_msg = {
            "type": "hello",
            "name": "plushie",
            "version": "0.4.0",
            "protocol": 1,
            "mode": "mock",
            "backend": "mock",
            "transport": "iostream",
        }
        reader.feed(_encode_msg(hello_msg))

        hello = adapter.wait_hello(timeout=2.0)
        assert hello.name == "plushie"
        assert hello.version == "0.4.0"
        adapter.close()

    def test_send_encodes_frame(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)

        adapter.send({"type": "settings", "data": {}})
        assert len(writer.chunks) == 1

        # Verify the written data is a valid msgpack frame
        data = writer.chunks[0]
        assert len(data) > 4
        (payload_len,) = struct.unpack(">I", data[:4])
        payload = data[4:]
        assert len(payload) == payload_len
        decoded = msgpack.unpackb(payload, raw=False)
        assert decoded["type"] == "settings"

        adapter.close()

    def test_receive_event(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)

        event_msg = {
            "type": "event",
            "family": "click",
            "id": "btn",
            "window_id": "main",
        }
        reader.feed(_encode_msg(event_msg))

        event = adapter.receive_event(timeout=2.0)
        assert event is not None
        adapter.close()

    def test_on_event_callback(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        received: list[Any] = []

        adapter = IoStreamAdapter(reader, writer, on_event=received.append)

        event_msg = {"type": "event", "kind": "click", "id": "btn"}
        reader.feed(_encode_msg(event_msg))

        # Wait briefly for the reader thread to process
        time.sleep(0.1)
        assert len(received) >= 1
        adapter.close()

    def test_close_is_idempotent(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)
        adapter.close()
        adapter.close()  # should not raise
        assert adapter.is_closed

    def test_send_after_close_raises(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)
        adapter.close()
        with pytest.raises(ConnectionError, match="closed"):
            adapter.send({"type": "test"})

    def test_context_manager(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        with IoStreamAdapter(reader, writer) as adapter:
            assert not adapter.is_closed
        assert adapter.is_closed

    def test_hello_timeout(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)
        with pytest.raises(TimeoutError, match="hello"):
            adapter.wait_hello(timeout=0.1)
        adapter.close()

    def test_protocol_mismatch_raises(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)

        hello_msg = {
            "type": "hello",
            "name": "plushie",
            "version": "0.4.0",
            "protocol": PROTOCOL_VERSION + 1,
            "mode": "mock",
            "backend": "mock",
            "transport": "iostream",
        }
        reader.feed(_encode_msg(hello_msg))

        with pytest.raises(ProtocolMismatchError, match="protocol version mismatch"):
            adapter.wait_hello(timeout=2.0)
        assert adapter.receive_event(timeout=0.01) is None
        adapter.close()

    def test_malformed_protocol_raises(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)

        hello_msg = {
            "type": "hello",
            "name": "plushie",
            "version": "0.4.0",
            "protocol": "1",
            "mode": "mock",
            "backend": "mock",
            "transport": "iostream",
        }
        reader.feed(_encode_msg(hello_msg))

        with pytest.raises(ProtocolMismatchError, match=r"protocol.*int"):
            adapter.wait_hello(timeout=2.0)
        assert adapter.receive_event(timeout=0.01) is None
        adapter.close()


class TestWebSocketAdapter:
    """WebSocketAdapter with a mock WebSocket."""

    def test_send_and_receive(self) -> None:
        mock_ws = MagicMock()

        # Set up recv to return a hello message then block
        hello_msg = _encode_msg(
            {
                "type": "hello",
                "name": "plushie",
                "version": "0.4.0",
                "protocol": 1,
                "mode": "wasm",
                "backend": "wasm",
                "transport": "websocket",
            }
        )

        call_count = 0

        def fake_recv() -> bytes:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return hello_msg
            # Block on subsequent calls
            time.sleep(10)
            return b""

        mock_ws.recv = fake_recv
        mock_ws.send = MagicMock()

        adapter = WebSocketAdapter(mock_ws)
        hello = adapter.wait_hello(timeout=2.0)
        assert hello.name == "plushie"
        assert hello.backend == "wasm"

        adapter.send({"type": "settings", "data": {}})
        assert mock_ws.send.called

        adapter.close()

    def test_receives_concatenated_frames_from_one_payload(self) -> None:
        closed = threading.Event()

        class MockWebSocket:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload
                self._recv_count = 0
                self.send = MagicMock()

            def recv(self) -> bytes:
                self._recv_count += 1
                if self._recv_count == 1:
                    return self._payload
                closed.wait()
                return b""

            def close(self) -> None:
                closed.set()

        hello_msg = _encode_msg(
            {
                "type": "hello",
                "name": "plushie",
                "version": "0.4.0",
                "protocol": PROTOCOL_VERSION,
                "mode": "wasm",
                "backend": "wasm",
                "transport": "websocket",
            }
        )
        event_msg = _encode_msg(
            {
                "type": "event",
                "family": "input",
                "id": "message",
                "value": "x" * 5000,
                "window_id": "main",
            }
        )
        adapter = WebSocketAdapter(MockWebSocket(hello_msg + event_msg))
        event: Any = None
        try:
            assert adapter.wait_hello(timeout=2.0).transport == "websocket"
            assert isinstance(adapter.receive_event(timeout=0.2), HelloInfo)
            event = adapter.receive_event(timeout=0.2)
        finally:
            adapter.close()
        assert isinstance(event, Input)
        assert event.id == "message"
        assert len(event.value) == 5000

    def test_recv_exception_is_logged(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_ws = MagicMock()
        mock_ws.recv.side_effect = ConnectionError("websocket dropped")

        def logged_recv_failure() -> None:
            assert "websocket recv failed" in caplog.text

        with caplog.at_level(logging.ERROR, logger="plushie"):
            adapter = WebSocketAdapter(mock_ws)
            _wait_until(logged_recv_failure)

        adapter.close()
        assert "websocket dropped" in caplog.text


class TestConnectionFromIostream:
    """Connection.from_iostream() integration."""

    def test_creates_connection_like_object(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)
        conn = Connection.from_iostream(adapter, session="test")
        assert conn.session == "test"
        assert conn.is_alive
        conn.close()
        assert not conn.is_alive

    def test_send_settings_through_adapter(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)
        conn = Connection.from_iostream(adapter)
        conn.send_settings({"theme": "dark"})
        assert len(writer.chunks) == 1
        conn.close()

    def test_wait_hello_raises_protocol_mismatch(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)
        conn = Connection.from_iostream(adapter)

        reader.feed(
            _encode_msg(
                {
                    "type": "hello",
                    "name": "plushie",
                    "version": "0.4.0",
                    "protocol": PROTOCOL_VERSION + 1,
                    "mode": "mock",
                    "backend": "mock",
                    "transport": "iostream",
                }
            )
        )

        with pytest.raises(ProtocolMismatchError, match="protocol version mismatch"):
            conn.wait_hello(timeout=2.0)
        assert conn.receive_event(timeout=0.01) is None
        conn.close()

    def test_wrapped_adapter_preserves_on_event_callback(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        received: list[Any] = []
        adapter = IoStreamAdapter(reader, writer, on_event=received.append)
        conn = Connection.from_iostream(adapter)

        reader.feed(
            _encode_msg(
                {
                    "type": "event",
                    "family": "click",
                    "id": "btn",
                    "window_id": "main",
                }
            )
        )

        def received_event() -> None:
            assert len(received) == 1

        _wait_until(received_event)
        assert received[0] is not None
        conn.close()

    def test_wrap_after_valid_hello_uses_adapter_state(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)

        reader.feed(_encode_msg(_valid_hello_msg()))
        adapter.wait_hello(timeout=2.0)

        conn = Connection.from_iostream(adapter)
        assert conn.wait_hello(timeout=0.01).name == "plushie"
        assert conn.hello is adapter.hello
        conn.close()

    def test_wrap_after_protocol_mismatch_raises_original_error(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)

        hello_msg = _valid_hello_msg()
        hello_msg["protocol"] = PROTOCOL_VERSION + 1
        reader.feed(_encode_msg(hello_msg))

        with pytest.raises(ProtocolMismatchError, match="protocol version mismatch"):
            adapter.wait_hello(timeout=2.0)

        conn = Connection.from_iostream(adapter)
        with pytest.raises(ProtocolMismatchError, match="protocol version mismatch"):
            conn.wait_hello(timeout=0.01)
        conn.close()

    def test_generic_adapter_request_response_fails_fast(self) -> None:
        adapter = _GenericAdapter()
        conn = Connection.from_iostream(adapter)

        assert conn.wait_hello(timeout=0.01).transport == "generic"
        conn.send_settings({"theme": "dark"})
        assert adapter.sent[0]["type"] == "settings"

        with pytest.raises(PlushieConnectionError, match="set_message_handler"):
            conn.query_tree(timeout=0.01)
        assert len(adapter.sent) == 1

        with pytest.raises(PlushieConnectionError, match="set_message_handler"):
            conn.interact("click", "#btn", timeout=0.01)
        assert len(adapter.sent) == 1
        conn.close()

    def test_request_response_methods_route_through_iostream(self) -> None:
        reader = _PipeReader()
        writer = _PipeWriter()
        adapter = IoStreamAdapter(reader, writer)
        conn = Connection.from_iostream(adapter, session="test")
        request_index = 0

        conn._send_request(
            {"type": "query", "session": "test", "id": "manual", "target": "tree"},
            "manual",
        )
        request = _wait_for_written(writer, request_index)
        request_index += 1
        assert request["id"] == "manual"
        reader.feed(
            _encode_msg(
                {
                    "type": "query_response",
                    "id": "manual",
                    "target": "tree",
                    "data": {"id": "root"},
                }
            )
        )
        assert conn._wait_response("manual", timeout=2.0)["data"] == {"id": "root"}

        request, result = _call_with_response(
            reader,
            writer,
            request_index,
            lambda: conn.query_find("#btn", timeout=2.0),
            lambda req: {
                "type": "query_response",
                "id": req["id"],
                "target": "find",
                "data": {"id": "btn"},
            },
        )
        request_index += 1
        assert request["target"] == "find"
        assert result == {"id": "btn"}

        request, result = _call_with_response(
            reader,
            writer,
            request_index,
            lambda: conn.query_tree(timeout=2.0),
            lambda req: {
                "type": "query_response",
                "id": req["id"],
                "target": "tree",
                "data": {"id": "root"},
            },
        )
        request_index += 1
        assert request["target"] == "tree"
        assert result == {"id": "root"}

        request, result = _call_with_response(
            reader,
            writer,
            request_index,
            lambda: conn.interact("click", "#btn", timeout=2.0),
            lambda req: {
                "type": "interact_response",
                "id": req["id"],
                "events": [],
            },
        )
        request_index += 1
        assert request["type"] == "interact"
        assert result == []

        stepped_events: Queue[Any] = Queue()
        stepped_results: Queue[Any] = Queue()
        stepped_errors: Queue[BaseException] = Queue()

        def on_step(events: list[Any]) -> dict[str, Any]:
            stepped_events.put(events)
            return {"id": "root", "type": "column", "children": []}

        def run_stepped_interact() -> None:
            try:
                stepped_results.put(
                    conn.interact("click", "#btn", on_step=on_step, timeout=2.0)
                )
            except BaseException as exc:
                stepped_errors.put(exc)

        step_thread = threading.Thread(target=run_stepped_interact)
        step_thread.start()
        request = _wait_for_written(writer, request_index)
        reader.feed(
            _encode_msg(
                {
                    "type": "interact_step",
                    "id": request["id"],
                    "events": [
                        {
                            "type": "event",
                            "family": "click",
                            "id": "btn",
                            "window_id": "main",
                        }
                    ],
                }
            )
        )
        snapshot = _wait_for_written(writer, request_index + 1)
        reader.feed(
            _encode_msg(
                {
                    "type": "interact_response",
                    "id": request["id"],
                    "events": [],
                }
            )
        )
        step_thread.join(timeout=2.0)
        request_index += 2
        assert not step_thread.is_alive()
        if not stepped_errors.empty():
            raise stepped_errors.get()
        assert request["type"] == "interact"
        assert snapshot["type"] == "snapshot"
        assert stepped_results.get_nowait() == stepped_events.get_nowait()

        request, result = _call_with_response(
            reader,
            writer,
            request_index,
            lambda: conn.request_effect(
                "effect-1", "clipboard_read", {"format": "text"}, timeout=2.0
            ),
            lambda req: {
                "type": "effect_response",
                "id": req["id"],
                "status": "ok",
                "result": {"text": "copied"},
            },
        )
        request_index += 1
        assert request["type"] == "effect"
        assert result["result"] == {"text": "copied"}

        request, result = _call_with_response(
            reader,
            writer,
            request_index,
            lambda: conn.take_screenshot("main", timeout=2.0),
            lambda req: {
                "type": "screenshot_response",
                "id": req["id"],
                "name": req["name"],
                "path": "/tmp/main.png",
            },
        )
        request_index += 1
        assert request["type"] == "screenshot"
        assert result["path"] == "/tmp/main.png"

        request, result = _call_with_response(
            reader,
            writer,
            request_index,
            lambda: conn.compute_tree_hash("main", timeout=2.0),
            lambda req: {
                "type": "tree_hash_response",
                "id": req["id"],
                "name": req["name"],
                "hash": "abc123",
            },
        )
        request_index += 1
        assert request["type"] == "tree_hash"
        assert result["hash"] == "abc123"

        request, result = _call_with_response(
            reader,
            writer,
            request_index,
            lambda: conn.reset_session(timeout=2.0),
            lambda req: {"type": "reset_response", "id": req["id"], "ok": True},
        )
        assert request["type"] == "reset"
        assert result["ok"] is True
        conn.close()


class TestSocketAdapterInit:
    """SocketAdapter address parsing and connection (no live server)."""

    @staticmethod
    def _connected_socket() -> MagicMock:
        reader = MagicMock()
        reader.read.return_value = b""
        reader.close.return_value = None

        writer = MagicMock()
        writer.write.return_value = 0
        writer.flush.return_value = None
        writer.close.return_value = None

        sock = MagicMock()
        sock.makefile.side_effect = [reader, writer]
        sock.close.return_value = None
        return sock

    def test_tcp_connection_refused(self) -> None:
        with pytest.raises(ConnectionRefusedError):
            SocketAdapter(":1")

    def test_tcp_host_port_refused(self) -> None:
        with pytest.raises(ConnectionRefusedError):
            SocketAdapter("127.0.0.1:1")

    def test_unix_connection_refused(self) -> None:
        with pytest.raises((ConnectionRefusedError, FileNotFoundError)):
            SocketAdapter("/tmp/_plushie_nonexistent_test.sock")

    def test_tcp_localhost_shorthand_uses_ipv4_loopback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_socket = self._connected_socket()
        create_connection = MagicMock(return_value=fake_socket)
        monkeypatch.setattr(socket, "create_connection", create_connection)

        adapter = SocketAdapter(":4567")

        create_connection.assert_called_once_with(("127.0.0.1", 4567))
        adapter.close()

    def test_tcp_host_port_uses_create_connection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_socket = self._connected_socket()
        create_connection = MagicMock(return_value=fake_socket)
        monkeypatch.setattr(socket, "create_connection", create_connection)

        adapter = SocketAdapter("example.test:4567")

        create_connection.assert_called_once_with(("example.test", 4567))
        adapter.close()

    def test_tcp_ipv6_bracketed_strips_brackets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_socket = self._connected_socket()
        create_connection = MagicMock(return_value=fake_socket)
        monkeypatch.setattr(socket, "create_connection", create_connection)

        adapter = SocketAdapter("[::1]:4567")

        create_connection.assert_called_once_with(("::1", 4567))
        adapter.close()

    def test_unix_relative_path_uses_unix_socket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_socket = self._connected_socket()
        socket_ctor = MagicMock(return_value=fake_socket)
        monkeypatch.setattr(socket, "socket", socket_ctor)

        adapter = SocketAdapter("tmp/plushie.sock")

        socket_ctor.assert_called_once_with(socket.AF_UNIX, socket.SOCK_STREAM)
        fake_socket.connect.assert_called_once_with("tmp/plushie.sock")
        adapter.close()

    @pytest.mark.parametrize(
        "address",
        [
            "[::1]",
            "[::1",
            "::1:4567",
            "2001:db8::1:4567",
            "[::1]:abc",
            "host:0",
        ],
    )
    def test_invalid_socket_address_raises_value_error(self, address: str) -> None:
        with pytest.raises(ValueError, match="invalid socket"):
            SocketAdapter(address)
