"""Tests for the plushie testing framework (non-binary parts).

Tests Element, fixture command processing, pool session management,
selector resolution, key parsing, and assertion helpers without
requiring the plushie binary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from unittest.mock import MagicMock

import pytest

from plushie.commands import Command
from plushie.events import AsyncResult, StreamChunk
from plushie.testing.element import Element, ElementNotFoundError
from plushie.testing.fixture import (
    AppFixture,
    _parse_key,
    _process_commands,
    _resolve_selector,
    _unwrap_update,
)

# ---------------------------------------------------------------------------
# Element tests
# ---------------------------------------------------------------------------


class TestElement:
    """Tests for the Element dataclass."""

    def test_basic_properties(self) -> None:
        node = {
            "id": "btn",
            "type": "button",
            "props": {"label": "Click me"},
            "children": [],
        }
        el = Element(node=node)
        assert el.id == "btn"
        assert el.type == "button"
        assert el.props == {"label": "Click me"}
        assert el.children == []

    def test_missing_keys_have_defaults(self) -> None:
        el = Element(node={})
        assert el.id == ""
        assert el.type == ""
        assert el.props == {}
        assert el.children == []

    def test_text_extracts_content(self) -> None:
        el = Element(node={"props": {"content": "Hello"}})
        assert el.text() == "Hello"

    def test_text_extracts_label(self) -> None:
        el = Element(node={"props": {"label": "Save"}})
        assert el.text() == "Save"

    def test_text_extracts_value(self) -> None:
        el = Element(node={"props": {"value": "typed text"}})
        assert el.text() == "typed text"

    def test_text_extracts_placeholder(self) -> None:
        el = Element(node={"props": {"placeholder": "Enter name..."}})
        assert el.text() == "Enter name..."

    def test_text_priority_order(self) -> None:
        """content wins over label wins over value wins over placeholder."""
        el = Element(
            node={
                "props": {
                    "content": "C",
                    "label": "L",
                    "value": "V",
                    "placeholder": "P",
                }
            }
        )
        assert el.text() == "C"

        el2 = Element(node={"props": {"label": "L", "value": "V"}})
        assert el2.text() == "L"

    def test_text_returns_none_when_no_text(self) -> None:
        el = Element(node={"props": {"width": 100}})
        assert el.text() is None

    def test_text_returns_none_for_non_string_value(self) -> None:
        el = Element(node={"props": {"content": 42}})
        assert el.text() is None

    def test_children_wraps_as_elements(self) -> None:
        node = {
            "children": [
                {"id": "a", "type": "text", "props": {"content": "A"}, "children": []},
                {"id": "b", "type": "text", "props": {"content": "B"}, "children": []},
            ]
        }
        el = Element(node=node)
        children = el.children
        assert len(children) == 2
        assert children[0].id == "a"
        assert children[1].id == "b"

    def test_children_filters_non_dict(self) -> None:
        node = {"children": [{"id": "a"}, "not a dict", None, 42]}
        el = Element(node=node)
        assert len(el.children) == 1

    def test_frozen(self) -> None:
        el = Element(node={"id": "x"})
        with pytest.raises(AttributeError):
            el.node = {}  # type: ignore[misc]

    def test_scoped_id(self) -> None:
        el = Element(node={"id": "form/email"})
        assert el.id == "form/email"


class TestElementNotFoundError:
    def test_is_exception(self) -> None:
        err = ElementNotFoundError("not found: #foo")
        assert isinstance(err, Exception)
        assert "not found" in str(err)


# ---------------------------------------------------------------------------
# unwrap_update tests
# ---------------------------------------------------------------------------


class TestUnwrapUpdate:
    def test_bare_model(self) -> None:
        model, cmds = _unwrap_update(42)
        assert model == 42
        assert cmds == []

    def test_model_with_command(self) -> None:
        cmd = Command.none()
        model, cmds = _unwrap_update((42, cmd))
        assert model == 42
        assert cmds == [cmd]

    def test_model_with_command_list(self) -> None:
        c1 = Command.none()
        c2 = Command.none()
        model, cmds = _unwrap_update((42, [c1, c2]))
        assert model == 42
        assert cmds == [c1, c2]

    def test_model_with_non_command_second_element(self) -> None:
        model, cmds = _unwrap_update((42, "not a command"))
        assert model == 42
        assert cmds == []

    def test_dict_model(self) -> None:
        """Dicts are not tuples, so they're treated as bare models."""
        model, cmds = _unwrap_update({"count": 0})
        assert model == {"count": 0}
        assert cmds == []


