""".plushie script parser and runner.

Parses and executes ``.plushie`` test scripts -- a declarative format
for describing interaction sequences. The format has a header (app,
viewport, theme, backend) separated from the instruction body by
``-----``.

Supported instructions:

- ``click "selector"``
- ``type "selector" "text"``
- ``type_key key`` (press + release, supports modifiers like ``ctrl+s``)
- ``press key``
- ``release key``
- ``expect "text"``
- ``tree_hash "name"``
- ``screenshot "name"``
- ``assert_text "selector" "text"``
- ``assert_model "expression"``
- ``move "selector"`` or ``move "x,y"``
- ``wait N`` (milliseconds)

Reference: ``~/projects/plushie-elixir/docs/testing.md`` "Script-based testing".
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("plushie")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScriptHeader:
    """Parsed header of a ``.plushie`` script.

    Attributes:
        app: Module:Class specifier for the app.
        viewport: Viewport size as ``(width, height)``.
        theme: Theme name.
        backend: Backend name (``mock``, ``headless``, ``windowed``).
    """

    app: str
    viewport: tuple[int, int] = (800, 600)
    theme: str = "dark"
    backend: str = "mock"


@dataclass(frozen=True, slots=True)
class Instruction:
    """A single parsed instruction from a ``.plushie`` script.

    Attributes:
        command: The instruction name (e.g. ``"click"``, ``"expect"``).
        args: Positional arguments parsed from the instruction line.
        line_number: Source line number for error reporting.
    """

    command: str
    args: list[str] = field(default_factory=list)
    line_number: int = 0


@dataclass(frozen=True, slots=True)
class Script:
    """A fully parsed ``.plushie`` script.

    Attributes:
        path: Filesystem path to the script.
        header: Parsed header fields.
        instructions: Ordered list of instructions.
    """

    path: str
    header: ScriptHeader
    instructions: list[Instruction]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


_QUOTED_RE = re.compile(r'"([^"]*)"')
"""Regex to extract double-quoted string arguments."""


def parse_script(path: str) -> Script:
    """Parse a ``.plushie`` script file.

    Args:
        path: Path to the script file.

    Returns:
        A parsed ``Script`` instance.

    Raises:
        ValueError: If the script is malformed (no separator, missing
            required header fields).
    """
    text = Path(path).read_text(encoding="utf-8")
    return parse_script_text(text, path=path)


def parse_script_text(text: str, *, path: str = "<string>") -> Script:
    """Parse a ``.plushie`` script from a string.

    Args:
        text: The script content.
        path: Display path for error messages.

    Returns:
        A parsed ``Script`` instance.

    Raises:
        ValueError: If the script is malformed.
    """
    lines = text.split("\n")

    # Find the separator
    sep_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("-----"):
            sep_index = i
            break

    if sep_index < 0:
        raise ValueError(f"{path}: missing '-----' separator between header and body")

    header_lines = lines[:sep_index]
    body_lines = lines[sep_index + 1 :]

    header = _parse_header(header_lines, path)
    instructions = _parse_instructions(body_lines, path, offset=sep_index + 2)

    return Script(path=path, header=header, instructions=instructions)


def _parse_header(lines: list[str], path: str) -> ScriptHeader:
    """Parse the header section of a script.

    Args:
        lines: Header lines (before the separator).
        path: Script path for error messages.

    Returns:
        A ``ScriptHeader`` instance.

    Raises:
        ValueError: If required fields are missing.
    """
    fields: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        fields[key.strip().lower()] = value.strip()

    app = fields.get("app")
    if not app:
        raise ValueError(f"{path}: header missing required 'app' field")

    viewport = (800, 600)
    vp_str = fields.get("viewport", "")
    if vp_str:
        match = re.match(r"(\d+)x(\d+)", vp_str)
        if match:
            viewport = (int(match.group(1)), int(match.group(2)))

    theme = fields.get("theme", "dark")
    backend = fields.get("backend", "mock")

    return ScriptHeader(app=app, viewport=viewport, theme=theme, backend=backend)


def _parse_instructions(
    lines: list[str],
    path: str,
    offset: int,
) -> list[Instruction]:
    """Parse the instruction body of a script.

    Args:
        lines: Body lines (after the separator).
        path: Script path for error messages.
        offset: Line number offset for error reporting.

    Returns:
        List of parsed ``Instruction`` instances.
    """
    instructions: list[Instruction] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        line_num = offset + i
        instruction = _parse_instruction_line(stripped, line_num)
        if instruction is not None:
            instructions.append(instruction)

    return instructions


def _parse_instruction_line(line: str, line_number: int) -> Instruction | None:
    """Parse a single instruction line.

    Handles both quoted arguments (``click "#btn"``) and bare
    arguments (``wait 500``, ``press ctrl+s``).

    Args:
        line: The trimmed instruction line.
        line_number: Source line number.

    Returns:
        An ``Instruction``, or ``None`` if the line is unparseable.
    """
    # Split on first whitespace to get the command
    parts = line.split(None, 1)
    if not parts:
        return None

    command = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # Extract all quoted strings
    quoted = _QUOTED_RE.findall(rest)

    if quoted:
        args = quoted
    elif rest.strip():
        # Bare arguments (e.g. "wait 500", "press ctrl+s")
        args = rest.strip().split()
    else:
        args = []

    return Instruction(command=command, args=args, line_number=line_number)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class ScriptRunner:
    """Executes parsed ``.plushie`` scripts against an ``AppFixture``.

    Args:
        fixture: The test fixture to run instructions against.
        replay: If ``True``, honour ``wait`` instructions with real
            delays.
    """

    def __init__(self, fixture: Any, *, replay: bool = False) -> None:
        self._fixture = fixture
        self._replay = replay
        self._errors: list[str] = []

    @property
    def errors(self) -> list[str]:
        """Accumulated error messages from failed assertions."""
        return list(self._errors)

    def run(self, script: Script) -> bool:
        """Execute all instructions in a script.

        Args:
            script: The parsed script to execute.

        Returns:
            ``True`` if all instructions passed, ``False`` if any
            assertion failed.
        """
        self._errors = []

        for instr in script.instructions:
            try:
                self._execute(instr, script.path)
            except Exception as exc:
                msg = (
                    f"{script.path}:{instr.line_number}: {instr.command} failed: {exc}"
                )
                self._errors.append(msg)
                logger.error(msg)

        return len(self._errors) == 0

    def _execute(self, instr: Instruction, path: str) -> None:
        """Execute a single instruction.

        Args:
            instr: The instruction to execute.
            path: Script path for error context.
        """
        cmd = instr.command
        args = instr.args
        fixture = self._fixture

        if cmd == "click":
            if not args:
                raise ValueError("click requires a selector argument")
            fixture.click(args[0])

        elif cmd == "type":
            if len(args) >= 2:
                # type "selector" "text"
                fixture.type_text(args[0], args[1])
            elif len(args) == 1:
                # type enter  (bare key -- type_key shorthand)
                fixture.type_key(args[0])
            else:
                raise ValueError("type requires arguments")

        elif cmd == "type_key":
            if not args:
                raise ValueError("type_key requires a key argument")
            fixture.type_key(args[0])

        elif cmd == "press":
            if not args:
                raise ValueError("press requires a key argument")
            fixture.press(args[0])

        elif cmd == "release":
            if not args:
                raise ValueError("release requires a key argument")
            fixture.release(args[0])

        elif cmd == "expect":
            if not args:
                raise ValueError("expect requires a text argument")
            expected = args[0]
            tree = fixture.tree
            if tree is None:
                raise AssertionError(f"expect {expected!r}: no tree available")
            tree_text = _extract_all_text(tree)
            if expected not in tree_text:
                raise AssertionError(
                    f"expect {expected!r}: text not found in tree. "
                    f"Available text: {tree_text[:200]!r}"
                )

        elif cmd == "tree_hash":
            if not args:
                raise ValueError("tree_hash requires a name argument")
            fixture.assert_tree_hash(args[0])

        elif cmd == "screenshot":
            if not args:
                raise ValueError("screenshot requires a name argument")
            fixture.assert_screenshot(args[0])

        elif cmd == "assert_text":
            if len(args) < 2:
                raise ValueError("assert_text requires selector and text arguments")
            selector = args[0]
            expected = args[1]
            actual = fixture.text(selector)
            if actual is None:
                raise AssertionError(
                    f"assert_text {selector!r}: element not found or has no text"
                )
            if actual != expected:
                raise AssertionError(
                    f"assert_text {selector!r}: expected {expected!r}, got {actual!r}"
                )

        elif cmd == "assert_model":
            if not args:
                raise ValueError("assert_model requires an expression argument")
            expression = args[0]
            model_str = repr(fixture.model)
            if expression not in model_str:
                raise AssertionError(
                    f"assert_model: {expression!r} not found in model repr: "
                    f"{model_str[:200]!r}"
                )

        elif cmd == "move":
            if not args:
                raise ValueError("move requires arguments")
            target = args[0]
            # Check if it's coordinates "x,y"
            if "," in target:
                parts = target.split(",")
                if len(parts) == 2:
                    x, y = float(parts[0]), float(parts[1])
                    fixture.move_to(x, y)
                else:
                    raise ValueError(f"invalid move coordinates: {target!r}")
            else:
                # Move to a selector -- currently a no-op in mock mode
                # since we don't have widget bounds.
                logger.debug("move to selector %r (no-op in mock mode)", target)

        elif cmd == "wait":
            if not args:
                raise ValueError("wait requires a duration argument")
            ms = int(args[0])
            if self._replay:
                time.sleep(ms / 1000.0)

        else:
            logger.warning(
                "%s:%d: unknown instruction: %s",
                path,
                instr.line_number,
                cmd,
            )


# ---------------------------------------------------------------------------
# Text extraction helper
# ---------------------------------------------------------------------------


def _extract_all_text(tree: dict[str, Any]) -> str:
    """Recursively extract all text content from a tree for ``expect``.

    Concatenates content, label, value, and placeholder props from all
    nodes, separated by spaces.

    Args:
        tree: A normalized tree node dict.

    Returns:
        A single string containing all text in the tree.
    """
    parts: list[str] = []
    _collect_text(tree, parts)
    return " ".join(parts)


def _collect_text(node: dict[str, Any], parts: list[str]) -> None:
    """Recursively collect text props from a tree node.

    Args:
        node: A tree node dict.
        parts: Accumulator list.
    """
    props = node.get("props", {})
    for key in ("content", "label", "value", "placeholder"):
        val = props.get(key)
        if isinstance(val, str) and val:
            parts.append(val)

    for child in node.get("children", []):
        if isinstance(child, dict):
            _collect_text(child, parts)


# ---------------------------------------------------------------------------
# Top-level runners
# ---------------------------------------------------------------------------


def run_scripts(files: list[str]) -> bool:
    """Run a list of ``.plushie`` script files.

    Each script is parsed, the app is loaded into an ``AppFixture``,
    and instructions are executed. Results are printed to stdout.

    Args:
        files: List of script file paths.

    Returns:
        ``True`` if all scripts passed, ``False`` otherwise.
    """
    from plushie.__main__ import _import_app
    from plushie.testing.fixture import AppFixture
    from plushie.testing.pool import SessionPool

    all_passed = True
    pool: SessionPool | None = None

    try:
        for filepath in files:
            script = parse_script(filepath)
            header = script.header

            # Start pool if needed (lazy, one per backend)
            if pool is None:
                pool = SessionPool(mode=header.backend)
                pool.start()

            app_class = _import_app(header.app)

            with AppFixture(app_class, pool) as fixture:
                runner = ScriptRunner(fixture)
                passed = runner.run(script)

            status = "PASS" if passed else "FAIL"
            print(f"  {status}  {filepath}")

            if not passed:
                all_passed = False
                for err in runner.errors:
                    print(f"    {err}")
    finally:
        if pool is not None:
            pool.stop()

    return all_passed


def replay_script(filepath: str) -> None:
    """Replay a ``.plushie`` script with real windows.

    Forces windowed backend and honours ``wait`` timings.

    Args:
        filepath: Path to the script file.
    """
    from plushie.__main__ import _import_app
    from plushie.testing.fixture import AppFixture
    from plushie.testing.pool import SessionPool

    script = parse_script(filepath)

    pool = SessionPool(mode="windowed")
    pool.start()

    try:
        app_class = _import_app(script.header.app)

        with AppFixture(app_class, pool) as fixture:
            runner = ScriptRunner(fixture, replay=True)
            passed = runner.run(script)

        status = "PASS" if passed else "FAIL"
        print(f"{status}  {filepath}")

        if not passed:
            for err in runner.errors:
                print(f"  {err}")
    finally:
        pool.stop()


__all__ = [
    "Instruction",
    "Script",
    "ScriptHeader",
    "ScriptRunner",
    "parse_script",
    "parse_script_text",
    "replay_script",
    "run_scripts",
]
