"""Replication plan to TenantGraph conversion service.

This module provides conversion functionality to transform architecture-based
replication plans (pattern-based resource selection) into TenantGraph structures
suitable for IaC generation and deployment.

The conversion bridges the gap between:
- Pattern-level analysis (type-based aggregation)
- Instance-level deployment (specific resources with relationships)

Key Responsibility:
- Flatten nested replication plan structure
- Query Neo4j for instance-level relationships
- Apply pattern and instance filtering
- Construct TenantGraph for IaC emitters

Philosophy:
- Ruthless simplicity: Each function has one clear purpose
- Zero-BS: All data comes from Neo4j, no inference or guessing
- Modular: Each helper function is independently testable
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from neo4j import AsyncSession

from ..iac.traverser import TenantGraph

logger = logging.getLogger(__name__)

# Type alias for replication plan structure
ReplicationPlan = Tuple[
    List[Tuple[str, List[List[Dict[str, Any]]]]],  # selected_instances by pattern
    List[float],  # spectral_history
    Optional[Dict[str, Any]],  # distribution_metadata
]

# Default relationship types for deployment
DEFAULT_RELATIONSHIP_TYPES = [
    "CONTAINS",
    "DEPENDS_ON",
    "DIAGNOSTIC_TARGET",
    "MONITORS",
    "TAG_RELATIONSHIP",
]


def _flatten_resources(
    selected_instances: List[Tuple[str, List[List[Dict[str, Any]]]]],
    pattern_filter: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Extract flat resource list and resource IDs from nested replication plan.

    Args:
        selected_instances: Nested structure from replication plan
            Format: [(pattern_name, [instance1, instance2, ...]), ...]
            Each instance is a list of resource dicts
        pattern_filter: Optional list of pattern names to include (filters others out)

    Returns:
        Tuple of:
            - Flat list of all resource dicts
            - Set of all resource IDs (for relationship queries)

    Example:
        Input: [("Web App", [[{id: "vm1"}, {id: "nic1"}], [{id: "vm2"}]])]
        Output: ([{id: "vm1"}, {id: "nic1"}, {id: "vm2"}], {"vm1", "nic1", "vm2"})
    """
    flat_resources: List[Dict[str, Any]] = []
    resource_ids: Set[str] = set()

    for pattern_name, instances in selected_instances:
        # Apply pattern filter if specified
        if pattern_filter and pattern_name not in pattern_filter:
            logger.debug(f"Skipping pattern '{pattern_name}' (not in filter)")
            continue

        # Flatten instances (each instance is a list of resources)
        for instance in instances:
            for resource in instance:
                flat_resources.append(resource)
                resource_ids.add(resource["id"])

    logger.info(
        f"Flattened {len(flat_resources)} resources from "
        f"{len(selected_instances)} patterns"
    )

    return flat_resources, resource_ids


def _filter_instances(
    instances: List[List[Dict[str, Any]]], instance_filter: Optional[str]
) -> List[List[Dict[str, Any]]]:
    """Filter instances by index specification.

    Args:
        instances: List of instance groups (each instance is list of resources)
        instance_filter: Filter specification (e.g., "0,2,5" or "0-3")
            None means include all instances

    Returns:
        Filtered list of instances

    Examples:
        instance_filter="0,2" → Include instances at index 0 and 2
        instance_filter="0-3" → Include instances at indices 0, 1, 2, 3
        instance_filter=None → Include all instances
    """
    if not instance_filter:
        return instances

    # Parse filter specification
    indices: Set[int] = set()

    for part in instance_filter.split(","):
        part = part.strip()
        if "-" in part:
            # Range specification (e.g., "0-3")
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            indices.update(range(start, end + 1))
        else:
            # Single index (e.g., "2")
            indices.add(int(part))

    # Filter instances by parsed indices
    filtered = [inst for i, inst in enumerate(instances) if i in indices]

    logger.info(
        f"Filtered instances: {len(filtered)}/{len(instances)} "
        f"(filter: {instance_filter})"
    )

    return filtered


def _filter_patterns(
    selected_instances: List[Tuple[str, List[List[Dict[str, Any]]]]],
    pattern_filter: Optional[List[str]],
    instance_filter: Optional[str],
) -> List[Tuple[str, List[List[Dict[str, Any]]]]]:
    """Apply pattern and instance filtering to replication plan.

    Args:
        selected_instances: Full replication plan instance list
        pattern_filter: Pattern names to include (None = all patterns)
        instance_filter: Instance index filter (None = all instances)

    Returns:
        Filtered selected_instances structure
    """
    filtered_result: List[Tuple[str, List[List[Dict[str, Any]]]]] = []

    for pattern_name, instances in selected_instances:
        # Apply pattern filter
        if pattern_filter and pattern_name not in pattern_filter:
            continue

        # Apply instance filter
        filtered_instances = _filter_instances(instances, instance_filter)

        if filtered_instances:
            filtered_result.append((pattern_name, filtered_instances))

    logger.info(
        f"Pattern filtering: {len(filtered_result)}/{len(selected_instances)} "
        f"patterns included"
    )

    return filtered_result