# ---------------------------------------------------------------------------
# process_commands tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CounterModel:
    count: int = 0
    data: str = ""


class FakeApp:
    """Minimal fake app for command processing tests."""

    def init(self) -> CounterModel:
        return CounterModel()

    def update(self, model: CounterModel, event: object) -> Any:
        match event:
            case AsyncResult(tag="inc"):
                return replace(model, count=model.count + event.value)
            case StreamChunk(tag="stream"):
                return replace(model, data=model.data + str(event.value))
            case AsyncResult(tag="stream"):
                return replace(model, data=model.data + "_done")
            case str() as s if s == "custom":
                return replace(model, count=model.count + 10)
            case _:
                return model

    def view(self, model: CounterModel) -> dict[str, Any]:
        return {}

    def subscribe(self, model: CounterModel) -> list[Any]:
        return []

    def settings(self) -> dict[str, Any]:
        return {}


class TestProcessCommands:
    def test_none_command(self) -> None:
        app = FakeApp()
        model = CounterModel()
        result = _process_commands(app, model, [Command.none()])  # type: ignore[arg-type]
        assert result == model

    def test_task_command(self) -> None:
        app = FakeApp()
        model = CounterModel()
        cmd = Command.task(lambda: 5, "inc")
        result = _process_commands(app, model, [cmd])  # type: ignore[arg-type]
        assert result.count == 5

    def test_stream_command(self) -> None:
        app = FakeApp()
        model = CounterModel()

        def stream_fn(emit: Any) -> str:
            emit("a")
            emit("b")
            return "final"

        cmd = Command.stream(stream_fn, "stream")
        result = _process_commands(app, model, [cmd])  # type: ignore[arg-type]
        # "a" + "b" from chunks + "_done" from final AsyncResult
        assert result.data == "ab_done"

    def test_done_command(self) -> None:
        app = FakeApp()
        model = CounterModel()
        cmd = Command.done("custom", lambda v: v)
        result = _process_commands(app, model, [cmd])  # type: ignore[arg-type]
        assert result.count == 10

    def test_batch_command(self) -> None:
        app = FakeApp()
        model = CounterModel()
        cmd = Command.batch(
            [
                Command.task(lambda: 3, "inc"),
                Command.task(lambda: 7, "inc"),
            ]
        )
        result = _process_commands(app, model, [cmd])  # type: ignore[arg-type]
        assert result.count == 10

    def test_max_depth_prevents_infinite_loop(self) -> None:
        """Verify that deeply recursive commands terminate."""

        class InfiniteApp:
            def update(self, model: int, event: object) -> Any:
                return model + 1, Command.task(lambda: 1, "inc")

        app = InfiniteApp()
        cmd = Command.task(lambda: 1, "inc")
        # Should not hang; depth limit stops it
        result = _process_commands(app, 0, [cmd])  # type: ignore[arg-type]
        assert isinstance(result, int)
        assert result > 0

    def test_skips_widget_ops(self) -> None:
        app = FakeApp()
        model = CounterModel()
        cmd = Command.focus("some-widget")
        result = _process_commands(app, model, [cmd])  # type: ignore[arg-type]
        assert result == model

    def test_skips_window_ops(self) -> None:
        app = FakeApp()
        model = CounterModel()
        cmd = Command.focus_next()
        result = _process_commands(app, model, [cmd])  # type: ignore[arg-type]
        assert result == model

    def test_empty_commands(self) -> None:
        app = FakeApp()
        model = CounterModel()
        result = _process_commands(app, model, [])  # type: ignore[arg-type]
        assert result == model


# ---------------------------------------------------------------------------
# Selector resolution tests
# ---------------------------------------------------------------------------


class TestResolveSelector:
    def test_id_selector(self) -> None:
        result = _resolve_selector("#save", None)
        assert result == {"by": "id", "value": "save"}

    def test_id_selector_with_tree_lookup(self) -> None:
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [
                {
                    "id": "main",
                    "type": "window",
                    "props": {},
                    "children": [
                        {
                            "id": "form/save",
                            "type": "button",
                            "props": {},
                            "children": [],
                        },
                    ],
                },
            ],
        }
        result = _resolve_selector("#save", tree)
        assert result == {"by": "id", "value": "form/save", "window_id": "main"}

    def test_id_selector_with_slash(self) -> None:
        result = _resolve_selector("#form/save", None)
        assert result == {"by": "id", "value": "form/save"}

    def test_text_selector(self) -> None:
        result = _resolve_selector("Click me", None)
        assert result == {"by": "text", "value": "Click me"}

    def test_id_not_found_in_tree_raises(self) -> None:
        tree = {
            "id": "root",
            "type": "container",
            "props": {},
            "children": [],
        }
        with pytest.raises(ValueError, match="widget not found"):
            _resolve_selector("#missing", tree)


