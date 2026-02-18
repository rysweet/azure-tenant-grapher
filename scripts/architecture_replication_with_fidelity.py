#!/usr/bin/env python3
"""
Architecture-Based Tenant Replication with Fidelity Validation

This script orchestrates the complete workflow:
1. Analyze source tenant using ArchitecturalPatternAnalyzer
2. Generate replication plan using ArchitecturePatternReplicator
3. Store source-to-target resource mappings
4. Deploy resources to target tenant
5. Validate fidelity using explicit source-target mappings
6. Generate comprehensive fidelity report

Usage:
    python scripts/architecture_replication_with_fidelity.py \\
        --source-subscription SOURCE_ID \\
        --target-subscription TARGET_ID \\
        --target-instance-count 10 \\
        --output-dir ./output/replication_run_001

Philosophy:
- Ruthless simplicity: Single script orchestrates entire workflow
- Zero-BS: No stubs, fully functional from end to end
- Modular design: Delegates to existing bricks (analyzer, replicator, fidelity calculator)
- Regeneratable: Can be run multiple times with different parameters
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.architectural_pattern_analyzer import ArchitecturalPatternAnalyzer
from src.architecture_based_replicator import ArchitecturePatternReplicator
from src.config_manager import Neo4jConfig
from src.deployment.terraform_deployer import deploy_terraform
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph
from src.replicator.modules.target_graph_builder import TargetGraphBuilder
from src.utils.session_manager import Neo4jSessionManager
from src.validation.resource_fidelity_calculator import (
    RedactionLevel,
    ResourceFidelityCalculator,
)
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ReplicationMapping:
    """Tracks mapping between source and target resources."""

    source_resource_id: str
    source_resource_name: str
    source_resource_type: str
    target_resource_id: str
    target_resource_name: str
    target_resource_type: str
    pattern_name: str
    configuration_fingerprint: Dict[str, Any] = field(default_factory=dict)
    deployment_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ReplicationResult:
    """Complete replication workflow result."""

    success: bool
    source_subscription: str
    target_subscription: str
    analysis_summary: Dict[str, Any]
    replication_plan_summary: Dict[str, Any]
    mappings: List[ReplicationMapping]
    deployment_summary: Dict[str, Any]
    fidelity_result: Any  # FidelityResult from ResourceFidelityCalculator
    output_dir: Path
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ArchitectureReplicationOrchestrator:
    """Orchestrates architecture-based replication with fidelity validation."""

    def __init__(
        self,
        source_subscription: str,
        target_subscription: str,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        output_dir: Path,
    ):
        """Initialize orchestrator.

        Args:
            source_subscription: Source subscription ID
            target_subscription: Target subscription ID
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            output_dir: Output directory for results
        """
        self.source_subscription = source_subscription
        self.target_subscription = target_subscription
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.output_dir = output_dir

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.analyzer = ArchitecturalPatternAnalyzer(neo4j_uri, neo4j_user, neo4j_password)
        self.replicator = ArchitecturePatternReplicator(neo4j_uri, neo4j_user, neo4j_password)

        # Tracking
        self.mappings: List[ReplicationMapping] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    async def run_complete_workflow(
        self,
        target_instance_count: Optional[int] = None,
        use_configuration_coherence: bool = True,
        coherence_threshold: float = 0.7,
        include_orphaned_resources: bool = True,
        use_spectral_guidance: bool = True,
        redaction_level: RedactionLevel = RedactionLevel.FULL,
    ) -> ReplicationResult:
        """Run complete replication and validation workflow.

        Args:
            target_instance_count: Number of instances to replicate (None = all)
            use_configuration_coherence: Enable configuration-based clustering
            coherence_threshold: Minimum similarity for clustering (0.0-1.0)
            include_orphaned_resources: Include orphaned resource types
            use_spectral_guidance: Use spectral distance for selection
            redaction_level: Security redaction level for fidelity validation

        Returns:
            ReplicationResult with complete workflow results
        """
        try:
            # STEP 1: Analyze source tenant
            logger.info("=" * 80)
            logger.info("STEP 1: Analyzing source tenant for architectural patterns...")
            logger.info("=" * 80)

            analysis_summary = self.replicator.analyze_source_tenant(
                use_configuration_coherence=use_configuration_coherence,
                coherence_threshold=coherence_threshold,
                include_colocated_orphaned_resources=include_orphaned_resources,
            )

            logger.info(f"Analysis complete:")
            logger.info(f"  - Detected patterns: {analysis_summary['detected_patterns']}")
            logger.info(f"  - Resource types: {analysis_summary['resource_types']}")
            logger.info(f"  - Total resources: {analysis_summary['total_pattern_resources']}")

            # Save analysis summary
            analysis_file = self.output_dir / "01_analysis_summary.json"
            with open(analysis_file, "w") as f:
                json.dump(analysis_summary, f, indent=2)
            logger.info(f"Analysis summary saved to {analysis_file}")

            # STEP 2: Generate replication plan
            logger.info("\n" + "=" * 80)
            logger.info("STEP 2: Generating replication plan...")
            logger.info("=" * 80)

            selected_instances, spectral_history, distribution_metadata = self.replicator.generate_replication_plan(
                target_instance_count=target_instance_count,
                include_orphaned_node_patterns=include_orphaned_resources,
                use_architecture_distribution=True,
                use_configuration_coherence=use_configuration_coherence,
                use_spectral_guidance=use_spectral_guidance,
            )

            logger.info(f"Replication plan generated:")
            logger.info(f"  - Selected instances: {len(selected_instances)}")
            logger.info(f"  - Patterns covered: {len(set(p[0] for p in selected_instances))}")

            # Build replication plan summary
            plan_summary = {
                "total_instances": len(selected_instances),
                "patterns": {},
                "spectral_distance_history": spectral_history,
                "distribution_metadata": distribution_metadata,
            }

            # Count resources by pattern
            for pattern_name, instances in selected_instances:
                resource_count = sum(len(inst) for inst in instances)
                plan_summary["patterns"][pattern_name] = {
                    "instance_count": len(instances),
                    "resource_count": resource_count,
                }

            # Save replication plan
            plan_file = self.output_dir / "02_replication_plan.json"
            with open(plan_file, "w") as f:
                json.dump(plan_summary, f, indent=2)
            logger.info(f"Replication plan saved to {plan_file}")

            # STEP 3: Create source-target mappings
            logger.info("\n" + "=" * 80)
            logger.info("STEP 3: Creating source-to-target resource mappings...")
            logger.info("=" * 80)

            self._create_resource_mappings(selected_instances)

            logger.info(f"Created {len(self.mappings)} resource mappings")

            # Save mappings
            mappings_file = self.output_dir / "03_resource_mappings.json"
            with open(mappings_file, "w") as f:
                mappings_data = [
                    {
                        "source_id": m.source_resource_id,
                        "source_name": m.source_resource_name,
                        "source_type": m.source_resource_type,
                        "target_id": m.target_resource_id,
                        "target_name": m.target_resource_name,
                        "target_type": m.target_resource_type,
                        "pattern": m.pattern_name,
                        "timestamp": m.deployment_timestamp,
                    }
                    for m in self.mappings
                ]
                json.dump(mappings_data, f, indent=2)
            logger.info(f"Resource mappings saved to {mappings_file}")

            # STEP 4: Deploy resources (actual deployment via Terraform)
            logger.info("\n" + "=" * 80)
            logger.info("STEP 4: Deploying resources to target tenant...")
            logger.info("=" * 80)

            deployment_summary = await self._deploy_resources(selected_instances)

            # STEP 4.5: Store REPLICATED_FROM relationships in Neo4j
            logger.info("\n" + "=" * 80)
            logger.info("STEP 4.5: Storing REPLICATED_FROM relationships in Neo4j...")
            logger.info("=" * 80)
            stored_mappings = await self._store_replication_relationships()
            logger.info(f"Stored {stored_mappings} REPLICATED_FROM relationships in Neo4j")

            logger.info(f"Deployment summary:")
            logger.info(f"  - Status: {deployment_summary['status']}")
            logger.info(f"  - Resources deployed: {deployment_summary['resources_deployed']}")

            # Save deployment summary
            deployment_file = self.output_dir / "04_deployment_summary.json"
            with open(deployment_file, "w") as f:
                json.dump(deployment_summary, f, indent=2)
            logger.info(f"Deployment summary saved to {deployment_file}")

            # STEP 4.6: Scan target subscription into Neo4j for fidelity validation
            logger.info("\n" + "=" * 80)
            logger.info("STEP 4.6: Scanning target subscription into Neo4j...")
            logger.info("=" * 80)
            await self._scan_target_subscription()

            # STEP 5: Validate fidelity with explicit mappings
            logger.info("\n" + "=" * 80)
            logger.info("STEP 5: Validating fidelity using source-target mappings...")
            logger.info("=" * 80)

            fidelity_result = await self._validate_fidelity_with_mappings(redaction_level)

            logger.info(f"Fidelity validation complete:")
            logger.info(f"  - Total resources: {fidelity_result.metrics.total_resources}")
            logger.info(f"  - Exact match: {fidelity_result.metrics.exact_match}")
            logger.info(f"  - Drifted: {fidelity_result.metrics.drifted}")
            logger.info(f"  - Match percentage: {fidelity_result.metrics.match_percentage:.1f}%")

            # Save fidelity result
            fidelity_file = self.output_dir / "05_fidelity_validation.json"
            with open(fidelity_file, "w") as f:
                fidelity_data = {
                    "metadata": {
                        "timestamp": fidelity_result.validation_timestamp,
                        "source_subscription": fidelity_result.source_subscription,
                        "target_subscription": fidelity_result.target_subscription,
                        "redaction_level": fidelity_result.redaction_level.value,
                    },
                    "summary": {
                        "total_resources": fidelity_result.metrics.total_resources,
                        "exact_match": fidelity_result.metrics.exact_match,
                        "drifted": fidelity_result.metrics.drifted,
                        "missing_target": fidelity_result.metrics.missing_target,
                        "missing_source": fidelity_result.metrics.missing_source,
                        "match_percentage": fidelity_result.metrics.match_percentage,
                    },
                    "resources": [
                        {
                            "id": c.resource_id,
                            "name": c.resource_name,
                            "type": c.resource_type,
                            "status": c.status.value,
                            "mismatch_count": c.mismatch_count,
                        }
                        for c in fidelity_result.classifications
                    ],
                }
                json.dump(fidelity_data, f, indent=2)
            logger.info(f"Fidelity validation saved to {fidelity_file}")

            # STEP 6: Generate comprehensive report
            logger.info("\n" + "=" * 80)
            logger.info("STEP 6: Generating comprehensive report...")
            logger.info("=" * 80)

            report = self._generate_comprehensive_report(
                analysis_summary,
                plan_summary,
                deployment_summary,
                fidelity_result,
            )

            report_file = self.output_dir / "00_COMPREHENSIVE_REPORT.md"
            with open(report_file, "w") as f:
                f.write(report)
            logger.info(f"Comprehensive report saved to {report_file}")

            logger.info("\n" + "=" * 80)
            logger.info("WORKFLOW COMPLETE!")
            logger.info("=" * 80)
            logger.info(f"All results saved to: {self.output_dir}")

            return ReplicationResult(
                success=True,
                source_subscription=self.source_subscription,
                target_subscription=self.target_subscription,
                analysis_summary=analysis_summary,
                replication_plan_summary=plan_summary,
                mappings=self.mappings,
                deployment_summary=deployment_summary,
                fidelity_result=fidelity_result,
                output_dir=self.output_dir,
                errors=self.errors,
                warnings=self.warnings,
            )

        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            self.errors.append(f"Workflow error: {str(e)}")

            return ReplicationResult(
                success=False,
                source_subscription=self.source_subscription,
                target_subscription=self.target_subscription,
                analysis_summary={},
                replication_plan_summary={},
                mappings=self.mappings,
                deployment_summary={"status": "failed", "error": str(e)},
                fidelity_result=None,
                output_dir=self.output_dir,
                errors=self.errors,
                warnings=self.warnings,
            )

    def _create_resource_mappings(self, selected_instances: List[tuple]) -> None:
        """Create source-to-target resource mappings from replication plan.

        Args:
            selected_instances: List of (pattern_name, instances) tuples
        """
        for pattern_name, instances in selected_instances:
            for instance in instances:
                for resource in instance:
                    # Handle both dict and string (resource ID) formats
                    if isinstance(resource, dict):
                        source_id = resource.get("id", "")
                        source_name = resource.get("name", "")
                        source_type = resource.get("type", "")
                    elif isinstance(resource, str):
                        # Resource is just an ID string - skip for mapping
                        # (we need full resource metadata for proper mapping)
                        continue
                    else:
                        # Unknown format - skip
                        continue

                    # Generate target name (append suffix for uniqueness)
                    target_name = f"{source_name}-replica"
                    target_id = source_id.replace(self.source_subscription, self.target_subscription)
                    target_id = target_id.replace(source_name, target_name)

                    mapping = ReplicationMapping(
                        source_resource_id=source_id,
                        source_resource_name=source_name,
                        source_resource_type=source_type,
                        target_resource_id=target_id,
                        target_resource_name=target_name,
                        target_resource_type=source_type,
                        pattern_name=pattern_name,
                        configuration_fingerprint=resource.get("configuration", {}),
                    )

                    self.mappings.append(mapping)

    async def _deploy_resources(self, selected_instances: List[tuple]) -> Dict[str, Any]:
        """Deploy resources to target tenant.

        Generates Terraform IaC from replication plan and deploys to target subscription.

        Args:
            selected_instances: Selected instances from replication plan

        Returns:
            Deployment summary dictionary with status, resources_deployed, and terraform_dir
        """
        logger.info("================================================================================")
        logger.info("Starting actual resource deployment to target tenant...")
        logger.info("================================================================================")

        # Step 1: Fetch full resource data from Neo4j for selected instances
        logger.info("Step 1: Fetching full resource data from Neo4j...")
        tenant_graph = await self._build_tenant_graph_from_instances(selected_instances)
        logger.info(f"  Fetched {len(tenant_graph.resources)} resources with {len(tenant_graph.relationships)} relationships")

        # Step 2: Generate Terraform IaC
        logger.info("Step 2: Generating Terraform IaC...")
        terraform_dir = self.output_dir / "terraform"
        terraform_dir.mkdir(exist_ok=True, parents=True)

        # Convert mappings to format expected by emitter: {source_id: target_name}
        resource_name_mappings = {
            mapping.source_resource_id: mapping.target_resource_name
            for mapping in self.mappings
        }
        logger.info(f"Passing {len(resource_name_mappings)} resource name mappings to emitter")

        emitter = TerraformEmitter(
            target_subscription_id=self.target_subscription,
            source_subscription_id=self.source_subscription,
            auto_import_existing=False,  # Don't import existing resources for replication
            resource_name_mappings=resource_name_mappings,  # Pass mappings for "-replica" suffix
        )

        generated_files = emitter.emit(
            graph=tenant_graph,
            out_dir=terraform_dir,
            subscription_id=self.target_subscription,
        )
        logger.info(f"  Generated {len(generated_files)} Terraform files in {terraform_dir}")

        # Step 3: Deploy using Terraform
        logger.info("Step 3: Deploying Terraform IaC to target tenant...")
        logger.info(f"  Target subscription: {self.target_subscription}")
        logger.info(f"  Terraform directory: {terraform_dir}")

        deployment_result = deploy_terraform(
            iac_dir=terraform_dir,
            resource_group="architecture-replication",  # Will be created by Terraform
            location="eastus",  # Default location
            dry_run=False,  # Actually deploy
            subscription_id=self.target_subscription,
            verbose=True,
        )

        logger.info(f"  Deployment status: {deployment_result['status']}")

        return {
            "status": deployment_result["status"],
            "resources_deployed": len(tenant_graph.resources),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "terraform_dir": str(terraform_dir),
            "terraform_output": deployment_result.get("output", ""),
        }

    async def _build_tenant_graph_from_instances(
        self, selected_instances: List[tuple]
    ) -> TenantGraph:
        """Build TenantGraph from selected instances by querying Neo4j.

        Args:
            selected_instances: List of (pattern_name, instances) tuples

        Returns:
            TenantGraph with full resource and relationship data
        """
        # Collect all resource IDs from selected instances
        all_resource_ids = []
        dict_count = 0
        string_count = 0
        for _pattern_name, instances in selected_instances:
            for instance in instances:
                for resource in instance:
                    if isinstance(resource, dict) and "id" in resource:
                        all_resource_ids.append(resource["id"])
                        dict_count += 1
                    elif isinstance(resource, str):
                        all_resource_ids.append(resource)
                        string_count += 1

        logger.info(f"  Querying Neo4j for {len(all_resource_ids)} resources...")
        logger.info(f"  Resource format breakdown: {dict_count} dicts, {string_count} strings")

        # Log first few resource IDs for debugging
        if all_resource_ids:
            logger.info(f"  Sample resource IDs (first 3):")
            for i, res_id in enumerate(all_resource_ids[:3], 1):
                logger.info(f"    {i}. {res_id}")

        # Query Neo4j for full resource data
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        resources = []
        relationships = []

        try:
            with driver.session() as session:
                # Fetch resources
                result = session.run(
                    """
                    MATCH (r:Resource:Original)
                    WHERE r.id IN $ids
                    RETURN r
                    """,
                    ids=all_resource_ids,
                )

                for record in result:
                    resource_dict = dict(record["r"])
                    resources.append(resource_dict)

                # Fetch relationships between selected resources
                result = session.run(
                    """
                    MATCH (source:Resource:Original)-[rel]->(target:Resource:Original)
                    WHERE source.id IN $ids AND target.id IN $ids
                    AND type(rel) <> 'SCAN_SOURCE_NODE'
                    RETURN source.id as source_id,
                           type(rel) as rel_type,
                           target.id as target_id,
                           properties(rel) as rel_props
                    """,
                    ids=all_resource_ids,
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

        finally:
            driver.close()

        logger.info(f"  Retrieved {len(resources)} resources and {len(relationships)} relationships from Neo4j")

        return TenantGraph(resources=resources, relationships=relationships)

    async def _store_replication_relationships(self) -> int:
        """Store REPLICATED_FROM relationships in Neo4j.

        Creates relationships between target (replicated) resources and source resources
        using the mappings created earlier.

        Returns:
            Number of relationships stored
        """
        # Convert mappings to format expected by TargetGraphBuilder
        resource_mappings = {}
        for mapping in self.mappings:
            resource_mappings[mapping.target_resource_id] = {
                "source_resource_id": mapping.source_resource_id,
            }

        # Use TargetGraphBuilder to store mappings
        analyzer = ArchitecturalPatternAnalyzer(
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
        )

        target_builder = TargetGraphBuilder(
            analyzer,
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
        )

        stored_count = target_builder.store_replication_mappings(resource_mappings)

        return stored_count

    async def _scan_target_subscription(self) -> None:
        """Scan target subscription into Neo4j for fidelity validation.

        This method ensures the target subscription resources are available in Neo4j
        before performing fidelity validation. Without this, all resources would show
        as "missing_target" even if they were successfully deployed.
        """
        logger.info("=" * 80)
        logger.info("STEP 4.5: Scanning target subscription into Neo4j...")
        logger.info("=" * 80)
        logger.info(f"Target subscription: {self.target_subscription}")

        try:
            # Import required modules
            from src.azure_tenant_grapher import AzureTenantGrapher
            from src.config_manager import AzureTenantGrapherConfig
            from src.models.filter_config import FilterConfig
            import os

            # Get tenant ID from environment or use a default
            tenant_id = os.environ.get("AZURE_TENANT_ID")
            if not tenant_id:
                logger.warning("AZURE_TENANT_ID not set, target scan may fail")
                return

            # Create minimal config for target scanning
            config = AzureTenantGrapherConfig(
                neo4j=Neo4jConfig(
                    uri=self.neo4j_uri,
                    user=self.neo4j_user,
                    password=self.neo4j_password,
                ),
                tenant_id=tenant_id,
            )

            # Filter to only scan target subscription
            filter_config = FilterConfig(
                subscription_ids=[self.target_subscription],
                resource_group_names=[],
            )

            logger.info("Initializing Azure Tenant Grapher for target scan...")
            grapher = AzureTenantGrapher(config)

            logger.info("Starting target subscription scan...")
            await grapher.build_graph_async(
                rebuild_edges=False,
                filter_config=filter_config,
                include_references=True,
            )

            logger.info("Target subscription scan complete!")

        except Exception as e:
            logger.error(f"Target subscription scan failed: {e}")
            logger.warning("Fidelity validation will show all resources as missing_target")
            # Don't raise - allow workflow to continue with incomplete fidelity data

    async def _validate_fidelity_with_mappings(self, redaction_level: RedactionLevel) -> Any:
        """Validate fidelity using explicit source-target mappings.

        This improved implementation:
        1. Uses resource mappings for accurate ID translation (source → target)
        2. Compares only replicated resources (not entire source tenant)
        3. Handles cross-subscription resource ID differences

        Args:
            redaction_level: Security redaction level

        Returns:
            FidelityResult from ResourceFidelityCalculator
        """
        # Create Neo4j session manager
        neo4j_config = Neo4jConfig(uri=self.neo4j_uri, user=self.neo4j_user, password=self.neo4j_password)
        session_manager = Neo4jSessionManager(neo4j_config)
        session_manager.connect()

        try:
            # Create fidelity calculator
            calculator = ResourceFidelityCalculator(
                session_manager=session_manager,
                source_subscription_id=self.source_subscription,
                target_subscription_id=self.target_subscription,
            )

            # Convert ResourceMapping objects to dict format expected by calculator
            resource_mappings = [
                {
                    "source_id": mapping.source_resource_id,
                    "target_id": mapping.target_resource_id,
                }
                for mapping in self.mappings
            ]

            logger.info(f"Validating fidelity for {len(resource_mappings)} replicated resources...")

            # Calculate fidelity using explicit mappings (NEW METHOD)
            fidelity_result = calculator.calculate_fidelity_with_mappings(
                resource_mappings=resource_mappings,
                redaction_level=redaction_level,
            )

            return fidelity_result

        finally:
            session_manager.disconnect()

    def _generate_comprehensive_report(
        self,
        analysis_summary: Dict[str, Any],
        plan_summary: Dict[str, Any],
        deployment_summary: Dict[str, Any],
        fidelity_result: Any,
    ) -> str:
        """Generate comprehensive markdown report.

        Args:
            analysis_summary: Source analysis results
            plan_summary: Replication plan summary
            deployment_summary: Deployment results
            fidelity_result: Fidelity validation results

        Returns:
            Markdown report string
        """
        report = f"""# Architecture-Based Tenant Replication Report

