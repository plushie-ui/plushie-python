"""Native desktop GUI framework for Python, powered by iced.

Top-level API for plushie applications. Import the ``App`` class for
class-based apps, ``create_app`` for the decorator-based builder, and
``run``/``start`` for lifecycle management.

Quick start::

    from dataclasses import dataclass, replace
    import plushie
    from plushie import ui
    from plushie.events import Click

    @dataclass(frozen=True)
    class Model:
        count: int = 0

    class Counter(plushie.App[Model]):
        def init(self) -> Model:
            return Model()

        def update(self, model: Model, event: object) -> Model:
            match event:
                case Click(id="inc"):
                    return replace(model, count=model.count + 1)
                case _:
                    return model

        def view(self, model: Model) -> dict:
            return ui.window("main", ui.column(
                ui.text("count", f"Count: {model.count}"),
                ui.button("inc", "Increment"),
            ))

    if __name__ == "__main__":
        plushie.run(Counter)
"""

from __future__ import annotations

import threading
from typing import Any

__version__ = "0.5.0"

from plushie import ui as ui
from plushie.app import App, AppBuilder, create_app
from plushie.commands import Command
from plushie.events import (
    AllWindowsClosed,
    AsyncResult,
    Click,
    EffectResult,
    Event,
    Input,
    KeyEvent,
    Select,
    Slide,
    StreamChunk,
    Submit,
    TimerTick,
    Toggle,
)
from plushie.runtime import RuntimeHandle
from plushie.subscriptions import Subscription

# Re-exported from events.py as the union of all event types.


def run(
    app_class: type[App[Any]] | AppBuilder,
    *,
    binary_path: str | None = None,
    mode: str | None = None,
    daemon: bool = False,
    **connection_opts: Any,
) -> None:
    """Run a plushie application (blocking).

    Resolves the binary, opens a connection, creates the runtime, and
    blocks until the application exits.

    Args:
        app_class: An ``App`` subclass (will be instantiated) or an
            ``AppBuilder`` instance.
        binary_path: Explicit path to the plushie binary.
        mode: Renderer mode: ``"mock"``, ``"headless"``, or ``None``
            for windowed (default).
        daemon: If ``True``, ``AllWindowsClosed`` does not stop the
            runtime.
        **connection_opts: Extra keyword arguments forwarded to
            ``Connection.open()``.
    """
    from plushie.connection import Connection
    from plushie.runtime import Runtime

    app: App[Any]
    if isinstance(app_class, AppBuilder):
        app = app_class.build()
    elif isinstance(app_class, type):
        app = app_class()
    else:
        app = app_class  # type: ignore[assignment]

    with Connection.open(binary_path=binary_path, mode=mode, **connection_opts) as conn:
        runtime = Runtime(app, conn, daemon=daemon)
        runtime.run()


def start(
    app_class: type[App[Any]] | AppBuilder,
    *,
    binary_path: str | None = None,
    mode: str | None = None,
    daemon: bool = False,
    **connection_opts: Any,
) -> RuntimeHandle:
    """Start a plushie application on a background thread.

    Returns a ``RuntimeHandle`` for controlling the runtime from
    external code. Call ``handle.wait()`` to block until exit, or
    ``handle.stop()`` to signal shutdown.

    Args:
        app_class: An ``App`` subclass (will be instantiated) or an
            ``AppBuilder`` instance.
        binary_path: Explicit path to the plushie binary.
        mode: Renderer mode.
        daemon: If ``True``, ``AllWindowsClosed`` does not stop the
            runtime.
        **connection_opts: Extra keyword arguments forwarded to
            ``Connection.open()``.

    Returns:
        A ``RuntimeHandle`` with ``stop()``, ``wait()``, and
        ``inject()`` methods.
    """
    from plushie.connection import Connection
    from plushie.runtime import Runtime

    app: App[Any]
    if isinstance(app_class, AppBuilder):
        app = app_class.build()
    elif isinstance(app_class, type):
        app = app_class()
    else:
        app = app_class  # type: ignore[assignment]

    conn = Connection.open(binary_path=binary_path, mode=mode, **connection_opts)
    runtime = Runtime(app, conn, daemon=daemon)

    def run_thread() -> None:
        try:
            runtime.run()
        finally:
            conn.close()

    thread = threading.Thread(target=run_thread, name="plushie-runtime", daemon=True)
    thread.start()
    return RuntimeHandle(runtime, thread)


__all__ = [
    "AllWindowsClosed",
    "App",
    "AppBuilder",
    "AsyncResult",
    "Click",
    "Command",
    "EffectResult",
    "Event",
    "Input",
    "KeyEvent",
    "RuntimeHandle",
    "Select",
    "Slide",
    "StreamChunk",
    "Submit",
    "Subscription",
    "TimerTick",
    "Toggle",
    "__version__",
    "create_app",
    "run",
    "start",
    "ui",
]
