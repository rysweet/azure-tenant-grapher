#!/usr/bin/env python3
"""
Fix broken markdown link syntax where descriptive text was put inside link parentheses.
These files all exist - just need to fix the markdown syntax.
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def fix_broken_syntax():
    """Fix all broken markdown link syntax."""

    fixes = {
        # All these files DO exist - just fix the markdown syntax
        "docs/demo/commands/build.md": [
            (r"\(see `atg build --help`\)", "")  # Remove - not a link
        ],
        "docs/demo/overview.md": [
            (r"- \[\]\(commands/ \(see individual command files\)\)", "- See individual command files in commands/ directory")
        ],
        "docs/design/DESIGN_VNET_OVERLAP_DETECTION.md": [
            (r"\[\]\(VNET overlap detection \(see design documentation\)\)", "VNET overlap detection (see design documentation)")
        ],
        "docs/diagrams/DIAGRAM_MANIFEST.md": [
            (r"\(see \.\./DUAL_GRAPH_ARCHITECTURE_DIAGRAM\.txt for ASCII diagram\)", "")  # Already referenced in text
        ],
        "docs/diagrams/README.md": [
            (r"\(see \.\./DUAL_GRAPH_ARCHITECTURE_DIAGRAM\.txt for ASCII diagram\)", "")  # Already referenced in text
        ],
    }

    for file_path, replacements in fixes.items():
        full_path = BASE_DIR / file_path
        if not full_path.exists():
            continue

        content = full_path.read_text()
        modified = False

        for pattern, replacement in replacements:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                modified = True

        if modified:
            full_path.write_text(content)
            print(f"✓ Fixed {file_path}")


def main():
    fix_broken_syntax()
    print("\n✅ Fixed markdown syntax issues")


if __name__ == "__main__":
    main()
