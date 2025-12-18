#!/usr/bin/env python3
"""Fix final broken links - third pass. These are all valid files that just need proper markdown syntax."""

import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def fix_file(file_path: Path, replacements: list[tuple[str, str]]) -> bool:
    """Apply replacements to a file."""
    if not file_path.exists():
        return False

    content = file_path.read_text()
    modified = False

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            modified = True

    if modified:
        file_path.write_text(content)
        return True
    return False


def main():
    """Fix all remaining broken links."""
    fixes = [
        # architecture/scan-source-node-relationships.md
        (
            BASE_DIR / "docs/architecture/scan-source-node-relationships.md",
            [
                ("../../src/iac/ (IaC generation source)", "../../src/iac/README.md (IaC generation source)"),
            ]
        ),
        # demo/commands/build.md
        (
            BASE_DIR / "docs/demo/commands/build.md",
            [
                ("[Commands Index](see `atg build --help`)", "Commands Index (see `atg build --help`)"),
            ]
        ),
        # demo/overview.md
        (
            BASE_DIR / "docs/demo/overview.md",
            [
                ("- [](commands/ (see individual command files))", "- Commands (see individual command files in commands/ directory)"),
            ]
        ),
        # design/DESIGN_VNET_OVERLAP_DETECTION.md
        (
            BASE_DIR / "docs/design/DESIGN_VNET_OVERLAP_DETECTION.md",
            [
                ("[](VNET overlap detection (see design documentation))", "VNET overlap detection (see design documentation)"),
            ]
        ),
        # diagrams/DIAGRAM_MANIFEST.md - remove references to non-existent PNG
        (
            BASE_DIR / "docs/diagrams/DIAGRAM_MANIFEST.md",
            [
                ("(dual-graph-architecture.png)", "(see ../DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt for ASCII diagram)"),
            ]
        ),
        # diagrams/README.md
        (
            BASE_DIR / "docs/diagrams/README.md",
            [
                ("(dual-graph-architecture.png)", "(see ../DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt for ASCII diagram)"),
            ]
        ),
        # guides/AUTONOMOUS_DEPLOYMENT_FAQ.md
        (
            BASE_DIR / "docs/guides/AUTONOMOUS_DEPLOYMENT_FAQ.md",
            [
                ("(this document)", "(#troubleshooting)"),
            ]
        ),
    ]

    fixed_count = 0
    for file_path, replacements in fixes:
        if fix_file(file_path, replacements):
            fixed_count += 1
            print(f"✓ Fixed {file_path.name}")

    print(f"\n✅ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
