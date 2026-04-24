"""Tests for plushie.runtime: non-binary logic tests.

Tests the pure-logic parts of the runtime: unwrap_result, window
detection, coalescing, subscription diffing, and the App ABC.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from plushie.app import App, AppBuilder, create_app
from plushie.commands import Command
from plushie.events import (
    AsyncResult,
    Click,
    EffectResult,
    EffectStubAck,
    Move,
    RecoveryFailed,
    RendererRestarted,
    TimerTick,
)
from plushie.runtime import (
    _DEV_PREFIX,
    _build_frozen_overlay_bar,
    _inject_frozen_overlay,
    _is_overlay_event,
    coalesce_key,
    detect_windows,
    extract_window_props,
    unwrap_result,
)
from plushie.subscriptions import Subscription

# ===================================================================
# unwrap_result
# ===================================================================


class TestUnwrapResult:
    """Validate init/update return value normalization."""

    def test_bare_model(self) -> None:
        model, cmds = unwrap_result(42)
        assert model == 42
        assert cmds == []

    def test_bare_dict_model(self) -> None:
        m = {"count": 0}
        model, cmds = unwrap_result(m)
        assert model is m
        assert cmds == []

    def test_bare_none_model(self) -> None:
        model, cmds = unwrap_result(None)
        assert model is None
        assert cmds == []

    def test_tuple_with_single_command(self) -> None:
        cmd = Command.none()
        model, cmds = unwrap_result(("model", cmd))
        assert model == "model"
        assert cmds == [cmd]

    def test_tuple_with_command_list(self) -> None:
        c1 = Command.none()
        c2 = Command.exit()
        model, cmds = unwrap_result(("model", [c1, c2]))
        assert model == "model"
        assert cmds == [c1, c2]

    def test_tuple_with_empty_command_list(self) -> None:
        model, cmds = unwrap_result(("model", []))
        assert model == "model"
        assert cmds == []

    def test_rejects_three_tuple(self) -> None:
        with pytest.raises(TypeError, match="3-element tuple"):
            unwrap_result((1, 2, 3))

    def test_rejects_non_command_second_element(self) -> None:
        with pytest.raises(TypeError, match="expected a Command"):
            unwrap_result(("model", "not_a_command"))

    def test_rejects_list_with_non_command(self) -> None:
        with pytest.raises(TypeError, match="command list contains"):
            unwrap_result(("model", [Command.none(), "bad"]))

    def test_string_model_not_treated_as_tuple(self) -> None:
        """Strings are iterable but should be treated as bare models."""
        model, cmds = unwrap_result("hello")
        assert model == "hello"
        assert cmds == []

    def test_list_model_not_treated_as_tuple(self) -> None:
        """Lists are bare models (only 2-tuples are command pairs)."""
        m = [1, 2, 3]
        model, cmds = unwrap_result(m)
        assert model == [1, 2, 3]
        assert cmds == []


# ===================================================================
# detect_windows
# ===================================================================


class TestDetectWindows:
    """Window node detection at root and direct-child level."""

    def test_none_tree(self) -> None:
        assert detect_windows(None) == set()

    def test_root_is_window(self) -> None:
        tree = {"id": "main", "type": "window", "props": {}, "children": []}
        assert detect_windows(tree) == {"main"}

    def test_direct_child_windows(self) -> None:
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                {"id": "win1", "type": "window", "props": {}, "children": []},
                {"id": "panel", "type": "container", "props": {}, "children": []},
                {"id": "win2", "type": "window", "props": {}, "children": []},
            ],
        }
        assert detect_windows(tree) == {"win1", "win2"}

    def test_nested_windows_detected(self) -> None:
        """Windows at any depth are detected recursively."""
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                {
                    "id": "wrapper",
                    "type": "container",
                    "props": {},
                    "children": [
                        {
                            "id": "deep_win",
                            "type": "window",
                            "props": {},
                            "children": [],
                        },
                    ],
                },
            ],
        }
        assert detect_windows(tree) == {"deep_win"}

    def test_no_windows(self) -> None:
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                {"id": "btn", "type": "button", "props": {}, "children": []},
            ],
        }
        assert detect_windows(tree) == set()

    def test_empty_children(self) -> None:
        tree = {"id": "root", "type": "container", "props": {}, "children": []}
        assert detect_windows(tree) == set()


# ===================================================================
# extract_window_props
# ===================================================================


class TestExtractWindowProps:
    """Window prop extraction from tree nodes."""

    def test_none_tree(self) -> None:
        assert extract_window_props(None, "main") == {}

    def test_root_window(self) -> None:
        tree = {
            "id": "main",
            "type": "window",
            "props": {
                "title": "My App",
                "width": 800,
                "height": 600,
                "custom": "ignored",
            },
            "children": [],
        }
        result = extract_window_props(tree, "main")
        assert result == {"title": "My App", "width": 800, "height": 600}
        assert "custom" not in result

    def test_child_window(self) -> None:
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                {
                    "id": "win",
                    "type": "window",
                    "props": {"title": "Settings", "resizable": False},
                    "children": [],
                },
            ],
        }
        result = extract_window_props(tree, "win")
        assert result == {"title": "Settings", "resizable": False}

    def test_missing_window(self) -> None:
        tree = {"id": "root", "type": "container", "props": {}, "children": []}
        assert extract_window_props(tree, "nonexistent") == {}


# ===================================================================
# coalesce_key
# ===================================================================


class TestCoalesceKey:
    """Event coalescing key generation."""

    def test_pointer_move(self) -> None:
        event = Move(id="area1", x=10.0, y=20.0, window_id="main")
        assert coalesce_key(event) == ("move", "main", "area1")

    def test_different_move_targets_different_keys(self) -> None:
        e1 = Move(id="area1", x=10.0, y=20.0, window_id="main")
        e2 = Move(id="area2", x=10.0, y=20.0, window_id="main")
        assert coalesce_key(e1) != coalesce_key(e2)

    def test_non_coalescable_returns_none(self) -> None:
        assert coalesce_key(Click(id="btn", window_id="main")) is None
        assert coalesce_key(AsyncResult(tag="t", value=1)) is None
        assert coalesce_key(TimerTick(tag="t", timestamp=0)) is None


# ===================================================================
# App ABC
# ===================================================================


class TestAppABC:
    """App base class contracts."""

    def test_concrete_subclass(self) -> None:
        @dataclass(frozen=True)
        class Model:
            count: int = 0

        class MyApp(App[Model]):
            def init(self) -> Model:
                return Model()

            def update(self, model: Model, event: Any) -> Model:
                return model

            def view(self, model: Model) -> dict[str, Any]:
                return {"id": "root", "type": "container", "props": {}, "children": []}

        app = MyApp()
        model = app.init()
        assert model == Model()
        assert app.update(model, "event") == model
        assert app.view(model)["type"] == "container"
        assert app.subscribe(model) == []
        assert app.settings() == {}
        assert app.handle_renderer_exit(model, "crash") == model

    def test_subscribe_override(self) -> None:
        class SubApp(App[int]):
            def init(self) -> int:
                return 0

            def update(self, model: int, event: Any) -> int:
                return model

            def view(self, model: int) -> dict[str, Any]:
                return {"id": "r", "type": "container", "props": {}, "children": []}

            def subscribe(self, model: int) -> list[Subscription]:
                return [Subscription.every(100, "tick")]

        app = SubApp()
        subs = app.subscribe(0)
        assert len(subs) == 1
        assert subs[0].kind == "every"

    def test_init_returns_tuple(self) -> None:
        class CmdApp(App[str]):
            def init(self) -> tuple[str, Command]:
                return "model", Command.none()

            def update(self, model: str, event: Any) -> str:
                return model

            def view(self, model: str) -> dict[str, Any]:
                return {"id": "r", "type": "container", "props": {}, "children": []}

        app = CmdApp()
        result = app.init()
        model, cmds = unwrap_result(result)
        assert model == "model"
        assert len(cmds) == 1


# ===================================================================
# create_app (decorator factory)
# ===================================================================


class TestCreateApp:
    """AppBuilder / create_app decorator API."""

    def test_full_decorator_flow(self) -> None:
        builder = create_app("TestApp")

        @builder.init
        def init() -> dict[str, int]:
            return {"count": 0}

        @builder.update
        def update(model: dict[str, int], event: Any) -> dict[str, int]:
            return model

        @builder.view
        def view(model: dict[str, int]) -> dict[str, Any]:
            return {"id": "r", "type": "container", "props": {}, "children": []}

        app = builder.build()
        m = app.init()
        assert m == {"count": 0}
        assert app.update(m, None) is m

    def test_missing_init_raises(self) -> None:
        builder = create_app("Broken")

        @builder.view
        def view(model: Any) -> dict[str, Any]:
            return {}

        @builder.update
        def update(model: Any, event: Any) -> Any:
            return model

        app = builder.build()
        with pytest.raises(NotImplementedError, match="Broken"):
            app.init()

    def test_missing_update_raises(self) -> None:
        builder = create_app("Broken")

        @builder.init
        def init() -> int:
            return 0

        @builder.view
        def view(model: Any) -> dict[str, Any]:
            return {}

        app = builder.build()
        with pytest.raises(NotImplementedError, match="Broken"):
            app.update(0, None)

    def test_missing_view_raises(self) -> None:
        builder = create_app("Broken")

        @builder.init
        def init() -> int:
            return 0

        @builder.update
        def update(model: Any, event: Any) -> Any:
            return model

        app = builder.build()
        with pytest.raises(NotImplementedError, match="Broken"):
            app.view(0)

    def test_optional_callbacks(self) -> None:
        builder = create_app("Full")

        @builder.init
        def init() -> int:
            return 0

        @builder.update
        def update(model: int, event: Any) -> int:
            return model

        @builder.view
        def view(model: int) -> dict[str, Any]:
            return {}

        @builder.subscribe
        def subscribe(model: int) -> list[Subscription]:
            return [Subscription.every(16, "anim")]

        @builder.settings
        def settings() -> dict[str, Any]:
            return {"theme": "dark"}

        app = builder.build()
        assert app.settings() == {"theme": "dark"}
        subs = app.subscribe(0)
        assert len(subs) == 1

    def test_builder_is_returned_by_create_app(self) -> None:
        builder = create_app("Test")
        assert isinstance(builder, AppBuilder)

    def test_decorators_return_original_function(self) -> None:
        builder = create_app("Test")

        @builder.init
        def my_init() -> int:
            return 0

        # The decorator should return the original function
        assert my_init() == 0


# ===================================================================
# Subscription key and diffing helpers
# ===================================================================


class TestSubscriptionKeys:
    """Subscription key computation for diffing."""

    def test_timer_key_includes_interval(self) -> None:
        s = Subscription.every(100, "tick")
        assert s.key == ("every", "100", "tick")

    def test_renderer_key(self) -> None:
        s = Subscription.on_key_press()
        assert s.key == ("on_key_press", "")

    def test_same_kind_same_key(self) -> None:
        s1 = Subscription.on_key_press()
        s2 = Subscription.on_key_press()
        assert s1.key == s2.key

    def test_max_rate_not_in_key(self) -> None:
        """max_rate is not part of the key: same sub, different rate."""
        s1 = Subscription.on_pointer_move(max_rate=30)
        s2 = Subscription.on_pointer_move(max_rate=60)
        assert s1.key == s2.key


# ===================================================================
# Edge cases for window prop extraction
# ===================================================================


class TestWindowPropEdgeCases:
    """Edge cases for window property handling."""

    def test_all_window_props_extracted(self) -> None:
        tree = {
            "id": "main",
            "type": "window",
            "props": {
                "title": "Test",
                "width": 800,
                "height": 600,
                "maximized": True,
                "resizable": True,
                "decorations": True,
                "transparent": False,
                "blur": False,
                "level": "normal",
                "visible": True,
                "exit_on_close_request": True,
                "custom_prop": "ignored",
            },
            "children": [],
        }
        result = extract_window_props(tree, "main")
        assert "title" in result
        assert "width" in result
        assert "maximized" in result
        assert "custom_prop" not in result

    def test_empty_props(self) -> None:
        tree = {
            "id": "main",
            "type": "window",
            "props": {},
            "children": [],
        }
        assert extract_window_props(tree, "main") == {}


# ===================================================================
# window_config callback
# ===================================================================


class TestWindowConfig:
    """App.window_config() defaults and override behavior."""

    def test_default_returns_empty_dict(self) -> None:
        class MinimalApp(App[int]):
            def init(self) -> int:
                return 0

            def update(self, model: int, event: Any) -> int:
                return model

            def view(self, model: int) -> dict[str, Any]:
                return {}

        app = MinimalApp()
        assert app.window_config(0) == {}

    def test_override_returns_custom_props(self) -> None:
        class CustomApp(App[int]):
            def init(self) -> int:
                return 0

            def update(self, model: int, event: Any) -> int:
                return model

            def view(self, model: int) -> dict[str, Any]:
                return {}

            def window_config(self, model: int) -> dict[str, Any]:
                return {"title": "My App", "width": 1024, "height": 768}

        app = CustomApp()
        config = app.window_config(0)
        assert config["title"] == "My App"
        assert config["width"] == 1024

    def test_model_available_in_window_config(self) -> None:
        """window_config receives the current model for dynamic defaults."""

        class DynamicApp(App[str]):
            def init(self) -> str:
                return "untitled"

            def update(self, model: str, event: Any) -> str:
                return model

            def view(self, model: str) -> dict[str, Any]:
                return {}

            def window_config(self, model: str) -> dict[str, Any]:
                return {"title": model.capitalize()}

        app = DynamicApp()
        assert app.window_config("hello") == {"title": "Hello"}
        assert app.window_config("world") == {"title": "World"}

    def test_decorator_app_window_config(self) -> None:
        builder = create_app("WinApp")

        @builder.init
        def init() -> int:
            return 0

        @builder.update
        def update(model: int, event: Any) -> int:
            return model

        @builder.view
        def view(model: int) -> dict[str, Any]:
            return {}

        @builder.window_config
        def window_config(model: int) -> dict[str, Any]:
            return {"title": "Decorated", "theme": "dark"}

        app = builder.build()
        config = app.window_config(0)
        assert config == {"title": "Decorated", "theme": "dark"}

    def test_decorator_app_window_config_default(self) -> None:
        """Without registering window_config, returns empty dict."""
        builder = create_app("Plain")

        @builder.init
        def init() -> int:
            return 0

        @builder.update
        def update(model: int, event: Any) -> int:
            return model

        @builder.view
        def view(model: int) -> dict[str, Any]:
            return {}

        app = builder.build()
        assert app.window_config(0) == {}


class TestRuntimeHandshake:
    def test_initialize_waits_for_hello_before_initial_snapshot(self) -> None:
        from plushie.connection import ProtocolMismatchError
        from plushie.runtime import Runtime

        calls: list[str] = []
        builder = create_app("HandshakeTest")

        @builder.init
        def init() -> int:
            calls.append("init")
            return 0

        @builder.update
        def update(model: int, _event: object) -> int:
            return model

        @builder.settings
        def settings() -> dict[str, Any]:
            calls.append("settings")
            return {}

        @builder.view
        def view(_model: int) -> dict[str, Any]:
            calls.append("view")
            return {"id": "root", "type": "container", "props": {}, "children": []}

        class RejectingConnection:
            session = ""

            def send_settings(self, _settings: dict[str, Any]) -> None:
                calls.append("send_settings")

            def wait_hello(self, timeout: float = 10.0) -> Any:
                calls.append(f"wait_hello:{timeout}")
                raise ProtocolMismatchError("protocol version mismatch")

            def send_snapshot(self, _tree: dict[str, Any]) -> None:
                calls.append("send_snapshot")

        conn: Any = RejectingConnection()
        rt = Runtime(builder, conn)

        with pytest.raises(ProtocolMismatchError, match="protocol version mismatch"):
            rt._initialize()

        assert calls == ["init", "settings", "send_settings", "wait_hello:10.0"]


# ===================================================================
# Dev overlay / frozen UI
# ===================================================================


class TestFrozenOverlay:
    def test_overlay_bar_has_dev_prefix_ids(self) -> None:
        bar = _build_frozen_overlay_bar()
        assert bar["id"] == f"{_DEV_PREFIX}/anchor"
        ids = _collect_ids(bar)
        for node_id in ids:
            assert node_id.startswith(_DEV_PREFIX + "/")

    def test_overlay_bar_has_dismiss_button(self) -> None:
        bar = _build_frozen_overlay_bar()
        ids = _collect_ids(bar)
        assert f"{_DEV_PREFIX}/dismiss" in ids

    def test_overlay_bar_has_status_text(self) -> None:
        bar = _build_frozen_overlay_bar()
        ids = _collect_ids(bar)
        assert f"{_DEV_PREFIX}/status" in ids

    def test_inject_overlay_into_single_window(self) -> None:
        tree = {
            "id": "main",
            "type": "window",
            "props": {"title": "App"},
            "children": [
                {"id": "main#content", "type": "column", "props": {}, "children": []}
            ],
        }
        result = _inject_frozen_overlay(tree)
        assert result["type"] == "window"
        assert len(result["children"]) == 1
        stack = result["children"][0]
        assert stack["type"] == "stack"
        assert stack["id"] == f"{_DEV_PREFIX}/stack"
        assert len(stack["children"]) == 2
        assert stack["children"][0]["id"] == "main#content"
        assert stack["children"][1]["id"] == f"{_DEV_PREFIX}/anchor"

    def test_inject_overlay_into_root_with_windows(self) -> None:
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                {
                    "id": "win1",
                    "type": "window",
                    "props": {},
                    "children": [
                        {
                            "id": "win1#content",
                            "type": "text",
                            "props": {},
                            "children": [],
                        }
                    ],
                },
                {
                    "id": "win2",
                    "type": "window",
                    "props": {},
                    "children": [
                        {
                            "id": "win2#content",
                            "type": "text",
                            "props": {},
                            "children": [],
                        }
                    ],
                },
            ],
        }
        result = _inject_frozen_overlay(tree)
        win1 = result["children"][0]
        win2 = result["children"][1]
        assert win1["type"] == "window"
        assert win1["children"][0]["type"] == "stack"
        assert win2["type"] == "window"
        assert win2["children"][0]["type"] == "stack"

    def test_inject_overlay_window_no_children_unchanged(self) -> None:
        tree = {"id": "main", "type": "window", "props": {}, "children": []}
        result = _inject_frozen_overlay(tree)
        assert result is tree

    def test_overlay_event_detection(self) -> None:
        click = Click(id=f"{_DEV_PREFIX}/dismiss")
        assert _is_overlay_event(click) is True

    def test_normal_event_not_overlay(self) -> None:
        click = Click(id="save")
        assert _is_overlay_event(click) is False

    def test_event_without_id_not_overlay(self) -> None:
        tick = TimerTick(tag="t1", timestamp=0)
        assert _is_overlay_event(tick) is False


def _collect_ids(node: dict[str, Any]) -> list[str]:
    """Collect all IDs from a tree node."""
    result: list[str] = []
    if "id" in node:
        result.append(node["id"])
    for child in node.get("children", []):
        result.extend(_collect_ids(child))
    return result


# ===================================================================
# Dispatch-depth guard
# ===================================================================


class TestDispatchDepthGuard:
    """`Command.dispatch` past the depth cap surfaces a typed diagnostic."""

    def _make_runtime(self) -> Any:
        from unittest.mock import MagicMock

        from plushie.app import create_app
        from plushie.runtime import Runtime

        builder = create_app("DispatchDepthTest")

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, _event: object) -> int:
            return model

        @builder.view
        def _view(_model: int) -> None:
            return None

        conn = MagicMock()
        conn.session = ""
        # Runtime spawns no reader threads because we don't call start().
        rt = Runtime(builder, conn)
        return rt

    def test_dispatch_under_limit_enqueues_event(self) -> None:
        rt = self._make_runtime()
        cmd = Command.dispatch("hello", lambda v: v)
        rt._current_dispatch_depth = 5
        rt._execute_command(cmd)
        # Should enqueue a ("_dispatched", 6, event) tuple.
        queued = rt._queue.get_nowait()
        assert queued[0] == "_dispatched"
        assert queued[1] == 6
        assert queued[2] == "hello"

    def test_dispatch_at_limit_drops_and_emits_diagnostic(self) -> None:
        from plushie.diagnostics import DiagnosticMessage, DispatchLoopExceeded
        from plushie.runtime import DISPATCH_DEPTH_LIMIT

        rt = self._make_runtime()
        # Simulate being one dispatch away from the cap.
        rt._current_dispatch_depth = DISPATCH_DEPTH_LIMIT
        cmd = Command.dispatch("boom", lambda v: v)
        rt._execute_command(cmd)

        # The command was dropped: nothing queued.
        assert rt._queue.empty()

        # Typed DispatchLoopExceeded diagnostic was accumulated.
        with rt._diagnostics_lock:
            diags = list(rt._diagnostics)
        assert len(diags) == 1
        msg = diags[0]
        assert isinstance(msg, DiagnosticMessage)
        assert isinstance(msg.diagnostic, DispatchLoopExceeded)
        assert msg.diagnostic.depth == DISPATCH_DEPTH_LIMIT + 1
        assert msg.diagnostic.limit == DISPATCH_DEPTH_LIMIT


class TestInteractDecode:
    def _make_runtime(self) -> Any:
        from unittest.mock import MagicMock

        from plushie.app import create_app
        from plushie.runtime import Runtime

        builder = create_app("InteractDecodeTest")

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, _event: object) -> int:
            return model

        @builder.view
        def _view(_model: int) -> None:
            return None

        conn = MagicMock()
        conn.session = ""
        return Runtime(builder, conn)

    def test_unknown_embedded_interact_event_emits_diagnostic(self) -> None:
        from plushie.diagnostics import DiagnosticMessage, UnknownMessageType

        rt = self._make_runtime()
        decoded = rt._decode_interact_event({"family": "future_global_event"})

        assert decoded is None

        with rt._diagnostics_lock:
            diags = list(rt._diagnostics)

        assert len(diags) == 1
        msg = diags[0]
        assert isinstance(msg, DiagnosticMessage)
        assert isinstance(msg.diagnostic, UnknownMessageType)
        assert msg.diagnostic.msg_type == "event/future_global_event"


class TestInteractStepWidgetState:
    def test_widget_state_change_updates_snapshot_and_registry(self) -> None:
        from unittest.mock import MagicMock

        from plushie.runtime import Runtime
        from plushie.widget import EventAction, EventActionResult, WidgetDef

        class StepWidget(WidgetDef):
            def init(self, props: dict[str, Any]) -> dict[str, Any]:
                return {"count": 0}

            def view(
                self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
            ) -> dict[str, Any]:
                return {
                    "id": widget_id,
                    "type": "container",
                    "props": {},
                    "children": [
                        {
                            "id": "value",
                            "type": "text",
                            "props": {"content": str(state["count"])},
                            "children": [],
                        }
                    ],
                }

            def handle_event(
                self, event: Any, state: dict[str, Any]
            ) -> EventActionResult:
                return EventAction.update_state({"count": state["count"] + 1})

        builder = create_app("InteractStepWidgetState")

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, _event: object) -> int:
            return model + 100

        @builder.view
        def _view(_model: int) -> dict[str, Any]:
            return {
                "id": "main",
                "type": "window",
                "props": {},
                "children": [StepWidget.build("counter")],
            }

        conn = MagicMock()
        conn.session = ""
        rt = Runtime(builder, conn)
        rt._model = 0

        from plushie.widget import derive_registry

        initial = rt._safe_view(rt._model)
        assert initial is not None
        rt._tree = initial
        rt._widget_registry = derive_registry(initial)
        conn.send_snapshot.reset_mock()

        rt._handle_interact_step(
            [
                {
                    "type": "event",
                    "family": "click",
                    "id": "counter/value",
                    "window_id": "main",
                }
            ]
        )

        snapshot = conn.send_snapshot.call_args.args[0]
        widget_node = snapshot["children"][0]
        value_node = widget_node["children"][0]

        assert rt._model == 0
        assert value_node["props"]["content"] == "1"
        assert rt._widget_registry[("main", "main#counter")].state == {"count": 1}
        assert derive_registry(snapshot)[("main", "main#counter")].state == {"count": 1}


class TestReconnectStubAckCleanup:
    def _make_runtime(self) -> Any:
        from unittest.mock import MagicMock

        from plushie.runtime import Runtime

        builder = create_app("ReconnectStubAckTest")

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, _event: object) -> int:
            return model

        @builder.view
        def _view(_model: int) -> dict[str, Any]:
            return {"id": "root", "type": "container", "props": {}, "children": []}

        conn = MagicMock()
        conn.session = ""
        conn.restart.return_value = None
        conn.send_settings.return_value = None
        conn.wait_hello.return_value = None
        conn.send_snapshot.return_value = None

        rt = Runtime(builder, conn)
        rt._model = 0
        rt._start_reader = lambda: None
        return rt

    @pytest.mark.parametrize(
        "method_name", ["register_effect_stub", "unregister_effect_stub"]
    )
    def test_reconnect_releases_pending_stub_ack_waiter(
        self, monkeypatch: pytest.MonkeyPatch, method_name: str
    ) -> None:
        rt = self._make_runtime()
        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        finished = threading.Event()
        result: dict[str, Any] = {"error": None}

        def call() -> None:
            try:
                if method_name == "register_effect_stub":
                    rt.register_effect_stub(
                        "file_open", {"path": "/tmp/file.txt"}, timeout=5.0
                    )
                else:
                    rt.unregister_effect_stub("file_open", timeout=5.0)
            except Exception as exc:  # pragma: no cover - assertion below
                result["error"] = exc
            finally:
                finished.set()

        worker = threading.Thread(target=call, daemon=True)
        worker.start()

        for _ in range(100):
            if "file_open" in rt._pending_stub_acks:
                break
            threading.Event().wait(0.01)
        else:  # pragma: no cover - test would fail below anyway
            pytest.fail("stub ack waiter was never registered")

        assert rt._attempt_reconnect("renderer_crashed") is True
        assert finished.wait(0.5), (
            "stub ack waiter was not released by reconnect cleanup"
        )
        worker.join(timeout=0.1)

        assert result["error"] is None
        assert rt._pending_stub_acks == {}

    def test_late_ack_with_wrong_operation_does_not_release_new_waiter(self) -> None:
        from plushie.runtime import _StubAckWaiter

        rt = self._make_runtime()
        waiter = _StubAckWaiter(registered=True, generation=rt._stub_ack_generation)
        rt._pending_stub_acks["file_open"] = waiter

        rt._handle_effect_stub_ack(EffectStubAck(kind="file_open", registered=False))

        assert rt._pending_stub_acks["file_open"] is waiter
        assert waiter.acknowledged is False
        assert waiter.done.is_set() is False

        rt._handle_effect_stub_ack(EffectStubAck(kind="file_open", registered=True))

        assert rt._pending_stub_acks == {}
        assert waiter.acknowledged is True
        assert waiter.done.is_set() is True

    def test_late_ack_with_old_generation_does_not_release_new_waiter(self) -> None:
        from plushie.runtime import _StubAckWaiter

        rt = self._make_runtime()
        old_generation = rt._stub_ack_generation
        old_waiter = _StubAckWaiter(registered=True, generation=old_generation)
        rt._pending_stub_acks["file_open"] = old_waiter

        rt._flush_pending_stub_acks()

        new_generation = rt._stub_ack_generation
        new_waiter = _StubAckWaiter(registered=True, generation=new_generation)
        rt._pending_stub_acks["file_open"] = new_waiter

        rt._handle_effect_stub_ack(
            EffectStubAck(kind="file_open", registered=True),
            generation=old_generation,
        )

        assert old_waiter.acknowledged is False
        assert old_waiter.done.is_set() is True
        assert rt._pending_stub_acks["file_open"] is new_waiter
        assert new_waiter.acknowledged is False
        assert new_waiter.done.is_set() is False

        rt._handle_effect_stub_ack(
            EffectStubAck(kind="file_open", registered=True),
            generation=new_generation,
        )

        assert rt._pending_stub_acks == {}
        assert new_waiter.acknowledged is True
        assert new_waiter.done.is_set() is True

    def test_timed_out_waiter_only_retires_itself(self) -> None:
        from plushie.runtime import _StubAckWaiter

        rt = self._make_runtime()
        old_waiter = _StubAckWaiter(registered=True, generation=rt._stub_ack_generation)
        new_waiter = _StubAckWaiter(registered=True, generation=rt._stub_ack_generation)
        rt._pending_stub_acks["file_open"] = new_waiter

        assert rt._retire_stub_ack_waiter("file_open", old_waiter) is False

        assert rt._pending_stub_acks["file_open"] is new_waiter
        assert rt._stale_stub_acks == {}

    def test_late_timed_out_ack_does_not_release_later_waiter(self) -> None:
        from plushie.runtime import _StubAckWaiter

        rt = self._make_runtime()
        old_waiter = _StubAckWaiter(registered=True, generation=rt._stub_ack_generation)
        rt._pending_stub_acks["file_open"] = old_waiter

        assert rt._retire_stub_ack_waiter("file_open", old_waiter) is True

        new_waiter = _StubAckWaiter(registered=True, generation=rt._stub_ack_generation)
        rt._pending_stub_acks["file_open"] = new_waiter

        rt._handle_effect_stub_ack(EffectStubAck(kind="file_open", registered=True))

        assert rt._pending_stub_acks["file_open"] is new_waiter
        assert new_waiter.acknowledged is False
        assert new_waiter.done.is_set() is False
        assert rt._stale_stub_acks == {}

        rt._handle_effect_stub_ack(EffectStubAck(kind="file_open", registered=True))

        assert rt._pending_stub_acks == {}
        assert new_waiter.acknowledged is True
        assert new_waiter.done.is_set() is True


class TestAwaitAsyncCleanup:
    def _make_runtime(self) -> Any:
        from unittest.mock import MagicMock

        from plushie.runtime import Runtime

        builder = create_app("AwaitAsyncCleanupTest")

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, _event: object) -> int:
            return model

        @builder.view
        def _view(_model: int) -> dict[str, Any]:
            return {"id": "root", "type": "container", "props": {}, "children": []}

        conn = MagicMock()
        conn.session = ""
        conn.restart.return_value = None
        conn.send_settings.return_value = None
        conn.wait_hello.return_value = None
        conn.send_snapshot.return_value = None

        rt = Runtime(builder, conn)
        rt._model = 0
        rt._start_reader = lambda: None
        return rt

    def test_await_async_timeout_removes_waiter(self) -> None:
        rt = self._make_runtime()
        future: Future[Any] = Future()
        rt._async_tasks["load"] = (future, 1)

        assert rt.await_async("load", timeout=0.001) is False
        assert rt._pending_await_async == {}

    def test_reconnect_releases_pending_await_async_waiter_without_completion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rt = self._make_runtime()
        future: Future[Any] = Future()
        rt._async_tasks["load"] = (future, 1)

        finished = threading.Event()
        result: dict[str, Any] = {"value": None}

        def call() -> None:
            result["value"] = rt.await_async("load", timeout=5.0)
            finished.set()

        worker = threading.Thread(target=call, daemon=True)
        worker.start()

        for _ in range(100):
            if "load" in rt._pending_await_async:
                break
            threading.Event().wait(0.01)
        else:  # pragma: no cover - test would fail below anyway
            pytest.fail("await_async waiter was never registered")

        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is True
        assert finished.wait(0.5)
        worker.join(timeout=0.1)

        assert result["value"] is False
        assert rt._async_tasks["load"] == (future, 1)
        assert rt._pending_await_async == {}


class TestReconnectWidgetRegistry:
    def _make_runtime(
        self,
        *,
        initial_widget_ids: tuple[str, ...] = ("probe",),
        reconnect_widget_ids: tuple[str, ...] | None = None,
    ) -> Any:
        from unittest.mock import MagicMock

        from plushie.runtime import Runtime
        from plushie.tree import normalize_view
        from plushie.widget import WidgetDef, derive_registry

        class StatefulWidget(WidgetDef):
            def init(self, props: dict[str, Any]) -> dict[str, Any]:
                _ = props
                return {"value": "fresh"}

            def view(
                self, widget_id: str, props: dict[str, Any], state: dict[str, Any]
            ) -> dict[str, Any]:
                _ = props
                return {
                    "id": widget_id,
                    "type": "text",
                    "props": {"content": state["value"]},
                    "children": [],
                }

            def subscribe(
                self, props: dict[str, Any], state: dict[str, Any]
            ) -> list[Subscription]:
                _ = props, state
                return [Subscription.on_key_press(max_rate=30)]

        builder = create_app("ReconnectWidgetRegistryTest")
        next_widget_ids = (
            reconnect_widget_ids
            if reconnect_widget_ids is not None
            else initial_widget_ids
        )

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, _event: object) -> int:
            return model

        @builder.view
        def _view(model: int) -> dict[str, Any]:
            widget_ids = initial_widget_ids if model == 0 else next_widget_ids
            return {
                "id": "main",
                "type": "window",
                "props": {},
                "children": [
                    StatefulWidget.build(widget_id) for widget_id in widget_ids
                ],
            }

        @builder.handle_renderer_exit
        def _handle_renderer_exit(model: int, _reason: Any) -> int:
            return 1 if reconnect_widget_ids is not None else model

        conn = MagicMock()
        conn.session = ""
        conn.restart.return_value = None
        conn.send_settings.return_value = None
        conn.wait_hello.return_value = None
        conn.send_snapshot.return_value = None

        rt = Runtime(builder, conn)
        old_tree = normalize_view(rt._app.view(0), registry={})
        old_registry = derive_registry(old_tree)
        for entry in old_registry.values():
            entry.state["value"] = "old"
        old_tree = normalize_view(rt._app.view(0), registry=old_registry)
        old_registry = derive_registry(old_tree)

        rt._model = 0
        rt._tree = old_tree
        rt._widget_registry = old_registry
        rt._memo_cache_prev = {"memo": "old"}
        rt._widget_cache_prev = {"widget": "old"}
        rt._windows = {"main"}
        rt._start_reader = lambda: None
        return rt

    def test_successful_reconnect_preserves_widget_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rt = self._make_runtime()
        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is True

        snapshot = rt._conn.send_snapshot.call_args.args[0]
        assert snapshot["children"][0]["props"]["content"] == "old"
        assert rt._widget_registry[("main", "main#probe")].state == {"value": "old"}
        assert rt._memo_cache_prev == {}
        assert rt._widget_cache_prev == {}

    def test_successful_reconnect_prunes_removed_widgets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rt = self._make_runtime(
            initial_widget_ids=("probe", "removed"),
            reconnect_widget_ids=("probe",),
        )
        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is True

        snapshot = rt._conn.send_snapshot.call_args.args[0]
        assert [child["id"] for child in snapshot["children"]] == ["main#probe"]
        assert rt._widget_registry[("main", "main#probe")].state == {"value": "old"}
        assert ("main", "main#removed") not in rt._widget_registry

    def test_reconnect_replay_failure_restores_previous_widget_registry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rt = self._make_runtime()
        old_registry = dict(rt._widget_registry)
        old_tree = rt._tree
        rt._conn.send_snapshot.side_effect = RuntimeError("snapshot failed")
        rt._MAX_RESTART_ATTEMPTS = 1
        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is False

        assert rt._tree is old_tree
        assert rt._widget_registry == old_registry
        assert rt._widget_registry[("main", "main#probe")].state == {"value": "old"}
        assert rt._memo_cache_prev == {"memo": "old"}
        assert rt._widget_cache_prev == {"widget": "old"}

    def test_reconnect_view_failure_fallback_keeps_widget_registry_and_subscriptions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rt = self._make_runtime()
        old_tree = rt._tree
        old_registry = dict(rt._widget_registry)

        def fail_view(_model: int) -> dict[str, Any]:
            raise RuntimeError("view failed")

        rt._app.view = fail_view  # type: ignore[method-assign]
        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is True

        snapshot = rt._conn.send_snapshot.call_args.args[0]
        assert snapshot is old_tree
        assert rt._widget_registry == old_registry
        assert rt._widget_registry[("main", "main#probe")].state == {"value": "old"}
        assert rt._subscription_keys == [("on_key_press", "")]
        assert rt._subscriptions[("on_key_press", "")].max_rate == 30
        assert rt._memo_cache_prev == {"memo": "old"}
        assert rt._widget_cache_prev == {"widget": "old"}


class TestReconnectSequencing:
    def _make_runtime(
        self,
        *,
        handle_renderer_exit: Any,
        update: Any,
    ) -> Any:
        from unittest.mock import MagicMock

        from plushie.runtime import Runtime

        builder = create_app("ReconnectSequencingTest")

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, event: Any) -> int:
            return update(model, event)

        @builder.view
        def _view(model: int) -> dict[str, Any]:
            return {
                "id": "root",
                "type": "container",
                "props": {"value": model},
                "children": [],
            }

        @builder.handle_renderer_exit
        def _handle_renderer_exit(model: int, reason: Any) -> int:
            return handle_renderer_exit(model, reason)

        conn = MagicMock()
        conn.session = ""
        conn.send_settings.return_value = None
        conn.wait_hello.return_value = None
        conn.send_snapshot.return_value = None

        rt = Runtime(builder, conn)
        rt._model = 5
        rt._tree = {
            "id": "root",
            "type": "container",
            "props": {"value": 5},
            "children": [],
        }
        rt._widget_registry = {}
        rt._subscriptions = {}
        rt._subscription_keys = []
        rt._windows = {"main"}
        rt._widget_statuses = {"btn": "focused"}
        rt._focused_widget_id = "btn"
        rt._start_reader = lambda: None
        return rt

    def test_failed_reconnect_preserves_local_state_until_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeTimer:
            def __init__(self) -> None:
                self.cancelled = False

            def cancel(self) -> None:
                self.cancelled = True

        def update(model: int, event: Any) -> int:
            match event:
                case EffectResult(result=RendererRestarted()):
                    return model + 10
                case RecoveryFailed():
                    return model + 100
                case _:
                    return model

        rt = self._make_runtime(
            handle_renderer_exit=lambda model, _reason: model + 1,
            update=update,
        )
        rt._conn.restart.side_effect = RuntimeError("boom")
        rt._pending_effects["wire-1"] = {
            "tag": "reload",
            "kind": "file_open",
            "timer": FakeTimer(),
        }
        rt._subscriptions = {
            ("every", "100", "tick"): rt._start_subscription(
                Subscription.every(100, "tick")
            )
        }
        rt._subscription_keys = [("every", "100", "tick")]

        old_tree = rt._tree
        old_subscriptions = dict(rt._subscriptions)
        old_windows = set(rt._windows)
        old_statuses = dict(rt._widget_statuses)
        old_focus = rt._focused_widget_id

        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is False
        assert rt._model == 5
        assert rt._tree == old_tree
        assert rt._windows == old_windows
        assert rt._widget_statuses == old_statuses
        assert rt._focused_widget_id == old_focus
        assert rt._subscriptions == old_subscriptions
        assert rt._pending_effects == {}

    def test_reconnect_replay_failure_restores_local_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeTimer:
            created: ClassVar[list[FakeTimer]] = []

            def __init__(self, interval: float, callback: Any) -> None:
                self.interval = interval
                self.callback = callback
                self.daemon = False
                self.started = False
                self.cancelled = False
                FakeTimer.created.append(self)

            def start(self) -> None:
                self.started = True

            def cancel(self) -> None:
                self.cancelled = True

        monkeypatch.setattr("plushie.runtime.threading.Timer", FakeTimer)

        rt = self._make_runtime(
            handle_renderer_exit=lambda model, _reason: model + 1,
            update=lambda model, _event: model,
        )
        rt._conn.restart.return_value = None
        rt._MAX_RESTART_ATTEMPTS = 1
        rt._subscriptions = {
            ("every", "100", "tick"): rt._start_subscription(
                Subscription.every(100, "tick")
            )
        }
        rt._subscription_keys = [("every", "100", "tick")]
        rt._memo_cache_prev = {"memo": "old"}
        rt._widget_cache_prev = {"widget": "old"}

        old_timer = rt._subscriptions[("every", "100", "tick")].timer
        assert old_timer is not None

        def fail_snapshot(_tree: dict[str, Any]) -> None:
            old_timer.callback()
            raise RuntimeError("snapshot failed")

        rt._conn.send_snapshot.side_effect = fail_snapshot

        old_tree = rt._tree
        old_subscriptions = dict(rt._subscriptions)
        old_windows = set(rt._windows)
        old_statuses = dict(rt._widget_statuses)
        old_focus = rt._focused_widget_id

        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is False
        assert rt._model == 5
        assert rt._tree == old_tree
        assert rt._windows == old_windows
        assert rt._widget_statuses == old_statuses
        assert rt._focused_widget_id == old_focus
        restored_entry = rt._subscriptions[("every", "100", "tick")]
        assert restored_entry.token == old_subscriptions[("every", "100", "tick")].token
        assert restored_entry.timer is not None
        assert restored_entry.timer is not old_timer
        assert restored_entry.timer.started is True
        assert rt._memo_cache_prev == {"memo": "old"}
        assert rt._widget_cache_prev == {"widget": "old"}

    def test_reconnect_subscribe_failure_preserves_existing_subscriptions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeTimer:
            created: ClassVar[list[FakeTimer]] = []

            def __init__(self, interval: float, callback: Any) -> None:
                self.interval = interval
                self.callback = callback
                self.daemon = False
                self.started = False
                self.cancelled = False
                FakeTimer.created.append(self)

            def start(self) -> None:
                self.started = True

            def cancel(self) -> None:
                self.cancelled = True

        def update(model: int, event: Any) -> int:
            match event:
                case EffectResult(result=RendererRestarted()):
                    return model + 10
                case _:
                    return model

        monkeypatch.setattr("plushie.runtime.threading.Timer", FakeTimer)

        rt = self._make_runtime(
            handle_renderer_exit=lambda model, _reason: model + 1,
            update=update,
        )
        rt._conn.restart.return_value = None
        rt._MAX_RESTART_ATTEMPTS = 1
        rt._pending_effects["wire-1"] = {
            "tag": "reload",
            "kind": "file_open",
            "timer": FakeTimer(0.1, lambda: None),
        }
        rt._subscriptions = {
            ("every", "100", "tick"): rt._start_subscription(
                Subscription.every(100, "tick")
            )
        }
        rt._subscription_keys = [("every", "100", "tick")]

        old_entry = rt._subscriptions[("every", "100", "tick")]
        old_timer = old_entry.timer
        assert old_timer is not None

        def fail_subscribe(_model: int) -> list[Subscription]:
            raise RuntimeError("subscribe failed")

        rt._app.subscribe = fail_subscribe  # type: ignore[method-assign]

        reader_started = False

        def start_reader() -> None:
            nonlocal reader_started
            reader_started = True

        rt._start_reader = start_reader

        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is False
        assert rt._model == 5
        assert reader_started is False
        assert rt._subscription_keys == [("every", "100", "tick")]

        restored_entry = rt._subscriptions[("every", "100", "tick")]
        assert restored_entry.token == old_entry.token
        assert restored_entry.timer is not None
        assert restored_entry.timer is not old_timer
        assert restored_entry.timer.started is True

    def test_successful_reconnect_commits_recovered_state_and_effect_flush(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeTimer:
            def __init__(self) -> None:
                self.cancelled = False

            def cancel(self) -> None:
                self.cancelled = True

        def update(model: int, event: Any) -> int:
            match event:
                case EffectResult(result=RendererRestarted()):
                    return model + 10
                case _:
                    return model

        rt = self._make_runtime(
            handle_renderer_exit=lambda model, _reason: model + 1,
            update=update,
        )
        rt._conn.restart.return_value = None
        rt._pending_effects["wire-1"] = {
            "tag": "reload",
            "kind": "file_open",
            "timer": FakeTimer(),
        }

        monkeypatch.setattr("plushie.runtime.time.sleep", lambda _seconds: None)

        assert rt._attempt_reconnect("renderer_crashed") is True
        assert rt._model == 16
        assert rt._widget_statuses == {}
        assert rt._focused_widget_id is None


class TestRuntimeConcurrency:
    def _make_runtime(self) -> Any:
        from unittest.mock import MagicMock

        from plushie.runtime import Runtime

        builder = create_app("RuntimeConcurrencyTest")

        @builder.init
        def _init() -> int:
            return 0

        @builder.update
        def _update(model: int, _event: object) -> int:
            return model

        @builder.view
        def _view(_model: int) -> dict[str, Any]:
            return {"id": "root", "type": "container", "props": {}, "children": []}

        conn = MagicMock()
        conn.session = ""
        return Runtime(builder, conn)

    def test_stale_timer_callback_does_not_rearm_new_occupant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeTimer:
            created: ClassVar[list[FakeTimer]] = []

            def __init__(self, interval: float, callback: Any) -> None:
                self.interval = interval
                self.callback = callback
                self.daemon = False
                self.started = False
                self.cancelled = False
                FakeTimer.created.append(self)

            def start(self) -> None:
                self.started = True

            def cancel(self) -> None:
                self.cancelled = True

        monkeypatch.setattr("plushie.runtime.threading.Timer", FakeTimer)

        rt = self._make_runtime()
        spec = Subscription.every(100, "tick")
        subscriptions: list[Subscription] = [spec]
        rt._app.subscribe = lambda _model: list(subscriptions)  # type: ignore[method-assign]

        rt._sync_subscriptions(0)
        with rt._subscriptions_lock:
            old_entry = rt._subscriptions[spec.key]

        subscriptions.clear()
        rt._sync_subscriptions(0)

        subscriptions.append(spec)
        rt._sync_subscriptions(0)
        with rt._subscriptions_lock:
            new_entry = rt._subscriptions[spec.key]

        assert old_entry.token != new_entry.token
        created_before = len(FakeTimer.created)
        old_timer = old_entry.timer
        assert old_timer is not None

        old_timer.callback()

        assert len(FakeTimer.created) == created_before
        with rt._subscriptions_lock:
            current = rt._subscriptions[spec.key]
        assert current is new_entry
        assert current.token == new_entry.token
        assert current.timer is new_entry.timer
        assert rt._queue.empty()

    def test_concurrent_interact_rejects_second_caller(self) -> None:
        rt = self._make_runtime()
        sent = threading.Event()
        first_error: list[BaseException] = []

        def send(_msg: dict[str, Any]) -> None:
            sent.set()

        rt._conn.send.side_effect = send

        def first_call() -> None:
            try:
                rt.interact("click", timeout=0.5)
            except BaseException as exc:  # pragma: no cover - asserted below
                first_error.append(exc)

        worker = threading.Thread(target=first_call, daemon=True)
        worker.start()

        assert sent.wait(0.5), "first interact did not reach send()"

        with pytest.raises(RuntimeError, match="already in progress"):
            rt.interact("click", timeout=0.1)

        rt._fail_pending_interact()
        worker.join(timeout=0.5)
        assert not worker.is_alive()
        assert len(first_error) == 1
        assert str(first_error[0]) == "renderer exited during interact('click')"

    def test_runtime_handle_stop_uses_runtime_stop_path(self) -> None:
        from unittest.mock import MagicMock

        from plushie.runtime import RuntimeHandle

        rt = self._make_runtime()
        stop = MagicMock()
        rt.stop = stop  # type: ignore[method-assign]

        handle = RuntimeHandle(rt, threading.Thread())
        handle.stop()

        stop.assert_called_once_with()
