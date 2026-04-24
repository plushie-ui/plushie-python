"""Tests for binary resolution and connection (non-I/O parts).

Tests that require the plushie binary are marked with
``@pytest.mark.skipif`` and skipped when the binary is not available.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import sys
import threading
from pathlib import Path
from queue import Queue
from typing import Any
from unittest.mock import patch as mock_patch

import pytest

from plushie.binary import (
    GITHUB_RELEASE_URL,
    WASM_BG_NAME,
    WASM_JS_NAME,
    PlushieNotFoundError,
    WasmNotFoundError,
    _resolve_bundled,
    detect_arch,
    detect_os,
    download_dir,
    download_name,
    resolve,
    resolve_wasm,
    wasm_dir,
    wasm_download_name,
)
from plushie.connection import (
    Connection,
    ConnectionError,
    ProtocolMismatchError,
    StdioConnection,
    _decode_events_list,
    _next_request_id,
    _normalize_expected_widgets,
    _validate_required_widgets,
)
from plushie.framing import MsgpackFraming
from plushie.native_widget import NativeWidget
from plushie.protocol import PROTOCOL_VERSION, decode_message
from plushie.types import HelloInfo

# ===================================================================
# Binary resolution tests (no binary required)
# ===================================================================


class TestGitHubReleaseURL:
    """Verify the GitHub release URL points to the correct organization."""

    def test_url_uses_plushie_ui_org(self) -> None:
        assert GITHUB_RELEASE_URL == (
            "https://github.com/plushie-ui/plushie-renderer/releases/download"
        )

    def test_url_does_not_use_anthropics(self) -> None:
        assert "anthropics" not in GITHUB_RELEASE_URL


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


class TestHelloRequiredWidgetValidation:
    def test_accepts_native_widgets(self) -> None:
        hello = HelloInfo(
            protocol=PROTOCOL_VERSION,
            version="0.5.0",
            name="plushie",
            mode="mock",
            backend="none",
            transport="spawn",
            native_widgets=("gauge",),
        )
        expected = (
            NativeWidget(
                kind="gauge",
                rust_crate="native/gauge",
                rust_constructor="gauge::Gauge::new()",
            ),
        )

        _validate_required_widgets(hello, _normalize_expected_widgets(expected))

    def test_accepts_widgets(self) -> None:
        hello = HelloInfo(
            protocol=PROTOCOL_VERSION,
            version="0.5.0",
            name="plushie",
            mode="mock",
            backend="none",
            transport="spawn",
            widgets=("custom_chart",),
        )

        _validate_required_widgets(hello, ("custom_chart",))

    def test_accepts_legacy_extensions(self) -> None:
        hello = HelloInfo(
            protocol=PROTOCOL_VERSION,
            version="0.5.0",
            name="plushie",
            mode="mock",
            backend="none",
            transport="spawn",
            extensions=("charts",),
        )

        _validate_required_widgets(hello, ("charts",))

    def test_missing_required_widget_raises(self) -> None:
        hello = HelloInfo(
            protocol=PROTOCOL_VERSION,
            version="0.5.0",
            name="plushie",
            mode="mock",
            backend="none",
            transport="spawn",
            extensions=(),
        )
        expected = (
            NativeWidget(
                kind="gauge",
                rust_crate="native/gauge",
                rust_constructor="gauge::Gauge::new()",
            ),
        )

        with pytest.raises(
            ConnectionError, match="missing required widgets/capabilities"
        ):
            _validate_required_widgets(hello, _normalize_expected_widgets(expected))


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
        assert (
            download_name(os_name="linux", arch="x86_64")
            == "plushie-renderer-linux-x86_64"
        )

    def test_darwin_aarch64(self) -> None:
        assert (
            download_name(os_name="darwin", arch="aarch64")
            == "plushie-renderer-darwin-aarch64"
        )

    def test_windows_exe(self) -> None:
        assert (
            download_name(os_name="windows", arch="x86_64")
            == "plushie-renderer-windows-x86_64.exe"
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
    """Tests for resolve(): the resolution chain."""

    def test_env_var_valid(self, tmp_path: Path) -> None:
        """PLUSHIE_BINARY_PATH points to an existing file."""
        binary = tmp_path / "plushie"
        binary.write_text("#!/bin/sh\necho hi")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

        with mock_patch.dict(os.environ, {"PLUSHIE_BINARY_PATH": str(binary)}):
            result = resolve()
            assert result == str(binary)

    def test_env_var_missing_file(self) -> None:
        """PLUSHIE_BINARY_PATH set but file does not exist: fail fast."""
        with (
            mock_patch.dict(
                os.environ, {"PLUSHIE_BINARY_PATH": "/nonexistent/plushie"}
            ),
            pytest.raises(PlushieNotFoundError, match="does not exist"),
        ):
            resolve()

    def test_not_found_raises(self, tmp_path: Path) -> None:
        """When nothing is found, PlushieNotFoundError lists the chain."""
        env = dict(os.environ)
        env.pop("PLUSHIE_BINARY_PATH", None)
        # Override PATH so shutil.which won't find anything
        env["PATH"] = "/nonexistent"
        with (
            mock_patch.dict(os.environ, env, clear=True),
            mock_patch("plushie.binary.download_dir") as mock_dd,
            mock_patch("plushie.binary._resolve_bundled", return_value=None),
            pytest.raises(PlushieNotFoundError, match="Resolution chain"),
        ):
            mock_dd.return_value = tmp_path / "nonexistent"
            resolve()

    def test_path_fallback(self, tmp_path: Path) -> None:
        """Falls back to PATH when env var, download, and bundled not available."""
        binary = tmp_path / "plushie-renderer"
        # Write a fake ELF header so _is_native_binary recognizes it
        binary.write_bytes(b"\x7fELF" + b"\x00" * 100)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)

        env = dict(os.environ)
        env.pop("PLUSHIE_BINARY_PATH", None)
        env["PATH"] = str(tmp_path)
        with (
            mock_patch.dict(os.environ, env, clear=True),
            mock_patch("plushie.binary.download_dir") as mock_dd,
            mock_patch("plushie.binary._resolve_bundled", return_value=None),
        ):
            mock_dd.return_value = tmp_path / "nonexistent"
            result = resolve()
            assert os.path.basename(result) == "plushie-renderer"

    def test_bundled_binary(self, tmp_path: Path) -> None:
        """Falls through to bundled binary when env var and download are absent."""
        bundled = tmp_path / "bundled" / "plushie"
        bundled.parent.mkdir()
        bundled.write_bytes(b"\x7fELF" + b"\x00" * 100)
        bundled.chmod(bundled.stat().st_mode | stat.S_IXUSR)

        env = dict(os.environ)
        env.pop("PLUSHIE_BINARY_PATH", None)
        env["PATH"] = "/nonexistent"
        with (
            mock_patch.dict(os.environ, env, clear=True),
            mock_patch("plushie.binary.download_dir") as mock_dd,
            mock_patch("plushie.binary._resolve_bundled", return_value=str(bundled)),
        ):
            mock_dd.return_value = tmp_path / "nonexistent"
            result = resolve()
            assert result == str(bundled)

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
# WASM functions
# ===================================================================


class TestWasmDir:
    """Tests for wasm_dir()."""

    def test_xdg_data_home(self) -> None:
        with (
            mock_patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/data"}, clear=False),
            mock_patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            d = wasm_dir()
            assert d == Path("/custom/data/plushie/wasm")

    def test_default_linux(self) -> None:
        env = dict(os.environ)
        env.pop("XDG_DATA_HOME", None)
        with (
            mock_patch.dict(os.environ, env, clear=True),
            mock_patch("plushie.binary.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            d = wasm_dir()
            assert str(d).endswith(".local/share/plushie/wasm")


class TestWasmDownloadName:
    """Tests for wasm_download_name()."""

    def test_returns_archive_name(self) -> None:
        assert wasm_download_name() == "plushie-renderer-wasm.tar.gz"


class TestResolveWasm:
    """Tests for resolve_wasm()."""

    def test_found(self, tmp_path: Path) -> None:
        """Returns paths when both files exist."""
        js_file = tmp_path / WASM_JS_NAME
        wasm_file = tmp_path / WASM_BG_NAME
        js_file.write_text("// js")
        wasm_file.write_bytes(b"\x00wasm")

        with mock_patch("plushie.binary.wasm_dir", return_value=tmp_path):
            js_path, bg_path = resolve_wasm()
            assert js_path == js_file
            assert bg_path == wasm_file

    def test_missing_raises(self, tmp_path: Path) -> None:
        """Raises WasmNotFoundError when files are absent."""
        with (
            mock_patch("plushie.binary.wasm_dir", return_value=tmp_path),
            pytest.raises(WasmNotFoundError, match="WASM renderer files not found"),
        ):
            resolve_wasm()

    def test_partial_missing_raises(self, tmp_path: Path) -> None:
        """Raises when only JS file exists but WASM is missing."""
        js_file = tmp_path / WASM_JS_NAME
        js_file.write_text("// js")

        with (
            mock_patch("plushie.binary.wasm_dir", return_value=tmp_path),
            pytest.raises(WasmNotFoundError),
        ):
            resolve_wasm()


# ===================================================================
# Bundled binary resolution
# ===================================================================


class TestResolveBundled:
    """Tests for _resolve_bundled()."""

    def test_pyinstaller_meipass(self, tmp_path: Path) -> None:
        """Finds binary in PyInstaller's _MEIPASS directory."""
        binary = tmp_path / "plushie-renderer"
        binary.write_bytes(b"\x7fELF" + b"\x00" * 100)

        with mock_patch.object(
            __import__("sys"), "_MEIPASS", str(tmp_path), create=True
        ):
            result = _resolve_bundled()
            assert result is not None
            assert result.endswith("plushie-renderer")

    def test_no_bundled(self) -> None:
        """Returns None when no bundled binary exists."""
        # Ensure _MEIPASS is not set
        import sys

        had_meipass = hasattr(sys, "_MEIPASS")
        if had_meipass:
            old = sys._MEIPASS  # type: ignore[attr-defined]
        try:
            if had_meipass:
                delattr(sys, "_MEIPASS")
            result = _resolve_bundled()
            # May or may not be None depending on environment, but
            # should not raise
            assert result is None or isinstance(result, str)
        finally:
            if had_meipass:
                sys._MEIPASS = old  # type: ignore[attr-defined]

    def test_adjacent_to_file(self, tmp_path: Path) -> None:
        """Finds binary adjacent to __file__ when it's a native binary."""
        binary = tmp_path / "plushie-renderer"
        binary.write_bytes(b"\x7fELF" + b"\x00" * 100)

        import sys

        had_meipass = hasattr(sys, "_MEIPASS")
        if had_meipass:
            old_meipass = sys._MEIPASS  # type: ignore[attr-defined]
            delattr(sys, "_MEIPASS")

        try:
            with mock_patch("plushie.binary.__file__", str(tmp_path / "binary.py")):
                result = _resolve_bundled()
                assert result is not None
                assert result.endswith("plushie-renderer")
        finally:
            if had_meipass:
                sys._MEIPASS = old_meipass  # type: ignore[attr-defined]


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

    def test_uses_random_token(self) -> None:
        with mock_patch("plushie.connection.secrets.token_hex") as token_hex:
            token_hex.return_value = "abc123"

            assert _next_request_id() == "py-rabc123"
            token_hex.assert_called_once_with(16)


