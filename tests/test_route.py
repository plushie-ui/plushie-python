"""Tests for plushie.route."""

from __future__ import annotations

from plushie.route import Route


class TestNew:
    def test_initial_path(self) -> None:
        r = Route.new("home")
        assert r.current() == "home"
        assert r.params() == {}
        assert r.depth == 1

    def test_initial_with_params(self) -> None:
        r = Route.new("home", {"theme": "dark"})
        assert r.params() == {"theme": "dark"}


class TestPush:
    def test_push_changes_current(self) -> None:
        r = Route.new("home").push("settings")
        assert r.current() == "settings"
        assert r.depth == 2

    def test_push_with_params(self) -> None:
        r = Route.new("home").push("settings", {"tab": "general"})
        assert r.params() == {"tab": "general"}

    def test_push_preserves_history(self) -> None:
        r = Route.new("home").push("a").push("b")
        assert r.history() == ["b", "a", "home"]


class TestPop:
    def test_pop_goes_back(self) -> None:
        r = Route.new("home").push("settings")
        r = r.pop()
        assert r.current() == "home"
        assert r.depth == 1

    def test_pop_at_root_is_noop(self) -> None:
        r = Route.new("home")
        r2 = r.pop()
        assert r2.current() == "home"
        assert r2.depth == 1

    def test_pop_multiple(self) -> None:
        r = Route.new("home").push("a").push("b").push("c")
        r = r.pop().pop()
        assert r.current() == "a"


class TestReplace:
    def test_replace_top(self) -> None:
        r = Route.new("home").push("old")
        r = r.replace_top("new", {"x": 1})
        assert r.current() == "new"
        assert r.params() == {"x": 1}
        assert r.depth == 2

    def test_replace_root(self) -> None:
        r = Route.new("home")
        r = r.replace_top("landing")
        assert r.current() == "landing"
        assert r.depth == 1


class TestCanGoBack:
    def test_false_at_root(self) -> None:
        assert Route.new("home").can_go_back is False

    def test_true_after_push(self) -> None:
        assert Route.new("home").push("x").can_go_back is True


class TestFrozen:
    def test_is_frozen(self) -> None:
        r = Route.new("home")
        try:
            r.stack = ()  # type: ignore[misc]
            msg = "expected FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass
