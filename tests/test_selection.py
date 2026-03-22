"""Tests for plushie.selection."""

from __future__ import annotations

from plushie.selection import Selection


class TestNew:
    def test_defaults(self) -> None:
        sel = Selection.new()
        assert sel.mode == "single"
        assert sel.selected() == frozenset()
        assert sel.anchor is None
        assert sel.order == ()

    def test_custom_mode_and_order(self) -> None:
        sel = Selection.new(mode="range", order=["a", "b", "c"])
        assert sel.mode == "range"
        assert sel.order == ("a", "b", "c")


class TestSingleMode:
    def test_select_replaces(self) -> None:
        sel = Selection.new().select("a")
        assert sel.selected() == frozenset({"a"})
        sel = sel.select("b")
        assert sel.selected() == frozenset({"b"})

    def test_toggle_on_and_off(self) -> None:
        sel = Selection.new().select("a")
        sel = sel.toggle("a")
        assert sel.selected() == frozenset()
        assert sel.anchor is None

    def test_toggle_adds_when_empty(self) -> None:
        sel = Selection.new().toggle("x")
        assert sel.selected() == frozenset({"x"})

    def test_deselect(self) -> None:
        sel = Selection.new().select("a")
        sel = sel.deselect("a")
        assert sel.selected() == frozenset()

    def test_clear(self) -> None:
        sel = Selection.new().select("a")
        sel = sel.clear()
        assert sel.selected() == frozenset()
        assert sel.anchor is None


class TestMultiMode:
    def test_select_without_extend_replaces(self) -> None:
        sel = Selection.new(mode="multi").select("a")
        sel = sel.select("b")
        assert sel.selected() == frozenset({"b"})

    def test_select_with_extend_adds(self) -> None:
        sel = Selection.new(mode="multi").select("a")
        sel = sel.select("b", extend=True)
        assert sel.selected() == frozenset({"a", "b"})

    def test_toggle_adds_and_removes(self) -> None:
        sel = Selection.new(mode="multi").toggle("a")
        assert sel.selected() == frozenset({"a"})
        sel = sel.toggle("b")
        assert sel.selected() == frozenset({"a", "b"})
        sel = sel.toggle("a")
        assert sel.selected() == frozenset({"b"})

    def test_select_all(self) -> None:
        sel = Selection.new(mode="multi", order=["a", "b", "c"]).select_all()
        assert sel.selected() == frozenset({"a", "b", "c"})


class TestRangeMode:
    def test_range_select_from_anchor(self) -> None:
        sel = Selection.new(mode="range", order=["a", "b", "c", "d", "e"])
        sel = sel.select("b")
        sel = sel.range_select("d")
        assert sel.selected() == frozenset({"b", "c", "d"})

    def test_range_select_backwards(self) -> None:
        sel = Selection.new(mode="range", order=["a", "b", "c", "d", "e"])
        sel = sel.select("d")
        sel = sel.range_select("b")
        assert sel.selected() == frozenset({"b", "c", "d"})

    def test_range_select_no_anchor(self) -> None:
        sel = Selection.new(mode="range", order=["a", "b", "c"])
        sel = sel.range_select("b")
        assert sel.selected() == frozenset({"b"})
        assert sel.anchor == "b"

    def test_range_select_unknown_anchor(self) -> None:
        sel = Selection.new(mode="range", order=["a", "b", "c"])
        # Manually set anchor to something not in order
        sel = sel.select("z")
        sel = sel.range_select("b")
        assert sel.selected() == frozenset({"b"})


class TestIsSelected:
    def test_returns_true_for_selected(self) -> None:
        sel = Selection.new().select("a")
        assert sel.is_selected("a") is True

    def test_returns_false_for_unselected(self) -> None:
        sel = Selection.new().select("a")
        assert sel.is_selected("b") is False


class TestFrozen:
    def test_is_frozen(self) -> None:
        sel = Selection.new()
        try:
            sel.mode = "multi"  # type: ignore[misc]
            msg = "expected FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass
