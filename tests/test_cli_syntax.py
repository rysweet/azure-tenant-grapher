"""Test that CLI modules have valid Python syntax."""

import ast
import sys
from pathlib import Path

import pytest


def test_cli_commands_syntax():
    """Test that cli_commands.py has valid Python syntax."""
    cli_commands_path = Path(__file__).parent.parent / "src" / "cli_commands.py"

    # Read the file content
    with open(cli_commands_path, encoding="utf-8") as f:
        source_code = f.read()

    # Try to parse it as valid Python
    try:
        ast.parse(source_code)
    except SyntaxError as e:
        pytest.fail(f"Syntax error in cli_commands.py at line {e.lineno}: {e.msg}")


def test_cli_script_syntax():
    """Test that cli.py has valid Python syntax."""
    cli_script_path = Path(__file__).parent.parent / "scripts" / "cli.py"

    # Read the file content
    with open(cli_script_path, encoding="utf-8") as f:
        source_code = f.read()

    # Try to parse it as valid Python
    try:
        ast.parse(source_code)
    except SyntaxError as e:
        pytest.fail(f"Syntax error in cli.py at line {e.lineno}: {e.msg}")


def test_can_import_cli():
    """Test that we can import the CLI without errors."""
    try:
        # Add parent directory to path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        # Try to import cli_commands
        # Try to import the main CLI
        from scripts.cli import cli

        import src.cli_commands

    except SyntaxError as e:
        pytest.fail(f"Cannot import CLI due to syntax error: {e}")
    except ImportError as e:
        # ImportError is okay if dependencies are missing, we're just checking syntax
        if "invalid syntax" in str(e):
            pytest.fail(f"Cannot import CLI due to syntax error: {e}")
        # Otherwise pass - we're only testing syntax, not dependencies
        pass
    finally:
        # Remove from path
        if str(Path(__file__).parent.parent) in sys.path:
            sys.path.remove(str(Path(__file__).parent.parent))


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
