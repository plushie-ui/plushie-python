"""Tests for the custom widget system."""

from __future__ import annotations

from typing import Any, ClassVar

from plushie.events import (
    Click,
    Enter,
    Press,
    RawEvent,
    Select,
)
from plushie.subscriptions import Subscription
from plushie.tree import normalize
from plushie.widget import (
    EventAction,
    EventActionResult,
    EventSpec,
    RegistryEntry,
    WidgetDef,
    collect_subscriptions,
    derive_registry,
    dispatch_through_widgets,
    maybe_handle_timer,
)

# ---------------------------------------------------------------------------
# Test widget definitions
# ---------------------------------------------------------------------------


class StarRating(WidgetDef):
    """Simple star rating widget for testing."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"hovered": None, "max": props.get("max", 5)}

    def view(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        if isinstance(event, Enter):
            return EventAction.update_state({**state, "hovered": event.id})
        if isinstance(event, Click):
            return EventAction.emit("select", {"value": event.id})
        return EventAction.ignored()


class IgnoreAll(WidgetDef):
    """Widget that ignores all events."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def view(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        return EventAction.ignored()


class ConsumeAll(WidgetDef):
    """Widget that consumes all events."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def view(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        return EventAction.consumed()


class CustomEmitter(WidgetDef):
    """Widget that emits a custom (non-built-in) event name."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def view(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        if isinstance(event, Click):
            return EventAction.emit("change", {"hue": 180.0, "sat": 0.5})
        return EventAction.ignored()


