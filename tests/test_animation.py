"""Tests for plushie.animation."""

from __future__ import annotations

from plushie.animation import (
    FINISHED,
    Animation,
    ease_in,
    ease_in_out,
    ease_in_out_quad,
    ease_in_quad,
    ease_out,
    ease_out_quad,
    interpolate,
    linear,
    spring,
)


class TestEasingFunctions:
    """Each easing function maps 0->0 and 1->1."""

    def test_linear(self) -> None:
        assert linear(0.0) == 0.0
        assert linear(0.5) == 0.5
        assert linear(1.0) == 1.0

    def test_ease_in(self) -> None:
        assert ease_in(0.0) == 0.0
        assert ease_in(1.0) == 1.0
        assert ease_in(0.5) < 0.5  # cubic starts slow

    def test_ease_out(self) -> None:
        assert ease_out(0.0) == 0.0
        assert ease_out(1.0) == 1.0
        assert ease_out(0.5) > 0.5  # cubic ends slow

    def test_ease_in_out(self) -> None:
        assert ease_in_out(0.0) == 0.0
        assert ease_in_out(1.0) == 1.0
        assert ease_in_out(0.5) == 0.5  # symmetric midpoint

    def test_ease_in_quad(self) -> None:
        assert ease_in_quad(0.0) == 0.0
        assert ease_in_quad(1.0) == 1.0
        assert ease_in_quad(0.5) == 0.25

    def test_ease_out_quad(self) -> None:
        assert ease_out_quad(0.0) == 0.0
        assert ease_out_quad(1.0) == 1.0
        assert ease_out_quad(0.5) == 0.75

    def test_ease_in_out_quad(self) -> None:
        assert ease_in_out_quad(0.0) == 0.0
        assert ease_in_out_quad(1.0) == 1.0
        assert ease_in_out_quad(0.5) == 0.5

    def test_spring_boundaries(self) -> None:
        assert spring(0.0) == 0.0
        assert spring(1.0) == 1.0

    def test_spring_overshoots(self) -> None:
        # Spring should overshoot past 1.0 at some point
        overshoot = any(spring(t / 100) > 1.0 for t in range(1, 100))
        assert overshoot


class TestInterpolate:
    def test_basic_lerp(self) -> None:
        assert interpolate(0.0, 100.0, 0.0) == 0.0
        assert interpolate(0.0, 100.0, 0.5) == 50.0
        assert interpolate(0.0, 100.0, 1.0) == 100.0

    def test_with_easing(self) -> None:
        result = interpolate(0.0, 100.0, 0.5, ease_in)
        assert result == 12.5  # 0.5^3 * 100

    def test_clamps_below_zero(self) -> None:
        assert interpolate(0.0, 100.0, -1.0) == 0.0

    def test_clamps_above_one(self) -> None:
        assert interpolate(0.0, 100.0, 2.0) == 100.0

    def test_reverse_direction(self) -> None:
        assert interpolate(100.0, 0.0, 0.5) == 50.0


class TestAnimationNew:
    def test_creates_with_defaults(self) -> None:
        anim = Animation.new(0.0, 1.0, 300)
        assert anim.from_val == 0.0
        assert anim.to_val == 1.0
        assert anim.duration_ms == 300
        assert anim.started_at is None
        assert anim.value() == 0.0

    def test_rejects_zero_duration(self) -> None:
        try:
            Animation.new(0.0, 1.0, 0)
            msg = "expected ValueError"
            raise AssertionError(msg)
        except ValueError:
            pass

    def test_custom_easing(self) -> None:
        anim = Animation.new(0.0, 1.0, 300, easing=ease_out)
        assert anim.easing is ease_out


class TestAnimationLifecycle:
    def test_start_sets_timestamp(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000)
        started = anim.start(500)
        assert started.started_at == 500
        assert started.value() == 0.0

    def test_advance_before_start_returns_unchanged(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000)
        val, result = anim.advance(999)
        assert val == 0.0
        assert result is anim

    def test_advance_midway(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000).start(0)
        val, result = anim.advance(500)
        assert val == 50.0
        assert isinstance(result, Animation)
        assert result.value() == 50.0

    def test_advance_to_completion(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000).start(0)
        val, result = anim.advance(1000)
        assert val == 100.0
        assert result is FINISHED

    def test_advance_past_end(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000).start(0)
        val, result = anim.advance(2000)
        assert val == 100.0
        assert result is FINISHED

    def test_finished_not_started(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000)
        assert anim.finished() is False

    def test_finished_after_reaching_target(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000).start(0)
        # Advance to just before end -- not finished yet
        _, mid = anim.advance(500)
        assert isinstance(mid, Animation)
        assert mid.finished() is False

    def test_restart_resets(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000).start(0)
        _, mid = anim.advance(500)
        assert isinstance(mid, Animation)
        restarted = mid.start(1000)
        assert restarted.value() == 0.0
        assert restarted.started_at == 1000

    def test_with_easing(self) -> None:
        anim = Animation.new(0.0, 100.0, 1000, easing=ease_in_quad).start(0)
        val, _ = anim.advance(500)
        # ease_in_quad(0.5) = 0.25, so 0 + 100 * 0.25 = 25.0
        assert val == 25.0

    def test_is_frozen(self) -> None:
        anim = Animation.new(0.0, 1.0, 100)
        try:
            anim.from_val = 99.0  # type: ignore[misc]
            msg = "expected FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass
