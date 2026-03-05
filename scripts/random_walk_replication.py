#!/usr/bin/env python3
"""
Random Walk Replication — Scale-down tenant replication using random walk sampling.

Samples N resources from the source tenant using random walk, generates Terraform
IaC, and deploys using `atg deploy --agent`.

Usage:
    python scripts/random_walk_replication.py \
        --source-subscription SOURCE_ID \
        --target-subscription TARGET_ID \
        --target-tenant-id TARGET_TENANT \
        --target-count 500 \
        --output-dir ./output/rw_replication
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import networkx as nx
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph
from src.services.scale_down.sampling.random_walk_sampler import RandomWalkSampler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SEP = "─" * 72


def build_graph_from_neo4j(
    driver, subscription_id: str
) -> tuple[nx.DiGraph, list[dict], list[dict]]:
    """Build a NetworkX graph + raw resource/relationship lists from Original nodes."""
    resources = []
    relationships = []
    G = nx.DiGraph()

    with driver.session() as session:
        # Load all Original resources for source subscription
        result = session.run(
            """
            MATCH (r:Resource:Original)
            WHERE r.subscription_id = $sub
            RETURN r.id AS id, properties(r) AS props
            """,
            sub=subscription_id,
        )
        for record in result:
            node_id = record["id"]
            props = dict(record["props"])
            G.add_node(node_id, **props)
            resources.append(props)

        logger.info(f"Loaded {G.number_of_nodes()} resource nodes")

        # Load relationships between them
        result = session.run(
            """
            MATCH (s:Resource:Original)-[rel]->(t:Resource:Original)
            WHERE s.subscription_id = $sub
              AND t.subscription_id = $sub
              AND type(rel) <> 'SCAN_SOURCE_NODE'
            RETURN s.id AS source_id,
                   type(rel) AS rel_type,
                   t.id AS target_id,
                   properties(rel) AS rel_props
            """,
            sub=subscription_id,
        )
        for record in result:
            src, tgt = record["source_id"], record["target_id"]
            rel_type = record["rel_type"]
            G.add_edge(src, tgt, relationship_type=rel_type)
            relationships.append(
                {
                    "source_id": src,
                    "relationship_type": rel_type,
                    "target_id": tgt,
                    "properties": dict(record["rel_props"] or {}),
                }
            )

        logger.info(
            f"Loaded {len(relationships)} relationships, {G.number_of_edges()} edges"
        )

    return G, resources, relationships


async def sample_resources(
    G: nx.DiGraph, resources: list[dict], relationships: list[dict], target_count: int
) -> tuple[list[dict], list[dict]]:
    """Sample target_count nodes via random walk and filter resources + relationships."""
    logger.info(f"Sampling {target_count} nodes using random walk...")
    sampler = RandomWalkSampler()
    sampled_ids = await sampler.sample(G, target_count)
    logger.info(f"Sampled {len(sampled_ids)} nodes")

    # Filter resources to sampled set
    id_set = set(sampled_ids)
    sampled_resources = [r for r in resources if r.get("id") in id_set]

    # Filter relationships: both endpoints must be in sampled set
    sampled_relationships = [
        r
        for r in relationships
        if r["source_id"] in id_set and r["target_id"] in id_set
    ]

    logger.info(
        f"Filtered to {len(sampled_resources)} resources, "
        f"{len(sampled_relationships)} relationships"
    )
    return sampled_resources, sampled_relationships


def generate_iac(
    resources: list[dict],
    relationships: list[dict],
    source_subscription: str,
    target_subscription: str,
    output_dir: Path,
    target_tenant_id: Optional[str] = None,
) -> Path:
    """Generate Terraform IaC for sampled resources."""
    terraform_dir = output_dir / "terraform"
    terraform_dir.mkdir(parents=True, exist_ok=True)

    tenant_graph = TenantGraph(resources=resources, relationships=relationships)

    emitter = TerraformEmitter(
        target_subscription_id=target_subscription,
        source_subscription_id=source_subscription,
        target_tenant_id=target_tenant_id,
        auto_import_existing=False,
    )

    generated_files = emitter.emit(
        graph=tenant_graph,
        out_dir=terraform_dir,
        subscription_id=target_subscription,
    )

    logger.info(f"Generated {len(generated_files)} Terraform files in {terraform_dir}")
    return terraform_dir


def deploy_with_agent(
    terraform_dir: Path,
    target_tenant: str,
    target_subscription: str,
    max_iterations: int = 20,
    agent_timeout: int = 6000,
) -> int:
    """Deploy using `atg deploy --agent`."""
    cmd = [
        "atg", "deploy",
        "--iac-dir", str(terraform_dir),
        "--target-tenant-id", target_tenant,
        "--subscription-id", target_subscription,
        "--resource-group", "random-walk-replication",  # label only for Terraform
        "--agent",
        "--max-iterations", str(max_iterations),
        "--agent-timeout", str(agent_timeout),
    ]
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


async def main(args: argparse.Namespace) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / f"random_walk_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(SEP)
    print(f"  Random Walk Replication — target {args.target_count} resources")
    print(SEP)
    print(f"  Source subscription : {args.source_subscription}")
    print(f"  Target subscription : {args.target_subscription}")
    print(f"  Target tenant       : {args.target_tenant}")
    print(f"  Output directory    : {output_dir}")
    print(SEP)

    # ── Step 1: Load graph from Neo4j ─────────────────────────────────────────
    print("\n  STEP 1: Loading source graph from Neo4j...")
    driver = GraphDatabase.driver(
        args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password)
    )
    try:
        G, resources, relationships = build_graph_from_neo4j(
            driver, args.source_subscription
        )
    finally:
        driver.close()

    print(f"  Loaded {len(resources):,} resources, {len(relationships):,} relationships")

    # ── Step 2: Sample with random walk ───────────────────────────────────────
    print(f"\n  STEP 2: Sampling {args.target_count} resources via random walk...")
    sampled_resources, sampled_relationships = await sample_resources(
        G, resources, relationships, args.target_count
    )
    print(f"  Sampled {len(sampled_resources):,} resources, {len(sampled_relationships):,} relationships")

    # Save manifest of sampled resource IDs
    manifest_file = output_dir / "sampled_resources.json"
    with open(manifest_file, "w") as f:
        json.dump(
            {"resource_ids": [r.get("id") for r in sampled_resources]}, f, indent=2
        )
    print(f"  Manifest saved → {manifest_file}")

    # ── Step 3: Generate Terraform IaC ────────────────────────────────────────
    print("\n  STEP 3: Generating Terraform IaC...")
    terraform_dir = generate_iac(
        sampled_resources,
        sampled_relationships,
        args.source_subscription,
        args.target_subscription,
        output_dir,
        target_tenant_id=args.target_tenant,
    )
    print(f"  IaC written → {terraform_dir}")

    # ── Step 4: Deploy with agent mode ────────────────────────────────────────
    print("\n  STEP 4: Deploying with atg deploy --agent...")
    rc = deploy_with_agent(
        terraform_dir,
        args.target_tenant,
        args.target_subscription,
        max_iterations=args.max_iterations,
        agent_timeout=args.agent_timeout,
    )

    print(SEP)
    if rc == 0:
        print("  Deployment completed successfully.")
    else:
        print(f"  Deployment finished with exit code {rc} (check logs above).")
    print(SEP)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Random walk tenant replication")
    p.add_argument("--source-subscription", required=True)
    p.add_argument("--target-subscription", required=True)
    p.add_argument("--target-tenant-id", dest="target_tenant", required=True)
    p.add_argument("--target-count", type=int, default=100)
    p.add_argument("--output-dir", default="./output/random_walk_replication")
    p.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    p.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    p.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD"))
    p.add_argument("--max-iterations", type=int, default=20)
    p.add_argument("--agent-timeout", type=int, default=6000)
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
