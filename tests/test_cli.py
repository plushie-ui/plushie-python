"""Tests for the plushie command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

import pytest

import plushie
import plushie.__main__ as cli


class DummyApp:
    pass


def test_run_json_forwards_format_without_old_json_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(_app_class: object, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie, "run", fake_run)

    cli._cmd_run(
        argparse.Namespace(
            app="demo:App",
            mode="mock",
            json=True,
            watch=False,
            daemon=False,
        )
    )

    assert calls == [{"mode": "mock", "daemon": False, "format": "json"}]
    assert "json" not in calls[0]


def test_run_default_keeps_connection_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(_app_class: object, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie, "run", fake_run)

    cli._cmd_run(
        argparse.Namespace(
            app="demo:App",
            mode=None,
            json=False,
            watch=False,
            daemon=False,
        )
    )

    assert calls == [{"mode": None, "daemon": False}]


def test_connect_top_level_uses_socket_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import plushie.connection
    import plushie.runtime
    import plushie.transport

    adapter_calls: list[dict[str, Any]] = []
    connection_calls: list[dict[str, Any]] = []
    runtime_calls: list[dict[str, Any]] = []
    runtime_runs: list[bool] = []

    class FakeSocketAdapter:
        def __init__(self, address: str, **kwargs: Any) -> None:
            adapter_calls.append({"address": address, **kwargs})

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    class FakeRuntime:
        def __init__(self, app: object, conn: object, **kwargs: Any) -> None:
            runtime_calls.append({"app": app, "conn": conn, **kwargs})

        def run(self) -> None:
            runtime_runs.append(True)

    def fake_from_iostream(adapter: object, **kwargs: Any) -> FakeConnection:
        connection_calls.append({"adapter": adapter, **kwargs})
        return FakeConnection()

    monkeypatch.setenv("PLUSHIE_SOCKET", "/tmp/plushie.sock")
    monkeypatch.setenv("PLUSHIE_TOKEN", "listen-token")
    monkeypatch.setattr(plushie.transport, "SocketAdapter", FakeSocketAdapter)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "from_iostream",
        staticmethod(fake_from_iostream),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)

    plushie.connect(cast(Any, DummyApp), format="json", daemon=True)

    assert adapter_calls == [{"address": "/tmp/plushie.sock", "format": "json"}]
    assert len(connection_calls) == 1
    assert connection_calls[0]["adapter"].__class__ is FakeSocketAdapter
    assert connection_calls[0]["token"] == "listen-token"
    assert isinstance(runtime_calls[0]["app"], DummyApp)
    assert runtime_calls[0]["conn"].__class__ is FakeConnection
    assert runtime_calls[0]["daemon"] is True
    assert runtime_runs == [True]


def test_connect_top_level_spawns_renderer_without_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime

    open_calls: list[dict[str, Any]] = []
    runtime_calls: list[dict[str, Any]] = []
    runtime_runs: list[bool] = []

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    class FakeRuntime:
        def __init__(self, app: object, conn: object, **kwargs: Any) -> None:
            runtime_calls.append({"app": app, "conn": conn, **kwargs})

        def run(self) -> None:
            runtime_runs.append(True)

    monkeypatch.delenv("PLUSHIE_SOCKET", raising=False)
    monkeypatch.delenv("PLUSHIE_TOKEN", raising=False)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "open",
        staticmethod(lambda **kwargs: open_calls.append(kwargs) or FakeConnection()),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)

    plushie.connect(cast(Any, DummyApp))

    assert open_calls == [{"format": "msgpack"}]
    assert isinstance(runtime_calls[0]["app"], DummyApp)
    assert runtime_calls[0]["conn"].__class__ is FakeConnection
    assert runtime_calls[0]["daemon"] is False
    assert runtime_runs == [True]


def test_connect_json_opens_spawn_connection_with_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime

    open_calls: list[dict[str, Any]] = []
    runtime_calls: list[tuple[object, object]] = []
    runtime_runs: list[bool] = []

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    class FakeRuntime:
        def __init__(self, app: object, conn: object) -> None:
            runtime_calls.append((app, conn))

        def run(self) -> None:
            runtime_runs.append(True)

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "open",
        staticmethod(lambda **kwargs: open_calls.append(kwargs) or FakeConnection()),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)
    monkeypatch.delenv("PLUSHIE_SOCKET", raising=False)

    cli._cmd_connect(argparse.Namespace(app="demo:App", json=True))

    assert open_calls == [{"format": "json"}]
    assert isinstance(runtime_calls[0][0], DummyApp)
    assert runtime_calls[0][1].__class__ is FakeConnection
    assert runtime_runs == [True]


def test_connect_default_opens_spawn_connection_with_msgpack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime

    open_calls: list[dict[str, Any]] = []

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    class FakeRuntime:
        def __init__(self, _app: object, _conn: object) -> None:
            pass

        def run(self) -> None:
            pass

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "open",
        staticmethod(lambda **kwargs: open_calls.append(kwargs) or FakeConnection()),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)
    monkeypatch.delenv("PLUSHIE_SOCKET", raising=False)

    cli._cmd_connect(argparse.Namespace(app="demo:App", json=False))

    assert open_calls == [{"format": "msgpack"}]


def test_connect_socket_constructs_iostream_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime
    import plushie.transport

    adapter_calls: list[dict[str, Any]] = []
    connection_calls: list[dict[str, Any]] = []
    runtime_calls: list[tuple[object, object]] = []
    runtime_runs: list[bool] = []

    class FakeSocketAdapter:
        def __init__(self, address: str, **kwargs: Any) -> None:
            adapter_calls.append({"address": address, **kwargs})

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    class FakeRuntime:
        def __init__(self, app: object, conn: object) -> None:
            runtime_calls.append((app, conn))

        def run(self) -> None:
            runtime_runs.append(True)

    def fake_from_iostream(adapter: object, **kwargs: Any) -> FakeConnection:
        connection_calls.append({"adapter": adapter, **kwargs})
        return FakeConnection()

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie.transport, "SocketAdapter", FakeSocketAdapter)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "from_iostream",
        staticmethod(fake_from_iostream),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)

    cli._cmd_connect(
        argparse.Namespace(
            app="demo:App",
            json=True,
            socket="/tmp/plushie.sock",
            token="listen-token",
        )
    )

    assert adapter_calls == [{"address": "/tmp/plushie.sock", "format": "json"}]
    assert len(connection_calls) == 1
    assert connection_calls[0]["adapter"].__class__ is FakeSocketAdapter
    assert connection_calls[0]["token"] == "listen-token"
    assert isinstance(runtime_calls[0][0], DummyApp)
    assert runtime_calls[0][1].__class__ is FakeConnection
    assert runtime_runs == [True]


def test_connect_parser_accepts_json_flag() -> None:
    args = cli._build_parser().parse_args(["connect", "--json", "demo:App"])

    assert args.command == "connect"
    assert args.json is True


def test_connect_parser_accepts_socket_and_token() -> None:
    args = cli._build_parser().parse_args(
        ["connect", "--socket", "/tmp/plushie.sock", "--token", "abc", "demo:App"]
    )

    assert args.command == "connect"
    assert args.socket == "/tmp/plushie.sock"
    assert args.token == "abc"


def test_package_parser_accepts_prepared_payload_shape() -> None:
    args = cli._build_parser().parse_args(
        [
            "package",
            "--app-id",
            "dev.plushie.test",
            "--renderer-path",
            "bin/plushie-renderer",
            "--payload-dir",
            "dist/package/payload",
            "--start-command",
            "host/app",
        ]
    )

    assert args.command == "package"
    assert args.renderer_path == "bin/plushie-renderer"
    assert args.payload_dir == "dist/package/payload"
    assert args.start_command == ["host/app"]


def test_package_parser_accepts_package_config() -> None:
    args = cli._build_parser().parse_args(
        [
            "package",
            "--app-id",
            "dev.plushie.test",
            "--package-config",
            "plushie-package.config.toml",
            "--pyinstaller-entry",
            "src/test_app/__main__.py",
            "--pyinstaller-name",
            "TestApp",
        ]
    )

    assert args.command == "package"
    assert args.package_config == "plushie-package.config.toml"


def test_package_parser_accepts_write_package_config_without_app_id() -> None:
    args = cli._build_parser().parse_args(["package", "--write-package-config"])

    assert args.command == "package"
    assert args.write_package_config is True


def test_package_write_config_uses_pyinstaller_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    cli._cmd_package(
        argparse.Namespace(
            write_package_config=True,
            package_config=None,
            pyinstaller_name="ConfigApp",
            app_name=None,
        )
    )

    text = (tmp_path / "plushie-package.config.toml").read_text(encoding="utf-8")
    assert 'command = ["host/ConfigApp/ConfigApp"]' in text


def test_package_parser_accepts_pyinstaller_shape() -> None:
    args = cli._build_parser().parse_args(
        [
            "package",
            "--app-id",
            "dev.plushie.test",
            "--app-name",
            "Test App",
            "--pyinstaller-entry",
            "src/test_app/__main__.py",
            "--pyinstaller-name",
            "TestApp",
            "--add-data",
            "assets:assets",
            "--hidden-import",
            "pandas",
            "--collect-submodules",
            "plushie",
        ]
    )

    assert args.command == "package"
    assert args.pyinstaller_entry == "src/test_app/__main__.py"
    assert args.pyinstaller_name == "TestApp"
    assert args.add_data == ["assets:assets"]
    assert args.hidden_import == ["pandas"]
    assert args.collect_submodules == ["plushie"]


def test_package_pyinstaller_forwards_renderer_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, Any]] = []

    def fake_package_pyinstaller_payload(**kwargs: Any) -> dict[str, Path | str]:
        calls.append(kwargs)
        return {
            "manifest_path": Path("dist/package/plushie-package.toml"),
        }

    monkeypatch.setattr(
        "plushie.package.package_pyinstaller_payload",
        fake_package_pyinstaller_payload,
    )

    cli._cmd_package(
        argparse.Namespace(
            write_package_config=False,
            app_id="dev.plushie.test",
            app_name="Test App",
            app_version="0.1.0",
            package_config=None,
            pyinstaller_entry="src/test_app/__main__.py",
            pyinstaller_name="TestApp",
            target="linux-x86_64",
            renderer_kind="stock",
            renderer_path="dist/custom-renderer",
            app_icon=None,
            add_data=[],
            hidden_import=[],
            collect_submodules=[],
            pyinstaller_arg=[],
            package_dir="dist",
            dist_dir="dist",
            spec_dir="build/pyinstaller-spec",
            work_dir="build/pyinstaller",
            manifest_out=None,
        )
    )

    assert calls[0]["renderer_path"] == "dist/custom-renderer"


def test_connect_token_flag_wins_over_env_and_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime
    import plushie.transport

    connection_calls: list[dict[str, Any]] = []

    class FakeSocketAdapter:
        def __init__(self, address: str, **kwargs: Any) -> None:
            pass

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    def fake_from_iostream(adapter: object, **kwargs: Any) -> FakeConnection:
        connection_calls.append(kwargs)
        return FakeConnection()

    class FakeRuntime:
        def __init__(self, _app: object, _conn: object) -> None:
            pass

        def run(self) -> None:
            pass

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie.transport, "SocketAdapter", FakeSocketAdapter)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "from_iostream",
        staticmethod(fake_from_iostream),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)
    monkeypatch.setenv("PLUSHIE_TOKEN", "env-token")
    monkeypatch.setattr(cli, "_read_token_from_stdin", lambda: "stdin-token")

    cli._cmd_connect(
        argparse.Namespace(
            app="demo:App",
            json=False,
            socket="/tmp/plushie.sock",
            token="flag-token",
        )
    )

    assert connection_calls[0]["token"] == "flag-token"


def test_connect_env_token_wins_over_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime
    import plushie.transport

    connection_calls: list[dict[str, Any]] = []

    class FakeSocketAdapter:
        def __init__(self, address: str, **kwargs: Any) -> None:
            pass

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    def fake_from_iostream(adapter: object, **kwargs: Any) -> FakeConnection:
        connection_calls.append(kwargs)
        return FakeConnection()

    class FakeRuntime:
        def __init__(self, _app: object, _conn: object) -> None:
            pass

        def run(self) -> None:
            pass

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie.transport, "SocketAdapter", FakeSocketAdapter)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "from_iostream",
        staticmethod(fake_from_iostream),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)
    monkeypatch.setenv("PLUSHIE_TOKEN", "env-token")
    monkeypatch.setattr(cli, "_read_token_from_stdin", lambda: "stdin-token")

    cli._cmd_connect(
        argparse.Namespace(
            app="demo:App",
            json=False,
            socket="/tmp/plushie.sock",
            token=None,
        )
    )

    assert connection_calls[0]["token"] == "env-token"


def test_connect_stdin_token_used_when_no_flag_or_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime
    import plushie.transport

    connection_calls: list[dict[str, Any]] = []

    class FakeSocketAdapter:
        def __init__(self, address: str, **kwargs: Any) -> None:
            pass

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    def fake_from_iostream(adapter: object, **kwargs: Any) -> FakeConnection:
        connection_calls.append(kwargs)
        return FakeConnection()

    class FakeRuntime:
        def __init__(self, _app: object, _conn: object) -> None:
            pass

        def run(self) -> None:
            pass

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie.transport, "SocketAdapter", FakeSocketAdapter)
    monkeypatch.setattr(
        plushie.connection.Connection,
        "from_iostream",
        staticmethod(fake_from_iostream),
    )
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)
    monkeypatch.delenv("PLUSHIE_TOKEN", raising=False)
    monkeypatch.setattr(cli, "_read_token_from_stdin", lambda: "stdin-token")

    cli._cmd_connect(
        argparse.Namespace(
            app="demo:App",
            json=False,
            socket="/tmp/plushie.sock",
            token=None,
        )
    )

    assert connection_calls[0]["token"] == "stdin-token"


def test_connect_errors_on_stdin_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.delenv("PLUSHIE_TOKEN", raising=False)
    monkeypatch.setattr(cli, "_read_token_from_stdin", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        cli._cmd_connect(
            argparse.Namespace(
                app="demo:App",
                json=False,
                socket="/tmp/plushie.sock",
                token=None,
            )
        )

    assert exc_info.value.code == 1


def test_read_token_from_stdin_parses_valid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io
    import select

    monkeypatch.setattr(select, "select", lambda *_args, **_kwargs: ([True], [], []))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"token": "abc123"}\n'))

    result = cli._read_token_from_stdin()

    assert result == "abc123"


def test_read_token_from_stdin_returns_none_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import select

    monkeypatch.setattr(select, "select", lambda *_args, **_kwargs: ([], [], []))

    result = cli._read_token_from_stdin()

    assert result is None


def test_read_token_from_stdin_errors_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io
    import select

    monkeypatch.setattr(select, "select", lambda *_args, **_kwargs: ([True], [], []))
    monkeypatch.setattr(sys, "stdin", io.StringIO("not-json\n"))

    with pytest.raises(SystemExit) as exc_info:
        cli._read_token_from_stdin()

    assert exc_info.value.code == 1


def test_read_token_from_stdin_errors_on_wrong_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io
    import select

    monkeypatch.setattr(select, "select", lambda *_args, **_kwargs: ([True], [], []))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"not_token": "abc"}\n'))

    with pytest.raises(SystemExit) as exc_info:
        cli._read_token_from_stdin()

    assert exc_info.value.code == 1


def test_package_stock_renderer_rejected_when_native_widgets_in_pyproject(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--renderer-kind stock must fail before doing any payload work when native widgets are declared."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.plushie]\nextensions = [{kind = "rust", crate = "my_widget"}]\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cli._cmd_package(
            argparse.Namespace(
                write_package_config=False,
                app_id="dev.plushie.test",
                app_name=None,
                app_version=None,
                package_config=None,
                pyinstaller_entry=None,
                target="linux-x86_64",
                renderer_kind="stock",
                renderer_path="bin/plushie-renderer",
                payload_dir=str(tmp_path / "payload"),
                start_command=["host/Test/Test"],
                manifest_out=None,
            )
        )

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Native widget packaging requires a custom renderer" in err
    assert "Use --renderer-kind custom" in err
    assert not (tmp_path / "payload").exists()


def test_package_stock_renderer_rejected_when_native_widgets_in_json_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback plushie_extensions.json also triggers the stock-renderer rejection."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "plushie_extensions.json").write_text(
        '{"extensions": [{"kind": "rust", "crate": "my_widget"}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cli._cmd_package(
            argparse.Namespace(
                write_package_config=False,
                app_id="dev.plushie.test",
                app_name=None,
                app_version=None,
                package_config=None,
                pyinstaller_entry=None,
                target="linux-x86_64",
                renderer_kind="stock",
                renderer_path="bin/plushie-renderer",
                payload_dir=str(tmp_path / "payload"),
                start_command=["host/Test/Test"],
                manifest_out=None,
            )
        )

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Native widget packaging requires a custom renderer" in err


def test_package_custom_renderer_allowed_when_native_widgets_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--renderer-kind custom must not be rejected even when native widgets are declared."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.plushie]\nextensions = [{kind = "rust", crate = "my_widget"}]\n',
        encoding="utf-8",
    )

    calls: list[dict[str, Any]] = []

    def fake_package_prepared_payload(**kwargs: Any) -> Path:
        calls.append(kwargs)
        manifest = tmp_path / "plushie-package.toml"
        manifest.write_text("schema_version = 1\n")
        return manifest

    monkeypatch.setattr(
        "plushie.package.package_prepared_payload",
        fake_package_prepared_payload,
    )

    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()

    cli._cmd_package(
        argparse.Namespace(
            write_package_config=False,
            app_id="dev.plushie.test",
            app_name=None,
            app_version=None,
            package_config=None,
            pyinstaller_entry=None,
            target="linux-x86_64",
            renderer_kind="custom",
            renderer_path="bin/plushie-renderer",
            payload_dir=str(payload_dir),
            start_command=["host/Test/Test"],
            manifest_out=None,
        )
    )

    assert calls, "package_prepared_payload should have been called"


def test_package_prepared_payload_writes_and_assembles(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assemble_calls: list[dict[str, Any]] = []

    def fake_package_prepared_payload(**kwargs: Any) -> Path:
        assemble_calls.append(kwargs)
        manifest = Path("dist/package/plushie-package.toml")
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("schema_version = 1\n")
        return manifest

    monkeypatch.setattr(
        "plushie.package.package_prepared_payload",
        fake_package_prepared_payload,
    )

    payload_dir = tmp_path / "dist" / "package" / "payload"
    payload_dir.mkdir(parents=True)

    cli._cmd_package(
        argparse.Namespace(
            write_package_config=False,
            app_id="dev.plushie.test",
            app_name=None,
            app_version="0.1.0",
            package_config=None,
            pyinstaller_entry=None,
            target="linux-x86_64",
            renderer_kind="stock",
            renderer_path="bin/plushie-renderer",
            payload_dir=str(payload_dir),
            start_command=["host/Test/Test"],
            manifest_out=None,
        )
    )

    output = capsys.readouterr().out
    assert "Wrote dist/package/plushie-package.toml" in output
    assert assemble_calls[0]["renderer_path"] == "bin/plushie-renderer"
    assert assemble_calls[0]["start_command"] == ["host/Test/Test"]
