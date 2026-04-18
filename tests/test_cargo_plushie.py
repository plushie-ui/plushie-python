"""Tests for :mod:`plushie.cargo_plushie` invocation resolution."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from plushie.binary import PLUSHIE_RUST_VERSION
from plushie.cargo_plushie import (
    CargoPlushieNotFoundError,
    resolve_cargo_plushie,
)

# ---------------------------------------------------------------------------
# PLUSHIE_RUST_SOURCE_PATH branch
# ---------------------------------------------------------------------------


class TestSourcePathBranch:
    """When ``PLUSHIE_RUST_SOURCE_PATH`` is set, ``cargo run`` is used."""

    def test_returns_cargo_run_invocation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLUSHIE_RUST_SOURCE_PATH", "/tmp/plushie-rust")

        command, prefix = resolve_cargo_plushie()

        assert command == "cargo"
        assert prefix[0] == "run"
        assert "--manifest-path" in prefix
        manifest_idx = prefix.index("--manifest-path")
        assert prefix[manifest_idx + 1].endswith("Cargo.toml")
        assert "cargo-plushie" in prefix
        assert "--release" in prefix
        assert "--quiet" in prefix
        assert prefix[-1] == "--"

    def test_source_path_wins_over_on_path_binary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even if ``cargo-plushie`` is on PATH, the source override wins."""
        monkeypatch.setenv("PLUSHIE_RUST_SOURCE_PATH", "/tmp/plushie-rust")

        # If the source branch leaks through to the PATH check, shutil.which
        # would have to fire. Force a failure there so any accidental leak
        # manifests.
        def _boom(_name: str) -> str | None:
            raise AssertionError("shutil.which should not be called")

        monkeypatch.setattr("plushie.cargo_plushie.shutil.which", _boom)

        command, _prefix = resolve_cargo_plushie()
        assert command == "cargo"


# ---------------------------------------------------------------------------
# cargo-plushie on PATH branch
# ---------------------------------------------------------------------------


def _fake_run(stdout: str, returncode: int = 0) -> Any:
    """Return a stub that replaces ``subprocess.run`` with a fixed result."""

    class _Completed:
        def __init__(self) -> None:
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def runner(*_args: Any, **_kwargs: Any) -> _Completed:
        return _Completed()

    return runner


class TestOnPathBranch:
    """``cargo-plushie`` on PATH with a matching version."""

    def test_matching_version_returns_direct_invocation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)
        monkeypatch.setattr(
            "plushie.cargo_plushie.shutil.which",
            lambda _name: "/usr/local/bin/cargo-plushie",
        )
        monkeypatch.setattr(
            "plushie.cargo_plushie.subprocess.run",
            _fake_run(f"cargo-plushie {PLUSHIE_RUST_VERSION}\n"),
        )

        command, prefix = resolve_cargo_plushie()

        assert command == "cargo-plushie"
        assert prefix == []

    def test_mismatched_version_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)
        monkeypatch.setattr(
            "plushie.cargo_plushie.shutil.which",
            lambda _name: "/usr/local/bin/cargo-plushie",
        )
        monkeypatch.setattr(
            "plushie.cargo_plushie.subprocess.run",
            _fake_run("cargo-plushie 0.0.99\n"),
        )

        with pytest.raises(CargoPlushieNotFoundError) as exc_info:
            resolve_cargo_plushie()

        message = str(exc_info.value)
        assert "0.0.99" in message
        assert PLUSHIE_RUST_VERSION in message
        assert (
            f"cargo install cargo-plushie --version {PLUSHIE_RUST_VERSION} --locked"
            in message
        )
        assert "PLUSHIE_RUST_SOURCE_PATH" in message

    def test_partial_version_match_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``0.6.1`` must not match ``0.6.10``."""
        monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)
        monkeypatch.setattr(
            "plushie.cargo_plushie.shutil.which",
            lambda _name: "/usr/local/bin/cargo-plushie",
        )
        near_miss = f"cargo-plushie {PLUSHIE_RUST_VERSION}0\n"
        monkeypatch.setattr(
            "plushie.cargo_plushie.subprocess.run",
            _fake_run(near_miss),
        )

        with pytest.raises(CargoPlushieNotFoundError):
            resolve_cargo_plushie()

    def test_version_check_exit_nonzero_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)
        monkeypatch.setattr(
            "plushie.cargo_plushie.shutil.which",
            lambda _name: "/usr/local/bin/cargo-plushie",
        )
        monkeypatch.setattr(
            "plushie.cargo_plushie.subprocess.run",
            _fake_run("", returncode=1),
        )

        with pytest.raises(CargoPlushieNotFoundError) as exc_info:
            resolve_cargo_plushie()

        assert "exited 1" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Missing binary branch
# ---------------------------------------------------------------------------


class TestMissingBranch:
    """Neither the env var nor PATH yields a usable tool."""

    def test_missing_binary_raises_with_install_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)
        monkeypatch.setattr("plushie.cargo_plushie.shutil.which", lambda _name: None)

        with pytest.raises(CargoPlushieNotFoundError) as exc_info:
            resolve_cargo_plushie()

        message = str(exc_info.value)
        assert "cargo-plushie is not on PATH" in message
        assert (
            f"cargo install cargo-plushie --version {PLUSHIE_RUST_VERSION} --locked"
            in message
        )
        assert "PLUSHIE_RUST_SOURCE_PATH" in message

    def test_oserror_during_version_check_is_wrapped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If ``cargo-plushie --version`` fails to exec, surface a clear error."""
        monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)
        monkeypatch.setattr(
            "plushie.cargo_plushie.shutil.which",
            lambda _name: "/usr/local/bin/cargo-plushie",
        )

        def _raise(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise OSError("exec failed")

        monkeypatch.setattr("plushie.cargo_plushie.subprocess.run", _raise)

        with pytest.raises(CargoPlushieNotFoundError) as exc_info:
            resolve_cargo_plushie()

        assert "exec failed" in str(exc_info.value)
