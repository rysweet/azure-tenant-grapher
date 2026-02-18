"""
Target Graph Builder Brick

Brick for building target pattern graphs from selected architectural instances.

Philosophy:
- Single Responsibility: Graph construction from instances
- Self-contained: Clear public contracts with injected dependencies
- Regeneratable: Stateless operations
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx
from neo4j import GraphDatabase

if TYPE_CHECKING:
    from ...architectural_pattern_analyzer import ArchitecturalPatternAnalyzer

class TargetGraphBuilder:
    """
    Builds target pattern graphs from selected architectural instances.

    This brick provides methods for constructing NetworkX graphs from
    resource instances by querying Neo4j for relationships and aggregating
    them by resource type.

    Dependencies (injected):
        - analyzer: ArchitecturalPatternAnalyzer for relationship aggregation
        - neo4j_uri: Neo4j connection URI
        - neo4j_user: Neo4j username
        - neo4j_password: Neo4j password

    Public Contract:
        - build_from_instances(selected_instances) -> nx.MultiDiGraph
    """

    def __init__(
        self,
        analyzer: ArchitecturalPatternAnalyzer,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
    ):
        """
        Initialize with injected dependencies.

        Args:
            analyzer: ArchitecturalPatternAnalyzer for relationship aggregation
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.analyzer = analyzer
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

    def build_from_instances(
        self, selected_instances: list[tuple[str, list[dict[str, Any]]]]
    ) -> nx.MultiDiGraph:
        """
        Build pattern graph from selected architectural instances.

        This queries Neo4j for actual relationships between the resources
        in the selected instances and aggregates them by resource type to
        create the pattern graph.

        Args:
            selected_instances: List of (pattern_name, instance) tuples,
                               where each instance is a list of connected resources

        Returns:
            Pattern graph (MultiDiGraph) with resource types as nodes and
            relationship types as edges. Nodes have 'count' attribute for
            number of instances of that type. Edges have 'relationship' and
            'frequency' attributes.

        Examples:
            >>> builder = TargetGraphBuilder(analyzer, uri, user, password)
            >>> instances = [
            ...     ("web_app", [{"id": "vm1", "type": "virtualMachines"}]),
            ...     ("database", [{"id": "db1", "type": "sqlServers"}])
            ... ]
            >>> graph = builder.build_from_instances(instances)
            >>> graph.number_of_nodes()
            2
            >>> "virtualMachines" in graph.nodes()
            True
        """
        # Collect all resource IDs from selected instances
        all_resource_ids = []
        for _pattern_name, instance in selected_instances:
            all_resource_ids.extend([r["id"] for r in instance])

        # Build pattern graph
        target_graph = nx.MultiDiGraph()

        # If no instances, return empty graph
        if not all_resource_ids:
            return target_graph

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

    def store_replication_mappings(
        self,
        resource_mappings: dict[str, dict[str, Any]],
    ) -> int:
        """
        Store REPLICATED_FROM relationships in Neo4j after deployment.

        This method creates relationships between target (replicated) resources
        and their source resources, enabling accurate fidelity validation and
        tracking of replication lineage.

        Args:
            resource_mappings: Dict mapping target_resource_id to metadata
                              {"source_resource_id": source_id, ...}

        Returns:
            Number of mappings successfully stored

        Examples:
            >>> builder = TargetGraphBuilder(analyzer, uri, user, password)
            >>> mappings = {
            ...     "target_vm1": {"source_resource_id": "source_vm1"},
            ...     "target_db1": {"source_resource_id": "source_db1"}
            ... }
            >>> count = builder.store_replication_mappings(mappings)
            >>> print(f"Stored {count} mappings")
            Stored 2 mappings
        """
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

        stored_count = 0

        try:
            with driver.session() as session:
                for target_id, mapping in resource_mappings.items():
                    source_id = mapping.get("source_resource_id")
                    if not source_id:
                        continue

                    try:
                        # Create REPLICATED_FROM relationship and store source_id property
                        result = session.run(
                            """
                            MATCH (source:Resource:Original {id: $source_id})
                            MATCH (target:Resource {id: $target_id})
                            MERGE (target)-[:REPLICATED_FROM]->(source)
                            SET target.source_id = $source_id
                            RETURN target.id AS target_id
                            """,
                            source_id=source_id,
                            target_id=target_id,
                        )

                        if result.single():
                            stored_count += 1

                    except Exception as e:
                        # Log error but continue with other mappings
                        print(f"Warning: Failed to store mapping {target_id} -> {source_id}: {e}")
                        continue

        finally:
            driver.close()

        return stored_count


__all__ = ["TargetGraphBuilder"]
