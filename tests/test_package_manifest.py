"""Tests for standalone package manifest helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from plushie import __version__
from plushie.binary import PLUSHIE_RUST_VERSION, launcher_name, tool_name
from plushie.package import (
    PackageStartConfig,
    _payload_host_executable_path,
    _payload_renderer_path,
    _resolve_package_renderer,
    normalize_package_target,
    package_pyinstaller_payload,
    render_package_config,
    write_package_config,
    write_partial_manifest,
)

# ---- platform config helpers ----


def test_normalize_package_target() -> None:
    assert normalize_package_target("Linux", "x86_64") == "linux-x86_64"
    assert normalize_package_target("Darwin", "arm64") == "darwin-aarch64"
    assert normalize_package_target("Windows", "AMD64") == "windows-x86_64"


def test_rejects_unknown_package_target_parts() -> None:
    with pytest.raises(ValueError, match="unsupported package OS"):
        normalize_package_target("plan9", "x86_64")

    with pytest.raises(ValueError, match="unsupported package architecture"):
        normalize_package_target("linux", "riscv64")


# ---- partial manifest ----


def test_write_partial_manifest_contains_required_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "plushie-package.toml"

    write_partial_manifest(
        manifest_path,
        app_id="dev.plushie.test",
        app_name="Test App",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_kind="custom",
        renderer_path="bin/plushie-renderer",
        start_command=["host/app", "--flag"],
    )

    toml = manifest_path.read_text()
    assert 'host_sdk = "python"' in toml
    assert f'host_sdk_version = "{__version__}"' in toml
    assert f'plushie_rust_version = "{PLUSHIE_RUST_VERSION}"' in toml
    assert "protocol_version = 1" in toml
    assert "[start]" in toml
    assert 'command = ["host/app", "--flag"]' in toml
    assert '[renderer]\npath = "bin/plushie-renderer"' in toml
    assert 'kind = "custom"' in toml
    assert 'app_name = "Test App"' in toml


def test_write_partial_manifest_omits_app_name_when_none(tmp_path: Path) -> None:
    manifest_path = tmp_path / "plushie-package.toml"

    write_partial_manifest(
        manifest_path,
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_path="bin/plushie-renderer",
        start_command=["host/app"],
    )

    toml = manifest_path.read_text()
    assert "app_name" not in toml


def test_write_partial_manifest_no_payload_section(tmp_path: Path) -> None:
    manifest_path = tmp_path / "plushie-package.toml"

    write_partial_manifest(
        manifest_path,
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_path="bin/plushie-renderer",
        start_command=["host/app"],
    )

    toml = manifest_path.read_text()
    assert "[payload]" not in toml
    assert "forward_env" not in toml
    assert "working_dir" not in toml
    assert "[platform]" not in toml


def test_write_partial_manifest_creates_parent_directories(tmp_path: Path) -> None:
    manifest_path = tmp_path / "dist" / "package" / "plushie-package.toml"

    write_partial_manifest(
        manifest_path,
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_path="bin/plushie-renderer",
        start_command=["host/app"],
    )

    assert manifest_path.exists()


# ---- package config template ----


def test_write_package_config_uses_real_start_values(tmp_path: Path) -> None:
    path = tmp_path / "plushie-package.config.toml"

    write_package_config(
        path,
        PackageStartConfig(
            working_dir=".",
            command=["host/MyApp/MyApp"],
        ),
    )

    text = path.read_text()
    assert "config_version = 1" in text
    assert 'working_dir = "."' in text
    assert 'command = ["host/MyApp/MyApp"]' in text


def test_render_package_config_defaults_to_pyinstaller_host_placeholder() -> None:
    text = render_package_config()

    assert 'working_dir = "."' in text
    # PyInstaller bakes the entry into a host executable; there is no
    # wrapper script. The placeholder points at the host path the user
    # is expected to edit.
    assert 'command = ["host/<app>/<app>"]' in text


def test_render_package_config_includes_platform_template() -> None:
    text = render_package_config()
    assert "# [platform]" in text
    assert "# publisher" in text
    assert "# [platform.macos]" in text
    assert "# [platform.windows]" in text
    assert "install_scope" in text


def test_render_package_config_includes_assets_template() -> None:
    text = render_package_config()
    assert "# [assets]" in text
    assert '# dir = "package_assets"' in text
    # The assets block sits between [start] and the platform block.
    start_idx = text.index("[start]")
    assets_idx = text.index("# [assets]")
    platform_idx = text.index("# [platform]")
    assert start_idx < assets_idx < platform_idx


# ---- payload paths (target-driven, not host-driven) ----


def test_payload_host_executable_uses_target_for_windows_suffix() -> None:
    # Cross-compile from any host to windows-x86_64 must produce a
    # `.exe`-suffixed manifest path.
    assert (
        _payload_host_executable_path("MyApp", "windows-x86_64")
        == "host/MyApp/MyApp.exe"
    )
    assert _payload_host_executable_path("MyApp", "linux-x86_64") == "host/MyApp/MyApp"
    assert (
        _payload_host_executable_path("MyApp", "darwin-aarch64") == "host/MyApp/MyApp"
    )


def test_payload_renderer_uses_target_for_windows_suffix() -> None:
    assert _payload_renderer_path("windows-x86_64") == "bin/plushie-renderer.exe"
    assert _payload_renderer_path("linux-x86_64") == "bin/plushie-renderer"


# ---- renderer resolution ----


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

    renderer = _resolve_package_renderer("stock")

    assert renderer == synced_renderer.resolve()


def test_source_package_renderer_syncs_managed_tool_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    synced_renderer = tmp_path / "bin" / "plushie-renderer"
    synced_renderer.parent.mkdir()
    synced_renderer.write_bytes(b"renderer")
    monkeypatch.delenv("PLUSHIE_BINARY_PATH", raising=False)
    monkeypatch.setenv("PLUSHIE_RUST_SOURCE_PATH", str(tmp_path / "plushie-rust"))

    monkeypatch.setattr(
        "plushie.binary.sync_renderer_with_tool", lambda: str(synced_renderer)
    )

    renderer = _resolve_package_renderer("stock")

    assert renderer == synced_renderer.resolve()


def test_explicit_package_renderer_requires_managed_packaging_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    renderer = tmp_path / "custom-renderer"
    renderer.write_bytes(b"renderer")
    monkeypatch.setenv("PLUSHIE_BINARY_PATH", str(renderer))

    with pytest.raises(RuntimeError, match="managed Plushie tool set"):
        _resolve_package_renderer("stock")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / tool_name()).write_bytes(b"tool")
    (bin_dir / launcher_name()).write_bytes(b"launcher")

    resolved = _resolve_package_renderer("stock")

    assert resolved == renderer.resolve()


# ---- PyInstaller payload ----


def test_package_pyinstaller_payload_assembles_payload_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    prepared_renderer = tmp_path / "renderer" / "plushie-renderer"
    prepared_renderer.parent.mkdir()
    prepared_renderer.write_bytes(b"renderer")

    assemble_calls: list[dict[str, Any]] = []

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

    def fake_assemble_package(
        manifest_path: Any, payload_dir: Any, *, package_config: Any = None
    ) -> None:
        assemble_calls.append(
            {"manifest_path": Path(manifest_path), "payload_dir": Path(payload_dir)}
        )

    monkeypatch.setattr(
        "plushie.package._prepare_renderer_for_pyinstaller",
        lambda _renderer_kind="stock": prepared_renderer,
    )
    monkeypatch.setattr("plushie.package._run_pyinstaller", fake_run_pyinstaller)
    monkeypatch.setattr("plushie.package.assemble_package", fake_assemble_package)

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

    payload_root = result["payload_root"]
    assert isinstance(payload_root, Path)
    assert (payload_root / "bin" / "plushie-renderer").read_bytes() == b"renderer"
    assert (
        payload_root / "host" / "DataExplorer" / "DataExplorer"
    ).read_text() == "host"
    assert not (payload_root / "host" / "DataExplorer" / "plushie-renderer").exists()

    partial = (tmp_path / "dist" / "plushie-package.toml").read_text()
    assert '[renderer]\npath = "bin/plushie-renderer"' in partial
    assert 'command = ["host/DataExplorer/DataExplorer"]' in partial
    assert "[payload]" not in partial

    assert len(assemble_calls) == 1
    assert Path(assemble_calls[0]["manifest_path"]).resolve() == (
        tmp_path / "dist" / "plushie-package.toml"
    )
    assert assemble_calls[0]["payload_dir"].resolve() == payload_root.resolve()


def test_package_pyinstaller_payload_uses_explicit_renderer_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    explicit_renderer = tmp_path / "custom-renderer"
    explicit_renderer.write_bytes(b"explicit renderer")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / tool_name()).write_bytes(b"tool")
    (bin_dir / launcher_name()).write_bytes(b"launcher")

    def fake_run_pyinstaller(**kwargs: Any) -> None:
        name = str(kwargs["name"])
        app_dir = Path(kwargs["dist_dir"]) / name
        app_dir.mkdir(parents=True)
        (app_dir / name).write_text("host")
        assert Path(kwargs["prepared_renderer"]).read_bytes() == b"explicit renderer"

    def fake_assemble_package(*_args: Any, **_kwargs: Any) -> None:
        pass

    def fail_prepare_renderer(*_args: Any, **_kwargs: Any) -> tuple[Path, str]:
        raise AssertionError("stock renderer resolution should not run")

    monkeypatch.setattr(
        "plushie.package._resolve_package_renderer",
        fail_prepare_renderer,
    )
    monkeypatch.setattr("plushie.package._run_pyinstaller", fake_run_pyinstaller)
    monkeypatch.setattr("plushie.package.assemble_package", fake_assemble_package)

    result = package_pyinstaller_payload(
        entry="app.py",
        name="ExplicitRendererApp",
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        renderer_path=explicit_renderer,
    )

    assert result["renderer_path"] == "bin/plushie-renderer"


def test_package_pyinstaller_payload_uses_start_command(
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

    def fake_assemble_package(*_args: Any, **_kwargs: Any) -> None:
        pass

    monkeypatch.setattr(
        "plushie.package._prepare_renderer_for_pyinstaller",
        lambda _renderer_kind="stock": prepared_renderer,
    )
    monkeypatch.setattr("plushie.package._run_pyinstaller", fake_run_pyinstaller)
    monkeypatch.setattr("plushie.package.assemble_package", fake_assemble_package)

    result = package_pyinstaller_payload(
        entry="app.py",
        name="ConfigApp",
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        start_command=["host/ConfigApp/ConfigApp", "--profile", "demo"],
    )

    assert result["start_command"] == ["host/ConfigApp/ConfigApp", "--profile", "demo"]

    partial = (tmp_path / "dist" / "plushie-package.toml").read_text()
    assert 'command = ["host/ConfigApp/ConfigApp", "--profile", "demo"]' in partial


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


def test_package_pyinstaller_payload_forwards_package_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    prepared_renderer = tmp_path / "renderer" / "plushie-renderer"
    prepared_renderer.parent.mkdir()
    prepared_renderer.write_bytes(b"renderer")

    assemble_calls: list[dict[str, Any]] = []

    def fake_run_pyinstaller(**kwargs: Any) -> None:
        name = str(kwargs["name"])
        app_dir = Path(kwargs["dist_dir"]) / name
        app_dir.mkdir(parents=True)
        (app_dir / name).write_text("host")

    def fake_assemble_package(
        manifest_path: Any, payload_dir: Any, *, package_config: Any = None
    ) -> None:
        assemble_calls.append({"package_config": package_config})

    monkeypatch.setattr(
        "plushie.package._prepare_renderer_for_pyinstaller",
        lambda _renderer_kind="stock": prepared_renderer,
    )
    monkeypatch.setattr("plushie.package._run_pyinstaller", fake_run_pyinstaller)
    monkeypatch.setattr("plushie.package.assemble_package", fake_assemble_package)

    config_path = tmp_path / "plushie-package.config.toml"
    config_path.write_text('config_version = 1\n[start]\nworking_dir = "."\n')

    package_pyinstaller_payload(
        entry="app.py",
        name="CfgApp",
        app_id="dev.plushie.test",
        app_version="0.1.0",
        target="linux-x86_64",
        package_config=config_path,
    )

    assert assemble_calls[0]["package_config"] == config_path
