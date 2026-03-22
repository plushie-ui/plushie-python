"""Query pipeline for in-memory record collections.

Pure functions supporting filter, search, sort, group, and pagination.
Operations are applied in order: filter -> search -> sort -> paginate.
Grouping is applied to the paginated results.

Example::

    records = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
        {"name": "Carol", "age": 35},
    ]

    result = query(records, filter_fn=lambda r: r["age"] > 24, sort=("asc", "name"))
    result.entries
    #=> [{"name": "Alice", ...}, {"name": "Bob", ...}, {"name": "Carol", ...}]
    result.total
    #=> 3
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "QueryResult",
    "query",
]

from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Result of a :func:`query` call.

    Attributes:
        entries: The paginated list of records.
        total: Total number of records after filtering/searching (before pagination).
        page: Current page number (1-based).
        page_size: Records per page.
        groups: Records grouped by field, or ``None`` if no grouping was requested.
    """

    entries: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    groups: dict[Any, list[dict[str, Any]]] | None


def query(
    records: list[dict[str, Any]],
    *,
    filter_fn: Callable[[dict[str, Any]], bool] | None = None,
    search: tuple[list[str], str] | None = None,
    sort: tuple[str, str] | list[tuple[str, str]] | None = None,
    group: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> QueryResult:
    """Query a list of records with optional filtering, searching, sorting,
    grouping, and pagination.

    Args:
        records: List of dicts to query.
        filter_fn: Predicate ``(record) -> bool`` to filter records.
        search: A ``(fields, query_string)`` tuple.  *fields* is a list
            of dict keys; *query_string* is case-insensitive
            substring-matched.
        sort: A ``(direction, field)`` tuple or list of tuples.
            Direction is ``"asc"`` or ``"desc"``.
        group: A dict key to group paginated results by.
        page: Page number (1-based, default 1).
        page_size: Records per page (default 25).

    Returns:
        A :class:`QueryResult` with entries, total, page, page_size,
        and optional groups.

    Example::

        >>> result = query([{"x": 1}, {"x": 2}], page_size=1, page=2)
        >>> result.entries
        [{'x': 2}]
        >>> result.total
        2
    """
    result = records

    # Filter
    if filter_fn is not None:
        result = [r for r in result if filter_fn(r)]

    # Search
    if search is not None:
        fields, query_string = search
        q = query_string.lower()
        result = [
            r for r in result if any(q in str(r.get(f, "")).lower() for f in fields)
        ]

    # Sort
    if sort is not None:
        specs = (
            [sort]
            if isinstance(sort, tuple) and len(sort) == 2 and isinstance(sort[0], str)
            else sort
        )  # type: ignore[assignment]
        result = _sort_records(result, specs)  # type: ignore[arg-type]

    total = len(result)

    # Paginate
    offset = (page - 1) * page_size
    entries = result[offset : offset + page_size]

    # Group
    groups: dict[Any, list[dict[str, Any]]] | None = None
    if group is not None:
        groups = {}
        for entry in entries:
            key = entry.get(group)
            groups.setdefault(key, []).append(entry)

    return QueryResult(
        entries=entries,
        total=total,
        page=page,
        page_size=page_size,
        groups=groups,
    )


def _sort_records(
    records: list[dict[str, Any]],
    specs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Sort records by multiple (direction, field) specs."""
    import functools

    def compare(a: dict[str, Any], b: dict[str, Any]) -> int:
        for direction, field in specs:
            va = a.get(field)
            vb = b.get(field)
            if va == vb:
                continue
            if direction == "desc":
                va, vb = vb, va
            cmp = _compare_values(va, vb)
            if cmp != 0:
                return cmp
        return 0

    return sorted(records, key=functools.cmp_to_key(compare))


def _compare_values(a: Any, b: Any) -> int:
    """Compare two values, coercing to string if types differ."""
    try:
        if a < b:
            return -1
        if a > b:
            return 1
        return 0
    except TypeError:
        sa, sb = str(a), str(b)
        if sa < sb:
            return -1
        if sa > sb:
            return 1
        return 0
