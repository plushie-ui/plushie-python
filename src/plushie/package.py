"""Standalone package manifest helpers."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, TypedDict

from plushie import __version__
from plushie.binary import PLUSHIE_RUST_VERSION, PlushieNotFoundError
from plushie.protocol import PROTOCOL_VERSION

DEFAULT_FORWARD_ENV = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "XDG_RUNTIME_DIR",
    "WAYLAND_DISPLAY",
    "DISPLAY",
)
DEFAULT_PACKAGE_CONFIG = "plushie-package.config.toml"
RESERVED_FORWARD_ENV = frozenset(
    {"PLUSHIE_BINARY_PATH", "PLUSHIE_PACKAGE_DIR", "PLUSHIE_PACKAGE_READY_FILE"}
)

RendererKind = Literal["stock", "custom"]


class RendererManifest(TypedDict):
    """Renderer provenance recorded in a package manifest."""

    kind: RendererKind
    source: str
    path: str


class PackageManifest(TypedDict):
    """Fields required to render ``plushie-package.toml``."""

    app_id: str
    app_name: str | None
    app_version: str
    target: str
    renderer: RendererManifest
    platform_icon: str | None
    start_command: list[str]
    working_dir: str
    forward_env: list[str]
    payload_archive: str
    payload_hash: str
    payload_size: int


class PyInstallerPackageResult(TypedDict):
    """Files produced by a PyInstaller package build."""

    payload_root: Path
    payload_archive: Path
    manifest_path: Path
    renderer_path: str
    start_command: list[str]
    platform_icon: str | None


@dataclass(frozen=True, slots=True)
class PackageStartConfig:
    """Validated package start configuration."""

    working_dir: str = "."
    command: list[str] | None = None
    forward_env: list[str] | None = None


def normalize_package_target(os_name: str, arch: str) -> str:
    """Normalize an OS and architecture to the Plushie package target."""
    os_key = os_name.lower()
    if os_key.startswith("linux"):
        os_part = "linux"
    elif os_key.startswith("darwin") or os_key == "macos":
        os_part = "darwin"
    elif os_key in {"win32", "windows", "cygwin", "msys"} or os_key.startswith("mingw"):
        os_part = "windows"
    else:
        raise ValueError(f"unsupported package OS: {os_name}")

    arch_key = arch.lower()
    if arch_key in {"amd64", "x64", "x86_64"}:
        arch_part = "x86_64"
    elif arch_key in {"arm64", "aarch64"}:
        arch_part = "aarch64"
    else:
        raise ValueError(f"unsupported package architecture: {arch}")

    return f"{os_part}-{arch_part}"


def package_target() -> str:
    """Return the current host package target."""
    return normalize_package_target(platform.system(), platform.machine())


def sha256_file(path: str | Path) -> str:
    """Return the hex SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path: str | Path) -> int:
    """Return the file size in bytes."""
    return Path(path).stat().st_size


def load_package_config(path: str | Path | None = None) -> PackageStartConfig | None:
    """Load ``plushie-package.config.toml`` package start configuration.

    Missing default config returns ``None`` so packaging keeps its existing
    defaults. An explicit path must exist and parse successfully.
    """
    config_path = Path(DEFAULT_PACKAGE_CONFIG if path is None else path)
    if path is None and not config_path.exists():
        return None
    if not config_path.is_file():
        raise FileNotFoundError(f"package config does not exist: {config_path}")

    with config_path.open("rb") as file:
        data = tomllib.load(file)
    return _parse_package_config(data, config_path)


def default_start_config(command: list[str] | None = None) -> PackageStartConfig:
    """Return the default package start config for Python payloads."""
    return PackageStartConfig(
        working_dir=".",
        command=["bin/connect"] if command is None else command,
        forward_env=list(DEFAULT_FORWARD_ENV),
    )


