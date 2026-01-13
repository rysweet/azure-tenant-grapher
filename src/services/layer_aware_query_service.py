"""
Layer-Aware Query Service

This service provides query operations that respect layer boundaries.
All queries default to the active layer unless explicitly specified.

Key Features:
- Layer-aware resource queries
- Relationship traversal within layers
- Access to Original nodes for cross-reference
- Layer isolation guarantees

Thread Safety: All methods are thread-safe via Neo4j sessions
"""

import logging
from typing import Any, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.services.layer import (
    LayerManagementService,
    LayerNotFoundError,
)
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class LayerAwareQueryService:
    """
    Service for querying resources with layer awareness.

    All queries default to active layer unless explicitly specified.
    Ensures layer isolation and prevents cross-layer contamination.
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        layer_service: LayerManagementService,
    ):
        """
        Initialize the layer-aware query service.

        Args:
            session_manager: Neo4j session manager for database operations
            layer_service: Layer management service for layer metadata
        """
        self.session_manager = session_manager
        self.layer_service = layer_service
        self.logger = logging.getLogger(__name__)

    async def _get_effective_layer_id(self, layer_id: Optional[str] = None) -> str:
        """
        Get effective layer ID (provided or active).

        Args:
            layer_id: Explicit layer ID or None for active

        Returns:
            Layer ID to use for query

        Raises:
            ValueError: If no active layer and no layer_id provided
            LayerNotFoundError: If specified layer doesn't exist
        """
        if layer_id:
            # Verify layer exists
            layer = await self.layer_service.get_layer(layer_id)
            if not layer:
                raise LayerNotFoundError(layer_id)
            return layer_id

        # Use active layer
        active_layer = await self.layer_service.get_active_layer()
        if not active_layer:
            raise ValueError(
                "No active layer set and no layer_id specified. "
                "Use layer_service.set_active_layer() or provide layer_id."
            )

        return active_layer.layer_id

    async def get_resource(
        self,
        resource_id: str,
        layer_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a resource from specified or active layer.

        Args:
            resource_id: Resource ID (abstracted ID, not Azure ID)
            layer_id: Specific layer, or None for active

        Returns:
            Resource properties dict, or None if not found

        Example:
            # From active layer
            resource = await service.get_resource("vm-a1b2c3d4")

            # From specific layer
            resource = await service.get_resource("vm-a1b2c3d4", layer_id="scaled-v1")
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.id = $resource_id
          AND r.layer_id = $layer_id
        RETURN properties(r) as props
        """

        with self.session_manager.session() as session:
            result = session.run(
                query,
                {"resource_id": resource_id, "layer_id": effective_layer_id},
            )
            record = result.single()

            if not record:
                return None

            return dict(record["props"])

    async def find_resources(
        self,
        resource_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        layer_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Find resources matching criteria in layer.

        Args:
            resource_type: Filter by type (e.g., "VirtualMachine")
            filters: Property filters {"name": "prod-vm-*", "location": "eastus"}
            layer_id: Specific layer, or None for active
            limit: Max results
            offset: Skip first N results

        Returns:
            List of resource dicts

        Example:
            # Find all VMs in active layer
            vms = await service.find_resources(resource_type="VirtualMachine")

            # Find VNets in specific region
            vnets = await service.find_resources(
                resource_type="VirtualNetwork",
                filters={"location": "eastus"}
            )
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        # Build query dynamically
        where_clauses = [
            "NOT r:Original",
            "r.layer_id = $layer_id",
        ]
        params: Dict[str, Any] = {"layer_id": effective_layer_id}

        if resource_type:
            where_clauses.append("r.type = $resource_type")
            params["resource_type"] = resource_type

        # Apply property filters safely using SafeCypherBuilder
        if filters:
            from src.utils.safe_cypher_builder import (
                validate_filter_keys,
            )

            # Define allowed filter keys for resources
            ALLOWED_FILTER_KEYS = {
                "id",
                "name",
                "type",
                "location",
                "resource_group",
                "subscription_id",
                "layer_id",
                "tenant_id",
                "sku",
                "kind",
                "provisioning_state",
            }

            # Validate all filter keys against whitelist
            validate_filter_keys(filters, ALLOWED_FILTER_KEYS)

            # Build parameterized WHERE clauses safely
            for key, value in filters.items():
                param_name = f"filter_{key.replace('.', '_')}"
                where_clauses.append(f"r.{key} = ${param_name}")
                params[param_name] = value

        where_clause = " AND ".join(where_clauses)

        query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN properties(r) as props
        """

        # Add pagination (safe - using integer values, not user input in query string)
        if offset > 0:
            query += f" SKIP {offset}"
        if limit:
            query += f" LIMIT {limit}"

        resources = []

        with self.session_manager.session() as session:
            result = session.run(query, params)

            for record in result:
                resources.append(dict(record["props"]))

        return resources

    async def traverse_relationships(
        self,
        start_resource_id: str,
        relationship_type: str,
        direction: str = "outgoing",
        layer_id: Optional[str] = None,
        depth: int = 1,
        include_path: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Traverse relationships within a layer.

        Args:
            start_resource_id: Starting node
            relationship_type: Relationship to follow (e.g., "CONTAINS")
            direction: "outgoing", "incoming", "both"
            layer_id: Layer to traverse
            depth: Max traversal depth
            include_path: Include full path in results

        Returns:
            List of connected resources

        Guarantees:
            - Never crosses layer boundaries
            - All returned nodes have same layer_id

        Example:
            # Find all VMs in a VNet
            vms = await service.traverse_relationships(
                start_resource_id="vnet-12345",
                relationship_type="CONTAINS",
                depth=2  # VNet -> Subnet -> VM
            )
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        # Build relationship pattern based on direction
        if direction == "outgoing":
            rel_pattern = f"-[rel:{relationship_type}]->"
        elif direction == "incoming":
            rel_pattern = f"<-[rel:{relationship_type}]-"
        elif direction == "both":
            rel_pattern = f"-[rel:{relationship_type}]-"
        else:
            raise ValueError(f"Invalid direction: {direction}")

        # Build variable-length pattern for depth
        if depth > 1:
            rel_pattern = rel_pattern.replace("]", f"*1..{depth}]")

        query = f"""
        MATCH path = (start:Resource){rel_pattern}(target:Resource)
        WHERE NOT start:Original AND NOT target:Original
          AND start.id = $start_resource_id
          AND start.layer_id = $layer_id
          AND target.layer_id = $layer_id
        RETURN DISTINCT target, properties(target) as props
        """

        resources = []

        with self.session_manager.session() as session:
            result = session.run(
                query,
                {
                    "start_resource_id": start_resource_id,
                    "layer_id": effective_layer_id,
                },
            )

            for record in result:
                resources.append(dict(record["props"]))

        return resources

    async def get_resource_original(
        self,
        resource_id: str,
        layer_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the :Original node for a resource.

        Args:
            resource_id: Abstracted resource ID
            layer_id: Layer context

        Returns:
            Original node properties (with real Azure ID)

        Use Cases:
            - Cross-reference abstracted IDs to Azure IDs
            - Validate abstraction correctness
            - Debug ID translation

        Example:
            original = await service.get_resource_original("vm-a1b2c3d4")
            azure_id = original["id"]  # Real Azure resource ID
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        query = """
        MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)
        WHERE NOT r:Original
          AND r.id = $resource_id
          AND r.layer_id = $layer_id
        RETURN properties(orig) as props
        """

        with self.session_manager.session() as session:
            result = session.run(
                query,
                {"resource_id": resource_id, "layer_id": effective_layer_id},
            )
            record = result.single()

            if not record:
                return None

            return dict(record["props"])

    async def count_resources(
        self,
        resource_type: Optional[str] = None,
        layer_id: Optional[str] = None,
    ) -> int:
        """
        Count resources in layer.

        Args:
            resource_type: Filter by type (None = all types)
            layer_id: Layer to count

        Returns:
            Resource count

        Example:
            total = await service.count_resources()
            vms = await service.count_resources(resource_type="VirtualMachine")
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        where_clauses = [
            "NOT r:Original",
            "r.layer_id = $layer_id",
        ]
        params: Dict[str, Any] = {"layer_id": effective_layer_id}

        if resource_type:
            where_clauses.append("r.type = $resource_type")
            params["resource_type"] = resource_type

        where_clause = " AND ".join(where_clauses)

        query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN count(r) as count
        """

        with self.session_manager.session() as session:
            result = session.run(query, params)
            record = result.single()

            return record["count"] if record else 0

    async def get_layer_statistics(
        self, layer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a layer.

        Args:
            layer_id: Layer to analyze, or None for active

        Returns:
            Dict with statistics including:
            - total_nodes: Total resource count
            - total_relationships: Total relationship count
            - resource_types: Dict of type -> count
            - relationship_types: Dict of type -> count
            - avg_degree: Average node degree

        Example:
            stats = await service.get_layer_statistics()
            print(f"Layer has {stats['total_nodes']} resources")
            print(f"Most common type: {max(stats['resource_types'].items(), key=lambda x: x[1])}")
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        stats = {}

        with self.session_manager.session() as session:
            # Total nodes
            result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN count(r) as count
                """,
                {"layer_id": effective_layer_id},
            )
            stats["total_nodes"] = result.single()["count"]

            # Total relationships
            result = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": effective_layer_id},
            )
            stats["total_relationships"] = result.single()["count"]

            # Resource type distribution
            result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN r.type as type, count(r) as count
                ORDER BY count DESC
                """,
                {"layer_id": effective_layer_id},
            )
            stats["resource_types"] = {
                record["type"]: record["count"] for record in result
            }

            # Relationship type distribution
            result = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN type(rel) as type, count(rel) as count
                ORDER BY count DESC
                """,
                {"layer_id": effective_layer_id},
            )
            stats["relationship_types"] = {
                record["type"]: record["count"] for record in result
            }

            # Average degree
            if stats["total_nodes"] > 0:
                stats["avg_degree"] = (stats["total_relationships"] * 2) / stats[
                    "total_nodes"
                ]
            else:
                stats["avg_degree"] = 0.0

        return stats

    async def exists_in_layer(
        self,
        resource_id: str,
        layer_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a resource exists in a layer.

        Args:
            resource_id: Resource ID to check
            layer_id: Layer to check, or None for active

        Returns:
            True if resource exists in layer, False otherwise

        Example:
            if await service.exists_in_layer("vm-a1b2c3d4"):
                print("Resource exists in active layer")
        """
        resource = await self.get_resource(resource_id, layer_id)
        return resource is not None

    async def get_connected_components(
        self, layer_id: Optional[str] = None
    ) -> List[List[str]]:
        """
        Get weakly connected components in layer.

        Args:
            layer_id: Layer to analyze, or None for active

        Returns:
            List of components, where each component is a list of resource IDs

        Example:
            components = await service.get_connected_components()
            print(str(f"Found {len(components)} connected components"))
            print(str(f"Largest component has {len(components[0])} resources"))
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        # Use Neo4j's connected components algorithm if available
        # Otherwise fall back to manual traversal
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original AND r.layer_id = $layer_id
        WITH collect(r) as nodes
        CALL gds.alpha.wcc.stream({
            nodeProjection: 'Resource',
            relationshipProjection: '*',
            nodeQuery: 'MATCH (n:Resource) WHERE NOT n:Original AND n.layer_id = $layer_id RETURN id(n) as id'
        })
        YIELD nodeId, componentId
        RETURN componentId, collect(gds.util.asNode(nodeId).id) as resources
        ORDER BY size(resources) DESC
        """

        components = []

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"layer_id": effective_layer_id})

                for record in result:
                    components.append(record["resources"])
        except Neo4jError as e:
            # GDS not available, use simple traversal
            self.logger.warning(str(f"GDS not available, using simple traversal: {e}"))

            # Fallback: simple connected components via traversal
            with self.session_manager.session() as session:
                # Get all nodes
                result = session.run(
                    """
                    MATCH (r:Resource)
                    WHERE NOT r:Original AND r.layer_id = $layer_id
                    RETURN collect(r.id) as ids
                    """,
                    {"layer_id": effective_layer_id},
                )
                all_ids = set(result.single()["ids"])

                visited = set()

                while all_ids:
                    # Start new component
                    start_id = all_ids.pop()
                    component = {start_id}
                    visited.add(start_id)

                    # BFS from start_id
                    frontier = [start_id]

                    while frontier:
                        current = frontier.pop(0)

                        # Get neighbors
                        result = session.run(
                            """
                            MATCH (r:Resource {id: $current_id, layer_id: $layer_id})
                            MATCH (r)-[]-(neighbor:Resource)
                            WHERE NOT neighbor:Original
                              AND neighbor.layer_id = $layer_id
                            RETURN collect(DISTINCT neighbor.id) as neighbor_ids
                            """,
                            {
                                "current_id": current,
                                "layer_id": effective_layer_id,
                            },
                        )

                        neighbor_ids = result.single()["neighbor_ids"]

                        for neighbor_id in neighbor_ids:
                            if neighbor_id not in visited:
                                visited.add(neighbor_id)
                                component.add(neighbor_id)
                                frontier.append(neighbor_id)
                                all_ids.discard(neighbor_id)

                    components.append(list(component))

                # Sort by size descending
                components.sort(key=len, reverse=True)

        return components

    async def get_resources_by_ids(
        self,
        resource_ids: List[str],
        layer_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get multiple resources by ID in batch.

        Args:
            resource_ids: List of resource IDs
            layer_id: Layer to query, or None for active

        Returns:
            List of resource dicts (in same order as input, None for missing)

        Example:
            resources = await service.get_resources_by_ids([
                "vm-1", "vm-2", "vm-3"
            ])
        """
        effective_layer_id = await self._get_effective_layer_id(layer_id)

        query = """
        UNWIND $resource_ids as rid
        OPTIONAL MATCH (r:Resource {id: rid, layer_id: $layer_id})
        WHERE NOT r:Original
        RETURN rid, properties(r) as props
        """

        with self.session_manager.session() as session:
            result = session.run(
                query,
                {
                    "resource_ids": resource_ids,
                    "layer_id": effective_layer_id,
                },
            )

            # Build result map
            result_map = {}
            for record in result:
                rid = record["rid"]
                props = record["props"]
                result_map[rid] = dict(props) if props else None

            # Return in order
            return [result_map.get(rid) for rid in resource_ids]
