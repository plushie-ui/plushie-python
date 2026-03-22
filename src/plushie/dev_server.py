"""File watcher for live reload during development.

Watches source directories for ``.py`` file changes, reimports the app
module, reinstantiates the App class, calls ``view()`` with the
preserved model, and sends a full snapshot to the renderer.

Uses ``watchfiles`` (fast, Rust-backed) if available, falling back to
a simple polling-based watcher.

Usage::

    from plushie.dev_server import DevServer

    dev = DevServer("myapp.counter:Counter")
    dev.run()
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import os
import sys
import threading
import time
from typing import Any

from plushie.app import App

logger = logging.getLogger("plushie")

# Minimum time between reloads in seconds.
_DEBOUNCE_SECONDS: float = 0.3


def _import_app_from_spec(spec: str) -> type[App[Any]]:
    """Import an App class from a ``module:Class`` specifier.

    Args:
        spec: Dotted module path + class name separated by ``:``.

    Returns:
        The App subclass.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the class does not exist.
        TypeError: If the class is not an App subclass.
    """
    module_path, class_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, App)):
        raise TypeError(f"{spec!r} is not an App subclass")
    return cls


def _reimport_module(module_path: str) -> Any:
    """Force-reimport a module and return it.

    If the module is already loaded, ``importlib.reload`` is used.
    Otherwise, a fresh import is performed.

    Args:
        module_path: Dotted module path.

    Returns:
        The reloaded module object.
    """
    if module_path in sys.modules:
        return importlib.reload(sys.modules[module_path])
    return importlib.import_module(module_path)


class DevServer:
    """Development server with file watching and live reload.

    Spawns the renderer, runs the app, and watches for source changes.
    On change, the app module is reimported, a new App instance is
    created, ``view()`` is called with the preserved model, and a full
    snapshot is sent.

    Args:
        app_spec: App specifier in ``module:Class`` format.
        watch_paths: Directories to watch. Defaults to ``["src", "."]``.
        mode: Renderer mode (``None`` for windowed, ``"mock"``,
            ``"headless"``).
        **connection_opts: Extra keyword arguments forwarded to
            ``Connection.open()``.
    """

    def __init__(
        self,
        app_spec: str,
        *,
        watch_paths: list[str] | None = None,
        mode: str | None = None,
        **connection_opts: Any,
    ) -> None:
        self._app_spec = app_spec
        self._module_path, self._class_name = app_spec.rsplit(":", 1)
        self._watch_paths = watch_paths or _default_watch_paths()
        self._mode = mode
        self._connection_opts = connection_opts
        self._running = False

    def run(self) -> None:
        """Run the dev server (blocking).

        Starts the renderer connection, initialises the app, begins
        file watching, and blocks until interrupted or the renderer
        exits.
        """
        from plushie.connection import Connection
        from plushie.runtime import Runtime

        app_class = _import_app_from_spec(self._app_spec)
        app = app_class()

        conn = Connection.open(mode=self._mode, **self._connection_opts)
        runtime = Runtime(app, conn)

        self._running = True

        # Start the watcher thread
        watcher_thread = threading.Thread(
            target=self._watch_loop,
            args=(runtime,),
            name="plushie-dev-watcher",
            daemon=True,
        )
        watcher_thread.start()

        try:
            runtime.run()
        finally:
            self._running = False
            conn.close()

    def _reload(self, runtime: Any) -> None:
        """Attempt to reload the app module and send a fresh snapshot.

        Preserves the current model. On error, logs and continues.

        Args:
            runtime: The running ``Runtime`` instance.
        """
        from plushie.tree import normalize

        try:
            module = _reimport_module(self._module_path)
            cls = getattr(module, self._class_name)
            if not (isinstance(cls, type) and issubclass(cls, App)):
                logger.error("reload: %s is no longer an App subclass", self._app_spec)
                return

            new_app = cls()
            model = runtime.model

            # Update the runtime's app reference
            runtime._app = new_app

            # Re-render and send full snapshot
            raw_tree = new_app.view(model)
            tree = normalize(raw_tree)
            if tree is not None:
                runtime._conn.send_snapshot(tree)
                runtime._tree = tree

            logger.info("reloaded: %s", self._app_spec)
        except Exception:
            logger.exception("reload failed for %s", self._app_spec)

    def _watch_loop(self, runtime: Any) -> None:
        """Background thread that watches for file changes.

        Tries ``watchfiles`` first; falls back to polling.

        Args:
            runtime: The running ``Runtime`` instance.
        """
        try:
            self._watch_with_watchfiles(runtime)
        except ImportError:
            logger.debug("watchfiles not available, falling back to polling")
            self._watch_with_polling(runtime)

    def _watch_with_watchfiles(self, runtime: Any) -> None:
        """Watch for changes using the ``watchfiles`` library.

        Args:
            runtime: The running ``Runtime`` instance.
        """
        import watchfiles  # type: ignore[import-untyped]

        paths = [p for p in self._watch_paths if os.path.isdir(p)]
        if not paths:
            logger.warning("no valid watch paths found")
            return

        for changes in watchfiles.watch(
            *paths,
            watch_filter=_python_filter,
            debounce=int(_DEBOUNCE_SECONDS * 1000),
            stop_event=threading.Event(),  # never set -- runs until daemon exits
        ):
            if not self._running:
                break
            if changes:
                logger.debug("detected changes: %s", changes)
                self._reload(runtime)

    def _watch_with_polling(self, runtime: Any) -> None:
        """Watch for changes using filesystem polling.

        Scans watch paths every second for mtime changes on ``.py`` files.

        Args:
            runtime: The running ``Runtime`` instance.
        """
        mtimes: dict[str, float] = {}
        last_reload: float = 0.0

        # Initial scan
        for path in self._watch_paths:
            if os.path.isdir(path):
                _scan_mtimes(path, mtimes)

        while self._running:
            time.sleep(1.0)

            changed = False
            for path in self._watch_paths:
                if os.path.isdir(path) and _check_changes(path, mtimes):
                    changed = True

            if changed:
                now = time.monotonic()
                if now - last_reload >= _DEBOUNCE_SECONDS:
                    self._reload(runtime)
                    last_reload = now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_watch_paths() -> list[str]:
    """Return default directories to watch for source changes."""
    candidates = ["src", "lib", "."]
    return [p for p in candidates if os.path.isdir(p)]


def _python_filter(change: Any, path: str) -> bool:
    """Filter for watchfiles: only trigger on .py file changes.

    Args:
        change: The watchfiles change type.
        path: The file path that changed.

    Returns:
        ``True`` if the change should trigger a reload.
    """
    return path.endswith(".py")


def _scan_mtimes(directory: str, mtimes: dict[str, float]) -> None:
    """Scan a directory tree and record mtime for all .py files.

    Args:
        directory: Root directory to scan.
        mtimes: Dict to update with ``{path: mtime}`` entries.
    """
    for root, _dirs, files in os.walk(directory):
        for name in files:
            if name.endswith(".py"):
                filepath = os.path.join(root, name)
                with contextlib.suppress(OSError):
                    mtimes[filepath] = os.path.getmtime(filepath)


def _check_changes(directory: str, mtimes: dict[str, float]) -> bool:
    """Check for mtime changes in .py files under a directory.

    Updates ``mtimes`` in place with new entries and changed times.

    Args:
        directory: Root directory to scan.
        mtimes: The mtime tracking dict.

    Returns:
        ``True`` if any file was added or modified since last scan.
    """
    changed = False
    for root, _dirs, files in os.walk(directory):
        for name in files:
            if name.endswith(".py"):
                filepath = os.path.join(root, name)
                try:
                    mtime = os.path.getmtime(filepath)
                except OSError:
                    continue

                old = mtimes.get(filepath)
                if old is None or mtime > old:
                    mtimes[filepath] = mtime
                    changed = True
    return changed


__all__ = [
    "DevServer",
]
