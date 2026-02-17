#!/usr/bin/env python3
"""
Test that subgraph-based spectral distance produces varying scores.

This validates the fix for spectral_weight threshold behavior where
0.4, 0.6, 0.9 previously produced identical results.
"""

import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Enable DEBUG logging to see score statistics
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(message)s'
)

from src.architecture_based_replicator import ArchitecturePatternReplicator


def run_quick_test(spectral_weight):
    """Run quick test with DEBUG logging to see spectral score variance."""
    print(f"\n{'='*80}")
    print(f"TEST: spectral_weight={spectral_weight}")
    print(f"{'='*80}\n")

    # Initialize
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "neo4j123")

    replicator = ArchitecturePatternReplicator(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password
    )

    # Analyze source (suppress verbose output)
    logger = logging.getLogger('src.architecture_based_replicator')
    original_level = logger.level
    logger.setLevel(logging.WARNING)

    replicator.analyze_source_tenant(
        use_configuration_coherence=True,
        coherence_threshold=0.5,
    )

    logger.setLevel(logging.DEBUG)  # Re-enable DEBUG for scoring

    # Generate plan - focus on first few patterns to see score variance
    print(f"\nGenerating plan with spectral_weight={spectral_weight}...")
    print("(Check DEBUG logs for spectral score variance)\n")

    selected, history, metadata = replicator.generate_replication_plan(
        target_instance_count=50,
        hops=2,
        include_orphaned_node_patterns=False,
        use_architecture_distribution=True,
        use_configuration_coherence=True,
        use_spectral_guidance=True,
        spectral_weight=spectral_weight,
        max_config_samples=100,
        sampling_strategy='coverage',
    )

    logger.setLevel(original_level)

    # Build target and measure coverage
    flattened = [(pn, inst) for pn, instances in selected for inst in instances]
    target_graph = replicator._build_target_pattern_graph_from_instances(flattened)

    source_nodes = set(replicator.source_pattern_graph.nodes())
    target_nodes = set(target_graph.nodes())
    common_nodes = source_nodes.intersection(target_nodes)

    coverage = len(common_nodes) / len(source_nodes) * 100

    print(f"\n📊 Results:")
    print(f"   Coverage: {len(common_nodes)}/{len(source_nodes)} = {coverage:.1f}%")
    print(f"   Common types (first 10): {sorted(list(common_nodes))[:10]}")

    return coverage, sorted(list(common_nodes))


def main():
    print("🔍 Testing subgraph-based spectral distance fix\n")
    print("Expected: Spectral scores should now have HIGH variance")
    print("Expected: Different spectral_weight values should produce different coverage\n")

    # Test three values
    test_weights = [0.4, 0.6, 0.9]

    results = []
    for weight in test_weights:
        coverage, common_types = run_quick_test(weight)
        results.append((weight, coverage, common_types))

    # Compare results
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}\n")

    print("Coverage comparison:")
    for weight, coverage, _ in results:
        print(f"  spectral_weight={weight}: {coverage:.1f}%")

    # Check variance
    coverages = [c for _, c, _ in results]
    coverage_range = max(coverages) - min(coverages)

    print(f"\nCoverage range: {coverage_range:.1f}%")

    if coverage_range < 1.0:
        print("❌ STILL CLUSTERING - spectral scores still not varying enough")
    elif coverage_range < 5.0:
        print("⚠️  MINIMAL EFFECT - some variation but still clustering")
    else:
        print("✅ FIX WORKING - spectral_weight now has meaningful effect")

    # Check if types differ
    baseline_types = set(results[0][2])
    all_identical = all(set(types) == baseline_types for _, _, types in results[1:])

    if all_identical:
        print("⚠️  Common types still identical across all tests")
    else:
        print("✅ Common types differ - parameter affecting selection")

    print("\n💡 Check DEBUG logs above for 'Spectral: min=X, max=Y, range=Z'")
    print("   Before fix: range ~0.008 (clustering)")
    print("   After fix:  range should be >> 0.05 (good variance)")


if __name__ == "__main__":
    main()
