"""App ABC and decorator factory for plushie applications.

Defines the ``App`` base class using the Elm architecture pattern
(init/update/view) and the ``create_app`` decorator factory for a
lighter-weight Flask-like API.

Usage (class-based)::

    from dataclasses import dataclass, replace
    from plushie import App, ui
    from plushie.events import Click

    @dataclass(frozen=True)
    class Model:
        count: int = 0

    class Counter(App[Model]):
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

Usage (decorator factory)::

    from plushie import create_app

    app = create_app("Counter")

    @app.init
    def init():
        return {"count": 0}

    @app.update
    def update(model, event):
        ...

    @app.view
    def view(model):
        ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from plushie.commands import Command
from plushie.subscriptions import Subscription


class App[M](ABC):
    """Abstract base class for plushie applications.

    Generic over the model type ``M``.  Subclass and implement the
    three required methods (``init``, ``update``, ``view``) to define
    an application.

    ``subscribe``, ``settings``, and ``handle_renderer_exit`` have
    default implementations that can be overridden.
    """

    @abstractmethod
    def init(self) -> M | tuple[M, Command]:
        """Called once at startup to produce the initial model.

        Return either a bare model or ``(model, command)`` to schedule
        initial side effects (e.g. loading data).
        """
        ...

    @abstractmethod
    def update(self, model: M, event: Any) -> M | tuple[M, Command]:
        """Called on every event.  Returns the next model state.

        Return either a bare model or ``(model, command)`` to schedule
        side effects.  A catch-all clause is recommended to handle
        unknown events gracefully::

            case _:
                return model
        """
        ...

    @abstractmethod
    def view(self, model: M) -> dict[str, Any] | list[dict[str, Any]]:
        """Called after every update. Returns explicit top-level window nodes.

        Return either one ``ui.window(...)`` node or a list of window
        nodes. Bare top-level widgets are rejected by the runtime.
        """
        ...

    def subscribe(self, model: M) -> list[Subscription]:
        """Called after every update.  Returns active subscriptions.

        The runtime diffs subscriptions by key, starting new ones and
        stopping removed ones.  Default: empty list (no subscriptions).
        """
        return []

    def settings(self) -> dict[str, Any]:
        """Called once at startup.  Returns renderer settings.

        Supported keys: ``default_font``, ``default_text_size``,
        ``antialiasing``, ``vsync``, ``scale_factor``, ``theme``,
        ``fonts``, ``default_event_rate``, ``widget_config``,
        ``required_widgets``, ``validate_props``.

        The ``widget_config`` key accepts a dict keyed by native
        widget type. It is forwarded to the renderer and made available
        to native widgets.

        The ``required_widgets`` key accepts a list of native widget
        type names; the renderer validates the list during handshake
        and emits a ``required_widgets_missing`` diagnostic for any
        names it does not recognize. Non-fatal.

        Default: empty dict (renderer defaults).
        """
        return {}

    def window_config(self, model: M) -> dict[str, Any]:
        """Called when windows are opened. Returns default window properties.

        Override to set default title, size, position, theme, etc.
        Per-window props set in the view tree override these defaults.
        """
        return {}

    def handle_renderer_exit(self, model: M, reason: Any) -> M:
        """Called when the renderer process exits unexpectedly.

        Return the model to use when the renderer restarts.
        Default: return model unchanged.
        """
        return model


class _DecoratorApp(App[Any]):
    """Dynamically-built App from decorator registrations.

    Used by ``create_app()``. Not part of the public API.
    """

    def __init__(
        self,
        name: str,
        init_fn: Any = None,
        update_fn: Any = None,
        view_fn: Any = None,
        subscribe_fn: Any = None,
        settings_fn: Any = None,
        window_config_fn: Any = None,
        handle_renderer_exit_fn: Any = None,
    ) -> None:
        self._name = name
        self._init_fn = init_fn
        self._update_fn = update_fn
        self._view_fn = view_fn
        self._subscribe_fn = subscribe_fn
        self._settings_fn = settings_fn
        self._window_config_fn = window_config_fn
        self._handle_renderer_exit_fn = handle_renderer_exit_fn

    def init(self) -> Any:
        if self._init_fn is None:
            raise NotImplementedError(f"{self._name}: no init function registered")
        return self._init_fn()

    def update(self, model: Any, event: Any) -> Any:
        if self._update_fn is None:
            raise NotImplementedError(f"{self._name}: no update function registered")
        return self._update_fn(model, event)

    def view(self, model: Any) -> dict[str, Any] | list[dict[str, Any]]:
        if self._view_fn is None:
            raise NotImplementedError(f"{self._name}: no view function registered")
        return self._view_fn(model)

    def subscribe(self, model: Any) -> list[Subscription]:
        if self._subscribe_fn is not None:
            return self._subscribe_fn(model)
        return []

    def settings(self) -> dict[str, Any]:
        if self._settings_fn is not None:
            return self._settings_fn()
        return {}

    def window_config(self, model: Any) -> dict[str, Any]:
        if self._window_config_fn is not None:
            return self._window_config_fn(model)
        return {}

    def handle_renderer_exit(self, model: Any, reason: Any) -> Any:
        if self._handle_renderer_exit_fn is not None:
            return self._handle_renderer_exit_fn(model, reason)
        return model


class AppBuilder:
    """Fluent builder returned by ``create_app()``.

    Register callbacks with decorator methods::

        app = create_app("MyApp")

        @app.init
        def init():
            return {"count": 0}

        @app.update
        def update(model, event):
            return model

        @app.view
        def view(model):
            return {}

    Call ``app.build()`` to get the concrete ``App`` instance, or
    pass the builder directly to ``plushie.run()`` which calls
    ``build()`` automatically.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._init_fn: Any = None
        self._update_fn: Any = None
        self._view_fn: Any = None
        self._subscribe_fn: Any = None
        self._settings_fn: Any = None
        self._window_config_fn: Any = None
        self._handle_renderer_exit_fn: Any = None

    def init(self, fn: Any) -> Any:
        """Register the ``init`` callback."""
        self._init_fn = fn
        return fn

    def update(self, fn: Any) -> Any:
        """Register the ``update`` callback."""
        self._update_fn = fn
        return fn

    def view(self, fn: Any) -> Any:
        """Register the ``view`` callback."""
        self._view_fn = fn
        return fn

    def subscribe(self, fn: Any) -> Any:
        """Register the ``subscribe`` callback."""
        self._subscribe_fn = fn
        return fn

    def settings(self, fn: Any) -> Any:
        """Register the ``settings`` callback."""
        self._settings_fn = fn
        return fn

    def window_config(self, fn: Any) -> Any:
        """Register the ``window_config`` callback."""
        self._window_config_fn = fn
        return fn

    def handle_renderer_exit(self, fn: Any) -> Any:
        """Register the ``handle_renderer_exit`` callback."""
        self._handle_renderer_exit_fn = fn
        return fn

    def build(self) -> App[Any]:
        """Build and return the concrete ``App`` instance.

        Raises ``NotImplementedError`` at call time if any required
        callback (init, update, view) is missing.
        """
        return _DecoratorApp(
            name=self._name,
            init_fn=self._init_fn,
            update_fn=self._update_fn,
            view_fn=self._view_fn,
            subscribe_fn=self._subscribe_fn,
            settings_fn=self._settings_fn,
            window_config_fn=self._window_config_fn,
            handle_renderer_exit_fn=self._handle_renderer_exit_fn,
        )


def create_app(name: str = "PlushieApp") -> AppBuilder:
    """Create an ``AppBuilder`` for decorator-based app definition.

    Args:
        name: Application name (used in error messages).

    Returns:
        An ``AppBuilder`` instance.  Register callbacks with its
        decorator methods, then call ``build()`` or pass it to
        ``plushie.run()``.
    """
    return AppBuilder(name)


__all__ = [
    "App",
    "AppBuilder",
    "create_app",
]