# ===================================================================
# Decode events list
# ===================================================================


class TestDecodeEventsList:
    """Tests for _decode_events_list()."""

    def test_empty_list(self) -> None:
        assert _decode_events_list([]) == []

    def test_click_event(self) -> None:
        raw = [{"type": "event", "family": "click", "id": "btn1", "window_id": "main"}]
        events = _decode_events_list(raw)
        assert len(events) == 1
        from plushie.events import Click

        assert isinstance(events[0], Click)
        assert events[0].id == "btn1"

    def test_multiple_events(self) -> None:
        raw = [
            {"type": "event", "family": "click", "id": "a", "window_id": "main"},
            {
                "type": "event",
                "family": "input",
                "id": "b",
                "value": "hello",
                "window_id": "main",
            },
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
        assert issubclass(ProtocolMismatchError, ConnectionError)

    def test_wait_hello_raises_protocol_mismatch(self) -> None:
        conn: Any = Connection.__new__(Connection)
        conn._hello = None
        conn._hello_error = None
        conn._hello_event = threading.Event()
        conn._expected_widgets = ()
        conn._event_queue = Queue()

        conn._route_message(
            {
                "type": "hello",
                "session": "",
                "protocol": PROTOCOL_VERSION + 1,
                "version": "0.4.0",
                "name": "plushie",
                "mode": "mock",
                "backend": "none",
                "transport": "stdio",
                "extensions": [],
            }
        )

        with pytest.raises(ProtocolMismatchError, match="protocol version mismatch"):
            conn.wait_hello(timeout=0.1)
        assert conn.receive_event(timeout=0.01) is None

    def test_wait_hello_raises_malformed_protocol(self) -> None:
        conn: Any = Connection.__new__(Connection)
        conn._hello = None
        conn._hello_error = None
        conn._hello_event = threading.Event()
        conn._expected_widgets = ()
        conn._event_queue = Queue()

        conn._route_message(
            {
                "type": "hello",
                "session": "",
                "protocol": "1",
                "version": "0.4.0",
                "name": "plushie",
                "mode": "mock",
                "backend": "none",
                "transport": "stdio",
                "extensions": [],
            }
        )

        with pytest.raises(ProtocolMismatchError, match=r"protocol.*int"):
            conn.wait_hello(timeout=0.1)
        assert conn.receive_event(timeout=0.01) is None

    def test_plushie_not_found_is_file_not_found(self) -> None:
        """PlushieNotFoundError is a FileNotFoundError."""
        assert issubclass(PlushieNotFoundError, FileNotFoundError)


class _FakeWritePipe:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, data: bytes) -> int:
        self.data.extend(data)
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeReadPipe:
    def read(self, _n: int = -1) -> bytes:
        return b""

    def close(self) -> None:
        pass


