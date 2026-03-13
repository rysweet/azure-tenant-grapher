#!/usr/bin/env python3
"""
Empirical test of spectral_weight and max_config_samples parameters.

Tests different combinations to see if they actually produce different results.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.architecture_based_replicator import ArchitecturePatternReplicator


def run_test(spectral_weight, max_config_samples, test_id):
    """Run a single test configuration."""
    print(f"\n{'='*80}")
    print(f"TEST {test_id}: spectral_weight={spectral_weight}, max_config_samples={max_config_samples}")
    print(f"{'='*80}")

    # Initialize replicator
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    replicator = ArchitecturePatternReplicator(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password
    )

    # Analyze source
    print("Analyzing source tenant...")
    analysis = replicator.analyze_source_tenant(
        use_configuration_coherence=True,
        coherence_threshold=0.5,
    )

    print(f"Source: {analysis['resource_types']} types, {analysis['pattern_graph_edges']} edges")

    # Generate replication plan
    print(f"Generating plan with spectral_weight={spectral_weight}, max_config_samples={max_config_samples}...")
    selected_instances, spectral_history, metadata = replicator.generate_replication_plan(
        target_instance_count=500,
        hops=2,
        include_orphaned_node_patterns=True,
        use_architecture_distribution=True,
        use_configuration_coherence=True,
        use_spectral_guidance=True,
        spectral_weight=spectral_weight,
        max_config_samples=max_config_samples,
        sampling_strategy='coverage',
    )

    # Build target graph
    flattened = [(pn, inst) for pn, instances in selected_instances for inst in instances]
    target_graph = replicator._build_target_pattern_graph_from_instances(flattened)

    # Calculate metrics
    source_nodes = set(replicator.source_pattern_graph.nodes())
    target_nodes = set(target_graph.nodes())
    common_nodes = source_nodes.intersection(target_nodes)

    total_instances = sum(len(instances) for _, instances in selected_instances)
    total_resources = sum(len(inst) for _, instances in selected_instances for inst in instances)

    # Extract instance IDs for comparison
    instance_ids = set()
    for _, instances in selected_instances:
        for instance in instances:
            for resource in instance:
                instance_ids.add(resource.get('id', resource.get('name', 'unknown')))

    results = {
        'test_id': test_id,
        'spectral_weight': spectral_weight,
        'max_config_samples': max_config_samples,
        'source_types': len(source_nodes),
        'target_types': len(target_nodes),
        'common_types': len(common_nodes),
        'coverage_pct': len(common_nodes) / len(source_nodes) * 100,
        'total_instances': total_instances,
        'total_resources': total_resources,
        'spectral_initial': spectral_history[0] if spectral_history else None,
        'spectral_final': spectral_history[-1] if spectral_history else None,
        'spectral_improvement': ((spectral_history[0] - spectral_history[-1]) / spectral_history[0] * 100) if spectral_history else None,
        'common_types_list': sorted(list(common_nodes))[:20],  # First 20 for comparison
        'instance_ids_sample': sorted(list(instance_ids))[:20],  # First 20 for comparison
    }

    print(f"\n📊 Results:")
    print(f"   Coverage: {results['common_types']}/{results['source_types']} = {results['coverage_pct']:.1f}%")
    print(f"   Instances: {results['total_instances']}, Resources: {results['total_resources']}")
    if results['spectral_improvement'] is not None:
        print(f"   Spectral improvement: {results['spectral_improvement']:.1f}%")
    print(f"   Common types (first 10): {', '.join(results['common_types_list'][:10])}")

    return results


def main():
    """Run test matrix and compare results."""
    print("🔬 EMPIRICAL TEST: spectral_weight and max_config_samples Parameter Sweep\n")

    # Test matrix
    spectral_weights = [0.0, 0.4, 0.6, 0.9]
    max_config_samples_list = [100, 500, 1000]

    all_results = []
    test_id = 1

    # Run all tests
    for spectral_weight in spectral_weights:
        for max_config_samples in max_config_samples_list:
            try:
                result = run_test(spectral_weight, max_config_samples, test_id)
                all_results.append(result)
                test_id += 1
            except Exception as e:
                print(f"\n❌ Test {test_id} FAILED: {e}")
                import traceback
                traceback.print_exc()
                test_id += 1

    # Analysis
    print(f"\n{'='*80}")
    print("COMPARISON ANALYSIS")
    print(f"{'='*80}\n")

    # Group by spectral_weight to see if max_config_samples matters
    print("📊 Effect of max_config_samples (grouped by spectral_weight):\n")
    for sw in spectral_weights:
        print(f"spectral_weight = {sw}:")
        sw_results = [r for r in all_results if r['spectral_weight'] == sw]
        for r in sw_results:
            print(f"  max_config_samples={r['max_config_samples']:4d} → Coverage: {r['coverage_pct']:5.1f}%, "
                  f"Instances: {r['total_instances']:3d}, Types: {r['common_types']:2d}")
        print()

    # Group by max_config_samples to see if spectral_weight matters
    print("📊 Effect of spectral_weight (grouped by max_config_samples):\n")
    for mcs in max_config_samples_list:
        print(f"max_config_samples = {mcs}:")
        mcs_results = [r for r in all_results if r['max_config_samples'] == mcs]
        for r in mcs_results:
            print(f"  spectral_weight={r['spectral_weight']:.1f} → Coverage: {r['coverage_pct']:5.1f}%, "
                  f"Instances: {r['total_instances']:3d}, Types: {r['common_types']:2d}")
        print()

    # Check if common_types_list is identical across all tests
    print("🔍 Checking if common resource types are identical across tests:\n")
    baseline_types = set(all_results[0]['common_types_list'])
    all_identical = True
    for i, r in enumerate(all_results[1:], 2):
        current_types = set(r['common_types_list'])
        if current_types != baseline_types:
            all_identical = False
            diff = current_types.symmetric_difference(baseline_types)
            print(f"Test {i} DIFFERS from Test 1: {len(diff)} types different")
            print(f"  Different types: {', '.join(sorted(diff)[:5])}...")

    if all_identical:
        print("⚠️  ALL TESTS PRODUCED IDENTICAL COMMON RESOURCE TYPES")
        print("   This suggests parameters have NO EFFECT on which types are selected")
    else:
        print("✅ Tests produced DIFFERENT common resource types")
        print("   Parameters ARE affecting selection")

    # Coverage variance
    coverages = [r['coverage_pct'] for r in all_results]
    coverage_range = max(coverages) - min(coverages)
    print(f"\n📊 Coverage variance:")
    print(f"   Min: {min(coverages):.1f}%, Max: {max(coverages):.1f}%, Range: {coverage_range:.1f}%")

    if coverage_range < 1.0:
        print("   ⚠️  Coverage varies by less than 1% - effectively identical")
    else:
        print("   ✅ Coverage shows meaningful variation")

    # Final verdict
    print(f"\n{'='*80}")
    print("VERDICT")
    print(f"{'='*80}\n")

    if coverage_range < 1.0 and all_identical:
        print("❌ PARAMETERS HAVE NO EFFECT")
        print("   Both spectral_weight and max_config_samples produce identical results")
        print("   Root cause is likely DIFFERENT than predicted")
    elif coverage_range >= 5.0:
        print("✅ PARAMETERS ARE WORKING")
        print("   Results vary significantly across parameter combinations")
    else:
        print("⚠️  PARAMETERS HAVE MINIMAL EFFECT")
        print(f"   Coverage varies by {coverage_range:.1f}% - marginal impact")


if __name__ == "__main__":
    main()
