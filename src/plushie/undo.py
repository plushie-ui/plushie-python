"""Undo/redo stack for reversible commands.

Pure data structure, no processes.  Each command provides an *apply*
callable and an *undo* callable.  The stack tracks entries so that undo
moves an entry to the redo stack (calling *undo*) and redo moves it
back (calling *apply*).

Coalescing
----------

Commands with the same ``coalesce`` key that arrive within
``coalesce_window_ms`` of each other are merged into a single undo
entry.  The merged entry keeps the *original* undo callable (so one
undo reverses all coalesced changes) and composes the apply callables.

Example::

    u = UndoStack.new(0)
    u = u.apply_command(UndoCommand(apply_fn=lambda v: v + 1, undo_fn=lambda v: v - 1))
    u.current   # => 1
    u = u.undo()
    u.current   # => 0
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

__all__ = [
    "UndoCommand",
    "UndoEntry",
    "UndoStack",
]


@dataclass(frozen=True, slots=True)
class UndoCommand:
    """A reversible command to push onto the undo stack.

    Attributes:
        apply_fn: Function ``(model) -> model`` that applies the change.
        undo_fn: Function ``(model) -> model`` that reverses the change.
        label: Optional human-readable label for history display.
        coalesce: Optional key for merging rapid successive edits.
        coalesce_window_ms: Time window in ms for coalescing (default 0).
    """

    apply_fn: Callable[[Any], Any]
    undo_fn: Callable[[Any], Any]
    label: str | None = None
    coalesce: Any | None = None
    coalesce_window_ms: int = 0


@dataclass(frozen=True, slots=True)
class UndoEntry:
    """Internal stack entry tracking a reversible change."""

    apply_fn: Callable[[Any], Any]
    undo_fn: Callable[[Any], Any]
    label: str | None
    coalesce: Any | None
    timestamp: int


def _default_timestamp() -> int:
    return int(time.monotonic() * 1000)


# Module-level timestamp function; tests can monkey-patch this.
_timestamp_fn: Callable[[], int] = _default_timestamp


def set_timestamp_fn(fn: Callable[[], int]) -> None:
    """Override the timestamp source (for testing)."""
    global _timestamp_fn
    _timestamp_fn = fn


@dataclass(frozen=True, slots=True)
class UndoStack:
    """Immutable undo/redo stack.

    Create via :meth:`new`.  All mutating methods return a new
    ``UndoStack``.
    """

    current: Any
    undo_stack: tuple[UndoEntry, ...]
    redo_stack: tuple[UndoEntry, ...]

    # -- Construction -------------------------------------------------------

    @staticmethod
    def new(model: Any) -> UndoStack:
        """Create a new undo stack with *model* as the initial state.

        Example::

            >>> u = UndoStack.new(0)
            >>> u.current
            0
            >>> u.can_undo
            False
        """
        return UndoStack(current=model, undo_stack=(), redo_stack=())

    # -- Operations ---------------------------------------------------------

    def apply_command(self, command: UndoCommand) -> UndoStack:
        """Apply *command*, updating the model and pushing onto the undo stack.

        Clears the redo stack.  If the command carries a ``coalesce``
        key matching the top of the undo stack within the time window,
        the entry is merged rather than pushed.
        """
        now = _timestamp_fn()
        new_model = command.apply_fn(self.current)

        merged = self._maybe_coalesce(command, now)
        if merged is not None:
            return replace(
                self,
                current=new_model,
                undo_stack=(merged, *self.undo_stack[1:]),
                redo_stack=(),
            )

        entry = UndoEntry(
            apply_fn=command.apply_fn,
            undo_fn=command.undo_fn,
            label=command.label,
            coalesce=command.coalesce,
            timestamp=now,
        )
        return replace(
            self,
            current=new_model,
            undo_stack=(entry, *self.undo_stack),
            redo_stack=(),
        )

    def undo(self) -> UndoStack:
        """Undo the last command.

        Returns unchanged if the undo stack is empty.
        """
        if not self.undo_stack:
            return self
        entry = self.undo_stack[0]
        rest = self.undo_stack[1:]
        old_model = entry.undo_fn(self.current)
        return replace(
            self,
            current=old_model,
            undo_stack=rest,
            redo_stack=(entry, *self.redo_stack),
        )

    def redo(self) -> UndoStack:
        """Redo the last undone command.

        Returns unchanged if the redo stack is empty.
        """
        if not self.redo_stack:
            return self
        entry = self.redo_stack[0]
        rest = self.redo_stack[1:]
        new_model = entry.apply_fn(self.current)
        return replace(
            self,
            current=new_model,
            redo_stack=rest,
            undo_stack=(entry, *self.undo_stack),
        )

    # -- Queries ------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        """Return ``True`` if there are entries on the undo stack."""
        return len(self.undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """Return ``True`` if there are entries on the redo stack."""
        return len(self.redo_stack) > 0

    def history(self) -> list[str | None]:
        """Return labels from the undo stack, most recent first."""
        return [e.label for e in self.undo_stack]

    # -- Private ------------------------------------------------------------

    def _maybe_coalesce(self, command: UndoCommand, now: int) -> UndoEntry | None:
        if not self.undo_stack:
            return None
        top = self.undo_stack[0]
        coalesce_key = command.coalesce
        window = command.coalesce_window_ms

        if (
            coalesce_key is not None
            and coalesce_key == top.coalesce
            and now - top.timestamp <= window
        ):
            old_apply = top.apply_fn
            new_apply = command.apply_fn
            old_undo = top.undo_fn
            new_undo = command.undo_fn
            return UndoEntry(
                apply_fn=lambda model, _oa=old_apply, _na=new_apply: _na(_oa(model)),
                undo_fn=lambda model, _ou=old_undo, _nu=new_undo: _ou(_nu(model)),
                label=top.label,
                coalesce=coalesce_key,
                timestamp=now,
            )
        return None