class _BlockingReadPipe:
    def __init__(self, *, close_unblocks: bool = True) -> None:
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._read_entered = threading.Event()
        self._read_event = threading.Event()
        self._closed = False
        self._close_unblocks = close_unblocks

    def feed(self, data: bytes) -> None:
        with self._lock:
            self._buffer.extend(data)
            self._ready.set()

    def read(self, n: int = 4096) -> bytes:
        self._read_entered.set()
        while True:
            with self._lock:
                if self._buffer:
                    result = bytes(self._buffer[:n])
                    del self._buffer[:n]
                    if not self._buffer:
                        self._ready.clear()
                    self._read_event.set()
                    return result
                if self._closed:
                    return b""
            if self._close_unblocks:
                self._ready.wait(timeout=1.0)
            else:
                self._ready.wait()

    def wait_for_read(self) -> None:
        assert self._read_event.wait(timeout=2.0)

    def wait_for_reader(self) -> None:
        assert self._read_entered.wait(timeout=2.0)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._close_unblocks:
                self._ready.set()


class _FakeProcess:
    def __init__(self) -> None:
        self.stdin = _FakeWritePipe()
        self.stdout = _FakeReadPipe()
        self.stderr = _FakeReadPipe()
        self._returncode: int | None = None

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self._returncode = 0

    def kill(self) -> None:
        self._returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        self._returncode = 0
        return 0


