#!/usr/bin/env python3
"""Example workflow for version tracking with hash validation.

This example demonstrates:
1. Calculating construction hash
2. Validating hash against stored value
3. Detecting version mismatches
4. Updating version file when code changes

Usage:
    python3 examples/version_tracking_workflow.py
"""

import json
from datetime import datetime
from pathlib import Path

from src.version_tracking import (
    VersionDetector,
    calculate_construction_hash,
    validate_hash,
)


def example_calculate_hash():
    """Example: Calculate current construction hash."""
    print("=" * 60)
    print("Example 1: Calculate Construction Hash")
    print("=" * 60)

    # Calculate hash
    hash_value = calculate_construction_hash()

    print(f"Current construction hash: {hash_value}")
    print(f"Hash length: {len(hash_value)} characters")
    print()

    return hash_value


def example_validate_hash(stored_hash: str):
    """Example: Validate stored hash against current code."""
    print("=" * 60)
    print("Example 2: Validate Hash")
    print("=" * 60)

    # Validate
    result = validate_hash(stored_hash)

    print("Hash validation result:")
    print(f"  Matches: {result.matches}")
    print(f"  Stored hash:  {result.stored_hash}")
    print(f"  Current hash: {result.current_hash}")

    if not result.matches:
        print(f"\n  Changed files ({len(result.changed_files)}):")
        for file in result.changed_files[:10]:  # Show first 10
            print(f"    - {file}")
        if len(result.changed_files) > 10:
            print(f"    ... and {len(result.changed_files) - 10} more")
    print()

    return result


def example_read_version_file():
    """Example: Read current version file."""
    print("=" * 60)
    print("Example 3: Read Version File")
    print("=" * 60)

    # Read version file
    version_file = Path(".atg_graph_version")

    if not version_file.exists():
        print("Version file not found!")
        return None

    data = json.loads(version_file.read_text())

    print("Current version data:")
    print(f"  Version: {data.get('version')}")
    print(f"  Last modified: {data.get('last_modified')}")
    print(f"  Description: {data.get('description')}")
    print(f"  Hash: {data.get('construction_hash', 'N/A')[:16]}...")
    print()

    return data


def example_update_version_file(new_version: str, description: str):
    """Example: Update version file with new hash.

    Args:
        new_version: New version string (e.g., "1.0.1")
        description: Description of changes
    """
    print("=" * 60)
    print("Example 4: Update Version File")
    print("=" * 60)

    # Calculate new hash
    new_hash = calculate_construction_hash()

    # Create updated data
    data = {
        "version": new_version,
        "last_modified": datetime.now().isoformat() + "Z",
        "description": description,
        "construction_hash": new_hash,
        "tracked_paths": [
            "src/relationship_rules/",
            "src/services/azure_discovery_service.py",
            "src/resource_processor.py",
            "src/azure_tenant_grapher.py",
        ],
    }

    print("New version data:")
    print(f"  Version: {data['version']}")
    print(f"  Last modified: {data['last_modified']}")
    print(f"  Description: {data['description']}")
    print(f"  Hash: {data['construction_hash'][:16]}...")
    print()

    # NOTE: This example does NOT write the file
    # In real usage: Path('.atg_graph_version').write_text(json.dumps(data, indent=2))
    print("(File not written - this is a read-only example)")
    print()

    return data


def example_detect_mismatch():
    """Example: Detect version/hash mismatch with detector."""
    print("=" * 60)
    print("Example 5: Detect Mismatch (Detector)")
    print("=" * 60)

    # Initialize detector
    detector = VersionDetector()

    # Read semaphore data
    semaphore_data = detector.read_semaphore_data()

    if semaphore_data:
        print("Semaphore file found:")
        print(f"  Version: {semaphore_data.get('version')}")
        print(f"  Hash: {semaphore_data.get('construction_hash', 'N/A')[:16]}...")
    else:
        print("Semaphore file not found or empty")

    # Validate hash (without metadata service)
    hash_mismatch = detector._validate_construction_hash()

    if hash_mismatch:
        print("\n❌ Hash mismatch detected!")
        print(f"  Reason: {hash_mismatch['reason']}")
        print(f"  Type: {hash_mismatch['type']}")
        print(f"  Changed files: {len(hash_mismatch.get('changed_files', []))}")
    else:
        print("\n✅ Hash matches current code")

    print()


def example_complete_workflow():
    """Example: Complete workflow for updating version."""
    print("=" * 60)
    print("COMPLETE WORKFLOW EXAMPLE")
    print("=" * 60)
    print()

    # Step 1: Read current version
    print("Step 1: Read current version file")
    current_data = example_read_version_file()

    if not current_data:
        print("Skipping workflow - no version file found")
        return

    current_version = current_data.get("version", "0.0.0")
    stored_hash = current_data.get("construction_hash")

    # Step 2: Calculate current hash
    print("Step 2: Calculate current hash")
    current_hash = example_calculate_hash()

    # Step 3: Validate hash
    print("Step 3: Validate hash")
    result = example_validate_hash(stored_hash)

    # Step 4: Determine if update needed
    if result.matches:
        print("✅ No update needed - hash matches")
        print()
    else:
        print("❌ Update needed - hash mismatch detected")
        print()

        # Parse current version
        parts = current_version.split(".")
        if len(parts) == 3:
            major, minor, patch = parts
            # Bump patch version
            new_version = f"{major}.{minor}.{int(patch) + 1}"
        else:
            new_version = "1.0.1"

        print(f"Suggested new version: {new_version}")
        print()

        # Show what would be updated
        example_update_version_file(
            new_version=new_version,
            description="Example update with code changes",
        )

    print("Workflow complete!")
    print()


def main():
    """Run all examples."""
    print()
    print("*" * 60)
    print("VERSION TRACKING WORKFLOW EXAMPLES")
    print("*" * 60)
    print()

    try:
        # Run individual examples
        example_read_version_file()
        example_calculate_hash()
        example_validate_hash(calculate_construction_hash())
        example_detect_mismatch()

        # Run complete workflow
        example_complete_workflow()

        print("*" * 60)
        print("All examples completed successfully!")
        print("*" * 60)
        print()

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
