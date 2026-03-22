"""Tests for plushie.data."""

from __future__ import annotations

from plushie.data import QueryResult, query

RECORDS = [
    {"name": "Alice", "age": 30, "dept": "eng"},
    {"name": "Bob", "age": 25, "dept": "eng"},
    {"name": "Carol", "age": 35, "dept": "design"},
    {"name": "Dave", "age": 28, "dept": "design"},
    {"name": "Eve", "age": 22, "dept": "eng"},
]


class TestQueryBasic:
    def test_no_options_returns_all(self) -> None:
        result = query(RECORDS)
        assert len(result.entries) == 5
        assert result.total == 5
        assert result.page == 1
        assert result.page_size == 25
        assert result.groups is None

    def test_returns_query_result(self) -> None:
        result = query(RECORDS)
        assert isinstance(result, QueryResult)


class TestFilter:
    def test_filter_by_age(self) -> None:
        result = query(RECORDS, filter_fn=lambda r: r["age"] >= 28)
        assert result.total == 3
        names = {r["name"] for r in result.entries}
        assert names == {"Alice", "Carol", "Dave"}


class TestSearch:
    def test_search_by_name(self) -> None:
        result = query(RECORDS, search=(["name"], "ali"))
        assert result.total == 1
        assert result.entries[0]["name"] == "Alice"

    def test_search_case_insensitive(self) -> None:
        result = query(RECORDS, search=(["name"], "BOB"))
        assert result.total == 1

    def test_search_no_match(self) -> None:
        result = query(RECORDS, search=(["name"], "zzz"))
        assert result.total == 0

    def test_search_multiple_fields(self) -> None:
        result = query(RECORDS, search=(["name", "dept"], "eng"))
        # Should match Alice, Bob, Eve (dept=eng)
        assert result.total == 3


class TestSort:
    def test_sort_asc(self) -> None:
        result = query(RECORDS, sort=("asc", "age"))
        ages = [r["age"] for r in result.entries]
        assert ages == [22, 25, 28, 30, 35]

    def test_sort_desc(self) -> None:
        result = query(RECORDS, sort=("desc", "age"))
        ages = [r["age"] for r in result.entries]
        assert ages == [35, 30, 28, 25, 22]

    def test_sort_by_string(self) -> None:
        result = query(RECORDS, sort=("asc", "name"))
        names = [r["name"] for r in result.entries]
        assert names == ["Alice", "Bob", "Carol", "Dave", "Eve"]

    def test_multi_sort(self) -> None:
        result = query(RECORDS, sort=[("asc", "dept"), ("desc", "age")])
        entries = result.entries
        # design first (Carol 35, Dave 28), then eng (Alice 30, Bob 25, Eve 22)
        assert entries[0]["name"] == "Carol"
        assert entries[1]["name"] == "Dave"
        assert entries[2]["name"] == "Alice"
        assert entries[3]["name"] == "Bob"
        assert entries[4]["name"] == "Eve"


class TestPagination:
    def test_page_1(self) -> None:
        result = query(RECORDS, page=1, page_size=2, sort=("asc", "name"))
        assert len(result.entries) == 2
        assert result.total == 5
        assert result.entries[0]["name"] == "Alice"
        assert result.entries[1]["name"] == "Bob"

    def test_page_2(self) -> None:
        result = query(RECORDS, page=2, page_size=2, sort=("asc", "name"))
        assert len(result.entries) == 2
        assert result.entries[0]["name"] == "Carol"
        assert result.entries[1]["name"] == "Dave"

    def test_last_page_partial(self) -> None:
        result = query(RECORDS, page=3, page_size=2, sort=("asc", "name"))
        assert len(result.entries) == 1
        assert result.entries[0]["name"] == "Eve"

    def test_beyond_last_page(self) -> None:
        result = query(RECORDS, page=99, page_size=2)
        assert len(result.entries) == 0
        assert result.total == 5


class TestGroup:
    def test_group_by_dept(self) -> None:
        result = query(RECORDS, group="dept")
        assert result.groups is not None
        assert "eng" in result.groups
        assert "design" in result.groups

    def test_group_respects_pagination(self) -> None:
        result = query(RECORDS, group="dept", page=1, page_size=2, sort=("asc", "name"))
        assert result.groups is not None
        # Only first 2 records (Alice, Bob) which are both eng
        assert set(result.groups.keys()) == {"eng"}


class TestPipelineOrder:
    def test_filter_then_sort_then_paginate(self) -> None:
        result = query(
            RECORDS,
            filter_fn=lambda r: r["dept"] == "eng",
            sort=("asc", "name"),
            page=1,
            page_size=2,
        )
        assert result.total == 3
        assert len(result.entries) == 2
        assert result.entries[0]["name"] == "Alice"
        assert result.entries[1]["name"] == "Bob"
