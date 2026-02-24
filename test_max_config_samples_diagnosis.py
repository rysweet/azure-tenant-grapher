#!/usr/bin/env python3
"""
Diagnose why max_config_samples has no effect.
Check how many instances each pattern has.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.architecture_based_replicator import ArchitecturePatternReplicator


def main():
    print("🔍 Diagnosing max_config_samples parameter\n")

    # Initialize
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

    print(f"\n📊 Pattern Instance Counts:\n")
    print(f"{'Pattern Name':<40} {'Instances':>10} {'Avg Size':>10}")
    print("=" * 65)

    total_instances = 0
    for pattern_name in sorted(replicator.detected_patterns.keys()):
        instances = replicator.pattern_resources.get(pattern_name, [])
        instance_count = len(instances)
        total_instances += instance_count

        if instances:
            total_resources = sum(len(inst) for inst in instances)
            avg_size = total_resources / instance_count
        else:
            avg_size = 0

        print(f"{pattern_name:<40} {instance_count:>10} {avg_size:>10.1f}")

    print("=" * 65)
    print(f"{'TOTAL':<40} {total_instances:>10}")

    # Check if any pattern has > 100 instances
    large_patterns = [
        (name, len(replicator.pattern_resources.get(name, [])))
        for name in replicator.detected_patterns.keys()
        if len(replicator.pattern_resources.get(name, [])) > 100
    ]

    print(f"\n🔍 Analysis:\n")
    if large_patterns:
        print(f"✅ {len(large_patterns)} patterns have > 100 instances:")
        for name, count in large_patterns:
            print(f"   - {name}: {count} instances")
        print("\n   → max_config_samples SHOULD have effect on these patterns")
    else:
        print("❌ NO patterns have > 100 instances!")
        print("   → max_config_samples=100 is LARGER than all pattern sizes")
        print("   → Parameter has NO EFFECT (all instances always sampled)")

        max_pattern_size = max(
            len(replicator.pattern_resources.get(name, []))
            for name in replicator.detected_patterns.keys()
        )
        print(f"\n   Largest pattern: {max_pattern_size} instances")
        print(f"   → max_config_samples would need to be < {max_pattern_size} to have effect")


if __name__ == "__main__":
    main()
