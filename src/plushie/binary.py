"""Binary resolution, download, and platform detection for the plushie renderer.

Resolution chain for ``resolve()``:

1. ``PLUSHIE_BINARY_PATH`` environment variable (fail-fast if set but missing)
2. Custom extension build in ``build/*/target/``
3. Downloaded binary in ``~/.local/share/plushie/bin/``
4. Bundled binary (PyInstaller, Nuitka, Briefcase)
5. ``plushie`` on system PATH via ``shutil.which``

Platform detection identifies os (linux/darwin/windows) and arch
(x86_64/aarch64) for download naming.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("plushie")

GITHUB_RELEASE_URL = "https://github.com/plushie-ui/plushie/releases/download"
"""Base URL for GitHub release asset downloads."""

WASM_ARCHIVE_NAME = "plushie-wasm.tar.gz"
"""Filename of the WASM renderer archive on GitHub releases."""

WASM_JS_NAME = "plushie_wasm.js"
"""JS entry point filename inside the WASM bundle."""

WASM_BG_NAME = "plushie_wasm_bg.wasm"
"""Background WASM binary filename inside the WASM bundle."""


class PlushieNotFoundError(FileNotFoundError):
    """Raised when the plushie binary cannot be resolved.

    The error message lists the resolution chain and provides install
    instructions.
    """


class WasmNotFoundError(FileNotFoundError):
    """Raised when the WASM renderer files cannot be resolved."""


class ChecksumError(RuntimeError):
    """Raised when SHA-256 verification of a downloaded artifact fails."""


BINARY_VERSION = "0.4.1"
"""Default plushie binary version. Matches the renderer protocol this SDK was built against."""

MIN_RUST_VERSION = (1, 92, 0)
"""Minimum required Rust toolchain version for building from source."""


# ---------------------------------------------------------------------------
# Checksum verification
# ---------------------------------------------------------------------------


def _verify_checksum(file_path: Path, checksum_url: str) -> None:
    """Fetch ``{url}.sha256`` and verify the file's SHA-256 digest.

    Downloads the checksum file from *checksum_url*, computes the SHA-256
    of *file_path*, and compares the two. On mismatch or if the checksum
    file cannot be fetched, deletes *file_path* and raises.

    Args:
        file_path: Local file to verify.
        checksum_url: URL to the ``.sha256`` sidecar file.

    Raises:
        ChecksumError: On mismatch or if the checksum file is unavailable.
    """
    try:
        with urllib.request.urlopen(checksum_url) as resp:
            body = resp.read().decode("utf-8").strip()
    except (urllib.error.URLError, OSError) as exc:
        file_path.unlink(missing_ok=True)
        raise ChecksumError(
            f"SHA-256 checksum file could not be downloaded ({exc}). "
            f"Refusing to use unverified artifact. URL: {checksum_url}"
        ) from exc

    expected = body.split()[0].lower()
    actual = hashlib.sha256(file_path.read_bytes()).hexdigest()

    if actual != expected:
        file_path.unlink(missing_ok=True)
        raise ChecksumError(f"Checksum mismatch! Expected {expected}, got {actual}")

    logger.info("checksum verified for %s", file_path)


# ---------------------------------------------------------------------------
# Rust version check
# ---------------------------------------------------------------------------


def check_rust_version() -> None:
    """Verify that ``rustc`` is installed and meets the minimum version.

    Raises:
        RuntimeError: If rustc is not found or the version is too old.
    """
    min_str = ".".join(str(v) for v in MIN_RUST_VERSION)

    try:
        result = subprocess.run(
            ["rustc", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"rustc not found. Install Rust {min_str}+ via https://rustup.rs"
        ) from exc

    match = re.search(r"rustc (\d+)\.(\d+)\.(\d+)", result.stdout)
    if not match:
        raise RuntimeError(
            f"could not parse rustc version from: {result.stdout.strip()}"
        )

    version = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if version < MIN_RUST_VERSION:
        version_str = ".".join(str(v) for v in version)
        raise RuntimeError(
            f"rustc {version_str} detected, but plushie requires >= {min_str}. "
            f"Upgrade with `rustup update`."
        )


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


# ---------------------------------------------------------------------------
# WASM directory
# ---------------------------------------------------------------------------


def wasm_dir() -> Path:
    """Return the standard directory for WASM renderer files.

    Uses ``~/.local/share/plushie/wasm/`` on Linux/macOS and
    ``%LOCALAPPDATA%/plushie/wasm/`` on Windows.

    Returns:
        Path to the WASM directory (may not exist yet).
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "plushie" / "wasm"


