"""Tests for plushie.script -- .plushie script parser and runner.

Tests header parsing, instruction parsing, comment/blank handling,
separator detection, quoted string extraction, ScriptRunner dispatch,
and error paths.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from plushie.script import (
    Instruction,
    Script,
    ScriptHeader,
    ScriptRunner,
    _extract_all_text,
    _parse_instruction_line,
    parse_script_text,
)

# ===================================================================
# Header parsing
# ===================================================================


class TestHeaderParsing:
    """Validate header field extraction."""

    def test_basic_header(self) -> None:
        text = "app: myapp.counter:Counter\n-----\n"
        script = parse_script_text(text)
        assert script.header.app == "myapp.counter:Counter"
        assert script.header.viewport == (800, 600)
        assert script.header.theme == "dark"
        assert script.header.backend == "mock"

    def test_all_header_fields(self) -> None:
        text = (
            "app: myapp:App\n"
            "viewport: 1024x768\n"
            "theme: light\n"
            "backend: headless\n"
            "-----\n"
        )
        script = parse_script_text(text)
        assert script.header.app == "myapp:App"
        assert script.header.viewport == (1024, 768)
        assert script.header.theme == "light"
        assert script.header.backend == "headless"

    def test_missing_app_raises(self) -> None:
        text = "theme: dark\n-----\n"
        with pytest.raises(ValueError, match="missing required 'app' field"):
            parse_script_text(text)

    def test_header_comments_ignored(self) -> None:
        text = "# This is a comment\napp: mymod:Cls\n-----\n"
        script = parse_script_text(text)
        assert script.header.app == "mymod:Cls"

    def test_header_blank_lines_ignored(self) -> None:
        text = "\n\napp: mymod:Cls\n\n-----\n"
        script = parse_script_text(text)
        assert script.header.app == "mymod:Cls"

    def test_header_case_insensitive_keys(self) -> None:
        text = "App: mymod:Cls\nTheme: light\nBackend: headless\n-----\n"
        script = parse_script_text(text)
        assert script.header.app == "mymod:Cls"
        assert script.header.theme == "light"
        assert script.header.backend == "headless"

    def test_viewport_invalid_format_uses_default(self) -> None:
        text = "app: m:C\nviewport: not-a-size\n-----\n"
        script = parse_script_text(text)
        assert script.header.viewport == (800, 600)


# ===================================================================
# Separator detection
# ===================================================================


class TestSeparatorDetection:
    """Validate the ----- separator requirement."""

    def test_missing_separator_raises(self) -> None:
        text = 'app: mymod:Cls\nclick "btn"\n'
        with pytest.raises(ValueError, match="missing '-----' separator"):
            parse_script_text(text)

    def test_longer_separator_accepted(self) -> None:
        text = 'app: m:C\n----------\nclick "btn"\n'
        script = parse_script_text(text)
        assert len(script.instructions) == 1

    def test_separator_with_leading_whitespace(self) -> None:
        text = 'app: m:C\n  -----\nclick "btn"\n'
        script = parse_script_text(text)
        assert len(script.instructions) == 1


# ===================================================================
# Instruction parsing
# ===================================================================


class TestInstructionParsing:
    """Validate parsing of every instruction type."""

    def _parse(self, body: str) -> list[Instruction]:
        text = f"app: m:C\n-----\n{body}"
        return parse_script_text(text).instructions

    def test_click(self) -> None:
        instrs = self._parse('click "submit"')
        assert len(instrs) == 1
        assert instrs[0].command == "click"
        assert instrs[0].args == ["submit"]

    def test_type_with_selector_and_text(self) -> None:
        instrs = self._parse('type "input" "hello world"')
        assert instrs[0].command == "type"
        assert instrs[0].args == ["input", "hello world"]

    def test_type_key(self) -> None:
        instrs = self._parse("type_key ctrl+s")
        assert instrs[0].command == "type_key"
        assert instrs[0].args == ["ctrl+s"]

    def test_press(self) -> None:
        instrs = self._parse("press shift")
        assert instrs[0].command == "press"
        assert instrs[0].args == ["shift"]

    def test_release(self) -> None:
        instrs = self._parse("release shift")
        assert instrs[0].command == "release"
        assert instrs[0].args == ["shift"]

    def test_expect(self) -> None:
        instrs = self._parse('expect "Count: 1"')
        assert instrs[0].command == "expect"
        assert instrs[0].args == ["Count: 1"]

    def test_tree_hash(self) -> None:
        instrs = self._parse('tree_hash "initial"')
        assert instrs[0].command == "tree_hash"
        assert instrs[0].args == ["initial"]

    def test_screenshot(self) -> None:
        instrs = self._parse('screenshot "after_click"')
        assert instrs[0].command == "screenshot"
        assert instrs[0].args == ["after_click"]

    def test_assert_text(self) -> None:
        instrs = self._parse('assert_text "label" "Hello"')
        assert instrs[0].command == "assert_text"
        assert instrs[0].args == ["label", "Hello"]

    def test_assert_model(self) -> None:
        instrs = self._parse('assert_model "count=1"')
        assert instrs[0].command == "assert_model"
        assert instrs[0].args == ["count=1"]

    def test_move_selector(self) -> None:
        instrs = self._parse('move "button"')
        assert instrs[0].command == "move"
        assert instrs[0].args == ["button"]

    def test_move_coordinates(self) -> None:
        instrs = self._parse("move 100,200")
        assert instrs[0].command == "move"
        assert instrs[0].args == ["100,200"]

    def test_wait(self) -> None:
        instrs = self._parse("wait 500")
        assert instrs[0].command == "wait"
        assert instrs[0].args == ["500"]


# ===================================================================
# Comments and blank lines in body
# ===================================================================


class TestCommentsAndBlanks:
    """Validate that comments and blank lines are skipped."""

    def _parse(self, body: str) -> list[Instruction]:
        text = f"app: m:C\n-----\n{body}"
        return parse_script_text(text).instructions

    def test_comments_skipped(self) -> None:
        instrs = self._parse('# a comment\nclick "btn"\n# another comment\n')
        assert len(instrs) == 1
        assert instrs[0].command == "click"

    def test_blank_lines_skipped(self) -> None:
        instrs = self._parse('\n\nclick "btn"\n\n')
        assert len(instrs) == 1

    def test_all_comments_yields_empty(self) -> None:
        instrs = self._parse("# just a comment\n# another\n")
        assert instrs == []


# ===================================================================
# Multiple instructions
# ===================================================================


class TestMultipleInstructions:
    """Validate parsing of multi-instruction scripts."""

    def test_sequence(self) -> None:
        body = 'click "btn"\nwait 100\nexpect "done"\n'
        text = f"app: m:C\n-----\n{body}"
        script = parse_script_text(text)
        cmds = [i.command for i in script.instructions]
        assert cmds == ["click", "wait", "expect"]

    def test_line_numbers_are_tracked(self) -> None:
        body = 'click "a"\n# comment\nwait 100\n'
        text = f"app: m:C\n-----\n{body}"
        script = parse_script_text(text)
        # Separator is at line index 1, offset = 1 + 2 = 3
        # First body line (index 0) -> line_number = 3
        # Third body line (index 2, "wait 100") -> line_number = 5
        assert script.instructions[0].line_number == 3
        assert script.instructions[1].line_number == 5


# ===================================================================
# Quoted string parsing
# ===================================================================


class TestQuotedStringParsing:
    """Validate extraction of quoted arguments."""

    def test_single_quoted_arg(self) -> None:
        instr = _parse_instruction_line('click "my button"', 1)
        assert instr is not None
        assert instr.args == ["my button"]

    def test_multiple_quoted_args(self) -> None:
        instr = _parse_instruction_line('assert_text "sel" "value"', 1)
        assert instr is not None
        assert instr.args == ["sel", "value"]

    def test_bare_args_when_no_quotes(self) -> None:
        instr = _parse_instruction_line("wait 500", 1)
        assert instr is not None
        assert instr.args == ["500"]

    def test_command_lowercased(self) -> None:
        instr = _parse_instruction_line('CLICK "btn"', 1)
        assert instr is not None
        assert instr.command == "click"

    def test_no_args(self) -> None:
        instr = _parse_instruction_line("noop", 1)
        assert instr is not None
        assert instr.command == "noop"
        assert instr.args == []

    def test_empty_line_returns_none(self) -> None:
        assert _parse_instruction_line("", 1) is None


# ===================================================================
# Script path metadata
# ===================================================================


class TestScriptMetadata:
    """Validate that the Script carries correct metadata."""

    def test_default_path(self) -> None:
        text = "app: m:C\n-----\n"
        script = parse_script_text(text)
        assert script.path == "<string>"

    def test_custom_path(self) -> None:
        text = "app: m:C\n-----\n"
        script = parse_script_text(text, path="/tmp/test.plushie")
        assert script.path == "/tmp/test.plushie"


# ===================================================================
# _extract_all_text
# ===================================================================


class TestExtractAllText:
    """Validate recursive text extraction from tree dicts."""

    def test_flat_tree(self) -> None:
        tree = {
            "id": "root",
            "props": {"content": "hello"},
            "children": [],
        }
        assert _extract_all_text(tree) == "hello"

    def test_nested_tree(self) -> None:
        tree = {
            "id": "root",
            "props": {"label": "Title"},
            "children": [
                {
                    "id": "child",
                    "props": {"content": "body", "placeholder": "hint"},
                    "children": [],
                }
            ],
        }
        result = _extract_all_text(tree)
        assert "Title" in result
        assert "body" in result
        assert "hint" in result

    def test_empty_tree(self) -> None:
        tree = {"id": "root", "props": {}, "children": []}
        assert _extract_all_text(tree) == ""


# ===================================================================
# ScriptRunner dispatch
# ===================================================================


class TestScriptRunner:
    """Validate instruction dispatch to the fixture mock."""

    def _make_runner(self, *, replay: bool = False) -> tuple[ScriptRunner, MagicMock]:
        fixture = MagicMock()
        fixture.tree = {
            "id": "root",
            "props": {"content": "Hello World"},
            "children": [],
        }
        fixture.model = MagicMock(__repr__=lambda self: "Model(count=1)")
        fixture.text = MagicMock(return_value="Hello")
        fixture.assert_tree_hash = MagicMock()
        fixture.assert_screenshot = MagicMock()
        runner = ScriptRunner(fixture, replay=replay)
        return runner, fixture

    def _run_instruction(self, command: str, args: list[str]) -> tuple[bool, MagicMock]:
        runner, fixture = self._make_runner()
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[Instruction(command=command, args=args, line_number=1)],
        )
        passed = runner.run(script)
        return passed, fixture

    def test_click_dispatches(self) -> None:
        passed, fixture = self._run_instruction("click", ["btn"])
        assert passed
        fixture.click.assert_called_once_with("btn")

    def test_type_two_args(self) -> None:
        passed, fixture = self._run_instruction("type", ["input", "hello"])
        assert passed
        fixture.type_text.assert_called_once_with("input", "hello")

    def test_type_one_arg_delegates_to_type_key(self) -> None:
        passed, fixture = self._run_instruction("type", ["enter"])
        assert passed
        fixture.type_key.assert_called_once_with("enter")

    def test_type_key_dispatches(self) -> None:
        passed, fixture = self._run_instruction("type_key", ["ctrl+s"])
        assert passed
        fixture.type_key.assert_called_once_with("ctrl+s")

    def test_press_dispatches(self) -> None:
        passed, fixture = self._run_instruction("press", ["shift"])
        assert passed
        fixture.press.assert_called_once_with("shift")

    def test_release_dispatches(self) -> None:
        passed, fixture = self._run_instruction("release", ["shift"])
        assert passed
        fixture.release.assert_called_once_with("shift")

    def test_expect_passes_when_text_present(self) -> None:
        passed, _ = self._run_instruction("expect", ["Hello"])
        assert passed

    def test_expect_fails_when_text_missing(self) -> None:
        runner, fixture = self._make_runner()
        fixture.tree = {
            "id": "root",
            "props": {"content": "Goodbye"},
            "children": [],
        }
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[
                Instruction(command="expect", args=["NotThere"], line_number=1)
            ],
        )
        passed = runner.run(script)
        assert not passed
        assert len(runner.errors) == 1

    def test_expect_fails_when_no_tree(self) -> None:
        runner, fixture = self._make_runner()
        fixture.tree = None
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[
                Instruction(command="expect", args=["anything"], line_number=1)
            ],
        )
        passed = runner.run(script)
        assert not passed

    def test_tree_hash_dispatches(self) -> None:
        passed, fixture = self._run_instruction("tree_hash", ["snap"])
        assert passed
        fixture.assert_tree_hash.assert_called_once_with("snap")

    def test_screenshot_dispatches(self) -> None:
        passed, fixture = self._run_instruction("screenshot", ["shot1"])
        assert passed
        fixture.assert_screenshot.assert_called_once_with("shot1")

    def test_assert_text_passes(self) -> None:
        passed, fixture = self._run_instruction("assert_text", ["sel", "Hello"])
        assert passed
        fixture.text.assert_called_once_with("sel")

    def test_assert_text_fails_on_mismatch(self) -> None:
        runner, fixture = self._make_runner()
        fixture.text.return_value = "Wrong"
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[
                Instruction(
                    command="assert_text",
                    args=["sel", "Expected"],
                    line_number=1,
                )
            ],
        )
        passed = runner.run(script)
        assert not passed

    def test_assert_text_fails_when_element_not_found(self) -> None:
        runner, fixture = self._make_runner()
        fixture.text.return_value = None
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[
                Instruction(command="assert_text", args=["sel", "X"], line_number=1)
            ],
        )
        passed = runner.run(script)
        assert not passed

    def test_assert_model_passes(self) -> None:
        passed, _ = self._run_instruction("assert_model", ["count=1"])
        assert passed

    def test_assert_model_fails(self) -> None:
        runner, fixture = self._make_runner()
        fixture.model.__repr__ = lambda self: "Model(count=0)"
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[
                Instruction(command="assert_model", args=["count=99"], line_number=1)
            ],
        )
        passed = runner.run(script)
        assert not passed

    def test_move_coordinates(self) -> None:
        passed, fixture = self._run_instruction("move", ["100,200"])
        assert passed
        fixture.move_to.assert_called_once_with(100.0, 200.0)

    def test_move_selector_is_noop(self) -> None:
        passed, fixture = self._run_instruction("move", ["button"])
        assert passed
        fixture.move_to.assert_not_called()

    def test_wait_no_delay_in_non_replay(self) -> None:
        runner, _fixture = self._make_runner(replay=False)
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[Instruction(command="wait", args=["500"], line_number=1)],
        )
        start = time.monotonic()
        runner.run(script)
        elapsed = time.monotonic() - start
        # Should be nearly instant (no sleep)
        assert elapsed < 0.1

    def test_wait_honours_replay_delay(self) -> None:
        runner, _fixture = self._make_runner(replay=True)
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[Instruction(command="wait", args=["100"], line_number=1)],
        )
        start = time.monotonic()
        runner.run(script)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.08  # at least ~80ms (allowing jitter)

    def test_unknown_instruction_logged_not_error(self, caplog: Any) -> None:
        """Unknown instructions are warned about but don't cause failure."""
        import logging

        runner, _fixture = self._make_runner()
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[Instruction(command="bogus", args=[], line_number=1)],
        )
        with caplog.at_level(logging.WARNING, logger="plushie"):
            passed = runner.run(script)

        assert passed  # unknown instruction is not a failure
        assert "unknown instruction" in caplog.text


