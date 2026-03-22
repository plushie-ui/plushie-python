"""Path-based state management with revision tracking and transactions.

A lightweight wrapper around a plain dict that tracks a monotonically
increasing revision number on every mutation.  Useful for detecting
changes and implementing optimistic concurrency.

Transactions
------------

:meth:`State.begin_transaction` captures a snapshot of the current data
and revision.  Subsequent mutations increment the revision as usual.
:meth:`State.commit_transaction` finalises (bumping the revision once
from the pre-transaction value).  :meth:`State.rollback_transaction`
restores the snapshot exactly.

Example::

    state = State.new({"count": 0})
    state = state.put(["count"], 5)
    state.get(["count"])    # => 5
    state.revision          # => 1
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "State",
]


@dataclass(slots=True)
class State:
    """Mutable state container with revision tracking.

    Create via :meth:`new`.  Mutations return ``self`` for chaining
    but also modify in place (transaction support requires mutability).
    """

    data: dict[str, Any]
    revision: int
    _transaction: dict[str, Any] | None = field(default=None, repr=False)

    # -- Construction -------------------------------------------------------

    @staticmethod
    def new(data: dict[str, Any]) -> State:
        """Create a new state container wrapping *data*.

        The initial revision is 0.

        Example::

            >>> s = State.new({"x": 1})
            >>> s.get(["x"])
            1
            >>> s.revision
            0
        """
        return State(data=copy.deepcopy(data), revision=0)

    # -- Access -------------------------------------------------------------

    def get(self, path: list[str]) -> Any:
        """Read the value at *path* in the state data.

        An empty path returns the entire data dict.  Each element of
        *path* is a key used for successive dict lookups.

        Example::

            >>> s = State.new({"a": {"b": 42}})
            >>> s.get(["a", "b"])
            42
        """
        if not path:
            return self.data
        current: Any = self.data
        for key in path:
            current = current[key]
        return current

    # -- Mutation -----------------------------------------------------------

    def put(self, path: list[str], value: Any) -> State:
        """Set the value at *path*, incrementing the revision."""
        self._set_nested(path, value)
        self.revision += 1
        return self

    def update(self, path: list[str], fn: Callable[[Any], Any]) -> State:
        """Apply *fn* to the value at *path*, incrementing the revision.

        *fn* receives the current value and must return the new value.
        """
        current = self.get(path)
        new_val = fn(current)
        self._set_nested(path, new_val)
        self.revision += 1
        return self

    def delete(self, path: list[str]) -> State:
        """Remove the value at *path*, incrementing the revision."""
        if len(path) == 1:
            del self.data[path[0]]
        else:
            parent = self.get(path[:-1])
            del parent[path[-1]]
        self.revision += 1
        return self

    # -- Transactions -------------------------------------------------------

    def begin_transaction(self) -> State:
        """Capture a snapshot and begin a transaction.

        Raises ``RuntimeError`` if a transaction is already active.
        """
        if self._transaction is not None:
            msg = "transaction already active"
            raise RuntimeError(msg)
        self._transaction = {
            "data": copy.deepcopy(self.data),
            "revision": self.revision,
        }
        return self

    def commit_transaction(self) -> State:
        """Commit the active transaction.

        Sets the revision to one past the pre-transaction value.

        Raises ``RuntimeError`` if no transaction is active.
        """
        if self._transaction is None:
            msg = "no active transaction"
            raise RuntimeError(msg)
        self.revision = self._transaction["revision"] + 1
        self._transaction = None
        return self

    def rollback_transaction(self) -> State:
        """Roll back the active transaction.

        Restores data and revision to their pre-transaction values.

        Raises ``RuntimeError`` if no transaction is active.
        """
        if self._transaction is None:
            msg = "no active transaction"
            raise RuntimeError(msg)
        self.data = self._transaction["data"]
        self.revision = self._transaction["revision"]
        self._transaction = None
        return self

    # -- Private helpers ----------------------------------------------------

    def _set_nested(self, path: list[str], value: Any) -> None:
        """Set a value at an arbitrary nested path."""
        if len(path) == 1:
            self.data[path[0]] = value
            return
        current: Any = self.data
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = value
