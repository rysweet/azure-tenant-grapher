"""
Architecture-Based Tenant Replication

This module replicates tenants by operating at the architecture layer instead of
individual resources. An "architecture" is a pattern grouping of related resource types
(e.g., "Web Application" = sites + serverFarms + storageAccounts + components).

Architectures are the patterns detected by ArchitecturalPatternAnalyzer.detect_patterns().

Key approach:
- Selects complete architectural patterns (groups of related resources)
- Ensures connections exist in target graph
- Reuses resources when connections already exist between patterns
- Maintains architectural patterns using spectral comparison
- Goal: Build target pattern graph that MATCHES source pattern graph structure
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
from neo4j import GraphDatabase

from .architectural_pattern_analyzer import ArchitecturalPatternAnalyzer
from .architecture_replication_constants import (
    DEFAULT_COHERENCE_THRESHOLD,
    DEFAULT_MAX_CONFIG_SAMPLES,
    DEFAULT_SPECTRAL_WEIGHT,
    ORPHANED_PATTERN_BUDGET_FRACTION,
    ReplicationDefaults,
)
from .configuration_coherence_analyzer import ConfigurationCoherenceAnalyzer
from .orphaned_resource_handler import OrphanedResourceHandler
from .spectral_distance_calculator import SpectralDistanceCalculator

logger = logging.getLogger(__name__)


class ArchitecturePatternReplicator:
    """
    Replicate tenants by selecting architectural pattern groupings.

    An architectural pattern is a grouping of related resource types that work together
    (e.g., "Web Application", "VM Workload", "Container Platform").

    These patterns are detected using ArchitecturalPatternAnalyzer.detect_patterns().
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
    ):
        """
        Initialize the architecture-based replicator.

        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        # Pattern analyzer for building generalized graphs
        self.analyzer = ArchitecturalPatternAnalyzer(
            neo4j_uri, neo4j_user, neo4j_password
        )

        # Helper classes for modular operations
        self.config_analyzer = ConfigurationCoherenceAnalyzer(analyzer=self.analyzer)
        self.spectral_calculator = SpectralDistanceCalculator()
        self.orphaned_handler = OrphanedResourceHandler(
            neo4j_uri, neo4j_user, neo4j_password, analyzer=self.analyzer
        )

        # Graphs
        self.source_pattern_graph: Optional[nx.MultiDiGraph] = None
        self.source_resource_type_counts: Optional[Dict[str, int]] = None

        # Detected architectural patterns from source tenant
        self.detected_patterns: Optional[Dict[str, Dict[str, Any]]] = None

        # Available resources grouped by pattern
        self.pattern_resources: Dict[str, List[Dict[str, Any]]] = {}

    def analyze_source_tenant(
        self,
        use_configuration_coherence: bool = True,
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
        include_colocated_orphaned_resources: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze source tenant and identify architectural patterns.

        Args:
            use_configuration_coherence: If True, splits instances by configuration coherence
            coherence_threshold: Minimum similarity score for resources to be in same instance (0.0-1.0)
            include_colocated_orphaned_resources: If True, includes orphaned resource types that
                                                  co-locate in the same ResourceGroup as pattern resources.
                                                  This preserves source tenant co-location relationships.
                                                  (default: True, recommended)

        Returns:
            Dictionary with analysis summary
        """
        logger.info("Analyzing source tenant for architectural patterns...")
        self.analyzer.connect()

        try:
            # Build source pattern graph
            all_relationships = self.analyzer.fetch_all_relationships()
            aggregated_relationships = self.analyzer.aggregate_relationships(
                all_relationships
            )

            (
                self.source_pattern_graph,
                self.source_resource_type_counts,
                _,
            ) = self.analyzer.build_networkx_graph(aggregated_relationships)

            # Detect architectural patterns
            self.detected_patterns = self.analyzer.detect_patterns(
                self.source_pattern_graph, self.source_resource_type_counts
            )

            # Fetch actual resources for each pattern
            self._fetch_pattern_resources(
                use_configuration_coherence,
                coherence_threshold,
                include_colocated_orphaned_resources,
            )

            logger.info(
                f"Detected {len(self.detected_patterns)} architectural patterns"
            )

            # Log pattern details
            for pattern_name, pattern_info in self.detected_patterns.items():
                resource_count = len(self.pattern_resources.get(pattern_name, []))
                logger.info(
                    f"  {pattern_name}: {resource_count} resources, "
                    f"{pattern_info['completeness']:.1%} complete"
                )

            return {
                "total_relationships": len(all_relationships),
                "unique_patterns": len(aggregated_relationships),
                "resource_types": len(self.source_resource_type_counts),
                "pattern_graph_edges": self.source_pattern_graph.number_of_edges(),
                "detected_patterns": len(self.detected_patterns),
                "total_pattern_resources": sum(
                    len(resources) for resources in self.pattern_resources.values()
                ),
                "configuration_coherence_enabled": use_configuration_coherence,
            }

        finally:
            self.analyzer.close()

    def _fetch_pattern_resources(
        self,
        use_configuration_coherence: bool = True,
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
        include_colocated_orphaned_resources: bool = True,
    ) -> None:
        """
        Fetch connected subgraphs for each detected architectural pattern.

        For each pattern, finds connected groups of resources (architectural instances)
        where the resources are actually connected to each other, not just all resources
        of matching types.

        If use_configuration_coherence is True, splits ResourceGroups into configuration-coherent
        clusters where resources have similar configurations (same location, similar tier, etc.).

        If include_colocated_orphaned_resources is True, includes orphaned resource types (types
        not in any pattern) that co-locate in the same ResourceGroup as pattern resources. This
        preserves source tenant co-location relationships (e.g., KeyVault in same RG as VMs).

        Args:
            use_configuration_coherence: If True, splits instances by configuration coherence
            coherence_threshold: Minimum similarity score for resources to be in same instance (0.0-1.0)
            include_colocated_orphaned_resources: If True, includes co-located orphaned resources

        Example: Instead of "all VMs + all disks + all NICs", this finds connected groups
        like "VM1 + its disk + its NIC", "VM2 + its disk + its NIC", etc.

        Each pattern will have a list of architectural instances (connected subgraphs).
        """
        if not self.detected_patterns:
            logger.warning("No patterns detected, nothing to fetch")
            return

        mode = (
            "configuration-coherent"
            if use_configuration_coherence
            else "ResourceGroup-based"
        )
        logger.info(f"Finding {mode} architectural instances for each pattern...")

        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        try:
            with driver.session() as session:
                for pattern_name, pattern_info in self.detected_patterns.items():
                    matched_types = pattern_info["matched_resources"]

                    # Find connected subgraphs where resources of these types are connected
                    if use_configuration_coherence:
                        instances = self._find_configuration_coherent_instances(
                            pattern_name,
                            matched_types,
                            session,
                            coherence_threshold,
                            include_colocated_orphaned_resources,
                        )
                    else:
                        instances = self._find_connected_pattern_instances(
                            session,
                            matched_types,
                            pattern_name,
                            include_colocated_orphaned_resources,
                        )

                    self.pattern_resources[pattern_name] = instances

                    logger.info(
                        f"  {pattern_name}: {len(instances)} {mode} instances found"
                    )

        finally:
            driver.close()

        total_instances = sum(
            len(instances) for instances in self.pattern_resources.values()
        )
        logger.info(
            f"Found {total_instances} total {mode} instances across {len(self.pattern_resources)} patterns"
        )

    def _find_connected_pattern_instances(
        self,
        session,
        matched_types: Set[str],
        pattern_name: str,
        include_colocated_orphaned_resources: bool = True,
    ) -> List[List[Dict[str, Any]]]:
        """
        Find connected instances of an architectural pattern.

        Architectural instances are groups of resources that share a common parent
        (ResourceGroup) and match the pattern's resource types. This reflects how
        the instance resource graph creates the pattern graph through aggregation.

        If include_colocated_orphaned_resources is True, also includes orphaned resource
        types (not in any pattern) that co-locate in the same ResourceGroup as pattern
        resources. This preserves source tenant co-location relationships.

        Args:
            session: Neo4j session
            matched_types: Resource types that match this pattern
            pattern_name: Name of the pattern
            include_colocated_orphaned_resources: Include orphaned resources from same RG

        Returns a list of architectural instances, where each instance is a list
        of resources that belong together (same ResourceGroup).
        """
        # Compute all pattern types across all detected patterns (for orphan detection)
        all_pattern_types = set()
        for pattern_info in self.detected_patterns.values():
            all_pattern_types.update(pattern_info["matched_resources"])

        # Query to find all ORIGINAL resources (the real instance graph) along with their ResourceGroup
        # We query Original nodes because they represent the actual Azure resources
        # Resources are connected through shared parents (ResourceGroup), not direct edges
        query = """
        MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
        RETURN r.id as id, r.type as type, r.name as name, rg.id as resource_group_id
        """

        result = session.run(query)

        # Build mapping: ResourceGroup -> List of resources in that RG
        # Track both pattern resources and potentially orphaned resources
        rg_to_pattern_resources = {}  # Resources matching this pattern
        rg_to_all_resources = {}  # All resources (for orphan inclusion)
        resource_info = {}  # All resources by ID (for direct connection tracking)

        for record in result:
            simplified_type = self.analyzer._get_resource_type_name(
                ["Resource"], record["type"]
            )

            rg_id = record["resource_group_id"]
            resource = {
                "id": record["id"],
                "type": simplified_type,
                "name": record["name"],
            }

            # Track ALL resources by ID (needed for direct connection graph)
            resource_info[record["id"]] = resource

            # Track all resources by RG (for orphan inclusion later)
            if rg_id not in rg_to_all_resources:
                rg_to_all_resources[rg_id] = []
            rg_to_all_resources[rg_id].append((simplified_type, resource))

            # Track resources that match the pattern types
            if simplified_type in matched_types:
                if rg_id not in rg_to_pattern_resources:
                    rg_to_pattern_resources[rg_id] = []

                rg_to_pattern_resources[rg_id].append(resource)

        if not rg_to_pattern_resources:
            return []

        # Also find direct Resource->Resource connections (like VNet->Subnet)
        # to merge resources connected by explicit edges
        # Query Original nodes for the real instance relationships
        query = """
        MATCH (source:Resource:Original)-[r]->(target:Resource:Original)
        WHERE source.id IN $ids AND target.id IN $ids
        AND type(r) <> 'SCAN_SOURCE_NODE'
        RETURN source.id as source_id, target.id as target_id
        """

        result = session.run(query, ids=list(resource_info.keys()))

        # Build adjacency list for direct connections
        direct_connections = {rid: set() for rid in resource_info.keys()}
        for record in result:
            source_id = record["source_id"]
            target_id = record["target_id"]
            direct_connections[source_id].add(target_id)
            direct_connections[target_id].add(source_id)

        # Build instances by merging RG-based groups with direct connections
        instances = []

        for rg_id, pattern_resources in rg_to_pattern_resources.items():
            if len(pattern_resources) >= 2:
                # This RG has multiple resources of pattern types
                instance = list(pattern_resources)

                # Include co-located orphaned resources if enabled
                if include_colocated_orphaned_resources and rg_id in rg_to_all_resources:
                    orphaned_count = 0
                    for resource_type, resource in rg_to_all_resources[rg_id]:
                        # Check if this resource type is NOT in any pattern (orphaned)
                        if resource_type not in all_pattern_types:
                            # Check if not already in instance (avoid duplicates)
                            if not any(r["id"] == resource["id"] for r in instance):
                                instance.append(resource)
                                orphaned_count += 1

                    if orphaned_count > 0:
                        logger.debug(
                            f"  Added {orphaned_count} co-located orphaned resources to instance in RG {rg_id}"
                        )

                # Add any directly connected resources from other RGs
                instance_ids = {r["id"] for r in instance}
                expanded = True

                while expanded:
                    expanded = False
                    for res_id in list(instance_ids):
                        for connected_id in direct_connections[res_id]:
                            if (
                                connected_id not in instance_ids
                                and connected_id in resource_info
                            ):
                                instance.append(resource_info[connected_id])
                                instance_ids.add(connected_id)
                                expanded = True

                instances.append(instance)

        logger.debug(
            f"  Found {len(instances)} instances from {len(rg_to_pattern_resources)} resource groups"
        )

        return instances

    def _compute_configuration_similarity(
        self,
        fingerprint1: Dict[str, Any],
        fingerprint2: Dict[str, Any],
    ) -> float:
        """
        Compute similarity score between two configuration fingerprints.

        Configuration coherence is based on:
        - Location match (same Azure region)
        - SKU tier similarity (e.g., Standard vs Premium)
        - Tag overlap

        Args:
            fingerprint1: First configuration fingerprint
            fingerprint2: Second configuration fingerprint

        Returns:
            Similarity score (0.0 to 1.0, where 1.0 = identical)
        """
        return self.config_analyzer.compute_similarity(fingerprint1, fingerprint2)

    def _find_configuration_coherent_instances(
        self,
        pattern_name: str,
        matched_types: Set[str],
        session,
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
        include_colocated_orphaned_resources: bool = True,
    ) -> List[List[Dict[str, Any]]]:
        """
        Find architectural instances with configuration coherence.

        Instead of grouping resources only by ResourceGroup, this method
        splits ResourceGroups into configuration-coherent clusters where
        resources have similar configurations (same location, similar tier, etc.).

        If include_colocated_orphaned_resources is True, also includes orphaned resource
        types (not in any pattern) that co-locate in the same ResourceGroup as pattern
        resources. This preserves source tenant co-location relationships.

        Args:
            pattern_name: Name of the architectural pattern
            matched_types: Set of resource types in this pattern
            session: Neo4j session
            coherence_threshold: Minimum similarity score for resources to be in same instance (0.0-1.0)
            include_colocated_orphaned_resources: Include orphaned resources from same RG

        Returns:
            List of configuration-coherent instances
        """
        return self.config_analyzer.find_configuration_coherent_instances(
            pattern_name=pattern_name,
            matched_types=matched_types,
            session=session,
            detected_patterns=self.detected_patterns,
            coherence_threshold=coherence_threshold,
            include_colocated_orphaned_resources=include_colocated_orphaned_resources,
        )

    def generate_replication_plan(
        self,
        target_instance_count: Optional[int] = None,
        include_orphaned_node_patterns: bool = True,
        node_coverage_weight: Optional[float] = None,
        use_architecture_distribution: bool = True,
        use_configuration_coherence: bool = True,
        use_spectral_guidance: bool = True,
        spectral_weight: float = DEFAULT_SPECTRAL_WEIGHT,
        max_config_samples: int = DEFAULT_MAX_CONFIG_SAMPLES,
        sampling_strategy: str = "coverage",
    ) -> Tuple[
        List[Tuple[str, List[List[Dict[str, Any]]]]],
        List[float],
        Optional[Dict[str, Any]],
    ]:
        """
        Generate tenant replication plan to match source pattern graph.

        Multi-layer selection strategy:
        1. Architecture Distribution Analysis (optional): Compute distribution scores for patterns
        2. Proportional Pattern Sampling (optional): Allocate instances proportionally
        3. Instance Selection (2 modes):
           a. Hybrid Spectral-Guided: Distribution balance + spectral optimization (RECOMMENDED, default)
           b. Random: Fast, no bias (when spectral guidance disabled)
        4. Greedy Spectral Matching (fallback): Original spectral distance-based selection

        Args:
            target_instance_count: Number of architectural instances to select (default: all)
            include_orphaned_node_patterns: If True, includes instances containing orphaned
                                           node resource types to improve coverage (default: True)
            node_coverage_weight: Weight (0.0-1.0) for prioritizing new nodes vs spectral distance.
                                 0.0 = only spectral distance (original behavior)
                                 1.0 = only node coverage (greedy node selection)
                                 None = randomly choose 0.0 or 1.0 (default, exploration/exploitation)
                                 Only used when use_architecture_distribution=False (fallback mode)
            use_architecture_distribution: If True, uses distribution-based proportional allocation
                                          (default: True, recommended)
            use_configuration_coherence: If True, clusters resources by configuration similarity during
                                        instance fetching (location, SKU, tags). Does NOT affect selection.
                                        (default: True, recommended for realistic instances)
            use_spectral_guidance: If True, uses hybrid scoring (distribution + spectral) for selection
                                  Improves node coverage by considering structural similarity.
                                  (default: True, recommended)
            spectral_weight: Weight for spectral component in hybrid score (0.0-1.0, default: 0.4)
                            Only used when use_spectral_guidance=True.
                            0.0 = pure distribution adherence
                            0.4 = recommended balance (60% distribution, 40% spectral)
                            1.0 = pure spectral distance
            max_config_samples: Maximum number of representative configurations to sample per pattern
                               when using spectral guidance (default: 100). Only affects patterns
                               with MORE instances than this value. For small datasets (all patterns
                               < 100 instances), this parameter has no effect as all instances are
                               evaluated. Higher values increase diversity but slow execution.
                               Recommended: 10 (fast), 100 (balanced, sufficient for most datasets),
                               500+ (for very large patterns only)
            sampling_strategy: Strategy for selecting configuration samples within patterns
                              (default: "coverage", recommended).
                              "coverage": Greedy set cover to maximize unique resource types
                              "diversity": Maximin diversity sampling for configuration variation
                              Use "coverage" for maximizing node coverage, "diversity" for config exploration

        Returns:
            Tuple of (selected instances, spectral distance history, distribution metadata)
            where selected instances is a list of (pattern_name, [instances]) tuples,
            each instance is a list of connected resources,
            and distribution metadata contains architecture distribution analysis (if enabled)
        """
        if not self.source_pattern_graph:
            raise RuntimeError("Must call analyze_source_tenant() first")

        if not self.detected_patterns:
            raise RuntimeError("No patterns detected in source tenant")

        # Randomly choose between pure spectral (0.0) or pure coverage (1.0) if not specified
        if node_coverage_weight is None:
            import random

            node_coverage_weight = float(random.choice([0, 1]))

        logger.info("Generating replication plan to match source pattern graph...")
        logger.info(
            f"Source pattern: {self.source_pattern_graph.number_of_nodes()} types, "
            f"{self.source_pattern_graph.number_of_edges()} edges"
        )

        # Initialize distribution metadata
        distribution_metadata: Optional[Dict[str, Any]] = None

        # LAYER 1: ARCHITECTURE DISTRIBUTION ANALYSIS
        if use_architecture_distribution:
            logger.info("=" * 80)
            logger.info("LAYER 1: Computing architecture distribution...")

            distribution_scores = self.analyzer.compute_architecture_distribution(
                self.pattern_resources, self.source_pattern_graph
            )

            logger.info(
                f"Distribution analysis complete for {len(distribution_scores)} patterns"
            )
            for pattern_name, data in sorted(
                distribution_scores.items(),
                key=lambda x: x[1]["distribution_score"],
                reverse=True,
            )[:5]:
                logger.info(
                    f"  {data['rank']}. {pattern_name}: "
                    f"{data['distribution_score']:.1f} "
                    f"({data['source_instances']} instances)"
                )
        else:
            logger.info("Architecture distribution analysis disabled")
            distribution_scores = None

        # Collect all instances from all patterns
        all_instances = []
        for pattern_name, instances in self.pattern_resources.items():
            for instance in instances:
                all_instances.append((pattern_name, instance))

        # If requested, add instances containing orphaned node types
        orphaned_instances_added = 0
        if include_orphaned_node_patterns:
            orphaned_instances = self._find_orphaned_node_instances()
            if orphaned_instances:
                all_instances.extend(orphaned_instances)
                orphaned_instances_added = len(orphaned_instances)
                logger.info(
                    f"Added {orphaned_instances_added} instances containing orphaned node types"
                )

        # Default to all instances
        if target_instance_count is None:
            target_instance_count = len(all_instances)

        logger.info(
            f"Will select up to {target_instance_count} architectural instances "
            f"from {len(all_instances)} total available "
            f"({orphaned_instances_added} for orphaned nodes)"
        )

        # LAYER 2: PROPORTIONAL PATTERN SAMPLING
        pattern_targets: Optional[Dict[str, int]] = None
        if use_architecture_distribution and distribution_scores:
            logger.info("=" * 80)
            logger.info("LAYER 2: Computing proportional pattern targets...")

            # NEW (2026-02-02): Add orphaned resources BEFORE computing targets
            # so coverage-aware allocation can include them in scoring
            if include_orphaned_node_patterns and orphaned_instances:
                # Add to pattern_resources so coverage computation can see them
                # Extract resource lists from tuples (orphaned_instances is List[Tuple[str, List[Dict]]])
                self.pattern_resources["Orphaned Resources"] = [
                    resources for _, resources in orphaned_instances
                ]

            # Compute proportional pattern targets from distribution scores
            pattern_targets = self.analyzer.compute_pattern_targets(
                distribution_scores,
                target_instance_count,
                pattern_resources=self.pattern_resources,
                source_type_counts=self.source_resource_type_counts,
            )

            # Include orphaned instances in pattern targets for selection
            if include_orphaned_node_patterns and orphaned_instances:

                # NEW (2026-02-02): Only set orphaned target if not already computed by coverage-aware allocation
                if "Orphaned Resources" not in pattern_targets:
                    # Reserve budget for orphaned resources (25% of total by default)
                    orphaned_target_count = max(1, int(target_instance_count * ORPHANED_PATTERN_BUDGET_FRACTION))
                    pattern_targets["Orphaned Resources"] = orphaned_target_count
                    logger.info(
                        f"Added 'Orphaned Resources' pattern with {len(orphaned_instances)} instances "
                        f"(target: {orphaned_target_count} instances, {orphaned_target_count / target_instance_count * 100:.1f}%)"
                    )
                else:
                    # Coverage-aware allocation already computed orphaned target
                    logger.info(
                        f"'Orphaned Resources' pattern already allocated by coverage-aware mode "
                        f"({len(orphaned_instances)} instances available, "
                        f"target: {pattern_targets['Orphaned Resources']} instances, "
                        f"{pattern_targets['Orphaned Resources'] / target_instance_count * 100:.1f}%)"
                    )

            logger.info(
                f"Proportional allocation for {target_instance_count} instances:"
            )
            for pattern_name, target_count in sorted(
                pattern_targets.items(), key=lambda x: x[1], reverse=True
            ):
                pct = (target_count / target_instance_count) * 100
                logger.info(f"  {pattern_name}: {target_count} ({pct:.1f}%)")
        else:
            logger.info("Proportional pattern sampling disabled")

        # LAYER 3 & 4: INSTANCE SELECTION
        logger.info("=" * 80)
        if use_architecture_distribution and pattern_targets:
            if use_spectral_guidance:
                logger.info(
                    f"LAYER 3: Hybrid spectral-guided instance selection "
                    f"(spectral_weight={spectral_weight:.2f})"
                )
            else:
                logger.info("LAYER 3: Random instance selection")
            selected_instances = self._select_instances_proportionally(
                pattern_targets,
                use_configuration_coherence,
                use_spectral_guidance,
                spectral_weight,
                max_config_samples,
                sampling_strategy
            )
        else:
            logger.info("LAYER 3: Greedy spectral matching (fallback mode)")
            logger.info(
                f"Node coverage weight: {node_coverage_weight:.2f} "
                f"(0.0=spectral only, 1.0=coverage only)"
            )
            selected_instances = self._select_instances_greedy(
                all_instances, target_instance_count, node_coverage_weight
            )

        # Build spectral distance history for all selected instances
        spectral_history: List[float] = []
        for i in range(1, len(selected_instances) + 1):
            target_graph = self._build_target_pattern_graph_from_instances(
                selected_instances[:i]
            )
            distance = self._compute_spectral_distance(
                self.source_pattern_graph, target_graph
            )
            spectral_history.append(distance)

        logger.info("=" * 80)
        logger.info(
            f"Replication plan complete: {len(selected_instances)} architectural instances selected"
        )

        final_target = self._build_target_pattern_graph_from_instances(
            selected_instances
        )
        logger.info(
            f"Final target pattern: {final_target.number_of_nodes()} types, "
            f"{final_target.number_of_edges()} edges"
        )

        # LAYER 4: VALIDATION & TRACEABILITY
        if use_architecture_distribution and distribution_scores and pattern_targets:
            logger.info("=" * 80)
            logger.info("LAYER 4: Validating proportional sampling...")

            # Count actual selections by pattern
            actual_counts = {}
            for pattern_name, instance in selected_instances:
                actual_counts[pattern_name] = actual_counts.get(pattern_name, 0) + 1

            # Build target distribution from actual counts
            # Create a distribution structure matching the source format
            target_distribution = {}
            total_actual = sum(actual_counts.values())

            for pattern_name in distribution_scores.keys():
                actual = actual_counts.get(pattern_name, 0)
                # Calculate distribution score based on actual instances
                # Use same weight as instance count (30% of total)
                actual_score = (
                    (actual / total_actual * 100) if total_actual > 0 else 0.0
                )

                target_distribution[pattern_name] = {
                    "distribution_score": actual_score,
                    "source_instances": actual,
                    "rank": 0,  # Will be set after sorting
                }

            # Rank target patterns by actual count
            sorted_target = sorted(
                target_distribution.items(),
                key=lambda x: x[1]["source_instances"],
                reverse=True,
            )
            for rank, (pattern_name, data) in enumerate(sorted_target, start=1):
                data["rank"] = rank

            # Validate
            validation = self.analyzer.validate_proportional_sampling(
                distribution_scores, target_distribution
            )

            # Log validation results (handle case where scipy isn't available)
            if "cosine_similarity" in validation:
                logger.info(
                    f"Validation: {validation['interpretation']} "
                    f"(cosine similarity: {validation['cosine_similarity']:.4f})"
                )
            else:
                logger.warning(
                    f"Validation: {validation.get('interpretation', 'No validation available')}"
                )

            # Build distribution metadata
            distribution_metadata = {
                "architecture_distribution": distribution_scores,
                "pattern_targets": pattern_targets,
                "actual_counts": actual_counts,
                "validation": validation,
                "selection_mode": "proportional"
                if use_configuration_coherence
                else "proportional_spectral",
            }
        else:
            logger.info("Distribution validation skipped (disabled or no distribution)")
            distribution_metadata = {"selection_mode": "greedy_spectral"}

        # Group selected instances by pattern for return value
        pattern_instances = {}
        for pattern_name, instance in selected_instances:
            if pattern_name not in pattern_instances:
                pattern_instances[pattern_name] = []
            pattern_instances[pattern_name].append(instance)

        return list(pattern_instances.items()), spectral_history, distribution_metadata

    def _find_orphaned_node_instances(self) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """
        Find instances that contain orphaned node resource types.

        Orphaned nodes are resource types not covered by any detected pattern.
        This method finds actual resource instances containing these types.

        Returns:
            List of (pseudo_pattern_name, instance) tuples for orphaned resources
        """
        return self.orphaned_handler.find_orphaned_node_instances(
            detected_patterns=self.detected_patterns,
            source_resource_type_counts=self.source_resource_type_counts,
        )

    def _build_target_pattern_graph_from_instances(
        self, selected_instances: List[Tuple[str, List[Dict[str, Any]]]]
    ) -> nx.MultiDiGraph:
        """
        Build pattern graph from selected architectural instances.

        This queries Neo4j for actual relationships between the resources
        in the selected instances.

        Args:
            selected_instances: List of (pattern_name, instance) tuples,
                               where each instance is a list of connected resources

        Returns:
            Pattern graph with resource types as nodes
        """
        # Collect all resource IDs from selected instances
        all_resource_ids = []
        for pattern_name, instance in selected_instances:
            all_resource_ids.extend([r["id"] for r in instance])

        # Build pattern graph
        target_graph = nx.MultiDiGraph()

        # Count resource types
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        try:
            with driver.session() as session:
                # Fetch ALL relationships involving the selected Original resources
                # This includes Resource→Resource, Resource→ResourceGroup, Resource→Tag, etc.
                # We need to match the same approach as ArchitecturalPatternAnalyzer
                result = session.run(
                    """
                    MATCH (source)-[r]->(target)
                    WHERE (source:Resource:Original AND source.id IN $ids)
                       OR (target:Resource:Original AND target.id IN $ids)
                    AND type(r) <> 'SCAN_SOURCE_NODE'
                    RETURN labels(source) as source_labels,
                           source.type as source_type,
                           type(r) as rel_type,
                           labels(target) as target_labels,
                           target.type as target_type
                """,
                    ids=all_resource_ids,
                )

                # Collect all relationships
                relationships = []
                for record in result:
                    relationships.append(
                        {
                            "source_labels": record["source_labels"],
                            "source_type": record["source_type"],
                            "rel_type": record["rel_type"],
                            "target_labels": record["target_labels"],
                            "target_type": record["target_type"],
                        }
                    )

                # First, add ALL resource types from selected instances as nodes
                # This ensures orphaned types without relationships still appear in the graph
                resource_type_counts = {}
                for pattern_name, instance in selected_instances:
                    for resource in instance:
                        rtype = resource["type"]
                        resource_type_counts[rtype] = (
                            resource_type_counts.get(rtype, 0) + 1
                        )

                # Add all resource types as nodes
                for rtype, count in resource_type_counts.items():
                    if not target_graph.has_node(rtype):
                        target_graph.add_node(rtype, count=count)

                # Aggregate relationships by type (same as ArchitecturalPatternAnalyzer)
                aggregated = self.analyzer.aggregate_relationships(relationships)

                # Build edges from aggregated relationships
                for rel in aggregated:
                    source_type = rel["source_type"]
                    target_type = rel["target_type"]
                    rel_type = rel["rel_type"]
                    frequency = rel["frequency"]

                    # Add nodes if not already added (for relationship endpoints)
                    if not target_graph.has_node(source_type):
                        target_graph.add_node(source_type, count=0)
                    if not target_graph.has_node(target_type):
                        target_graph.add_node(target_type, count=0)

                    # Add edge
                    target_graph.add_edge(
                        source_type,
                        target_type,
                        relationship=rel_type,
                        frequency=frequency,
                    )

        finally:
            driver.close()

        return target_graph

    def analyze_orphaned_nodes(
        self, target_pattern_graph: nx.MultiDiGraph
    ) -> Dict[str, Any]:
        """
        Analyze orphaned nodes in source and target graphs.

        Identifies resource types not covered by detected patterns and suggests
        new patterns or instances to improve coverage.

        Args:
            target_pattern_graph: The target pattern graph built from selected instances

        Returns:
            Dictionary with orphaned node analysis including:
            - source_orphaned: Orphaned nodes in source graph
            - target_orphaned: Orphaned nodes in target graph
            - missing_in_target: Nodes in source but not in target
            - suggested_patterns: Pattern suggestions to improve coverage
        """
        if not self.source_pattern_graph or not self.detected_patterns:
            raise RuntimeError("Must call analyze_source_tenant() first")

        # Identify orphaned nodes in source graph
        source_orphaned = self.analyzer.identify_orphaned_nodes(
            self.source_pattern_graph, self.detected_patterns
        )

        # For target graph, we need to detect which patterns it has
        # Use the same pattern detection on target graph
        target_resource_type_counts = dict(
            target_pattern_graph.nodes(data="count", default=0)
        )
        target_detected_patterns = self.analyzer.detect_patterns(
            target_pattern_graph, target_resource_type_counts
        )

        # Identify orphaned nodes in target graph
        target_orphaned = self.analyzer.identify_orphaned_nodes(
            target_pattern_graph, target_detected_patterns
        )

        # Find nodes that are in source but missing from target
        source_nodes = set(self.source_pattern_graph.nodes())
        target_nodes = set(target_pattern_graph.nodes())
        missing_in_target = source_nodes - target_nodes

        # Get suggested patterns for source orphaned nodes
        suggested_patterns = self.analyzer.suggest_new_patterns(
            source_orphaned, self.source_pattern_graph
        )

        logger.info(
            f"Orphaned node analysis: "
            f"{len(source_orphaned)} in source, "
            f"{len(target_orphaned)} in target, "
            f"{len(missing_in_target)} missing in target"
        )

        return {
            "source_orphaned": source_orphaned,
            "target_orphaned": target_orphaned,
            "missing_in_target": list(missing_in_target),
            "suggested_patterns": suggested_patterns,
            "source_orphaned_count": len(source_orphaned),
            "target_orphaned_count": len(target_orphaned),
            "missing_count": len(missing_in_target),
        }

    def suggest_replication_improvements(
        self, orphaned_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Suggest specific instances to select to improve target graph coverage.

        Analyzes which resource types are missing from the target and suggests
        which pattern instances would help capture them.

        Args:
            orphaned_analysis: Result from analyze_orphaned_nodes()

        Returns:
            List of improvement recommendations with pattern instances
        """
        missing_types = set(orphaned_analysis["missing_in_target"])
        suggestions = []

        # For each missing type, find which patterns contain it
        for resource_type in missing_types:
            # Check which detected patterns include this type
            patterns_with_type = []
            for pattern_name, pattern_info in self.detected_patterns.items():
                if resource_type in pattern_info["matched_resources"]:
                    # Count how many instances have this type
                    instances_with_type = []
                    for instance in self.pattern_resources.get(pattern_name, []):
                        if any(r["type"] == resource_type for r in instance):
                            instances_with_type.append(instance)

                    if instances_with_type:
                        patterns_with_type.append(
                            {
                                "pattern_name": pattern_name,
                                "instance_count": len(instances_with_type),
                                "sample_instance": instances_with_type[0],
                            }
                        )

            if patterns_with_type:
                # Sort by instance count (more instances = more reliable pattern)
                patterns_with_type.sort(key=lambda x: x["instance_count"], reverse=True)

                suggestions.append(
                    {
                        "missing_type": resource_type,
                        "available_patterns": patterns_with_type,
                        "recommendation": f"Select more instances from '{patterns_with_type[0]['pattern_name']}' pattern",
                    }
                )

        logger.info(f"Generated {len(suggestions)} improvement recommendations")
        return suggestions

    def _compute_weighted_score(
        self,
        source_graph: nx.DiGraph,
        target_graph: nx.DiGraph,
        source_node_types: Set[str],
        node_coverage_weight: float,
    ) -> float:
        """
        Compute weighted score combining spectral distance and node coverage.

        Lower score is better. The score balances structural similarity (spectral distance)
        with node type coverage (having the same types as source).

        Args:
            source_graph: Source pattern graph
            target_graph: Target pattern graph being built
            source_node_types: Set of node types in source graph
            node_coverage_weight: Weight for node coverage (0.0-1.0)
                                 0.0 = only spectral distance
                                 1.0 = only node coverage
                                 0.5 = balanced

        Returns:
            Weighted score (lower is better)
        """
        # Compute spectral distance (structural similarity)
        spectral_distance = self.spectral_calculator.compute_distance(source_graph, target_graph)

        # Compute node coverage penalty (missing types)
        # This is the fraction of source nodes NOT yet in target
        target_node_types = set(target_graph.nodes())
        missing_nodes = source_node_types - target_node_types
        node_coverage_penalty = (
            len(missing_nodes) / len(source_node_types) if source_node_types else 0.0
        )

        # Use the calculator's weighted score method
        return self.spectral_calculator.compute_weighted_score(
            spectral_distance=spectral_distance,
            node_coverage_penalty=node_coverage_penalty,
            node_coverage_weight=node_coverage_weight,
        )

    def _compute_spectral_distance(
        self, graph1: nx.DiGraph, graph2: nx.DiGraph
    ) -> float:
        """
        Compute normalized spectral distance using Laplacian eigenvalues.

        Args:
            graph1: First graph
            graph2: Second graph

        Returns:
            Normalized spectral distance
        """
        return self.spectral_calculator.compute_distance(graph1, graph2)

    def generate_configuration_based_plan(
        self,
        target_resource_counts: Optional[Dict[str, int]] = None,
        seed: Optional[int] = None,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Generate tenant replication plan using configuration-based sampling.

        Uses bag-of-words model for proportional sampling: configurations are
        sampled randomly from a weighted vector where each configuration appears
        proportionally to its frequency in the source tenant.

        This approach ensures the target tenant has the same configuration
        distribution as the source tenant.

        Args:
            target_resource_counts: Dictionary mapping resource types to target counts.
                                   If None, uses 10% of source counts for all types.
            seed: Random seed for reproducible sampling (default: None)

        Returns:
            Tuple of (selected_resources, resource_mapping):
            - selected_resources: Dict[resource_type, List[resource_dict]]
            - resource_mapping: Dict with metadata, mappings, and distribution analysis
        """
        import random

        if seed is not None:
            random.seed(seed)

        logger.info("Generating configuration-based replication plan...")

        # Step 1: Analyze source tenant configurations
        logger.info("Analyzing source tenant configurations...")
        config_analysis = self.analyzer.analyze_configuration_distributions()

        # Step 2: Build configuration bags for proportional sampling
        logger.info("Building configuration bags for proportional sampling...")
        config_bags = self.analyzer.build_configuration_bags(config_analysis)

        # Step 3: Determine target counts
        if target_resource_counts is None:
            target_resource_counts = {}
            for resource_type, analysis in config_analysis.items():
                # Default to 10% of source count
                target_count = max(1, int(analysis["total_count"] * 0.1))
                target_resource_counts[resource_type] = target_count

        # Step 4: Sample resources using bag-of-words model
        selected_resources: Dict[str, List[Dict[str, Any]]] = {}
        resource_mappings: Dict[str, Dict[str, Any]] = {}
        target_config_distributions: Dict[str, Dict[str, int]] = {}

        for resource_type, target_count in target_resource_counts.items():
            if resource_type not in config_bags:
                logger.warning(f"No configuration bag for {resource_type}, skipping")
                continue

            bag = config_bags[resource_type]
            if not bag:
                logger.warning(f"Empty configuration bag for {resource_type}, skipping")
                continue

            logger.info(
                f"Sampling {target_count} resources for {resource_type} "
                f"from bag of {len(bag)} configurations..."
            )

            selected_resources[resource_type] = []
            target_config_distributions[resource_type] = {}

            # Sample from bag using random.choices (bag-of-words model)
            for i in range(target_count):
                # Random selection from bag (naturally proportional)
                sampled_entry = random.choice(bag)
                fingerprint = sampled_entry["fingerprint"]
                sample_resources = sampled_entry["sample_resources"]

                # Pick a source resource matching this configuration
                if sample_resources:
                    source_resource_id = random.choice(sample_resources)
                else:
                    logger.warning("No sample resources for configuration, skipping")
                    continue

                # Generate target resource ID (simulated)
                target_resource_id = f"{source_resource_id}_target_{i}"

                # Track mapping
                resource_mappings[target_resource_id] = {
                    "source_resource_id": source_resource_id,
                    "resource_type": resource_type,
                    "configuration_fingerprint": fingerprint,
                    "configuration_match_quality": "exact",
                    "selection_reason": "proportional_sampling",
                    "selection_weight": len(sample_resources) / len(bag),
                }

                # Track target distribution
                config_key = json.dumps(fingerprint, sort_keys=True)
                target_config_distributions[resource_type][config_key] = (
                    target_config_distributions[resource_type].get(config_key, 0) + 1
                )

                selected_resources[resource_type].append(
                    {
                        "target_id": target_resource_id,
                        "source_id": source_resource_id,
                        "fingerprint": fingerprint,
                    }
                )

        # Step 5: Compute distribution analysis
        logger.info("Computing distribution similarity metrics...")
        distribution_analysis = self._compute_distribution_similarity(
            config_analysis, target_config_distributions, target_resource_counts
        )

        # Build resource mapping output
        resource_mapping = {
            "metadata": {
                "generation_timestamp": Path(__file__).stat().st_mtime,
                "total_resources_mapped": sum(
                    len(v) for v in selected_resources.values()
                ),
                "resource_types": len(selected_resources),
            },
            "mappings": resource_mappings,
            "distribution_analysis": distribution_analysis,
        }

        logger.info(
            f"Configuration-based plan complete: "
            f"{resource_mapping['metadata']['total_resources_mapped']} resources "
            f"across {resource_mapping['metadata']['resource_types']} types"
        )

        return selected_resources, resource_mapping

    def _compute_distribution_similarity(
        self,
        source_analysis: Dict[str, Dict[str, Any]],
        target_distributions: Dict[str, Dict[str, int]],
        target_counts: Dict[str, int],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute statistical similarity between source and target distributions.

        Uses:
        - Cosine similarity (1.0 = identical distributions)
        - Kolmogorov-Smirnov statistic (0.0 = identical distributions)

        Args:
            source_analysis: Configuration analysis from source tenant
            target_distributions: Configuration counts in target tenant
            target_counts: Target resource counts per type

        Returns:
            Distribution analysis with similarity metrics per resource type
        """
        from scipy.spatial.distance import cosine
        from scipy.stats import ks_2samp

        distribution_analysis = {}

        for resource_type in source_analysis.keys():
            if resource_type not in target_distributions:
                continue

            source_configs = source_analysis[resource_type]["configurations"]
            target_config_counts = target_distributions[resource_type]

            # Build source distribution vector
            source_vector = {}
            for config in source_configs:
                config_key = json.dumps(config["fingerprint"], sort_keys=True)
                source_vector[config_key] = config["count"]

            # Build target distribution vector (same keys as source)
            target_vector = {}
            for config_key in source_vector.keys():
                target_vector[config_key] = target_config_counts.get(config_key, 0)

            # Compute cosine similarity
            source_vals = list(source_vector.values())
            target_vals = list(target_vector.values())

            if sum(source_vals) > 0 and sum(target_vals) > 0:
                # Normalize to percentages
                source_pct = [v / sum(source_vals) for v in source_vals]
                target_pct = [v / sum(target_vals) for v in target_vals]

                # Cosine similarity (1 - cosine distance)
                similarity = 1.0 - cosine(source_pct, target_pct)

                # KS test for distribution comparison
                ks_stat, p_value = ks_2samp(source_pct, target_pct)

                distribution_analysis[resource_type] = {
                    "source_distribution": {
                        k: {"count": v, "percentage": (v / sum(source_vals)) * 100}
                        for k, v in source_vector.items()
                    },
                    "target_distribution": {
                        k: {
                            "count": v,
                            "percentage": (v / sum(target_vals)) * 100
                            if sum(target_vals) > 0
                            else 0,
                        }
                        for k, v in target_vector.items()
                    },
                    "distribution_similarity": similarity,
                    "ks_statistic": ks_stat,
                    "p_value": p_value,
                }
            else:
                distribution_analysis[resource_type] = {
                    "source_distribution": {},
                    "target_distribution": {},
                    "distribution_similarity": 0.0,
                    "ks_statistic": 1.0,
                    "p_value": 0.0,
                }

        return distribution_analysis

    def _select_instances_proportionally(
        self,
        pattern_targets: Dict[str, int],
        use_configuration_coherence: bool,
        use_spectral_guidance: bool = False,
        spectral_weight: float = DEFAULT_SPECTRAL_WEIGHT,
        max_config_samples: int = DEFAULT_MAX_CONFIG_SAMPLES,
        sampling_strategy: str = "coverage"
    ) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """
        Select instances proportionally from each pattern.

        Supports two selection modes:
        1. Spectral-guided: Uses hybrid score (distribution + spectral) for best structural match
        2. Random: Fast, no bias (default when spectral guidance disabled)

        Note: use_configuration_coherence parameter is kept for backward compatibility but only
        affects instance FETCHING (clustering during analyze phase), not selection here.

        Args:
            pattern_targets: Target count per pattern from proportional allocation
            use_configuration_coherence: Unused in selection (kept for backward compatibility)
            use_spectral_guidance: If True, use hybrid scoring with spectral distance
            spectral_weight: Weight for spectral component in hybrid score (0.0-1.0)
                            distribution_weight = 1.0 - spectral_weight
            max_config_samples: Maximum configurations to sample per pattern
            sampling_strategy: "coverage" (greedy set cover) or "diversity" (maximin)

        Returns:
            List of (pattern_name, instance) tuples
        """
        import random

        selected_instances: List[Tuple[str, List[Dict[str, Any]]]] = []
        current_counts: Dict[str, int] = {p: 0 for p in pattern_targets}
        total_target = sum(pattern_targets.values())

        for pattern_name, target_count in pattern_targets.items():
            if pattern_name not in self.pattern_resources:
                logger.warning(
                    f"Pattern {pattern_name} not found in pattern_resources, skipping"
                )
                continue

            available_instances = self.pattern_resources[pattern_name]

            if not available_instances:
                logger.warning(
                    f"No instances available for pattern {pattern_name}, skipping"
                )
                continue

            # Limit to available instances
            actual_count = min(target_count, len(available_instances))

            if use_spectral_guidance:
                # Hybrid spectral-guided selection
                logger.info(
                    f"  Selecting {actual_count}/{len(available_instances)} instances "
                    f"from {pattern_name} (spectral-guided, weight={spectral_weight:.2f})"
                )

                chosen_instances = self._select_with_hybrid_scoring(
                    available_instances,
                    actual_count,
                    pattern_name,
                    selected_instances,
                    current_counts,
                    total_target,
                    spectral_weight,
                    max_config_samples,
                    sampling_strategy
                )

            else:
                # Random selection
                logger.info(
                    f"  Selecting {actual_count}/{len(available_instances)} instances "
                    f"from {pattern_name} (random)"
                )
                chosen_instances = random.sample(available_instances, actual_count)

            # Add to selected
            for instance in chosen_instances:
                selected_instances.append((pattern_name, instance))
                current_counts[pattern_name] += 1

        logger.info(
            f"Selected {len(selected_instances)} total instances across all patterns"
        )

        return selected_instances

    def _select_with_hybrid_scoring(
        self,
        available_instances: List[List[Dict[str, Any]]],
        target_count: int,
        pattern_name: str,
        selected_so_far: List[Tuple[str, List[Dict[str, Any]]]],
        current_counts: Dict[str, int],
        total_target: int,
        spectral_weight: float,
        max_config_samples: int = DEFAULT_MAX_CONFIG_SAMPLES,
        sampling_strategy: str = "coverage"
    ) -> List[List[Dict[str, Any]]]:
        """
        Select instances using hybrid scoring: distribution adherence + spectral improvement.

        Samples representative configurations (up to max_config_samples) using specified
        strategy, then scores each based on:
        - Distribution adherence: How well it maintains proportional balance
        - Spectral contribution: How much it improves structural similarity

        Args:
            available_instances: Pool of instances to select from
            target_count: Number of instances to select
            pattern_name: Name of the current pattern
            selected_so_far: Instances already selected from all patterns
            current_counts: Current count per pattern
            total_target: Total target instance count across all patterns
            spectral_weight: Weight for spectral component (0.0-1.0)
            max_config_samples: Maximum samples to consider per pattern.
                               Only affects patterns with MORE instances than this value.
                               Example: With max_config_samples=100, patterns with 50 instances
                               will evaluate all 50, but patterns with 200 will sample 100.
                               Default 100 is sufficient for most datasets.
            sampling_strategy: "coverage" (greedy set cover) or "diversity" (maximin)

        Returns:
            List of selected instances
        """
        # Sample representative configurations using chosen strategy
        actual_max_samples = min(max_config_samples, len(available_instances))

        # Log sampling behavior for diagnostics
        if actual_max_samples < len(available_instances):
            logger.info(
                f"    Sampling limited: {actual_max_samples}/{len(available_instances)} instances "
                f"(max_config_samples={max_config_samples})"
            )
        else:
            logger.debug(
                f"    No sampling limit: evaluating all {len(available_instances)} instances "
                f"(max_config_samples={max_config_samples} >= available)"
            )

        if sampling_strategy == "coverage":
            sampled_instances, instance_metadata = self._sample_for_coverage(
                available_instances,
                max_samples=actual_max_samples
            )
        else:  # "diversity" or default
            sampled_instances = self._sample_representative_configs(
                available_instances, max_samples=actual_max_samples
            )
            instance_metadata = {}  # No metadata for diversity sampling

        # Build current target graph once (for comparing edge additions)
        current_target = self._build_target_pattern_graph_from_instances(selected_so_far)
        current_edges = set(current_target.edges())

        # Score each sampled instance using hybrid function
        scored_instances = []
        for sampled_idx, instance in enumerate(sampled_instances):
            # Build hypothetical target graph with this instance added
            hypothetical_selected = selected_so_far + [(pattern_name, instance)]
            hypothetical_target = self._build_target_pattern_graph_from_instances(
                hypothetical_selected
            )

            # Component 2: Spectral contribution using SUBGRAPH approach
            # Identify NEW EDGES added by this instance
            hypothetical_edges = set(hypothetical_target.edges())
            new_edges = hypothetical_edges - current_edges

            if len(new_edges) > 0:
                # Extract nodes involved in new edges
                new_edge_nodes = set()
                for edge in new_edges:
                    # Edge could be (source, target) or (source, target, key) depending on graph type
                    if len(edge) == 3:
                        source, target, _ = edge
                    else:
                        source, target = edge
                    new_edge_nodes.add(source)
                    new_edge_nodes.add(target)

                # Build subgraph of nodes involved in new edges
                source_subgraph = self.source_pattern_graph.subgraph(new_edge_nodes)
                target_subgraph = hypothetical_target.subgraph(new_edge_nodes)

                # Compare local structure of newly connected nodes
                spectral_contribution = self._compute_spectral_distance(
                    source_subgraph,
                    target_subgraph
                )
            else:
                # No new edges - instance doesn't add structural information
                spectral_contribution = 1.0  # High penalty

            # Use spectral contribution as the primary score (lower is better)
            hybrid_score = spectral_contribution

            # For logging compatibility, compute distribution adherence
            total_selected = sum(current_counts.values())
            if total_selected > 0:
                actual_ratio = (current_counts[pattern_name] + 1) / (total_selected + 1)
                target_ratio = (current_counts[pattern_name] + 1) / total_target
                distribution_adherence = abs(actual_ratio - target_ratio)
            else:
                distribution_adherence = 0.0

            scored_instances.append((hybrid_score, distribution_adherence, spectral_contribution, instance))

        # Log score statistics for debugging spectral_weight behavior
        if scored_instances:
            hybrid_scores = [s[0] for s in scored_instances]
            dist_scores = [s[1] for s in scored_instances]
            spec_scores = [s[2] for s in scored_instances]

            logger.debug(
                f"    Score statistics for {pattern_name} (n={len(scored_instances)}, spectral_weight={spectral_weight}):"
            )
            logger.debug(
                f"      Current edges: {len(current_edges)}"
            )
            logger.debug(
                f"      Distribution: min={min(dist_scores):.4f}, max={max(dist_scores):.4f}, "
                f"range={max(dist_scores)-min(dist_scores):.4f}"
            )
            logger.debug(
                f"      Spectral:     min={min(spec_scores):.4f}, max={max(spec_scores):.4f}, "
                f"range={max(spec_scores)-min(spec_scores):.4f}"
            )
            logger.debug(
                f"      Hybrid:       min={min(hybrid_scores):.4f}, max={max(hybrid_scores):.4f}, "
                f"range={max(hybrid_scores)-min(hybrid_scores):.4f}"
            )

        # Sort by hybrid score (lower is better) and take top instances
        scored_instances.sort(key=lambda x: x[0])

        logger.debug(
            f"    After spectral rescoring: {len(scored_instances)} candidates, "
            f"selecting top {target_count}"
        )

        # Select best instances up to target_count
        # If we sampled < target_count, need to fill remaining slots
        chosen = []
        for hybrid_score, dist_score, spec_score, instance in scored_instances[:target_count]:
            chosen.append(instance)

        # If we need more instances (sampled < target), fill with remaining
        if len(chosen) < target_count:
            import random
            remaining = [inst for inst in available_instances if inst not in chosen]
            additional_needed = target_count - len(chosen)
            if remaining:
                chosen.extend(random.sample(
                    remaining,
                    min(additional_needed, len(remaining))
                ))

        logger.debug(
            f"    Hybrid scoring: sampled {len(sampled_instances)} configs, "
            f"selected {len(chosen)} instances (dist_weight={1.0-spectral_weight:.2f}, "
            f"spec_weight={spectral_weight:.2f})"
        )

        return chosen

    def _sample_representative_configs(
        self,
        instances: List[List[Dict[str, Any]]],
        max_samples: int = 10
    ) -> List[List[Dict[str, Any]]]:
        """
        Sample representative instances using maximin diversity.

        Ensures sampled instances are spread across configuration space
        (different resource types, counts) rather than clustered.

        Args:
            instances: Pool of instances to sample from
            max_samples: Maximum number of samples to return

        Returns:
            List of sampled instances (diverse configurations)
        """
        import random

        if len(instances) <= max_samples:
            return instances

        sampled = []
        remaining = list(instances)

        # Pick first instance randomly
        seed = random.choice(remaining)
        sampled.append(seed)
        remaining.remove(seed)

        # Iteratively pick most diverse instance (maximin strategy)
        while len(sampled) < max_samples and remaining:
            best_diversity = -1
            best_instance = None

            for candidate in remaining:
                # Compute minimum similarity to already sampled instances
                # Use simplified diversity metric: resource type overlap
                min_similarity = min(
                    self._instance_similarity(candidate, s)
                    for s in sampled
                )

                # Pick instance most different from existing samples
                if min_similarity > best_diversity:
                    best_diversity = min_similarity
                    best_instance = candidate

            if best_instance:
                sampled.append(best_instance)
                remaining.remove(best_instance)

        return sampled

    def _sample_for_coverage(
        self,
        instances: List[List[Dict[str, Any]]],
        max_samples: int = DEFAULT_MAX_CONFIG_SAMPLES
    ) -> Tuple[List[List[Dict[str, Any]]], Dict[int, Dict[str, Any]]]:
        """
        Sample instances using greedy set cover to maximize unique resource types.

        Uses greedy algorithm to prioritize instances containing rare resource types,
        ensuring maximum node coverage in the pattern graph.

        Args:
            instances: Pool of instances to sample from
            max_samples: Maximum number of samples to return

        Returns:
            Tuple of (sampled_instances, instance_metadata) where:
            - sampled_instances: List of sampled instances
            - instance_metadata: Dict mapping instance index to metadata dict with:
                - 'types': Set of resource types in instance

        Performance:
            O(N * M * T) where N=instances, M=max_samples, T=avg types per instance
        """
        logger.info(
            f"Coverage sampling: instances={len(instances)}, max_samples={max_samples}"
        )

        # Build type frequency map across all instances
        type_counts: Dict[str, int] = {}
        instance_types: List[Set[str]] = []

        for instance in instances:
            types_in_instance = set()
            for resource in instance:
                resource_type = resource.get("type", "unknown")
                types_in_instance.add(resource_type)
                type_counts[resource_type] = type_counts.get(resource_type, 0) + 1
            instance_types.append(types_in_instance)

        # Greedy set cover: prioritize instances with rare types
        sampled = []
        covered_types: Set[str] = set()
        remaining_indices = list(range(len(instances)))

        for _ in range(min(max_samples, len(instances))):
            if not remaining_indices:
                break

            best_idx = None
            best_score = -1

            for idx in remaining_indices:
                # Calculate coverage score: prioritize rare uncovered types
                new_types = instance_types[idx] - covered_types
                if not new_types:
                    continue

                # Score based on rarity: sum of inverse frequencies
                score = sum(1.0 / type_counts[t] for t in new_types)

                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is None:
                # No more new types to cover, sample randomly from remaining
                import random
                best_idx = random.choice(remaining_indices)

            sampled.append(instances[best_idx])
            covered_types.update(instance_types[best_idx])
            remaining_indices.remove(best_idx)

        # Build metadata dict
        metadata = {}
        for idx, instance in enumerate(sampled):
            metadata[idx] = {
                'types': instance_types[instances.index(instance)]
            }

        logger.info(
            f"Coverage sampling complete: {len(sampled)} instances "
            f"covering {len(covered_types)} unique resource types"
        )

        logger.debug(
            f"    Coverage sampling: selected {len(sampled)} instances covering "
            f"{len(covered_types)} unique resource types"
        )

        return sampled, metadata

    def _instance_similarity(
        self,
        instance1: List[Dict[str, Any]],
        instance2: List[Dict[str, Any]]
    ) -> float:
        """
        Compute similarity between two instances based on resource types.

        Uses Jaccard similarity: |intersection| / |union| of resource types.

        Args:
            instance1: First instance (list of resources)
            instance2: Second instance (list of resources)

        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical types)
        """
        types1 = set(r["type"] for r in instance1)
        types2 = set(r["type"] for r in instance2)

        if not types1 and not types2:
            return 1.0

        intersection = len(types1 & types2)
        union = len(types1 | types2)

        return intersection / union if union > 0 else 0.0

    def _select_instances_greedy(
        self,
        all_instances: List[Tuple[str, List[Dict[str, Any]]]],
        target_instance_count: int,
        node_coverage_weight: float,
    ) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """
        Greedy spectral distance-based instance selection (original algorithm).

        Iteratively selects instances that minimize a weighted score combining
        spectral distance and node coverage.

        Args:
            all_instances: All available (pattern_name, instance) tuples
            target_instance_count: Number of instances to select
            node_coverage_weight: Weight for node coverage (0.0-1.0)

        Returns:
            List of selected (pattern_name, instance) tuples
        """
        # Get source node types for coverage tracking
        source_node_types = set(self.source_pattern_graph.nodes())

        selected_instances: List[Tuple[str, List[Dict[str, Any]]]] = []
        remaining_instances = list(all_instances)  # Make a copy

        # Greedy selection: iteratively pick the instance that best improves our score
        for i in range(min(target_instance_count, len(remaining_instances))):
            best_score = float("inf")
            best_idx = 0
            best_new_nodes = set()

            # Evaluate each remaining instance
            for idx, (pattern_name, instance) in enumerate(remaining_instances):
                # Build hypothetical target graph with this instance added
                hypothetical_selected = selected_instances + [(pattern_name, instance)]
                hypothetical_target = self._build_target_pattern_graph_from_instances(
                    hypothetical_selected
                )

                # Compute weighted score
                score = self._compute_weighted_score(
                    self.source_pattern_graph,
                    hypothetical_target,
                    source_node_types,
                    node_coverage_weight,
                )

                # Track which instance gives best score
                if score < best_score:
                    best_score = score
                    best_idx = idx
                    best_new_nodes = set(hypothetical_target.nodes()) - (
                        set(
                            self._build_target_pattern_graph_from_instances(
                                selected_instances
                            ).nodes()
                        )
                        if selected_instances
                        else set()
                    )

            # Select the best instance
            pattern_name, instance = remaining_instances.pop(best_idx)
            selected_instances.append((pattern_name, instance))

            # Build current target pattern graph from selected instances
            target_pattern_graph = self._build_target_pattern_graph_from_instances(
                selected_instances
            )

            # Calculate coverage metrics
            current_nodes = set(target_pattern_graph.nodes())
            node_coverage = len(current_nodes & source_node_types) / len(
                source_node_types
            )

            if (i + 1) % 10 == 0 or i < 10:
                distance = self._compute_spectral_distance(
                    self.source_pattern_graph, target_pattern_graph
                )
                logger.info(
                    f"Selected instance {i + 1}/{target_instance_count}: {pattern_name} "
                    f"({len(instance)} resources, +{len(best_new_nodes)} new types)"
                )
                logger.info(
                    f"  Target: {target_pattern_graph.number_of_nodes()} types "
                    f"({node_coverage:.1%} coverage), "
                    f"{target_pattern_graph.number_of_edges()} edges, "
                    f"spectral: {distance:.4f}, score: {best_score:.4f}"
                )

        return selected_instances