# ===================================================================
# Error handling for missing args
# ===================================================================


class TestMissingArgErrors:
    """Validate that instructions with missing args produce errors."""

    def _run_and_expect_failure(self, command: str) -> list[str]:
        fixture = MagicMock()
        fixture.tree = None
        fixture.model = MagicMock(__repr__=lambda self: "M()")
        runner = ScriptRunner(fixture)
        script = Script(
            path="<test>",
            header=ScriptHeader(app="m:C"),
            instructions=[Instruction(command=command, args=[], line_number=1)],
        )
        runner.run(script)
        return runner.errors

    def test_click_no_args(self) -> None:
        errors = self._run_and_expect_failure("click")
        assert len(errors) == 1
        assert "click" in errors[0]

    def test_type_no_args(self) -> None:
        errors = self._run_and_expect_failure("type")
        assert len(errors) == 1

    def test_type_key_no_args(self) -> None:
        errors = self._run_and_expect_failure("type_key")
        assert len(errors) == 1

    def test_press_no_args(self) -> None:
        errors = self._run_and_expect_failure("press")
        assert len(errors) == 1

    def test_release_no_args(self) -> None:
        errors = self._run_and_expect_failure("release")
        assert len(errors) == 1

    def test_expect_no_args(self) -> None:
        errors = self._run_and_expect_failure("expect")
        assert len(errors) == 1

    def test_tree_hash_no_args(self) -> None:
        errors = self._run_and_expect_failure("tree_hash")
        assert len(errors) == 1

    def test_screenshot_no_args(self) -> None:
        errors = self._run_and_expect_failure("screenshot")
        assert len(errors) == 1

    def test_assert_text_no_args(self) -> None:
        errors = self._run_and_expect_failure("assert_text")
        assert len(errors) == 1

    def test_assert_model_no_args(self) -> None:
        errors = self._run_and_expect_failure("assert_model")
        assert len(errors) == 1

    def test_move_no_args(self) -> None:
        errors = self._run_and_expect_failure("move")
        assert len(errors) == 1

    def test_wait_no_args(self) -> None:
        errors = self._run_and_expect_failure("wait")
        assert len(errors) == 1
