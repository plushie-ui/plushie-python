"""Tests for plushie.undo."""

from __future__ import annotations

from plushie.undo import UndoCommand, UndoStack, set_timestamp_fn


class TestNew:
    def test_initial_state(self) -> None:
        u = UndoStack.new(0)
        assert u.current == 0
        assert u.can_undo is False
        assert u.can_redo is False


class TestApplyAndUndo:
    def test_apply_updates_current(self) -> None:
        u = UndoStack.new(0)
        cmd = UndoCommand(apply_fn=lambda v: v + 1, undo_fn=lambda v: v - 1)
        u = u.apply_command(cmd)
        assert u.current == 1
        assert u.can_undo is True
        assert u.can_redo is False

    def test_undo_reverses(self) -> None:
        u = UndoStack.new(0)
        cmd = UndoCommand(apply_fn=lambda v: v + 1, undo_fn=lambda v: v - 1)
        u = u.apply_command(cmd)
        u = u.undo()
        assert u.current == 0
        assert u.can_undo is False
        assert u.can_redo is True

    def test_redo_reapplies(self) -> None:
        u = UndoStack.new(0)
        cmd = UndoCommand(apply_fn=lambda v: v + 1, undo_fn=lambda v: v - 1)
        u = u.apply_command(cmd)
        u = u.undo()
        u = u.redo()
        assert u.current == 1

    def test_undo_empty_is_noop(self) -> None:
        u = UndoStack.new(42)
        u2 = u.undo()
        assert u2.current == 42

    def test_redo_empty_is_noop(self) -> None:
        u = UndoStack.new(42)
        u2 = u.redo()
        assert u2.current == 42

    def test_apply_clears_redo(self) -> None:
        u = UndoStack.new(0)
        cmd = UndoCommand(apply_fn=lambda v: v + 1, undo_fn=lambda v: v - 1)
        u = u.apply_command(cmd)
        u = u.undo()
        assert u.can_redo is True
        u = u.apply_command(cmd)
        assert u.can_redo is False

    def test_multiple_undo_redo(self) -> None:
        u = UndoStack.new(0)
        add1 = UndoCommand(apply_fn=lambda v: v + 1, undo_fn=lambda v: v - 1)
        mul2 = UndoCommand(apply_fn=lambda v: v * 2, undo_fn=lambda v: v // 2)
        u = u.apply_command(add1)  # 1
        u = u.apply_command(mul2)  # 2
        assert u.current == 2
        u = u.undo()  # 1
        assert u.current == 1
        u = u.undo()  # 0
        assert u.current == 0
        u = u.redo()  # 1
        assert u.current == 1
        u = u.redo()  # 2
        assert u.current == 2


class TestHistory:
    def test_labels_most_recent_first(self) -> None:
        u = UndoStack.new(0)
        u = u.apply_command(
            UndoCommand(apply_fn=lambda v: v, undo_fn=lambda v: v, label="first")
        )
        u = u.apply_command(
            UndoCommand(apply_fn=lambda v: v, undo_fn=lambda v: v, label="second")
        )
        assert u.history() == ["second", "first"]


class TestCoalescing:
    def setup_method(self) -> None:
        self._ts = 0
        set_timestamp_fn(lambda: self._ts)

    def teardown_method(self) -> None:
        import time

        set_timestamp_fn(lambda: int(time.monotonic() * 1000))

    def _tick(self, ms: int) -> None:
        self._ts += ms

    def test_coalesces_within_window(self) -> None:
        u = UndoStack.new("")
        cmd_a = UndoCommand(
            apply_fn=lambda v: v + "a",
            undo_fn=lambda v: v[:-1],
            coalesce="typing",
            coalesce_window_ms=500,
        )
        cmd_b = UndoCommand(
            apply_fn=lambda v: v + "b",
            undo_fn=lambda v: v[:-1],
            coalesce="typing",
            coalesce_window_ms=500,
        )
        u = u.apply_command(cmd_a)
        self._tick(100)
        u = u.apply_command(cmd_b)
        assert u.current == "ab"
        # Single undo should revert both
        u = u.undo()
        assert u.current == ""

    def test_no_coalesce_outside_window(self) -> None:
        u = UndoStack.new("")
        cmd_a = UndoCommand(
            apply_fn=lambda v: v + "a",
            undo_fn=lambda v: v[:-1],
            coalesce="typing",
            coalesce_window_ms=100,
        )
        cmd_b = UndoCommand(
            apply_fn=lambda v: v + "b",
            undo_fn=lambda v: v[:-1],
            coalesce="typing",
            coalesce_window_ms=100,
        )
        u = u.apply_command(cmd_a)
        self._tick(200)
        u = u.apply_command(cmd_b)
        assert u.current == "ab"
        # Two separate undos
        u = u.undo()
        assert u.current == "a"
        u = u.undo()
        assert u.current == ""

    def test_no_coalesce_different_keys(self) -> None:
        u = UndoStack.new(0)
        cmd_a = UndoCommand(
            apply_fn=lambda v: v + 1,
            undo_fn=lambda v: v - 1,
            coalesce="key_a",
            coalesce_window_ms=500,
        )
        cmd_b = UndoCommand(
            apply_fn=lambda v: v + 10,
            undo_fn=lambda v: v - 10,
            coalesce="key_b",
            coalesce_window_ms=500,
        )
        u = u.apply_command(cmd_a)
        u = u.apply_command(cmd_b)
        assert u.current == 11
        u = u.undo()
        assert u.current == 1


class TestFrozen:
    def test_is_frozen(self) -> None:
        u = UndoStack.new(0)
        try:
            u.current = 99  # type: ignore[misc]
            msg = "expected FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass
