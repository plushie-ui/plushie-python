"""Tests for plushie.state."""

from __future__ import annotations

import pytest

from plushie.state import State


class TestNew:
    def test_initial_state(self) -> None:
        s = State.new({"x": 1})
        assert s.get(["x"]) == 1
        assert s.revision == 0

    def test_deep_copies_data(self) -> None:
        original = {"nested": {"a": 1}}
        s = State.new(original)
        original["nested"]["a"] = 999
        assert s.get(["nested", "a"]) == 1


class TestGet:
    def test_empty_path_returns_all(self) -> None:
        s = State.new({"a": 1, "b": 2})
        assert s.get([]) == {"a": 1, "b": 2}

    def test_nested_path(self) -> None:
        s = State.new({"a": {"b": {"c": 42}}})
        assert s.get(["a", "b", "c"]) == 42

    def test_missing_key_raises(self) -> None:
        s = State.new({"a": 1})
        with pytest.raises(KeyError):
            s.get(["z"])


class TestPut:
    def test_put_increments_revision(self) -> None:
        s = State.new({"x": 0})
        s.put(["x"], 5)
        assert s.get(["x"]) == 5
        assert s.revision == 1

    def test_put_nested(self) -> None:
        s = State.new({"a": {"b": 0}})
        s.put(["a", "b"], 99)
        assert s.get(["a", "b"]) == 99

    def test_put_returns_self(self) -> None:
        s = State.new({"x": 0})
        result = s.put(["x"], 1)
        assert result is s


class TestUpdate:
    def test_update_applies_function(self) -> None:
        s = State.new({"count": 10})
        s.update(["count"], lambda v: v + 5)
        assert s.get(["count"]) == 15
        assert s.revision == 1

    def test_update_nested(self) -> None:
        s = State.new({"a": {"b": 2}})
        s.update(["a", "b"], lambda v: v * 3)
        assert s.get(["a", "b"]) == 6


class TestDelete:
    def test_delete_top_level(self) -> None:
        s = State.new({"a": 1, "b": 2})
        s.delete(["a"])
        assert s.get([]) == {"b": 2}
        assert s.revision == 1

    def test_delete_nested(self) -> None:
        s = State.new({"a": {"b": 1, "c": 2}})
        s.delete(["a", "b"])
        assert s.get(["a"]) == {"c": 2}


class TestTransaction:
    def test_commit(self) -> None:
        s = State.new({"x": 0})
        s.begin_transaction()
        s.put(["x"], 1)  # revision -> 1
        s.put(["x"], 2)  # revision -> 2
        s.commit_transaction()
        assert s.get(["x"]) == 2
        # Commit sets revision to old_rev + 1
        assert s.revision == 1

    def test_rollback(self) -> None:
        s = State.new({"x": 0})
        s.put(["x"], 5)  # revision -> 1
        s.begin_transaction()
        s.put(["x"], 99)
        s.put(["x"], 100)
        s.rollback_transaction()
        assert s.get(["x"]) == 5
        assert s.revision == 1

    def test_nested_transaction_raises(self) -> None:
        s = State.new({"x": 0})
        s.begin_transaction()
        with pytest.raises(RuntimeError, match="already active"):
            s.begin_transaction()

    def test_commit_without_transaction_raises(self) -> None:
        s = State.new({"x": 0})
        with pytest.raises(RuntimeError, match="no active"):
            s.commit_transaction()

    def test_rollback_without_transaction_raises(self) -> None:
        s = State.new({"x": 0})
        with pytest.raises(RuntimeError, match="no active"):
            s.rollback_transaction()


class TestRevision:
    def test_increments_on_each_mutation(self) -> None:
        s = State.new({"x": 0})
        assert s.revision == 0
        s.put(["x"], 1)
        assert s.revision == 1
        s.update(["x"], lambda v: v + 1)
        assert s.revision == 2
        s.delete(["x"])
        assert s.revision == 3
