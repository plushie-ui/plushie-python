"""Tests for plushie.subscriptions."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from plushie.subscriptions import Subscription

type _SubFactory = Callable[..., Subscription]


class TestEvery:
    def test_basic(self) -> None:
        sub = Subscription.every(16, "tick")
        assert sub.kind == "every"
        assert sub.tag == "tick"
        assert sub.interval_ms == 16
        assert sub.max_rate is None

    def test_key_includes_interval(self) -> None:
        sub = Subscription.every(16, "tick")
        assert sub.key == ("every", "16", "tick")

    def test_different_intervals_different_keys(self) -> None:
        a = Subscription.every(16, "tick")
        b = Subscription.every(32, "tick")
        assert a.key != b.key

    def test_wire_kind(self) -> None:
        sub = Subscription.every(100, "t")
        assert sub.wire_kind == "every"


class TestRendererSubscriptions:
    """Test all renderer subscription factory methods."""

    FACTORIES: ClassVar[list[tuple[str, _SubFactory]]] = [
        ("on_key_press", Subscription.on_key_press),
        ("on_key_release", Subscription.on_key_release),
        ("on_modifiers_changed", Subscription.on_modifiers_changed),
        ("on_mouse_move", Subscription.on_mouse_move),
        ("on_mouse_button", Subscription.on_mouse_button),
        ("on_mouse_scroll", Subscription.on_mouse_scroll),
        ("on_touch", Subscription.on_touch),
        ("on_ime", Subscription.on_ime),
        ("on_window_event", Subscription.on_window_event),
        ("on_window_open", Subscription.on_window_open),
        ("on_window_close", Subscription.on_window_close),
        ("on_window_resize", Subscription.on_window_resize),
        ("on_window_move", Subscription.on_window_move),
        ("on_window_focus", Subscription.on_window_focus),
        ("on_window_unfocus", Subscription.on_window_unfocus),
        ("on_file_drop", Subscription.on_file_drop),
        ("on_animation_frame", Subscription.on_animation_frame),
        ("on_theme_change", Subscription.on_theme_change),
        ("on_event", Subscription.on_event),
    ]

    def test_kind_and_tag(self) -> None:
        for kind, factory in self.FACTORIES:
            sub = factory("t")
            assert sub.kind == kind, f"Failed for {kind}"
            assert sub.tag == "t", f"Failed for {kind}"
            assert sub.interval_ms is None, f"Failed for {kind}"
            assert sub.max_rate is None, f"Failed for {kind}"

    def test_key_is_kind_tag(self) -> None:
        for kind, factory in self.FACTORIES:
            sub = factory("mytag")
            assert sub.key == (kind, "mytag"), f"Failed for {kind}"

    def test_max_rate(self) -> None:
        for kind, factory in self.FACTORIES:
            sub = factory("t", max_rate=60)
            assert sub.max_rate == 60, f"Failed for {kind}"

    def test_wire_kind(self) -> None:
        for kind, factory in self.FACTORIES:
            sub = factory("t")
            assert sub.wire_kind == kind, f"Failed for {kind}"


class TestKeyEquality:
    def test_same_key_equal(self) -> None:
        a = Subscription.on_key_press("keys")
        b = Subscription.on_key_press("keys")
        assert a.key == b.key

    def test_same_kind_different_tag(self) -> None:
        a = Subscription.on_key_press("a")
        b = Subscription.on_key_press("b")
        assert a.key != b.key

    def test_different_kind_same_tag(self) -> None:
        a = Subscription.on_key_press("t")
        b = Subscription.on_key_release("t")
        assert a.key != b.key

    def test_max_rate_does_not_affect_key(self) -> None:
        a = Subscription.on_key_press("t")
        b = Subscription.on_key_press("t", max_rate=60)
        assert a.key == b.key


class TestFrozen:
    def test_subscription_is_frozen(self) -> None:
        sub = Subscription.every(16, "tick")
        try:
            sub.kind = "bad"  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass
