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
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
from neo4j import GraphDatabase

from .architectural_pattern_analyzer import ArchitecturalPatternAnalyzer

logger = logging.getLogger(__name__)


class ArchitectureBasedReplicator:
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
        self.source_pattern_graph: Optional[nx.MultiDiGraph] = None
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

        total_instances = sum(len(instances) for instances in self.pattern_resources.values())
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

        for rg_id, resources in rg_to_resources.items():
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
                            if connected_id not in instance_ids and connected_id in resource_info:
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
    ) -> Tuple[List[Tuple[str, List[List[Dict[str, Any]]]]], List[float]]:
        """
        Generate tenant replication plan to match source pattern graph.

        The goal is to build a target pattern graph that MATCHES the source pattern graph
        by selecting connected architectural instances one at a time.

        Args:
            target_instance_count: Number of architectural instances to select (default: all)
            hops: Number of hops for local subgraph comparison (default: 2)

        Returns:
            Tuple of (selected instances, spectral distance history)
            where selected instances is a list of (pattern_name, [instances]) tuples,
            and each instance is a list of connected resources
        """
        if not self.source_pattern_graph:
            raise RuntimeError("Must call analyze_source_tenant() first")

        if not self.detected_patterns:
            raise RuntimeError("No patterns detected in source tenant")

        logger.info(
            f"Generating replication plan to match source pattern graph..."
        )
        logger.info(
            f"Source pattern: {self.source_pattern_graph.number_of_nodes()} types, "
            f"{self.source_pattern_graph.number_of_edges()} edges"
        )

        # Collect all instances from all patterns
        all_instances = []
        for pattern_name, instances in self.pattern_resources.items():
            for instance in instances:
                all_instances.append((pattern_name, instance))

        # Default to all instances
        if target_instance_count is None:
            target_instance_count = len(all_instances)

        logger.info(
            f"Will select up to {target_instance_count} architectural instances "
            f"from {len(all_instances)} total available"
        )

        # Sort instances by size (number of resources in instance)
        all_instances.sort(key=lambda x: len(x[1]), reverse=True)

        selected_instances: List[Tuple[str, List[Dict[str, Any]]]] = []
        spectral_history: List[float] = []

        # Strategy: Iteratively select instances that help match the source pattern graph
        for i, (pattern_name, instance) in enumerate(all_instances[:target_instance_count]):
            selected_instances.append((pattern_name, instance))

            # Build current target pattern graph from selected instances
            target_pattern_graph = self._build_target_pattern_graph_from_instances(
                selected_instances
            )

            # Compute spectral distance between source and target PATTERN graphs
            distance = self._compute_spectral_distance(
                self.source_pattern_graph, target_pattern_graph
            )
            spectral_history.append(distance)

            if (i + 1) % 10 == 0 or i < 10:
                logger.info(
                    f"Selected instance {i + 1}/{target_instance_count}: {pattern_name} "
                    f"({len(instance)} resources)"
                )
                logger.info(
                    f"  Target now has {target_pattern_graph.number_of_nodes()} types, "
                    f"{target_pattern_graph.number_of_edges()} edges, "
                    f"spectral distance: {distance:.4f}"
                )

        logger.info(
            f"Replication plan complete: {len(selected_instances)} architectural instances selected"
        )

        final_target = self._build_target_pattern_graph_from_instances(selected_instances)
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
                result = session.run("""
                    MATCH (source)-[r]->(target)
                    WHERE (source:Resource:Original AND source.id IN $ids)
                       OR (target:Resource:Original AND target.id IN $ids)
                    AND type(r) <> 'SCAN_SOURCE_NODE'
                    RETURN labels(source) as source_labels,
                           source.type as source_type,
                           type(r) as rel_type,
                           labels(target) as target_labels,
                           target.type as target_type
                """, ids=all_resource_ids)

                # Collect all relationships
                relationships = []
                for record in result:
                    relationships.append({
                        "source_labels": record["source_labels"],
                        "source_type": record["source_type"],
                        "rel_type": record["rel_type"],
                        "target_labels": record["target_labels"],
                        "target_type": record["target_type"],
                    })

                # Aggregate relationships by type (same as ArchitecturalPatternAnalyzer)
                aggregated = self.analyzer.aggregate_relationships(relationships)

                # Build graph from aggregated relationships
                for rel in aggregated:
                    source_type = rel["source_type"]
                    target_type = rel["target_type"]
                    rel_type = rel["rel_type"]
                    frequency = rel["frequency"]

                    # Add nodes
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
            logger.warning(f"Failed to compute spectral distance: {e}")
            return 1.0
