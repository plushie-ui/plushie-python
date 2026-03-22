"""Tests for plushie.transport -- iostream adapter tests.

Tests the IoStreamAdapter with in-memory pipe-like streams, verifying
frame encoding/decoding, event routing, and lifecycle management.
"""

from __future__ import annotations

import struct
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import msgpack
import pytest

from plushie.connection import Connection
from plushie.transport import IoStreamAdapter, WebSocketAdapter


def _encode_msg(msg: dict[str, Any]) -> bytes:
    """Encode a message as a length-prefixed msgpack frame."""
    payload: bytes = msgpack.packb(msg, use_bin_type=True)  # type: ignore[assignment]
    return struct.pack(">I", len(payload)) + payload


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
        """Blocking read -- waits for data or close."""
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

        event_msg = {"type": "event", "kind": "click", "id": "btn"}
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