def wasm_download_name() -> str:
    """Return the WASM archive filename for downloads.

    Returns:
        ``"plushie-wasm.tar.gz"``.
    """
    return WASM_ARCHIVE_NAME


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
# Custom extension build resolution
# ---------------------------------------------------------------------------


def _resolve_custom_build() -> str | None:
    """Check for a custom-built binary in the build/ directory.

    Looks for binaries built by ``python -m plushie build`` in
    ``build/*/target/{release,debug}/``. Checks release first,
    then debug.

    Returns:
        Absolute path to the binary if found, ``None`` otherwise.
    """
    build_root = Path("build")
    if not build_root.is_dir():
        return None

    ext = ".exe" if sys.platform in ("win32", "cygwin") else ""

    for build_dir in build_root.iterdir():
        if not build_dir.is_dir():
            continue
        for profile in ("release", "debug"):
            candidate = build_dir / "target" / profile / f"{build_dir.name}{ext}"
            if candidate.is_file() and _is_native_binary(str(candidate)):
                return str(candidate.resolve())

    return None


# ---------------------------------------------------------------------------
# Bundled binary resolution (PyInstaller / Nuitka / Briefcase)
# ---------------------------------------------------------------------------


def _resolve_bundled() -> str | None:
    """Check for plushie binary in common bundled/packaged locations.

    Checks (in order):

    1. PyInstaller's ``sys._MEIPASS`` temporary directory
    2. Adjacent to this Python file (Nuitka, Briefcase)
    3. Adjacent to the running executable (``sys.executable``)

    Returns:
        Absolute path to the binary if found, ``None`` otherwise.
    """
    binary_name = (
        "plushie-renderer.exe"
        if sys.platform in ("win32", "cygwin")
        else "plushie-renderer"
    )

    # PyInstaller: frozen apps unpack data to sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        candidate = os.path.join(meipass, binary_name)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    # Adjacent to this source file (Nuitka, Briefcase)
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(pkg_dir, binary_name)
    if os.path.isfile(candidate) and _is_native_binary(candidate):
        return os.path.abspath(candidate)

    # Adjacent to the running executable
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidate = os.path.join(exe_dir, binary_name)
    if os.path.isfile(candidate) and _is_native_binary(candidate):
        return os.path.abspath(candidate)

    return None


# ---------------------------------------------------------------------------
# Resolution chain
# ---------------------------------------------------------------------------


