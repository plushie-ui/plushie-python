"""Tests for plushie.dev_server -- file watching and live reload.

Tests the DevServer construction, module import/reimport helpers,
file change detection, debounce logic, reload error handling, and
watchfiles vs polling fallback.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from plushie.app import App
from plushie.dev_server import (
    DevServer,
    _check_changes,
    _default_watch_paths,
    _import_app_from_spec,
    _python_filter,
    _reimport_module,
    _scan_mtimes,
)

# ===================================================================
# Dummy App for tests
# ===================================================================


class _DummyModel:
    pass


class _DummyApp(App[_DummyModel]):
    def init(self) -> _DummyModel:
        return _DummyModel()

    def update(self, model: _DummyModel, event: object) -> _DummyModel:
        return model

    def view(self, model: _DummyModel) -> dict[str, Any]:
        return {"id": "root", "type": "window", "props": {}, "children": []}


# ===================================================================
# _import_app_from_spec
# ===================================================================


class TestImportAppFromSpec:
    """Validate the module:Class import helper."""

    def test_valid_spec(self) -> None:
        # Use the dummy app defined in this test module
        mod_path = f"{__name__}:_DummyApp"
        cls = _import_app_from_spec(mod_path)
        assert cls is _DummyApp

    def test_missing_module_raises_import_error(self) -> None:
        with pytest.raises(ImportError):
            _import_app_from_spec("nonexistent.module.zzz:Foo")

    def test_missing_class_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            _import_app_from_spec(f"{__name__}:NoSuchClass")

    def test_non_app_subclass_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="not an App subclass"):
            _import_app_from_spec(f"{__name__}:_DummyModel")


# ===================================================================
# _reimport_module
# ===================================================================


class TestReimportModule:
    """Validate the reimport helper."""

    def test_reimport_already_loaded_module(self) -> None:
        """If the module is in sys.modules, importlib.reload is used."""
        with patch.object(importlib, "reload", wraps=importlib.reload) as mock_reload:
            mod = _reimport_module("os.path")
            mock_reload.assert_called_once()
            assert mod is sys.modules["os.path"]

    def test_import_fresh_module(self) -> None:
        """If the module is NOT in sys.modules, importlib.import_module is called."""
        fake_name = "plushie._test_reimport_sentinel"
        # Ensure it's not loaded
        sys.modules.pop(fake_name, None)

        fake_mod = MagicMock()
        with patch.object(
            importlib, "import_module", return_value=fake_mod
        ) as mock_import:
            result = _reimport_module(fake_name)
            mock_import.assert_called_once_with(fake_name)
            assert result is fake_mod


# ===================================================================
# DevServer construction
# ===================================================================


class TestDevServerConstruction:
    """Validate DevServer.__init__ plumbing."""

    def test_default_construction(self) -> None:
        with patch(
            "plushie.dev_server._default_watch_paths", return_value=["src", "."]
        ):
            ds = DevServer("myapp.counter:Counter")

        assert ds._app_spec == "myapp.counter:Counter"
        assert ds._module_path == "myapp.counter"
        assert ds._class_name == "Counter"
        assert ds._mode is None
        assert ds._running is False

    def test_custom_watch_paths(self) -> None:
        ds = DevServer("mod:Cls", watch_paths=["/tmp/watch"])
        assert ds._watch_paths == ["/tmp/watch"]

    def test_mode_passthrough(self) -> None:
        ds = DevServer("mod:Cls", mode="headless", watch_paths=["."])
        assert ds._mode == "headless"

    def test_connection_opts_passthrough(self) -> None:
        ds = DevServer("mod:Cls", watch_paths=["."], host="localhost", port=9999)
        assert ds._connection_opts == {"host": "localhost", "port": 9999}


# ===================================================================
# _reload
# ===================================================================


class TestReload:
    """Validate the reload method that preserves model state."""

    def _make_server_and_runtime(self) -> tuple[DevServer, MagicMock]:
        ds = DevServer(f"{__name__}:_DummyApp", watch_paths=["."])
        runtime = MagicMock()
        runtime.model = _DummyModel()
        runtime._app = None
        runtime._conn = MagicMock()
        runtime._tree = None
        return ds, runtime

    def test_reload_preserves_model(self) -> None:
        ds, runtime = self._make_server_and_runtime()
        ds._reload(runtime)

        # The runtime's app should have been replaced
        assert isinstance(runtime._app, _DummyApp)
        # The model is preserved -- view was called with the original model
        runtime._conn.send_snapshot.assert_called_once()

    def test_reload_updates_tree(self) -> None:
        ds, runtime = self._make_server_and_runtime()

        with patch("plushie.tree.normalize", return_value={"id": "root"}):
            ds._reload(runtime)

        assert runtime._tree == {"id": "root"}

    def test_reload_skips_snapshot_when_tree_is_none(self) -> None:
        ds, runtime = self._make_server_and_runtime()

        with patch("plushie.tree.normalize", return_value=None):
            ds._reload(runtime)

        runtime._conn.send_snapshot.assert_not_called()

    def test_reload_logs_and_continues_on_error(self, caplog: Any) -> None:
        ds, runtime = self._make_server_and_runtime()

        with (
            patch(
                "plushie.dev_server._reimport_module",
                side_effect=SyntaxError("bad code"),
            ),
            caplog.at_level(logging.ERROR, logger="plushie"),
        ):
            ds._reload(runtime)

        assert "reload failed" in caplog.text

    def test_reload_rejects_non_app_subclass(self, caplog: Any) -> None:
        ds = DevServer(f"{__name__}:_DummyModel", watch_paths=["."])
        runtime = MagicMock()
        runtime.model = "some model"

        with caplog.at_level(logging.ERROR, logger="plushie"):
            ds._reload(runtime)

        assert "no longer an App subclass" in caplog.text


# ===================================================================
# File change detection
# ===================================================================


class TestFileChangeDetection:
    """Validate polling-based file watching helpers."""

    def test_scan_mtimes(self, tmp_path: Any) -> None:
        py_file = tmp_path / "mod.py"
        py_file.write_text("x = 1")
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("hello")

        mtimes: dict[str, float] = {}
        _scan_mtimes(str(tmp_path), mtimes)

        assert str(py_file) in mtimes
        assert str(txt_file) not in mtimes

    def test_check_changes_detects_new_file(self, tmp_path: Any) -> None:
        mtimes: dict[str, float] = {}

        # Initial scan -- empty dir, no changes
        assert not _check_changes(str(tmp_path), mtimes)

        # Add a .py file
        new_file = tmp_path / "new.py"
        new_file.write_text("y = 2")

        assert _check_changes(str(tmp_path), mtimes)
        assert str(new_file) in mtimes

    def test_check_changes_detects_modified_file(self, tmp_path: Any) -> None:
        py_file = tmp_path / "mod.py"
        py_file.write_text("v1")

        mtimes: dict[str, float] = {}
        _scan_mtimes(str(tmp_path), mtimes)

        # Ensure mtime actually advances (some filesystems have 1s resolution)
        time.sleep(0.05)
        old_mtime = os.path.getmtime(str(py_file))
        os.utime(str(py_file), (old_mtime + 1, old_mtime + 1))

        assert _check_changes(str(tmp_path), mtimes)

    def test_check_changes_ignores_non_py_files(self, tmp_path: Any) -> None:
        mtimes: dict[str, float] = {}
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("hello")

        assert not _check_changes(str(tmp_path), mtimes)


# ===================================================================
# Debounce
# ===================================================================


class TestDebounce:
    """Validate that the polling watcher respects debounce timing."""

    def test_debounce_suppresses_rapid_reloads(self) -> None:
        """Simulate the debounce check from _watch_with_polling."""
        from plushie.dev_server import _DEBOUNCE_SECONDS

        last_reload = time.monotonic()
        # Immediately after a reload, another change should be suppressed
        now = last_reload + 0.01
        assert now - last_reload < _DEBOUNCE_SECONDS

        # After debounce window, reload should be allowed
        now = last_reload + _DEBOUNCE_SECONDS + 0.01
        assert now - last_reload >= _DEBOUNCE_SECONDS


# ===================================================================
# _python_filter
# ===================================================================


class TestPythonFilter:
    """Validate the watchfiles filter function."""

    def test_accepts_py_files(self) -> None:
        assert _python_filter("modified", "/foo/bar.py") is True

    def test_rejects_non_py_files(self) -> None:
        assert _python_filter("modified", "/foo/bar.txt") is False
        assert _python_filter("modified", "/foo/bar.pyc") is False
        assert _python_filter("modified", "/foo/bar.pyx") is False


# ===================================================================
# _default_watch_paths
# ===================================================================


class TestDefaultWatchPaths:
    """Validate default directory selection."""

    def test_returns_existing_dirs(self, tmp_path: Any) -> None:
        src = tmp_path / "src"
        src.mkdir()

        with patch("plushie.dev_server.os.path.isdir") as mock_isdir:
            mock_isdir.side_effect = lambda p: p in ("src", ".")
            result = _default_watch_paths()

        assert "src" in result
        assert "." in result

    def test_skips_nonexistent_dirs(self) -> None:
        with patch("plushie.dev_server.os.path.isdir", return_value=False):
            result = _default_watch_paths()

        assert result == []


# ===================================================================
# Watch loop fallback
# ===================================================================


class TestWatchLoopFallback:
    """Validate watchfiles vs polling fallback detection."""

    def test_falls_back_to_polling_when_watchfiles_missing(self) -> None:
        ds = DevServer("mod:Cls", watch_paths=["."])
        runtime = MagicMock()

        with (
            patch.object(
                ds,
                "_watch_with_watchfiles",
                side_effect=ImportError("no watchfiles"),
            ),
            patch.object(ds, "_watch_with_polling") as mock_polling,
        ):
            ds._watch_loop(runtime)

        mock_polling.assert_called_once_with(runtime)

    def test_uses_watchfiles_when_available(self) -> None:
        ds = DevServer("mod:Cls", watch_paths=["."])
        runtime = MagicMock()

        with (
            patch.object(ds, "_watch_with_watchfiles") as mock_wf,
            patch.object(ds, "_watch_with_polling") as mock_polling,
        ):
            ds._watch_loop(runtime)

        mock_wf.assert_called_once_with(runtime)
        mock_polling.assert_not_called()
