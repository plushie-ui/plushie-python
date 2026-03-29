"""Tests for plushie.runtime -- non-binary logic tests.

Tests the pure-logic parts of the runtime: unwrap_result, window
detection, coalescing, subscription diffing, and the App ABC.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from plushie.app import App, AppBuilder, create_app
from plushie.commands import Command
from plushie.events import (
    AsyncResult,
    Click,
    MouseMove,
    SensorResize,
    TimerTick,
)
from plushie.runtime import (
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

    def test_mouse_move(self) -> None:
        event = MouseMove(x=10.0, y=20.0)
        assert coalesce_key(event) == ("mouse_move",)

    def test_sensor_resize(self) -> None:
        event = SensorResize(id="s1", window_id="main", width=100.0, height=200.0)
        assert coalesce_key(event) == ("sensor_resize", "main", "s1")

    def test_different_sensors_different_keys(self) -> None:
        e1 = SensorResize(id="s1", window_id="main", width=100.0, height=200.0)
        e2 = SensorResize(id="s2", window_id="main", width=100.0, height=200.0)
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
        s = Subscription.on_key_press("keys")
        assert s.key == ("on_key_press", "keys")

    def test_same_kind_different_tag(self) -> None:
        s1 = Subscription.on_key_press("a")
        s2 = Subscription.on_key_press("b")
        assert s1.key != s2.key

    def test_max_rate_not_in_key(self) -> None:
        """max_rate is not part of the key -- same sub, different rate."""
        s1 = Subscription.on_mouse_move("m", max_rate=30)
        s2 = Subscription.on_mouse_move("m", max_rate=60)
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
