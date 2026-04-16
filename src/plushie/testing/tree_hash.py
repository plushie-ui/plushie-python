"""Structural tree hash and golden-file assertions for tests.

Computes a SHA-256 hash of a normalized UI tree and compares against
golden files on disk. Mirrors the Elixir SDK's
``Plushie.Test.TreeHash`` module.

Usage::

    from plushie.testing.tree_hash import TreeHash

    th = TreeHash.from_tree("my_snapshot", tree)
    th.assert_match("test/snapshots")

Or via the fixture::

    def test_counter(plushie_pool):
        with AppFixture(Counter, plushie_pool) as app:
            app.assert_tree_hash("initial_state")
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class TreeHash:
    """A structural hash of a UI tree for golden-file comparison.

    Attributes:
        name: Label for this hash capture.
        hash: SHA-256 hex digest of the normalized tree.
        backend: Optional backend mode tag (e.g. ``"mock"``, ``"headless"``).
    """

    name: str
    hash: str
    backend: str | None = None

    @staticmethod
    def compute_hash(data: str | bytes) -> str:
        """Compute a SHA-256 hash of the given data.

        Args:
            data: String or bytes to hash.

        Returns:
            Lowercase hex digest.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def from_tree(
        name: str,
        tree: dict[str, Any],
        backend: str | None = None,
    ) -> TreeHash:
        """Build a TreeHash from a normalized UI tree.

        Args:
            name: Label for this hash capture.
            tree: The normalized UI tree dict.
            backend: Optional backend mode tag.

        Returns:
            A ``TreeHash`` with the computed SHA-256 digest.
        """
        normalized = _normalize_for_hash(tree)
        encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return TreeHash(
            name=name,
            hash=TreeHash.compute_hash(encoded),
            backend=backend,
        )

    @staticmethod
    def from_response(msg: dict[str, Any]) -> TreeHash:
        """Build a TreeHash from a renderer ``tree_hash_response`` message.

        Args:
            msg: The raw response dict with ``name`` and ``hash`` fields.

        Returns:
            A ``TreeHash`` from the renderer-computed hash.

        Raises:
            ValueError: If the message is not a valid tree_hash_response.
        """
        name = msg.get("name")
        hash_val = msg.get("hash")
        if not isinstance(name, str) or not isinstance(hash_val, str):
            raise ValueError(f"invalid tree_hash_response: {msg!r}")
        return TreeHash(name=name, hash=hash_val)

    def assert_match(self, golden_dir: str | Path) -> None:
        """Assert this hash matches the golden file.

        On first run, creates the golden file. On subsequent runs,
        compares hashes. Set ``PLUSHIE_UPDATE_SNAPSHOTS=1`` to
        force-update golden files.

        Args:
            golden_dir: Directory containing golden ``.sha256`` files.

        Raises:
            AssertionError: If the hash does not match the golden file.
        """
        golden_dir = Path(golden_dir)
        golden_dir.mkdir(parents=True, exist_ok=True)
        suffix = f".{self.backend}" if self.backend else ""
        golden_path = golden_dir / f"{self.name}{suffix}.sha256"

        update = os.environ.get("PLUSHIE_UPDATE_SNAPSHOTS") == "1"

        if update or not golden_path.exists():
            golden_path.write_text(self.hash)
            return

        expected = golden_path.read_text().strip()
        if self.hash != expected:
            raise AssertionError(
                f'Tree hash mismatch for "{self.name}".\n\n'
                f"Expected hash: {expected}\n"
                f"Actual hash:   {self.hash}\n\n"
                "Run with PLUSHIE_UPDATE_SNAPSHOTS=1 to update the golden file.\n"
                f"Golden file: {golden_path}"
            )


def _normalize_for_hash(data: Any) -> Any:
    """Recursively normalize data for deterministic hashing.

    Sorts dict keys, normalizes lists, and leaves scalars unchanged.
    """
    if isinstance(data, dict):
        return {str(k): _normalize_for_hash(v) for k, v in sorted(data.items())}
    if isinstance(data, list):
        return [_normalize_for_hash(item) for item in data]
    return data


__all__ = ["TreeHash"]
