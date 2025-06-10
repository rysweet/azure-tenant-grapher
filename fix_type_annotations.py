#!/usr/bin/env python3
"""
Script to automatically fix missing type annotations in test files
"""

import os
import re


def fix_test_functions(file_path: str) -> None:
    """Fix missing type annotations in test functions."""
    with open(file_path) as f:
        content = f.read()

    # Pattern to match test functions without return type annotations
    # Matches: def test_something(self): or def test_something():
    patterns = [
        # Test methods with self parameter
        (r"(\s+def test_[^(]+\([^)]*self[^)]*\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
        # Test functions without self parameter
        (r"(\s+def test_[^(]+\([^)]*\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
        # Fixture methods
        (r"(\s+def [^(]+\([^)]*self[^)]*\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
        # Regular test functions
        (r"(^def test_[^(]+\([^)]*\))(\s*:)(\s*\n)", r"\1 -> None\2\3"),
    ]

    original_content = content

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    # Check if anything changed
    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print(f"✅ Fixed {file_path}")
    else:
        print(f"i  No changes needed for {file_path}")


def main() -> None:
    """Main function to fix all test files."""
    test_files = [
        "tests/test_resource_processor.py",
        "tests/test_container_manager.py",
        "tests/test_config_manager.py",
        "tests/test_llm_descriptions.py",
        "tests/test_azure_tenant_grapher.py",
    ]

    for test_file in test_files:
        if os.path.exists(test_file):
            fix_test_functions(test_file)
        else:
            print(f"❌ File not found: {test_file}")


if __name__ == "__main__":
    main()
