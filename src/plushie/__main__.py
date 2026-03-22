"""CLI entry point for plushie: ``python -m plushie <command>``.

Provides commands matching the Elixir mix tasks:

- ``run`` -- resolve binary, spawn renderer, start runtime, block
- ``connect`` -- stdio transport mode (for ``plushie --exec``)
- ``download`` -- fetch precompiled binary
- ``build`` -- build custom binary with extensions
- ``inspect`` -- init app, call view, normalize, print as JSON
- ``script`` -- run ``.plushie`` test scripts
- ``replay`` -- replay a script with real windows
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from typing import Any

from plushie.app import App

logger = logging.getLogger("plushie")


def _import_app(spec: str) -> type[App[Any]]:
    """Import an App class from a ``module:Class`` specifier.

    Args:
        spec: A string like ``"mypackage.mymodule:MyApp"`` where the
            part before the colon is a dotted module path and the part
            after is the class name.

    Returns:
        The App subclass.

    Raises:
        SystemExit: If the specifier is malformed, the module cannot be
            imported, or the attribute is not an App subclass.
    """
    if ":" not in spec:
        print(
            f"error: invalid app specifier {spec!r} -- expected module:Class",
            file=sys.stderr,
        )
        raise SystemExit(1)

    module_path, class_name = spec.rsplit(":", 1)

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        print(f"error: cannot import module {module_path!r}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    cls = getattr(module, class_name, None)
    if cls is None:
        print(
            f"error: module {module_path!r} has no attribute {class_name!r}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not (isinstance(cls, type) and issubclass(cls, App)):
        print(
            f"error: {spec!r} is not an App subclass",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return cls


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_run(args: argparse.Namespace) -> None:
    """Handle the ``run`` command."""
    import plushie

    app_class = _import_app(args.app)

    mode = args.mode
    use_json = args.json
    watch = args.watch

    conn_opts: dict[str, Any] = {}
    if use_json:
        conn_opts["json"] = True

    if watch:
        from plushie.dev_server import DevServer

        dev = DevServer(args.app, mode=mode, **conn_opts)
        dev.run()
    else:
        plushie.run(app_class, mode=mode, **conn_opts)


def _cmd_connect(args: argparse.Namespace) -> None:
    """Handle the ``connect`` command (stdio transport)."""
    from plushie.connection import StdioConnection
    from plushie.runtime import Runtime

    app_class = _import_app(args.app)
    app = app_class()

    with StdioConnection() as conn:
        # StdioConnection doesn't have the same interface as Connection
        # but Runtime expects Connection. We use duck typing here since
        # both implement the same send/receive interface.
        runtime = Runtime(app, conn)  # type: ignore[arg-type]
        runtime.run()


def _cmd_download(args: argparse.Namespace) -> None:
    """Handle the ``download`` command."""
    version = args.version

    if args.wasm:
        from plushie.binary import download_wasm

        path = download_wasm(version=version)
        print(f"downloaded WASM bundle: {path}")
    else:
        from plushie.binary import download

        path = download(version=version)
        print(f"downloaded: {path}")


def _cmd_build(args: argparse.Namespace) -> None:
    """Handle the ``build`` command."""
    import os
    import subprocess

    if args.wasm:
        from plushie.binary import build_wasm

        source = os.environ.get("PLUSHIE_SOURCE_PATH")
        path = build_wasm(source_path=source)
        print(f"built WASM renderer: {path}")
        return

    from plushie.extension import ExtensionDef, generate_cargo_toml, generate_main_rs

    # Look for extensions configuration. For now, support a simple
    # JSON config file or environment variable.
    config_path = args.config or "plushie_extensions.json"

    extensions: list[ExtensionDef] = []

    if os.path.isfile(config_path):
        with open(config_path) as f:
            data = json.load(f)

        for ext_data in data.get("extensions", []):
            from plushie.extension import CommandDef, ParamDef, PropDef

            props = [
                PropDef(p["name"], p["prop_type"]) for p in ext_data.get("props", [])
            ]
            commands = [
                CommandDef(
                    c["name"],
                    [
                        ParamDef(pm["name"], pm["param_type"])
                        for pm in c.get("params", [])
                    ],
                )
                for c in ext_data.get("commands", [])
            ]
            extensions.append(
                ExtensionDef(
                    kind=ext_data["kind"],
                    rust_crate=ext_data["rust_crate"],
                    rust_constructor=ext_data["rust_constructor"],
                    props=props,
                    commands=commands,
                )
            )

    if not extensions:
        print("no extensions found -- nothing to build")
        print(f"  looked for config at: {config_path}")
        raise SystemExit(1)

    binary_name = args.name or "plushie-custom"

    # Generate build files
    build_dir = os.path.join("build", binary_name)
    os.makedirs(os.path.join(build_dir, "runner", "src"), exist_ok=True)

    cargo_toml = generate_cargo_toml(extensions, binary_name=binary_name)
    main_rs = generate_main_rs(extensions)

    cargo_path = os.path.join(build_dir, "Cargo.toml")
    main_path = os.path.join(build_dir, "runner", "src", "main.rs")

    with open(cargo_path, "w") as f:
        f.write(cargo_toml)
    with open(main_path, "w") as f:
        f.write(main_rs)

    print(f"generated: {cargo_path}")
    print(f"generated: {main_path}")

    # Run cargo build
    print("building...")
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=build_dir,
        check=False,
    )
    if result.returncode != 0:
        print("build failed", file=sys.stderr)
        raise SystemExit(result.returncode)

    print(f"built: {build_dir}/target/release/{binary_name}")


def _cmd_inspect(args: argparse.Namespace) -> None:
    """Handle the ``inspect`` command."""
    from plushie.runtime import unwrap_result
    from plushie.tree import normalize

    app_class = _import_app(args.app)
    app = app_class()

    raw = app.init()
    model, _commands = unwrap_result(raw)

    raw_tree = app.view(model)
    tree = normalize(raw_tree)

    print(json.dumps(tree, indent=2, default=str))


def _cmd_script(args: argparse.Namespace) -> None:
    """Handle the ``script`` command."""
    from plushie.script import run_scripts

    files = args.files
    if not files:
        # Default: look for .plushie files in test/scripts/
        import glob

        files = sorted(glob.glob("test/scripts/**/*.plushie", recursive=True))
        if not files:
            files = sorted(glob.glob("tests/scripts/**/*.plushie", recursive=True))

    if not files:
        print("no .plushie script files found")
        raise SystemExit(1)

    success = run_scripts(files)
    if not success:
        raise SystemExit(1)


def _cmd_replay(args: argparse.Namespace) -> None:
    """Handle the ``replay`` command."""
    from plushie.script import replay_script

    replay_script(args.file)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="plushie",
        description="plushie -- native desktop GUI framework for Python",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="enable verbose logging",
    )
    subparsers = parser.add_subparsers(dest="command", help="available commands")

    # run
    run_parser = subparsers.add_parser(
        "run",
        help="run a plushie application",
    )
    run_parser.add_argument("app", help="app specifier (module:Class)")
    run_parser.add_argument(
        "--mode",
        choices=["mock", "headless"],
        default=None,
        help="renderer mode (default: windowed)",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="use JSON wire format instead of msgpack",
    )
    run_parser.add_argument(
        "--watch",
        action="store_true",
        help="enable file watching for live reload",
    )

    # connect
    connect_parser = subparsers.add_parser(
        "connect",
        help="stdio transport mode (for plushie --exec)",
    )
    connect_parser.add_argument("app", help="app specifier (module:Class)")

    # download
    download_parser = subparsers.add_parser(
        "download",
        help="download precompiled binary",
    )
    download_parser.add_argument(
        "--version",
        default=None,
        help="version to download (default: latest)",
    )
    download_parser.add_argument(
        "--wasm",
        action="store_true",
        help="download WASM renderer bundle instead of native binary",
    )

    # build
    build_parser = subparsers.add_parser(
        "build",
        help="build custom binary with extensions",
    )
    build_parser.add_argument(
        "--config",
        default=None,
        help="path to extensions config JSON (default: plushie_extensions.json)",
    )
    build_parser.add_argument(
        "--name",
        default=None,
        help="output binary name (default: plushie-custom)",
    )
    build_parser.add_argument(
        "--wasm",
        action="store_true",
        help="build WASM renderer from source via wasm-pack",
    )

    # inspect
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="init app, call view, normalize, print tree as JSON",
    )
    inspect_parser.add_argument("app", help="app specifier (module:Class)")

    # script
    script_parser = subparsers.add_parser(
        "script",
        help="run .plushie test scripts",
    )
    script_parser.add_argument(
        "files",
        nargs="*",
        help="script files to run (default: test/scripts/**/*.plushie)",
    )

    # replay
    replay_parser = subparsers.add_parser(
        "replay",
        help="replay a .plushie script with real windows",
    )
    replay_parser.add_argument("file", help="script file to replay")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )

    command_map: dict[str, Any] = {
        "run": _cmd_run,
        "connect": _cmd_connect,
        "download": _cmd_download,
        "build": _cmd_build,
        "inspect": _cmd_inspect,
        "script": _cmd_script,
        "replay": _cmd_replay,
    }

    handler = command_map.get(args.command)
    if handler is None:
        parser.print_help()
        raise SystemExit(1)

    handler(args)


if __name__ == "__main__":
    main()
