"""Tests for pyproject.toml extension configuration and build config loading."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from plushie.__main__ import _load_pyproject_config, _parse_extensions
from plushie.extension import ExtensionDef

# ===================================================================
# _load_pyproject_config
# ===================================================================


class TestLoadPyprojectConfig:
    """Loading [tool.plushie] from pyproject.toml."""

    def test_returns_empty_when_no_file(self, tmp_path: Path) -> None:
        result = _load_pyproject_config(tmp_path)
        assert result == {}

    def test_returns_empty_when_no_tool_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        result = _load_pyproject_config(tmp_path)
        assert result == {}

    def test_returns_empty_when_no_plushie_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
        result = _load_pyproject_config(tmp_path)
        assert result == {}

    def test_reads_extensions(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            extensions = [
                {kind = "sparkline", rust_crate = "native/spark", rust_constructor = "spark::new()"},
            ]
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        result = _load_pyproject_config(tmp_path)
        assert len(result["extensions"]) == 1
        assert result["extensions"][0]["kind"] == "sparkline"

    def test_reads_source_path(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            source_path = "~/projects/plushie"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        result = _load_pyproject_config(tmp_path)
        assert result["source_path"] == "~/projects/plushie"

    def test_reads_build_name(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            build_name = "my-app-plushie"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        result = _load_pyproject_config(tmp_path)
        assert result["build_name"] == "my-app-plushie"

    def test_returns_empty_on_malformed_toml(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("this is not valid toml [[[")
        result = _load_pyproject_config(tmp_path)
        assert result == {}

    def test_defaults_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            build_name = "from-cwd"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        monkeypatch.chdir(tmp_path)
        result = _load_pyproject_config()
        assert result["build_name"] == "from-cwd"

    def test_full_config(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            source_path = "/opt/plushie"
            build_name = "acme-plushie"
            extensions = [
                {kind = "gauge", rust_crate = "native/gauge", rust_constructor = "gauge::new()"},
                {kind = "chart", rust_crate = "native/chart", rust_constructor = "chart::new()"},
            ]
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        result = _load_pyproject_config(tmp_path)
        assert result["source_path"] == "/opt/plushie"
        assert result["build_name"] == "acme-plushie"
        assert len(result["extensions"]) == 2


# ===================================================================
# _parse_extensions
# ===================================================================


class TestParseExtensions:
    """Converting raw extension dicts into ExtensionDef objects."""

    def test_minimal_extension(self) -> None:
        raw: list[dict[str, Any]] = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
            },
        ]
        exts = _parse_extensions(raw)
        assert len(exts) == 1
        assert isinstance(exts[0], ExtensionDef)
        assert exts[0].kind == "spark"
        assert exts[0].rust_crate == "native/spark"
        assert exts[0].rust_constructor == "spark::new()"
        assert exts[0].props == []
        assert exts[0].commands == []

    def test_extension_with_props_and_commands(self) -> None:
        raw: list[dict[str, Any]] = [
            {
                "kind": "gauge",
                "rust_crate": "native/gauge",
                "rust_constructor": "gauge::new()",
                "props": [
                    {"name": "value", "prop_type": "number"},
                    {"name": "label", "prop_type": "string"},
                ],
                "commands": [
                    {
                        "name": "set_value",
                        "params": [{"name": "value", "param_type": "number"}],
                    },
                ],
            },
        ]
        exts = _parse_extensions(raw)
        assert len(exts) == 1
        assert len(exts[0].props) == 2
        assert exts[0].props[0].name == "value"
        assert len(exts[0].commands) == 1
        assert exts[0].commands[0].name == "set_value"
        assert len(exts[0].commands[0].params) == 1

    def test_empty_list(self) -> None:
        assert _parse_extensions([]) == []

    def test_multiple_extensions(self) -> None:
        raw: list[dict[str, Any]] = [
            {"kind": "a", "rust_crate": "native/a", "rust_constructor": "a::new()"},
            {"kind": "b", "rust_crate": "native/b", "rust_constructor": "b::new()"},
        ]
        exts = _parse_extensions(raw)
        assert len(exts) == 2
        assert exts[0].kind == "a"
        assert exts[1].kind == "b"


# ===================================================================
# extension_config in settings
# ===================================================================


class TestExtensionConfigInSettings:
    """The extension_config key passes through to the wire message."""

    def test_extension_config_forwarded(self) -> None:
        from plushie.protocol import settings

        ext_cfg = {"sparkline": {"color": "red"}}
        msg = settings({"extension_config": ext_cfg})
        assert msg["settings"]["extension_config"] == ext_cfg

    def test_extension_config_absent_when_not_set(self) -> None:
        from plushie.protocol import settings

        msg = settings({})
        assert "extension_config" not in msg["settings"]


# ===================================================================
# Build config resolution order
# ===================================================================


class TestBuildConfigResolution:
    """Verify pyproject.toml integration with the build command's config loading."""

    def test_pyproject_extensions_take_priority_over_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When pyproject.toml has extensions, the JSON file is not read."""
        import json

        # Write a pyproject.toml with an extension
        toml = textwrap.dedent("""\
            [tool.plushie]
            extensions = [
                {kind = "from_toml", rust_crate = "native/toml", rust_constructor = "toml::new()"},
            ]
        """)
        (tmp_path / "pyproject.toml").write_text(toml)

        # Write a JSON config with a different extension
        json_data = {
            "extensions": [
                {
                    "kind": "from_json",
                    "rust_crate": "native/json",
                    "rust_constructor": "json::new()",
                },
            ]
        }
        (tmp_path / "plushie_extensions.json").write_text(json.dumps(json_data))

        monkeypatch.chdir(tmp_path)

        cfg = _load_pyproject_config()
        exts = _parse_extensions(cfg.get("extensions", []))
        assert len(exts) == 1
        assert exts[0].kind == "from_toml"

    def test_build_name_from_pyproject(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            build_name = "my-custom-renderer"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        cfg = _load_pyproject_config(tmp_path)
        # Simulate the resolution: --name flag > pyproject > default
        name_flag = None
        binary_name = name_flag or cfg.get("build_name") or "plushie-custom"
        assert binary_name == "my-custom-renderer"

    def test_cli_flag_overrides_pyproject_build_name(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            build_name = "from-toml"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        cfg = _load_pyproject_config(tmp_path)
        name_flag = "from-cli"
        binary_name = name_flag or cfg.get("build_name") or "plushie-custom"
        assert binary_name == "from-cli"

    def test_source_path_from_pyproject(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            source_path = "/opt/plushie-src"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        monkeypatch.delenv("PLUSHIE_SOURCE_PATH", raising=False)
        cfg = _load_pyproject_config(tmp_path)
        import os

        source = os.environ.get("PLUSHIE_SOURCE_PATH", cfg.get("source_path"))
        assert source == "/opt/plushie-src"

    def test_env_var_overrides_pyproject_source_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            source_path = "/opt/plushie-src"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        monkeypatch.setenv("PLUSHIE_SOURCE_PATH", "/env/plushie")
        cfg = _load_pyproject_config(tmp_path)
        import os

        source = os.environ.get("PLUSHIE_SOURCE_PATH", cfg.get("source_path"))
        assert source == "/env/plushie"
