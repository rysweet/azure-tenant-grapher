#!/usr/bin/env python3
"""
Fix Python 3.13 type annotation compatibility by adding 'from __future__ import annotations'
to files that use subscripted generics like nx.Graph[str].

This fixes the TypeError: type 'Graph' is not subscriptable error in Python 3.13.
"""

from pathlib import Path

FILES_TO_FIX = [
    "src/architecture_based_replicator.py",
    "src/services/graph_embedding_generator.py",
    "src/services/graph_embedding_sampler.py",
    "src/services/graph_export_service.py",
    "src/services/scale_down/exporters/base_exporter.py",
    "src/services/scale_down/exporters/iac_exporter.py",
    "src/services/scale_down/exporters/json_exporter.py",
    "src/services/scale_down/exporters/neo4j_exporter.py",
    "src/services/scale_down/exporters/yaml_exporter.py",
    "src/services/scale_down/graph_extractor.py",
    "src/services/scale_down/graph_operations.py",
    "src/services/scale_down/orchestrator.py",
    "src/services/scale_down/sampling/base_sampler.py",
    "src/services/scale_down/sampling/forest_fire_sampler.py",
    "src/services/scale_down/sampling/mhrw_sampler.py",
    "src/services/scale_down/sampling/pattern_sampler.py",
    "src/services/scale_down/sampling/random_walk_sampler.py",
]

FUTURE_IMPORT = "from __future__ import annotations\n"


def fix_file(filepath: str) -> bool:
    """Add 'from __future__ import annotations' to the top of a Python file if not present."""
    path = Path(filepath)

    if not path.exists():
        print(f"❌ File not found: {filepath}")
        return False

    # Read the file
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Check if already has the import
    if "from __future__ import annotations" in content:
        print(f"✓ Already fixed: {filepath}")
        return True

    # Find where to insert (after shebang and docstring, before other imports)
    lines = content.split("\n")
    insert_pos = 0

    # Skip shebang
    if lines and lines[0].startswith("#!"):
        insert_pos = 1

    # Skip module docstring
    in_docstring = False
    docstring_char = None
    for i in range(insert_pos, len(lines)):
        line = lines[i].strip()

        # Check for docstring start
        if not in_docstring and (line.startswith('"""') or line.startswith("'''")):
            docstring_char = line[:3]
            in_docstring = True
            # Check if docstring ends on same line
            if line.count(docstring_char) >= 2:
                insert_pos = i + 1
                break
        elif in_docstring and docstring_char in line:
            insert_pos = i + 1
            break
        elif not in_docstring and line and not line.startswith("#"):
            # Found first non-comment, non-docstring line
            insert_pos = i
            break

    # Insert the future import
    lines.insert(insert_pos, FUTURE_IMPORT)

    # Write back
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ Fixed: {filepath}")
    return True


def main():
    """Fix all files that need the future import."""
    print("🔧 Fixing Python 3.13 type annotation compatibility...\n")

    fixed_count = 0
    for filepath in FILES_TO_FIX:
        if fix_file(filepath):
            fixed_count += 1

    print(f"\n✨ Fixed {fixed_count}/{len(FILES_TO_FIX)} files")
    print("\n🎯 Now try running: atg --version")


if __name__ == "__main__":
    main()
