"""Binary resolution, download, and platform detection for the plushie renderer.

Resolution chain for ``resolve()``:

1. ``PLUSHIE_BINARY_PATH`` environment variable (fail-fast if set but missing)
2. Downloaded binary in ``~/.local/share/plushie/bin/``
3. ``plushie`` on system PATH via ``shutil.which``

Platform detection identifies os (linux/darwin/windows) and arch
(x86_64/aarch64) for download naming.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("plushie")

GITHUB_RELEASE_URL = "https://github.com/anthropics/plushie/releases/download"
"""Base URL for GitHub release asset downloads."""


class PlushieNotFoundError(FileNotFoundError):
    """Raised when the plushie binary cannot be resolved.

    The error message lists the resolution chain and provides install
    instructions.
    """


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def detect_os() -> str:
    """Detect the current operating system.

    Returns:
        ``"linux"``, ``"darwin"``, or ``"windows"``.

    Raises:
        RuntimeError: If the OS is not recognized.
    """
    name = sys.platform
    if name.startswith("linux"):
        return "linux"
    if name == "darwin":
        return "darwin"
    if name in ("win32", "cygwin"):
        return "windows"
    raise RuntimeError(f"unsupported platform: {name}")


def detect_arch() -> str:
    """Detect the CPU architecture.

    Returns:
        ``"x86_64"`` or ``"aarch64"``.

    Raises:
        RuntimeError: If the architecture is not recognized.
    """
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    if machine in ("aarch64", "arm64"):
        return "aarch64"
    raise RuntimeError(f"unsupported architecture: {machine}")


def download_name(*, os_name: str | None = None, arch: str | None = None) -> str:
    """Return the platform-specific binary asset name for downloads.

    Format: ``plushie-{os}-{arch}`` (e.g. ``plushie-linux-x86_64``).
    On Windows the ``.exe`` extension is appended.

    Args:
        os_name: Override OS detection (for testing).
        arch: Override arch detection (for testing).

    Returns:
        Asset filename string.
    """
    os_val = os_name or detect_os()
    arch_val = arch or detect_arch()
    ext = ".exe" if os_val == "windows" else ""
    return f"plushie-{os_val}-{arch_val}{ext}"


# ---------------------------------------------------------------------------
# Download directory
# ---------------------------------------------------------------------------


def download_dir() -> Path:
    """Return the standard directory for downloaded plushie binaries.

    Uses ``~/.local/share/plushie/bin/`` on Linux/macOS and
    ``%LOCALAPPDATA%/plushie/bin/`` on Windows.

    Returns:
        Path to the download directory (may not exist yet).
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "plushie" / "bin"


def _is_native_binary(path: str) -> bool:
    """Check if a file is a native executable, not a Python script.

    Reads the first two bytes to detect ELF (``\\x7fELF``), Mach-O,
    or PE (``MZ``) magic. Returns ``False`` for text files like
    Python entry-point scripts (which start with ``#!``).
    """
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        if len(header) < 2:
            return False
        # ELF (Linux)
        if header[:4] == b"\x7fELF":
            return True
        # Mach-O (macOS) -- both 32 and 64 bit, both endiannesses
        if header[:4] in (
            b"\xfe\xed\xfa\xce",
            b"\xfe\xed\xfa\xcf",
            b"\xce\xfa\xed\xfe",
            b"\xcf\xfa\xed\xfe",
        ):
            return True
        # PE (Windows)
        return header[:2] == b"MZ"
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Resolution chain
# ---------------------------------------------------------------------------


def resolve() -> str:
    """Resolve the path to the plushie binary.

    Resolution order:

    1. ``PLUSHIE_BINARY_PATH`` environment variable -- if set but the
       file does not exist, raises immediately (explicit config should
       not silently fall through).
    2. Downloaded binary in the standard download directory.
    3. ``plushie`` on the system PATH.

    Returns:
        Absolute path to the plushie binary.

    Raises:
        PlushieNotFoundError: If no binary can be found.
    """
    # Step 1: environment variable
    env_path = os.environ.get("PLUSHIE_BINARY_PATH")
    if env_path is not None:
        if not os.path.isfile(env_path):
            raise PlushieNotFoundError(
                f"PLUSHIE_BINARY_PATH is set to {env_path!r} but the file "
                f"does not exist.\n\n"
                f"Check the path or unset the variable to use automatic "
                f"resolution."
            )
        return os.path.abspath(env_path)

    # Step 2: downloaded binary
    try:
        name = download_name()
        downloaded = download_dir() / name
        if downloaded.is_file():
            return str(downloaded)
    except RuntimeError:
        # Platform detection failed -- skip this step
        pass

    # Step 3: system PATH (native binaries only, not Python scripts)
    which_path = shutil.which("plushie")
    if which_path is not None and _is_native_binary(which_path):
        return os.path.abspath(which_path)

    try:
        dl_dir = str(download_dir())
    except RuntimeError:
        dl_dir = "~/.local/share/plushie/bin/"

    raise PlushieNotFoundError(
        "plushie binary not found.\n"
        "\n"
        "Resolution chain (checked in order):\n"
        "  1. PLUSHIE_BINARY_PATH environment variable (not set)\n"
        f"  2. Downloaded binary in {dl_dir} (not found)\n"
        "  3. 'plushie' on system PATH (not found)\n"
        "\n"
        "To download a precompiled binary:\n"
        "  python -m plushie download\n"
        "\n"
        "To use an existing binary:\n"
        "  export PLUSHIE_BINARY_PATH=/path/to/plushie"
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download(version: str | None = None) -> str:
    """Download a precompiled plushie binary from GitHub releases.

    The binary is saved to the standard download directory and made
    executable on Unix systems.

    Args:
        version: Release version tag (e.g. ``"0.4.0"``). If ``None``,
            downloads the latest release.

    Returns:
        Path to the downloaded binary.

    Raises:
        RuntimeError: On download failure or unsupported platform.
        urllib.error.URLError: On network errors.
    """
    name = download_name()
    tag = f"v{version}" if version else "latest"

    if tag == "latest":
        url = f"{GITHUB_RELEASE_URL}/latest/{name}"
    else:
        url = f"{GITHUB_RELEASE_URL}/{tag}/{name}"

    dest_dir = download_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name

    logger.info("downloading plushie binary from %s", url)

    try:
        urllib.request.urlretrieve(url, str(dest))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"failed to download plushie binary from {url}: "
            f"HTTP {exc.code} {exc.reason}"
        ) from exc

    # Make executable on Unix
    if sys.platform != "win32":
        st = dest.stat()
        dest.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    logger.info("plushie binary saved to %s", dest)
    return str(dest)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "GITHUB_RELEASE_URL",
    "PlushieNotFoundError",
    "detect_arch",
    "detect_os",
    "download",
    "download_dir",
    "download_name",
    "resolve",
]
