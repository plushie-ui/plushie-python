"""Tests for the plushie command line entry point."""

from __future__ import annotations

import argparse
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


def test_connect_top_level_uses_stdio_without_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime

    stdio_calls: list[dict[str, Any]] = []
    runtime_calls: list[dict[str, Any]] = []
    runtime_runs: list[bool] = []

    class FakeStdioConnection:
        def __init__(self, **kwargs: Any) -> None:
            stdio_calls.append(kwargs)

        def __enter__(self) -> FakeStdioConnection:
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
    monkeypatch.setattr(plushie.connection, "StdioConnection", FakeStdioConnection)
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)

    plushie.connect(cast(Any, DummyApp))

    assert stdio_calls == [{"format": "msgpack"}]
    assert isinstance(runtime_calls[0]["app"], DummyApp)
    assert runtime_calls[0]["conn"].__class__ is FakeStdioConnection
    assert runtime_calls[0]["daemon"] is False
    assert runtime_runs == [True]


def test_connect_json_constructs_stdio_connection_with_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime

    stdio_calls: list[dict[str, Any]] = []
    runtime_calls: list[tuple[object, object]] = []
    runtime_runs: list[bool] = []

    class FakeStdioConnection:
        def __init__(self, **kwargs: Any) -> None:
            stdio_calls.append(kwargs)

        def __enter__(self) -> FakeStdioConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    class FakeRuntime:
        def __init__(self, app: object, conn: object) -> None:
            runtime_calls.append((app, conn))

        def run(self) -> None:
            runtime_runs.append(True)

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie.connection, "StdioConnection", FakeStdioConnection)
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)
    monkeypatch.delenv("PLUSHIE_SOCKET", raising=False)

    cli._cmd_connect(argparse.Namespace(app="demo:App", json=True))

    assert stdio_calls == [{"format": "json"}]
    assert isinstance(runtime_calls[0][0], DummyApp)
    assert runtime_calls[0][1].__class__ is FakeStdioConnection
    assert runtime_runs == [True]


def test_connect_default_constructs_stdio_connection_with_msgpack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plushie.connection
    import plushie.runtime

    stdio_calls: list[dict[str, Any]] = []

    class FakeStdioConnection:
        def __init__(self, **kwargs: Any) -> None:
            stdio_calls.append(kwargs)

        def __enter__(self) -> FakeStdioConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    class FakeRuntime:
        def __init__(self, _app: object, _conn: object) -> None:
            pass

        def run(self) -> None:
            pass

    monkeypatch.setattr(cli, "_import_app", lambda _spec: DummyApp)
    monkeypatch.setattr(plushie.connection, "StdioConnection", FakeStdioConnection)
    monkeypatch.setattr(plushie.runtime, "Runtime", FakeRuntime)
    monkeypatch.delenv("PLUSHIE_SOCKET", raising=False)

    cli._cmd_connect(argparse.Namespace(app="demo:App", json=False))

    assert stdio_calls == [{"format": "msgpack"}]


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
