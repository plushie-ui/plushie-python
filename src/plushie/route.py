"""Client-side routing for multi-view apps.

Pure data structure maintaining a navigation stack of ``(path, params)``
entries.  The stack is last-in-first-out: :meth:`Route.push` adds a new
entry on top; :meth:`Route.pop` removes the top entry (never pops the
last one).

Example::

    route = Route.new("home")
    route = route.push("settings", {"tab": "general"})
    route.current()    # => "settings"
    route.params()     # => {"tab": "general"}
    route = route.pop()
    route.current()    # => "home"
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

__all__ = [
    "Route",
]


@dataclass(frozen=True, slots=True)
class Route:
    """Immutable navigation stack.

    Create via :meth:`new`.  All mutating methods return a new
    ``Route``.
    """

    stack: tuple[tuple[Any, dict[str, Any]], ...]

    # -- Construction -------------------------------------------------------

    @staticmethod
    def new(initial_path: Any, params: dict[str, Any] | None = None) -> Route:
        """Create a new route with *initial_path* at the bottom of the stack.

        Args:
            initial_path: The root path.
            params: Optional parameters (defaults to empty dict).

        Example::

            >>> r = Route.new("home")
            >>> r.current()
            'home'
        """
        return Route(stack=((initial_path, params or {}),))

    # -- Navigation ---------------------------------------------------------

    def push(self, path: Any, params: dict[str, Any] | None = None) -> Route:
        """Push a new *path* (with optional *params*) onto the stack."""
        return replace(self, stack=((path, params or {}), *self.stack))

    def pop(self) -> Route:
        """Pop the top entry.

        Returns the route unchanged if only one entry remains (the root
        is never popped).
        """
        if len(self.stack) <= 1:
            return self
        return replace(self, stack=self.stack[1:])

    def replace_top(self, path: Any, params: dict[str, Any] | None = None) -> Route:
        """Replace the top entry with a new *path* and *params*."""
        rest = self.stack[1:] if len(self.stack) > 1 else ()
        return replace(self, stack=((path, params or {}), *rest))

    # -- Queries ------------------------------------------------------------

    def current(self) -> Any:
        """Return the current (top) path."""
        return self.stack[0][0]

    def params(self) -> dict[str, Any]:
        """Return the params associated with the current (top) path."""
        return self.stack[0][1]

    @property
    def can_go_back(self) -> bool:
        """Return ``True`` if there is more than one entry on the stack."""
        return len(self.stack) > 1

    @property
    def depth(self) -> int:
        """Return the number of entries on the stack."""
        return len(self.stack)

    def history(self) -> list[Any]:
        """Return all paths in the stack, most recent first."""
        return [path for path, _ in self.stack]
