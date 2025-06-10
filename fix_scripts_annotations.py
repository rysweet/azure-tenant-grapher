#!/usr/bin/env python3
"""
Script to fix all type annotation issues across the entire codebase
"""

import os
import re


def fix_all_functions(file_path: str) -> None:
    """Fix missing type annotations in all functions."""
    with open(file_path) as f:
        content = f.read()

    original_content = content

    # Patterns to fix various function signatures
    patterns = [
        # Functions without parameters that need -> None
        (r"(def [a-zA-Z_][a-zA-Z0-9_]*\(\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
        # Functions with parameters that need -> None
        (r"(def [a-zA-Z_][a-zA-Z0-9_]*\([^)]+\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
        # Test methods with self
        (r"(\s+def test_[^(]+\([^)]*self[^)]*\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
        # Test functions
        (r"(\s+def test_[^(]+\([^)]*\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
    ]

    for pattern, replacement in patterns:
        # Only replace if it doesn't already have a return type annotation
        if " -> " not in content:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    # Handle specific function names that return specific types
    specific_replacements = [
        # Functions that should return bool
        (r"(def is_[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)) -> None(\s*:)", r"\1 -> bool\2"),
        # Functions that return strings
        (r"(def get_[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)) -> None(\s*:)", r"\1 -> str\2"),
    ]

    for pattern, replacement in specific_replacements:
        content = re.sub(pattern, replacement, content)

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print(f"✅ Fixed {file_path}")
    else:
        print(f"i  No changes needed for {file_path}")


def main() -> None:
    """Fix all Python files."""
    files_to_fix = [
        "scripts/check_progress.py",
        "scripts/demo_enhanced_features.py",
        "scripts/test_modular_structure.py",
        "scripts/cli.py",
    ]

    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_all_functions(file_path)
        else:
            print(f"❌ File not found: {file_path}")


if __name__ == "__main__":
    main()
