#!/usr/bin/env python3
"""
Full Tenant Replication - Complete Resource Copy

This script performs a complete, full replication of all resources from a source
subscription to a target subscription. Unlike architecture-based replication which
selectively chooses instances based on patterns, this script replicates EVERYTHING.

Usage:
    python scripts/full_tenant_replication.py \
        --source-subscription SOURCE_ID \
        --target-subscription TARGET_ID \
        --output-dir ./output/full_replication

Philosophy:
- Ruthless simplicity: Direct query → generate → deploy workflow
- Zero-BS: No pattern analysis, no selective filtering
- Complete replication: Every single resource from source
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from neo4j import GraphDatabase
from src.deployment.terraform_deployer import deploy_terraform
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class FullReplicationResult:
    """Result of full tenant replication."""

    success: bool
    source_subscription: str
    target_subscription: str
    total_resources: int
    total_relationships: int
    terraform_dir: Path
    deployment_status: str
    timestamp: str
    errors: List[str]


class FullTenantReplicator:
    """Performs complete tenant replication without filtering."""

    def __init__(
        self,
        source_subscription: str,
        target_subscription: str,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        output_dir: Path,
    ):
        """Initialize full tenant replicator.

        Args:
            source_subscription: Source subscription ID
            target_subscription: Target subscription ID
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            output_dir: Output directory for Terraform and results
        """
        self.source_subscription = source_subscription
        self.target_subscription = target_subscription
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.output_dir = output_dir
        self.errors = []

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def replicate(self) -> FullReplicationResult:
        """Execute full replication workflow.

        Returns:
            FullReplicationResult with complete status
        """
        try:
            # STEP 1: Query ALL resources from Neo4j
            logger.info("=" * 80)
            logger.info("STEP 1: Querying ALL resources from source subscription...")
            logger.info("=" * 80)
            logger.info(f"Source subscription: {self.source_subscription}")

            tenant_graph = self._fetch_all_resources()

            logger.info(f"Retrieved {len(tenant_graph.resources)} resources")
            logger.info(f"Retrieved {len(tenant_graph.relationships)} relationships")

            # STEP 2: Generate Terraform IaC for ALL resources
            logger.info("\n" + "=" * 80)
            logger.info("STEP 2: Generating Terraform IaC for all resources...")
            logger.info("=" * 80)

            terraform_dir = self.output_dir / "terraform"
            terraform_dir.mkdir(exist_ok=True, parents=True)

            emitter = TerraformEmitter(
                target_subscription_id=self.target_subscription,
                source_subscription_id=self.source_subscription,
                auto_import_existing=False,
            )

            generated_files = emitter.emit(
                graph=tenant_graph,
                out_dir=terraform_dir,
                subscription_id=self.target_subscription,
            )

            logger.info(f"Generated {len(generated_files)} Terraform files")

            # STEP 3: Deploy to target subscription
            logger.info("\n" + "=" * 80)
            logger.info("STEP 3: Deploying to target subscription...")
            logger.info("=" * 80)
            logger.info(f"Target subscription: {self.target_subscription}")

            deployment_result = deploy_terraform(
                iac_dir=terraform_dir,
                resource_group="full-tenant-replication",
                location="eastus",
                dry_run=False,
                subscription_id=self.target_subscription,
                verbose=True,
            )

            logger.info(f"Deployment status: {deployment_result['status']}")

            # STEP 4: Generate summary report
            logger.info("\n" + "=" * 80)
            logger.info("STEP 4: Generating summary report...")
            logger.info("=" * 80)

            report = self._generate_report(
                tenant_graph, terraform_dir, deployment_result
            )

            report_file = self.output_dir / "REPLICATION_REPORT.md"
            with open(report_file, "w") as f:
                f.write(report)

            logger.info(f"Report saved to {report_file}")

            logger.info("\n" + "=" * 80)
            logger.info("FULL REPLICATION COMPLETE!")
            logger.info("=" * 80)

            return FullReplicationResult(
                success=True,
                source_subscription=self.source_subscription,
                target_subscription=self.target_subscription,
                total_resources=len(tenant_graph.resources),
                total_relationships=len(tenant_graph.relationships),
                terraform_dir=terraform_dir,
                deployment_status=deployment_result["status"],
                timestamp=datetime.now(timezone.utc).isoformat(),
                errors=self.errors,
            )

        except Exception as e:
            logger.error(f"Replication failed: {e}", exc_info=True)
            self.errors.append(str(e))

            return FullReplicationResult(
                success=False,
                source_subscription=self.source_subscription,
                target_subscription=self.target_subscription,
                total_resources=0,
                total_relationships=0,
                terraform_dir=Path(),
                deployment_status="failed",
                timestamp=datetime.now(timezone.utc).isoformat(),
                errors=self.errors,
            )

    def _fetch_all_resources(self) -> TenantGraph:
        """Fetch ALL resources from source subscription in Neo4j.

        Returns:
            TenantGraph with all resources and relationships
        """
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        resources = []
        relationships = []

        try:
            with driver.session() as session:
                # Fetch ALL resources from source subscription
                result = session.run(
                    """
                    MATCH (r:Resource:Original)
                    WHERE r.subscription_id = $subscription_id
                    RETURN r
                    """,
                    subscription_id=self.source_subscription,
                )

                for record in result:
                    resource_dict = dict(record["r"])
                    resources.append(resource_dict)

                logger.info(f"Fetched {len(resources)} resources from Neo4j")

                # Fetch ALL relationships between these resources
                result = session.run(
                    """
                    MATCH (source:Resource:Original)-[rel]->(target:Resource:Original)
                    WHERE source.subscription_id = $subscription_id
                      AND target.subscription_id = $subscription_id
                      AND type(rel) <> 'SCAN_SOURCE_NODE'
                    RETURN source.id as source_id,
                           type(rel) as rel_type,
                           target.id as target_id,
                           properties(rel) as rel_props
                    """,
                    subscription_id=self.source_subscription,
                )

                for record in result:
                    relationships.append(
                        {
                            "source_id": record["source_id"],
                            "relationship_type": record["rel_type"],
                            "target_id": record["target_id"],
                            "properties": record["rel_props"],
                        }
                    )

                logger.info(f"Fetched {len(relationships)} relationships from Neo4j")

        finally:
            driver.close()

        return TenantGraph(resources=resources, relationships=relationships)

    def _generate_report(
        self,
        tenant_graph: TenantGraph,
        terraform_dir: Path,
        deployment_result: Dict[str, Any],
    ) -> str:
        """Generate markdown summary report.

        Args:
            tenant_graph: Complete tenant graph
            terraform_dir: Terraform output directory
            deployment_result: Deployment result dictionary

        Returns:
            Markdown report string
        """
        report = f"""# Full Tenant Replication Report

