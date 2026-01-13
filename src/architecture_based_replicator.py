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

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
from neo4j import GraphDatabase

from .architectural_pattern_analyzer import ArchitecturalPatternAnalyzer

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

        # Graphs
        self.source_pattern_graph: Optional[nx.MultiDiGraph[str]] = None
        self.source_resource_type_counts: Optional[Dict[str, int]] = None

        # Detected architectural patterns from source tenant
        self.detected_patterns: Optional[Dict[str, Dict[str, Any]]] = None

        # Available resources grouped by pattern
        self.pattern_resources: Dict[str, List[Dict[str, Any]]] = {}

    def analyze_source_tenant(self) -> Dict[str, Any]:
        """
        Analyze source tenant and identify architectural patterns.

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
            self._fetch_pattern_resources()

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
            }

        finally:
            self.analyzer.close()

    def _fetch_pattern_resources(self) -> None:
        """
        Fetch connected subgraphs for each detected architectural pattern.

        For each pattern, finds connected groups of resources (architectural instances)
        where the resources are actually connected to each other, not just all resources
        of matching types.

        Example: Instead of "all VMs + all disks + all NICs", this finds connected groups
        like "VM1 + its disk + its NIC", "VM2 + its disk + its NIC", etc.

        Each pattern will have a list of architectural instances (connected subgraphs).
        """
        if not self.detected_patterns:
            logger.warning("No patterns detected, nothing to fetch")
            return

        logger.info("Finding connected architectural instances for each pattern...")

        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        try:
            with driver.session() as session:
                for pattern_name, pattern_info in self.detected_patterns.items():
                    matched_types = pattern_info["matched_resources"]

                    # Find connected subgraphs where resources of these types are connected
                    # Strategy: Start from each resource of a pattern type and expand to
                    # connected resources (also of pattern types), forming connected components

                    instances = self._find_connected_pattern_instances(
                        session, matched_types, pattern_name
                    )

                    self.pattern_resources[pattern_name] = instances

                    logger.info(
                        f"  {pattern_name}: {len(instances)} connected instances found"
                    )

        finally:
            driver.close()

        total_instances = sum(
            len(instances) for instances in self.pattern_resources.values()
        )
        logger.info(
            f"Found {total_instances} total architectural instances across {len(self.pattern_resources)} patterns"
        )

    def _find_connected_pattern_instances(
        self, session, matched_types: Set[str], pattern_name: str
    ) -> List[List[Dict[str, Any]]]:
        """
        Find connected instances of an architectural pattern.

        Architectural instances are groups of resources that share a common parent
        (ResourceGroup) and match the pattern's resource types. This reflects how
        the instance resource graph creates the pattern graph through aggregation.

        Returns a list of architectural instances, where each instance is a list
        of resources that belong together (same ResourceGroup).
        """
        # Query to find all ORIGINAL resources (the real instance graph) along with their ResourceGroup
        # We query Original nodes because they represent the actual Azure resources
        # Resources are connected through shared parents (ResourceGroup), not direct edges
        query = """
        MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
        RETURN r.id as id, r.type as type, r.name as name, rg.id as resource_group_id
        """

        result = session.run(query)

        # Build mapping: ResourceGroup -> List of resources in that RG
        rg_to_resources = {}
        resource_info = {}

        for record in result:
            simplified_type = self.analyzer._get_resource_type_name(
                ["Resource"], record["type"]
            )

            # Only include resources that match the pattern types
            if simplified_type in matched_types:
                resource = {
                    "id": record["id"],
                    "type": simplified_type,
                    "name": record["name"],
                }

                rg_id = record["resource_group_id"]

                if rg_id not in rg_to_resources:
                    rg_to_resources[rg_id] = []

                rg_to_resources[rg_id].append(resource)
                resource_info[record["id"]] = resource

        if not rg_to_resources:
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

        for _rg_id, resources in rg_to_resources.items():
            if len(resources) >= 2:
                # This RG has multiple resources of pattern types
                instance = list(resources)

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
            f"  Found {len(instances)} instances from {len(rg_to_resources)} resource groups"
        )

        return instances

    def generate_replication_plan(
        self,
        target_instance_count: Optional[int] = None,
        hops: int = 2,
        include_orphaned_node_patterns: bool = True,
        node_coverage_weight: Optional[float] = None,
    ) -> Tuple[List[Tuple[str, List[List[Dict[str, Any]]]]], List[float]]:
        """
        Generate tenant replication plan to match source pattern graph.

        The goal is to build a target pattern graph that MATCHES the source pattern graph
        by selecting connected architectural instances one at a time.

        Args:
            target_instance_count: Number of architectural instances to select (default: all)
            hops: Number of hops for local subgraph comparison (default: 2)
            include_orphaned_node_patterns: If True, includes instances containing orphaned
                                           node resource types to improve coverage (default: True)
            node_coverage_weight: Weight (0.0-1.0) for prioritizing new nodes vs spectral distance.
                                 0.0 = only spectral distance (original behavior)
                                 1.0 = only node coverage (greedy node selection)
                                 None = randomly choose 0.0 or 1.0 (default, exploration/exploitation)

        Returns:
            Tuple of (selected instances, spectral distance history)
            where selected instances is a list of (pattern_name, [instances]) tuples,
            and each instance is a list of connected resources
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
        logger.info(
            f"Node coverage weight: {node_coverage_weight:.2f} "
            f"(0.0=spectral only, 1.0=coverage only)"
        )

        # Get source node types for coverage tracking
        source_node_types = set(self.source_pattern_graph.nodes())

        selected_instances: List[Tuple[str, List[Dict[str, Any]]]] = []
        spectral_history: List[float] = []
        remaining_instances = list(all_instances)  # Make a copy

        # Greedy selection: iteratively pick the instance that best improves our score
        for i in range(min(target_instance_count, len(remaining_instances))):
            best_score = float("inf")
            best_idx = 0
            best_new_nodes = set()

            # Evaluate each remaining instance
            for idx, (pattern_name, instance) in enumerate(remaining_instances):
                # Build hypothetical target graph with this instance added
                hypothetical_selected = [*selected_instances, (pattern_name, instance)]
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

            # Track spectral distance for history
            distance = self._compute_spectral_distance(
                self.source_pattern_graph, target_pattern_graph
            )
            spectral_history.append(distance)

            # Calculate coverage metrics
            current_nodes = set(target_pattern_graph.nodes())
            node_coverage = len(current_nodes & source_node_types) / len(
                source_node_types
            )

            if (i + 1) % 10 == 0 or i < 10:
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

        # Group selected instances by pattern for return value
        pattern_instances = {}
        for pattern_name, instance in selected_instances:
            if pattern_name not in pattern_instances:
                pattern_instances[pattern_name] = []
            pattern_instances[pattern_name].append(instance)

        return list(pattern_instances.items()), spectral_history

    def _find_orphaned_node_instances(self) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """
        Find instances that contain orphaned node resource types.

        Orphaned nodes are resource types not covered by any detected pattern.
        This method finds actual resource instances containing these types.

        Returns:
            List of (pseudo_pattern_name, instance) tuples for orphaned resources
        """
        # First identify orphaned nodes in source graph
        source_orphaned = self.analyzer.identify_orphaned_nodes(
            self.source_pattern_graph, self.detected_patterns
        )

        if not source_orphaned:
            logger.info("No orphaned nodes found in source graph")
            return []

        orphaned_types = {node["resource_type"] for node in source_orphaned}
        logger.info(
            str(f"Found {len(orphaned_types)} orphaned resource types in source")
        )

        # Query Neo4j to find instances containing these orphaned types
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        orphaned_instances = []

        try:
            with driver.session() as session:
                # Find ResourceGroups that contain orphaned resource types
                query = """
                MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
                WHERE r.type IN $orphaned_types
                RETURN rg.id as rg_id,
                       collect({id: r.id, type: r.type, name: r.name}) as resources
                """

                # Convert types to full format expected by Neo4j
                full_orphaned_types = []
                for otype in orphaned_types:
                    # Try common provider namespaces
                    for namespace in [
                        "Microsoft.Network",
                        "Microsoft.Compute",
                        "Microsoft.Storage",
                        "Microsoft.Insights",
                        "Microsoft.Web",
                        "Microsoft.ContainerService",
                        "Microsoft.OperationalInsights",
                        "Microsoft.KeyVault",
                    ]:
                        full_orphaned_types.append(f"{namespace}/{otype}")
                    # Also add the simple type
                    full_orphaned_types.append(otype)

                result = session.run(query, orphaned_types=full_orphaned_types)

                for record in result:
                    resources = record["resources"]
                    if resources:
                        # Simplify resource types
                        simplified_resources = []
                        for r in resources:
                            simplified_type = self.analyzer._get_resource_type_name(
                                ["Resource"], r["type"]
                            )
                            simplified_resources.append(
                                {
                                    "id": r["id"],
                                    "type": simplified_type,
                                    "name": r["name"],
                                }
                            )

                        # Only include if at least one resource is an orphaned type
                        has_orphaned = any(
                            r["type"] in orphaned_types for r in simplified_resources
                        )

                        if has_orphaned:
                            # Create a pseudo-pattern name for these orphaned instances
                            orphaned_in_instance = {
                                r["type"]
                                for r in simplified_resources
                                if r["type"] in orphaned_types
                            }
                            pseudo_pattern_name = f"Orphaned: {', '.join(sorted(list(orphaned_in_instance)[:3]))}"

                            orphaned_instances.append(
                                (pseudo_pattern_name, simplified_resources)
                            )

        finally:
            driver.close()

        logger.info(
            f"Found {len(orphaned_instances)} instances containing orphaned resource types"
        )

        return orphaned_instances

    def _build_target_pattern_graph_from_instances(
        self, selected_instances: List[Tuple[str, List[Dict[str, Any]]]]
    ) -> nx.MultiDiGraph[str]:
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
        for _pattern_name, instance in selected_instances:
            all_resource_ids.extend([r["id"] for r in instance])

        # Build pattern graph
        target_graph = nx.MultiDiGraph[str]()

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
                for _pattern_name, instance in selected_instances:
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
        self, target_pattern_graph: nx.MultiDiGraph[str]
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

        logger.info(str(f"Generated {len(suggestions)} improvement recommendations"))
        return suggestions

    def _compute_weighted_score(
        self,
        source_graph: nx.DiGraph[str],
        target_graph: nx.DiGraph[str],
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
        spectral_distance = self._compute_spectral_distance(source_graph, target_graph)

        # Compute node coverage penalty (missing types)
        # This is the fraction of source nodes NOT yet in target
        target_node_types = set(target_graph.nodes())
        missing_nodes = source_node_types - target_node_types
        node_coverage_penalty = (
            len(missing_nodes) / len(source_node_types) if source_node_types else 0.0
        )

        # Weighted combination
        # node_coverage_weight = 0.0: score = spectral_distance (original behavior)
        # node_coverage_weight = 1.0: score = node_coverage_penalty (pure greedy)
        # node_coverage_weight = 0.5: score = balanced average
        score = (
            1.0 - node_coverage_weight
        ) * spectral_distance + node_coverage_weight * node_coverage_penalty

        return score

    def _compute_spectral_distance(
        self, graph1: nx.DiGraph[str], graph2: nx.DiGraph[str]
    ) -> float:
        """
        Compute normalized spectral distance using Laplacian eigenvalues.

        Args:
            graph1: First graph
            graph2: Second graph

        Returns:
            Normalized spectral distance
        """
        if len(graph1.nodes()) == 0 or len(graph2.nodes()) == 0:
            return 1.0

        try:
            # Get Laplacian matrices
            L1 = nx.laplacian_matrix(graph1.to_undirected()).toarray()
            L2 = nx.laplacian_matrix(graph2.to_undirected()).toarray()

            # Pad matrices to same size
            max_size = max(L1.shape[0], L2.shape[0])
            L1_padded = np.zeros((max_size, max_size))
            L2_padded = np.zeros((max_size, max_size))
            L1_padded[: L1.shape[0], : L1.shape[1]] = L1
            L2_padded[: L2.shape[0], : L2.shape[1]] = L2

            # Compute eigenvalues
            eigenvals1 = np.sort(np.linalg.eigvalsh(L1_padded))
            eigenvals2 = np.sort(np.linalg.eigvalsh(L2_padded))

            # Compute normalized distance
            diff = eigenvals1 - eigenvals2
            max_eigenval = max(
                np.max(np.abs(eigenvals1)), np.max(np.abs(eigenvals2)), 1.0
            )

            # Use normalized L2 distance
            distance = np.linalg.norm(diff) / (max_eigenval * np.sqrt(max_size))

            return distance

        except Exception as e:
            logger.warning(str(f"Failed to compute spectral distance: {e}"))
            return 1.0
