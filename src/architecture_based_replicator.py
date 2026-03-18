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

import itertools
import json
import logging
import random
import re
from collections import defaultdict
from typing import Any

import networkx as nx
from neo4j import GraphDatabase

from .architectural_pattern_analyzer import ArchitecturalPatternAnalyzer
from .architecture_replication_constants import (
    DEFAULT_COHERENCE_THRESHOLD,
    DEFAULT_MAX_CONFIG_SAMPLES,
    DEFAULT_SPECTRAL_WEIGHT,
    NODE_COVERAGE_WEIGHT_EXTREMES,
)
from .replicator.modules import (
    ConfigurationSimilarity,
    GraphStructureAnalyzer,
    InstanceSelector,
    OrphanedResourceManager,
    PatternInstanceFinder,
    ResourceTypeResolver,
    TargetGraphBuilder,
)

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
        source_tenant_id: str | None = None,
    ):
        """
        Initialize the architecture-based replicator.

        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            source_tenant_id: Azure tenant ID of the source scan.  Passed to
                ``ArchitecturalPatternAnalyzer`` so that resources belonging to
                other tenants are excluded from pattern analysis.
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        # Pattern analyzer for building generalized graphs
        self.analyzer = ArchitecturalPatternAnalyzer(
            neo4j_uri, neo4j_user, neo4j_password, source_tenant_id=source_tenant_id
        )

        # Initialize brick modules
        self.type_resolver = ResourceTypeResolver()
        self.config_similarity = ConfigurationSimilarity()
        self.graph_analyzer = GraphStructureAnalyzer()
        self.instance_finder = PatternInstanceFinder(
            self.analyzer,
            self.config_similarity,
        )
        self.orphaned_manager = OrphanedResourceManager(
            self.analyzer,
        )
        self.target_builder = TargetGraphBuilder(
            self.analyzer, neo4j_uri, neo4j_user, neo4j_password
        )
        self.selector = InstanceSelector(self.graph_analyzer, self.target_builder)

        # Graphs
        self.source_pattern_graph: nx.MultiDiGraph | None = None
        self.source_resource_type_counts: dict[str, int] | None = None

        # Detected architectural patterns from source tenant
        self.detected_patterns: dict[str, dict[str, Any]] | None = None

        # Available resources grouped by pattern
        self.pattern_resources: dict[str, list[dict[str, Any]]] = {}

    def analyze_source_tenant(
        self,
        use_configuration_coherence: bool = True,
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
        include_colocated_orphaned_resources: bool = True,
    ) -> dict[str, Any]:
        """
        Analyze source tenant and identify architectural patterns.

        This method performs the following steps:
        1. Connects to Neo4j and fetches all resource relationships
        2. Builds a source pattern graph showing resource type connections
        3. Detects architectural patterns (Web App, VM Workload, etc.)
        4. Fetches actual resource instances for each detected pattern
        5. Optionally splits instances by configuration coherence
        6. Optionally includes co-located orphaned resources

        Args:
            use_configuration_coherence: If True, splits instances by configuration coherence
                (location, SKU, tags similarity). This ensures architecturally coherent groupings.
                Default: True (recommended)
            coherence_threshold: Minimum similarity score for resources to be in same instance (0.0-1.0).
                Higher values create tighter, more homogeneous groups. Lower values allow more variation.
                Default: 0.7 (70% similarity)
            include_colocated_orphaned_resources: If True, includes orphaned resource types that
                co-locate in the same ResourceGroup as pattern resources. This preserves source tenant
                co-location relationships (e.g., KeyVault in same RG as VMs).
                Default: True (recommended)

        Returns:
            Dictionary with analysis summary containing:
            - total_relationships: Total resource relationships found
            - unique_patterns: Number of unique relationship patterns
            - resource_types: Number of distinct resource types
            - pattern_graph_edges: Number of edges in pattern graph
            - detected_patterns: Number of architectural patterns detected
            - total_pattern_resources: Total resources in all pattern instances
            - configuration_coherence_enabled: Whether coherence splitting was used

        Raises:
            RuntimeError: If connection to Neo4j fails or source tenant is empty

        Example:
            >>> replicator = ArchitecturePatternReplicator(uri, user, pwd)
            >>> analysis = replicator.analyze_source_tenant(
            ...     use_configuration_coherence=True,
            ...     coherence_threshold=0.7
            ... )
            >>> print(f"Found {analysis['detected_patterns']} patterns")
        """
        logger.info("Analyzing source tenant for architectural patterns...")
        self.analyzer.connect()

        try:
            # Step 1: Build source pattern graph
            all_relationships = self.analyzer.fetch_all_relationships()
            aggregated_relationships = self.analyzer.aggregate_relationships(
                all_relationships
            )
            all_resource_types = self.analyzer.fetch_all_resource_types()

            (
                self.source_pattern_graph,
                self.source_resource_type_counts,
                _,
            ) = self.analyzer.build_networkx_graph(
                aggregated_relationships, all_resource_types=all_resource_types
            )

            # Step 2: Detect architectural patterns
            self.detected_patterns = self.analyzer.detect_patterns(
                self.source_pattern_graph, self.source_resource_type_counts
            )

            # Step 3: Fetch actual resources for each pattern using brick module
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
            for pattern_name, pattern_info in self.detected_patterns.items():
                matched_resources = pattern_info["matched_resources"]

                logger.info(
                    f"Finding instances for pattern '{pattern_name}' "
                    f"(types: {', '.join(matched_resources)})"
                )

                with driver.session() as session:
                    if use_configuration_coherence:
                        # Use PatternInstanceFinder brick for configuration-coherent instances
                        instances = self.instance_finder.find_configuration_coherent_instances(
                            session,
                            pattern_name,
                            matched_resources,
                            self.detected_patterns,
                            coherence_threshold,
                            include_colocated_orphaned_resources,
                        )
                    else:
                        # Use PatternInstanceFinder brick for simple connected instances
                        instances = self.instance_finder.find_connected_instances(
                            session, matched_resources
                        )

                logger.info(
                    f"  Found {len(instances)} instances for pattern '{pattern_name}'"
                )
                self.pattern_resources[pattern_name] = instances

            # Add orphaned resource instances if requested
            if include_colocated_orphaned_resources:
                logger.info("Finding orphaned resource instances...")
                with driver.session() as session:
                    # Use OrphanedResourceManager brick
                    orphaned_instances = self.orphaned_manager.find_orphaned_instances(
                        session, self.detected_patterns, self.source_resource_type_counts
                    )

                if orphaned_instances:
                    logger.info(
                        f"  Found {len(orphaned_instances)} orphaned resource instances"
                    )
                    # Group orphaned instances into named architectural patterns via
                    # MS Learn lookup instead of the flat "orphaned_resources" key.
                    named_orphan_patterns = (
                        self.analyzer.group_orphans_into_named_patterns(orphaned_instances)
                    )
                    self.pattern_resources.update(named_orphan_patterns)

        finally:
            driver.close()

    def generate_replication_plan(
        self,
        target_instance_count: int | None = None,
        include_orphaned_node_patterns: bool = True,
        node_coverage_weight: float | None = None,
        use_architecture_distribution: bool = True,
        use_configuration_coherence: bool = True,
        use_spectral_guidance: bool = True,
        spectral_weight: float = DEFAULT_SPECTRAL_WEIGHT,
        max_config_samples: int = DEFAULT_MAX_CONFIG_SAMPLES,
        sampling_strategy: str = "coverage",
    ) -> tuple[
        list[tuple[str, list[list[dict[str, Any]]]]],
        list[float],
        dict[str, Any] | None,
    ]:
        """
        Generate tenant replication plan to match source pattern graph.

        This method uses a sophisticated multi-layer selection strategy to choose
        architectural instances that best replicate the source tenant's structure:

        1. Architecture Distribution Analysis (optional): Compute distribution scores for patterns
        2. Proportional Pattern Sampling (optional): Allocate instances proportionally
        3. Instance Selection (2 modes):
           a. Hybrid Spectral-Guided: Distribution balance + spectral optimization (RECOMMENDED, default)
           b. Random: Fast, no bias (when spectral guidance disabled)
        4. Greedy Spectral Matching (fallback): Original spectral distance-based selection

        Args:
            target_instance_count: Number of architectural instances to select.
                If None, selects all available instances. Recommended: Start with 10-20% of source.
            include_orphaned_node_patterns: If True, includes instances containing orphaned
                node resource types to improve coverage. This helps capture standalone resources
                like KeyVaults that aren't part of major patterns.
                Default: True (recommended)
            node_coverage_weight: Weight (0.0-1.0) for prioritizing new nodes vs spectral distance.
                Only used when use_architecture_distribution=False (fallback mode).
                - 0.0 = only spectral distance (original behavior)
                - 1.0 = only node coverage (greedy node selection)
                - None = randomly choose 0.0 or 1.0 (default, exploration/exploitation)
            use_architecture_distribution: If True, uses distribution-based proportional allocation.
                This ensures the target tenant has similar pattern distribution as source.
                Default: True (recommended)
            use_configuration_coherence: If True, clusters resources by configuration similarity during
                instance fetching (location, SKU, tags). Does NOT affect selection.
                Default: True (recommended for realistic instances)
            use_spectral_guidance: If True, uses hybrid scoring (distribution + spectral) for selection.
                Improves node coverage by considering structural similarity.
                Default: True (recommended)
            spectral_weight: Weight for spectral component in hybrid score (0.0-1.0).
                Only used when use_spectral_guidance=True.
                - 0.0 = pure distribution adherence
                - 0.4 = recommended balance (60% distribution, 40% spectral)
                - 1.0 = pure spectral distance
                Default: 0.4
            max_config_samples: Maximum number of representative configurations to sample per pattern
                when using spectral guidance. Only affects patterns with MORE instances than this value.
                For small datasets (all patterns < 100 instances), this parameter has no effect.
                Higher values increase diversity but slow execution.
                Recommended: 10 (fast), 100 (balanced), 500+ (for very large patterns)
                Default: 100
            sampling_strategy: Strategy for selecting configuration samples within patterns.
                - "coverage": Greedy set cover to maximize unique resource types (recommended)
                - "diversity": Maximin diversity sampling for configuration variation
                Use "coverage" for maximizing node coverage, "diversity" for config exploration
                Default: "coverage"

        Returns:
            Tuple of (selected_instances, spectral_distance_history, distribution_metadata):
            - selected_instances: List of (pattern_name, [instances]) tuples where each instance
              is a list of connected resources
            - spectral_distance_history: List of spectral distances during iterative selection
              (empty if not using spectral guidance)
            - distribution_metadata: Architecture distribution analysis (if enabled, else None)

        Raises:
            RuntimeError: If analyze_source_tenant() was not called first or no patterns detected

        Example:
            >>> replicator = ArchitecturePatternReplicator(uri, user, pwd)
            >>> replicator.analyze_source_tenant()
            >>> selected, distances, metadata = replicator.generate_replication_plan(
            ...     target_instance_count=10,
            ...     use_spectral_guidance=True,
            ...     spectral_weight=0.4
            ... )
            >>> print(f"Selected {len(selected)} pattern groups")
        """
        if not self.source_pattern_graph:
            raise RuntimeError("Must call analyze_source_tenant() first")

        if not self.detected_patterns:
            raise RuntimeError("No patterns detected in source tenant")

        # Randomly choose between pure spectral (0.0) or pure coverage (1.0) if not specified
        if node_coverage_weight is None:
            node_coverage_weight = float(random.choice(NODE_COVERAGE_WEIGHT_EXTREMES))

        logger.info("Generating replication plan to match source pattern graph...")
        logger.info(
            f"Source pattern: {self.source_pattern_graph.number_of_nodes()} types, "
            f"{self.source_pattern_graph.number_of_edges()} edges"
        )

        # Initialize distribution metadata
        distribution_metadata: dict[str, Any] | None = None

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
            for pattern_name, score_info in distribution_scores.items():
                logger.info(
                    f"  {pattern_name}: score={score_info['distribution_score']:.3f}, "
                    f"count={score_info['source_instances']}"
                )

            distribution_metadata = {
                "distribution_scores": distribution_scores,
                "total_instances": sum(
                    len(instances) for instances in self.pattern_resources.values()
                ),
            }

            # LAYER 2: PROPORTIONAL PATTERN SAMPLING
            logger.info("=" * 80)
            logger.info("LAYER 2: Allocating instances proportionally...")

            # If target_instance_count is None, select ALL instances
            if target_instance_count is None:
                logger.info("No target_instance_count specified - selecting ALL instances")
                pattern_targets = {
                    pattern_name: len(instances)
                    for pattern_name, instances in self.pattern_resources.items()
                }
            else:
                # Calculate pattern_targets from distribution_scores
                total_score = sum(info['distribution_score'] for info in distribution_scores.values())
                pattern_targets = {}
                for pattern_name, info in distribution_scores.items():
                    proportion = info['distribution_score'] / total_score if total_score > 0 else 0
                    pattern_targets[pattern_name] = max(1, round(target_instance_count * proportion))

            logger.info(f"Proportional allocation: {pattern_targets}")

            # Use InstanceSelector brick for proportional selection
            selected_instances = self.selector.select_proportionally(
                pattern_targets=pattern_targets,
                pattern_resources=self.pattern_resources,
                use_spectral_guidance=use_spectral_guidance,
                spectral_weight=spectral_weight,
                source_pattern_graph=self.source_pattern_graph,
                max_config_samples=max_config_samples,
                sampling_strategy=sampling_strategy,
            )

            spectral_distance_history: list[float] = []

            # Build final target graph
            final_target = self.target_builder.build_from_instances(selected_instances)


            # Compute final distance
            if use_spectral_guidance:
                distance = self.graph_analyzer.compute_spectral_distance(
                    self.source_pattern_graph, final_target
                )
                spectral_distance_history.append(distance)
                logger.info(f"Final spectral distance: {distance:.4f}")

            logger.info(
                f"Selected {len(selected_instances)} instances across patterns"
            )
            logger.info(
                f"Target graph: {final_target.number_of_nodes()} types, "
                f"{final_target.number_of_edges()} edges"
            )

            return (
                selected_instances,
                spectral_distance_history,
                distribution_metadata,
            )

        else:
            # FALLBACK: Original greedy spectral matching
            logger.info("Using greedy spectral matching (fallback mode)...")

            # Use InstanceSelector brick for greedy selection
            selected_instances, spectral_distance_history = self.selector.select_greedy(
                pattern_resources=self.pattern_resources,
                source_pattern_graph=self.source_pattern_graph,
                target_instance_count=target_instance_count,
                include_orphaned=include_orphaned_node_patterns,
                node_coverage_weight=node_coverage_weight,
            )

            return selected_instances, spectral_distance_history, None

    def analyze_orphaned_nodes(
        self, target_pattern_graph: nx.MultiDiGraph
    ) -> dict[str, Any]:
        """
        Analyze orphaned nodes in source and target graphs.

        Orphaned nodes are resource types that are not covered by any detected architectural
        pattern. They represent standalone resources (e.g., KeyVaults, Automation Accounts)
        that exist independently in the tenant.

        This method identifies:
        1. Orphaned nodes in source tenant (types not in any pattern)
        2. Orphaned nodes in target tenant (after replication)
        3. Resource types present in source but missing from target
        4. Suggested patterns to improve coverage

        Args:
            target_pattern_graph: The target pattern graph built from selected instances.
                This is typically the output of build_from_instances() after replication.

        Returns:
            Dictionary with orphaned node analysis containing:
            - source_orphaned: List of orphaned resource types in source graph
            - target_orphaned: List of orphaned resource types in target graph
            - missing_in_target: List of resource types in source but not in target
            - suggested_patterns: Pattern suggestions to improve coverage
            - source_orphaned_count: Count of orphaned types in source
            - target_orphaned_count: Count of orphaned types in target
            - missing_count: Count of missing types in target

        Raises:
            RuntimeError: If analyze_source_tenant() was not called first

        Example:
            >>> replicator = ArchitecturePatternReplicator(uri, user, pwd)
            >>> replicator.analyze_source_tenant()
            >>> selected, _, _ = replicator.generate_replication_plan()
            >>> target_graph = build_target_graph(selected)
            >>> orphaned = replicator.analyze_orphaned_nodes(target_graph)
            >>> print(f"{orphaned['missing_count']} types missing in target")
        """
        if not self.source_pattern_graph or not self.detected_patterns:
            raise RuntimeError("Must call analyze_source_tenant() first")

        # Identify orphaned nodes in source graph
        source_orphaned = self.analyzer.identify_orphaned_nodes(
            self.source_pattern_graph, self.detected_patterns
        )

        # For target graph, detect which patterns it has
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

    def _query_cross_rg_connections(self) -> set[tuple[str, str]]:
        """
        Query Neo4j for all resource pairs that are connected across ResourceGroup boundaries.

        Two resources are considered cross-RG connected when:

        - They have a **direct relationship** (any type except SCAN_SOURCE_NODE) and
          belong to different ResourceGroups, OR
        - They both connect to a **shared intermediate node** that is one of:
            - AAD User (``User`` label)
            - Service Principal (``ServicePrincipal`` label)
            - AAD Group (``IdentityGroup`` label)
            - Subnet (``Resource`` with type ``Microsoft.Network/subnets``)
          and belong to different ResourceGroups.

        Returns:
            Set of ``(resource_id_a, resource_id_b)`` pairs, normalised so
            ``resource_id_a < resource_id_b`` (each pair appears exactly once).
        """
        query = """
        MATCH (a:Resource:Original)-[r]->(b:Resource:Original)
        WHERE type(r) <> 'SCAN_SOURCE_NODE'
          AND a.id CONTAINS '/resourceGroups/'
          AND b.id CONTAINS '/resourceGroups/'
          AND a.id < b.id
        WITH a.id AS from_id, b.id AS to_id,
             split(toLower(a.id), '/resourcegroups/')[1] AS rg_a_raw,
             split(toLower(b.id), '/resourcegroups/')[1] AS rg_b_raw
        WITH from_id, to_id,
             split(rg_a_raw, '/')[0] AS rg_a,
             split(rg_b_raw, '/')[0] AS rg_b
        WHERE rg_a <> rg_b
        RETURN from_id, to_id

        UNION

        MATCH (a:Resource:Original)-[]->(shared)<-[]-(b:Resource:Original)
        WHERE (shared:User OR shared:ServicePrincipal OR shared:IdentityGroup
               OR (shared:Resource AND shared.type = 'Microsoft.Network/subnets'))
          AND a.id CONTAINS '/resourceGroups/'
          AND b.id CONTAINS '/resourceGroups/'
          AND a.id < b.id
        WITH a.id AS from_id, b.id AS to_id,
             split(toLower(a.id), '/resourcegroups/')[1] AS rg_a_raw,
             split(toLower(b.id), '/resourcegroups/')[1] AS rg_b_raw
        WITH from_id, to_id,
             split(rg_a_raw, '/')[0] AS rg_a,
             split(rg_b_raw, '/')[0] AS rg_b
        WHERE rg_a <> rg_b
        RETURN from_id, to_id
        """

        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        pairs: set[tuple[str, str]] = set()
        try:
            with driver.session() as session:
                for record in session.run(query):
                    pairs.add((record["from_id"], record["to_id"]))
        finally:
            driver.close()

        logger.info(f"Found {len(pairs)} cross-RG resource connections")
        return pairs

    def generate_replication_plan_by_resource_count(
        self,
        target_resource_count: int,
        use_architecture_distribution: bool = True,
    ) -> tuple[
        list[tuple[str, list[dict[str, Any]]]],
        list[int],
        dict[str, Any],
    ]:
        """
        Generate a replication plan by adding instances until a resource count is met.

        Unlike ``generate_replication_plan()`` which selects a fixed number of
        *instances*, this method keeps adding architectural instances—proportionally
        distributed across all detected patterns—until the cumulative *resource*
        count reaches ``target_resource_count``.

        Call ``analyze_source_tenant()`` first.

        Args:
            target_resource_count: Minimum total number of resources the plan
                should contain.  The method stops as soon as this threshold is
                crossed, so the actual count may be slightly higher (by at most
                the size of the last instance added).
            use_architecture_distribution: If ``True`` (default), weight pattern
                proportions by their architecture distribution scores so the plan
                mirrors the source tenant's pattern prevalence.  If ``False``,
                all patterns are weighted equally.

        Returns:
            Tuple of ``(selected_instances, resource_count_history, metadata)``
            where:

            - ``selected_instances``: ``(pattern_name, instance)`` pairs in the
              order they were added.
            - ``resource_count_history``: cumulative resource count after each
              instance was added, starting from ``[0]``.
            - ``metadata``: dict with keys ``target_resource_count``,
              ``actual_resource_count``, ``total_instances``,
              ``instance_counts_by_pattern``, and optionally
              ``distribution_scores``.

        Raises:
            RuntimeError: If ``analyze_source_tenant()`` was not called first.

        Example:
            >>> replicator = ArchitecturePatternReplicator(uri, user, pwd)
            >>> replicator.analyze_source_tenant()
            >>> selected, history, meta = replicator.generate_replication_plan_by_resource_count(500)
            >>> print(f"{meta['actual_resource_count']} resources in {meta['total_instances']} instances")
        """
        if not self.source_pattern_graph:
            raise RuntimeError("Must call analyze_source_tenant() first")
        if not self.detected_patterns:
            raise RuntimeError("No patterns detected in source tenant")

        logger.info(
            f"Generating replication plan for target_resource_count={target_resource_count}"
        )

        if use_architecture_distribution:
            distribution_scores = self.analyzer.compute_architecture_distribution(
                self.pattern_resources, self.source_pattern_graph
            )
        else:
            # Uniform weights — every pattern gets equal priority.
            distribution_scores = {
                name: {"distribution_score": 1.0, "source_instances": len(insts)}
                for name, insts in self.pattern_resources.items()
            }

        cross_rg_connections = self._query_cross_rg_connections()

        selected_instances, resource_count_history = self.selector.select_by_resource_count(
            pattern_resources=self.pattern_resources,
            target_resource_count=target_resource_count,
            distribution_scores=distribution_scores,
            cross_rg_connections=cross_rg_connections,
        )

        actual = resource_count_history[-1] if resource_count_history else 0

        metadata: dict[str, Any] = {
            "target_resource_count": target_resource_count,
            "actual_resource_count": actual,
            "total_instances": len(selected_instances),
            "instance_counts_by_pattern": {
                name: sum(1 for n, _ in selected_instances if n == name)
                for name in self.pattern_resources
            },
            "distribution_scores": distribution_scores,
        }

        logger.info(
            f"Plan complete: {len(selected_instances)} instances, "
            f"{actual} resources (target: {target_resource_count})"
        )
        return selected_instances, resource_count_history, metadata

    def build_instance_cooccurrence_graph(
        self,
        selected_instances: list[tuple[str, list[dict[str, Any]]]],
    ) -> tuple[nx.Graph, nx.Graph]:
        """
        Build graphs showing how architecture instances relate through shared ResourceGroups.

        Two instances are connected when their resources live in the same Azure
        ResourceGroup — meaning a single real-world RG contains resources that
        belong to more than one architectural pattern (e.g., VMs + a Key Vault +
        a Load Balancer deployed together).

        The ResourceGroup of each resource is extracted directly from the Azure
        resource ID path, so no Neo4j query is required.

        Args:
            selected_instances: ``(pattern_name, instance)`` pairs as returned by
                ``generate_replication_plan_by_resource_count()`` or
                ``generate_replication_plan()``.

        Returns:
            ``(instance_graph, pattern_graph)`` where:

            - ``instance_graph``: nodes are individual instances (index-keyed),
              edges connect instances that share at least one ResourceGroup.
              Node attrs: ``pattern``, ``size`` (resource count).
              Edge attrs: ``shared_rgs`` (count), ``rg_ids`` (list).

            - ``pattern_graph``: nodes are pattern names, edges connect patterns
              whose instances share ResourceGroups.
              Node attrs: ``instance_count``, ``resource_count``.
              Edge attrs: ``weight`` (total shared-RG count across all instance pairs),
              ``instance_pairs`` (number of instance pairs sharing an RG).
        """

        def _rg_prefix(resource_id: str) -> str | None:
            """Extract '/subscriptions/.../resourceGroups/NAME' from an Azure resource ID."""
            m = re.match(r"(.*?/resourceGroups/[^/]+)", resource_id, re.IGNORECASE)
            return m.group(1).lower() if m else None

        # Map each instance index → its set of ResourceGroup IDs
        instance_rgs: list[set[str]] = []
        for _pname, inst in selected_instances:
            rgs: set[str] = set()
            for r in inst:
                rg = _rg_prefix(r["id"])
                if rg:
                    rgs.add(rg)
            instance_rgs.append(rgs)

        # Build instance-level graph
        G_inst: nx.Graph = nx.Graph()
        for i, (pname, inst) in enumerate(selected_instances):
            G_inst.add_node(i, pattern=pname, size=len(inst))

        rg_to_instances: dict[str, list[int]] = defaultdict(list)
        for i, rgs in enumerate(instance_rgs):
            for rg in rgs:
                rg_to_instances[rg].append(i)

        for rg, indices in rg_to_instances.items():
            for a, b in itertools.combinations(indices, 2):
                if G_inst.has_edge(a, b):
                    G_inst[a][b]["shared_rgs"] += 1
                    G_inst[a][b]["rg_ids"].append(rg)
                else:
                    G_inst.add_edge(a, b, shared_rgs=1, rg_ids=[rg])

        # Build pattern-level graph (aggregate over instances)
        G_pattern: nx.Graph = nx.Graph()
        for pname, inst in selected_instances:
            if pname not in G_pattern:
                G_pattern.add_node(pname, instance_count=0, resource_count=0)
            G_pattern.nodes[pname]["instance_count"] += 1
            G_pattern.nodes[pname]["resource_count"] += len(inst)

        for a, b, data in G_inst.edges(data=True):
            pa = selected_instances[a][0]
            pb = selected_instances[b][0]
            if G_pattern.has_edge(pa, pb):
                G_pattern[pa][pb]["weight"] += data["shared_rgs"]
                G_pattern[pa][pb]["instance_pairs"] += 1
            else:
                G_pattern.add_edge(pa, pb, weight=data["shared_rgs"], instance_pairs=1)

        connected_instances = sum(1 for i in range(len(selected_instances)) if G_inst.degree(i) > 0)
        logger.info(
            f"Instance co-occurrence graph: {G_inst.number_of_nodes()} nodes, "
            f"{G_inst.number_of_edges()} edges, "
            f"{connected_instances} connected instances"
        )
        logger.info(
            f"Pattern co-occurrence graph: {G_pattern.number_of_nodes()} nodes, "
            f"{G_pattern.number_of_edges()} edges"
        )
        return G_inst, G_pattern

    def suggest_replication_improvements(
        self, orphaned_analysis: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Suggest specific instances to select to improve target graph coverage.

        This method analyzes which resource types are missing from the target tenant
        and suggests which pattern instances would help capture them. It's useful for
        iteratively improving replication plans.

        For each missing resource type, it:
        1. Finds which detected patterns contain that type
        2. Counts how many instances have that type
        3. Recommends selecting more instances from the most reliable pattern

        Args:
            orphaned_analysis: Result from analyze_orphaned_nodes() containing
                missing types and orphaned node information

        Returns:
            List of improvement recommendations, each containing:
            - missing_type: The resource type missing from target
            - available_patterns: List of patterns that contain this type, sorted by
              instance count (most reliable first)
            - recommendation: Human-readable suggestion for which pattern to select

        Example:
            >>> replicator = ArchitecturePatternReplicator(uri, user, pwd)
            >>> replicator.analyze_source_tenant()
            >>> selected, _, _ = replicator.generate_replication_plan()
            >>> target_graph = build_target_graph(selected)
            >>> orphaned = replicator.analyze_orphaned_nodes(target_graph)
            >>> improvements = replicator.suggest_replication_improvements(orphaned)
            >>> for suggestion in improvements:
            ...     print(suggestion['recommendation'])
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

    def generate_configuration_based_plan(
        self,
        target_resource_counts: dict[str, int] | None = None,
        seed: int | None = None,
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        """
        Generate tenant replication plan using configuration-based sampling.

        This method uses a bag-of-words model for proportional sampling: configurations
        are sampled randomly from a weighted vector where each configuration appears
        proportionally to its frequency in the source tenant.

        This approach ensures the target tenant has the same configuration distribution
        as the source tenant (same proportions of locations, SKUs, tags, etc.).

        Process:
        1. Analyze source tenant configurations
        2. Build configuration bags (weighted by frequency)
        3. Determine target counts (default: 10% of source)
        4. Sample resources using bag-of-words model
        5. Compute distribution similarity between source and target

        Args:
            target_resource_counts: Dictionary mapping resource types to target counts.
                If None, uses 10% of source counts for all types.
                Example: {"Microsoft.Compute/virtualMachines": 5, "Microsoft.Storage/storageAccounts": 10}
            seed: Random seed for reproducible sampling. Use the same seed to get
                identical results across multiple runs.
                Default: None (non-deterministic)

        Returns:
            Tuple of (selected_resources, resource_mapping):
            - selected_resources: Dict[resource_type, List[resource_dict]] mapping
              resource types to selected resource instances
            - resource_mapping: Dict with metadata including:
              - mappings: Source-to-target resource mappings
              - distribution_analysis: Comparison of source vs target distributions
              - metadata: Summary statistics

        Example:
            >>> replicator = ArchitecturePatternReplicator(uri, user, pwd)
            >>> replicator.analyze_source_tenant()
            >>> selected, metadata = replicator.generate_configuration_based_plan(
            ...     target_resource_counts={"Microsoft.Compute/virtualMachines": 5},
            ...     seed=42
            ... )
            >>> print(f"Selected {len(selected)} resource types")
        """
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
        selected_resources: dict[str, list[dict[str, Any]]] = {}
        resource_mappings: dict[str, dict[str, Any]] = {}
        target_config_distributions: dict[str, dict[str, int]] = {}

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

                # Add to selected resources
                selected_resources[resource_type].append(
                    {
                        "id": target_resource_id,
                        "source_id": source_resource_id,
                        "type": resource_type,
                        "configuration": fingerprint,
                    }
                )

        # Step 5: Compute distribution similarity
        logger.info("Computing distribution similarity...")

        # Use GraphStructureAnalyzer brick for distribution analysis
        distribution_similarity = {}
        for resource_type in selected_resources.keys():
            if resource_type in config_analysis:
                source_dist = config_analysis[resource_type].get("distribution", {})
                target_dist = target_config_distributions.get(resource_type, {})

                # Simple distribution comparison
                if source_dist and target_dist:
                    # Normalize distributions
                    source_total = sum(source_dist.values())
                    target_total = sum(target_dist.values())

                    source_norm = {k: v / source_total for k, v in source_dist.items()}
                    target_norm = {k: v / target_total for k, v in target_dist.items()}

                    # Compute similarity (1 - total variation distance)
                    all_keys = set(source_norm.keys()) | set(target_norm.keys())
                    tv_distance = 0.5 * sum(
                        abs(source_norm.get(k, 0) - target_norm.get(k, 0))
                        for k in all_keys
                    )
                    similarity = 1.0 - tv_distance

                    distribution_similarity[resource_type] = similarity

        logger.info(
            f"Configuration-based plan complete: "
            f"{len(selected_resources)} resource types, "
            f"{sum(len(r) for r in selected_resources.values())} total resources"
        )

        return selected_resources, {
            "mappings": resource_mappings,
            "distribution_similarity": distribution_similarity,
            "config_analysis": config_analysis,
            "target_counts": target_resource_counts,
        }
