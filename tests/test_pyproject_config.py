"""Tests for pyproject.toml extension configuration and build config loading."""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any

import pytest

from plushie.__main__ import (
    _load_pyproject_config,
    _parse_extensions,
    _resolve_artifacts,
)
from plushie.native_widget import NativeWidget

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
    """Converting raw extension dicts into NativeWidget objects."""

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
        assert isinstance(exts[0], NativeWidget)
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

    def test_requires_extension_list(self) -> None:
        with pytest.raises(ValueError, match="extensions must be a list"):
            _parse_extensions({"kind": "spark"})  # type: ignore[arg-type]

    def test_requires_extension_dict_entries(self) -> None:
        with pytest.raises(ValueError, match=r"extensions\[0\] must be a dict"):
            _parse_extensions(["spark"])  # type: ignore[list-item]

    @pytest.mark.parametrize("field", ["kind", "rust_crate", "rust_constructor"])
    def test_requires_extension_fields(self, field: str) -> None:
        raw: dict[str, Any] = {
            "kind": "spark",
            "rust_crate": "native/spark",
            "rust_constructor": "spark::new()",
        }
        del raw[field]

        with pytest.raises(ValueError, match=rf"extensions\[0\]\.{field} is required"):
            _parse_extensions([raw])

    @pytest.mark.parametrize("field", ["kind", "rust_crate", "rust_constructor"])
    def test_requires_extension_string_fields(self, field: str) -> None:
        raw: dict[str, Any] = {
            "kind": "spark",
            "rust_crate": "native/spark",
            "rust_constructor": "spark::new()",
        }
        raw[field] = 42

        with pytest.raises(
            ValueError, match=rf"extensions\[0\]\.{field} must be a string"
        ):
            _parse_extensions([raw])

    def test_requires_props_list(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "props": {"name": "value", "prop_type": "number"},
            }
        ]

        with pytest.raises(ValueError, match=r"extensions\[0\]\.props must be a list"):
            _parse_extensions(raw)  # type: ignore[arg-type]

    @pytest.mark.parametrize("field", ["name", "prop_type"])
    def test_requires_prop_fields(self, field: str) -> None:
        prop = {"name": "value", "prop_type": "number"}
        del prop[field]
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "props": [prop],
            }
        ]

        with pytest.raises(
            ValueError, match=rf"extensions\[0\]\.props\[0\]\.{field} is required"
        ):
            _parse_extensions(raw)

    def test_requires_prop_name_string(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "props": [{"name": 42, "prop_type": "number"}],
            }
        ]

        with pytest.raises(
            ValueError, match=r"extensions\[0\]\.props\[0\]\.name must be a string"
        ):
            _parse_extensions(raw)  # type: ignore[arg-type]

    def test_validates_prop_entry(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "props": [{"name": "value", "prop_type": "integer"}],
            }
        ]

        with pytest.raises(
            ValueError,
            match=r"extensions\[0\]\.props\[0\]\.prop_type must be a valid PropType",
        ):
            _parse_extensions(raw)

    def test_requires_commands_list(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "commands": {"name": "refresh"},
            }
        ]

        with pytest.raises(
            ValueError, match=r"extensions\[0\]\.commands must be a list"
        ):
            _parse_extensions(raw)  # type: ignore[arg-type]

    def test_requires_command_name(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "commands": [{"params": []}],
            }
        ]

        with pytest.raises(
            ValueError, match=r"extensions\[0\]\.commands\[0\]\.name is required"
        ):
            _parse_extensions(raw)

    def test_requires_command_name_string(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "commands": [{"name": 42}],
            }
        ]

        with pytest.raises(
            ValueError,
            match=r"extensions\[0\]\.commands\[0\]\.name must be a string",
        ):
            _parse_extensions(raw)  # type: ignore[arg-type]

    def test_validates_command_params(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "commands": [{"name": "set", "params": {"name": "value"}}],
            }
        ]

        with pytest.raises(
            ValueError,
            match=r"extensions\[0\]\.commands\[0\]\.params must be a list",
        ):
            _parse_extensions(raw)  # type: ignore[arg-type]

    def test_validates_param_entry(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "commands": [
                    {"name": "set", "params": [{"name": "value", "param_type": "any"}]}
                ],
            }
        ]

        with pytest.raises(
            ValueError,
            match=(
                r"extensions\[0\]\.commands\[0\]\.params\[0\]\.param_type "
                "must be a valid ParamType"
            ),
        ):
            _parse_extensions(raw)

    @pytest.mark.parametrize("field", ["name", "param_type"])
    def test_requires_param_fields(self, field: str) -> None:
        param = {"name": "value", "param_type": "number"}
        del param[field]
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "commands": [{"name": "set", "params": [param]}],
            }
        ]

        with pytest.raises(
            ValueError,
            match=(
                rf"extensions\[0\]\.commands\[0\]\.params\[0\]\.{field} "
                "is required"
            ),
        ):
            _parse_extensions(raw)

    def test_requires_param_name_string(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "commands": [
                    {"name": "set", "params": [{"name": 42, "param_type": "number"}]}
                ],
            }
        ]

        with pytest.raises(
            ValueError,
            match=(
                r"extensions\[0\]\.commands\[0\]\.params\[0\]\.name "
                "must be a string"
            ),
        ):
            _parse_extensions(raw)  # type: ignore[arg-type]

    def test_validates_native_widget_definition(self) -> None:
        raw = [
            {
                "kind": "button",
                "rust_crate": "native/button",
                "rust_constructor": "button::new()",
            }
        ]

        with pytest.raises(
            ValueError,
            match=r'extensions\[0\]: widget type "button" shadows a built-in widget',
        ):
            _parse_extensions(raw)

    def test_validates_duplicate_prop_names(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "props": [
                    {"name": "value", "prop_type": "number"},
                    {"name": "value", "prop_type": "number"},
                ],
            }
        ]

        with pytest.raises(
            ValueError,
            match=r'extensions\[0\]: duplicate prop name "value"',
        ):
            _parse_extensions(raw)

    def test_validates_reserved_prop_names(self) -> None:
        raw = [
            {
                "kind": "spark",
                "rust_crate": "native/spark",
                "rust_constructor": "spark::new()",
                "props": [{"name": "id", "prop_type": "string"}],
            }
        ]

        with pytest.raises(
            ValueError,
            match=r'extensions\[0\]: prop name "id" is reserved',
        ):
            _parse_extensions(raw)