def render_package_config(config: PackageStartConfig | None = None) -> str:
    """Render a developer-owned package config template."""
    cfg = default_start_config() if config is None else config
    command = cfg.command if cfg.command is not None else ["bin/connect"]
    forward_env = (
        cfg.forward_env if cfg.forward_env is not None else list(DEFAULT_FORWARD_ENV)
    )
    lines = [
        "# Plushie standalone package config.",
        "# Commit this file and edit it when the packaged app needs a",
        "# different entry point, working directory, or forwarded environment.",
        "",
        "config_version = 1",
        "",
        "[start]",
        "# Relative to the extracted app package.",
        f"working_dir = {_toml_string(cfg.working_dir)}",
        "# Structured argv. The first item is the packaged host executable.",
        f"command = {_toml_array(command)}",
        "# Environment variable names copied from the parent process.",
        "forward_env = [",
    ]
    lines.extend(f"  {_toml_string(name)}," for name in forward_env)
    lines.extend(["]", ""])
    return "\n".join(lines)


def write_package_config(
    path: str | Path = DEFAULT_PACKAGE_CONFIG,
    config: PackageStartConfig | None = None,
) -> None:
    """Write a developer-owned package config template."""
    cfg = default_start_config() if config is None else config
    _validate_payload_relative_path(cfg.working_dir, Path(path), "start.working_dir")
    _validate_start_command(cfg.command or ["bin/connect"], Path(path))
    _validate_forward_env(cfg.forward_env or list(DEFAULT_FORWARD_ENV), Path(path))
    Path(path).write_text(render_package_config(cfg), encoding="utf-8")


def _parse_package_config(data: dict[str, Any], path: Path) -> PackageStartConfig:
    version = data.get("config_version")
    if version != 1:
        raise ValueError(f"{path}: config_version must be 1")

    start = data.get("start", {})
    if not isinstance(start, dict):
        raise ValueError(f"{path}: [start] must be a table")

    working_dir = start.get("working_dir", ".")
    if not isinstance(working_dir, str):
        raise ValueError(f"{path}: start.working_dir must be a string")
    _validate_payload_relative_path(working_dir, path, "start.working_dir")

    raw_command = start.get("command")
    command = None
    if raw_command is not None:
        command = _validate_start_command(raw_command, path)

    raw_forward_env = start.get("forward_env")
    forward_env = None
    if raw_forward_env is not None:
        forward_env = _validate_forward_env(raw_forward_env, path)

    return PackageStartConfig(
        working_dir=working_dir,
        command=command,
        forward_env=forward_env,
    )


def _validate_start_command(value: object, path: Path) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{path}: start.command must be an array")
    if not value:
        raise ValueError(f"{path}: start.command must not be empty")
    command: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or item == "":
            raise ValueError(
                f"{path}: start.command[{index}] must be a non-empty string"
            )
        command.append(item)
    _validate_payload_relative_path(command[0], path, "start.command[0]")
    return command


def _validate_forward_env(value: object, path: Path) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{path}: start.forward_env must be an array")
    names: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or item == "":
            raise ValueError(
                f"{path}: start.forward_env[{index}] must be a non-empty string"
            )
        if "," in item or "=" in item:
            raise ValueError(
                f"{path}: start.forward_env[{index}] must not contain comma or equals"
            )
        if item in RESERVED_FORWARD_ENV:
            raise ValueError(f"{path}: start.forward_env[{index}] is reserved")
        names.append(item)
    return names


def _validate_payload_relative_path(value: str, path: Path, field: str) -> None:
    posix_candidate = PurePosixPath(value)
    windows_candidate = PureWindowsPath(value)
    if posix_candidate.is_absolute() or windows_candidate.is_absolute():
        raise ValueError(f"{path}: {field} must be payload-relative")
    if ".." in posix_candidate.parts or ".." in windows_candidate.parts:
        raise ValueError(f"{path}: {field} must not contain parent traversal")


