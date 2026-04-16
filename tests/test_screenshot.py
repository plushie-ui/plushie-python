"""Tests for Screenshot golden-file assertions."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from plushie.testing.screenshot import Screenshot


class TestScreenshotFromResponse:
    def test_basic_response(self) -> None:
        msg = {"name": "test", "hash": "abc123", "data": "base64data"}
        s = Screenshot.from_response(msg)
        assert s.name == "test"
        assert s.hash == "abc123"
        assert s.data == "base64data"

    def test_with_backend(self) -> None:
        msg = {"name": "test", "hash": "abc"}
        s = Screenshot.from_response(msg, backend="headless")
        assert s.backend == "headless"

    def test_missing_fields_default(self) -> None:
        s = Screenshot.from_response({})
        assert s.name == ""
        assert s.hash == ""


class TestScreenshotAssertMatch:
    def test_empty_hash_passes(self) -> None:
        s = Screenshot(name="test", hash="")
        s.assert_match("/nonexistent/dir")

    def test_creates_golden_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            s = Screenshot(name="test", hash="abc123")
            s.assert_match(tmp)
            golden = Path(tmp) / "test.sha256"
            assert golden.exists()
            assert golden.read_text() == "abc123"

    def test_matching_hash_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            golden = Path(tmp) / "test.sha256"
            golden.write_text("abc123")
            s = Screenshot(name="test", hash="abc123")
            s.assert_match(tmp)

    def test_mismatching_hash_raises(self) -> None:
        import pytest

        with tempfile.TemporaryDirectory() as tmp:
            golden = Path(tmp) / "test.sha256"
            golden.write_text("abc123")
            s = Screenshot(name="test", hash="def456")
            with pytest.raises(AssertionError, match=r"Screenshot mismatch"):
                s.assert_match(tmp)

    def test_update_env_var_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            golden = Path(tmp) / "test.sha256"
            golden.write_text("old")
            os.environ["PLUSHIE_UPDATE_SCREENSHOTS"] = "1"
            try:
                s = Screenshot(name="test", hash="new")
                s.assert_match(tmp)
                assert golden.read_text() == "new"
            finally:
                del os.environ["PLUSHIE_UPDATE_SCREENSHOTS"]

    def test_backend_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            s = Screenshot(name="test", hash="abc", backend="headless")
            s.assert_match(tmp)
            assert (Path(tmp) / "test.headless.sha256").exists()


class TestScreenshotSavePng:
    def test_save_bytes(self) -> None:
        import base64

        with tempfile.TemporaryDirectory() as tmp:
            data = base64.b64encode(b"\x89PNG fake data").decode()
            s = Screenshot(name="test", hash="abc", data=data)
            path = Path(tmp) / "test.png"
            s.save_png(path)
            assert path.exists()

    def test_save_no_data_raises(self) -> None:
        import pytest

        s = Screenshot(name="test", hash="abc", data=None)
        with pytest.raises(ValueError, match=r"no pixel data"):
            s.save_png("/tmp/test.png")
