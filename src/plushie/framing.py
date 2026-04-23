"""Wire framing for the plushie protocol.

Two framing modes:

- **MsgpackFraming**: 4-byte big-endian length prefix + MessagePack payload.
- **JsonFraming**: newline-delimited JSON (JSONL).

Both framings support ``encode`` (message -> bytes) and ``feed``
(accumulate incoming bytes, yield complete frames). The caller
picks the framing up front (via the ``format`` option on
``Connection.open`` / ``IoStreamAdapter``); framings do not sniff
the wire to detect the peer's format.

Binary fields (image data, pixel buffers) use base64 encoding in JSON
mode and native bytes in MessagePack mode.

Maximum message size: 64 MiB.
"""

from __future__ import annotations

import base64
import json
import math
import struct
from typing import Any

import msgpack

MAX_MESSAGE_SIZE: int = 64 * 1024 * 1024
"""Maximum wire message size in bytes (64 MiB)."""

_LENGTH_PREFIX = struct.Struct(">I")


class FramingError(Exception):
    """Raised when a framing violation is detected (e.g. oversized message)."""


class BufferOverflowError(FramingError):
    """Raised when a single wire frame exceeds the 64 MiB per-message cap.

    Subclasses :class:`FramingError` so existing handlers still match;
    callers who want to distinguish the overflow case can catch this
    class directly. The exception carries both the offending size and
    the configured cap for structured handling.

    Attributes:
        size: Size of the offending frame or payload in bytes.
        limit: Configured cap in bytes (64 MiB).
    """

    __slots__ = ("limit", "size")

    def __init__(self, *, size: int, limit: int) -> None:
        super().__init__(f"wire frame of {size} bytes exceeds {limit} byte limit")
        self.size = size
        self.limit = limit


# ---------------------------------------------------------------------------
# MsgpackFraming
# ---------------------------------------------------------------------------