**Generated:** {datetime.now(timezone.utc).isoformat()}

**Source Subscription:** `{self.source_subscription}`
**Target Subscription:** `{self.target_subscription}`

---

## Executive Summary

This report documents the complete architecture-based tenant replication workflow,
from source analysis through deployment and fidelity validation.

- **Detected Patterns:** {analysis_summary.get('detected_patterns', 0)}
- **Resources Selected:** {len(self.mappings)}
- **Deployment Status:** {deployment_summary.get('status', 'unknown').upper()}
- **Fidelity Match:** {fidelity_result.metrics.match_percentage if fidelity_result else 0:.1f}%

---

## 1. Source Tenant Analysis

### Summary Statistics

- **Total Relationships:** {analysis_summary.get('total_relationships', 0)}
- **Unique Patterns:** {analysis_summary.get('unique_patterns', 0)}
- **Resource Types:** {analysis_summary.get('resource_types', 0)}
- **Pattern Graph Edges:** {analysis_summary.get('pattern_graph_edges', 0)}
- **Detected Patterns:** {analysis_summary.get('detected_patterns', 0)}
- **Total Resources:** {analysis_summary.get('total_pattern_resources', 0)}

### Configuration Coherence

- **Enabled:** {analysis_summary.get('configuration_coherence_enabled', False)}
- **Threshold:** 0.7 (70% similarity required for clustering)

