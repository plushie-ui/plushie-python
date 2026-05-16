"""Tests for the gitignore-coverage warning helper."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plushie._gitignore import warn_if_not_gitignored


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _init_repo(path: Path) -> None:
    _git(path, "init", "-q", "-b", "main")
    # Pin identity so commits don't depend on global git config.
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Test")


def test_silent_when_not_in_git_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "bin"
    target.mkdir()

    warn_if_not_gitignored(target)

    out = capsys.readouterr()
    assert out.err == ""
    assert out.out == ""


def test_silent_when_path_already_gitignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("/bin/\n", encoding="utf-8")
    target = tmp_path / "bin"
    target.mkdir()
    monkeypatch.chdir(tmp_path)

    warn_if_not_gitignored(target)

    out = capsys.readouterr()
    assert out.err == ""


def test_warns_when_path_not_gitignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "dist"
    target.mkdir()
    monkeypatch.chdir(tmp_path)

    warn_if_not_gitignored(target)

    out = capsys.readouterr()
    assert "warning: dist/ is not in .gitignore." in out.err
    assert "/dist/" in out.err


def test_warns_with_relative_form_for_nested_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "build" / "artifacts"
    target.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    warn_if_not_gitignored(target)

    out = capsys.readouterr()
    assert "warning: build/artifacts/ is not in .gitignore." in out.err
    assert "/build/artifacts/" in out.err
