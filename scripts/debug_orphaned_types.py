#!/usr/bin/env python3
"""
Debug script to understand why no orphaned instances are being found.

This script will:
1. Show all source resource types
2. Show all pattern-matched resource types
3. Compute orphaned types (source - patterns)
4. Query Neo4j directly to check if orphaned types exist
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.architecture_based_replicator import ArchitecturePatternReplicator
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")

def main():
    print("=" * 80)
    print("ORPHANED TYPE DEBUGGING")
    print("=" * 80)
    print()

    # Initialize replicator
    print("🔧 Initializing replicator...")
    replicator = ArchitecturePatternReplicator(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD
    )

    # Analyze source tenant
    print("🔍 Analyzing source tenant...")
    replicator.analyze_source_tenant(
        use_configuration_coherence=True,
        coherence_threshold=0.5
    )
    print()

    # Get source types
    source_types = set(replicator.source_resource_type_counts.keys())
    print(f"📊 Source Resource Types: {len(source_types)}")
    print(f"   First 20: {sorted(list(source_types))[:20]}")
    print()

    # Get pattern types
    pattern_types = set()
    for pattern_info in replicator.detected_patterns.values():
        pattern_types.update(pattern_info["matched_resources"])

    print(f"📐 Pattern-Matched Types: {len(pattern_types)}")
    print(f"   First 20: {sorted(list(pattern_types))[:20]}")
    print()

    # Compute orphaned types
    orphaned_types = source_types - pattern_types
    print(f"🔍 Orphaned Types (source - patterns): {len(orphaned_types)}")
    if orphaned_types:
        print(f"   First 20: {sorted(list(orphaned_types))[:20]}")
        print(f"   All orphaned: {sorted(list(orphaned_types))}")
    else:
        print("   ✅ No orphaned types - all source types are covered by patterns!")
    print()

    # Check if source_types == pattern_types
    if source_types == pattern_types:
        print("💡 INSIGHT: source_types exactly equals pattern_types!")
        print("   This means ALL resource types are included in detected patterns.")
        print("   There are NO orphaned types to find.")
        print()
        print("   This is actually GOOD - it means:")
        print("   - Pattern detection is comprehensive")
        print("   - All resource types are architecturally connected")
        print("   - rare_boost_factor has nothing to upweight")
        print()
        return 0

    # Query Neo4j directly for orphaned types
    if not orphaned_types:
        print("   No orphaned types to query")
        return 0

    print("🔬 Querying Neo4j for orphaned type instances...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Query for ResourceGroups containing orphaned types
            query = """
            MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
            WHERE r.type IN $orphaned_types
            RETURN rg.id as rg_id, r.type as resource_type, count(r) as count
            ORDER BY count DESC
            LIMIT 20
            """

            result = session.run(query, orphaned_types=list(orphaned_types))
            records = list(result)

            if records:
                print(f"   ✅ Found {len(records)} ResourceGroups with orphaned types:")
                for record in records:
                    print(f"      RG: {record['rg_id']}, Type: {record['resource_type']}, Count: {record['count']}")
            else:
                print("   ❌ No ResourceGroups found with orphaned types!")
                print()
                print("   This means:")
                print("   - Orphaned types exist in source_resource_type_counts")
                print("   - But they don't exist in Neo4j ResourceGroups")
                print("   - Possible reasons:")
                print("     1. Orphaned types are standalone (not in ResourceGroups)")
                print("     2. Orphaned types are non-Azure resources (subscriptions, regions, etc.)")
                print("     3. Data mismatch between source analysis and Neo4j")

            print()

            # Query for standalone orphaned resources
            query_standalone = """
            MATCH (r:Resource:Original)
            WHERE r.type IN $orphaned_types
            AND NOT (r)<-[:CONTAINS]-(:ResourceGroup)
            RETURN r.type as resource_type, count(r) as count
            ORDER BY count DESC
            LIMIT 20
            """

            result_standalone = session.run(query_standalone, orphaned_types=list(orphaned_types))
            records_standalone = list(result_standalone)

            if records_standalone:
                print(f"   🔍 Found {len(records_standalone)} standalone orphaned resource types:")
                for record in records_standalone:
                    print(f"      Type: {record['resource_type']}, Count: {record['count']}")
            else:
                print("   No standalone orphaned resources found")

    finally:
        driver.close()

    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()

    if not orphaned_types:
        print("✅ All resource types are covered by architectural patterns!")
        print("   This is actually the ideal state - no orphaned types to worry about.")
        print()
        print("   The rare_boost_factor parameter is designed for cases where:")
        print("   - Some types are missing from pattern detection")
        print("   - Those types exist in Neo4j ResourceGroups")
        print("   - You want to prioritize including them")
        print()
        print("   Since all types are already in patterns, upweighting has no effect.")
        print("   This is expected behavior, not a bug!")
    else:
        print(f"⚠️  Found {len(orphaned_types)} orphaned types but they may not be selectable")
        print("   Check the Neo4j query results above to understand why.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