---

## 2. Replication Plan

### Instance Selection

- **Total Instances Selected:** {plan_summary.get('total_instances', 0)}
- **Patterns Covered:** {len(plan_summary.get('patterns', {}))}

### Pattern Distribution

"""

        # Add pattern details
        for pattern_name, pattern_info in plan_summary.get("patterns", {}).items():
            report += f"- **{pattern_name}:**\n"
            report += f"  - Instances: {pattern_info.get('instance_count', 0)}\n"
            report += f"  - Resources: {pattern_info.get('resource_count', 0)}\n"

        report += f"""
---

## 3. Resource Mappings

**Total Mappings:** {len(self.mappings)}

Sample mappings (first 10):

"""

        # Add sample mappings
        for i, mapping in enumerate(self.mappings[:10], 1):
            report += f"{i}. **{mapping.source_resource_name}** → **{mapping.target_resource_name}**\n"
            report += f"   - Type: `{mapping.source_resource_type}`\n"
            report += f"   - Pattern: `{mapping.pattern_name}`\n\n"

        report += f"""
---

## 4. Deployment Summary

- **Status:** {deployment_summary.get('status', 'unknown').upper()}
- **Resources Deployed:** {deployment_summary.get('resources_deployed', 0)}
- **Timestamp:** {deployment_summary.get('timestamp', 'N/A')}

