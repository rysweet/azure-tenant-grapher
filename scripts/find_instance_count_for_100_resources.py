#!/usr/bin/env python3
"""
Find the number of architecture instances needed to reach 100 resources in the plan.
Counts resources directly from the replication plan (no Terraform, no deployment).
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.architecture_based_replicator import ArchitecturePatternReplicator

logging.basicConfig(level=logging.WARNING)

NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
TARGET = 100


async def main():
    print("Analyzing source tenant...")
    replicator = ArchitecturePatternReplicator(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    replicator.analyze_source_tenant(
        use_configuration_coherence=True,
        coherence_threshold=0.7,
        include_colocated_orphaned_resources=True,
    )
    print(f"Done. {len(replicator.pattern_resources)} patterns, "
          f"{sum(len(v) for v in replicator.pattern_resources.values())} total instances\n")

    print(f"{'Target N':>10}  {'Instances Selected':>20}  {'Resources in Plan':>20}  Note")
    print("-" * 70)

    found_at = None
    for n in range(1, 50):
        selected, _, _ = replicator.generate_replication_plan(
            target_instance_count=n,
            include_orphaned_node_patterns=True,
            use_architecture_distribution=True,
            use_configuration_coherence=True,
            use_spectral_guidance=True,
        )
        instances_selected = len(selected)
        resources_in_plan  = sum(len(inst) for _, inst in selected)

        note = ""
        if resources_in_plan >= TARGET and found_at is None:
            note = f"<-- CROSSOVER"
            found_at = n

        print(f"{n:>10}  {instances_selected:>20}  {resources_in_plan:>20}  {note}")
        sys.stdout.flush()

        if resources_in_plan >= TARGET + 30:
            break

    print()
    if found_at:
        print(f"RESULT: target_instance_count={found_at} is the first count to reach "
              f"{TARGET} resources in the replication plan.")
    else:
        print(f"Did not reach {TARGET} resources within tested range.")


if __name__ == "__main__":
    asyncio.run(main())
