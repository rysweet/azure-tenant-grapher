#!/usr/bin/env python3
"""
Verify that no actual Azure resource types are being dropped during simplified→full name mapping.

This script checks if types that fail to map are truly non-resources (Region, Subscription, etc.)
or if we're accidentally dropping real Azure resources.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.architecture_based_replicator import ArchitecturePatternReplicator
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")

# Known non-resource types (organizational/meta types)
KNOWN_NON_RESOURCES = {
    "Region",           # Geographic region (organizational)
    "Subscription",     # Azure subscription (billing boundary)
    "ResourceGroup",    # Resource container (organizational)
    "Tag",              # Metadata tag
    "User",             # Azure AD user identity
    "users",            # Azure AD users
    "groups",           # Azure AD groups
    "servicePrincipals", # Azure AD service principals
    "RoleDefinition",   # RBAC role definition
    "roleAssignments",  # RBAC role assignment (may be in Neo4j as Microsoft.Authorization/roleAssignments)
}

def main():
    print("=" * 80)
    print("VERIFICATION: No Dropped Azure Resource Types")
    print("=" * 80)
    print()

    replicator = ArchitecturePatternReplicator(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD
    )

    print("🔍 Analyzing source tenant...")
    replicator.analyze_source_tenant(
        use_configuration_coherence=True,
        coherence_threshold=0.5
    )
    print()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Get all full type names from Neo4j
            type_query = """
            MATCH (r:Resource:Original)
            RETURN DISTINCT r.type as full_type
            ORDER BY r.type
            """
            type_result = session.run(type_query)
            all_full_types = [record["full_type"] for record in type_result]

            print(f"📊 Found {len(all_full_types)} distinct resource types in Neo4j")
            print()

            # Build mapping
            simplified_to_full = {}
            full_to_simplified = {}
            for full_type in all_full_types:
                simplified = replicator.analyzer._get_resource_type_name(["Resource"], full_type)
                if simplified not in simplified_to_full:
                    simplified_to_full[simplified] = []
                simplified_to_full[simplified].append(full_type)
                full_to_simplified[full_type] = simplified

            # Get pattern types
            pattern_types_simplified = set()
            for pattern_info in replicator.detected_patterns.values():
                pattern_types_simplified.update(pattern_info["matched_resources"])

            # Compute orphaned types
            orphaned_types_simplified = set(replicator.source_resource_type_counts.keys()) - pattern_types_simplified

            print(f"🔬 Analysis:")
            print(f"   Source types (simplified): {len(replicator.source_resource_type_counts)}")
            print(f"   Pattern types (simplified): {len(pattern_types_simplified)}")
            print(f"   Orphaned types (simplified): {len(orphaned_types_simplified)}")
            print()

            # Check unmapped types
            unmapped_types = []
            mapped_types = []
            for simplified in orphaned_types_simplified:
                if simplified in simplified_to_full:
                    mapped_types.append(simplified)
                else:
                    unmapped_types.append(simplified)

            print(f"✅ Mapped orphaned types: {len(mapped_types)}")
            print(f"⚠️  Unmapped orphaned types: {len(unmapped_types)}")
            print()

            if unmapped_types:
                print("🔍 Checking unmapped types:")
                print()

                known_non_resources = []
                potential_issues = []

                for simplified in sorted(unmapped_types):
                    if simplified in KNOWN_NON_RESOURCES:
                        known_non_resources.append(simplified)
                    else:
                        potential_issues.append(simplified)

                print(f"✅ Known non-resources (expected): {len(known_non_resources)}")
                for t in known_non_resources:
                    print(f"   - {t}")
                print()

                if potential_issues:
                    print(f"⚠️  POTENTIAL ISSUES: {len(potential_issues)} types")
                    print("   These might be actual Azure resources being dropped:")
                    for t in potential_issues:
                        # Check if this exists in Neo4j with a different pattern
                        count_query = """
                        MATCH (r:Resource:Original)
                        WHERE toLower(r.type) CONTAINS toLower($simplified)
                        RETURN r.type as full_type, count(r) as count
                        ORDER BY count DESC
                        LIMIT 5
                        """
                        result = session.run(count_query, simplified=t)
                        matches = list(result)

                        if matches:
                            print(f"   ⚠️  {t}: Found potential matches in Neo4j:")
                            for match in matches:
                                print(f"      - {match['full_type']} (count: {match['count']})")
                        else:
                            print(f"   ✅ {t}: No matches in Neo4j (truly not a resource)")
                    print()
                else:
                    print("✅ No potential issues - all unmapped types are known non-resources")
                    print()

            # Check for many-to-one mappings (might indicate issues)
            print("🔬 Checking for ambiguous mappings (simplified → multiple full types):")
            ambiguous = []
            for simplified, full_types in simplified_to_full.items():
                if len(full_types) > 1:
                    ambiguous.append((simplified, full_types))

            if ambiguous:
                print(f"   Found {len(ambiguous)} ambiguous mappings:")
                for simplified, full_types in sorted(ambiguous)[:10]:
                    print(f"   - {simplified} → {full_types}")
                if len(ambiguous) > 10:
                    print(f"   ... and {len(ambiguous) - 10} more")
            else:
                print("   ✅ No ambiguous mappings")
            print()

            # Final verdict
            print("=" * 80)
            print("VERDICT")
            print("=" * 80)
            print()

            if not potential_issues:
                print("✅ SUCCESS: No Azure resource types are being dropped!")
                print()
                print("   All unmapped types are:")
                print("   - Organizational constructs (Region, Subscription, ResourceGroup)")
                print("   - Identity types (User, groups, servicePrincipals)")
                print("   - Metadata (Tag, RoleDefinition)")
                print()
                print("   These do not exist as resources in Neo4j ResourceGroups,")
                print("   so it's correct that they don't map.")
                return 0
            else:
                print(f"⚠️  WARNING: Found {len(potential_issues)} potentially dropped types")
                print("   Review the output above to determine if these are:")
                print("   1. Real Azure resources being dropped (BUG)")
                print("   2. Additional non-resource types to add to KNOWN_NON_RESOURCES")
                return 1

    finally:
        driver.close()

if __name__ == "__main__":
    sys.exit(main())
