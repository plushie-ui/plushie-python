"""CLI entry point for plushie: ``python -m plushie <command>``.

Provides commands matching the Elixir mix tasks:

- ``run`` - resolve binary, spawn renderer, start runtime, block
- ``connect`` - standalone app entrypoint for socket or spawned renderer startup
- ``download`` - fetch precompiled binary
- ``build`` - build custom binary with extensions
- ``inspect`` - init app, call view, normalize, print as JSON
- ``script`` - run ``.plushie`` test scripts
- ``replay`` - replay a script with real windows
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, get_args

if TYPE_CHECKING:
    from plushie.native_widget import NativeWidget

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
            f"error: invalid app specifier {spec!r}, expected module:Class",
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
# pyproject.toml config
# ---------------------------------------------------------------------------


def _load_pyproject_config(project_dir: str | Path | None = None) -> dict[str, Any]:
    """Load ``[tool.plushie]`` from pyproject.toml if present.

    Looks for ``pyproject.toml`` in *project_dir* (defaults to cwd).
    Returns the ``[tool.plushie]`` table as a dict, or an empty dict
    if the file is missing or the section doesn't exist.
    """
    root = Path(project_dir) if project_dir else Path.cwd()
    toml_path = root / "pyproject.toml"
    if not toml_path.is_file():
        return {}
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data.get("tool", {}).get("plushie", {})


def _load_project_config(project_dir: str | Path | None = None) -> dict[str, Any]:
    """Load ``[project]`` from pyproject.toml if present."""
    root = Path(project_dir) if project_dir else Path.cwd()
    toml_path = root / "pyproject.toml"
    if not toml_path.is_file():
        return {}
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    project = data.get("project", {})
    return project if isinstance(project, dict) else {}


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
        conn_opts["format"] = "json"

    daemon = getattr(args, "daemon", False)

    if watch:
        from plushie.dev_server import DevServer

        dev = DevServer(args.app, mode=mode, **conn_opts)
        dev.run()
    else:
        plushie.run(app_class, mode=mode, daemon=daemon, **conn_opts)


def _cmd_connect(args: argparse.Namespace) -> None:
    """Handle the ``connect`` command."""
    from plushie.connection import Connection
    from plushie.runtime import Runtime
    from plushie.transport import SocketAdapter

    app_class = _import_app(args.app)
    app = app_class()

    wire_format = "json" if args.json else "msgpack"
    socket_addr = getattr(args, "socket", None) or os.environ.get("PLUSHIE_SOCKET")
    token = getattr(args, "token", None) or os.environ.get("PLUSHIE_TOKEN")

    if socket_addr:
        adapter = SocketAdapter(socket_addr, format=wire_format)
        with Connection.from_iostream(adapter, token=token) as conn:
            runtime = Runtime(app, cast(Any, conn))
            runtime.run()
        return

    with Connection.open(format=wire_format) as conn:
        runtime = Runtime(app, conn)
        runtime.run()


def _cmd_package(args: argparse.Namespace) -> None:
    """Handle the ``package`` command."""
    from plushie.package import (
        manifest_for_payload,
        package_pyinstaller_payload,
        write_manifest,
    )

    project_cfg = _load_project_config()
    app_version = args.app_version or project_cfg.get("version") or "0.1.0"

    if args.pyinstaller_entry is not None:
        name = args.pyinstaller_name or args.app_name
        if name is None:
            print(
                "error: --pyinstaller-entry requires --pyinstaller-name or --app-name",
                file=sys.stderr,
            )
            raise SystemExit(1)

        result = package_pyinstaller_payload(
            entry=args.pyinstaller_entry,
            name=name,
            app_id=args.app_id,
            app_name=args.app_name,
            app_version=app_version,
            target=args.target,
            renderer_kind=args.renderer_kind,
            renderer_source=args.renderer_source,
            app_icon=args.app_icon,
            add_data=args.add_data,
            hidden_import=args.hidden_import,
            collect_submodules=args.collect_submodules,
            pyinstaller_arg=args.pyinstaller_arg,
            package_dir=args.package_dir,
            dist_dir=args.dist_dir,
            spec_dir=args.spec_dir,
            work_dir=args.work_dir,
            output=args.output,
            working_dir=args.working_dir,
        )
        print(f"Wrote {result['manifest_path']}")
        print(f"Wrote {result['payload_archive']}")
        return

    if args.renderer_path is None:
        print(
            "error: --renderer-path is required for prepared payloads", file=sys.stderr
        )
        raise SystemExit(1)
    if args.payload_archive is None:
        print(
            "error: --payload-archive is required for prepared payloads",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if args.start_command is None:
        print(
            "error: --start-command is required for prepared payloads", file=sys.stderr
        )
        raise SystemExit(1)

    manifest = manifest_for_payload(
        app_id=args.app_id,
        app_name=args.app_name,
        app_version=app_version,
        target=args.target,
        renderer_kind=args.renderer_kind,
        renderer_source=args.renderer_source or "local-resolve",
        renderer_path=args.renderer_path,
        start_command=args.start_command,
        working_dir=args.working_dir,
        platform_icon=args.platform_icon,
        payload_archive=args.payload_archive,
    )
    output = args.output or "dist/package/plushie-package.toml"
    write_manifest(output, manifest)
    print(f"Wrote {output}")


def _resolve_artifacts(
    args: argparse.Namespace,
    pyproject_cfg: dict[str, Any],
) -> tuple[bool, bool]:
    """Determine which artifacts to process (bin, wasm).

    Resolution order: CLI flags > pyproject.toml ``artifacts`` > default ``["bin"]``.

    Returns:
        Tuple of ``(want_bin, want_wasm)``.
    """
    cli_bin = getattr(args, "bin", False)
    cli_wasm = getattr(args, "wasm", False)

    # If any CLI flag is set, use CLI flags exclusively
    if cli_bin or cli_wasm:
        return cli_bin, cli_wasm

    # Fall back to pyproject.toml artifacts config
    artifacts = pyproject_cfg.get("artifacts")
    if artifacts is not None:
        return "bin" in artifacts, "wasm" in artifacts

    # Default: bin only
    return True, False


def _cmd_download(args: argparse.Namespace) -> None:
    """Handle the ``download`` command."""
    version = args.version
    force = args.force

    pyproject_cfg = _load_pyproject_config()
    want_bin, want_wasm = _resolve_artifacts(args, pyproject_cfg)

    # Block precompiled download when native extensions are configured.
    # The stock binary won't have them registered.
    if want_bin and pyproject_cfg.get("extensions"):
        ext_kinds = [e.get("kind", "?") for e in pyproject_cfg["extensions"]]
        print(
            "cannot download a precompiled binary when native widgets are configured.",
            file=sys.stderr,
        )
        print(f"  native widgets: {', '.join(ext_kinds)}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "use `python -m plushie build` to compile a custom binary "
            "that includes them.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Resolve bin_file: CLI flag > pyproject.toml > None (project-local location)
    bin_file = getattr(args, "bin_file", None) or pyproject_cfg.get("bin_file")

    # Resolve wasm_dir: CLI flag > pyproject.toml > None (project-local location)
    wasm_dir_override = getattr(args, "wasm_dir", None) or pyproject_cfg.get("wasm_dir")

    if want_bin:
        from plushie.binary import download

        path = download(version=version, force=force, bin_file=bin_file)
        print(f"downloaded: {path}")

    if want_wasm:
        from plushie.binary import download_wasm

        path = download_wasm(
            version=version, force=force, wasm_dir_path=wasm_dir_override
        )
        print(f"downloaded WASM bundle: {path}")


def _parse_extensions(raw: list[dict[str, Any]]) -> list[NativeWidget]:
    """Parse a list of raw extension dicts into ``NativeWidget`` objects.

    Works for both JSON config files and pyproject.toml ``[tool.plushie]``
    extension entries.
    """
    from plushie.native_widget import (
        CommandDef,
        NativeWidget,
        ParamDef,
        ParamType,
        PropDef,
        PropType,
        validate,
    )

    if not isinstance(raw, list):
        raise ValueError("extensions must be a list")

    allowed_prop_types = set(get_args(PropType))
    allowed_param_types = set(get_args(ParamType))

    extensions: list[NativeWidget] = []
    for ext_index, ext_data in enumerate(raw):
        ext_path = f"extensions[{ext_index}]"
        if not isinstance(ext_data, dict):
            raise ValueError(f"{ext_path} must be a dict")

        for field in ("kind", "rust_crate", "rust_constructor"):
            if field not in ext_data:
                raise ValueError(f"{ext_path}.{field} is required")
            if not isinstance(ext_data[field], str):
                raise ValueError(f"{ext_path}.{field} must be a string")

        raw_props = ext_data.get("props", [])
        if not isinstance(raw_props, list):
            raise ValueError(f"{ext_path}.props must be a list")

        props: list[PropDef] = []
        for prop_index, prop_data in enumerate(raw_props):
            prop_path = f"{ext_path}.props[{prop_index}]"
            if not isinstance(prop_data, dict):
                raise ValueError(f"{prop_path} must be a dict")
            for field in ("name", "prop_type"):
                if field not in prop_data:
                    raise ValueError(f"{prop_path}.{field} is required")
                if not isinstance(prop_data[field], str):
                    raise ValueError(f"{prop_path}.{field} must be a string")
            prop_type = prop_data["prop_type"]
            if prop_type not in allowed_prop_types:
                raise ValueError(f"{prop_path}.prop_type must be a valid PropType")
            props.append(
                PropDef(prop_data["name"], cast("PropType", prop_type)),
            )

        raw_commands = ext_data.get("commands", [])
        if not isinstance(raw_commands, list):
            raise ValueError(f"{ext_path}.commands must be a list")

        commands: list[CommandDef] = []
        for command_index, command_data in enumerate(raw_commands):
            command_path = f"{ext_path}.commands[{command_index}]"
            if not isinstance(command_data, dict):
                raise ValueError(f"{command_path} must be a dict")
            if "name" not in command_data:
                raise ValueError(f"{command_path}.name is required")
            if not isinstance(command_data["name"], str):
                raise ValueError(f"{command_path}.name must be a string")

            raw_params = command_data.get("params", [])
            if not isinstance(raw_params, list):
                raise ValueError(f"{command_path}.params must be a list")

            params: list[ParamDef] = []
            for param_index, param_data in enumerate(raw_params):
                param_path = f"{command_path}.params[{param_index}]"
                if not isinstance(param_data, dict):
                    raise ValueError(f"{param_path} must be a dict")
                for field in ("name", "param_type"):
                    if field not in param_data:
                        raise ValueError(f"{param_path}.{field} is required")
                    if not isinstance(param_data[field], str):
                        raise ValueError(f"{param_path}.{field} must be a string")
                param_type = param_data["param_type"]
                if param_type not in allowed_param_types:
                    raise ValueError(
                        f"{param_path}.param_type must be a valid ParamType"
                    )
                params.append(
                    ParamDef(param_data["name"], cast("ParamType", param_type))
                )

            commands.append(CommandDef(command_data["name"], params))

        extension = NativeWidget(
            kind=ext_data["kind"],
            rust_crate=ext_data["rust_crate"],
            rust_constructor=ext_data["rust_constructor"],
            props=props,
            commands=commands,
        )
        errors = validate(extension)
        if errors:
            raise ValueError(f"{ext_path}: {'; '.join(errors)}")
        extensions.append(extension)
    return extensions


def _cmd_build(args: argparse.Namespace) -> None:
    """Handle the ``build`` command.

    Delegates renderer workspace generation, widget discovery, and the
    underlying ``cargo build`` invocation to ``cargo-plushie``. The
    Python SDK's role is now limited to: reading widget declarations
    from ``pyproject.toml``, injecting the matching
    ``[package.metadata.plushie.widget]`` blocks into each widget
    crate's ``Cargo.toml``, writing a virtual app ``Cargo.toml``
    carrying ``[package.metadata.plushie]``, and copying the resulting
    binary into the project-local renderer location.
    """
    import os

    from plushie.renderer_build import build

    release = args.release

    # Load pyproject.toml config (used for source_path, build_name,
    # extensions, artifacts, and path overrides).
    pyproject_cfg = _load_pyproject_config()

    want_bin, want_wasm = _resolve_artifacts(args, pyproject_cfg)

    if want_wasm:
        from plushie.binary import build_wasm

        source = os.environ.get(
            "PLUSHIE_RUST_SOURCE_PATH",
            pyproject_cfg.get("source_path"),
        )
        wasm_dir_override = pyproject_cfg.get("wasm_dir")
        path = build_wasm(
            source_path=source, release=release, wasm_dir_path=wasm_dir_override
        )
        print(f"built WASM renderer: {path}")

    if not want_bin:
        return

    # Widget discovery from pyproject.toml. The JSON-file fallback is
    # retained so existing projects keep working.
    extensions: list[NativeWidget] = []

    pyproject_extensions = pyproject_cfg.get("extensions", [])
    if pyproject_extensions:
        extensions = _parse_extensions(pyproject_extensions)
    else:
        config_path = args.config or "plushie_extensions.json"
        if os.path.isfile(config_path):
            with open(config_path) as f:
                data = json.load(f)
            extensions = _parse_extensions(data.get("extensions", []))

    # source_path resolution: env var > pyproject.toml
    source = os.environ.get(
        "PLUSHIE_RUST_SOURCE_PATH",
        pyproject_cfg.get("source_path"),
    )

    # binary_name resolution: --name flag > pyproject.toml build_name > default
    binary_name = args.name or pyproject_cfg.get("build_name") or "plushie-renderer"

    bin_file = pyproject_cfg.get("bin_file")
    verbose = getattr(args, "verbose", False)

    exit_code = build(
        extensions,
        binary_name=binary_name,
        source_path=source,
        release=release,
        verbose=verbose,
        bin_file=bin_file,
    )
    if exit_code != 0:
        raise SystemExit(exit_code)


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
        description="plushie: native desktop GUI framework for Python",
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
    run_parser.add_argument(
        "--daemon",
        action="store_true",
        help="keep running after all windows close",
    )

    # connect
    connect_parser = subparsers.add_parser(
        "connect",
        help="standalone app entrypoint for socket or spawned renderer startup",
    )
    connect_parser.add_argument("app", help="app specifier (module:Class)")
    connect_parser.add_argument(
        "--json",
        action="store_true",
        help="use JSON wire format instead of msgpack",
    )
    connect_parser.add_argument(
        "--socket",
        help="renderer socket address (defaults to PLUSHIE_SOCKET)",
    )
    connect_parser.add_argument(
        "--token",
        help="renderer listen token (defaults to PLUSHIE_TOKEN)",
    )

    # package
    package_parser = subparsers.add_parser(
        "package",
        help="stage a standalone package payload",
    )
    package_parser.add_argument("--app-id", required=True, help="package app id")
    package_parser.add_argument("--app-name", default=None, help="display app name")
    package_parser.add_argument(
        "--app-version",
        default=None,
        help="app version (default: [project].version or 0.1.0)",
    )
    package_parser.add_argument(
        "--target",
        default=None,
        help="package target (default: current OS and architecture)",
    )
    package_parser.add_argument(
        "--renderer-kind",
        choices=["stock", "custom"],
        default="stock",
        help="renderer provenance kind",
    )
    package_parser.add_argument(
        "--renderer-source",
        default=None,
        help="renderer provenance source",
    )
    package_parser.add_argument(
        "--renderer-path",
        default=None,
        help="payload-relative renderer executable path",
    )
    package_parser.add_argument(
        "--payload-archive",
        default=None,
        help="payload archive to hash and record",
    )
    package_parser.add_argument(
        "--platform-icon",
        default=None,
        help="payload-relative platform icon path",
    )
    package_parser.add_argument(
        "--output",
        default=None,
        help="manifest output path",
    )
    package_parser.add_argument(
        "--working-dir",
        default=".",
        help="payload-relative host working directory",
    )
    package_parser.add_argument(
        "--start-command",
        dest="start_command",
        default=None,
        nargs="+",
        help="payload-relative app start command argv",
    )
    package_parser.add_argument(
        "--pyinstaller-entry",
        default=None,
        help="build and stage a PyInstaller payload from this entry script",
    )
    package_parser.add_argument(
        "--pyinstaller-name",
        default=None,
        help="PyInstaller app name (default: --app-name)",
    )
    package_parser.add_argument(
        "--app-icon",
        default=None,
        help="icon file to pass to PyInstaller and copy into the payload",
    )
    package_parser.add_argument(
        "--add-data",
        action="append",
        default=[],
        help="PyInstaller data mapping, using PyInstaller's source:dest form",
    )
    package_parser.add_argument(
        "--hidden-import",
        action="append",
        default=[],
        help="hidden import to pass to PyInstaller",
    )
    package_parser.add_argument(
        "--collect-submodules",
        action="append",
        default=[],
        help="module package whose submodules PyInstaller should collect",
    )
    package_parser.add_argument(
        "--pyinstaller-arg",
        action="append",
        default=[],
        help="extra argument passed through to PyInstaller",
    )
    package_parser.add_argument(
        "--package-dir",
        default="dist/package",
        help="directory for payload, archive, and manifest",
    )
    package_parser.add_argument(
        "--dist-dir",
        default="dist",
        help="PyInstaller dist directory",
    )
    package_parser.add_argument(
        "--spec-dir",
        default="build/pyinstaller-spec",
        help="PyInstaller spec output directory",
    )
    package_parser.add_argument(
        "--work-dir",
        default="build/pyinstaller",
        help="PyInstaller work directory",
    )

    # download
    download_parser = subparsers.add_parser(
        "download",
        help="download precompiled binary",
    )
    download_parser.add_argument(
        "--version",
        default=None,
        help="version to download (default: pinned plushie-rust version)",
    )
    download_parser.add_argument(
        "--bin",
        action="store_true",
        help="download native binary (default when no target specified)",
    )
    download_parser.add_argument(
        "--wasm",
        action="store_true",
        help="download WASM renderer bundle",
    )
    download_parser.add_argument(
        "--force",
        action="store_true",
        help="re-download even if files already exist",
    )
    download_parser.add_argument(
        "--bin-file",
        default=None,
        help="override native binary destination path",
    )
    download_parser.add_argument(
        "--wasm-dir",
        default=None,
        help="override WASM output directory",
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
        help="output binary name (default: plushie-renderer)",
    )
    build_parser.add_argument(
        "--bin",
        action="store_true",
        help="build native binary (default when no target specified)",
    )
    build_parser.add_argument(
        "--wasm",
        action="store_true",
        help="build WASM renderer from source via wasm-pack",
    )
    build_parser.add_argument(
        "--release",
        action="store_true",
        help="build with optimizations (default: debug)",
    )
    build_parser.add_argument(
        "--verbose",
        action="store_true",
        help="print full cargo output on successful builds",
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
        "package": _cmd_package,
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