class ToggleEmitter(WidgetDef):
    """Widget that emits a built-in toggle event."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {"on": False}

    def view(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        if isinstance(event, Click):
            new_on = not state["on"]
            return EventAction.emit("toggle", new_on, state={"on": new_on})
        return EventAction.ignored()


class WithSubscriptions(WidgetDef):
    """Widget with timer subscription."""

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def view(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        return EventAction.ignored()

    def subscribe(
        self, props: dict[str, Any], state: dict[str, Any]
    ) -> list[Subscription]:
        return [Subscription.every(100, "tick")]


class ValidatedWidget(WidgetDef):
    """Widget with event_specs for validation testing."""

    event_specs: ClassVar[dict[str, EventSpec]] = {
        "change": EventSpec(fields={"hue": float, "saturation": float}),
        "select": EventSpec(value_type=int),
        "cleared": EventSpec(),
    }

    def init(self, props: dict[str, Any]) -> dict[str, Any]:
        return {}

    def view(
        self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

    def handle_event(self, event: Any, state: dict[str, Any]) -> EventActionResult:
        if isinstance(event, Click):
            eid = event.id
            if eid == "ring":
                return EventAction.emit("change", {"hue": 180.0, "saturation": 0.5})
            if eid == "star":
                return EventAction.emit("select", 3)
            if eid == "clear":
                return EventAction.emit("cleared")
        return EventAction.ignored()


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
        assert meta["__widget__"] is StarRating
        assert meta["__widget_props__"] == {"max": 5}

    def test_meta_preserved_through_normalize(self) -> None:
        node = StarRating.build("stars", props={"max": 5})
        tree = {
            "id": "main",
            "type": "window",
            "props": {},
            "children": [node],
        }
        result = normalize(tree)
        child = result["children"][0]
        assert "meta" in child
        assert child["meta"]["__widget__"] is StarRating


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestDeriveRegistry:
    def test_empty_tree(self) -> None:
        assert derive_registry(None) == {}

    def test_extracts_widget_entries(self) -> None:
        tree = normalize(
            {
                "id": "main",
                "type": "window",
                "props": {},
                "children": [StarRating.build("stars", props={"max": 5})],
            }
        )
        reg = derive_registry(tree)
        assert ("main", "stars") in reg
        entry = reg[("main", "stars")]
        assert isinstance(entry.definition, StarRating)
        assert entry.state == {"hovered": None, "max": 5}
        assert entry.props == {"max": 5}


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------


class TestDispatchThroughWidgets:
    def test_ignored_passes_through(self) -> None:
        reg = {
            ("main", "form/widget"): RegistryEntry(
                definition=IgnoreAll(), state={}, props={}
            )
        }
        event = Click(id="btn", window_id="main", scope=("widget", "form"))
        result, _new_reg, _changed = dispatch_through_widgets(reg, event)
        assert result is event

    def test_consumed_returns_none(self) -> None:
        reg = {
            ("main", "form/widget"): RegistryEntry(
                definition=ConsumeAll(), state={}, props={}
            )
        }
        event = Click(id="btn", window_id="main", scope=("widget", "form"))
        result, _new_reg, _changed = dispatch_through_widgets(reg, event)
        assert result is None

    def test_emit_replaces_event(self) -> None:
        reg = {
            ("main", "stars"): RegistryEntry(
                definition=StarRating(),
                state={"hovered": None, "max": 5},
                props={"max": 5},
            )
        }
        event = Click(
            id="star3",
            window_id="main",
            scope=("stars",),
        )
        result, _new_reg, _changed = dispatch_through_widgets(reg, event)
        assert isinstance(result, Select)
        assert result.value == "star3"
        assert result.window_id == "main"
        assert result.id == "stars"

    def test_emit_custom_event_produces_widget_event(self) -> None:
        """Custom event names produce RawEvent (no typed class)."""
        reg = {
            ("main", "picker"): RegistryEntry(
                definition=CustomEmitter(),
                state={},
                props={},
            )
        }
        event = Click(
            id="ring",
            window_id="main",
            scope=("picker",),
        )
        result, _, _changed = dispatch_through_widgets(reg, event)
        assert isinstance(result, RawEvent)
        assert result.kind == "change"
        assert result.data == {"hue": 180.0, "sat": 0.5}

    def test_emit_toggle_produces_typed_event(self) -> None:
        """Built-in 'toggle' emission produces a Toggle dataclass."""
        from plushie.events import Toggle

        reg = {
            ("main", "sw"): RegistryEntry(
                definition=ToggleEmitter(),
                state={"on": False},
                props={},
            )
        }
        event = Click(
            id="switch",
            window_id="main",
            scope=("sw",),
        )
        result, new_reg, _changed = dispatch_through_widgets(reg, event)
        assert isinstance(result, Toggle)
        assert result.value is True
        assert result.id == "sw"
        assert result.window_id == "main"
        # State was also updated
        assert new_reg[("main", "sw")].state == {"on": True}

    def test_update_state_modifies_registry(self) -> None:
        reg = {
            ("main", "stars"): RegistryEntry(
                definition=StarRating(),
                state={"hovered": None, "max": 5},
                props={"max": 5},
            )
        }
        event = Enter(
            id="star2",
            window_id="main",
            scope=("stars",),
        )
        result, new_reg, _changed = dispatch_through_widgets(reg, event)
        assert result is None  # consumed by update_state
        assert new_reg[("main", "stars")].state["hovered"] == "star2"

    def test_empty_registry_passes_through(self) -> None:
        event = Click(id="btn", window_id="main", scope=())
        result, _, _changed = dispatch_through_widgets({}, event)
        assert result is event

    def test_no_scope_passes_through(self) -> None:
        reg = {
            ("main", "stars"): RegistryEntry(definition=IgnoreAll(), state={}, props={})
        }
        event = Click(id="other", window_id="main")
        result, _, _changed = dispatch_through_widgets(reg, event)
        assert result is event

    def test_unhandled_press_passes_through(self) -> None:
        """Pointer events from unmatched scope pass through to update()."""
        reg = {
            ("main", "other_widget"): RegistryEntry(
                definition=IgnoreAll(), state={}, props={}
            )
        }
        event = Press(
            id="raw_canvas",
            x=0.0,
            y=0.0,
            button="left",
            window_id="main",
            scope=(),
        )
        result, _, _changed = dispatch_through_widgets(reg, event)
        assert result is event


# ---------------------------------------------------------------------------
# Event spec validation tests
# ---------------------------------------------------------------------------


class TestEventSpecs:
    def _make_reg(self) -> dict[tuple[str, str], RegistryEntry]:
        return {
            ("main", "picker"): RegistryEntry(
                definition=ValidatedWidget(),
                state={},
                props={},
            )
        }

    def _click(self, element_id: str) -> Click:
        return Click(
            id=element_id,
            window_id="main",
            scope=("picker",),
        )

    def test_valid_data_event_passes(self) -> None:
        reg = self._make_reg()
        result, _, _changed = dispatch_through_widgets(reg, self._click("ring"))
        assert isinstance(result, RawEvent)
        assert result.kind == "change"
        assert result.data == {"hue": 180.0, "saturation": 0.5}

    def test_valid_value_event_produces_typed(self) -> None:
        reg = self._make_reg()
        result, _, _changed = dispatch_through_widgets(reg, self._click("star"))
        assert isinstance(result, Select)
        assert result.value == 3

    def test_valid_no_payload_event(self) -> None:
        reg = self._make_reg()
        # "cleared" has EventSpec(), no payload expected
        # The widget emits with None data -> normalized to {}
        # Need a widget that emits "cleared":

        class ClearWidget(WidgetDef):
            event_specs: ClassVar[dict[str, EventSpec]] = {
                "cleared": EventSpec(),
            }

            def init(self, props: dict[str, Any]) -> dict[str, Any]:
                return {}

            def view(
                self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
            ) -> dict[str, Any]:
                return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

            def handle_event(
                self, event: Any, state: dict[str, Any]
            ) -> EventActionResult:
                return EventAction.emit("cleared")

        reg = {
            ("main", "w"): RegistryEntry(definition=ClearWidget(), state={}, props={})
        }
        event = Click(
            id="x",
            window_id="main",
            scope=("w",),
        )
        result, _, _changed = dispatch_through_widgets(reg, event)
        assert isinstance(result, RawEvent)
        assert result.kind == "cleared"

    def test_undeclared_event_name_raises(self) -> None:
        class BadWidget(WidgetDef):
            event_specs: ClassVar[dict[str, EventSpec]] = {
                "change": EventSpec(fields={"x": float}),
            }

            def init(self, props: dict[str, Any]) -> dict[str, Any]:
                return {}

            def view(
                self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
            ) -> dict[str, Any]:
                return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

            def handle_event(
                self, event: Any, state: dict[str, Any]
            ) -> EventActionResult:
                return EventAction.emit("chaneg", {"x": 1.0})  # typo!

        reg = {("main", "w"): RegistryEntry(definition=BadWidget(), state={}, props={})}
        event = Click(
            id="x",
            window_id="main",
            scope=("w",),
        )
        import pytest

        with pytest.raises(ValueError, match="undeclared event"):
            dispatch_through_widgets(reg, event)

    def test_missing_field_raises(self) -> None:
        class IncompleteWidget(WidgetDef):
            event_specs: ClassVar[dict[str, EventSpec]] = {
                "change": EventSpec(fields={"hue": float, "saturation": float}),
            }

            def init(self, props: dict[str, Any]) -> dict[str, Any]:
                return {}

            def view(
                self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
            ) -> dict[str, Any]:
                return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

            def handle_event(
                self, event: Any, state: dict[str, Any]
            ) -> EventActionResult:
                return EventAction.emit("change", {"hue": 180.0})  # missing saturation

        reg = {
            ("main", "w"): RegistryEntry(
                definition=IncompleteWidget(), state={}, props={}
            )
        }
        event = Click(
            id="x",
            window_id="main",
            scope=("w",),
        )
        import pytest

        with pytest.raises(ValueError, match="missing declared fields"):
            dispatch_through_widgets(reg, event)

    def test_wrong_value_type_raises(self) -> None:
        class WrongTypeWidget(WidgetDef):
            event_specs: ClassVar[dict[str, EventSpec]] = {
                "select": EventSpec(value_type=int),
            }

            def init(self, props: dict[str, Any]) -> dict[str, Any]:
                return {}

            def view(
                self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
            ) -> dict[str, Any]:
                return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

            def handle_event(
                self, event: Any, state: dict[str, Any]
            ) -> EventActionResult:
                return EventAction.emit("select", "not_an_int")

        reg = {
            ("main", "w"): RegistryEntry(
                definition=WrongTypeWidget(), state={}, props={}
            )
        }
        event = Click(
            id="x",
            window_id="main",
            scope=("w",),
        )
        import pytest

        with pytest.raises(TypeError, match="expected int"):
            dispatch_through_widgets(reg, event)

    def test_builtin_event_allowed_without_declaration(self) -> None:
        """A widget with event_specs can still emit built-in events."""

        class ClickEmitter(WidgetDef):
            event_specs: ClassVar[dict[str, EventSpec]] = {
                "custom": EventSpec(),
            }

            def init(self, props: dict[str, Any]) -> dict[str, Any]:
                return {}

            def view(
                self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
            ) -> dict[str, Any]:
                return {"id": widget_id, "type": "canvas", "props": {}, "children": []}

            def handle_event(
                self, event: Any, state: dict[str, Any]
            ) -> EventActionResult:
                return EventAction.emit("click")

        reg = {
            ("main", "w"): RegistryEntry(definition=ClickEmitter(), state={}, props={})
        }
        event = Click(
            id="x",
            window_id="main",
            scope=("w",),
        )
        result, _, _changed = dispatch_through_widgets(reg, event)
        assert isinstance(result, Click)

    def test_no_event_specs_skips_validation(self) -> None:
        """Widgets without event_specs can emit anything."""
        reg = {
            ("main", "picker"): RegistryEntry(
                definition=CustomEmitter(),  # no event_specs
                state={},
                props={},
            )
        }
        result, _, _changed = dispatch_through_widgets(reg, self._click("ring"))
        assert isinstance(result, RawEvent)
        assert result.kind == "change"


# ---------------------------------------------------------------------------
# Subscription collection tests
# ---------------------------------------------------------------------------


class TestCollectSubscriptions:
    def test_namespaced_tags(self) -> None:
        reg = {
            ("main", "widget1"): RegistryEntry(
                definition=WithSubscriptions(), state={}, props={}
            )
        }
        subs = collect_subscriptions(reg)
        assert len(subs) == 1
        assert subs[0].tag == ("__widget__", "main", "widget1", "tick")


# ---------------------------------------------------------------------------
# Timer routing tests
# ---------------------------------------------------------------------------


class TestMaybeHandleTimer:
    def test_non_widget_tag_not_routed(self) -> None:
        handled, _, _ = maybe_handle_timer({}, "regular_tag")
        assert handled is False

    def test_widget_tag_routed(self) -> None:
        reg = {
            ("main", "stars"): RegistryEntry(definition=IgnoreAll(), state={}, props={})
        }
        handled, event, _ = maybe_handle_timer(
            reg, ("__widget__", "main", "stars", "tick")
        )
        assert handled is True
        assert event is None  # IgnoreAll ignores everything
