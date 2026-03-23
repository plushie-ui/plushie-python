#!/usr/bin/env python3
"""Verify that doc test markers and test functions stay in sync.

Scans docs/*.md and README.md for <!-- test: name1, name2 --> HTML comment
markers. Cross-references against def test_* and class Test* definitions in
tests/docs/test_*.py files.

Exits 0 if everything lines up, 1 if orphans exist in either direction.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories / files to scan for markers
DOC_DIRS = [PROJECT_ROOT / "docs"]
DOC_FILES = [PROJECT_ROOT / "README.md"]

# Directory containing doc test files
TEST_DIR = PROJECT_ROOT / "tests" / "docs"

# Matches <!-- test: ... --> or <!-- test: ... -- (comment continues) -->
MARKER_RE = re.compile(r"<!--\s*test:\s*(.+?)(?:\s*-->|\s*--\s)", re.DOTALL)

# Strip parenthesized comments like "(see test_commands_doc.py)"
PAREN_RE = re.compile(r"\([^)]*\)")


def _parse_marker_names(raw: str) -> list[str]:
    """Extract test names from the raw content of a marker."""
    cleaned = PAREN_RE.sub("", raw)
    names = []
    for part in re.split(r"[,\s]+", cleaned.strip()):
        part = part.strip()
        if not part:
            continue
        if part.startswith("test_") or part.startswith("Test"):
            names.append(part)
    return names


def extract_marker_names(path: Path) -> set[str]:
    """Return all test names referenced by markers in a file."""
    text = path.read_text()
    names: set[str] = set()
    for match in MARKER_RE.finditer(text):
        names.update(_parse_marker_names(match.group(1)))
    return names


def collect_test_info(
    test_dir: Path,
) -> tuple[set[str], dict[str, set[str]], dict[str, str]]:
    """Collect test definitions from test files.

    Returns:
        - top_level_funcs: set of bare test_* function names (not in classes)
        - class_methods: dict mapping class name -> set of method names
        - name_to_file: mapping of any name -> relative file path
    """
    top_level_funcs: set[str] = set()
    class_methods: dict[str, set[str]] = {}
    name_to_file: dict[str, str] = {}

    if not test_dir.is_dir():
        return top_level_funcs, class_methods, name_to_file

    for path in sorted(test_dir.glob("test_*.py")):
        rel = str(path.relative_to(PROJECT_ROOT))
        tree = ast.parse(path.read_text(), filename=str(path))

        for child in ast.iter_child_nodes(tree):
            if isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                top_level_funcs.add(child.name)
                name_to_file[child.name] = rel
            elif isinstance(child, ast.ClassDef) and child.name.startswith("Test"):
                methods: set[str] = set()
                name_to_file[child.name] = rel
                for method in ast.iter_child_nodes(child):
                    if (
                        isinstance(method, ast.FunctionDef)
                        and method.name.startswith("test_")
                    ):
                        methods.add(method.name)
                        name_to_file.setdefault(method.name, rel)
                class_methods[child.name] = methods

    return top_level_funcs, class_methods, name_to_file


def main() -> int:
    # Gather marker names from docs
    marker_names: set[str] = set()
    marker_sources: dict[str, list[str]] = {}

    doc_paths: list[Path] = []
    for d in DOC_DIRS:
        if d.is_dir():
            doc_paths.extend(sorted(d.glob("*.md")))
    for f in DOC_FILES:
        if f.is_file():
            doc_paths.append(f)

    for path in doc_paths:
        names = extract_marker_names(path)
        marker_names |= names
        for name in names:
            marker_sources.setdefault(name, []).append(
                str(path.relative_to(PROJECT_ROOT))
            )

    # Gather test definitions
    top_level_funcs, class_methods, name_to_file = collect_test_info(TEST_DIR)

    # Build lookup: bare method name -> set of classes containing it
    method_to_classes: dict[str, set[str]] = {}
    for cls, methods in class_methods.items():
        for m in methods:
            method_to_classes.setdefault(m, set()).add(cls)

    # All known names (for existence check)
    all_known: set[str] = set(top_level_funcs)
    all_known.update(class_methods.keys())
    for methods in class_methods.values():
        all_known.update(methods)
    for cls, methods in class_methods.items():
        for m in methods:
            all_known.add(f"{cls}.{m}")

    # 1) Markers pointing to tests that don't exist
    missing_tests: set[str] = set()
    for name in marker_names:
        if name in all_known:
            continue
        missing_tests.add(name)

    # 2) Tests not referenced by any marker
    # A bare test function is covered if its name is in marker_names
    # A class method is covered if any of these hold:
    #   - The class name is in marker_names
    #   - The bare method name is in marker_names
    #   - ClassName.method_name is in marker_names
    unreferenced: list[str] = []

    for func in sorted(top_level_funcs):
        if func not in marker_names:
            unreferenced.append(func)

    for cls in sorted(class_methods):
        for method in sorted(class_methods[cls]):
            qualified = f"{cls}.{method}"
            if (
                cls not in marker_names
                and method not in marker_names
                and qualified not in marker_names
            ):
                unreferenced.append(qualified)

    # Report
    errors = False

    if missing_tests:
        errors = True
        print("Markers referencing tests that don't exist:")
        for name in sorted(missing_tests):
            sources = ", ".join(marker_sources.get(name, ["?"]))
            print(f"  {name}  (in {sources})")
        print()

    if unreferenced:
        errors = True
        print("Tests in tests/docs/ not referenced by any marker:")
        for name in sorted(unreferenced):
            base = name.split(".")[-1] if "." in name else name
            source = name_to_file.get(base, "?")
            print(f"  {name}  (in {source})")
        print()

    if errors:
        print("FAIL: doc test markers and test functions are out of sync")
        return 1

    print("OK: all doc test markers and test functions are in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
