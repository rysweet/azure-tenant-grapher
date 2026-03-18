#!/usr/bin/env python3
"""
Tag a replication plan's resources in Neo4j so they can be explored in Neo4j Browser.

Nodes are tagged with:
  :ReplicationPlan          — all selected resources (used in the query)
  :RP_<PatternName>         — one per architectural pattern (drives node colour)
  :ReplicationPlanRG        — ResourceGroups that contain plan resources
  :ReplicationPlanRGBridge  — ResourceGroups shared between DIFFERENT patterns
                              (these are the architecture co-occurrence edges)

ResourceGroup properties set:
  cooccurrence_patterns     — list of pattern names that co-locate in that RG

Usage:
    python scripts/tag_replication_plan.py [--target 500]

After running, open http://localhost:7474/browser and run the Cypher printed at the end.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import find_dotenv, load_dotenv
import os

load_dotenv(find_dotenv())

NEO4J_URI         = os.getenv("NEO4J_URI",          "bolt://localhost:7687")
NEO4J_USER        = os.getenv("NEO4J_USER",         "neo4j")
NEO4J_PASS        = os.getenv("NEO4J_PASSWORD")
SOURCE_TENANT_ID  = os.getenv("SOURCE_TENANT_ID",   None)


def safe_label(name: str) -> str:
    """Convert a pattern name to a valid Neo4j label, prefixed with RP_."""
    return "RP_" + re.sub(r"[^A-Za-z0-9_]", "_", name)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", type=int, default=500,
                        help="Target resource count (default: 500)")
    parser.add_argument("--source-tenant-id", default=SOURCE_TENANT_ID,
                        required=not SOURCE_TENANT_ID,
                        help="Azure tenant ID of the source scan.  Resources "
                             "from other tenants are excluded from pattern "
                             "analysis. Can also be set via SOURCE_TENANT_ID env var.")
    args = parser.parse_args()

    from src.architecture_based_replicator import ArchitecturePatternReplicator
    from neo4j import GraphDatabase

    print(f"Source tenant filter: {args.source_tenant_id}")

    print(f"Connecting to {NEO4J_URI} ...")
    replicator = ArchitecturePatternReplicator(
        NEO4J_URI, NEO4J_USER, NEO4J_PASS,
        source_tenant_id=args.source_tenant_id,
    )

    print("Analysing source tenant ...")
    analysis = replicator.analyze_source_tenant(use_configuration_coherence=True)
    print(f"  {analysis['detected_patterns']} patterns, "
          f"{analysis['total_pattern_resources']} total resources")

    print(f"Building replication plan (target: {args.target} resources) ...")
    selected, _, meta = replicator.generate_replication_plan_by_resource_count(
        target_resource_count=args.target,
    )
    print(f"  {meta['total_instances']} instances → {meta['actual_resource_count']} resources")

    # Build resource-id → pattern label mapping, grouped by label
    by_pattern: dict[str, list[str]] = defaultdict(list)
    for pattern_name, inst in selected:
        lbl = safe_label(pattern_name)
        for r in inst:
            by_pattern[lbl].append(r["id"])

    all_ids = [rid for ids in by_pattern.values() for rid in ids]
    pattern_labels = list(by_pattern.keys())

    # ── Build architecture co-occurrence graph ─────────────────────────────────
    print("Building architecture co-occurrence graph ...")
    G_inst, G_pat = replicator.build_instance_cooccurrence_graph(selected)
    print(f"  {G_inst.number_of_edges()} instance co-occurrence edges, "
          f"{G_pat.number_of_edges()} pattern-level co-occurrence pairs")

    # Collect bridge RGs: ResourceGroups shared between instances of different patterns.
    # rg_ids in each edge are lowercase resource-ID prefixes up to the RG name,
    # e.g. /subscriptions/.../resourcegroups/my-rg
    bridge_rg_patterns: dict[str, set[str]] = defaultdict(set)
    for u, v, data in G_inst.edges(data=True):
        pname_u = G_inst.nodes[u]["pattern"]
        pname_v = G_inst.nodes[v]["pattern"]
        for rg_prefix in data["rg_ids"]:
            bridge_rg_patterns[rg_prefix].add(pname_u)
            bridge_rg_patterns[rg_prefix].add(pname_v)

    # Only flag RGs that bridge at least two distinct patterns
    bridge_rgs = {
        prefix: sorted(patterns)
        for prefix, patterns in bridge_rg_patterns.items()
        if len(patterns) > 1
    }
    print(f"  {len(bridge_rgs)} bridge ResourceGroups (shared between different patterns)")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as s:

        # ── clear all previous tags ────────────────────────────────────────────
        s.run("MATCH (r:ReplicationPlan) REMOVE r:ReplicationPlan")
        s.run("MATCH (r:ReplicationPlanRG) REMOVE r:ReplicationPlanRG")
        s.run("MATCH (r:ReplicationPlanRGBridge) "
              "REMOVE r:ReplicationPlanRGBridge "
              "REMOVE r.cooccurrence_patterns")
        for lbl in pattern_labels:
            s.run(f"MATCH (r:`{lbl}`) REMOVE r:`{lbl}`")

        # ── tag resources with base label + pattern label ──────────────────────
        total_tagged = 0
        for lbl, ids in by_pattern.items():
            result = s.run(
                f"MATCH (r:Resource:Original) WHERE r.id IN $ids "
                f"SET r:ReplicationPlan:`{lbl}` RETURN count(r) AS n",
                ids=ids,
            )
            n = result.single()["n"]
            total_tagged += n
            print(f"  :{lbl:<45} {n:>4} nodes tagged")

        if total_tagged == 0:
            print(f"\nERROR: No nodes matched. Sample IDs:\n  " + "\n  ".join(all_ids[:3]))
            sys.exit(1)

        # ── tag all ResourceGroups that contain plan resources ─────────────────
        rg_result = s.run(
            "MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:ReplicationPlan) "
            "SET rg:ReplicationPlanRG RETURN count(DISTINCT rg) AS n"
        )
        rg_tagged = rg_result.single()["n"]

        # ── tag bridge ResourceGroups and record bridging patterns ─────────────
        bridge_tagged = 0
        if bridge_rgs:
            # Use toLower(rg.id) to match the lowercase prefixes we extracted
            bridge_prefixes = list(bridge_rgs.keys())
            bridge_result = s.run(
                "MATCH (rg:ResourceGroup) "
                "WHERE toLower(rg.id) IN $prefixes "
                "SET rg:ReplicationPlanRGBridge "
                "RETURN count(rg) AS n",
                prefixes=bridge_prefixes,
            )
            bridge_tagged = bridge_result.single()["n"]

            # Set cooccurrence_patterns property per bridge RG
            for prefix, patterns in bridge_rgs.items():
                s.run(
                    "MATCH (rg:ResourceGroup) "
                    "WHERE toLower(rg.id) = $prefix "
                    "SET rg.cooccurrence_patterns = $patterns",
                    prefix=prefix,
                    patterns=patterns,
                )

    driver.close()

    print(f"\n  {total_tagged} / {len(all_ids)} resources tagged")
    print(f"  {rg_tagged} ResourceGroups tagged as :ReplicationPlanRG")
    print(f"  {bridge_tagged} / {len(bridge_rgs)} bridge RGs tagged as :ReplicationPlanRGBridge")

    # ── print pattern co-occurrence summary ────────────────────────────────────
    if G_pat.number_of_edges():
        print("\nPattern co-occurrences (patterns sharing a ResourceGroup):")
        for u, v, d in sorted(G_pat.edges(data=True), key=lambda x: -x[2]["instance_pairs"]):
            print(f"  {u}  ↔  {v}   "
                  f"({d['instance_pairs']} instance pair(s), {d['weight']} shared RG(s))")

    # ── print Browser instructions ─────────────────────────────────────────────
    label_colours = "\n".join(f"  :{lbl}" for lbl in sorted(pattern_labels))
    cypher = (
        "MATCH (r:ReplicationPlan)\n"
        "OPTIONAL MATCH (rg:ReplicationPlanRG)-[:CONTAINS]->(r)\n"
        "RETURN r, rg"
    )
    bridge_cypher = (
        "MATCH (rg:ReplicationPlanRGBridge)-[:CONTAINS]->(r:ReplicationPlan)\n"
        "RETURN rg, r"
    )
    cleanup = (
        "MATCH (r:ReplicationPlan) REMOVE r:ReplicationPlan\n"
        "WITH 1 AS x MATCH (rg:ReplicationPlanRG) REMOVE rg:ReplicationPlanRG\n"
        "WITH 1 AS x MATCH (rg:ReplicationPlanRGBridge) "
        "REMOVE rg:ReplicationPlanRGBridge REMOVE rg.cooccurrence_patterns"
    )

    print(f"""
─────────────────────────────────────────────────────
Open:  http://localhost:7474/browser

── Full plan (resources + all ResourceGroup hubs) ──

{cypher}

── Bridge view (only cross-pattern ResourceGroups) ──

{bridge_cypher}

  :ReplicationPlanRGBridge nodes have a cooccurrence_patterns property
  listing which architectural patterns meet in that ResourceGroup.
  Click a bridge RG in the Browser to see which patterns it connects.

Each node has TWO labels — Neo4j Browser colours by label:
  :ReplicationPlanRG       →  ResourceGroup hubs       (set to a neutral colour)
  :ReplicationPlanRGBridge →  cross-pattern bridge RGs (set to a distinct colour)
  :ReplicationPlan         →  all resources

  Pattern labels (set each to a distinct colour in the Browser legend):
{label_colours}

Cleanup when done:
{cleanup}
─────────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()
