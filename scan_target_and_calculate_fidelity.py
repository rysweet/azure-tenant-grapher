#!/usr/bin/env python3
"""
Scan target subscription into Neo4j and calculate fidelity score.
"""

import asyncio
import os
import json
import sys
from src.azure_tenant_grapher import AzureTenantGrapher
from src.config_manager import AzureTenantGrapherConfig, Neo4jConfig
from src.models.filter_config import FilterConfig
from src.validation.resource_fidelity_calculator import ResourceFidelityCalculator, RedactionLevel
from src.utils.session_manager import Neo4jSessionManager

async def scan_target_subscription(tenant_id: str, target_subscription: str, neo4j_config: Neo4jConfig):
    """Scan target subscription into Neo4j."""
    print("="*80)
    print("STEP 1: Scanning target subscription into Neo4j...")
    print("="*80)
    print(f"Tenant ID: {tenant_id}")
    print(f"Target Subscription: {target_subscription}")

    # Create config for target subscription
    config = AzureTenantGrapherConfig(
        neo4j=neo4j_config,
        tenant_id=tenant_id,
    )

    # Filter to only scan target subscription
    filter_config = FilterConfig(
        subscription_ids=[target_subscription],
        resource_group_names=[]
    )

    # Initialize grapher
    grapher = AzureTenantGrapher(config)

    # Run the scan
    print("\nStarting target subscription scan...")
    await grapher.build_graph(
        force_rebuild_edges=False,
        filter_config=filter_config
    )

    print("✓ Target subscription scan complete!\n")

def calculate_fidelity(mappings_file: str, source_subscription: str, target_subscription: str, neo4j_config: Neo4jConfig):
    """Calculate fidelity score using resource mappings."""
    print("="*80)
    print("STEP 2: Calculating fidelity score...")
    print("="*80)

    # Load resource mappings
    with open(mappings_file, 'r') as f:
        mappings_list = json.load(f)

    resource_mappings = [
        {
            "source_id": m["source_id"],
            "target_id": m["target_id"]
        }
        for m in mappings_list
    ]

    print(f"Loaded {len(resource_mappings)} resource mappings\n")

    # Create Neo4j session
    session_manager = Neo4jSessionManager(neo4j_config)
    session_manager.connect()

    try:
        # Create fidelity calculator
        calculator = ResourceFidelityCalculator(
            session_manager=session_manager,
            source_subscription_id=source_subscription,
            target_subscription_id=target_subscription
        )

        # Calculate fidelity
        fidelity_result = calculator.calculate_fidelity_with_mappings(
            resource_mappings=resource_mappings,
            redaction_level=RedactionLevel.FULL
        )

        # Display results
        print("="*80)
        print("FIDELITY VALIDATION RESULTS")
        print("="*80)
        print(f"Total Resources Compared: {fidelity_result.metrics.total_resources}")
        print(f"Exact Match: {fidelity_result.metrics.exact_match}")
        print(f"Drifted: {fidelity_result.metrics.drifted}")
        print(f"Missing in Target: {fidelity_result.metrics.missing_target}")
        print(f"Missing in Source: {fidelity_result.metrics.missing_source}")
        print(f"\n✓ FIDELITY SCORE: {fidelity_result.metrics.match_percentage:.1f}%\n")

        # Show sample classifications
        if fidelity_result.classifications:
            print("="*80)
            print("SAMPLE RESOURCE CLASSIFICATIONS (first 3)")
            print("="*80)
            for i, classification in enumerate(fidelity_result.classifications[:3], 1):
                print(f"\n{i}. {classification.resource_name}")
                print(f"   Type: {classification.resource_type}")
                print(f"   Status: {classification.status.value}")
                print(f"   Property Matches: {classification.match_count}")
                print(f"   Property Mismatches: {classification.mismatch_count}")

        return fidelity_result.metrics.match_percentage

    finally:
        session_manager.disconnect()

async def main():
    # Configuration
    tenant_id = "3591aa9b-70e0-4a11-8a96-699d669c7a81"
    source_subscription = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
    target_subscription = "ff7d97e0-db31-4969-9a0e-a1e6d19ccc78"
    mappings_file = "output/deployment_test_20260218_132955/03_resource_mappings.json"

    neo4j_config = Neo4jConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password=os.getenv("NEO4J_PASSWORD")
    )

    print("\n" + "="*80)
    print("FIDELITY SCORE CALCULATION WITH TARGET SCANNING")
    print("="*80 + "\n")

    # Step 1: Scan target subscription
    await scan_target_subscription(tenant_id, target_subscription, neo4j_config)

    # Step 2: Calculate fidelity
    fidelity_score = calculate_fidelity(
        mappings_file,
        source_subscription,
        target_subscription,
        neo4j_config
    )

    print("="*80)
    print(f"FINAL FIDELITY SCORE: {fidelity_score:.1f}%")
    print("="*80 + "\n")

    return 0 if fidelity_score > 0 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
