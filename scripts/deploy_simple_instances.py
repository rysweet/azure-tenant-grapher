#!/usr/bin/env python3
"""
Deploy Low-Complexity Architecture Instances to Target Tenant

This script:
1. Reads the existing Neo4j graph from the Docker scan (or loads cached plan)
2. Runs ArchitecturePatternReplicator to generate a replication plan
3. Filters to instances with deployment complexity score < 4.0 (the easy ones)
4. Deletes all existing resource groups in the target subscription
5. Deploys the selected low-complexity instances via Terraform
6. Plots spectral distance vs. number of resources deployed

The replication plan is cached to disk after generation so reruns skip the
slow analysis/selection steps and jump straight to deployment.

Usage:
    # First run (generates and caches plan):
    python scripts/deploy_simple_instances.py

    # Subsequent runs (loads cached plan, skips analysis):
    python scripts/deploy_simple_instances.py

    # Force plan regeneration:
    python scripts/deploy_simple_instances.py --refresh-plan

    # Dry run (no deletion/deployment):
    python scripts/deploy_simple_instances.py --dry-run

Defaults:
    Source subscription: <source-subscription-id>
    Target subscription: <target-subscription-id>
    Target tenant:       <tenant-id>
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving plots
import matplotlib.pyplot as plt
import networkx as nx
from neo4j import GraphDatabase

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.architectural_pattern_analyzer import ArchitecturalPatternAnalyzer
from src.architecture_based_replicator import ArchitecturePatternReplicator
from src.deployment.terraform_deployer import deploy_terraform
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph
from src.replicator.modules.graph_structure_analyzer import GraphStructureAnalyzer
from src.replicator.modules.target_graph_builder import TargetGraphBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

SOURCE_SUBSCRIPTION = "<source-subscription-id>"
TARGET_SUBSCRIPTION = "<target-subscription-id>"
TARGET_TENANT = "<tenant-id>"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

DEFAULT_MAX_SCORE = 4.0

# Stable cache path — survives across retries
PLAN_CACHE_FILE = PROJECT_ROOT / "output" / "simple_deployment_plan_cache.json"


# ── Plan cache I/O ─────────────────────────────────────────────────────────────


def save_plan_cache(selected_instances: list[tuple]) -> None:
    """Persist the raw replication plan (all instances) to disk.

    Each instance is stored as {pattern, resources: [{id, name, type, ...}]}.
    """
    PLAN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "pattern": pattern_name,
            "resources": [
                r if isinstance(r, dict) else {"id": r}
                for r in instance
            ],
        }
        for pattern_name, instance in selected_instances
    ]
    with open(PLAN_CACHE_FILE, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "instances": data}, f, indent=2)
    logger.info("Plan cached to %s (%d instances)", PLAN_CACHE_FILE, len(data))


def load_plan_cache() -> list[tuple[str, list[dict]]] | None:
    """Load the cached replication plan from disk.

    Returns list of (pattern_name, resources) tuples, or None if no cache.
    """
    if not PLAN_CACHE_FILE.exists():
        return None
    try:
        with open(PLAN_CACHE_FILE) as f:
            data = json.load(f)
        instances = [(item["pattern"], item["resources"]) for item in data["instances"]]
        logger.info(
            "Loaded cached plan from %s — %d instances (generated %s)",
            PLAN_CACHE_FILE,
            len(instances),
            data.get("generated_at", "unknown"),
        )
        return instances
    except Exception as e:
        logger.warning("Failed to load plan cache: %s — will regenerate.", e)
        return None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _run_az(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run an Azure CLI command and return the result."""
    cmd = ["az"] + args
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def delete_target_resource_groups(dry_run: bool = False) -> int:
    """Delete all resource groups in the target subscription.

    Returns number of resource groups queued for deletion.
    """
    logger.info("Listing resource groups in target subscription %s...", TARGET_SUBSCRIPTION)
    result = _run_az([
        "group", "list",
        "--subscription", TARGET_SUBSCRIPTION,
        "--query", "[].name",
        "-o", "json",
    ])
    groups: list[str] = json.loads(result.stdout)

    if not groups:
        logger.info("No resource groups found in target subscription — nothing to delete.")
        return 0

    logger.info("Found %d resource group(s): %s", len(groups), groups)

    if dry_run:
        logger.info("[DRY RUN] Would delete: %s", groups)
        return len(groups)

    for rg in groups:
        logger.info("Deleting resource group '%s'...", rg)
        _run_az([
            "group", "delete",
            "--name", rg,
            "--subscription", TARGET_SUBSCRIPTION,
            "--yes",
            "--no-wait",
        ])

    logger.info("Waiting for %d resource group(s) to finish deleting...", len(groups))
    _wait_for_rg_deletions(groups)
    return len(groups)


