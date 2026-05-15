"""Tests for standalone package manifest helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from plushie import __version__
from plushie.binary import PLUSHIE_RUST_VERSION
from plushie.package import (
    PackageStartConfig,
    _resolve_package_renderer,
    archive_payload,
    load_package_config,
    manifest_for_payload,
    normalize_package_target,
    package_pyinstaller_payload,
    render_manifest,
    render_package_config,
    write_manifest,
    write_package_config,
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
        start_command=["host/app", "--flag"],
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
    assert "[start]" in toml
    assert 'working_dir = "."' in toml
    assert 'command = ["host/app", "--flag"]' in toml
    assert (
        'forward_env = ["PATH", "HOME", "LANG", "LC_ALL", '
        '"XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DISPLAY"]'
    ) in toml
    assert '[renderer]\npath = "bin/plushie-renderer"' in toml
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
        start_command=["host/app"],
        payload_archive=archive,
    )

    output = tmp_path / "dist" / "package" / "plushie-package.toml"
    write_manifest(output, manifest)

    assert output.read_text() == render_manifest(manifest)


def test_manifest_for_payload_allows_empty_forward_env(tmp_path: Path) -> None:
    archive = tmp_path / "payload.tar.zst"
    archive.write_bytes(b"payload")

    manifest = manifest_for_payload(
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_path="bin/plushie-renderer",
        start_command=["host/app"],
        forward_env=[],
        payload_archive=archive,
    )

    assert manifest["forward_env"] == []
    assert "forward_env = []" in render_manifest(manifest)


def test_load_package_config_uses_default_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("plushie-package.config.toml").write_text(
        "\n".join(
            [
                "config_version = 1",
                "",
                "[start]",
                'working_dir = "host/DataExplorer"',
                'command = ["host/DataExplorer/DataExplorer", "--demo"]',
                'forward_env = ["PATH", "APP_MODE"]',
            ]
        )
    )

    config = load_package_config()

    assert config is not None
    assert config.working_dir == "host/DataExplorer"
    assert config.command == ["host/DataExplorer/DataExplorer", "--demo"]
    assert config.forward_env == ["PATH", "APP_MODE"]


def test_load_package_config_returns_none_when_default_file_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert load_package_config() is None


def test_write_package_config_uses_real_start_values(tmp_path: Path) -> None:
    path = tmp_path / "plushie-package.config.toml"

    write_package_config(
        path,
        PackageStartConfig(
            working_dir=".",
            command=["bin/connect"],
            forward_env=["PATH", "HOME"],
        ),
    )

    text = path.read_text()
    assert "config_version = 1" in text
    assert 'working_dir = "."' in text
    assert 'command = ["bin/connect"]' in text
    assert '"PATH"' in text


def test_render_package_config_defaults_to_connect_entrypoint() -> None:
    text = render_package_config()

    assert 'working_dir = "."' in text
    assert 'command = ["bin/connect"]' in text
    assert '"WAYLAND_DISPLAY"' in text


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("config_version = 2\n", "config_version must be 1"),
        (
            'config_version = 1\n[start]\nworking_dir = "/tmp/app"\n',
            "start.working_dir must be payload-relative",
        ),
        (
            'config_version = 1\n[start]\ncommand = ["../app"]\n',
            "start.command\\[0\\] must not contain parent traversal",
        ),
        (
            "config_version = 1\n[start]\ncommand = []\n",
            "start.command must not be empty",
        ),
        (
            'config_version = 1\n[start]\ncommand = ["host/app", ""]\n',
            "start.command\\[1\\] must be a non-empty string",
        ),
        (
            'config_version = 1\n[start]\nforward_env = ["PLUSHIE_BINARY_PATH"]\n',
            "start.forward_env\\[0\\] is reserved",
        ),
        (
            'config_version = 1\n[start]\nforward_env = ["PLUSHIE_PACKAGE_READY_FILE"]\n',
            "start.forward_env\\[0\\] is reserved",
        ),
        (
            'config_version = 1\n[start]\nforward_env = ["BAD=VALUE"]\n',
            "start.forward_env\\[0\\] must not contain comma or equals",
        ),
    ],
)
def test_load_package_config_validates_start_fields(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    config_path = tmp_path / "plushie-package.config.toml"
    config_path.write_text(content)

    with pytest.raises(ValueError, match=message):
        load_package_config(config_path)


def test_package_pyinstaller_payload_assembles_archive_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    prepared_renderer = tmp_path / "renderer" / "plushie-renderer"
    prepared_renderer.parent.mkdir()
    prepared_renderer.write_bytes(b"renderer")

    def fake_run_pyinstaller(**kwargs: Any) -> None:
        name = str(kwargs["name"])
        dist_dir = Path(kwargs["dist_dir"])
        app_dir = dist_dir / name
        app_dir.mkdir(parents=True)
        (app_dir / name).write_text("host")
        (app_dir / "plushie-renderer").write_text("nested renderer")
        assert kwargs["add_data"] == ["sample_data:sample_data"]
        assert kwargs["hidden_import"] == ["pandas"]
        assert kwargs["collect_submodules"] == ["plushie"]

    def fake_run_cargo_plushie(*args: str) -> None:
        out_dir = Path(args[args.index("--out") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "plushie-checkbox-512x512.png").write_bytes(b"icon")

    def fake_archive_payload(
        payload_root: str | Path, archive_path: str | Path
    ) -> None:
        root = Path(payload_root)
        assert (root / "bin" / "plushie-renderer").read_bytes() == b"renderer"
        assert (root / "host" / "DataExplorer" / "DataExplorer").read_text() == "host"
        assert not (root / "host" / "DataExplorer" / "plushie-renderer").exists()
        assert (
            root / "assets" / "plushie-checkbox-512x512.png"
        ).read_bytes() == b"icon"
        Path(archive_path).write_bytes(b"archive")

    monkeypatch.setattr(
        "plushie.package._prepare_renderer_for_pyinstaller",
        lambda _renderer_kind="stock": (prepared_renderer, "local-path"),
    )
    monkeypatch.setattr("plushie.package._run_pyinstaller", fake_run_pyinstaller)
    monkeypatch.setattr("plushie.package._run_cargo_plushie", fake_run_cargo_plushie)
    monkeypatch.setattr("plushie.package.archive_payload", fake_archive_payload)

    result = package_pyinstaller_payload(
        entry="src/data_explorer/__main__.py",
        name="DataExplorer",
        app_id="dev.plushie.test",
        app_name="Data Explorer",
        app_version="0.1.0",
        target="linux-x86_64",
        add_data=["sample_data:sample_data"],
        hidden_import=["pandas"],
        collect_submodules=["plushie"],
    )

    assert result["renderer_path"] == "bin/plushie-renderer"
    assert result["start_command"] == ["host/DataExplorer/DataExplorer"]
    assert result["platform_icon"] == "assets/plushie-checkbox-512x512.png"

    manifest = (tmp_path / "dist" / "package" / "plushie-package.toml").read_text()
    assert '[renderer]\npath = "bin/plushie-renderer"' in manifest
    assert 'command = ["host/DataExplorer/DataExplorer"]' in manifest
    assert 'source = "local-path"' in manifest
    assert 'icon = "assets/plushie-checkbox-512x512.png"' in manifest
    assert 'archive = "payload.tar.zst"' in manifest


def test_package_pyinstaller_payload_copies_app_icon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    prepared_renderer = tmp_path / "renderer" / "plushie-renderer"
    prepared_renderer.parent.mkdir()
    prepared_renderer.write_bytes(b"renderer")
    icon = tmp_path / "app.png"
    icon.write_bytes(b"app icon")

    def fake_run_pyinstaller(**kwargs: Any) -> None:
        name = str(kwargs["name"])
        app_dir = Path(kwargs["dist_dir"]) / name
        app_dir.mkdir(parents=True)
        (app_dir / name).write_text("host")
        assert kwargs["app_icon"] == icon

    def fake_archive_payload(
        payload_root: str | Path, archive_path: str | Path
    ) -> None:
        root = Path(payload_root)
        assert (root / "assets" / "app.png").read_bytes() == b"app icon"
        Path(archive_path).write_bytes(b"archive")

    monkeypatch.setattr(
        "plushie.package._prepare_renderer_for_pyinstaller",
        lambda _renderer_kind="stock": (prepared_renderer, "local-path"),
    )
    monkeypatch.setattr("plushie.package._run_pyinstaller", fake_run_pyinstaller)
    monkeypatch.setattr("plushie.package._run_cargo_plushie", lambda *_args: None)
    monkeypatch.setattr("plushie.package.archive_payload", fake_archive_payload)

    result = package_pyinstaller_payload(
        entry="app.py",
        name="IconApp",
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        app_icon=icon,
    )

    assert result["platform_icon"] == "assets/app.png"


def test_package_pyinstaller_payload_uses_start_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    prepared_renderer = tmp_path / "renderer" / "plushie-renderer"
    prepared_renderer.parent.mkdir()
    prepared_renderer.write_bytes(b"renderer")

    def fake_run_pyinstaller(**kwargs: Any) -> None:
        name = str(kwargs["name"])
        app_dir = Path(kwargs["dist_dir"]) / name
        app_dir.mkdir(parents=True)
        (app_dir / name).write_text("host")

    def fake_archive_payload(
        _payload_root: str | Path, archive_path: str | Path
    ) -> None:
        Path(archive_path).write_bytes(b"archive")

    monkeypatch.setattr(
        "plushie.package._prepare_renderer_for_pyinstaller",
        lambda _renderer_kind="stock": (prepared_renderer, "local-path"),
    )
    monkeypatch.setattr("plushie.package._run_pyinstaller", fake_run_pyinstaller)
    monkeypatch.setattr("plushie.package._run_cargo_plushie", lambda *_args: None)
    monkeypatch.setattr("plushie.package.archive_payload", fake_archive_payload)

    result = package_pyinstaller_payload(
        entry="app.py",
        name="ConfigApp",
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        working_dir="host/ConfigApp",
        start_command=["host/ConfigApp/ConfigApp", "--profile", "demo"],
        forward_env=["PATH", "APP_MODE"],
    )

    assert result["start_command"] == ["host/ConfigApp/ConfigApp", "--profile", "demo"]

    manifest = (tmp_path / "dist" / "package" / "plushie-package.toml").read_text()
    assert 'working_dir = "host/ConfigApp"' in manifest
    assert 'command = ["host/ConfigApp/ConfigApp", "--profile", "demo"]' in manifest
    assert 'forward_env = ["PATH", "APP_MODE"]' in manifest


def test_package_pyinstaller_payload_rejects_custom_without_custom_renderer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PLUSHIE_BINARY_PATH", raising=False)
    stale_custom = tmp_path / "build" / "demo" / "target" / "release"
    stale_custom.mkdir(parents=True)
    (stale_custom / "demo").write_text("not a package renderer")

    with pytest.raises(RuntimeError, match="custom renderer packaging requires"):
        package_pyinstaller_payload(
            entry="app.py",
            name="CustomApp",
            app_id="dev.plushie.test",
            app_version="0.1.0",
            target="linux-x86_64",
            renderer_kind="custom",
        )


def test_stock_package_renderer_syncs_managed_tool_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    synced_renderer = tmp_path / "bin" / "plushie-renderer"
    synced_renderer.parent.mkdir()
    synced_renderer.write_bytes(b"renderer")
    monkeypatch.delenv("PLUSHIE_BINARY_PATH", raising=False)
    monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)

    monkeypatch.setattr(
        "plushie.binary.sync_renderer_with_tool", lambda: str(synced_renderer)
    )

    renderer, source = _resolve_package_renderer("stock")

    assert renderer == synced_renderer.resolve()
    assert source == "download"


def test_archive_payload_rejects_symlinks(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "target").write_text("x")
    (payload / "link").symlink_to(payload / "target")

    with pytest.raises(RuntimeError, match="unsupported symlink"):
        archive_payload(payload, tmp_path / "payload.tar.zst")