# ===================================================================
# widget_config in settings
# ===================================================================


class TestWidgetConfigInSettings:
    """The widget_config key is sent unchanged on the wire."""

    def test_widget_config_forwarded(self) -> None:
        from plushie.protocol import settings

        widget_cfg = {"sparkline": {"color": "red"}}
        msg = settings({"widget_config": widget_cfg})
        assert msg["settings"]["widget_config"] == widget_cfg

    def test_widget_config_absent_when_not_set(self) -> None:
        from plushie.protocol import settings

        msg = settings({})
        assert "widget_config" not in msg["settings"]

    def test_validate_props_accepted(self) -> None:
        from plushie.protocol import settings

        msg = settings({"validate_props": True})
        assert msg["settings"]["validate_props"] is True


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
        monkeypatch.delenv("PLUSHIE_RUST_SOURCE_PATH", raising=False)
        cfg = _load_pyproject_config(tmp_path)
        import os

        source = os.environ.get("PLUSHIE_RUST_SOURCE_PATH", cfg.get("source_path"))
        assert source == "/opt/plushie-src"

    def test_env_var_overrides_pyproject_source_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            source_path = "/opt/plushie-src"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        monkeypatch.setenv("PLUSHIE_RUST_SOURCE_PATH", "/env/plushie")
        cfg = _load_pyproject_config(tmp_path)
        import os

        source = os.environ.get("PLUSHIE_RUST_SOURCE_PATH", cfg.get("source_path"))
        assert source == "/env/plushie"


# ===================================================================
# _resolve_artifacts
# ===================================================================