def _wait_for_rg_deletions(expected_deleted: list[str], timeout_s: int = 600, poll_s: int = 15) -> None:
    """Poll until all expected resource groups are gone from the target subscription."""
    deadline = time.time() + timeout_s
    pending = set(expected_deleted)

    while pending and time.time() < deadline:
        time.sleep(poll_s)
        result = _run_az([
            "group", "list",
            "--subscription", TARGET_SUBSCRIPTION,
            "--query", "[].name",
            "-o", "json",
        ], check=False)
        if result.returncode != 0:
            logger.warning("Could not list resource groups during wait: %s", result.stderr[:200])
            continue
        existing = set(json.loads(result.stdout or "[]"))
        still_present = pending & existing
        gone = pending - still_present
        if gone:
            logger.info("Deleted: %s", sorted(gone))
        pending = still_present
        if pending:
            logger.info("Still waiting for %d RG(s): %s", len(pending), sorted(pending))

    if pending:
        logger.warning(
            "Timed out waiting for deletion of: %s — continuing anyway.", sorted(pending)
        )
    else:
        logger.info("All resource groups confirmed deleted.")
    # Grace period: even after RG disappears from `az group list`, Azure may still be
    # finalizing deprovisioning of nested resources (CosmosDB, PostgreSQL, etc.)
    # Waiting here prevents "ResourceGroupBeingDeleted" 409 errors from Terraform.
    if expected_deleted:
        grace = 90
        logger.info("Waiting %ds grace period for Azure to fully deprovision resources...", grace)
        time.sleep(grace)


