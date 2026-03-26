"""Tests for the canvas widget system."""

from __future__ import annotations

from typing import Any

from plushie.canvas_widget import (
    CanvasWidgetDef,
    EventAction,
    EventActionResult,
    RegistryEntry,
    collect_subscriptions,
    derive_registry,
    dispatch_through_widgets,
    maybe_handle_timer,
)
from plushie.events import (
    CanvasElementClick,
    CanvasElementEnter,
    Click,
    WidgetEvent,
)
from plushie.subscriptions import Subscription
from plushie.tree import normalize

# ---------------------------------------------------------------------------
# Test widget definitions
# ---------------------------------------------------------------------------


class StarRating(CanvasWidgetDef):
    """Simple star rating widget for testing."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"hovered": None, "max": props.get("max", 5)}

    def render(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        if isinstance(event, CanvasElementEnter):
            return EventAction.update_state({**state, "hovered": event.element_id})
        if isinstance(event, CanvasElementClick):
            return EventAction.emit("select", {"value": event.element_id})
        return EventAction.ignored()


class IgnoreAll(CanvasWidgetDef):
    """Widget that ignores all events."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def render(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        return EventAction.ignored()


class ConsumeAll(CanvasWidgetDef):
    """Widget that consumes all events."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def render(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        return EventAction.consumed()


class WithSubscriptions(CanvasWidgetDef):
    """Widget with timer subscription."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def render(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        return EventAction.ignored()

    def subscribe(
        self, props: dict[str, Any], state: dict[str, Any]
    ) -> list[Subscription]:
        return [Subscription.every(100, "tick")]


# ---------------------------------------------------------------------------
# EventAction tests
# ---------------------------------------------------------------------------


class TestEventAction:
    def test_ignored(self) -> None:
        result = EventAction.ignored()
        assert result == EventAction.ignored()

    def test_consumed(self) -> None:
        result = EventAction.consumed()
        assert result == EventAction.consumed()

    def test_update_state(self) -> None:
        result = EventAction.update_state({"x": 1})
        assert result.state == {"x": 1}

    def test_emit_with_dict(self) -> None:
        result = EventAction.emit("select", {"value": "star3"})
        assert result.kind == "select"
        assert result.data == {"value": "star3"}

    def test_emit_with_scalar(self) -> None:
        result = EventAction.emit("change", 42)
        assert result.data == {"value": 42}

    def test_emit_with_state(self) -> None:
        result = EventAction.emit("select", {"v": 1}, state={"count": 3})
        assert result.state == {"count": 3}

    def test_emit_with_none_data(self) -> None:
        result = EventAction.emit("ping")
        assert result.data == {}


# ---------------------------------------------------------------------------
# Build tests
# ---------------------------------------------------------------------------


class TestBuild:
    def test_builds_placeholder(self) -> None:
        node = StarRating.build("stars", props={"max": 5})
        assert node["id"] == "stars"
        assert node["type"] == "canvas"
        meta = node["meta"]
        assert meta["__canvas_widget__"] is StarRating
        assert meta["__canvas_widget_props__"] == {"max": 5}

    def test_meta_preserved_through_normalize(self) -> None:
        node = StarRating.build("stars", props={"max": 5})
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [node],
        }
        result = normalize(tree)
        child = result["children"][0]
        assert "meta" in child
        assert child["meta"]["__canvas_widget__"] is StarRating


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestDeriveRegistry:
    def test_empty_tree(self) -> None:
        assert derive_registry(None) == {}

    def test_extracts_widget_entries(self) -> None:
        tree = normalize(
            {
                "id": "root",
                "type": "container",
                "props": {},
                "children": [StarRating.build("stars", props={"max": 5})],
            }
        )
        reg = derive_registry(tree)
        assert "root/stars" in reg
        entry = reg["root/stars"]
        assert isinstance(entry.definition, StarRating)
        assert entry.state == {"hovered": None, "max": 5}
        assert entry.props == {"max": 5}


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------


class TestDispatchThroughWidgets:
    def test_ignored_passes_through(self) -> None:
        reg = {"form/widget": RegistryEntry(definition=IgnoreAll(), state={}, props={})}
        event = Click(id="btn", scope=("widget", "form"))
        result, _new_reg = dispatch_through_widgets(reg, event)
        assert result is event

    def test_consumed_returns_none(self) -> None:
        reg = {
            "form/widget": RegistryEntry(definition=ConsumeAll(), state={}, props={})
        }
        event = Click(id="btn", scope=("widget", "form"))
        result, _new_reg = dispatch_through_widgets(reg, event)
        assert result is None

    def test_emit_replaces_event(self) -> None:
        reg = {
            "stars": RegistryEntry(
                definition=StarRating(),
                state={"hovered": None, "max": 5},
                props={"max": 5},
            )
        }
        event = CanvasElementClick(
            id="stars",
            element_id="star3",
            x=10.0,
            y=10.0,
            button="left",
            scope=(),
        )
        result, _new_reg = dispatch_through_widgets(reg, event)
        assert isinstance(result, WidgetEvent)
        assert result.kind == "select"
        assert result.data == {"value": "star3"}

    def test_update_state_modifies_registry(self) -> None:
        reg = {
            "stars": RegistryEntry(
                definition=StarRating(),
                state={"hovered": None, "max": 5},
                props={"max": 5},
            )
        }
        event = CanvasElementEnter(
            id="stars",
            element_id="star2",
            x=10.0,
            y=10.0,
            scope=(),
        )
        result, new_reg = dispatch_through_widgets(reg, event)
        assert result is None  # consumed by update_state
        assert new_reg["stars"].state["hovered"] == "star2"

    def test_empty_registry_passes_through(self) -> None:
        event = Click(id="btn", scope=())
        result, _ = dispatch_through_widgets({}, event)
        assert result is event

    def test_no_scope_passes_through(self) -> None:
        reg = {"stars": RegistryEntry(definition=IgnoreAll(), state={}, props={})}
        event = Click(id="other")
        result, _ = dispatch_through_widgets(reg, event)
        assert result is event


# ---------------------------------------------------------------------------
# Subscription collection tests
# ---------------------------------------------------------------------------


class TestCollectSubscriptions:
    def test_namespaced_tags(self) -> None:
        reg = {
            "widget1": RegistryEntry(definition=WithSubscriptions(), state={}, props={})
        }
        subs = collect_subscriptions(reg)
        assert len(subs) == 1
        assert subs[0].tag == ("__canvas_widget__", "widget1", "tick")


# ---------------------------------------------------------------------------
# Timer routing tests
# ---------------------------------------------------------------------------


class TestMaybeHandleTimer:
    def test_non_widget_tag_not_routed(self) -> None:
        handled, _, _ = maybe_handle_timer({}, "regular_tag")
        assert handled is False

    def test_widget_tag_routed(self) -> None:
        reg = {"stars": RegistryEntry(definition=IgnoreAll(), state={}, props={})}
        handled, event, _ = maybe_handle_timer(
            reg, ("__canvas_widget__", "stars", "tick")
        )
        assert handled is True
        assert event is None  # IgnoreAll ignores everything
