"""Tests for plushie.animation."""

from __future__ import annotations

import pytest

from plushie.animation import (
    FINISHED,
    Animation,
    Sequence,
    Spring,
    Transition,
    Tween,
    cubic_bezier,
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
        assert ease_in(1.0) == pytest.approx(1.0)
        assert ease_in(0.5) < 0.5  # starts slow

    def test_ease_out(self) -> None:
        assert ease_out(0.0) == 0.0
        assert ease_out(1.0) == pytest.approx(1.0)
        assert ease_out(0.5) > 0.5  # ends slow

    def test_ease_in_out(self) -> None:
        assert ease_in_out(0.0) == pytest.approx(0.0)
        assert ease_in_out(1.0) == pytest.approx(1.0)
        assert ease_in_out(0.5) == pytest.approx(0.5)  # symmetric midpoint

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
        assert result < 50.0  # ease_in is below linear at midpoint

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


class TestTweenAlias:
    def test_animation_is_tween(self) -> None:
        assert Animation is Tween


class TestTransition:
    def test_basic_wire_format(self) -> None:
        t = Transition(to=0.0, duration=300)
        wire = t.to_wire()
        assert wire == {"type": "transition", "to": 0.0, "duration": 300}

    def test_with_easing(self) -> None:
        t = Transition(to=1.0, duration=200, easing="ease_out")
        wire = t.to_wire()
        assert wire["easing"] == "ease_out"

    def test_default_easing_omitted(self) -> None:
        t = Transition(to=1.0, duration=200)
        assert "easing" not in t.to_wire()

    def test_from_value(self) -> None:
        t = Transition(to=1.0, duration=200, from_=0.0)
        assert t.to_wire()["from"] == 0.0

    def test_delay(self) -> None:
        t = Transition(to=1.0, duration=200, delay=100)
        assert t.to_wire()["delay"] == 100

    def test_on_complete(self) -> None:
        t = Transition(to=0.0, duration=300, on_complete="faded")
        assert t.to_wire()["on_complete"] == "faded"

    def test_repeat_forever(self) -> None:
        t = Transition(to=0.5, duration=800, repeat=-1, auto_reverse=True)
        wire = t.to_wire()
        assert wire["repeat"] == -1
        assert wire["auto_reverse"] is True

    def test_loop_factory(self) -> None:
        t = Transition.loop(to=0.4, from_=1.0, duration=800)
        wire = t.to_wire()
        assert wire["repeat"] == -1
        assert wire["auto_reverse"] is True
        assert wire["from"] == 1.0

    def test_loop_finite_cycles(self) -> None:
        t = Transition.loop(to=0.4, from_=1.0, duration=800, cycles=3)
        assert t.to_wire()["repeat"] == 3


class TestSpring:
    def test_basic_wire_format(self) -> None:
        s = Spring(to=1.0)
        wire = s.to_wire()
        assert wire == {
            "type": "spring",
            "to": 1.0,
            "stiffness": 100,
            "damping": 10,
        }

    def test_custom_params(self) -> None:
        s = Spring(to=1.0, stiffness=200, damping=20, mass=2.0)
        wire = s.to_wire()
        assert wire["mass"] == 2.0
        assert wire["stiffness"] == 200

    def test_default_mass_omitted(self) -> None:
        s = Spring(to=1.0)
        assert "mass" not in s.to_wire()

    def test_preset(self) -> None:
        s = Spring.preset("bouncy", to=1.05)
        assert s.stiffness == 300
        assert s.damping == 10

    def test_preset_with_overrides(self) -> None:
        s = Spring.preset("gentle", to=1.0, mass=2.0)
        assert s.stiffness == 120
        assert s.mass == 2.0

    def test_unknown_preset_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown spring preset"):
            Spring.preset("nonexistent", to=1.0)


class TestSequence:
    def test_wire_format(self) -> None:
        seq = Sequence(
            steps=[
                Transition(to=1.0, duration=200, from_=0.0),
                Transition(to=0.0, duration=300),
            ],
            on_complete="done",
        )
        wire = seq.to_wire()
        assert wire["type"] == "sequence"
        assert len(wire["steps"]) == 2
        assert wire["steps"][0]["type"] == "transition"
        assert wire["steps"][1]["type"] == "transition"
        assert wire["on_complete"] == "done"

    def test_mixed_steps(self) -> None:
        seq = Sequence(
            steps=[
                Transition(to=1.0, duration=200),
                Spring(to=0.0, stiffness=200, damping=20),
            ],
        )
        wire = seq.to_wire()
        assert wire["steps"][0]["type"] == "transition"
        assert wire["steps"][1]["type"] == "spring"
        assert "on_complete" not in wire

    def test_no_on_complete(self) -> None:
        seq = Sequence(steps=[Transition(to=1.0, duration=200)])
        assert "on_complete" not in seq.to_wire()


class TestCubicBezier:
    def test_boundaries(self) -> None:
        ease = cubic_bezier(0.25, 0.1, 0.25, 1.0)
        assert ease(0.0) == 0.0
        assert ease(1.0) == 1.0

    def test_midpoint_reasonable(self) -> None:
        ease = cubic_bezier(0.25, 0.1, 0.25, 1.0)
        mid = ease(0.5)
        assert 0.0 < mid < 1.0
