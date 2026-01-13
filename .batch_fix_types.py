#!/usr/bin/env python3
"""Batch fix common type errors across codebase

Applies proven patterns from Phases 1-2 to remaining files.
"""

import re
from pathlib import Path
from typing import List, Tuple


def fix_optional_access(content: str) -> Tuple[str, int]:
    """Fix optional attribute access patterns"""
    fixes = 0

    # Pattern: if obj: obj.method() -> if obj is not None: obj.method()
    pattern = r"\bif\s+([a-zA-Z_][a-zA-Z0-9_.]*):\s*\1\."
    matches = list(re.finditer(pattern, content))
    for match in reversed(matches):
        var_name = match.group(1)
        old = f"if {var_name}:"
        new = f"if {var_name} is not None:"
        content = (
            content[: match.start()]
            + content[match.start() : match.end()].replace(old, new)
            + content[match.end() :]
        )
        fixes += 1

    return content, fixes


def fix_print_fstring_literal(content: str) -> Tuple[str, int]:
    """Fix print(f"...") LiteralString issues"""
    fixes = 0

    # Add str() wrapper around f-strings in print()
    pattern = r'print\((f["\'][^"\']*["\'])\)'

    def replacer(match):
        nonlocal fixes
        fstring = match.group(1)
        fixes += 1
        return f"print(str({fstring}))"

    content = re.sub(pattern, replacer, content)
    return content, fixes


def fix_logger_fstring(content: str) -> Tuple[str, int]:
    """Fix logger.info/debug/error(f"...") LiteralString issues"""
    fixes = 0

    # Add str() wrapper around f-strings in logger calls
    pattern = r'(logger\.(info|debug|error|warning|critical))\((f["\'][^"\']*["\'])\)'

    def replacer(match):
        nonlocal fixes
        logger_call = match.group(1)
        fstring = match.group(3)
        fixes += 1
        return f"{logger_call}(str({fstring}))"

    content = re.sub(pattern, replacer, content)
    return content, fixes


def fix_graph_type_hints(content: str) -> Tuple[str, int]:
    """Fix Graph[...] -> Graph type hints"""
    fixes = 0

    # Remove generic parameters from networkx.Graph
    patterns = [
        (r"nx\.Graph\[Any\]", "nx.Graph"),
        (r"nx\.DiGraph\[Any\]", "nx.DiGraph"),
        (r"networkx\.Graph\[Any\]", "networkx.Graph"),
        (r"networkx\.DiGraph\[Any\]", "networkx.DiGraph"),
        (r": Graph\[Any\]", ": Graph"),
        (r": DiGraph\[Any\]", ": DiGraph"),
    ]

    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes += len(re.findall(pattern, content))
            content = new_content

    return content, fixes


def add_type_ignore_for_private(content: str) -> Tuple[str, int]:
    """Add # type: ignore[reportPrivateUsage] for necessary private access"""
    fixes = 0

    # Find lines accessing ._xyz that don't already have type: ignore
    pattern = r"^(\s+)([^#\n]*\._[a-zA-Z_][a-zA-Z0-9_]*[^#\n]*)$"

    lines = content.split("\n")
    for i, line in enumerate(lines):
        if re.match(pattern, line) and "# type: ignore" not in line:
            lines[i] = line.rstrip() + "  # type: ignore[reportPrivateUsage]"
            fixes += 1

    content = "\n".join(lines)
    return content, fixes


def process_file(filepath: Path) -> Tuple[int, List[str]]:
    """Process a single Python file with all fixes"""
    try:
        content = filepath.read_text()
        original = content
        total_fixes = 0
        changes = []

        # Apply all fix patterns
        content, n = fix_optional_access(content)
        if n > 0:
            changes.append(f"Optional access: {n}")
            total_fixes += n

        content, n = fix_print_fstring_literal(content)
        if n > 0:
            changes.append(f"Print f-strings: {n}")
            total_fixes += n

        content, n = fix_logger_fstring(content)
        if n > 0:
            changes.append(f"Logger f-strings: {n}")
            total_fixes += n

        content, n = fix_graph_type_hints(content)
        if n > 0:
            changes.append(f"Graph types: {n}")
            total_fixes += n

        # Only write if changes were made
        if content != original:
            filepath.write_text(content)

        return total_fixes, changes

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0, []


def main():
    """Find and fix Python files in main source directories"""
    root = Path("/home/azureuser/src/azure-tenant-grapher")

    # Target main source directories
    source_dirs = [
        root / "src",
        root / "scripts",
    ]

    total_files = 0
    total_fixes = 0

    for source_dir in source_dirs:
        if not source_dir.exists():
            continue

        print(f"\nProcessing {source_dir}...")

        for filepath in source_dir.rglob("*.py"):
            # Skip test files and __pycache__
            if "__pycache__" in str(filepath) or "test_" in filepath.name:
                continue

            fixes, changes = process_file(filepath)
            if fixes > 0:
                total_files += 1
                total_fixes += fixes
                print(f"  {filepath.name}: {fixes} fixes ({', '.join(changes)})")

    print(f"\n{'=' * 60}")
    print(f"Total: {total_fixes} fixes across {total_files} files")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
