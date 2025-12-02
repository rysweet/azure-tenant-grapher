#!/usr/bin/env python3
"""Auto-detect missing Azure→Terraform type mappings.

Usage:
    python scripts/detect_missing_type_mappings.py

This tool compares resource types in the source tenant (from registry)
against the type mappings in smart_import_generator.py and reports gaps.
"""

import json
import re
import sys
from pathlib import Path


def load_source_types(registry_path: str) -> dict:
    """Load resource types from deployment registry."""
    with open(registry_path) as f:
        data = json.load(f)
        if 'deployments' not in data or not data['deployments']:
            return {}
        return data['deployments'][0].get('resources', {})


def load_current_mappings(generator_path: str) -> set:
    """Load current type mappings from smart_import_generator.py."""
    with open(generator_path) as f:
        content = f.read()

    # Extract the dictionary
    dict_match = re.search(
        r'AZURE_TO_TERRAFORM_TYPE.*?= \{(.*?)\n\}',
        content,
        re.DOTALL
    )

    if not dict_match:
        return set()

    dict_content = dict_match.group(1)

    # Extract Azure types (keys in the dictionary)
    mappings = set()
    for line in dict_content.split('\n'):
        if '":' in line and not line.strip().startswith('#'):
            # Extract the Azure type from "Azure.Type": "terraform_type"
            match = re.search(r'"([^"]+)":\s*"', line)
            if match:
                mappings.add(match.group(1).lower())  # Lowercase for comparison

    return mappings


def main():
    """Main function."""
    # Paths
    registry_path = '.deployments/registry.json'
    generator_path = 'src/iac/emitters/smart_import_generator.py'

    # Load data
    print("Loading source types from registry...")
    source_types = load_source_types(registry_path)

    print(f"Loading current mappings from {generator_path}...")
    current_mappings = load_current_mappings(generator_path)

    # Find missing types (case-insensitive comparison)
    missing = []
    for azure_type, count in source_types.items():
        if azure_type.lower() not in current_mappings:
            missing.append((azure_type, count))

    # Sort by count (descending)
    missing.sort(key=lambda x: x[1], reverse=True)

    # Report
    print("\n" + "="*70)
    print("MISSING TYPE MAPPING REPORT")
    print("="*70)
    print(f"\nSource types: {len(source_types)}")
    print(f"Current mappings: {len(current_mappings)}")
    print(f"Missing mappings: {len(missing)}")
    print(f"\nCoverage: {len(current_mappings)}/{len(source_types)} = {len(current_mappings)/max(1,len(source_types))*100:.1f}%")

    if missing:
        print("\n" + "-"*70)
        print("MISSING TYPES (by resource count):")
        print("-"*70)

        total_missing_resources = 0
        for azure_type, count in missing:
            print(f"  {azure_type}: {count} resources")
            total_missing_resources += count

        print(f"\nTotal resources in missing types: {total_missing_resources}")

        # High-priority recommendations
        high_priority = [(t, c) for t, c in missing if c >= 10]
        if high_priority:
            print("\n" + "-"*70)
            print("HIGH PRIORITY (>=10 resources):")
            print("-"*70)
            for azure_type, count in high_priority:
                print(f"  {azure_type}: {count}")
    else:
        print("\n✅ All source types are mapped!")

    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