def resolve() -> str:
    """Resolve the path to the plushie binary.

    Resolution order:

    1. ``PLUSHIE_BINARY_PATH`` environment variable -- if set but the
       file does not exist, raises immediately (explicit config should
       not silently fall through).
    2. Custom extension build in ``build/*/target/``.
    3. Downloaded binary in the standard download directory.
    4. Bundled binary (PyInstaller, Nuitka, Briefcase).
    5. ``plushie`` on the system PATH.

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

    # Step 2: custom extension build in build/ directory
    custom = _resolve_custom_build()
    if custom is not None:
        return custom

    # Step 3: downloaded binary
    try:
        name = download_name()
        downloaded = download_dir() / name
        if downloaded.is_file():
            return str(downloaded)
    except RuntimeError:
        # Platform detection failed -- skip this step
        pass

    # Step 4: bundled binary (PyInstaller / Nuitka / Briefcase)
    bundled = _resolve_bundled()
    if bundled is not None:
        return bundled

    # Step 5: system PATH (native binaries only, not Python scripts)
    which_path = shutil.which("plushie-renderer")
    if which_path is not None and _is_native_binary(which_path):
        return os.path.abspath(which_path)

    try:
        dl_dir = str(download_dir())
    except RuntimeError:
        dl_dir = "~/.local/share/plushie/bin/"

    raise PlushieNotFoundError(
        "plushie-renderer binary not found.\n"
        "\n"
        "Resolution chain (checked in order):\n"
        "  1. PLUSHIE_BINARY_PATH environment variable (not set)\n"
        "  2. Custom extension build in build/ (not found)\n"
        f"  3. Downloaded binary in {dl_dir} (not found)\n"
        "  4. Bundled binary (PyInstaller/Nuitka/Briefcase) (not found)\n"
        "  5. 'plushie-renderer' on system PATH (not found)\n"
        "\n"
        "To download a precompiled binary:\n"
        "  python -m plushie download\n"
        "\n"
        "To use an existing binary:\n"
        "  export PLUSHIE_BINARY_PATH=/path/to/plushie-renderer"
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download(version: str | None = None, *, force: bool = False) -> str:
    """Download a precompiled plushie binary from GitHub releases.

    The binary is saved to the standard download directory and made
    executable on Unix systems. After download, the SHA-256 checksum
    is verified against the sidecar ``.sha256`` file on GitHub.

    Args:
        version: Release version tag (e.g. ``"0.4.0"``). If ``None``,
            uses ``BINARY_VERSION`` (the pinned default for this SDK).
        force: Re-download even if the binary already exists.

    Returns:
        Path to the downloaded binary.

    Raises:
        RuntimeError: On download failure or unsupported platform.
        ChecksumError: On checksum mismatch or unavailable checksum.
        urllib.error.URLError: On network errors.
    """
    name = download_name()
    tag = f"v{version or BINARY_VERSION}"
    url = f"{GITHUB_RELEASE_URL}/{tag}/{name}"

    dest_dir = download_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name

    if dest.is_file() and not force:
        logger.info(
            "binary already exists at %s -- use force=True to re-download", dest
        )
        return str(dest)

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

    _verify_checksum(dest, f"{url}.sha256")

    logger.info("plushie binary saved to %s", dest)
    return str(dest)


# ---------------------------------------------------------------------------
# WASM download
# ---------------------------------------------------------------------------


def download_wasm(version: str | None = None, *, force: bool = False) -> str:
    """Download the WASM renderer bundle from GitHub releases.

    Downloads ``plushie-wasm.tar.gz``, verifies its SHA-256 checksum,
    then extracts ``plushie_wasm.js`` and ``plushie_wasm_bg.wasm`` into
    the standard WASM directory.

    Args:
        version: Release version tag (e.g. ``"0.4.0"``). If ``None``,
            uses ``BINARY_VERSION`` (the pinned default for this SDK).
        force: Re-download even if WASM files already exist.

    Returns:
        Path to the WASM directory containing the extracted files.

    Raises:
        RuntimeError: On download failure or extraction error.
        ChecksumError: On checksum mismatch or unavailable checksum.
    """
    archive_name = wasm_download_name()
    tag = f"v{version or BINARY_VERSION}"
    url = f"{GITHUB_RELEASE_URL}/{tag}/{archive_name}"

    dest_dir = wasm_dir()
    js_path = dest_dir / WASM_JS_NAME
    wasm_path = dest_dir / WASM_BG_NAME

    if js_path.is_file() and wasm_path.is_file() and not force:
        logger.info(
            "WASM files already exist in %s -- use force=True to re-download",
            dest_dir,
        )
        return str(dest_dir)

    dest_dir.mkdir(parents=True, exist_ok=True)
    tarball = dest_dir / archive_name

    logger.info("downloading WASM bundle from %s", url)

    try:
        urllib.request.urlretrieve(url, str(tarball))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"failed to download WASM bundle from {url}: "
            f"HTTP {exc.code} {exc.reason}\n\n"
            f"To build from source instead:\n"
            f"  python -m plushie build --wasm"
        ) from exc

    _verify_checksum(tarball, f"{url}.sha256")

    # Extract and clean up tarball
    try:
        with tarfile.open(str(tarball), "r:gz") as tf:
            tf.extractall(path=str(dest_dir), filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise RuntimeError(f"failed to extract WASM bundle: {exc}") from exc
    finally:
        tarball.unlink(missing_ok=True)

    logger.info("WASM files extracted to %s", dest_dir)
    return str(dest_dir)


# ---------------------------------------------------------------------------
# WASM build
# ---------------------------------------------------------------------------


def build_wasm(
    source_path: str | None = None,
    *,
    release: bool = False,
) -> str:
    """Build the WASM renderer from source using wasm-pack.

    Requires ``wasm-pack`` to be installed and the plushie Rust source
    checkout to contain a ``plushie-renderer-wasm`` crate directory.

    Args:
        source_path: Path to the plushie Rust source checkout. If
            ``None``, reads from ``PLUSHIE_SOURCE_PATH`` env var.
        release: Build with optimizations. Default is debug build.

    Returns:
        Path to the WASM output directory.

    Raises:
        RuntimeError: If wasm-pack is not found, source path is
            invalid, or the build fails.
    """
    # Verify wasm-pack is available
    try:
        subprocess.run(
            ["wasm-pack", "--version"],
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "wasm-pack not found. Install via https://rustwasm.github.io/wasm-pack/"
        ) from exc

    # Resolve source path
    src = source_path or os.environ.get("PLUSHIE_SOURCE_PATH")
    if src is None:
        raise RuntimeError(
            "plushie source path not specified.\n\n"
            "Set PLUSHIE_SOURCE_PATH or pass source_path= argument."
        )

    wasm_crate = os.path.join(src, "plushie-renderer-wasm")
    if not os.path.isdir(wasm_crate):
        raise RuntimeError(
            f"plushie-renderer-wasm crate not found at {wasm_crate}.\n\n"
            f"The WASM build requires the plushie source checkout to "
            f"include the plushie-renderer-wasm crate directory."
        )

    profile = "--release" if release else "--dev"
    logger.info(
        "building plushie-renderer-wasm%s from %s",
        " (release)" if release else "",
        wasm_crate,
    )

    result = subprocess.run(
        ["wasm-pack", "build", "--target", "web", profile],
        cwd=wasm_crate,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"wasm-pack build failed (exit code {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    # Copy output to standard WASM directory
    pkg_dir = os.path.join(wasm_crate, "pkg")
    dest = wasm_dir()
    dest.mkdir(parents=True, exist_ok=True)

    for name in [WASM_JS_NAME, WASM_BG_NAME]:
        src_file = os.path.join(pkg_dir, name)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, str(dest / name))
        else:
            logger.warning("expected %s not found in wasm-pack output", src_file)

    logger.info("WASM files installed to %s", dest)
    return str(dest)


# ---------------------------------------------------------------------------
# WASM resolution
# ---------------------------------------------------------------------------


def resolve_wasm() -> tuple[Path, Path]:
    """Resolve paths to the WASM renderer JS and WASM files.

    Checks the standard WASM directory for ``plushie_wasm.js`` and
    ``plushie_wasm_bg.wasm``.

    Returns:
        Tuple of ``(js_path, wasm_path)``.

    Raises:
        WasmNotFoundError: If either file is missing.
    """
    d = wasm_dir()
    js_path = d / WASM_JS_NAME
    wasm_path = d / WASM_BG_NAME

    if not js_path.is_file() or not wasm_path.is_file():
        raise WasmNotFoundError(
            f"WASM renderer files not found in {d}.\n"
            "\n"
            "To download the precompiled WASM bundle:\n"
            "  python -m plushie download --wasm\n"
            "\n"
            "To build from source:\n"
            "  python -m plushie build --wasm"
        )

    return js_path, wasm_path


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "BINARY_VERSION",
    "GITHUB_RELEASE_URL",
    "MIN_RUST_VERSION",
    "WASM_ARCHIVE_NAME",
    "WASM_BG_NAME",
    "WASM_JS_NAME",
    "ChecksumError",
    "PlushieNotFoundError",
    "WasmNotFoundError",
    "build_wasm",
    "check_rust_version",
    "detect_arch",
    "detect_os",
    "download",
    "download_dir",
    "download_name",
    "download_wasm",
    "resolve",
    "resolve_wasm",
    "wasm_dir",
    "wasm_download_name",
]