"""

        if deployment_summary.get("note"):
            report += f"**Note:** {deployment_summary['note']}\n\n"

        if fidelity_result:
            report += f"""
---

## 5. Fidelity Validation

### Summary Metrics

- **Total Resources:** {fidelity_result.metrics.total_resources}
- **Exact Match:** {fidelity_result.metrics.exact_match} ({fidelity_result.metrics.exact_match / fidelity_result.metrics.total_resources * 100 if fidelity_result.metrics.total_resources > 0 else 0:.1f}%)
- **Drifted:** {fidelity_result.metrics.drifted} ({fidelity_result.metrics.drifted / fidelity_result.metrics.total_resources * 100 if fidelity_result.metrics.total_resources > 0 else 0:.1f}%)
- **Missing in Target:** {fidelity_result.metrics.missing_target}
- **Missing in Source:** {fidelity_result.metrics.missing_source}
- **Overall Match:** {fidelity_result.metrics.match_percentage:.1f}%

### Redaction Level

- **Level:** {fidelity_result.redaction_level.value.upper()}

### Security Warnings

"""
            for warning in fidelity_result.security_warnings:
                report += f"- {warning}\n"

            if fidelity_result.metrics.top_mismatched_properties:
                report += "\n### Top Mismatched Properties\n\n"
                for prop in fidelity_result.metrics.top_mismatched_properties[:10]:
                    report += f"- **{prop['property']}**: {prop['count']} mismatches\n"

        report += f"""
