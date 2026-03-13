#!/usr/bin/env python3
"""
Test spectral_weight with DEBUG logging to see actual score distributions.
This will help us understand why 0.4, 0.6, 0.9 produce identical results.
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


def run_test_with_logging(spectral_weight):
    """Run test with DEBUG logging to capture score statistics."""
    print(f"\n{'='*80}")
    print(f"TEST: spectral_weight={spectral_weight}")
    print(f"{'='*80}\n")

    # Initialize
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

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

    # Generate plan - only look at first pattern to keep output manageable
    print(f"\nGenerating plan with spectral_weight={spectral_weight}...")
    print("(Showing score statistics for first pattern only)\n")

    selected, history, metadata = replicator.generate_replication_plan(
        target_instance_count=50,  # Smaller for faster execution
        hops=2,
        include_orphaned_node_patterns=False,  # Simplify
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

    print(f"\n📊 Results:")
    print(f"   Coverage: {len(common_nodes)}/{len(source_nodes)} = {len(common_nodes)/len(source_nodes)*100:.1f}%")
    print(f"   Common types: {sorted(list(common_nodes))[:10]}")

    return len(common_nodes), sorted(list(common_nodes))


def main():
    print("🔍 Investigating spectral_weight threshold behavior with score logging\n")

    # Test three values that empirically produced identical results
    test_weights = [0.4, 0.6, 0.9]

    results = []
    for weight in test_weights:
        coverage, common_types = run_test_with_logging(weight)
        results.append((weight, coverage, common_types))

    # Compare results
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}\n")

    print("Coverage comparison:")
    for weight, coverage, _ in results:
        print(f"  spectral_weight={weight}: {coverage} types")

    # Check if common types are identical
    baseline_types = set(results[0][2])
    all_identical = all(set(types) == baseline_types for _, _, types in results[1:])

    if all_identical:
        print("\n⚠️  All tests produced IDENTICAL common resource types")
    else:
        print("\n✅ Tests produced DIFFERENT common resource types")

    print("\n💡 Check the DEBUG logs above to see score distributions")
    print("   Look for 'Score statistics' to see if spectral scores vary across candidates")


if __name__ == "__main__":
    main()
