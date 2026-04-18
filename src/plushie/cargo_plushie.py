"""Resolve the ``cargo-plushie`` build tool invocation.

``cargo-plushie`` generates the renderer workspace and drives the
underlying ``cargo build``. The Python SDK shells out to it instead of
generating Cargo files itself.

Resolution strategy (in order):

1. If ``PLUSHIE_RUST_SOURCE_PATH`` is set, run the tool from the local
   plushie-rust checkout via ``cargo run -p cargo-plushie``. This path
   supports real-world verification against an in-flight workspace
   without a published release.
2. Otherwise, look for ``cargo-plushie`` on ``PATH`` and confirm its
   ``--version`` output matches :data:`PLUSHIE_RUST_VERSION`.
3. On missing or mismatched installs, raise
   :class:`CargoPlushieNotFoundError` with the exact
   ``cargo install`` command the user should run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

from plushie.binary import PLUSHIE_RUST_VERSION

if TYPE_CHECKING:
    pass


class CargoPlushieNotFoundError(RuntimeError):
    """Raised when ``cargo-plushie`` cannot be located at the required version.

    The message includes the exact ``cargo install`` command the user
    should run and mentions the ``PLUSHIE_RUST_SOURCE_PATH`` alternative
    for local-dev flows.
    """


def resolve_cargo_plushie() -> tuple[str, list[str]]:
    """Return the command and argument prefix for invoking ``cargo-plushie``.

    The return value is ``(command, args_prefix)``. Callers append
    their subcommand and flags to ``args_prefix`` and pass the full list
    to :func:`subprocess.run`. The extra ``--`` at the end of the source
    path branch separates the ``cargo run`` arguments from the
    subcommand arguments.

    Returns:
        A ``(command, args_prefix)`` tuple.

    Raises:
        CargoPlushieNotFoundError: If no matching ``cargo-plushie`` is
            found on ``PATH`` and ``PLUSHIE_RUST_SOURCE_PATH`` is unset.
    """
    # 1. PLUSHIE_RUST_SOURCE_PATH wins when set: run from the local workspace.
    source = os.environ.get("PLUSHIE_RUST_SOURCE_PATH")
    if source:
        manifest = os.path.join(source, "Cargo.toml")
        return (
            "cargo",
            [
                "run",
                "--manifest-path",
                manifest,
                "-p",
                "cargo-plushie",
                "--release",
                "--quiet",
                "--",
            ],
        )

    # 2. On-PATH installation. Verify the version matches.
    binary = shutil.which("cargo-plushie")
    if binary is not None:
        try:
            result = subprocess.run(
                ["cargo-plushie", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise _not_found_error(
                f"failed to invoke cargo-plushie --version: {exc}"
            ) from exc

        if result.returncode != 0:
            raise _not_found_error(
                f"cargo-plushie --version exited {result.returncode}"
            )

        if _matches_version(result.stdout, PLUSHIE_RUST_VERSION):
            return ("cargo-plushie", [])

        raise _not_found_error(
            f"cargo-plushie on PATH reports {result.stdout.strip()!r}, "
            f"but this SDK requires version {PLUSHIE_RUST_VERSION}"
        )

    # 3. Nothing resolvable.
    raise _not_found_error("cargo-plushie is not on PATH")


def _matches_version(version_output: str, expected: str) -> bool:
    """Check whether ``cargo-plushie --version`` reports the expected version.

    ``cargo-plushie`` prints ``cargo-plushie <version>`` by Cargo
    convention. The match is a whole-word compare so partial versions
    like ``0.6.1`` cannot match ``0.6.10``.
    """
    tokens = version_output.strip().split()
    return expected in tokens


def _not_found_error(detail: str) -> CargoPlushieNotFoundError:
    """Build a :class:`CargoPlushieNotFoundError` with install guidance."""
    return CargoPlushieNotFoundError(
        f"{detail}.\n"
        "\n"
        "To install the matching build tool:\n"
        f"  cargo install cargo-plushie --version {PLUSHIE_RUST_VERSION} --locked\n"
        "\n"
        "To use a local plushie-rust checkout instead:\n"
        "  export PLUSHIE_RUST_SOURCE_PATH=/path/to/plushie-rust"
    )


__all__ = [
    "CargoPlushieNotFoundError",
    "resolve_cargo_plushie",
]
