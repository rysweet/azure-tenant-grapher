"""
Pattern Instance Finder Brick

Brick for finding architectural pattern instances from Neo4j graph database.
Handles Neo4j queries for discovering connected resource groups and configuration-coherent instances.

Philosophy:
- Single Responsibility: Neo4j queries for pattern instance discovery
- Self-contained: Clear public contracts with injected dependencies
- Regeneratable: Stateless operations
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from ...architecture_replication_constants import (
    DEFAULT_COHERENCE_THRESHOLD,
    MIN_CLUSTER_SIZE,
)

if TYPE_CHECKING:
    from ...architectural_pattern_analyzer import ArchitecturalPatternAnalyzer
    from .configuration_similarity import ConfigurationSimilarity

logger = logging.getLogger(__name__)


class PatternInstanceFinder:
    """
    Finds architectural pattern instances from Neo4j graph database.

    This brick provides methods for querying Neo4j to discover:
    - Connected pattern instances (grouped by ResourceGroup)
    - Configuration-coherent instances (clustered by similarity)

    Dependencies (injected):
        - analyzer: ArchitecturalPatternAnalyzer for type resolution and fingerprinting
        - config_similarity: ConfigurationSimilarity for clustering

    Public Contract:
        - find_connected_instances(session, matched_types, ...) -> list[list[dict]]
        - find_configuration_coherent_instances(session, matched_types, ...) -> list[list[dict]]
    """

    def __init__(
        self,
        analyzer: ArchitecturalPatternAnalyzer,
        config_similarity: ConfigurationSimilarity,
    ):
        """
        Initialize with injected dependencies.

        Args:
            analyzer: ArchitecturalPatternAnalyzer for resource type resolution
            config_similarity: ConfigurationSimilarity for clustering resources
        """
        self.analyzer = analyzer
        self.config_similarity = config_similarity

    def find_connected_instances(
        self,
        session,
        matched_types: set[str],
        pattern_name: str,
        detected_patterns: dict[str, dict[str, Any]],
        include_colocated_orphaned_resources: bool = True,
    ) -> list[list[dict[str, Any]]]:
        """
        Find connected instances of an architectural pattern.

        Architectural instances are groups of resources that share a common parent
        (ResourceGroup) and match the pattern's resource types. This reflects how
        the instance resource graph creates the pattern graph through aggregation.

        If include_colocated_orphaned_resources is True, also includes orphaned resource
        types (not in any pattern) that co-locate in the same ResourceGroup as pattern
        resources. This preserves source tenant co-location relationships.

        Args:
            session: Neo4j session for queries
            matched_types: Resource types that match this pattern
            pattern_name: Name of the pattern
            detected_patterns: All detected patterns (for orphan detection)
            include_colocated_orphaned_resources: Include orphaned resources from same RG

        Returns:
            List of architectural instances, where each instance is a list of resources
            that belong together (same ResourceGroup).

        Examples:
            >>> finder = PatternInstanceFinder(analyzer, config_similarity)
            >>> instances = finder.find_connected_instances(
            ...     session,
            ...     matched_types={"virtualMachines", "disks", "networkInterfaces"},
            ...     pattern_name="VM Infrastructure",
            ...     detected_patterns={...}
            ... )
            >>> len(instances)
            3  # 3 connected instances found
        """
        # Compute all pattern types across all detected patterns (for orphan detection)
        all_pattern_types = set()
        for pattern_info in detected_patterns.values():
            all_pattern_types.update(pattern_info["matched_resources"])

        # Query to find all ORIGINAL resources along with their ResourceGroup
        query = """
        MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
        RETURN r.id as id, r.type as type, r.name as name, rg.id as resource_group_id
        """

        result = session.run(query)

        # Build mapping: ResourceGroup -> List of resources in that RG
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
                if (
                    include_colocated_orphaned_resources
                    and rg_id in rg_to_all_resources
                ):
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

    def find_configuration_coherent_instances(
        self,
        session,
        pattern_name: str,
        matched_types: set[str],
        detected_patterns: dict[str, dict[str, Any]],
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
        include_colocated_orphaned_resources: bool = True,
    ) -> list[list[dict[str, Any]]]:
        """
        Find architectural instances with configuration coherence.

        Instead of grouping resources only by ResourceGroup, this method
        splits ResourceGroups into configuration-coherent clusters where
        resources have similar configurations (same location, similar tier, etc.).

        If include_colocated_orphaned_resources is True, also includes orphaned resource
        types (not in any pattern) that co-locate in the same ResourceGroup as pattern
        resources. This preserves source tenant co-location relationships.

        Args:
            session: Neo4j session for queries
            pattern_name: Name of the architectural pattern
            matched_types: Set of resource types in this pattern
            detected_patterns: All detected patterns (for orphan detection)
            coherence_threshold: Minimum similarity score for resources to be in same instance (0.0-1.0)
            include_colocated_orphaned_resources: Include orphaned resources from same RG

        Returns:
            List of configuration-coherent instances

        Examples:
            >>> finder = PatternInstanceFinder(analyzer, config_similarity)
            >>> instances = finder.find_configuration_coherent_instances(
            ...     session,
            ...     pattern_name="Web Application",
            ...     matched_types={"sites", "serverFarms", "storageAccounts"},
            ...     detected_patterns={...},
            ...     coherence_threshold=0.7
            ... )
            >>> len(instances)
            5  # 5 coherent clusters found
        """
        # Compute all pattern types across all detected patterns (for orphan detection)
        all_pattern_types = set()
        for pattern_info in detected_patterns.values():
            all_pattern_types.update(pattern_info["matched_resources"])

        # Query for resources
        if include_colocated_orphaned_resources:
            # Get ALL resources to identify orphans
            query = """
            MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
            RETURN rg.id as resource_group_id,
                   r.id as id,
                   r.type as type,
                   r.name as name,
                   r.location as location,
                   r.tags as tags,
                   r.properties as properties
            ORDER BY rg.id
            """
            result = session.run(query)
        else:
            # Original behavior: only get pattern type resources
            query = """
            MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
            WHERE r.type IN $types
            RETURN rg.id as resource_group_id,
                   r.id as id,
                   r.type as type,
                   r.name as name,
                   r.location as location,
                   r.tags as tags,
                   r.properties as properties
            ORDER BY rg.id
            """

            # Convert simplified types to full Azure types
            full_types = []
            for simplified in matched_types:
                # Common namespace patterns
                for namespace in [
                    "Microsoft.Compute",
                    "Microsoft.Network",
                    "Microsoft.Storage",
                    "Microsoft.Web",
                    "Microsoft.Insights",
                    "Microsoft.Sql",
                    "Microsoft.KeyVault",
                    "Microsoft.ContainerRegistry",
                    "Microsoft.ContainerService",
                ]:
                    full_types.append(f"{namespace}/{simplified}")

            result = session.run(query, types=full_types)

        # Group by ResourceGroup first
        rg_to_pattern_resources = {}  # Only pattern types
        rg_to_all_resources = {}  # All resources (for orphan inclusion)
        resource_fingerprints = {}

        for record in result:
            simplified_type = self.analyzer._get_resource_type_name(
                ["Resource"], record["type"]
            )

            resource_id = record["id"]
            rg_id = record["resource_group_id"]

            # Parse properties if JSON string
            properties = record["properties"]
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    properties = None

            # Create configuration fingerprint
            fingerprint = self.analyzer.create_configuration_fingerprint(
                resource_id,
                record["type"],
                record["location"],
                record["tags"],
                properties,
            )

            resource = {
                "id": resource_id,
                "type": simplified_type,
                "name": record["name"],
            }

            # Track all resources if including orphaned
            if include_colocated_orphaned_resources:
                if rg_id not in rg_to_all_resources:
                    rg_to_all_resources[rg_id] = []
                rg_to_all_resources[rg_id].append((simplified_type, resource))

            # Only include pattern-matching resources in clustering
            if simplified_type not in matched_types:
                continue

            # This resource matches the pattern - add to pattern tracking
            if rg_id not in rg_to_pattern_resources:
                rg_to_pattern_resources[rg_id] = []

            rg_to_pattern_resources[rg_id].append(resource)
            resource_fingerprints[resource_id] = fingerprint

        if not rg_to_pattern_resources:
            return []

        # Now split each ResourceGroup into configuration-coherent clusters
        all_instances = []

        for rg_id, resources in rg_to_pattern_resources.items():
            if len(resources) < MIN_CLUSTER_SIZE:
                # < 2 resources, trivially coherent
                all_instances.append(resources)
                continue

            # Cluster resources by configuration coherence
            clusters = self.config_similarity.cluster_by_coherence(
                resources, resource_fingerprints, coherence_threshold
            )

            # Add orphaned resources if enabled
            for cluster in clusters:
                if (
                    include_colocated_orphaned_resources
                    and rg_id in rg_to_all_resources
                ):
                    orphaned_count = 0
                    for resource_type, resource in rg_to_all_resources[rg_id]:
                        # Check if this resource type is NOT in any pattern (orphaned)
                        if resource_type not in all_pattern_types:
                            # Check if not already in cluster (avoid duplicates)
                            if not any(r["id"] == resource["id"] for r in cluster):
                                cluster.append(resource)
                                orphaned_count += 1

                    if orphaned_count > 0:
                        logger.debug(
                            f"  Added {orphaned_count} co-located orphaned resources "
                            f"to cluster in RG {rg_id}"
                        )

                all_instances.append(cluster)

        logger.debug(
            f"  Found {len(all_instances)} configuration-coherent instances "
            f"(threshold: {coherence_threshold})"
        )

        return all_instances


__all__ = ["PatternInstanceFinder"]