**Generated:** {datetime.now(timezone.utc).isoformat()}

**Source Subscription:** `{self.source_subscription}`
**Target Subscription:** `{self.target_subscription}`

---

## Executive Summary

Complete replication of ALL resources from source to target subscription.

- **Total Resources:** {len(tenant_graph.resources)}
- **Total Relationships:** {len(tenant_graph.relationships)}
- **Deployment Status:** {deployment_result.get('status', 'unknown').upper()}
- **Terraform Directory:** `{terraform_dir}`

---

## Resource Breakdown

"""

        # Count resources by type
        type_counts = {}
        for resource in tenant_graph.resources:
            res_type = resource.get("type", "unknown")
            type_counts[res_type] = type_counts.get(res_type, 0) + 1

        report += "### Resources by Type\n\n"
        for res_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            report += f"- **{res_type}**: {count}\n"

        report += f"""

---

## Deployment Details

- **Status:** {deployment_result.get('status', 'unknown')}
- **Terraform Directory:** `{terraform_dir}`
- **Timestamp:** {datetime.now(timezone.utc).isoformat()}

---

## Errors and Warnings

"""

        if self.errors:
            for error in self.errors:
                report += f"- {error}\n"
        else:
            report += "None\n"

        report += """

---

*Generated by Full Tenant Replicator*
"""

        return report


async def main():
    """Main entry point for CLI execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Full tenant replication - copy ALL resources"
    )
    parser.add_argument(
        "--source-subscription",
        required=True,
        help="Source subscription ID",
    )
    parser.add_argument(
        "--target-subscription",
        required=True,
        help="Target subscription ID",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output/full_replication"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j URI",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.getenv("NEO4J_USER", "neo4j"),
        help="Neo4j username",
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.getenv("NEO4J_PASSWORD", "password"),
        help="Neo4j password",
    )

    args = parser.parse_args()

    # Create replicator
    replicator = FullTenantReplicator(
        source_subscription=args.source_subscription,
        target_subscription=args.target_subscription,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        output_dir=args.output_dir,
    )

    # Execute replication
    result = await replicator.replicate()

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    asyncio.run(main())
