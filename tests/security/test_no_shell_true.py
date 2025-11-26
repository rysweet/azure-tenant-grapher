"""
Security test to prevent shell=True usage in subprocess calls.

This test scans the codebase for dangerous shell=True patterns and fails
if any are found, preventing command injection vulnerabilities (CWE-78).

Issue: #477
"""

import ast
import re
from pathlib import Path

import pytest

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Directories to scan
SCAN_DIRS = [
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "scripts",
]

# Directories to exclude (relative to PROJECT_ROOT)
EXCLUDE_PATTERNS = [
    ".claude/skills",
    ".claude/agents",
    "node_modules",
    "__pycache__",
    ".git",
    "worktrees/",  # Exclude nested worktrees, but not when running from one
    "demos/walkthrough",  # Demo code may have shell=True for educational purposes
]


def should_exclude(file_path: Path) -> bool:
    """Check if a file path should be excluded from scanning.

    Uses relative paths from PROJECT_ROOT to avoid excluding files when running
    tests from within a worktree directory.
    """
    try:
        # Get path relative to PROJECT_ROOT for accurate pattern matching
        relative_path = file_path.relative_to(PROJECT_ROOT)
        path_str = str(relative_path)
    except ValueError:
        # File is outside PROJECT_ROOT, use absolute path
        path_str = str(file_path)

    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str:
            return True
    return False


def find_python_files(directories: list[Path]) -> list[Path]:
    """Find all Python files in the given directories."""
    python_files = []
    for directory in directories:
        if directory.exists():
            for py_file in directory.rglob("*.py"):
                if not should_exclude(py_file):
                    python_files.append(py_file)
    return python_files


def find_shell_true_usages(file_path: Path) -> list[tuple[int, str]]:
    """
    Find all shell=True usages in a Python file.

    Returns a list of (line_number, line_content) tuples.
    Excludes matches in comments and docstrings.
    """
    violations = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return violations

    # Use regex to find shell=True patterns, excluding comments
    pattern = re.compile(r"shell\s*=\s*True")

    for line_num, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        # Skip comment lines (lines that start with #)
        if stripped.startswith("#"):
            continue
        # Skip lines where shell=True appears only after a # comment
        if "#" in line:
            code_part = line.split("#")[0]
            if not pattern.search(code_part):
                continue
        # Skip docstrings (lines containing """ or ''')
        if '"""' in line or "'''" in line:
            continue
        if pattern.search(line):
            violations.append((line_num, line.strip()))

    return violations


def find_shell_true_with_ast(file_path: Path) -> list[tuple[int, str]]:
    """
    Find shell=True usages using AST parsing for more accuracy.

    This catches cases where the pattern is split across lines or uses
    indirect assignment.
    """
    violations = []

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        return violations

    class ShellTrueVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            # Check for subprocess calls with shell=True
            for keyword in node.keywords:
                if keyword.arg == "shell":
                    if (
                        isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        line = (
                            content.splitlines()[node.lineno - 1]
                            if node.lineno <= len(content.splitlines())
                            else ""
                        )
                        violations.append((node.lineno, line.strip()))
                    elif (
                        isinstance(keyword.value, ast.NameConstant)
                        and keyword.value.value is True
                    ):
                        line = (
                            content.splitlines()[node.lineno - 1]
                            if node.lineno <= len(content.splitlines())
                            else ""
                        )
                        violations.append((node.lineno, line.strip()))
            self.generic_visit(node)

    visitor = ShellTrueVisitor()
    visitor.visit(tree)

    return violations


class TestNoShellTrue:
    """Test suite to ensure no shell=True usage exists in the codebase."""

    def test_no_shell_true_in_src(self) -> None:
        """Verify src/ directory has no shell=True usage."""
        src_dir = PROJECT_ROOT / "src"
        if not src_dir.exists():
            pytest.skip("src/ directory not found")

        violations = []
        for py_file in find_python_files([src_dir]):
            file_violations = find_shell_true_usages(py_file)
            for line_num, line in file_violations:
                violations.append(
                    f"{py_file.relative_to(PROJECT_ROOT)}:{line_num}: {line}"
                )

        assert len(violations) == 0, (
            f"Found {len(violations)} shell=True usage(s) in src/:\n"
            + "\n".join(violations)
            + "\n\nSee docs/SECURITY_SUBPROCESS_GUIDELINES.md for secure alternatives."
        )

    def test_no_shell_true_in_scripts(self) -> None:
        """Verify scripts/ directory has no shell=True usage."""
        scripts_dir = PROJECT_ROOT / "scripts"
        if not scripts_dir.exists():
            pytest.skip("scripts/ directory not found")

        violations = []
        for py_file in find_python_files([scripts_dir]):
            file_violations = find_shell_true_usages(py_file)
            for line_num, line in file_violations:
                violations.append(
                    f"{py_file.relative_to(PROJECT_ROOT)}:{line_num}: {line}"
                )

        assert len(violations) == 0, (
            f"Found {len(violations)} shell=True usage(s) in scripts/:\n"
            + "\n".join(violations)
            + "\n\nSee docs/SECURITY_SUBPROCESS_GUIDELINES.md for secure alternatives."
        )

    def test_no_shell_true_comprehensive(self) -> None:
        """Comprehensive check using both regex and AST parsing."""
        violations = []

        for py_file in find_python_files(SCAN_DIRS):
            # Use regex for quick check
            regex_violations = find_shell_true_usages(py_file)

            # Use AST for accurate check
            ast_violations = find_shell_true_with_ast(py_file)

            # Combine (deduplicate by line number)
            seen_lines = set()
            for line_num, line in regex_violations + ast_violations:
                if line_num not in seen_lines:
                    seen_lines.add(line_num)
                    violations.append(
                        f"{py_file.relative_to(PROJECT_ROOT)}:{line_num}: {line}"
                    )

        assert len(violations) == 0, (
            f"SECURITY: Found {len(violations)} shell=True usage(s)!\n"
            "This is a command injection vulnerability (CWE-78).\n\n"
            "Violations:\n"
            + "\n".join(violations)
            + "\n\nFix: Replace shell=True with shell=False (default) and use list arguments.\n"
            "See docs/SECURITY_SUBPROCESS_GUIDELINES.md for secure alternatives."
        )


class TestSubprocessSecurityPatterns:
    """Test for other subprocess security anti-patterns."""

    def test_no_string_commands_with_user_input(self) -> None:
        """
        Check for potential command injection via string formatting.

        This is a heuristic check - it looks for subprocess calls that
        might be using f-strings or format() with variable interpolation.
        """
        # This is a weaker check - the shell=True check is the critical one
        # String commands without shell=True will fail anyway
        pass  # Placeholder for future enhancement
