#!/usr/bin/env python3
"""
Fix Python 3.13 compatibility by removing type subscripts from NetworkX types.

Instead of adding 'from __future__ import annotations', this simpler approach
removes [str] subscripts from nx.Graph and nx.DiGraph, making them unsubscripted.

Changes:
- Remove 'from __future__ import annotations' lines
- nx.Graph[str] -> nx.Graph
- nx.DiGraph[str] -> nx.DiGraph
"""

import re
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


def fix_file(filepath: str) -> bool:
    """Remove type subscripts from NetworkX types and future import."""
    path = Path(filepath)

    if not path.exists():
        print(f"ERROR: File not found: {filepath}")
        return False

    # Read the file
    with open(path, encoding="utf-8") as f:
        content = f.read()

    original_content = content
    changes_made = []

    # Remove 'from __future__ import annotations' line (and following blank line if present)
    lines = content.split("\n")
    new_lines = []
    skip_next_blank = False

    for _, line in enumerate(lines):
        if line.strip() == "from __future__ import annotations":
            changes_made.append("Removed future import")
            skip_next_blank = True
            continue
        if skip_next_blank and line.strip() == "":
            skip_next_blank = False
            continue
        new_lines.append(line)
        skip_next_blank = False

    content = "\n".join(new_lines)

    # Replace nx.Graph[str] with nx.Graph
    graph_pattern = r'nx\.Graph\[str\]'
    if re.search(graph_pattern, content):
        content = re.sub(graph_pattern, 'nx.Graph', content)
        changes_made.append("Changed nx.Graph[str] -> nx.Graph")

    # Replace nx.DiGraph[str] with nx.DiGraph
    digraph_pattern = r'nx\.DiGraph\[str\]'
    if re.search(digraph_pattern, content):
        content = re.sub(digraph_pattern, 'nx.DiGraph', content)
        changes_made.append("Changed nx.DiGraph[str] -> nx.DiGraph")

    # Write back only if changes were made
    if content != original_content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"FIXED: {filepath}")
        for change in changes_made:
            print(f"  - {change}")
        return True
    else:
        print(f"SKIP: No changes needed: {filepath}")
        return True


def main():
    """Fix all files by removing type subscripts."""
    print("Fixing Python 3.13 compatibility by removing type subscripts...")
    print()

    fixed_count = 0
    for filepath in FILES_TO_FIX:
        if fix_file(filepath):
            fixed_count += 1
        print()

    print(f"Processed {fixed_count}/{len(FILES_TO_FIX)} files")
    print()
    print("Now test with: atg --help")


if __name__ == "__main__":
    main()
