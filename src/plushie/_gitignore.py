"""Friendly gitignore-coverage warning for generated output paths.

Used by commands that write to a known output directory (downloaded
binaries, package payloads) to nudge users to ignore those paths so
build artifacts don't accidentally get committed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def warn_if_not_gitignored(path: str | Path) -> None:
    """Emit a stderr warning if ``path`` lives in a git repo but is not ignored.

    Silent when:
    - ``path`` is not inside a git work tree
    - ``path`` is already gitignored
    - git is not available on PATH

    The path is normalised to a relative form for the suggested
    ``.gitignore`` line when it sits under the current working
    directory; otherwise it is shown verbatim.
    """
    target = Path(path)
    cwd = target if target.is_dir() else target.parent
    if not cwd.exists():
        cwd = Path.cwd()

    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return

    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return

    check = subprocess.run(
        ["git", "check-ignore", "-q", os.fspath(target)],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    if check.returncode == 0:
        return

    display = _display_path(target)
    print(
        f"warning: {display}/ is not in .gitignore.\n"
        "  Recommended: add the following line so generated artifacts don't end\n"
        "  up committed:\n"
        "\n"
        f"      /{display}/",
        file=sys.stderr,
    )


def _display_path(path: Path) -> str:
    """Return a clean relative form of ``path`` for display."""
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return os.fspath(path)
    text = rel.as_posix()
    return text if text else "."