class MsgpackFraming:
    """MessagePack framing: 4-byte big-endian length prefix + msgpack payload.

    Use ``encode`` to produce a framed bytes object ready for the wire.
    Use ``feed`` to accumulate incoming bytes and extract complete frames.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    @staticmethod
    def encode(msg: dict[str, Any]) -> bytes:
        """Encode a message dict as a length-prefixed msgpack frame.

        Binary values (``bytes`` / ``bytearray``) in the message are
        preserved as native msgpack binary type (no base64 encoding).

        Raises ``FramingError`` if the encoded payload exceeds 64 MiB.
        """
        normalized = _normalize_outbound_fields(msg, binary_mode="msgpack")
        payload: bytes = msgpack.packb(normalized, use_bin_type=True)  # type: ignore[assignment]
        if len(payload) > MAX_MESSAGE_SIZE:
            raise BufferOverflowError(size=len(payload), limit=MAX_MESSAGE_SIZE)
        return _LENGTH_PREFIX.pack(len(payload)) + payload

    def feed(self, data: bytes | bytearray) -> list[dict[str, Any]]:
        """Accumulate incoming bytes and return any complete decoded messages.

        Partial frames are buffered internally. Call repeatedly as data
        arrives from the wire.

        Raises ``FramingError`` if a frame header declares a size
        exceeding 64 MiB.
        """
        self._buffer.extend(data)
        messages: list[dict[str, Any]] = []
        while len(self._buffer) >= 4:
            (payload_len,) = _LENGTH_PREFIX.unpack_from(self._buffer, 0)
            if payload_len > MAX_MESSAGE_SIZE:
                raise BufferOverflowError(size=payload_len, limit=MAX_MESSAGE_SIZE)
            if len(self._buffer) < 4 + payload_len:
                break
            payload = bytes(self._buffer[4 : 4 + payload_len])
            del self._buffer[: 4 + payload_len]
            messages.append(msgpack.unpackb(payload, raw=False))
        return messages

    def reset(self) -> None:
        """Clear the internal buffer."""
        self._buffer.clear()


# ---------------------------------------------------------------------------
# JsonFraming
# ---------------------------------------------------------------------------


class JsonFraming:
    """JSON framing: newline-delimited JSON (JSONL).

    Binary values (``bytes`` / ``bytearray``) are base64-encoded
    during ``encode`` and decoded back during ``feed``.

    Use ``encode`` to produce a framed bytes object ready for the wire.
    Use ``feed`` to accumulate incoming bytes and extract complete frames.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    @staticmethod
    def encode(msg: dict[str, Any]) -> bytes:
        """Encode a message dict as a JSON line (UTF-8 + newline).

        Binary values (``bytes`` / ``bytearray``) found in the message
        are replaced with their base64-encoded string representation.
        Non-finite float values are normalized to ``null``.

        Raises ``FramingError`` if the encoded line exceeds 64 MiB.
        """
        normalized = _normalize_outbound_fields(msg, binary_mode="json")
        line = json.dumps(
            normalized,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        encoded = line.encode("utf-8") + b"\n"
        if len(encoded) > MAX_MESSAGE_SIZE:
            raise BufferOverflowError(size=len(encoded), limit=MAX_MESSAGE_SIZE)
        return encoded

    def feed(self, data: bytes | bytearray) -> list[dict[str, Any]]:
        """Accumulate incoming bytes and return any complete decoded messages.

        Lines are split on ``\\n``. Partial lines are buffered.

        Raises ``FramingError`` if a complete line exceeds 64 MiB.
        """
        self._buffer.extend(data)
        messages: list[dict[str, Any]] = []
        while True:
            idx = self._buffer.find(b"\n")
            if idx < 0:
                break
            line_bytes = bytes(self._buffer[:idx])
            del self._buffer[: idx + 1]
            if len(line_bytes) > MAX_MESSAGE_SIZE:
                raise BufferOverflowError(size=len(line_bytes), limit=MAX_MESSAGE_SIZE)
            if not line_bytes:
                continue
            messages.append(json.loads(line_bytes))
        # Guard the partial tail so an unterminated line cannot grow
        # the internal buffer unboundedly across successive feeds.
        if len(self._buffer) > MAX_MESSAGE_SIZE:
            raise BufferOverflowError(size=len(self._buffer), limit=MAX_MESSAGE_SIZE)
        return messages

    def reset(self) -> None:
        """Clear the internal buffer."""
        self._buffer.clear()


# ---------------------------------------------------------------------------
# Outbound normalization helpers
# ---------------------------------------------------------------------------


def _normalize_outbound_fields(obj: Any, *, binary_mode: str) -> Any:
    """Normalize outbound wire values for JSONL and MessagePack.

    Binary values keep their existing wire contract:
    - JSON uses base64 strings
    - MsgPack uses native bytes

    Non-finite floats are normalized to ``None`` so both formats emit
    `null` / `nil` instead of NaN or Infinity.
    """
    if isinstance(obj, bool | int | str) or obj is None:
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (bytes, bytearray)):
        data = bytes(obj)
        if binary_mode == "json":
            return base64.b64encode(data).decode("ascii")
        return data
    if isinstance(obj, dict):
        return {
            k: _normalize_outbound_fields(v, binary_mode=binary_mode)
            for k, v in obj.items()
        }
    if isinstance(obj, list | tuple):
        return [_normalize_outbound_fields(v, binary_mode=binary_mode) for v in obj]
    return obj


def encode_binary_for_json(data: bytes | bytearray) -> str:
    """Encode binary data as a base64 string for JSON wire transport.

    Standard base64 alphabet, no padding stripped.

    Args:
        data: Raw binary data.

    Returns:
        Base64-encoded string.
    """
    return base64.b64encode(data).decode("ascii")


def decode_binary_from_json(value: str) -> bytes:
    """Decode a base64 string from JSON wire transport back to bytes.

    Args:
        value: Base64-encoded string.

    Returns:
        Decoded binary data.
    """
    return base64.b64decode(value)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "MAX_MESSAGE_SIZE",
    "BufferOverflowError",
    "FramingError",
    "JsonFraming",
    "MsgpackFraming",
    "decode_binary_from_json",
    "encode_binary_for_json",
]
