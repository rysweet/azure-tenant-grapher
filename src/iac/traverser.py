"""Graph traversal functionality for IaC generation.

This module provides graph traversal and data structure definitions
for converting Neo4j tenant graphs into IaC representations.

Includes dependency-aware traversal using topological sort (Kahn's algorithm)
to ensure resources are ordered by dependencies for proper IaC deployment.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, LiteralString, Optional, Set, cast

from neo4j import Driver

logger = logging.getLogger(__name__)


@dataclass
class TenantGraph:
    """Data structure representing a tenant's infrastructure graph."""

    resources: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)


class GraphTraverser:
    """Traverses Neo4j graph data to extract tenant infrastructure."""

    def __init__(
        self, driver: Driver, transformation_rules: Optional[List[Any]] = None
    ) -> None:
        """Initialize graph traverser with Neo4j driver.

        Args:
            driver: Neo4j database driver instance
            transformation_rules: Optional transformation rules (for future use)
        """
        self.driver = driver
        self.transformation_rules = transformation_rules or []

    async def traverse(
        self,
        filter_cypher: Optional[str] = None,
        use_original_ids: bool = False,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> TenantGraph:
        """Traverse and extract tenant graph data.

        Args:
            filter_cypher: Optional Cypher filter string
            use_original_ids: If True, query Original nodes; if False (default), query Abstracted nodes
            parameters: Optional dictionary of query parameters (Issue #524: for parameterized queries)

        Returns:
            TenantGraph instance with extracted data
        """
        logger.info("Starting graph traversal")
        parameters = parameters or {}

        def process_result(
            result: list[Any],
            resources: list[dict[str, Any]],
            relationships: list[dict[str, Any]],
        ) -> None:
            for record in result:
                resource_node = record["r"]
                rels = record["rels"] if "rels" in record else []

                # Convert resource node to dict
                resource_dict = dict(resource_node)

                # Bug #15 fix: Add original_id from query result if available
                # This enables smart import comparison without querying Neo4j for each resource
                if record.get("original_id"):
                    resource_dict["original_id"] = record["original_id"]

                # Bug #96 fix: Add original_properties from query result if available
                # This enables using original principal IDs for same-tenant role assignments
                if record.get("original_properties"):
                    resource_dict["original_properties"] = record["original_properties"]

                resources.append(resource_dict)

                # Process relationships
                for rel in rels:
                    if rel and rel.get("target"):  # Only add valid relationships
                        relationship_dict = {
                            "source": resource_node.get("id"),
                            "target": rel.get("target"),
                            "type": rel.get("type"),
                        }

                        # Add additional properties for GENERIC_RELATIONSHIP
                        if rel.get("type") == "GENERIC_RELATIONSHIP":
                            if rel.get("original_type"):
                                relationship_dict["original_type"] = rel.get(
                                    "original_type"
                                )
                            if rel.get("narrative_context"):
                                relationship_dict["narrative_context"] = rel.get(
                                    "narrative_context"
                                )

                        relationships.append(relationship_dict)

        if filter_cypher:
            query = filter_cypher
        else:
            # Default query - use abstracted nodes unless explicitly requesting original
            if use_original_ids:
                # Query Original nodes only (for legacy/debug purposes)
                query = """
                MATCH (r:Resource:Original)
                OPTIONAL MATCH (r)-[rel]->(t:Resource:Original)
                RETURN r, collect({
                    type: type(rel),
                    target: t.id,
                    original_type: rel.original_type,
                    narrative_context: rel.narrative_context
                }) AS rels
                """
            else:
                # Query ALL Resource nodes (both Original and Abstracted for IaC generation)
                # Priority: Abstracted nodes are preferred when both exist
                # This ensures we get all resources while using abstracted IDs when available
                # Bug #15 fix: Include original_id from SCAN_SOURCE_NODE relationship
                # for smart import comparison
                query = """
                MATCH (r:Resource)
                WHERE NOT EXISTS {
                    MATCH (abstracted:Resource)
                    WHERE NOT abstracted:Original
                    AND abstracted.original_id = r.id
                    AND r:Original
                }
                OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
                OPTIONAL MATCH (r)-[rel]->(t:Resource)
                WHERE NOT EXISTS {
                    MATCH (t_abstracted:Resource)
                    WHERE NOT t_abstracted:Original
                    AND t_abstracted.original_id = t.id
                    AND t:Original
                }
                RETURN r, orig.id AS original_id, orig.properties AS original_properties, collect({
                    type: type(rel),
                    target: t.id,
                    original_type: rel.original_type,
                    narrative_context: rel.original_type
                }) AS rels
                """

        resources = []
        relationships = []

        try:
            with self.driver.session() as session:
                # Issue #524: Pass parameters to prevent Cypher injection
                result = session.run(cast("LiteralString", query), parameters)  # type: ignore[arg-type]
                # Check if result is empty (consume iterator)
                result_list = list(result)
                if not result_list and not filter_cypher:
                    # Fallback query if no :Resource nodes found and not using a filter
                    # Respect use_original_ids flag in fallback too
                    if use_original_ids:
                        fallback_query = """
                        MATCH (r)
                        WHERE r.type IS NOT NULL
                        OPTIONAL MATCH (r)-[rel]->(t)
                        RETURN r, collect({
                            type: type(rel),
                            target: t.id,
                            original_type: rel.original_type,
                            narrative_context: rel.narrative_context
                        }) AS rels
                        """
                        logger.info(
                            "No :Resource:Original nodes found, running fallback query for any nodes with 'type' property"
                        )
                    else:
                        fallback_query = """
                        MATCH (r)
                        WHERE r.type IS NOT NULL AND NOT EXISTS {MATCH (r:Original)}
                        OPTIONAL MATCH (r)-[rel]->(t)
                        WHERE NOT EXISTS {MATCH (t:Original)}
                        RETURN r, collect({
                            type: type(rel),
                            target: t.id,
                            original_type: rel.original_type,
                            narrative_context: rel.narrative_context
                        }) AS rels
                        """
                        logger.info(
                            "No abstracted :Resource nodes found, running fallback query for non-Original nodes with 'type' property"
                        )
                    # Fallback queries don't use parameters (no user input)
                    result = session.run(cast("LiteralString", fallback_query))  # type: ignore[arg-type]
                    result_list = list(result)
                process_result(result_list, resources, relationships)
                logger.info(
                    f"Extracted {len(resources)} resources and {len(relationships)} relationships"
                )

        except Exception as e:
            logger.error(str(f"Error during graph traversal: {e}"))
            raise

        return TenantGraph(resources=resources, relationships=relationships)

    def topological_sort(
        self,
        graph: TenantGraph,
        relationship_types: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Sort resources by dependency order using Kahn's algorithm.

        Args:
            graph: TenantGraph with resources and relationships
            relationship_types: List of relationship types to consider (default: ["CONTAINS", "DEPENDS_ON"])
            max_depth: Optional maximum depth for traversal (default: unlimited)

        Returns:
            List of resources sorted in dependency order (dependencies first)

        Raises:
            ValueError: If circular dependencies are detected
        """
        if relationship_types is None:
            relationship_types = ["CONTAINS", "DEPENDS_ON"]

        logger.info(
            f"Performing topological sort on {len(graph.resources)} resources "
            f"using relationship types: {relationship_types}"
        )

        # Build resource ID to resource mapping
        resource_map = {r["id"]: r for r in graph.resources}

        # Filter relationships by type
        filtered_rels = [
            rel for rel in graph.relationships if rel.get("type") in relationship_types
        ]

        logger.debug(
            f"Filtered to {len(filtered_rels)} relationships from {len(graph.relationships)} total"
        )

        # Build adjacency lists and in-degree counts
        # Graph structure: source -> [targets] (resource depends on target)
        adj_list: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = defaultdict(int)

        # Initialize all resources with in_degree 0
        for resource in graph.resources:
            rid = resource["id"]
            in_degree[rid] = 0

        # Build graph from relationships
        for rel in filtered_rels:
            source = rel.get("source")
            target = rel.get("target")

            # Only consider relationships where both nodes exist
            if source in resource_map and target in resource_map:
                adj_list[target].append(
                    source
                )  # Target -> Source (reverse for topo sort)
                in_degree[source] += 1

        # Kahn's algorithm: Start with nodes that have no dependencies
        queue: deque = deque()
        for rid, degree in in_degree.items():
            if degree == 0:
                queue.append(rid)

        sorted_resources: List[Dict[str, Any]] = []
        depth_map: Dict[str, int] = {}

        # Initialize depth for roots
        for rid in queue:
            depth_map[rid] = 0

        while queue:
            current_id = queue.popleft()
            current_resource = resource_map[current_id]
            current_depth = depth_map.get(current_id, 0)

            # Skip if exceeds max_depth
            if max_depth is not None and current_depth > max_depth:
                continue

            sorted_resources.append(current_resource)

            # Process neighbors (resources that depend on current)
            for neighbor_id in adj_list[current_id]:
                in_degree[neighbor_id] -= 1

                # Update depth
                neighbor_depth = current_depth + 1
                depth_map[neighbor_id] = max(
                    depth_map.get(neighbor_id, 0), neighbor_depth
                )

                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        # Check for cycles (only if not using max_depth filter)
        if len(sorted_resources) < len(graph.resources):
            # Check if this is due to max_depth filtering or actual cycles
            if max_depth is None:
                # Find resources involved in cycles
                cycle_resources = [
                    rid for rid, degree in in_degree.items() if degree > 0
                ]
                cycle_details = self._detect_cycle_details(
                    cycle_resources, adj_list, resource_map
                )

                error_msg = (
                    f"Circular dependency detected! {len(cycle_resources)} resources "
                    f"are involved in dependency cycles:\n{cycle_details}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                # Resources filtered out by max_depth - this is expected
                logger.debug(
                    f"Filtered {len(graph.resources) - len(sorted_resources)} resources "
                    f"due to max_depth={max_depth}"
                )

        logger.info(
            f"Topological sort complete: {len(sorted_resources)} resources ordered"
        )

        # Log depth distribution
        depth_counts: Dict[int, int] = defaultdict(int)
        for depth in depth_map.values():
            depth_counts[depth] += 1

        logger.info("Resource depth distribution:")
        for depth in sorted(depth_counts.keys()):
            logger.info(f"  Depth {depth}: {depth_counts[depth]} resources")

        return sorted_resources

    def _detect_cycle_details(
        self,
        cycle_resources: List[str],
        adj_list: Dict[str, List[str]],
        resource_map: Dict[str, Dict[str, Any]],
    ) -> str:
        """Detect and format cycle details for error messages.

        Args:
            cycle_resources: List of resource IDs involved in cycles
            adj_list: Adjacency list (target -> [sources])
            resource_map: Map of resource ID to resource dict

        Returns:
            Formatted string describing the cycles
        """
        cycle_details = []
        visited: Set[str] = set()

        for start_id in cycle_resources[:5]:  # Limit to first 5 cycles
            if start_id in visited:
                continue

            # Try to find a cycle starting from this resource
            path = []
            current = start_id
            path_set: Set[str] = set()

            while current not in visited:
                if current in path_set:
                    # Found a cycle
                    cycle_start_idx = path.index(current)
                    cycle_path = path[cycle_start_idx:]
                    cycle_path.append(current)  # Close the cycle

                    # Format cycle
                    cycle_names = []
                    for rid in cycle_path:
                        resource = resource_map.get(rid, {})
                        name = resource.get("name", rid)
                        res_type = resource.get("type", "unknown")
                        cycle_names.append(f"{name} ({res_type})")

                    cycle_details.append(" -> ".join(cycle_names))
                    visited.update(path)
                    break

                visited.add(current)
                path.append(current)
                path_set.add(current)

                # Move to next node in adjacency list
                neighbors = adj_list.get(current, [])
                if neighbors:
                    current = neighbors[0]
                else:
                    break

        if cycle_details:
            return "\n".join(
                f"  Cycle {i + 1}: {cycle}" for i, cycle in enumerate(cycle_details)
            )
        else:
            return f"  {len(cycle_resources)} resources have unresolved dependencies"
