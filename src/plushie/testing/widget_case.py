"""Widget test harness for testing custom widgets in isolation.

Hosts a widget in a parameterized harness app and records emitted
events. Mirrors the Elixir SDK's ``Plushie.Test.WidgetCase``.

Usage::

    from plushie.testing.widget_case import WidgetFixture

    def test_star_rating(plushie_pool):
        with WidgetFixture(StarRating, "rating", plushie_pool) as w:
            w.canvas_press("#rating", 200.0, 10.0)
            assert w.last_event is not None
            assert w.last_event.data["value"] == 3
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from plushie.app import App
from plushie.testing.fixture import AppFixture
from plushie.testing.pool import SessionPool
from plushie.widget import WidgetDef


@dataclass(frozen=True, slots=True)
class _WidgetModel:
    widget_module: type[WidgetDef]
    widget_id: str
    widget_props: dict[str, Any]
    last_value: Any = None
    events: tuple[Any, ...] = ()
    last_event: Any = None


class _HarnessApp(App[_WidgetModel]):
    """Internal harness app that hosts a single widget."""

    def __init__(
        self,
        widget_module: type[WidgetDef],
        widget_id: str,
        widget_props: dict[str, Any],
    ) -> None:
        self._widget_module = widget_module
        self._widget_id = widget_id
        self._widget_props = widget_props

    def init(self) -> _WidgetModel:
        return _WidgetModel(
            widget_module=self._widget_module,
            widget_id=self._widget_id,
            widget_props=self._widget_props,
        )

    def update(self, model: _WidgetModel, event: Any) -> _WidgetModel:
        if isinstance(event, dict):
            return model
        data = getattr(event, "value", None)
        if isinstance(data, dict):
            pass
        else:
            data = {}
        return replace(
            model,
            last_value=data,
            events=(*model.events, event),
            last_event=event,
        )

    def view(self, model: _WidgetModel) -> dict:
        from plushie.ui import column, window

        wmod = model.widget_module
        wid = model.widget_id
        wopts = model.widget_props
        return window(
            "test_harness",
            column(
                wmod.build(wid, **wopts),
            ),
            title="Widget Test",
        )


class WidgetFixture(AppFixture[_WidgetModel]):
    """Test fixture that hosts a single widget in a harness app.

    Provides all standard ``AppFixture`` methods plus widget-specific
    helpers for accessing emitted events and data.

    Attributes:
        last_event: The most recent event emitted by the widget, or ``None``.
        events: Tuple of all emitted events (oldest first).
        last_value: The most recent event data dict, or ``None``.
    """

    def __init__(
        self,
        widget_class: type[WidgetDef],
        widget_id: str,
        pool: SessionPool,
        widget_props: dict[str, Any] | None = None,
    ) -> None:
        harness = _HarnessApp(
            widget_module=widget_class,
            widget_id=widget_id,
            widget_props=widget_props or {},
        )
        super().__init__(harness, pool)

    @property
    def last_event(self) -> Any:
        """The most recent event emitted by the widget."""
        return self._model.last_event

    @property
    def events(self) -> tuple[Any, ...]:
        """All events emitted by the widget (oldest first)."""
        return self._model.events

    @property
    def last_value(self) -> Any:
        """The most recent event data."""
        return self._model.last_value


__all__ = ["WidgetFixture"]