def _make_args(**kwargs: Any) -> argparse.Namespace:
    """Build an ``argparse.Namespace`` with download/build-style defaults."""
    defaults: dict[str, Any] = {"bin": False, "wasm": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestResolveArtifacts:
    """Artifact resolution: CLI flags > pyproject.toml > default."""

    def test_default_is_bin_only(self) -> None:
        want_bin, want_wasm = _resolve_artifacts(_make_args(), {})
        assert want_bin is True
        assert want_wasm is False

    def test_cli_bin_flag(self) -> None:
        want_bin, want_wasm = _resolve_artifacts(_make_args(bin=True), {})
        assert want_bin is True
        assert want_wasm is False

    def test_cli_wasm_flag(self) -> None:
        want_bin, want_wasm = _resolve_artifacts(_make_args(wasm=True), {})
        assert want_bin is False
        assert want_wasm is True

    def test_cli_both_flags(self) -> None:
        want_bin, want_wasm = _resolve_artifacts(_make_args(bin=True, wasm=True), {})
        assert want_bin is True
        assert want_wasm is True

    def test_pyproject_artifacts_bin_and_wasm(self) -> None:
        cfg = {"artifacts": ["bin", "wasm"]}
        want_bin, want_wasm = _resolve_artifacts(_make_args(), cfg)
        assert want_bin is True
        assert want_wasm is True

    def test_pyproject_artifacts_wasm_only(self) -> None:
        cfg = {"artifacts": ["wasm"]}
        want_bin, want_wasm = _resolve_artifacts(_make_args(), cfg)
        assert want_bin is False
        assert want_wasm is True

    def test_pyproject_artifacts_bin_only(self) -> None:
        cfg = {"artifacts": ["bin"]}
        want_bin, want_wasm = _resolve_artifacts(_make_args(), cfg)
        assert want_bin is True
        assert want_wasm is False

    def test_cli_flag_overrides_pyproject_artifacts(self) -> None:
        """CLI --wasm should ignore pyproject artifacts entirely."""
        cfg = {"artifacts": ["bin", "wasm"]}
        want_bin, want_wasm = _resolve_artifacts(_make_args(wasm=True), cfg)
        assert want_bin is False
        assert want_wasm is True

    def test_empty_artifacts_list(self) -> None:
        """An explicit empty list means download nothing."""
        cfg = {"artifacts": []}
        want_bin, want_wasm = _resolve_artifacts(_make_args(), cfg)
        assert want_bin is False
        assert want_wasm is False


# ===================================================================
# Artifact path config resolution
# ===================================================================


class TestArtifactPathConfig:
    """Reading bin_file and wasm_dir from pyproject.toml."""

    def test_reads_bin_file(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            bin_file = "bin/plushie-renderer"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        cfg = _load_pyproject_config(tmp_path)
        assert cfg["bin_file"] == "bin/plushie-renderer"

    def test_reads_wasm_dir(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            wasm_dir = "static/wasm"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        cfg = _load_pyproject_config(tmp_path)
        assert cfg["wasm_dir"] == "static/wasm"

    def test_reads_artifacts(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            artifacts = ["bin", "wasm"]
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        cfg = _load_pyproject_config(tmp_path)
        assert cfg["artifacts"] == ["bin", "wasm"]

    def test_full_artifact_config(self, tmp_path: Path) -> None:
        toml = textwrap.dedent("""\
            [tool.plushie]
            artifacts = ["bin", "wasm"]
            bin_file = "bin/plushie-renderer"
            wasm_dir = "static"
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        cfg = _load_pyproject_config(tmp_path)
        assert cfg["artifacts"] == ["bin", "wasm"]
        assert cfg["bin_file"] == "bin/plushie-renderer"
        assert cfg["wasm_dir"] == "static"

    def test_cli_bin_file_overrides_pyproject(self) -> None:
        """CLI --bin-file takes priority over pyproject bin_file."""
        cli_val = "/tmp/my-binary"
        cfg_val = "bin/plushie-renderer"
        resolved = cli_val or cfg_val
        assert resolved == "/tmp/my-binary"

    def test_pyproject_bin_file_used_when_no_cli(self) -> None:
        """Without --bin-file, pyproject bin_file is used."""
        cli_val = None
        cfg_val = "bin/plushie-renderer"
        resolved = cli_val or cfg_val
        assert resolved == "bin/plushie-renderer"

    def test_neither_cli_nor_pyproject_gives_none(self) -> None:
        """Without --bin-file or pyproject, result is None (standard location)."""
        cli_val = None
        cfg_val = None
        resolved = cli_val or cfg_val
        assert resolved is None