def render_manifest(manifest: PackageManifest) -> str:
    """Render a Plushie package manifest as TOML."""
    lines = [
        "schema_version = 1",
        f"app_id = {_toml_string(manifest['app_id'])}",
    ]
    if manifest["app_name"] is not None:
        lines.append(f"app_name = {_toml_string(manifest['app_name'])}")
    lines.extend(
        [
            f"app_version = {_toml_string(manifest['app_version'])}",
            f"target = {_toml_string(manifest['target'])}",
            'host_sdk = "python"',
            f"host_sdk_version = {_toml_string(__version__)}",
            f"plushie_rust_version = {_toml_string(PLUSHIE_RUST_VERSION)}",
            f"protocol_version = {PROTOCOL_VERSION}",
            "",
            "[start]",
            f"working_dir = {_toml_string(manifest['working_dir'])}",
            f"command = {_toml_array(manifest['start_command'])}",
            f"forward_env = {_toml_array(manifest['forward_env'])}",
            "",
            "[renderer]",
            f"path = {_toml_string(manifest['renderer']['path'])}",
            f"kind = {_toml_string(manifest['renderer']['kind'])}",
            f"source = {_toml_string(manifest['renderer']['source'])}",
            "",
        ]
    )
    if manifest["platform_icon"] is not None:
        lines.extend(
            [
                "[platform]",
                f"icon = {_toml_string(manifest['platform_icon'])}",
                "",
            ]
        )
    lines.extend(
        [
            "[payload]",
            f"archive = {_toml_string(manifest['payload_archive'])}",
            f"hash = {_toml_string('sha256:' + manifest['payload_hash'])}",
            f"size = {manifest['payload_size']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(path: str | Path, manifest: PackageManifest) -> None:
    """Write a Plushie package manifest to ``path``."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_manifest(manifest), encoding="utf-8")


def manifest_for_payload(
    *,
    app_id: str,
    app_version: str,
    renderer_path: str,
    start_command: list[str],
    payload_archive: str | Path,
    app_name: str | None = None,
    target: str | None = None,
    renderer_kind: RendererKind = "stock",
    renderer_source: str = "local-resolve",
    platform_icon: str | None = None,
    working_dir: str = ".",
    forward_env: list[str] | None = None,
) -> PackageManifest:
    """Build manifest values for an existing payload archive."""
    archive_path = Path(payload_archive)
    return {
        "app_id": app_id,
        "app_name": app_name,
        "app_version": app_version,
        "target": target or package_target(),
        "renderer": {
            "kind": renderer_kind,
            "source": renderer_source,
            "path": renderer_path,
        },
        "platform_icon": platform_icon,
        "start_command": start_command,
        "working_dir": working_dir,
        "forward_env": list(
            DEFAULT_FORWARD_ENV if forward_env is None else forward_env
        ),
        "payload_archive": os.fspath(archive_path.name),
        "payload_hash": sha256_file(archive_path),
        "payload_size": file_size(archive_path),
    }


def package_pyinstaller_payload(
    *,
    entry: str | Path,
    name: str,
    app_id: str,
    app_version: str,
    app_name: str | None = None,
    target: str | None = None,
    renderer_kind: RendererKind = "stock",
    renderer_source: str | None = None,
    app_icon: str | Path | None = None,
    add_data: list[str] | None = None,
    hidden_import: list[str] | None = None,
    collect_submodules: list[str] | None = None,
    pyinstaller_arg: list[str] | None = None,
    package_dir: str | Path = Path("dist") / "package",
    dist_dir: str | Path = "dist",
    spec_dir: str | Path = Path("build") / "pyinstaller-spec",
    work_dir: str | Path = Path("build") / "pyinstaller",
    output: str | Path | None = None,
    working_dir: str = ".",
    start_command: list[str] | None = None,
    forward_env: list[str] | None = None,
) -> PyInstallerPackageResult:
    """Build a PyInstaller payload and write ``plushie-package.toml``.

    The payload contains the PyInstaller one-folder app under ``host/``,
    a payload-local renderer under ``bin/``, and platform icon assets
    under ``assets/``. The payload archive is written before the
    manifest so the manifest records the final archive hash and size.
    """
    package_root = Path(package_dir)
    payload_root = package_root / "payload"
    payload_archive = package_root / "payload.tar.zst"
    manifest_path = (
        Path(output) if output is not None else package_root / "plushie-package.toml"
    )

    prepared_renderer, resolved_renderer_source = _prepare_renderer_for_pyinstaller(
        renderer_kind
    )
    effective_renderer_source = renderer_source or resolved_renderer_source

    _run_pyinstaller(
        entry=Path(entry),
        name=name,
        prepared_renderer=prepared_renderer,
        app_icon=Path(app_icon) if app_icon is not None else None,
        add_data=add_data or [],
        hidden_import=hidden_import or [],
        collect_submodules=collect_submodules or [],
        pyinstaller_arg=pyinstaller_arg or [],
        dist_dir=Path(dist_dir),
        spec_dir=Path(spec_dir),
        work_dir=Path(work_dir),
    )

    if payload_root.exists():
        shutil.rmtree(payload_root)
    payload_root.mkdir(parents=True)

    renderer_rel = _payload_renderer_path()
    renderer_dest = payload_root / renderer_rel
    renderer_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prepared_renderer, renderer_dest)
    _ensure_executable(renderer_dest)

    host_rel = _payload_host_executable_path(name)
    host_root = payload_root / "host" / name
    host_root.parent.mkdir(parents=True, exist_ok=True)
    source_host = Path(dist_dir) / name
    if not source_host.is_dir():
        raise FileNotFoundError(f"PyInstaller output missing at {source_host}")
    if host_root.exists():
        shutil.rmtree(host_root)
    shutil.copytree(source_host, host_root, symlinks=True)
    _remove_nested_renderer(host_root)

    platform_icon = _materialize_platform_icon(
        payload_root,
        app_icon=Path(app_icon) if app_icon is not None else None,
    )

    _dereference_payload_symlinks(payload_root)
    archive_payload(payload_root, payload_archive)

    effective_start_command = [host_rel] if start_command is None else start_command

    manifest = manifest_for_payload(
        app_id=app_id,
        app_name=app_name,
        app_version=app_version,
        target=target,
        renderer_kind=renderer_kind,
        renderer_source=effective_renderer_source,
        renderer_path=renderer_rel,
        start_command=effective_start_command,
        working_dir=working_dir,
        forward_env=forward_env,
        platform_icon=platform_icon,
        payload_archive=payload_archive,
    )
    write_manifest(manifest_path, manifest)

    return {
        "payload_root": payload_root,
        "payload_archive": payload_archive,
        "manifest_path": manifest_path,
        "renderer_path": renderer_rel,
        "start_command": effective_start_command,
        "platform_icon": platform_icon,
    }


def archive_payload(payload_dir: str | Path, archive_path: str | Path) -> None:
    """Write a deterministic ``.tar.zst`` archive for a package payload."""
    payload_root = Path(payload_dir)
    archive = Path(archive_path)
    archive.parent.mkdir(parents=True, exist_ok=True)
    _validate_payload_archive_inputs(payload_root)

    tar_bin = _archive_tar_command()
    if _archive_tar_supports_zstd(tar_bin):
        subprocess.run(
            [
                tar_bin,
                "-C",
                os.fspath(payload_root),
                "--sort=name",
                "--mtime=UTC 1970-01-01",
                "--owner=0",
                "--group=0",
                "--numeric-owner",
                "--zstd",
                "-cf",
                os.fspath(archive),
                ".",
            ],
            check=True,
        )
        return

    if not _archive_tar_supports_gnu_flags(tar_bin):
        raise RuntimeError(
            "GNU tar or gtar is required for deterministic payload archives"
        )

    zstd = shutil.which("zstd")
    if zstd is None:
        raise RuntimeError("missing required command: zstd")

    tar_proc = subprocess.Popen(
        [
            tar_bin,
            "-C",
            os.fspath(payload_root),
            "--sort=name",
            "--mtime=UTC 1970-01-01",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "-cf",
            "-",
            ".",
        ],
        stdout=subprocess.PIPE,
    )
    try:
        zstd_proc = subprocess.run(
            [zstd, "-q", "-o", os.fspath(archive)],
            stdin=tar_proc.stdout,
            check=False,
        )
        if tar_proc.stdout is not None:
            tar_proc.stdout.close()
        tar_return = tar_proc.wait()
    finally:
        if tar_proc.poll() is None:
            tar_proc.kill()

    if tar_return != 0:
        raise subprocess.CalledProcessError(tar_return, tar_bin)
    if zstd_proc.returncode != 0:
        raise subprocess.CalledProcessError(zstd_proc.returncode, zstd)


def _prepare_renderer_for_pyinstaller(
    renderer_kind: RendererKind = "stock",
) -> tuple[Path, str]:
    renderer, source = _resolve_package_renderer(renderer_kind)
    prepared = Path("build") / "standalone" / "renderer" / _renderer_binary_name()
    prepared.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(renderer, prepared)
    _ensure_executable(prepared)
    return prepared, source


def _resolve_package_renderer(
    renderer_kind: RendererKind = "stock",
) -> tuple[Path, str]:
    if renderer_kind == "custom":
        return _resolve_custom_package_renderer()

    env_binary = os.environ.get("PLUSHIE_BINARY_PATH")
    if env_binary:
        path = Path(env_binary)
        if not path.is_file():
            raise FileNotFoundError(f"PLUSHIE_BINARY_PATH does not exist: {env_binary}")
        return path.resolve(), "local-path"

    source_path = os.environ.get("PLUSHIE_RUST_SOURCE_PATH")
    if source_path:
        manifest = Path(source_path) / "Cargo.toml"
        if not manifest.is_file():
            raise FileNotFoundError(
                f"PLUSHIE_RUST_SOURCE_PATH does not contain Cargo.toml: {source_path}"
            )
        target_dir = Path("build") / "standalone" / "cargo-target"
        subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "-p",
                "plushie-renderer",
                "--manifest-path",
                os.fspath(manifest),
                "--target-dir",
                os.fspath(target_dir),
            ],
            check=True,
        )
        built = target_dir.resolve() / "release" / _renderer_binary_name()
        if not built.is_file():
            raise FileNotFoundError(
                f"cargo build completed but renderer is missing at {built}"
            )
        return built, "local-build"

    from plushie.binary import download, resolve

    try:
        return Path(resolve()).resolve(), "local-resolve"
    except PlushieNotFoundError:
        return Path(download()).resolve(), "download"


def _resolve_custom_package_renderer() -> tuple[Path, str]:
    env_binary = os.environ.get("PLUSHIE_BINARY_PATH")
    if env_binary:
        path = Path(env_binary)
        if not path.is_file():
            raise FileNotFoundError(f"PLUSHIE_BINARY_PATH does not exist: {env_binary}")
        return path.resolve(), "local-path"

    raise RuntimeError(
        "custom renderer packaging requires an explicit custom renderer binary. "
        "Set PLUSHIE_BINARY_PATH to the renderer built for this app."
    )


def _run_pyinstaller(
    *,
    entry: Path,
    name: str,
    prepared_renderer: Path,
    app_icon: Path | None,
    add_data: list[str],
    hidden_import: list[str],
    collect_submodules: list[str],
    pyinstaller_arg: list[str],
    dist_dir: Path,
    spec_dir: Path,
    work_dir: Path,
) -> None:
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        name,
        "--specpath",
        os.fspath(spec_dir),
        "--distpath",
        os.fspath(dist_dir),
        "--workpath",
        os.fspath(work_dir),
        "--add-binary",
        f"{prepared_renderer.resolve()}{os.pathsep}.",
        "--noconfirm",
    ]
    if app_icon is not None:
        args += ["--icon", os.fspath(app_icon)]
    for value in add_data:
        args += ["--add-data", value]
    for value in hidden_import:
        args += ["--hidden-import", value]
    for value in collect_submodules:
        args += ["--collect-submodules", value]
    args += pyinstaller_arg
    args.append(os.fspath(entry))
    subprocess.run(args, check=True)


def _materialize_platform_icon(
    payload_root: Path, *, app_icon: Path | None
) -> str | None:
    assets = payload_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    if app_icon is not None:
        dest = assets / app_icon.name
        shutil.copy2(app_icon, dest)
        return _payload_relative(payload_root, dest)

    _run_cargo_plushie("default-icons", "--out", os.fspath(assets))
    default_icon = assets / "plushie-checkbox-512x512.png"
    if default_icon.is_file():
        return _payload_relative(payload_root, default_icon)
    return None


def _run_cargo_plushie(subcommand: str, *args: str) -> None:
    from plushie.cargo_plushie import resolve_cargo_plushie

    command, prefix = resolve_cargo_plushie()
    subprocess.run(
        [command, *prefix, subcommand, *args],
        check=True,
    )


def _payload_renderer_path() -> str:
    return f"bin/{_renderer_binary_name()}"


def _payload_host_executable_path(name: str) -> str:
    executable = f"{name}.exe" if sys.platform in ("win32", "cygwin") else name
    return f"host/{name}/{executable}"


def _renderer_binary_name() -> str:
    return (
        "plushie-renderer.exe"
        if sys.platform in ("win32", "cygwin")
        else "plushie-renderer"
    )


def _ensure_executable(path: Path) -> None:
    if sys.platform in ("win32", "cygwin"):
        return
    mode = path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    path.chmod(mode)


def _remove_nested_renderer(root: Path) -> None:
    for candidate in root.rglob(_renderer_binary_name()):
        if candidate.is_file():
            candidate.unlink()


def _payload_relative(payload_root: Path, path: Path) -> str:
    return path.relative_to(payload_root).as_posix()


def _validate_payload_archive_inputs(payload_root: Path) -> None:
    for path in payload_root.rglob("*"):
        try:
            stat_result = path.lstat()
        except OSError as exc:
            raise RuntimeError(f"payload path cannot be inspected: {path}") from exc
        mode = stat_result.st_mode
        rel = path.relative_to(payload_root)
        if stat.S_ISLNK(mode):
            raise RuntimeError(f"payload contains unsupported symlink: {rel}")
        if (
            stat.S_ISFIFO(mode)
            or stat.S_ISSOCK(mode)
            or stat.S_ISBLK(mode)
            or stat.S_ISCHR(mode)
        ):
            raise RuntimeError(f"payload contains unsupported special file: {rel}")
        if stat.S_ISREG(mode) and stat_result.st_nlink > 1:
            raise RuntimeError(f"payload contains unsupported hard-linked file: {rel}")


def _dereference_payload_symlinks(payload_root: Path) -> None:
    links = [path for path in payload_root.rglob("*") if path.is_symlink()]
    for link in links:
        target = link.resolve(strict=True)
        tmp = link.with_name(f"{link.name}.deref.{os.getpid()}")
        if target.is_dir():
            shutil.copytree(target, tmp)
        else:
            shutil.copy2(target, tmp)
        link.unlink()
        tmp.rename(link)


def _archive_tar_command() -> str:
    if _is_gnu_tar("tar"):
        return "tar"
    gtar = shutil.which("gtar")
    if gtar is not None:
        return gtar
    return "tar"


def _archive_tar_supports_gnu_flags(tar_bin: str) -> bool:
    return tar_bin != "tar" or _is_gnu_tar("tar")


def _archive_tar_supports_zstd(tar_bin: str) -> bool:
    if not _archive_tar_supports_gnu_flags(tar_bin):
        return False
    result = subprocess.run(
        [tar_bin, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and "--zstd" in result.stdout


def _is_gnu_tar(tar_bin: str) -> bool:
    result = subprocess.run(
        [tar_bin, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and "GNU tar" in result.stdout


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"
