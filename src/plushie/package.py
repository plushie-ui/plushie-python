"""Standalone package manifest helpers."""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from plushie import __version__
from plushie.binary import PLUSHIE_RUST_VERSION
from plushie.protocol import PROTOCOL_VERSION

DEFAULT_PACKAGE_CONFIG = "plushie-package.config.toml"

InstallScope = Literal["perUser", "perMachine"]
RendererKind = Literal["stock", "custom"]


@dataclass(frozen=True, slots=True)
class PackageStartConfig:
    """Validated package start configuration."""

    working_dir: str = "."
    command: list[str] | None = None
    forward_env: list[str] | None = None
    platform: dict = field(default_factory=dict)  # type: ignore[assignment]


class PyInstallerPackageResult(dict):
    """Files produced by a PyInstaller package build."""


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


def default_start_config(command: list[str] | None = None) -> PackageStartConfig:
    """Return the default package start config for Python payloads."""
    return PackageStartConfig(
        working_dir=".",
        command=["bin/connect"] if command is None else command,
    )


def pyinstaller_start_config(name: str) -> PackageStartConfig:
    """Return the package start config for a PyInstaller payload."""
    return default_start_config([_payload_host_executable_path(name)])


def render_package_config(config: PackageStartConfig | None = None) -> str:
    """Render a developer-owned package config template."""
    cfg = default_start_config() if config is None else config
    command = cfg.command if cfg.command is not None else ["bin/connect"]
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
        '# forward_env = ["PATH", "HOME", ...]',
        "",
        "# Optional platform metadata passed through to plushie-package.toml.",
        "# Remove the comment markers for any fields you want to set.",
        "# [platform]",
        '# publisher = "Example Corp"',
        '# copyright = "Copyright 2025 Example Corp"',
        '# category = "Productivity"',
        '# description = "A brief description of the app"',
        '# bundle_id = "com.example.myapp"',
        "#",
        "# [platform.macos]",
        '# bundle_version = "1"',
        "#",
        "# [platform.windows]",
        '# install_scope = "perUser"  # or "perMachine"',
        "",
    ]
    return "\n".join(lines)


def write_package_config(
    path: str | Path = DEFAULT_PACKAGE_CONFIG,
    config: PackageStartConfig | None = None,
) -> None:
    """Write a developer-owned package config template."""
    cfg = default_start_config() if config is None else config
    Path(path).write_text(render_package_config(cfg), encoding="utf-8")


