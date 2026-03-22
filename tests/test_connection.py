"""Tests for binary resolution and connection (non-I/O parts).

Tests that require the plushie binary are marked with
``@pytest.mark.skipif`` and skipped when the binary is not available.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch as mock_patch

import pytest

from plushie.binary import (
    PlushieNotFoundError,
    detect_arch,
    detect_os,
    download_dir,
    download_name,
    resolve,
)
from plushie.connection import (
    Connection,
    ConnectionError,
    _decode_events_list,
    _next_request_id,
)
from plushie.protocol import PROTOCOL_VERSION, decode_message
from plushie.types import HelloInfo

# ===================================================================
# Binary resolution tests (no binary required)
# ===================================================================


class TestDetectOS:
    """Tests for detect_os()."""

    def test_linux(self) -> None:
        with mock_patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "linux"
            assert detect_os() == "linux"

    def test_darwin(self) -> None:
        with mock_patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert detect_os() == "darwin"

    def test_windows(self) -> None:
        with mock_patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "win32"
            assert detect_os() == "windows"

    def test_cygwin(self) -> None:
        with mock_patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "cygwin"
            assert detect_os() == "windows"

    def test_unsupported(self) -> None:
        with mock_patch("plushie.binary.sys") as mock_sys:
            mock_sys.platform = "freebsd12"
            with pytest.raises(RuntimeError, match="unsupported platform"):
                detect_os()


class TestDetectArch:
    """Tests for detect_arch()."""

    def test_x86_64(self) -> None:
        with mock_patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "x86_64"
            assert detect_arch() == "x86_64"

    def test_amd64(self) -> None:
        with mock_patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "AMD64"
            assert detect_arch() == "x86_64"

    def test_aarch64(self) -> None:
        with mock_patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "aarch64"
            assert detect_arch() == "aarch64"

    def test_arm64(self) -> None:
        with mock_patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "arm64"
            assert detect_arch() == "aarch64"

    def test_unsupported(self) -> None:
        with mock_patch("plushie.binary.platform") as mock_plat:
            mock_plat.machine.return_value = "armv7l"
            with pytest.raises(RuntimeError, match="unsupported architecture"):
                detect_arch()


class TestDownloadName:
    """Tests for download_name()."""

    def test_linux_x86_64(self) -> None:
        assert download_name(os_name="linux", arch="x86_64") == "plushie-linux-x86_64"

    def test_darwin_aarch64(self) -> None:
        assert (
            download_name(os_name="darwin", arch="aarch64") == "plushie-darwin-aarch64"
        )

    def test_windows_exe(self) -> None:
        assert (
            download_name(os_name="windows", arch="x86_64")
            == "plushie-windows-x86_64.exe"
        )


class TestDownloadDir:
    """Tests for download_dir()."""

    def test_xdg_data_home(self) -> None:
        with (
            mock_patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/data"}, clear=False),
            mock_patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            d = download_dir()
            assert d == Path("/custom/data/plushie/bin")

    def test_default_linux(self) -> None:
        env = dict(os.environ)
        env.pop("XDG_DATA_HOME", None)
        with (
            mock_patch.dict(os.environ, env, clear=True),
            mock_patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            d = download_dir()
            assert str(d).endswith(".local/share/plushie/bin")


class TestResolve:
    """Tests for resolve() -- the resolution chain."""

    def test_env_var_valid(self, tmp_path: Path) -> None:
        """PLUSHIE_BINARY_PATH points to an existing file."""
        binary = tmp_path / "plushie"
        binary.write_text("#!/bin/sh\necho hi")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

        with mock_patch.dict(os.environ, {"PLUSHIE_BINARY_PATH": str(binary)}):
            result = resolve()
            assert result == str(binary)

    def test_env_var_missing_file(self) -> None:
        """PLUSHIE_BINARY_PATH set but file does not exist -- fail fast."""
        with (
            mock_patch.dict(
                os.environ, {"PLUSHIE_BINARY_PATH": "/nonexistent/plushie"}
            ),
            pytest.raises(PlushieNotFoundError, match="does not exist"),
        ):
            resolve()

    def test_not_found_raises(self) -> None:
        """When nothing is found, PlushieNotFoundError lists the chain."""
        env = dict(os.environ)
        env.pop("PLUSHIE_BINARY_PATH", None)
        # Override PATH so shutil.which won't find anything
        env["PATH"] = "/nonexistent"
        with (
            mock_patch.dict(os.environ, env, clear=True),
            pytest.raises(PlushieNotFoundError, match="Resolution chain"),
        ):
            resolve()

    def test_path_fallback(self, tmp_path: Path) -> None:
        """Falls back to PATH when env var and download not available."""
        binary = tmp_path / "plushie"
        # Write a fake ELF header so _is_native_binary recognizes it
        binary.write_bytes(b"\x7fELF" + b"\x00" * 100)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

        env = dict(os.environ)
        env.pop("PLUSHIE_BINARY_PATH", None)
        env["PATH"] = str(tmp_path)
        with (
            mock_patch.dict(os.environ, env, clear=True),
            mock_patch("plushie.binary.download_dir") as mock_dd,
        ):
            mock_dd.return_value = tmp_path / "nonexistent"
            result = resolve()
            assert os.path.basename(result) == "plushie"

    def test_downloaded_binary(self, tmp_path: Path) -> None:
        """Falls through to downloaded binary when env var is not set."""
        # Create a fake downloaded binary in a mocked download dir
        bin_dir = tmp_path / "downloads"
        bin_dir.mkdir()

        current_os = detect_os()
        current_arch = detect_arch()
        name = download_name(os_name=current_os, arch=current_arch)
        binary = bin_dir / name
        binary.write_text("#!/bin/sh\necho hi")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

        env = dict(os.environ)
        env.pop("PLUSHIE_BINARY_PATH", None)
        env["PATH"] = "/nonexistent"
        with (
            mock_patch.dict(os.environ, env, clear=True),
            mock_patch("plushie.binary.download_dir") as mock_dd,
        ):
            mock_dd.return_value = bin_dir
            result = resolve()
            assert result == str(binary)


# ===================================================================
# Request ID generation
# ===================================================================


class TestRequestId:
    """Tests for _next_request_id()."""

    def test_unique_ids(self) -> None:
        ids = {_next_request_id() for _ in range(100)}
        assert len(ids) == 100

    def test_prefix(self) -> None:
        rid = _next_request_id()
        assert rid.startswith("py-")


# ===================================================================
# Decode events list
# ===================================================================


class TestDecodeEventsList:
    """Tests for _decode_events_list()."""

    def test_empty_list(self) -> None:
        assert _decode_events_list([]) == []

    def test_click_event(self) -> None:
        raw = [{"type": "event", "family": "click", "id": "btn1"}]
        events = _decode_events_list(raw)
        assert len(events) == 1
        from plushie.events import Click

        assert isinstance(events[0], Click)
        assert events[0].id == "btn1"

    def test_multiple_events(self) -> None:
        raw = [
            {"type": "event", "family": "click", "id": "a"},
            {"type": "event", "family": "input", "id": "b", "value": "hello"},
        ]
        events = _decode_events_list(raw)
        assert len(events) == 2


# ===================================================================
# HelloInfo parsing via decode_message
# ===================================================================


class TestHelloParsing:
    """Tests for hello message decoding."""

    def test_hello_parsed(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol": 1,
            "version": "0.4.0",
            "name": "plushie",
            "mode": "mock",
            "backend": "none",
            "transport": "stdio",
            "extensions": [],
        }
        result = decode_message(raw)
        assert isinstance(result, HelloInfo)
        assert result.protocol == 1
        assert result.mode == "mock"

    def test_hello_with_extensions(self) -> None:
        raw = {
            "type": "hello",
            "session": "",
            "protocol": 1,
            "version": "0.4.0",
            "name": "plushie",
            "mode": "headless",
            "backend": "tiny-skia",
            "transport": "stdio",
            "extensions": ["charts", "editor"],
        }
        result = decode_message(raw)
        assert isinstance(result, HelloInfo)
        assert result.extensions == ("charts", "editor")


# ===================================================================
# Connection class (unit-level, no subprocess)
# ===================================================================


class TestConnectionAttributes:
    """Test Connection properties without starting a subprocess."""

    def test_connection_error_hierarchy(self) -> None:
        """ConnectionError is a subclass of Exception."""
        assert issubclass(ConnectionError, Exception)

    def test_protocol_mismatch_error(self) -> None:
        """ProtocolMismatchError is a ConnectionError."""
        from plushie.connection import ProtocolMismatchError

        assert issubclass(ProtocolMismatchError, ConnectionError)

    def test_plushie_not_found_is_file_not_found(self) -> None:
        """PlushieNotFoundError is a FileNotFoundError."""
        assert issubclass(PlushieNotFoundError, FileNotFoundError)


# ===================================================================
# Binary-requiring tests (skipped when binary not available)
# ===================================================================

try:
    from plushie.binary import resolve

    _resolved = resolve()
    _binary_available = True
except Exception:
    _binary_available = False


@pytest.mark.skipif(
    not _binary_available,
    reason="plushie binary not available",
)
class TestConnectionWithBinary:
    """Integration tests requiring the plushie binary."""

    def test_open_and_hello(self) -> None:
        """Open a mock connection and verify the hello handshake."""
        with Connection.open(mode="mock") as conn:
            conn.send_settings({})
            hello = conn.wait_hello(timeout=5.0)
            assert hello.protocol == PROTOCOL_VERSION
            assert hello.mode == "mock"
            assert hello.name == "plushie"

    def test_snapshot_and_query(self) -> None:
        """Send a snapshot and query for a widget."""
        with Connection.open(mode="mock") as conn:
            conn.send_settings({})
            conn.wait_hello(timeout=5.0)
            tree = {
                "id": "root",
                "type": "column",
                "props": {},
                "children": [
                    {
                        "id": "btn1",
                        "type": "button",
                        "props": {"label": "Click"},
                        "children": [],
                    }
                ],
            }
            conn.send_snapshot(tree)
            result = conn.query_find("#btn1", timeout=5.0)
            assert result is not None
            assert result["id"] == "btn1"

    def test_interact_mock(self) -> None:
        """Interact in mock mode returns synthetic events."""
        with Connection.open(mode="mock") as conn:
            conn.send_settings({})
            conn.wait_hello(timeout=5.0)
            tree = {
                "id": "root",
                "type": "column",
                "props": {},
                "children": [
                    {
                        "id": "btn1",
                        "type": "button",
                        "props": {"label": "Click"},
                        "children": [],
                    }
                ],
            }
            conn.send_snapshot(tree)
            events = conn.interact("click", "#btn1", timeout=5.0)
            assert len(events) > 0

    def test_context_manager(self) -> None:
        """Connection works as a context manager."""
        with Connection.open(mode="mock") as conn:
            conn.send_settings({})
            conn.wait_hello(timeout=5.0)
            assert conn.is_alive
        # After exit, process should be terminated
        assert not conn.is_alive

    def test_query_tree(self) -> None:
        """Query the full tree."""
        with Connection.open(mode="mock") as conn:
            conn.send_settings({})
            conn.wait_hello(timeout=5.0)
            tree = {
                "id": "root",
                "type": "column",
                "props": {},
                "children": [],
            }
            conn.send_snapshot(tree)
            result = conn.query_tree(timeout=5.0)
            assert result is not None
            assert result["id"] == "root"

    def test_reset_session(self) -> None:
        """Reset session returns a response."""
        with Connection.open(mode="mock") as conn:
            conn.send_settings({})
            conn.wait_hello(timeout=5.0)
            tree = {
                "id": "root",
                "type": "column",
                "props": {},
                "children": [],
            }
            conn.send_snapshot(tree)
            resp = conn.reset_session(timeout=5.0)
            assert resp is not None
            assert resp.get("type") == "reset_response"
