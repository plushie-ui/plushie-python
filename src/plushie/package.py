"""Standalone package manifest helpers."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path
from typing import Literal, TypedDict

from plushie import __version__
from plushie.binary import PLUSHIE_RUST_VERSION
from plushie.protocol import PROTOCOL_VERSION

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
    host_command: list[str]
    working_dir: str
    payload_archive: str
    payload_hash: str
    payload_size: int


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
            f"renderer_path = {_toml_string(manifest['renderer']['path'])}",
            f"host_command = {_toml_array(manifest['host_command'])}",
            f"working_dir = {_toml_string(manifest['working_dir'])}",
            "exec_env = []",
            "",
            "[renderer]",
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
    host_command: list[str],
    payload_archive: str | Path,
    app_name: str | None = None,
    target: str | None = None,
    renderer_kind: RendererKind = "stock",
    renderer_source: str = "local-resolve",
    platform_icon: str | None = None,
    working_dir: str = ".",
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
        "host_command": host_command,
        "working_dir": working_dir,
        "payload_archive": os.fspath(archive_path.name),
        "payload_hash": sha256_file(archive_path),
        "payload_size": file_size(archive_path),
    }


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"
