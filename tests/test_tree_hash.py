"""Tests for TreeHash golden-file assertions."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from plushie.testing.tree_hash import TreeHash, _normalize_for_hash


class TestTreeHashCompute:
    def test_compute_hash_string(self) -> None:
        h = TreeHash.compute_hash("hello")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_compute_hash_bytes(self) -> None:
        h = TreeHash.compute_hash(b"hello")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_compute_hash_deterministic(self) -> None:
        assert TreeHash.compute_hash("test") == TreeHash.compute_hash("test")

    def test_compute_hash_different_inputs(self) -> None:
        assert TreeHash.compute_hash("a") != TreeHash.compute_hash("b")


class TestTreeHashFromTree:
    def test_basic_tree(self) -> None:
        tree = {"type": "column", "children": []}
        th = TreeHash.from_tree("test", tree)
        assert th.name == "test"
        assert len(th.hash) == 64
        assert th.backend is None

    def test_with_backend(self) -> None:
        tree = {"type": "text", "props": {"content": "hi"}}
        th = TreeHash.from_tree("snap", tree, backend="mock")
        assert th.backend == "mock"

    def test_deterministic(self) -> None:
        tree = {"type": "row", "children": [{"type": "text"}]}
        th1 = TreeHash.from_tree("x", tree)
        th2 = TreeHash.from_tree("x", tree)
        assert th1.hash == th2.hash

    def test_key_order_irrelevant(self) -> None:
        tree1 = {"a": 1, "b": 2}
        tree2 = {"b": 2, "a": 1}
        assert (
            TreeHash.from_tree("x", tree1).hash == TreeHash.from_tree("x", tree2).hash
        )


class TestTreeHashFromResponse:
    def test_valid_response(self) -> None:
        msg = {"type": "tree_hash_response", "name": "test", "hash": "abc123"}
        th = TreeHash.from_response(msg)
        assert th.name == "test"
        assert th.hash == "abc123"

    def test_invalid_response_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match=r"invalid tree_hash_response"):
            TreeHash.from_response({"type": "other"})


class TestTreeHashAssertMatch:
    def test_creates_golden_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            th = TreeHash(name="test", hash="abc123")
            th.assert_match(tmp)
            golden = Path(tmp) / "test.sha256"
            assert golden.exists()
            assert golden.read_text() == "abc123"

    def test_matching_hash_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            golden = Path(tmp) / "test.sha256"
            golden.write_text("abc123")
            th = TreeHash(name="test", hash="abc123")
            th.assert_match(tmp)

    def test_mismatching_hash_raises(self) -> None:
        import pytest

        with tempfile.TemporaryDirectory() as tmp:
            golden = Path(tmp) / "test.sha256"
            golden.write_text("abc123")
            th = TreeHash(name="test", hash="def456")
            with pytest.raises(AssertionError, match=r"Tree hash mismatch"):
                th.assert_match(tmp)

    def test_update_env_var_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            golden = Path(tmp) / "test.sha256"
            golden.write_text("old_hash")
            os.environ["PLUSHIE_UPDATE_SNAPSHOTS"] = "1"
            try:
                th = TreeHash(name="test", hash="new_hash")
                th.assert_match(tmp)
                assert golden.read_text() == "new_hash"
            finally:
                del os.environ["PLUSHIE_UPDATE_SNAPSHOTS"]

    def test_backend_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            th = TreeHash(name="test", hash="abc", backend="mock")
            th.assert_match(tmp)
            assert (Path(tmp) / "test.mock.sha256").exists()


class TestNormalizeForHash:
    def test_sorts_dict_keys(self) -> None:
        result = _normalize_for_hash({"z": 1, "a": 2})
        assert list(result.keys()) == ["a", "z"]

    def test_recurses_nested(self) -> None:
        result = _normalize_for_hash({"outer": {"z": 1, "a": 2}})
        assert list(result["outer"].keys()) == ["a", "z"]

    def test_preserves_lists(self) -> None:
        result = _normalize_for_hash([3, 1, 2])
        assert result == [3, 1, 2]

    def test_preserves_scalars(self) -> None:
        assert _normalize_for_hash(42) == 42
        assert _normalize_for_hash("hi") == "hi"
        assert _normalize_for_hash(None) is None
