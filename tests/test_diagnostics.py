"""Tests for the typed Diagnostic decoder."""

from __future__ import annotations

import pytest

from plushie.diagnostics import (
    BufferOverflow,
    DispatchLoopExceeded,
    DuplicateId,
    FontFamilyNotFound,
    RequiredWidgetsMissing,
    UpdatePanicked,
    decode,
    known_kinds,
)


class TestDecode:
    def test_duplicate_id(self) -> None:
        d = decode(
            {"kind": "duplicate_id", "id": "main#form/email", "window_id": "main"}
        )
        assert isinstance(d, DuplicateId)
        assert d.id == "main#form/email"
        assert d.window_id == "main"

    def test_update_panicked(self) -> None:
        d = decode({"kind": "update_panicked", "consecutive": 3, "message": "boom"})
        assert isinstance(d, UpdatePanicked)
        assert d.consecutive == 3
        assert d.message == "boom"

    def test_font_family_not_found(self) -> None:
        d = decode({"kind": "font_family_not_found", "family": "Inter"})
        assert isinstance(d, FontFamilyNotFound)
        assert d.family == "Inter"

    def test_required_widgets_missing_is_tuple(self) -> None:
        d = decode({"kind": "required_widgets_missing", "missing": ["a", "b"]})
        assert isinstance(d, RequiredWidgetsMissing)
        assert d.missing == ("a", "b")

    def test_dispatch_loop_exceeded(self) -> None:
        d = decode({"kind": "dispatch_loop_exceeded", "depth": 101, "limit": 100})
        assert isinstance(d, DispatchLoopExceeded)
        assert d.depth == 101
        assert d.limit == 100

    def test_buffer_overflow(self) -> None:
        d = decode({"kind": "buffer_overflow", "size": 80_000_000, "limit": 67_108_864})
        assert isinstance(d, BufferOverflow)
        assert d.size == 80_000_000
        assert d.limit == 67_108_864

    def test_unknown_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown diagnostic kind"):
            decode({"kind": "never_heard_of_it"})

    def test_missing_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="missing string 'kind' field"):
            decode({"id": "x"})

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="must be a dict"):
            decode("string")  # type: ignore[arg-type]

    def test_known_kinds_covers_new_variants(self) -> None:
        kinds = known_kinds()
        assert "duplicate_id" in kinds
        assert "update_panicked" in kinds
        assert "dispatch_loop_exceeded" in kinds
        assert "buffer_overflow" in kinds