def _auto_import_existing_resources(terraform_dir: Path, error_output: str) -> int:
    """Parse Terraform 'already exists' errors and import the conflicting resources.

    Returns the number of resources successfully imported.
    """
    import re

    # Match: 'resource with the ID "<azure_id>" already exists'
    # and the corresponding `with <tf_address>,` line
    id_pattern = re.compile(r'resource with the ID "([^"]+)" already exists')
    addr_pattern = re.compile(r'with ([a-z][a-z0-9_.]+),')

    lines = error_output.split("\n")
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        id_match = id_pattern.search(lines[i])
        if id_match:
            azure_id = id_match.group(1)
            # Search next ~10 lines for the `with <address>,` line
            for j in range(i + 1, min(i + 10, len(lines))):
                addr_match = addr_pattern.search(lines[j])
                if addr_match:
                    pairs.append((addr_match.group(1), azure_id))
                    break
        i += 1

    if not pairs:
        return 0

    logger.info("Auto-importing %d already-existing resource(s) into Terraform state", len(pairs))
    imported = 0
    for tf_addr, azure_id in pairs:
        result = subprocess.run(
            ["terraform", f"-chdir={terraform_dir}", "import", tf_addr, azure_id],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("  Imported %s ← %s", tf_addr, azure_id)
            imported += 1
        else:
            logger.warning("  Import failed for %s: %s", tf_addr, result.stderr[-200:])
    return imported


def fetch_full_resources_from_neo4j(
    instance_tuples: list[tuple[str, list[dict[str, Any]]]],
) -> TenantGraph:
    """Query Neo4j for full resource data and relationships for selected instances."""
    all_ids: list[str] = []
    for _pattern, instance in instance_tuples:
        for r in instance:
            if isinstance(r, dict) and "id" in r:
                all_ids.append(r["id"])
            elif isinstance(r, str):
                all_ids.append(r)

    logger.info("Querying Neo4j for %d resource IDs...", len(all_ids))

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    resources: list[dict] = []
    relationships: list[dict] = []

    try:
        with driver.session() as session:
            res = session.run(
                "MATCH (r:Resource:Original) WHERE r.id IN $ids RETURN r",
                ids=all_ids,
            )
            for record in res:
                resources.append(dict(record["r"]))

            res = session.run(
                """
                MATCH (s:Resource:Original)-[rel]->(t:Resource:Original)
                WHERE s.id IN $ids AND t.id IN $ids
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN s.id AS source_id,
                       type(rel) AS rel_type,
                       t.id AS target_id,
                       properties(rel) AS rel_props
                """,
                ids=all_ids,
            )
            for record in res:
                relationships.append({
                    "source_id": record["source_id"],
                    "relationship_type": record["rel_type"],
                    "target_id": record["target_id"],
                    "properties": record["rel_props"],
                })
    finally:
        driver.close()

    logger.info(
        "Retrieved %d resources, %d relationships from Neo4j.",
        len(resources),
        len(relationships),
    )
    return TenantGraph(resources=resources, relationships=relationships)


def compute_incremental_spectral_distances(
    low_complexity_instances: list[tuple[str, list[dict]]],
    replicator: ArchitecturePatternReplicator,
    analyzer: ArchitecturalPatternAnalyzer,
) -> tuple[list[int], list[float]]:
    """Compute spectral distance as we incrementally add each low-complexity instance."""
    graph_analyzer = GraphStructureAnalyzer()
    target_builder = TargetGraphBuilder(analyzer, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    source_graph = replicator.source_pattern_graph
    if source_graph is None:
        raise RuntimeError("source_pattern_graph is None — call analyze_source_tenant() first.")

    cumulative_resources: list[int] = []
    spectral_distances: list[float] = []
    running_instances: list[tuple[str, list[dict]]] = []
    total_resources = 0

    logger.info("Computing incremental spectral distance across %d instances...", len(low_complexity_instances))

    for pattern_name, instance in low_complexity_instances:
        running_instances.append((pattern_name, instance))
        total_resources += len(instance)

        target_graph: nx.MultiDiGraph = target_builder.build_from_instances(running_instances)

        try:
            dist = graph_analyzer.compute_spectral_distance(source_graph, target_graph)
        except Exception as e:
            logger.warning("Spectral distance computation failed at step %d: %s", len(running_instances), e)
            dist = float("nan")

        cumulative_resources.append(total_resources)
        spectral_distances.append(dist)

    return cumulative_resources, spectral_distances


def save_spectral_plot(
    cumulative_resources: list[int],
    spectral_distances: list[float],
    output_dir: Path,
) -> None:
    """Save spectral distance vs resources deployed plot to disk."""
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(
        cumulative_resources,
        spectral_distances,
        marker="o",
        linewidth=2,
        color="#0078D4",
        markersize=5,
        label="Spectral Distance",
    )
    ax.set_xlabel("Cumulative Resources Deployed", fontsize=12)
    ax.set_ylabel("Spectral Distance (source ↔ target)", fontsize=12)
    ax.set_title(
        "Spectral Distance vs. Resources Deployed\n(High-Complexity Instances, score ≥ 4.0)",
        fontsize=13,
    )
    ax.grid(True, alpha=0.3)
    ax.legend()

    if cumulative_resources:
        ax.annotate(
            f"Start\n{spectral_distances[0]:.3f}",
            xy=(cumulative_resources[0], spectral_distances[0]),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=9,
            color="green",
        )
        ax.annotate(
            f"Final\n{spectral_distances[-1]:.3f}",
            xy=(cumulative_resources[-1], spectral_distances[-1]),
            xytext=(-60, 10),
            textcoords="offset points",
            fontsize=9,
            color="red",
        )

    plot_path = output_dir / "spectral_distance_vs_resources.png"
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    logger.info("Spectral distance plot saved to %s", plot_path)


def print_deployment_table(
    instances: list[tuple[str, list[dict]]],
    scores: list[dict],
    max_score: float = DEFAULT_MAX_SCORE,
) -> None:
    """Print a summary table of selected instances."""
    header = f"{'#':>3}  {'Pattern':<30}  {'Score':>6}  {'Resources':>10}  {'Difficulty'}"
    print("\n" + "=" * len(header))
    print("INSTANCES SELECTED FOR DEPLOYMENT")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for i, ((pattern, instance), score) in enumerate(zip(instances, scores), 1):
        band = score.get("difficulty_band", "?")
        combined = score.get("combined_score", 0.0)
        n_res = score.get("resource_count", len(instance))
        flag = " *" if combined >= max_score else ""
        print(f"{i:>3}  {pattern:<30}  {combined:>6.2f}  {n_res:>10}  {band}{flag}")
    print("=" * len(header))
    low = sum(1 for s in scores if s.get("combined_score", 0) < max_score)
    print(f"Total instances: {len(instances)}  ({low} low-complexity <{max_score}, {len(instances)-low} fill-in *)")
    print(f"Total resources: {sum(s.get('resource_count', 0) for s in scores)}")
    print()


# Regions that are internal Microsoft preview regions — not available for
# general deployment. Resources in these regions must be skipped.
_PREVIEW_REGION_MARKERS = ("euap", "stage", "internal")

# Resource types with strict regional quotas, licensing, or soft-delete naming conflicts
# that prevent clean cross-subscription replication.
_QUOTA_RESTRICTED_TYPES = {
    "microsoft.dbforpostgresql/flexibleservers",  # LocationIsOfferRestricted in many regions
    "microsoft.dbformysql/flexibleservers",  # Same quota restrictions as PostgreSQL
    "microsoft.documentdb/databaseaccounts",  # Soft-delete: name reserved for days after RG deletion
}

# Resource types where only 1 instance is allowed per subscription (Azure quota).
# Pattern name → max instances allowed.
_PER_SUBSCRIPTION_LIMITS: dict[str, int] = {
    "Azure Managed Environments": 1,
}


def _is_preview_region(location: str) -> bool:
    loc = location.lower().replace(" ", "")
    return any(marker in loc for marker in _PREVIEW_REGION_MARKERS)


def filter_deployable_instances(
    instances: list[tuple[str, list[dict]]],
) -> list[tuple[str, list[dict]]]:
    """Remove instances that cannot be deployed cross-subscription.

    Filters out:
    - Instances where any resource resides in an internal/preview Azure region
      (e.g., centraluseuap, eastus2euap) not available for general deployment.
    - Instances beyond the per-subscription quota for certain resource types.
    """
    deployable: list[tuple[str, list[dict]]] = []
    pattern_counts: dict[str, int] = {}
    skipped_preview = 0
    skipped_quota: dict[str, int] = {}

    for pattern_name, instance in instances:
        # Check for preview region resources
        has_preview = any(
            _is_preview_region(r.get("location", ""))
            for r in instance
            if isinstance(r, dict)
        )
        if has_preview:
            locations = [r.get("location", "") for r in instance if isinstance(r, dict)]
            logger.info(
                "  Skipping instance of '%s' — preview/internal region(s): %s",
                pattern_name,
                [loc for loc in locations if _is_preview_region(loc)],
            )
            skipped_preview += 1
            continue

        # Check per-subscription quotas
        limit = _PER_SUBSCRIPTION_LIMITS.get(pattern_name)
        if limit is not None:
            count = pattern_counts.get(pattern_name, 0)
            if count >= limit:
                skipped_quota[pattern_name] = skipped_quota.get(pattern_name, 0) + 1
                continue
            pattern_counts[pattern_name] = count + 1
        else:
            pattern_counts[pattern_name] = pattern_counts.get(pattern_name, 0) + 1

        deployable.append((pattern_name, instance))

    if skipped_preview:
        logger.info("Filtered out %d instance(s) in internal/preview regions.", skipped_preview)
    for pat, n in skipped_quota.items():
        logger.info("Filtered out %d '%s' instance(s) over subscription quota.", n, pat)

    return deployable


# ── Main workflow ──────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip actual deployment and deletion")
    parser.add_argument("--max-score", type=float, default=DEFAULT_MAX_SCORE,
                        help=f"Maximum deployment complexity score to include (default: {DEFAULT_MAX_SCORE}). "
                             "Only instances with score strictly below this threshold are deployed.")
    parser.add_argument("--target-resource-count", type=int, default=500,
                        help="Target total resources to deploy (default: 500). "
                             "Low-complexity instances (< max-score) are prioritised; "
                             "higher-complexity instances fill the gap if needed.")
    parser.add_argument("--target-instance-count", type=int, default=None,
                        help="Max instances to consider from replication plan (default: all)")
    parser.add_argument("--refresh-plan", action="store_true",
                        help="Ignore cached plan and regenerate from Neo4j")
    parser.add_argument("--skip-delete", action="store_true",
                        help="Skip deleting existing target resources")
    parser.add_argument("--skip-spectral", action="store_true",
                        help="Skip incremental spectral distance computation (faster)")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "output" / f"simple_deployment_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory: %s", output_dir)

    # ── Steps 1-2: Analyze + generate plan (or load from cache) ───────────────
    replicator = ArchitecturePatternReplicator(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    analyzer = ArchitecturalPatternAnalyzer(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    selected_instances: list[tuple[str, list[dict]]] | None = None

    if not args.refresh_plan:
        selected_instances = load_plan_cache()

    if selected_instances is None:
        # ── Step 1: Analyze source tenant ─────────────────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 1: Analyzing source tenant (%s)...", SOURCE_SUBSCRIPTION)
        logger.info("=" * 70)

        analysis_summary = replicator.analyze_source_tenant(
            use_configuration_coherence=True,
            coherence_threshold=0.7,
            include_colocated_orphaned_resources=True,
        )
        logger.info(
            "Detected %d patterns, %d resource types, %d total resources.",
            analysis_summary["detected_patterns"],
            analysis_summary["resource_types"],
            analysis_summary["total_pattern_resources"],
        )

        # ── Step 2: Generate replication plan ─────────────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 2: Generating replication plan...")
        logger.info("=" * 70)

        raw_instances, _spectral_history, _ = replicator.generate_replication_plan(
            target_instance_count=args.target_instance_count,
            include_orphaned_node_patterns=True,
            use_architecture_distribution=True,
            use_configuration_coherence=True,
            use_spectral_guidance=True,
        )
        logger.info("Plan contains %d instances.", len(raw_instances))

        # Normalise to list[tuple[str, list[dict]]] and cache
        selected_instances = [
            (pattern, [r if isinstance(r, dict) else {"id": r} for r in inst])
            for pattern, inst in raw_instances
        ]
        save_plan_cache(selected_instances)
    else:
        logger.info("STEP 1-2: Using cached plan — skipping analysis and plan generation.")
        # Still need source_pattern_graph for spectral computation; run analyze_source_tenant
        # only if spectral distances are requested.
        if not args.skip_spectral:
            logger.info("Running analyze_source_tenant() to obtain source pattern graph for spectral distances...")
            replicator.analyze_source_tenant(
                use_configuration_coherence=True,
                coherence_threshold=0.7,
                include_colocated_orphaned_resources=True,
            )

    # ── Step 3: Score all instances, build prioritised selection ──────────────
    logger.info("=" * 70)
    logger.info(
        "STEP 3: Scoring instances — targeting %d resources (max score %.1f preferred)...",
        args.target_resource_count,
        args.max_score,
    )
    logger.info("=" * 70)

    # Score every instance in the plan
    all_scored: list[tuple[str, list[dict], dict]] = []
    for pattern_name, instance in selected_instances:
        score = analyzer.score_instance_deployment(instance)  # type: ignore[arg-type]
        all_scored.append((pattern_name, instance, score))

    # Sort ascending by score so low-complexity instances come first
    all_scored.sort(key=lambda x: x[2]["combined_score"])

    # Greedily select instances until we hit the target resource count.
    # Instances with score < max_score are always included first; higher-scored
    # ones pad the remainder up to target_resource_count.
    low_complexity: list[tuple[str, list[dict]]] = []
    low_scores: list[dict] = []
    total_resources = 0

    for pattern_name, instance, score in all_scored:
        if total_resources >= args.target_resource_count:
            break
        # Always include if score < max_score; include higher-scored to fill gap
        low_complexity.append((pattern_name, instance))
        low_scores.append(score)
        total_resources += score.get("resource_count", len(instance))

    low_score_count = sum(1 for s in low_scores if s["combined_score"] < args.max_score)
    logger.info(
        "Selected %d instances (%d with score < %.1f, %d fill-in) = %d resources.",
        len(low_complexity),
        low_score_count,
        args.max_score,
        len(low_complexity) - low_score_count,
        total_resources,
    )

    if not low_complexity:
        logger.warning("No instances selected. Check --target-resource-count or plan cache.")
        return 1

    # ── Step 3b: Filter out non-deployable instances ──────────────────────────
    logger.info("=" * 70)
    logger.info("STEP 3b: Filtering out preview-region and over-quota instances...")
    logger.info("=" * 70)

    before = len(low_complexity)
    deployable_instances = filter_deployable_instances(low_complexity)
    # Match by identity of the inner resource list (not the tuple, which is re-created)
    deployable_inst_ids = {id(inst_list) for _, inst_list in deployable_instances}
    paired_filtered = [
        ((pname, inst_list), score)
        for (pname, inst_list), score in zip(low_complexity, low_scores)
        if id(inst_list) in deployable_inst_ids
    ]
    low_complexity = [p[0] for p in paired_filtered]
    low_scores = [p[1] for p in paired_filtered]
    logger.info(
        "Deployable instances: %d (filtered out %d).",
        len(low_complexity),
        before - len(low_complexity),
    )

    if not low_complexity:
        logger.error("No deployable instances remain after filtering. Exiting.")
        return 1

    print_deployment_table(low_complexity, low_scores, max_score=args.max_score)

    # Save filtered plan alongside timestamped output
    plan_path = output_dir / "filtered_low_complexity_plan.json"
    with open(plan_path, "w") as f:
        json.dump(
            [
                {
                    "pattern": p,
                    "resource_count": len(inst),
                    "score": s,
                    "resource_ids": [r.get("id", r) if isinstance(r, dict) else r for r in inst],
                }
                for (p, inst), s in zip(low_complexity, low_scores)
            ],
            f,
            indent=2,
        )
    logger.info("Filtered plan saved to %s", plan_path)

    # ── Step 4: Compute spectral distance evolution ───────────────────────────
    cumulative_resources: list[int] = []
    spectral_distances: list[float] = []

    if not args.skip_spectral:
        logger.info("=" * 70)
        logger.info("STEP 4: Computing incremental spectral distances...")
        logger.info("=" * 70)

        cumulative_resources, spectral_distances = compute_incremental_spectral_distances(
            low_complexity, replicator, analyzer
        )
        save_spectral_plot(cumulative_resources, spectral_distances, output_dir)

        spectral_data_path = output_dir / "spectral_distance_data.json"
        with open(spectral_data_path, "w") as f:
            json.dump(
                {"cumulative_resources": cumulative_resources, "spectral_distances": spectral_distances},
                f, indent=2,
            )
        logger.info("Spectral data saved to %s", spectral_data_path)
    else:
        logger.info("STEP 4: Skipped (--skip-spectral)")

    # ── Step 5: Delete existing target resources ──────────────────────────────
    if not args.skip_delete:
        logger.info("=" * 70)
        logger.info("STEP 5: Deleting existing resources in target subscription...")
        logger.info("=" * 70)
        deleted = delete_target_resource_groups(dry_run=args.dry_run)
        logger.info("Queued deletion of %d resource group(s).", deleted)
    else:
        logger.info("STEP 5: Skipped (--skip-delete)")

    # ── Step 6: Deploy ─────────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("STEP 6: Deploying %d low-complexity instances...", len(low_complexity))
    logger.info("=" * 70)

    if args.dry_run:
        logger.info("[DRY RUN] Skipping actual deployment.")
        logger.info(
            "Would deploy %d instances (%d total resources) to subscription %s.",
            len(low_complexity),
            sum(s.get("resource_count", 0) for s in low_scores),
            TARGET_SUBSCRIPTION,
        )
        return 0

    # Build TenantGraph from Neo4j (full resource properties including location)
    tenant_graph = fetch_full_resources_from_neo4j(low_complexity)

    if not tenant_graph.resources:
        logger.error(
            "No resources found in Neo4j for the selected instances. "
            "Make sure the source subscription scan is in Neo4j (run --refresh-plan if needed)."
        )
        return 1

    # Remove resources in internal/preview regions from the TenantGraph.
    # These have location fields like "centraluseuap" that Azure rejects for our subscription.
    before_count = len(tenant_graph.resources)
    preview_ids: set[str] = set()
    for r in tenant_graph.resources:
        loc = r.get("location", "")
        if loc and _is_preview_region(loc):
            preview_ids.add(r.get("id", ""))
            logger.debug("Dropping preview-region resource: %s (%s)", r.get("name", "?"), loc)

    # Also skip quota-restricted resource types
    for r in tenant_graph.resources:
        rtype = r.get("type", "").lower()
        if rtype in _QUOTA_RESTRICTED_TYPES:
            preview_ids.add(r.get("id", ""))
            logger.debug("Dropping quota-restricted resource type: %s (%s)", r.get("name", "?"), rtype)

    if preview_ids:
        tenant_graph.resources = [r for r in tenant_graph.resources if r.get("id") not in preview_ids]
        tenant_graph.relationships = [
            rel for rel in tenant_graph.relationships
            if rel.get("source_id") not in preview_ids and rel.get("target_id") not in preview_ids
        ]
        logger.info(
            "Removed %d resource(s) in preview regions or with quota restrictions. Remaining: %d",
            before_count - len(tenant_graph.resources),
            len(tenant_graph.resources),
        )

    terraform_dir = output_dir / "terraform"
    terraform_dir.mkdir(exist_ok=True)

    # Don't pass explicit resource_name_mappings — resource types with strict naming
    # constraints (Container Registry: alphanumeric-only, Key Vault, etc.) already have
    # their own per-type unique-suffix logic in the emitter handlers.
    emitter = TerraformEmitter(
        target_subscription_id=TARGET_SUBSCRIPTION,
        source_subscription_id=SOURCE_SUBSCRIPTION,
        auto_import_existing=False,
        target_tenant_id=TARGET_TENANT,
    )

    generated_files = emitter.emit(
        graph=tenant_graph,
        out_dir=terraform_dir,
        subscription_id=TARGET_SUBSCRIPTION,
    )
    logger.info("Generated %d Terraform files in %s", len(generated_files), terraform_dir)

    try:
        deployment_result = deploy_terraform(
            iac_dir=terraform_dir,
            resource_group="simple-architecture-replication",
            location="eastus",
            dry_run=False,
            subscription_id=TARGET_SUBSCRIPTION,
            verbose=True,
        )
        deployment_status = deployment_result.get("status", "unknown")
    except RuntimeError as exc:
        # deploy_terraform raises on any terraform error, even partial apply.
        error_str = str(exc)
        # Auto-import any resources that already exist in Azure but not in state, then retry.
        imported = _auto_import_existing_resources(terraform_dir, error_str)
        # Also wait if any RG is still deprovisioning
        if "ResourceGroupBeingDeleted" in error_str or "deprovisioning state" in error_str:
            logger.warning("Azure RG still deprovisioning — waiting 120s before retry...")
            time.sleep(120)
            imported = max(imported, 1)  # force a retry

        if imported > 0:
            # Import any already-existing resources from the retry error too
            _auto_import_existing_resources(terraform_dir, error_str)
            logger.info("Retrying terraform apply after importing %d resource(s)...", imported)
            try:
                deployment_result = deploy_terraform(
                    iac_dir=terraform_dir,
                    resource_group="simple-architecture-replication",
                    location="eastus",
                    dry_run=False,
                    subscription_id=TARGET_SUBSCRIPTION,
                    verbose=True,
                )
                deployment_status = deployment_result.get("status", "unknown")
                error_str = ""
            except RuntimeError as exc2:
                error_str = str(exc2)
                logger.warning("Terraform reported errors after import retry: %s", error_str[:500])
                deployment_result = {"status": "partial", "output": error_str}
                deployment_status = "partial"
        else:
            logger.warning("Terraform reported errors (may be partial success): %s", error_str[:500])
            deployment_result = {"status": "partial", "output": error_str}
            deployment_status = "partial"
    logger.info("Deployment status: %s", deployment_status)

    # Save deployment summary
    summary = {
        "timestamp": timestamp,
        "source_subscription": SOURCE_SUBSCRIPTION,
        "target_subscription": TARGET_SUBSCRIPTION,
        "target_tenant": TARGET_TENANT,
        "max_score_threshold": args.max_score,
        "instances_deployed": len(low_complexity),
        "total_resources": sum(s.get("resource_count", 0) for s in low_scores),
        "mean_score": sum(s.get("combined_score", 0) for s in low_scores) / max(len(low_scores), 1),
        "deployment_status": deployment_status,
        "spectral_distance_initial": spectral_distances[0] if spectral_distances else None,
        "spectral_distance_final": spectral_distances[-1] if spectral_distances else None,
        "terraform_output": deployment_result.get("output", ""),
    }
    summary_path = output_dir / "deployment_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Deployment summary saved to %s", summary_path)

    # ── Final report ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("DEPLOYMENT COMPLETE")
    print("=" * 70)
    print(f"  Status:              {deployment_status.upper()}")
    print(f"  Instances deployed:  {len(low_complexity)}")
    print(f"  Resources deployed:  {sum(s.get('resource_count', 0) for s in low_scores)}")
    if spectral_distances:
        print(f"  Spectral distance:   {spectral_distances[0]:.4f} → {spectral_distances[-1]:.4f}")
    print(f"  Output directory:    {output_dir}")
    if not args.skip_spectral:
        print(f"  Plot:                {output_dir / 'spectral_distance_vs_resources.png'}")
    print("=" * 70)

    return 0 if deployment_status in ("success", "completed", "deployed") else 1


if __name__ == "__main__":
    sys.exit(main())
