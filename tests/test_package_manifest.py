"""Tests for standalone package manifest helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from plushie import __version__
from plushie.binary import PLUSHIE_RUST_VERSION
from plushie.package import (
    manifest_for_payload,
    normalize_package_target,
    render_manifest,
    write_manifest,
)


def test_normalize_package_target() -> None:
    assert normalize_package_target("Linux", "x86_64") == "linux-x86_64"
    assert normalize_package_target("Darwin", "arm64") == "darwin-aarch64"
    assert normalize_package_target("Windows", "AMD64") == "windows-x86_64"


def test_rejects_unknown_package_target_parts() -> None:
    with pytest.raises(ValueError, match="unsupported package OS"):
        normalize_package_target("plan9", "x86_64")

    with pytest.raises(ValueError, match="unsupported package architecture"):
        normalize_package_target("linux", "riscv64")


def test_manifest_for_payload_records_hash_and_size(tmp_path: Path) -> None:
    archive = tmp_path / "payload.tar.zst"
    archive.write_bytes(b"payload")

    manifest = manifest_for_payload(
        app_id="dev.plushie.test",
        app_name="Test App",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_kind="custom",
        renderer_source="local-build",
        renderer_path="bin/plushie-renderer",
        host_command=["host/app", "--flag"],
        platform_icon="assets/icon.png",
        working_dir=".",
        payload_archive=archive,
    )

    assert manifest["payload_size"] == 7
    assert len(manifest["payload_hash"]) == 64
    assert manifest["payload_archive"] == "payload.tar.zst"

    toml = render_manifest(manifest)
    assert 'host_sdk = "python"' in toml
    assert f'host_sdk_version = "{__version__}"' in toml
    assert f'plushie_rust_version = "{PLUSHIE_RUST_VERSION}"' in toml
    assert "protocol_version = 1" in toml
    assert 'renderer_path = "bin/plushie-renderer"' in toml
    assert 'host_command = ["host/app", "--flag"]' in toml
    assert 'kind = "custom"' in toml
    assert 'source = "local-build"' in toml
    assert 'icon = "assets/icon.png"' in toml


def test_write_manifest_creates_parent_directories(tmp_path: Path) -> None:
    archive = tmp_path / "payload.tar.zst"
    archive.write_bytes(b"payload")
    manifest = manifest_for_payload(
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_path="bin/plushie-renderer",
        host_command=["host/app"],
        payload_archive=archive,
    )

    output = tmp_path / "dist" / "package" / "plushie-package.toml"
    write_manifest(output, manifest)

    assert output.read_text() == render_manifest(manifest)
