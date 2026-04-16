"""Screenshot golden-file assertions for tests.

Compares screenshot hashes against golden files on disk. Mirrors the
Elixir SDK's ``Plushie.Test.Screenshot`` module.

Usage::

    from plushie.testing.screenshot import Screenshot

    s = Screenshot(name="my_view", hash="abc123...")
    s.assert_match("test/screenshots")

Or via the fixture::

    def test_counter(plushie_pool):
        with AppFixture(Counter, plushie_pool) as app:
            app.assert_screenshot("initial_state")
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Screenshot:
    """A screenshot capture with hash for golden-file comparison.

    Attributes:
        name: Label for this screenshot capture.
        hash: SHA-256 hex digest of the pixel data (empty if unsupported).
        data: Raw PNG bytes, base64 string, or ``None``.
        backend: Optional backend mode tag (e.g. ``"headless"``).
    """

    name: str
    hash: str
    data: bytes | str | None = None
    backend: str | None = None

    @staticmethod
    def from_response(
        msg: dict[str, Any],
        backend: str | None = None,
    ) -> Screenshot:
        """Build a Screenshot from a renderer ``screenshot_response`` message.

        Args:
            msg: The raw response dict with ``name``, ``hash``, and
                optionally ``data`` fields.
            backend: Optional backend mode tag.

        Returns:
            A ``Screenshot`` from the renderer response.
        """
        return Screenshot(
            name=msg.get("name", ""),
            hash=msg.get("hash", ""),
            data=msg.get("data"),
            backend=backend,
        )

    def save_png(self, path: str | Path) -> None:
        """Save the screenshot as a PNG file.

        Args:
            path: Output file path.

        Raises:
            ValueError: If there is no pixel data to save.
        """
        if not self.data:
            raise ValueError(f"no pixel data for screenshot {self.name!r}")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(self.data, str):
            path.write_bytes(base64.b64decode(self.data))
        else:
            path.write_bytes(self.data)

    def assert_match(self, golden_dir: str | Path) -> None:
        """Assert this screenshot hash matches the golden file.

        Empty hashes (backends that don't support pixel capture) are
        silently accepted. On first run, creates the golden file. On
        subsequent runs, compares hashes. Set
        ``PLUSHIE_UPDATE_SCREENSHOTS=1`` to force-update golden files.

        Args:
            golden_dir: Directory containing golden ``.sha256`` files.

        Raises:
            AssertionError: If the hash does not match the golden file.
        """
        if not self.hash:
            return

        golden_dir = Path(golden_dir)
        golden_dir.mkdir(parents=True, exist_ok=True)
        suffix = f".{self.backend}" if self.backend else ""
        golden_path = golden_dir / f"{self.name}{suffix}.sha256"

        update = os.environ.get("PLUSHIE_UPDATE_SCREENSHOTS") == "1"

        if update or not golden_path.exists():
            golden_path.write_text(self.hash)
            return

        expected = golden_path.read_text().strip()
        if self.hash != expected:
            raise AssertionError(
                f'Screenshot mismatch for "{self.name}".\n\n'
                f"Expected hash: {expected}\n"
                f"Actual hash:   {self.hash}\n\n"
                "Run with PLUSHIE_UPDATE_SCREENSHOTS=1 to update the golden file.\n"
                f"Golden file: {golden_path}"
            )


__all__ = ["Screenshot"]