def write_partial_manifest(
    path: str | Path,
    *,
    app_id: str,
    app_version: str,
    app_name: str | None = None,
    target: str | None = None,
    renderer_path: str,
    renderer_kind: RendererKind = "stock",
    start_command: list[str],
) -> None:
    """Write the partial ``plushie-package.toml`` manifest.

    cargo-plushie reads this during ``package assemble`` and fills in
    the payload archive, hash, size, and platform sections.
    """
    resolved_target = target or package_target()
    lines = [
        "schema_version = 1",
        f"app_id = {_toml_string(app_id)}",
    ]
    if app_name is not None:
        lines.append(f"app_name = {_toml_string(app_name)}")
    lines.extend(
        [
            f"app_version = {_toml_string(app_version)}",
            f"target = {_toml_string(resolved_target)}",
            'host_sdk = "python"',
            f"host_sdk_version = {_toml_string(__version__)}",
            f"plushie_rust_version = {_toml_string(PLUSHIE_RUST_VERSION)}",
            f"protocol_version = {PROTOCOL_VERSION}",
            "",
            "[start]",
            f"command = {_toml_array(start_command)}",
            "",
            "[renderer]",
            f"path = {_toml_string(renderer_path)}",
            f"kind = {_toml_string(renderer_kind)}",
            "",
        ]
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def assemble_package(
    manifest_path: str | Path,
    payload_dir: str | Path,
    *,
    package_config: str | Path | None = None,
) -> None:
    """Shell out to ``cargo plushie package assemble``.

    Raises ``subprocess.CalledProcessError`` on non-zero exit.
    """
    from plushie.cargo_plushie import resolve_cargo_plushie

    cmd, prefix = resolve_cargo_plushie()
    args = [
        cmd,
        *prefix,
        "package",
        "assemble",
        "--manifest",
        os.fspath(manifest_path),
        "--payload-dir",
        os.fspath(payload_dir),
    ]
    if package_config is not None:
        args += ["--package-config", os.fspath(package_config)]
    subprocess.run(args, check=True)


def package_pyinstaller_payload(
    *,
    entry: str | Path,
    name: str,
    app_id: str,
    app_version: str,
    app_name: str | None = None,
    target: str | None = None,
    renderer_kind: RendererKind = "stock",
    renderer_path: str | Path | None = None,
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
    start_command: list[str] | None = None,
    package_config: str | Path | None = None,
) -> dict[str, Path | str | list[str]]:
    """Build a PyInstaller payload and shell out to ``cargo plushie package assemble``.

    The payload contains the PyInstaller one-folder app under ``host/``
    and a payload-local renderer under ``bin/``. cargo-plushie handles
    archiving, hashing, platform icon materialisation, and writing the
    final ``plushie-package.toml``.
    """
    package_root = Path(package_dir)
    payload_root = package_root / "payload"
    manifest_path = (
        Path(output) if output is not None else package_root / "plushie-package.toml"
    )

    if renderer_path is None:
        prepared_renderer = _prepare_renderer_for_pyinstaller(renderer_kind)
    else:
        prepared_renderer = _prepare_renderer_for_pyinstaller(
            renderer_kind,
            renderer_path=Path(renderer_path),
        )

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

    host_root = payload_root / "host" / name
    host_root.parent.mkdir(parents=True, exist_ok=True)
    source_host = Path(dist_dir) / name
    if not source_host.is_dir():
        raise FileNotFoundError(f"PyInstaller output missing at {source_host}")
    if host_root.exists():
        shutil.rmtree(host_root)
    shutil.copytree(source_host, host_root, symlinks=True)
    _remove_nested_renderer(host_root)

    effective_start_command = (
        [_payload_host_executable_path(name)]
        if start_command is None
        else start_command
    )

    write_partial_manifest(
        manifest_path,
        app_id=app_id,
        app_name=app_name,
        app_version=app_version,
        target=target,
        renderer_kind=renderer_kind,
        renderer_path=renderer_rel,
        start_command=effective_start_command,
    )

    assemble_package(manifest_path, payload_root, package_config=package_config)

    return {
        "payload_root": payload_root,
        "manifest_path": manifest_path,
        "renderer_path": renderer_rel,
        "start_command": effective_start_command,
    }


def package_prepared_payload(
    *,
    app_id: str,
    app_version: str,
    renderer_path: str,
    start_command: list[str],
    payload_dir: str | Path,
    app_name: str | None = None,
    target: str | None = None,
    renderer_kind: RendererKind = "stock",
    manifest_out: str | Path | None = None,
    package_config: str | Path | None = None,
) -> Path:
    """Write a partial manifest for a caller-assembled payload and assemble.

    Returns the manifest path.
    """
    manifest_path = Path(
        manifest_out
        if manifest_out is not None
        else "dist/package/plushie-package.toml"
    )

    write_partial_manifest(
        manifest_path,
        app_id=app_id,
        app_name=app_name,
        app_version=app_version,
        target=target,
        renderer_kind=renderer_kind,
        renderer_path=renderer_path,
        start_command=start_command,
    )

    assemble_package(manifest_path, payload_dir, package_config=package_config)

    return manifest_path


def _prepare_renderer_for_pyinstaller(
    renderer_kind: RendererKind = "stock",
    *,
    renderer_path: Path | None = None,
) -> Path:
    """Resolve and stage a renderer binary for PyInstaller bundling."""
    if renderer_path is None:
        renderer = _resolve_package_renderer(renderer_kind)
    else:
        if not renderer_path.is_file():
            raise FileNotFoundError(f"renderer_path does not exist: {renderer_path}")
        _ensure_portable_package_tools_available()
        renderer = renderer_path.resolve()

    prepared = Path("build") / "standalone" / "renderer" / _renderer_binary_name()
    prepared.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(renderer, prepared)
    _ensure_executable(prepared)
    return prepared


def _resolve_package_renderer(
    renderer_kind: RendererKind = "stock",
) -> Path:
    """Resolve the renderer binary for packaging."""
    if renderer_kind == "custom":
        return _resolve_custom_package_renderer()

    env_binary = os.environ.get("PLUSHIE_BINARY_PATH")
    if env_binary:
        path = Path(env_binary)
        if not path.is_file():
            raise FileNotFoundError(f"PLUSHIE_BINARY_PATH does not exist: {env_binary}")
        _ensure_portable_package_tools_available()
        return path.resolve()

    source_path = os.environ.get("PLUSHIE_RUST_SOURCE_PATH")
    if source_path:
        from plushie.binary import sync_renderer_with_tool

        return Path(sync_renderer_with_tool()).resolve()

    from plushie.binary import sync_renderer_with_tool

    return Path(sync_renderer_with_tool()).resolve()


def _resolve_custom_package_renderer() -> Path:
    """Resolve the renderer binary for custom packaging."""
    env_binary = os.environ.get("PLUSHIE_BINARY_PATH")
    if env_binary:
        path = Path(env_binary)
        if not path.is_file():
            raise FileNotFoundError(f"PLUSHIE_BINARY_PATH does not exist: {env_binary}")
        _ensure_portable_package_tools_available()
        return path.resolve()

    raise RuntimeError(
        "custom renderer packaging requires an explicit custom renderer binary. "
        "Set PLUSHIE_BINARY_PATH to the renderer built for this app."
    )


def _ensure_portable_package_tools_available() -> None:
    """Raise if the managed Plushie tool set is not present."""
    from plushie.binary import download_dir, launcher_name, tool_name

    missing = [
        path
        for path in (
            download_dir() / tool_name(),
            download_dir() / launcher_name(),
        )
        if not path.is_file()
    ]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise RuntimeError(
            "Portable packaging requires the managed Plushie tool set. "
            f"Missing: {missing_text}. Run `python -m plushie download`."
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
    """Invoke PyInstaller to build a one-folder app."""
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


def _payload_renderer_path() -> str:
    """Return the payload-relative path for the renderer binary."""
    return f"bin/{_renderer_binary_name()}"


def _payload_host_executable_path(name: str) -> str:
    """Return the payload-relative path for the PyInstaller host executable."""
    executable = f"{name}.exe" if sys.platform in ("win32", "cygwin") else name
    return f"host/{name}/{executable}"


def _renderer_binary_name() -> str:
    """Return the platform-appropriate renderer binary name."""
    return (
        "plushie-renderer.exe"
        if sys.platform in ("win32", "cygwin")
        else "plushie-renderer"
    )


def _ensure_executable(path: Path) -> None:
    """Ensure a file has executable permission bits set."""
    if sys.platform in ("win32", "cygwin"):
        return
    mode = path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    path.chmod(mode)


def _remove_nested_renderer(root: Path) -> None:
    """Remove any nested renderer binary from a PyInstaller output tree."""
    for candidate in root.rglob(_renderer_binary_name()):
        if candidate.is_file():
            candidate.unlink()


def _toml_string(value: str) -> str:
    """Encode a string value as a TOML inline string."""
    return json.dumps(value)


def _toml_array(values: list[str]) -> str:
    """Encode a list of strings as a TOML inline array."""
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"
