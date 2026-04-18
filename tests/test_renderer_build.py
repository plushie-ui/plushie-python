"""Tests for :mod:`plushie.renderer_build`.

Covers widget-metadata injection, spec Cargo.toml generation, and the
end-to-end orchestrator (with cargo-plushie invocation mocked).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from plushie.native_widget import CommandDef, NativeWidget, ParamDef, PropDef
from plushie.renderer_build import (
    WIDGET_META_HEADER,
    build,
    write_spec_cargo_toml,
    write_widget_metadata,
)


def _gauge_widget(tmp_path: Path) -> NativeWidget:
    """A ``NativeWidget`` whose Cargo.toml lives under ``tmp_path``."""
    crate = tmp_path / "native" / "my_gauge"
    crate.mkdir(parents=True, exist_ok=True)
    return NativeWidget(
        kind="my_gauge",
        rust_crate=str(crate),
        rust_constructor="my_gauge::factory::new()",
        props=[PropDef("value", "number")],
        commands=[CommandDef("set_value", [ParamDef("value", "number")])],
    )


# ---------------------------------------------------------------------------
# write_widget_metadata
# ---------------------------------------------------------------------------


class TestWriteWidgetMetadata:
    def test_injects_when_missing(self, tmp_path: Path) -> None:
        widget = _gauge_widget(tmp_path)
        cargo = Path(widget.rust_crate) / "Cargo.toml"
        cargo.write_text('[package]\nname = "my_gauge"\nversion = "0.1.0"\n')

        write_widget_metadata(widget)

        content = cargo.read_text()
        assert WIDGET_META_HEADER in content
        assert 'type_name = "my_gauge"' in content
        assert 'constructor = "my_gauge::factory::new()"' in content

    def test_replaces_existing_block(self, tmp_path: Path) -> None:
        widget = _gauge_widget(tmp_path)
        cargo = Path(widget.rust_crate) / "Cargo.toml"
        cargo.write_text(
            '[package]\nname = "my_gauge"\n'
            "\n"
            f"{WIDGET_META_HEADER}\n"
            'type_name = "old"\n'
            'constructor = "stale"\n'
        )

        write_widget_metadata(widget)

        content = cargo.read_text()
        assert 'type_name = "my_gauge"' in content
        assert 'type_name = "old"' not in content
        assert 'constructor = "stale"' not in content
        # Only one metadata block remains.
        assert content.count(WIDGET_META_HEADER) == 1

    def test_raises_when_cargo_toml_missing(self, tmp_path: Path) -> None:
        widget = NativeWidget(
            kind="absent",
            rust_crate=str(tmp_path / "no-such-crate"),
            rust_constructor="absent::new()",
        )

        with pytest.raises(FileNotFoundError):
            write_widget_metadata(widget)


# ---------------------------------------------------------------------------
# write_spec_cargo_toml
# ---------------------------------------------------------------------------


class TestWriteSpecCargoToml:
    def test_writes_manifest_with_dependencies(self, tmp_path: Path) -> None:
        widget = _gauge_widget(tmp_path)
        spec_dir = tmp_path / "build" / "plushie-renderer-spec"

        manifest = write_spec_cargo_toml(
            [widget],
            binary_name="my-app-renderer",
            source_path=None,
            spec_dir=spec_dir,
        )

        assert manifest == spec_dir / "Cargo.toml"
        content = manifest.read_text()
        assert "[package]" in content
        assert 'name = "my_app_renderer-renderer-spec"' in content
        assert "[dependencies]" in content
        assert "my_gauge = { path =" in content
        assert "[package.metadata.plushie]" in content
        assert 'binary_name = "my-app-renderer"' in content
        # source_path absent -> no source_path metadata.
        assert "source_path" not in content

    def test_includes_source_path_when_provided(self, tmp_path: Path) -> None:
        widget = _gauge_widget(tmp_path)
        spec_dir = tmp_path / "spec"
        source = tmp_path / "plushie-rust"
        source.mkdir()

        manifest = write_spec_cargo_toml(
            [widget],
            binary_name="renderer",
            source_path=str(source),
            spec_dir=spec_dir,
        )

        content = manifest.read_text()
        assert f'source_path = "{source.resolve()}"' in content

    def test_creates_stub_lib_rs(self, tmp_path: Path) -> None:
        widget = _gauge_widget(tmp_path)
        spec_dir = tmp_path / "spec"

        write_spec_cargo_toml(
            [widget],
            binary_name="renderer",
            source_path=None,
            spec_dir=spec_dir,
        )

        assert (spec_dir / "src" / "lib.rs").is_file()

    def test_preserves_existing_lib_rs(self, tmp_path: Path) -> None:
        widget = _gauge_widget(tmp_path)
        spec_dir = tmp_path / "spec"
        (spec_dir / "src").mkdir(parents=True)
        (spec_dir / "src" / "lib.rs").write_text("// custom\n")

        write_spec_cargo_toml(
            [widget],
            binary_name="renderer",
            source_path=None,
            spec_dir=spec_dir,
        )

        assert (spec_dir / "src" / "lib.rs").read_text() == "// custom\n"


# ---------------------------------------------------------------------------
# build orchestrator
# ---------------------------------------------------------------------------


class TestBuild:
    def test_shell_out_and_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        widget = _gauge_widget(tmp_path)
        (Path(widget.rust_crate) / "Cargo.toml").write_text(
            '[package]\nname = "my_gauge"\nversion = "0.1.0"\n'
        )

        # Redirect SPEC_DIR to a tmp path and the download dir as well.
        spec_dir = tmp_path / "spec"
        download_dir = tmp_path / "dl"

        # cargo-plushie resolution: pretend PATH install with matching version.
        monkeypatch.setattr(
            "plushie.renderer_build.resolve_cargo_plushie",
            lambda: ("cargo-plushie", []),
        )

        monkeypatch.setattr("plushie.renderer_build.download_dir", lambda: download_dir)
        monkeypatch.setattr(
            "plushie.renderer_build.download_name",
            lambda: "plushie-renderer-test",
        )

        calls: list[list[str]] = []

        class _Completed:
            returncode = 0
            stdout = b""
            stderr = b""

        def _fake_run(args: list[str], **_kwargs: Any) -> _Completed:
            calls.append(args)
            # Simulate cargo plushie placing a binary at the expected
            # path: cargo-plushie's generated workspace nests its own
            # target/ under <spec_dir>/target/plushie-renderer/.
            binary = (
                spec_dir
                / "target"
                / "plushie-renderer"
                / "target"
                / "debug"
                / "my-app-renderer"
            )
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"\x7fELF fake binary")
            binary.chmod(0o755)
            return _Completed()

        monkeypatch.setattr("plushie.renderer_build.subprocess.run", _fake_run)
        monkeypatch.setattr("plushie.renderer_build.SPEC_DIR", spec_dir)

        exit_code = build(
            [widget],
            binary_name="my-app-renderer",
            source_path=None,
            release=False,
            verbose=False,
            bin_file=None,
            spec_dir=spec_dir,
        )

        assert exit_code == 0
        assert calls, "cargo plushie build should have been invoked"
        invocation = calls[0]
        assert invocation[0] == "cargo-plushie"
        assert invocation[1] == "build"
        assert "--manifest-path" in invocation
        assert (download_dir / "plushie-renderer-test").is_file()

    def test_propagates_cargo_plushie_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        widget = _gauge_widget(tmp_path)
        (Path(widget.rust_crate) / "Cargo.toml").write_text(
            '[package]\nname = "my_gauge"\nversion = "0.1.0"\n'
        )

        monkeypatch.setattr(
            "plushie.renderer_build.resolve_cargo_plushie",
            lambda: ("cargo-plushie", []),
        )

        class _Completed:
            returncode = 42
            stdout = b""
            stderr = b"boom\n"

        monkeypatch.setattr(
            "plushie.renderer_build.subprocess.run",
            lambda *_a, **_kw: _Completed(),
        )

        exit_code = build(
            [widget],
            binary_name="renderer",
            source_path=None,
            release=False,
            verbose=False,
            bin_file=None,
            spec_dir=tmp_path / "spec",
        )

        assert exit_code == 42

    def test_source_path_branch_composes_correctly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PLUSHIE_RUST_SOURCE_PATH branch: cargo run ... -- build ... ."""
        widget = _gauge_widget(tmp_path)
        (Path(widget.rust_crate) / "Cargo.toml").write_text(
            '[package]\nname = "my_gauge"\nversion = "0.1.0"\n'
        )
        spec_dir = tmp_path / "spec"

        monkeypatch.setattr(
            "plushie.renderer_build.resolve_cargo_plushie",
            lambda: (
                "cargo",
                [
                    "run",
                    "--manifest-path",
                    "/src/Cargo.toml",
                    "-p",
                    "cargo-plushie",
                    "--release",
                    "--quiet",
                    "--",
                ],
            ),
        )

        calls: list[list[str]] = []

        class _Completed:
            returncode = 0
            stdout = b""
            stderr = b""

        def _fake_run(args: list[str], **_kwargs: Any) -> _Completed:
            calls.append(args)
            binary = (
                spec_dir
                / "target"
                / "plushie-renderer"
                / "target"
                / "release"
                / "renderer"
            )
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"\x7fELF")
            return _Completed()

        monkeypatch.setattr("plushie.renderer_build.subprocess.run", _fake_run)
        monkeypatch.setattr(
            "plushie.renderer_build.download_dir", lambda: tmp_path / "dl"
        )
        monkeypatch.setattr(
            "plushie.renderer_build.download_name", lambda: "plushie-renderer-test"
        )

        build(
            [widget],
            binary_name="renderer",
            source_path=None,
            release=True,
            verbose=False,
            bin_file=None,
            spec_dir=spec_dir,
        )

        invocation = calls[0]
        assert invocation[0] == "cargo"
        assert invocation[1] == "run"
        # ``--`` must precede the cargo-plushie subcommand.
        dash_idx = invocation.index("--")
        assert invocation[dash_idx + 1] == "build"
        assert "--release" in invocation[dash_idx + 1 :]