---

## 6. Errors and Warnings

### Errors

"""
        if self.errors:
            for error in self.errors:
                report += f"- {error}\n"
        else:
            report += "None\n"

        report += "\n### Warnings\n\n"
        if self.warnings:
            for warning in self.warnings:
                report += f"- {warning}\n"
        else:
            report += "None\n"

        report += """
---

## Files Generated

1. `01_analysis_summary.json` - Source tenant analysis
2. `02_replication_plan.json` - Replication plan details
3. `03_resource_mappings.json` - Source-to-target mappings
4. `04_deployment_summary.json` - Deployment results
5. `05_fidelity_validation.json` - Fidelity validation data
6. `00_COMPREHENSIVE_REPORT.md` - This report

---

*Generated by Architecture-Based Tenant Replication Orchestrator*
"""

        return report


async def main():
    """Main entry point for CLI execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Architecture-based tenant replication with fidelity validation"
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
        "--target-instance-count",
        type=int,
        default=None,
        help="Number of instances to replicate (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output/replication_run"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7688"),
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
    parser.add_argument(
        "--redaction-level",
        choices=["FULL", "MINIMAL", "NONE"],
        default="FULL",
        help="Security redaction level for fidelity validation",
    )

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = ArchitectureReplicationOrchestrator(
        source_subscription=args.source_subscription,
        target_subscription=args.target_subscription,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        output_dir=args.output_dir,
    )

    # Run workflow
    redaction_level = RedactionLevel[args.redaction_level.upper()]
    result = await orchestrator.run_complete_workflow(
        target_instance_count=args.target_instance_count,
        use_configuration_coherence=True,
        coherence_threshold=0.7,
        include_orphaned_resources=True,
        use_spectral_guidance=True,
        redaction_level=redaction_level,
    )

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    asyncio.run(main())
