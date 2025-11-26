"""Test to ensure no debug print statements in production code.

This test enforces that:
1. No print() statements with DEBUG patterns exist in src/
2. No backup files (.backup) exist in src/
3. The ruff T20 rule is configured to prevent future print statements

This is a quality gate to prevent debug output pollution in production.
"""

import ast
import re
from pathlib import Path

import pytest


class DebugPrintVisitor(ast.NodeVisitor):
    """AST visitor to find print() calls with DEBUG patterns."""

    DEBUG_PATTERNS = [
        r"\[DEBUG\]",
        r"DEBUG:",
        r"DEBUG\s+",
        r"\[DEBUG\]\[",
    ]

    def __init__(self):
        self.debug_prints = []
        self.current_file = None

    def visit_Call(self, node: ast.Call):
        """Visit function calls and check for debug print statements."""
        # Check if it's a print() call
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            # Check the first argument for DEBUG patterns
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(
                    first_arg.value, str
                ):
                    for pattern in self.DEBUG_PATTERNS:
                        if re.search(pattern, first_arg.value):
                            self.debug_prints.append(
                                {
                                    "file": self.current_file,
                                    "line": node.lineno,
                                    "content": first_arg.value[:80],
                                }
                            )
                            break
                elif isinstance(first_arg, ast.JoinedStr):
                    # f-string - check the constant parts
                    for value in first_arg.values:
                        if isinstance(value, ast.Constant) and isinstance(
                            value.value, str
                        ):
                            for pattern in self.DEBUG_PATTERNS:
                                if re.search(pattern, value.value):
                                    self.debug_prints.append(
                                        {
                                            "file": self.current_file,
                                            "line": node.lineno,
                                            "content": value.value[:80],
                                        }
                                    )
                                    break
        self.generic_visit(node)


def get_python_files(src_dir: Path) -> list[Path]:
    """Get all Python files in src/ directory, excluding backup files."""
    return [
        f
        for f in src_dir.rglob("*.py")
        if not f.name.endswith(".backup")
        and "__pycache__" not in str(f)
        and ".pyc" not in str(f)
    ]


@pytest.fixture
def src_directory():
    """Get the src directory path."""
    # Find the src directory relative to tests
    test_dir = Path(__file__).parent
    src_dir = test_dir.parent / "src"
    assert src_dir.exists(), f"src directory not found at {src_dir}"
    return src_dir


class TestNoDebugPrints:
    """Test suite to verify no debug print statements exist."""

    def test_no_debug_print_statements(self, src_directory):
        """Verify no print() statements with DEBUG patterns exist in src/."""
        visitor = DebugPrintVisitor()
        errors = []

        for py_file in get_python_files(src_directory):
            try:
                content = py_file.read_text()
                tree = ast.parse(content, filename=str(py_file))
                visitor.current_file = str(py_file)
                visitor.visit(tree)
            except SyntaxError as e:
                # Skip files with syntax errors (they won't run anyway)
                errors.append(f"Syntax error in {py_file}: {e}")

        if visitor.debug_prints:
            debug_list = "\n".join(
                f"  - {d['file']}:{d['line']}: {d['content']}"
                for d in visitor.debug_prints
            )
            pytest.fail(
                f"Found {len(visitor.debug_prints)} debug print statements:\n{debug_list}"
            )

    def test_no_backup_files_in_src(self, src_directory):
        """Verify no .backup files exist in src/."""
        backup_files = list(src_directory.rglob("*.backup"))
        if backup_files:
            file_list = "\n".join(f"  - {f}" for f in backup_files)
            pytest.fail(f"Found backup files in src/:\n{file_list}")

    def test_ruff_t20_configured(self):
        """Verify ruff T20 rule is configured in pyproject.toml."""
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml not found"

        content = pyproject.read_text()
        # Check if T20 (flake8-print) is in the ruff select list
        assert (
            '"T20"' in content or "'T20'" in content
        ), "ruff T20 rule (flake8-print) is not configured in pyproject.toml"


class TestPrintStatementPattern:
    """Test the patterns used to detect debug prints."""

    @pytest.mark.parametrize(
        "debug_string",
        [
            "[DEBUG][CLI] Entering function",
            "[DEBUG] Something",
            "DEBUG: test message",
            "[DEBUG][RP] Processing",
            "[DEBUG][Neo4jEnv] os.environ",
        ],
    )
    def test_debug_patterns_detected(self, debug_string):
        """Verify debug patterns are correctly detected."""
        for pattern in DebugPrintVisitor.DEBUG_PATTERNS:
            if re.search(pattern, debug_string):
                return  # Pattern matched, test passes
        pytest.fail(f"Debug string not detected: {debug_string}")
