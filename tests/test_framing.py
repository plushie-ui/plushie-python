"""Tests for plushie.framing: wire framing encode/decode."""

from __future__ import annotations

import json
import struct

import msgpack
import pytest

from plushie.framing import (
    FramingError,
    JsonFraming,
    MsgpackFraming,
    decode_binary_from_json,
    detect_format,
    encode_binary_for_json,
)

# ===================================================================
# detect_format
# ===================================================================


class TestDetectFormat:
    def test_json_byte(self) -> None:
        assert detect_format(0x7B) == "json"

    def test_msgpack_byte_zero(self) -> None:
        assert detect_format(0x00) == "msgpack"

    def test_msgpack_byte_0x80(self) -> None:
        # 0x80 is msgpack fixmap
        assert detect_format(0x80) == "msgpack"

    def test_msgpack_byte_0xFF(self) -> None:
        assert detect_format(0xFF) == "msgpack"


# ===================================================================
# MsgpackFraming
# ===================================================================


class TestMsgpackFramingEncode:
    def test_round_trip_simple(self) -> None:
        msg = {"type": "settings", "session": ""}
        encoded = MsgpackFraming.encode(msg)
        # First 4 bytes are length prefix
        (payload_len,) = struct.unpack(">I", encoded[:4])
        payload = encoded[4:]
        assert len(payload) == payload_len
        decoded = msgpack.unpackb(payload, raw=False)
        assert decoded == msg

    def test_binary_data_preserved(self) -> None:
        raw_bytes = b"\x00\x01\x02\xff"
        msg = {"data": raw_bytes, "handle": "img"}
        encoded = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        results = framing.feed(encoded)
        assert len(results) == 1
        assert results[0]["data"] == raw_bytes

    def test_oversize_raises(self) -> None:
        # Craft a message that when packed exceeds 64 MiB
        huge = {"data": b"\x00" * (64 * 1024 * 1024 + 1)}
        with pytest.raises(FramingError, match="exceeds"):
            MsgpackFraming.encode(huge)


class TestMsgpackFramingFeed:
    def test_single_message(self) -> None:
        msg = {"type": "hello", "protocol": 1}
        encoded = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        results = framing.feed(encoded)
        assert len(results) == 1
        assert results[0] == msg

    def test_multiple_messages_at_once(self) -> None:
        msg1 = {"type": "event", "family": "click", "id": "a"}
        msg2 = {"type": "event", "family": "input", "id": "b"}
        data = MsgpackFraming.encode(msg1) + MsgpackFraming.encode(msg2)
        framing = MsgpackFraming()
        results = framing.feed(data)
        assert len(results) == 2
        assert results[0] == msg1
        assert results[1] == msg2

    def test_partial_header(self) -> None:
        msg = {"key": "val"}
        encoded = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        # Feed only 2 bytes of the 4-byte header
        results = framing.feed(encoded[:2])
        assert results == []
        # Feed the rest
        results = framing.feed(encoded[2:])
        assert len(results) == 1
        assert results[0] == msg

    def test_partial_payload(self) -> None:
        msg = {"hello": "world"}
        encoded = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        # Feed header + partial payload
        split = 4 + 2
        results = framing.feed(encoded[:split])
        assert results == []
        results = framing.feed(encoded[split:])
        assert len(results) == 1
        assert results[0] == msg

    def test_multiple_feeds(self) -> None:
        msgs = [{"n": i} for i in range(5)]
        framing = MsgpackFraming()
        all_encoded = b"".join(MsgpackFraming.encode(m) for m in msgs)
        # Feed one byte at a time
        collected: list[dict] = []
        for byte in all_encoded:
            collected.extend(framing.feed(bytes([byte])))
        assert len(collected) == 5
        for i, result in enumerate(collected):
            assert result == {"n": i}

    def test_oversize_frame_header_raises(self) -> None:
        # Forge a 4-byte header claiming a massive size
        header = struct.pack(">I", 64 * 1024 * 1024 + 1)
        framing = MsgpackFraming()
        with pytest.raises(FramingError, match="exceeds"):
            framing.feed(header)

    def test_reset(self) -> None:
        msg = {"x": 1}
        encoded = MsgpackFraming.encode(msg)
        framing = MsgpackFraming()
        framing.feed(encoded[:3])
        framing.reset()
        # After reset, should not produce any message from old partial data
        results = framing.feed(MsgpackFraming.encode({"y": 2}))
        assert len(results) == 1
        assert results[0] == {"y": 2}