# ---------------------------------------------------------------------------
# Key parsing tests
# ---------------------------------------------------------------------------


class TestParseKey:
    def test_simple_key(self) -> None:
        result = _parse_key("Enter")
        assert result == {"key": "Enter", "modifiers": {}}

    def test_single_modifier(self) -> None:
        result = _parse_key("ctrl+s")
        assert result == {"key": "s", "modifiers": {"ctrl": True}}

    def test_multiple_modifiers(self) -> None:
        result = _parse_key("ctrl+shift+s")
        assert result == {"key": "s", "modifiers": {"ctrl": True, "shift": True}}

    def test_all_modifiers(self) -> None:
        result = _parse_key("ctrl+shift+alt+logo+command+x")
        assert result == {
            "key": "x",
            "modifiers": {
                "ctrl": True,
                "shift": True,
                "alt": True,
                "logo": True,
                "command": True,
            },
        }

    def test_unknown_modifier_ignored(self) -> None:
        result = _parse_key("meta+a")
        assert result == {"key": "a", "modifiers": {}}

    def test_case_insensitive_named_key(self) -> None:
        assert _parse_key("escape")["key"] == "Escape"
        assert _parse_key("ESCAPE")["key"] == "Escape"
        assert _parse_key("Escape")["key"] == "Escape"

    def test_case_insensitive_arrow_keys(self) -> None:
        assert _parse_key("arrowup")["key"] == "ArrowUp"
        assert _parse_key("ARROWUP")["key"] == "ArrowUp"
        assert _parse_key("ArrowUp")["key"] == "ArrowUp"

    def test_single_char_lowercased(self) -> None:
        assert _parse_key("A")["key"] == "a"
        assert _parse_key("a")["key"] == "a"
        assert _parse_key("Z")["key"] == "z"

    def test_modifier_with_case_insensitive_key(self) -> None:
        result = _parse_key("ctrl+escape")
        assert result["key"] == "Escape"
        assert result["modifiers"]["ctrl"] is True

    def test_unknown_named_key_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown key"):
            _parse_key("NotARealKey")


# ---------------------------------------------------------------------------
# Assertion helper tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimpleModel:
    name: str = "world"


class SimpleApp:
    """Minimal app for testing assertion helpers."""

    def init(self) -> SimpleModel:
        return SimpleModel()

    def update(self, model: SimpleModel, event: object) -> SimpleModel:
        return model

    def view(self, model: SimpleModel) -> dict[str, Any]:
        return {
            "id": "main",
            "type": "window",
            "props": {},
            "children": [
                {
                    "id": "greeting",
                    "type": "text",
                    "props": {"content": f"Hello, {model.name}!"},
                    "children": [],
                },
                {
                    "id": "btn",
                    "type": "button",
                    "props": {"label": "Click"},
                    "children": [],
                },
            ],
        }

    def subscribe(self, model: SimpleModel) -> list[Any]:
        return []

    def settings(self) -> dict[str, Any]:
        return {}


def _make_fixture() -> AppFixture[SimpleModel]:
    """Build an AppFixture backed by a stub pool (no binary).

    The mock pool's query_find resolves #id selectors against a
    hard-coded set of known nodes so that exists/find work without
    a real renderer.
    """
    known_nodes: dict[str, dict[str, Any]] = {
        "greeting": {
            "id": "greeting",
            "type": "text",
            "props": {"content": "Hello, world!"},
            "children": [],
        },
        "btn": {
            "id": "btn",
            "type": "button",
            "props": {"label": "Click"},
            "children": [],
        },
    }

    def fake_query_find(
        _session_id: str, selector: Any, **_kw: Any
    ) -> dict[str, Any] | None:
        if isinstance(selector, str) and selector.startswith("#"):
            return known_nodes.get(selector[1:])
        if isinstance(selector, dict) and selector.get("by") == "id":
            return known_nodes.get(selector["value"])
        return None

    pool = MagicMock()
    pool.register.return_value = "test-session-1"
    pool.send_settings = MagicMock()
    pool.send_snapshot = MagicMock()
    pool.unregister = MagicMock()
    pool.query_find.side_effect = fake_query_find
    fixture = AppFixture(SimpleApp(), pool)  # type: ignore[arg-type]
    return fixture