async def _query_relationships(
    neo4j_session: AsyncSession,
    resource_ids: Set[str],
    include_relationship_types: List[str],
) -> List[Dict[str, Any]]:
    """Query Neo4j for instance-level relationships between selected resources.

    Args:
        neo4j_session: Active Neo4j async session
        resource_ids: Set of resource IDs to query relationships for
        include_relationship_types: Relationship types to include

    Returns:
        List of relationship dicts: [{source: id, target: id, type: rel_type}, ...]

    Note:
        Only queries relationships where BOTH source and target are in resource_ids.
        This ensures we only get relationships between selected resources.
    """
    if not resource_ids:
        logger.warning("No resource IDs provided for relationship query")
        return []

    relationship_query = """
    MATCH (source:Resource:Original)-[rel]->(target:Resource:Original)
    WHERE source.id IN $resource_ids
      AND target.id IN $resource_ids
      AND type(rel) IN $rel_types
    RETURN source.id AS source,
           target.id AS target,
           type(rel) AS type
    """

    try:
        result = await neo4j_session.run(
            relationship_query,
            resource_ids=list(resource_ids),
            rel_types=include_relationship_types,
        )

        relationships: List[Dict[str, Any]] = []
        async for record in result:
            relationships.append(
                {
                    "source": record["source"],
                    "target": record["target"],
                    "type": record["type"],
                }
            )

        logger.info(
            f"Queried {len(relationships)} relationships for "
            f"{len(resource_ids)} resources"
        )

        return relationships

    except Exception as e:
        logger.error(f"Relationship query failed: {e}")
        raise


async def replication_plan_to_tenant_graph(
    replication_plan: ReplicationPlan,
    neo4j_session: AsyncSession,
    pattern_filter: Optional[List[str]] = None,
    instance_filter: Optional[str] = None,
    include_relationship_types: Optional[List[str]] = None,
) -> TenantGraph:
    """Convert replication plan output to TenantGraph for IaC generation.

    This is the main conversion function that bridges pattern-based resource
    selection (from architecture_based_replicator) and deployment infrastructure
    (IaC emitters).

    Args:
        replication_plan: Output from architecture_based_replicator.generate_replication_plan()
            Tuple of (selected_instances, spectral_history, distribution_metadata)
        neo4j_session: Active Neo4j session for querying relationships
        pattern_filter: Optional list of pattern names to include (filters out others)
        instance_filter: Optional instance index filter (e.g., "0,2,5" or "0-3")
        include_relationship_types: Relationship types to include (default: CONTAINS,
            DEPENDS_ON, DIAGNOSTIC_TARGET, MONITORS, TAG_RELATIONSHIP)

    Returns:
        TenantGraph with resources and instance-level relationships

    Algorithm:
        1. Apply pattern and instance filtering
        2. Flatten nested structure to extract all resource dicts
        3. Collect all resource IDs
        4. Query Neo4j for relationships between selected resources
        5. Construct TenantGraph(resources=flat_list, relationships=queried_rels)

    Example:
        >>> plan = generate_replication_plan(...)
        >>> async with driver.session() as session:
        ...     graph = await replication_plan_to_tenant_graph(
        ...         plan, session, pattern_filter=["Web Application"]
        ...     )
        >>> # graph.resources = [{id: "/subscriptions/.../vm1", ...}, ...]
        >>> # graph.relationships = [{source: "vm1", target: "nic1", type: "CONTAINS"}]

    Edge Cases:
        - Empty replication plan → TenantGraph(resources=[], relationships=[])
        - No relationships found → TenantGraph(resources=..., relationships=[])
        - Pattern filter excludes all → TenantGraph(resources=[], relationships=[])
    """
    selected_instances, spectral_history, metadata = replication_plan

    # Set default relationship types if not specified
    if include_relationship_types is None:
        include_relationship_types = DEFAULT_RELATIONSHIP_TYPES

    # Step 1: Apply filtering
    filtered_instances = _filter_patterns(
        selected_instances, pattern_filter, instance_filter
    )

    # Handle empty result after filtering
    if not filtered_instances:
        logger.warning(
            f"No instances selected after filtering. "
            f"Pattern filter: {pattern_filter}, Instance filter: {instance_filter}"
        )
        return TenantGraph(resources=[], relationships=[])

    # Step 2: Flatten resources and collect IDs
    flat_resources, resource_ids = _flatten_resources(
        filtered_instances, pattern_filter=None  # Filtering already applied
    )

    # Handle no resources case
    if not resource_ids:
        logger.warning("No resources found in replication plan")
        return TenantGraph(resources=[], relationships=[])

    # Step 3: Query relationships between selected resources
    relationships = await _query_relationships(
        neo4j_session, resource_ids, include_relationship_types
    )

    # Step 4: Construct and return TenantGraph
    tenant_graph = TenantGraph(resources=flat_resources, relationships=relationships)

    logger.info(
        f"Converted replication plan to TenantGraph: "
        f"{len(flat_resources)} resources, {len(relationships)} relationships"
    )

    return tenant_graph