# ===================================================================
# JsonFraming
# ===================================================================


class TestJsonFramingEncode:
    def test_round_trip_simple(self) -> None:
        msg = {"type": "settings", "session": ""}
        encoded = JsonFraming.encode(msg)
        assert encoded.endswith(b"\n")
        decoded = json.loads(encoded.rstrip(b"\n"))
        assert decoded == msg

    def test_binary_data_base64_encoded(self) -> None:
        raw_bytes = b"\x00\x01\x02\xff"
        msg = {"data": raw_bytes, "handle": "img"}
        encoded = JsonFraming.encode(msg)
        decoded = json.loads(encoded.rstrip(b"\n"))
        # Binary field should be base64 string
        assert isinstance(decoded["data"], str)
        assert decode_binary_from_json(decoded["data"]) == raw_bytes

    def test_nested_binary_data(self) -> None:
        raw = b"hello"
        msg = {"outer": {"inner": raw, "list": [raw, "text"]}}
        encoded = JsonFraming.encode(msg)
        decoded = json.loads(encoded.rstrip(b"\n"))
        assert decode_binary_from_json(decoded["outer"]["inner"]) == raw
        assert decode_binary_from_json(decoded["outer"]["list"][0]) == raw
        assert decoded["outer"]["list"][1] == "text"

    def test_unicode_preserved(self) -> None:
        msg = {"text": "Hello, 世界"}
        encoded = JsonFraming.encode(msg)
        decoded = json.loads(encoded)
        assert decoded["text"] == "Hello, 世界"


class TestJsonFramingFeed:
    def test_single_message(self) -> None:
        msg = {"type": "hello", "protocol": 1}
        encoded = JsonFraming.encode(msg)
        framing = JsonFraming()
        results = framing.feed(encoded)
        assert len(results) == 1
        assert results[0] == msg

    def test_multiple_messages(self) -> None:
        msg1 = {"type": "event", "family": "click"}
        msg2 = {"type": "event", "family": "input"}
        data = JsonFraming.encode(msg1) + JsonFraming.encode(msg2)
        framing = JsonFraming()
        results = framing.feed(data)
        assert len(results) == 2
        assert results[0] == msg1
        assert results[1] == msg2

    def test_partial_line(self) -> None:
        msg = {"key": "val"}
        encoded = JsonFraming.encode(msg)
        framing = JsonFraming()
        # Feed without trailing newline
        results = framing.feed(encoded[:-1])
        assert results == []
        # Feed the newline
        results = framing.feed(b"\n")
        assert len(results) == 1
        assert results[0] == msg

    def test_empty_lines_skipped(self) -> None:
        msg = {"x": 1}
        data = b"\n" + JsonFraming.encode(msg) + b"\n\n"
        framing = JsonFraming()
        results = framing.feed(data)
        assert len(results) == 1
        assert results[0] == msg

    def test_reset(self) -> None:
        framing = JsonFraming()
        framing.feed(b'{"partial":')
        framing.reset()
        results = framing.feed(JsonFraming.encode({"y": 2}))
        assert len(results) == 1
        assert results[0] == {"y": 2}


# ===================================================================
# Binary field helpers
# ===================================================================


class TestBinaryHelpers:
    def test_encode_decode_round_trip(self) -> None:
        data = b"\x00\x01\x02\x03\xff\xfe\xfd"
        encoded = encode_binary_for_json(data)
        assert isinstance(encoded, str)
        decoded = decode_binary_from_json(encoded)
        assert decoded == data

    def test_empty_bytes(self) -> None:
        encoded = encode_binary_for_json(b"")
        decoded = decode_binary_from_json(encoded)
        assert decoded == b""
