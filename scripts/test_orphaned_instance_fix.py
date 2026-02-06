#!/usr/bin/env python3
"""
Test script to verify the orphaned instance selection fix.

This script tests whether the type name mismatch fix is working by:
1. Analyzing a source tenant
2. Generating replication plans with different rare_boost_factor values
3. Comparing node coverage between baseline and upweighted runs
4. Checking if orphaned ResourceGroups are being found

Expected Results After Fix:
- rare_boost_factor=1.0: ~44% coverage (baseline)
- rare_boost_factor=5.0: ~90-99% coverage (with orphaned instances)
- Orphaned ResourceGroups found: 185+ (vs 0 before fix)
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.architecture_based_replicator import ArchitecturePatternReplicator

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")
TARGET_INSTANCE_COUNT = 500

def main():
    print("=" * 80)
    print("ORPHANED INSTANCE SELECTION FIX VERIFICATION")
    print("=" * 80)
    print()

    # Initialize replicator
    print("🔧 Initializing replicator...")
    replicator = ArchitecturePatternReplicator(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD
    )
    print("✅ Replicator initialized\n")

    # Analyze source tenant
    print("🔍 Analyzing source tenant...")
    analysis = replicator.analyze_source_tenant(
        use_configuration_coherence=True,
        coherence_threshold=0.5
    )

    print(f"   Source Resource Types: {analysis['resource_types']}")
    print(f"   Detected Patterns: {analysis['detected_patterns']}")
    print(f"   Pattern Graph Edges: {analysis['pattern_graph_edges']}")
    print()

    # Check if source_resource_type_counts is populated
    if not replicator.source_resource_type_counts:
        print("❌ ERROR: source_resource_type_counts is None or empty!")
        print("   This is required for the new orphaned instance detection.")
        return 1

    print(f"✅ source_resource_type_counts populated: {len(replicator.source_resource_type_counts)} types")
    print(f"   First 10 types: {list(replicator.source_resource_type_counts.keys())[:10]}")
    print()

    # Test finding orphaned instances directly
    print("🔬 Testing _find_orphaned_node_instances() directly...")
    try:
        orphaned_instances = replicator._find_orphaned_node_instances()
        print(f"✅ Found {len(orphaned_instances)} orphaned instance groups")

        if len(orphaned_instances) == 0:
            print("⚠️  WARNING: No orphaned instances found!")
            print("   This could mean:")
            print("   1. All types are covered by patterns (unlikely with 91 types)")
            print("   2. The fix isn't working correctly")
            print("   3. Neo4j database doesn't have the expected data")
        else:
            print(f"   Orphaned types in first 5 groups:")
            for pattern_name, resources in orphaned_instances[:5]:
                types = set(r['type'] for r in resources)
                print(f"     - {pattern_name}: {types}")
    except Exception as e:
        print(f"❌ ERROR calling _find_orphaned_node_instances(): {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()

    # Test with different rare_boost_factor values
    print("=" * 80)
    print("PARAMETER SWEEP: rare_boost_factor")
    print("=" * 80)
    print()

    results = []
    for rare_boost_factor in [1.0, 5.0]:
        print(f"🔬 Test: rare_boost_factor = {rare_boost_factor}")
        print(f"   {'(BASELINE - feature disabled)' if rare_boost_factor == 1.0 else '(ENABLED)'}")

        try:
            selected_pattern_instances, spectral_history, distribution_metadata = (
                replicator.generate_replication_plan(
                    target_instance_count=TARGET_INSTANCE_COUNT,
                    rare_boost_factor=rare_boost_factor  # Now uses recommended defaults for other params
                )
            )

            # Build target pattern graph
            flattened_instances = []
            for pattern_name, instances in selected_pattern_instances:
                for instance in instances:
                    flattened_instances.append((pattern_name, instance))

            target_pattern_graph = replicator._build_target_pattern_graph_from_instances(flattened_instances)

            # Compute metrics
            source_nodes = set(replicator.source_pattern_graph.nodes())
            target_nodes = set(target_pattern_graph.nodes())
            common_nodes = source_nodes.intersection(target_nodes)

            node_coverage_pct = (len(common_nodes) / len(source_nodes)) * 100 if source_nodes else 0

            # Rare type inclusion (types with freq < 5)
            rare_types = {rt for rt, count in replicator.source_resource_type_counts.items() if count < 5}
            rare_in_target = rare_types.intersection(target_nodes)
            rare_inclusion_pct = (len(rare_in_target) / len(rare_types)) * 100 if rare_types else 0

            # Check for orphaned patterns in selection
            orphaned_pattern_count = sum(1 for name, _ in selected_pattern_instances if "Orphaned" in name)

            results.append({
                'rare_boost_factor': rare_boost_factor,
                'node_coverage_pct': node_coverage_pct,
                'rare_inclusion_pct': rare_inclusion_pct,
                'common_nodes': len(common_nodes),
                'source_nodes': len(source_nodes),
                'rare_in_target': len(rare_in_target),
                'rare_total': len(rare_types),
                'orphaned_patterns': orphaned_pattern_count
            })

            print(f"   Node Coverage:       {node_coverage_pct:.1f}% ({len(common_nodes)}/{len(source_nodes)})")
            print(f"   Rare Type Inclusion: {rare_inclusion_pct:.1f}% ({len(rare_in_target)}/{len(rare_types)})")
            print(f"   Orphaned Patterns:   {orphaned_pattern_count}")
            print()

        except Exception as e:
            print(f"❌ ERROR generating replication plan: {e}")
            import traceback
            traceback.print_exc()
            return 1

    # Compare results
    print("=" * 80)
    print("COMPARISON & VERDICT")
    print("=" * 80)
    print()

    baseline = results[0]
    upweighted = results[1]

    node_improvement = upweighted['node_coverage_pct'] - baseline['node_coverage_pct']
    rare_improvement = upweighted['rare_inclusion_pct'] - baseline['rare_inclusion_pct']
    orphaned_increase = upweighted['orphaned_patterns'] - baseline['orphaned_patterns']

    print(f"📊 Results Summary:")
    print()
    print(f"{'Metric':<30} {'Baseline (1.0)':<20} {'Upweighted (5.0)':<20} {'Change'}")
    print("-" * 80)
    print(f"{'Node Coverage':<30} {baseline['node_coverage_pct']:>6.1f}% ({baseline['common_nodes']}/{baseline['source_nodes']}){'':<7} {upweighted['node_coverage_pct']:>6.1f}% ({upweighted['common_nodes']}/{upweighted['source_nodes']}){'':<7} {node_improvement:+6.1f}%")
    print(f"{'Rare Type Inclusion':<30} {baseline['rare_inclusion_pct']:>6.1f}% ({baseline['rare_in_target']}/{baseline['rare_total']}){'':<7} {upweighted['rare_inclusion_pct']:>6.1f}% ({upweighted['rare_in_target']}/{upweighted['rare_total']}){'':<7} {rare_improvement:+6.1f}%")
    print(f"{'Orphaned Patterns':<30} {baseline['orphaned_patterns']:>6}{'':<14} {upweighted['orphaned_patterns']:>6}{'':<14} {orphaned_increase:+6}")
    print()

    # Verdict
    print("🔍 VERDICT:")
    print()

    if node_improvement > 10:
        print("✅ SUCCESS: Fix is working!")
        print(f"   Node coverage improved by {node_improvement:.1f}%")
        print(f"   Rare type inclusion improved by {rare_improvement:.1f}%")
        print(f"   Orphaned patterns increased by {orphaned_increase}")
        return 0
    elif node_improvement > 0:
        print("⚠️  PARTIAL: Small improvement detected")
        print(f"   Node coverage improved by {node_improvement:.1f}% (expected >10%)")
        print("   Possible issues:")
        print("   - Orphaned instances exist but have low coverage impact")
        print("   - Need to check if orphaned ResourceGroups are being selected")
        return 0
    else:
        print("❌ FAILURE: No improvement detected")
        print("   rare_boost_factor has NO effect on coverage")
        print()
        print("   Diagnostic steps:")
        print("   1. Check _find_orphaned_node_instances() output above")
        print("   2. Verify Neo4j contains resources with full type names")
        print("   3. Check if orphaned instances are being included in selection")
        print()
        print("   Expected after fix:")
        print("   - Orphaned instances found: 185+")
        print("   - Node coverage improvement: +15-55%")
        print("   - Rare type inclusion improvement: +20-40%")
        return 1

if __name__ == "__main__":
    sys.exit(main())