class TestAssertText:
    def test_passes_when_text_matches(self) -> None:
        with _make_fixture() as app:
            app.assert_text("#greeting", "Hello, world!")

    def test_fails_when_text_differs(self) -> None:
        with (
            _make_fixture() as app,
            pytest.raises(AssertionError, match=r"expected.*'Goodbye'.*got.*'Hello"),
        ):
            app.assert_text("#greeting", "Goodbye")

    def test_fails_when_element_not_found(self) -> None:
        with (
            _make_fixture() as app,
            pytest.raises(ValueError, match="widget not found"),
        ):
            app.assert_text("#missing", "anything")


class TestAssertExists:
    def test_passes_when_element_exists(self) -> None:
        with _make_fixture() as app:
            app.assert_exists("#greeting")

    def test_fails_when_element_missing(self) -> None:
        with (
            _make_fixture() as app,
            pytest.raises(AssertionError, match="element not found"),
        ):
            app.assert_exists("#nope")


class TestAssertNotExists:
    def test_passes_when_element_missing(self) -> None:
        with _make_fixture() as app:
            app.assert_not_exists("#nope")

    def test_fails_when_element_exists(self) -> None:
        with (
            _make_fixture() as app,
            pytest.raises(AssertionError, match="unexpectedly exists"),
        ):
            app.assert_not_exists("#greeting")


class TestAssertModel:
    def test_passes_when_model_matches(self) -> None:
        with _make_fixture() as app:
            app.assert_model(SimpleModel())

    def test_fails_when_model_differs(self) -> None:
        with (
            _make_fixture() as app,
            pytest.raises(AssertionError, match=r"expected.*name='other'"),
        ):
            app.assert_model(SimpleModel(name="other"))


class TestSaveScreenshot:
    def test_raises_when_no_data(self) -> None:
        with _make_fixture() as app:
            app._pool.screenshot.return_value = {"hash": "abc123"}  # type: ignore[union-attr]
            with pytest.raises(RuntimeError, match="did not return screenshot data"):
                app.save_screenshot("test_shot")


class TestAssertA11y:
    def test_passes_when_a11y_matches(self) -> None:
        with _make_fixture() as app:
            node = {
                "id": "greeting",
                "type": "text",
                "props": {
                    "content": "Hello",
                    "a11y": {"role": "heading", "level": 1},
                },
                "children": [],
            }
            app._pool.query_find.side_effect = lambda sid, sel, **kw: node  # type: ignore[union-attr]
            app.assert_a11y("#greeting", {"role": "heading", "level": 1})

    def test_fails_when_no_a11y(self) -> None:
        with (
            _make_fixture() as app,
            pytest.raises(AssertionError, match=r"no a11y prop"),
        ):
            app.assert_a11y("#greeting", {"role": "heading"})

    def test_fails_when_a11y_mismatch(self) -> None:
        with _make_fixture() as app:
            node = {
                "id": "greeting",
                "type": "text",
                "props": {"content": "Hello", "a11y": {"role": "heading"}},
                "children": [],
            }
            app._pool.query_find.side_effect = lambda sid, sel, **kw: node  # type: ignore[union-attr]
            with pytest.raises(AssertionError, match=r"role.*mismatch"):
                app.assert_a11y("#greeting", {"role": "button"})


class TestAssertRole:
    def test_passes_when_role_matches_explicit(self) -> None:
        with _make_fixture() as app:
            node = {
                "id": "greeting",
                "type": "text",
                "props": {"content": "Hello", "a11y": {"role": "heading"}},
                "children": [],
            }
            app._pool.query_find.side_effect = lambda sid, sel, **kw: node  # type: ignore[union-attr]
            app.assert_role("#greeting", "heading")

    def test_infers_role_from_type(self) -> None:
        with _make_fixture() as app:
            app.assert_role("#btn", "button")

    def test_fails_when_role_differs(self) -> None:
        with (
            _make_fixture() as app,
            pytest.raises(AssertionError, match=r"expected.*'heading'.*got.*'button'"),
        ):
            app.assert_role("#btn", "heading")


class TestAssertNoDiagnostics:
    def test_passes_when_empty(self) -> None:
        with _make_fixture() as app:
            app.assert_no_diagnostics()

    def test_fails_when_diagnostics_present(self) -> None:
        with _make_fixture() as app:
            from plushie.events import Diagnostic

            app._diagnostics.append(
                Diagnostic(
                    level="warning",
                    element_id="x",
                    code="BAD",
                    message="something wrong",
                )
            )
            with pytest.raises(AssertionError, match=r"Expected no diagnostics"):
                app.assert_no_diagnostics()