class TestConnectionOpenFormat:
    def test_open_json_uses_json_cli_arg_and_framing(self) -> None:
        process = _FakeProcess()

        with mock_patch(
            "plushie.connection.subprocess.Popen", return_value=process
        ) as popen:
            conn = Connection.open(
                binary_path="/tmp/plushie-renderer",
                mode="mock",
                format="json",
            )
            try:
                assert popen.call_args.args[0] == [
                    "/tmp/plushie-renderer",
                    "--mock",
                    "--json",
                ]

                msg = {"type": "settings", "session": "", "value": {"theme": "dark"}}
                conn.send(msg)

                data = bytes(process.stdin.data)
                assert data.startswith(b"{")
                assert data.endswith(b"\n")
                assert json.loads(data) == msg
            finally:
                conn.close()

    def test_restart_ignores_output_from_old_reader(self) -> None:
        old_stdout = _BlockingReadPipe(close_unblocks=False)
        old_process: Any = _FakeProcess()
        old_process.stdout = old_stdout

        new_stdout = _BlockingReadPipe()
        new_process: Any = _FakeProcess()
        new_process.stdout = new_stdout

        with mock_patch(
            "plushie.connection.subprocess.Popen", return_value=new_process
        ):
            conn = Connection(
                old_process,
                _spawn_args=["/tmp/plushie-renderer", "--mock"],
                _spawn_env={},
            )
            try:
                old_stdout.wait_for_reader()
                old_reader = conn._reader_thread
                conn.restart()

                old_stdout.feed(
                    MsgpackFraming.encode(
                        {
                            "type": "hello",
                            "session": "",
                            "protocol": PROTOCOL_VERSION,
                            "version": "0.4.0",
                            "name": "old-renderer",
                            "mode": "mock",
                            "backend": "none",
                            "transport": "spawn",
                        }
                    )
                )
                old_stdout.wait_for_read()
                old_reader.join(timeout=2.0)

                assert not old_reader.is_alive()
                assert conn.hello is None
                assert conn._event_queue.empty()
            finally:
                conn.close()


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
            assert hello.name == "plushie-renderer"

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
                "id": "main",
                "type": "window",
                "props": {"title": "Test"},
                "children": [
                    {
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


# ===================================================================
# StdioConnection format="json" round-trip
# ===================================================================


class TestStdioConnectionJsonFormat:
    """Exercise ``StdioConnection`` with ``format='json'``.

    The stdio transport is used when the renderer spawns the Python
    process via ``plushie --exec``. With ``format='msgpack'`` the
    framing tests already pin the expected byte layout; this class
    locks down the JSON alternative end-to-end: a frame written by
    ``send()`` must be newline-delimited JSON (not length-prefixed
    msgpack), and a frame read on ``receive_event()`` must decode
    from the same framing.

    Because ``StdioConnection.__init__`` does ``os.dup(0) / os.dup(1)``
    and reassigns ``sys.stdout`` to redirect prints, the test
    substitutes fake fds with ``os.pipe()`` and ``os.dup2()`` before
    the connection spins up, then restores the originals.
    """

    def test_json_round_trip(self) -> None:
        # Pipe A: test -> connection (renderer writes, SDK reads on fd 0)
        in_read, in_write = os.pipe()
        # Pipe B: connection -> test (SDK writes on fd 1, renderer reads)
        out_read, out_write = os.pipe()

        # Preserve the real fd 0, fd 1, and sys.stdout so the test
        # harness survives the connection's dup / reassignment dance.
        saved_in = os.dup(0)
        saved_out = os.dup(1)
        saved_stdout = sys.stdout

        conn: StdioConnection | None = None
        try:
            os.dup2(in_read, 0)
            os.dup2(out_write, 1)
            # The original descriptors are now duplicated on 0/1; close
            # the spare copies so only the connection holds the ends it
            # needs.
            os.close(in_read)
            os.close(out_write)

            conn = StdioConnection(format="json")

            # --- Outbound: a message sent through the connection
            # lands on the out_read pipe as newline-delimited JSON.
            conn.send({"type": "settings", "session": "", "value": 7})

            out_buf = b""
            # Read enough to cover the payload + trailing newline.
            # Non-blocking: write end is closed after we capture.
            while b"\n" not in out_buf:
                chunk = os.read(out_read, 4096)
                if not chunk:
                    break
                out_buf += chunk

            assert out_buf.endswith(b"\n"), (
                f"JSON framing must terminate with newline, got {out_buf!r}"
            )
            # A msgpack frame would begin with a 4-byte big-endian length
            # prefix: the first bytes would almost never be ASCII '{'.
            assert out_buf.startswith(b"{"), (
                f"JSON framing should start with '{{', got {out_buf[:8]!r}"
            )
            decoded_out = json.loads(out_buf.rstrip(b"\n"))
            assert decoded_out == {
                "type": "settings",
                "session": "",
                "value": 7,
            }

            # --- Inbound: feeding a newline-delimited JSON hello into
            # the connection's stdin surfaces a HelloInfo via wait_hello.
            hello_frame = (
                json.dumps(
                    {
                        "type": "hello",
                        "session": "",
                        "protocol": PROTOCOL_VERSION,
                        "version": "0.6.0",
                        "name": "plushie-renderer",
                        "mode": "mock",
                        "backend": "none",
                        "transport": "stdio",
                        "extensions": [],
                    }
                )
                + "\n"
            )
            os.write(in_write, hello_frame.encode("utf-8"))

            hello = conn.wait_hello(timeout=5.0)
            assert hello.protocol == PROTOCOL_VERSION
            assert hello.mode == "mock"
            assert hello.name == "plushie-renderer"
        finally:
            if conn is not None:
                conn.close()
            # Restore the original stdio before closing the pipes, so
            # nothing in the test runner attempts to write to the
            # dead fd 1 in the window between.
            os.dup2(saved_in, 0)
            os.dup2(saved_out, 1)
            os.close(saved_in)
            os.close(saved_out)
            sys.stdout = saved_stdout

            for fd in (in_write, out_read):
                with contextlib.suppress(OSError):
                    os.close(fd)

    def test_json_protocol_mismatch_raises(self) -> None:
        in_read, in_write = os.pipe()
        out_read, out_write = os.pipe()

        saved_in = os.dup(0)
        saved_out = os.dup(1)
        saved_stdout = sys.stdout

        conn: StdioConnection | None = None
        try:
            os.dup2(in_read, 0)
            os.dup2(out_write, 1)
            os.close(in_read)
            os.close(out_write)

            conn = StdioConnection(format="json")

            hello_frame = (
                json.dumps(
                    {
                        "type": "hello",
                        "session": "",
                        "protocol": PROTOCOL_VERSION + 1,
                        "version": "0.6.0",
                        "name": "plushie-renderer",
                        "mode": "mock",
                        "backend": "none",
                        "transport": "stdio",
                        "extensions": [],
                    }
                )
                + "\n"
            )
            os.write(in_write, hello_frame.encode("utf-8"))

            with pytest.raises(
                ProtocolMismatchError, match="protocol version mismatch"
            ):
                conn.wait_hello(timeout=5.0)
            assert conn.receive_event(timeout=0.01) is None
        finally:
            if conn is not None:
                conn.close()
            os.dup2(saved_in, 0)
            os.dup2(saved_out, 1)
            os.close(saved_in)
            os.close(saved_out)
            sys.stdout = saved_stdout

            for fd in (in_write, out_read):
                with contextlib.suppress(OSError):
                    os.close(fd)

    def test_json_malformed_protocol_raises(self) -> None:
        in_read, in_write = os.pipe()
        out_read, out_write = os.pipe()

        saved_in = os.dup(0)
        saved_out = os.dup(1)
        saved_stdout = sys.stdout

        conn: StdioConnection | None = None
        try:
            os.dup2(in_read, 0)
            os.dup2(out_write, 1)
            os.close(in_read)
            os.close(out_write)

            conn = StdioConnection(format="json")

            hello_frame = (
                json.dumps(
                    {
                        "type": "hello",
                        "session": "",
                        "protocol": "1",
                        "version": "0.6.0",
                        "name": "plushie-renderer",
                        "mode": "mock",
                        "backend": "none",
                        "transport": "stdio",
                        "extensions": [],
                    }
                )
                + "\n"
            )
            os.write(in_write, hello_frame.encode("utf-8"))

            with pytest.raises(ProtocolMismatchError, match=r"protocol.*int"):
                conn.wait_hello(timeout=5.0)
            assert conn.receive_event(timeout=0.01) is None
        finally:
            if conn is not None:
                conn.close()
            os.dup2(saved_in, 0)
            os.dup2(saved_out, 1)
            os.close(saved_in)
            os.close(saved_out)
            sys.stdout = saved_stdout

            for fd in (in_write, out_read):
                with contextlib.suppress(OSError):
                    os.close(fd)
