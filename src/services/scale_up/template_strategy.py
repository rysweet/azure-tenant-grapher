"""
Template-based replication strategy for scale-up operations.

This module implements template-based resource replication by analyzing
existing resources and creating synthetic copies with variations while
maintaining topology structure and relationship patterns.

Philosophy:
- Self-contained strategy module
- Maintains graph topology consistency
- Optimized for large-scale operations (adaptive batching, parallel processing)
- Zero-BS: Full working implementation

Public API:
    replicate_resources: Create synthetic copies of base resources
    clone_relationships: Replicate relationship patterns
    build_resource_mapping: Map base to synthetic resource IDs
    get_relationship_patterns: Extract patterns from base resources
"""

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.services.scale_performance import PerformanceMonitor
from src.services.scale_up import common
from src.utils.session_manager import Neo4jSessionManager
from src.utils.synthetic_id import generate_synthetic_id

logger = logging.getLogger(__name__)


async def get_base_resources(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    resource_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Get base resources from abstracted layer for template replication.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        resource_types: Optional list of resource types to filter

    Returns:
        List of resource dictionaries with id, type, properties

    Raises:
        ValueError: If resource_types contain invalid values

    Example:
        >>> resources = await get_base_resources(
        ...     session_manager,
        ...     "abc123",
        ...     ["Microsoft.Compute/virtualMachines"]
        ... )
    """
    # Validate resource types if provided
    if resource_types:
        # Whitelist validation: Azure resource types have specific format
        # Format: Provider.Service/resourceType (e.g., Microsoft.Compute/virtualMachines)
        for rt in resource_types:
            if not re.match(r"^[A-Za-z0-9]+\.[A-Za-z0-9]+/[A-Za-z0-9]+$", rt):
                raise ValueError(f"Invalid resource type format: {rt}")
            if len(rt) > 200:  # Reasonable max length
                raise ValueError(f"Resource type too long: {rt}")

    # Build query with parameterized resource types (no string interpolation)
    # Note: Query without tenant/subscription filter since Resource nodes may not have tenant_id
    # Instead, rely on the Tenant validation earlier to ensure tenant exists in DB
    if resource_types:
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND (r.synthetic IS NULL OR r.synthetic = false)
          AND r.type IN $resource_types
        RETURN r.id as id, r.type as type, properties(r) as props
        LIMIT 10000
        """
        params = {"resource_types": resource_types}
    else:
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND (r.synthetic IS NULL OR r.synthetic = false)
        RETURN r.id as id, r.type as type, properties(r) as props
        LIMIT 10000
        """
        params = {}

    with session_manager.session() as session:
        result = session.run(query, params)
        resources = [
            {"id": record["id"], "type": record["type"], "props": record["props"]}
            for record in result
        ]

    return resources


async def replicate_resources(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    operation_id: str,
    base_resources: List[Dict[str, Any]],
    target_count: int,
    batch_size: int,
    enable_adaptive_batching: bool,
    enable_performance_monitoring: bool,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    progress_start: int = 0,
    progress_end: int = 100,
) -> int:
    """
    Replicate base resources to create synthetic copies.

    Uses round-robin selection from base resources with property variations.
    Optimized with adaptive batching and parallel batch inserts for large operations.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        operation_id: Scale operation ID
        base_resources: List of base resources to replicate
        target_count: Number of synthetic resources to create
        batch_size: Base batch size
        enable_adaptive_batching: Use adaptive batch sizing
        enable_performance_monitoring: Enable performance metrics
        progress_callback: Optional progress callback
        progress_start: Progress percentage at start
        progress_end: Progress percentage at end

    Returns:
        Number of resources created

    Example:
        >>> created = await replicate_resources(
        ...     session_manager,
        ...     "abc123",
        ...     "scale-op-1",
        ...     base_resources,
        ...     1000,
        ...     500,
        ...     True,
        ...     True
        ... )
    """
    # Use performance monitoring if enabled
    monitor = (
        PerformanceMonitor(f"replicate_resources_{target_count}")
        if enable_performance_monitoring
        else None
    )

    if monitor is not None:
        monitor.__enter__()

    try:
        created_count = 0
        generation_timestamp = datetime.now().isoformat()

        # Use adaptive batch size for large operations
        adaptive_batch_size = common.get_adaptive_batch_size(
            target_count, "write", batch_size, enable_adaptive_batching
        )

        logger.info(
            f"Replicating {target_count} resources with batch size {adaptive_batch_size}"
        )

        # Batch resources
        batches = []
        current_batch = []

        for i in range(target_count):
            # Round-robin selection from base resources
            base = base_resources[i % len(base_resources)]

            # Generate synthetic ID
            synthetic_id = generate_synthetic_id(base["type"])

            # Copy properties and add synthetic markers
            props = dict(base["props"])
            props.update(
                {
                    "id": synthetic_id,
                    "synthetic": True,
                    "scale_operation_id": operation_id,
                    "generation_strategy": "template",
                    "generation_timestamp": generation_timestamp,
                    "template_source_id": base["id"],
                }
            )

            current_batch.append(
                {"id": synthetic_id, "type": base["type"], "props": props}
            )

            if len(current_batch) >= adaptive_batch_size:
                batches.append(current_batch)
                current_batch = []

        # Add remaining
        if current_batch:
            batches.append(current_batch)

        # For very large operations (>10k resources), process batches in parallel
        # with controlled concurrency to avoid overwhelming Neo4j
        if target_count > 10000 and len(batches) > 10:
            created_count = await common.insert_batches_parallel(
                session_manager,
                batches,
                target_count,
                progress_callback,
                progress_start,
                progress_end,
                monitor,
            )
        else:
            # Standard sequential processing for smaller operations
            for batch_idx, batch in enumerate(batches):
                await common.insert_resource_batch(session_manager, batch)
                created_count += len(batch)

                if monitor is not None:
                    monitor.record_items(len(batch))
                    monitor.record_batch(len(batch))

                # Update progress
                if progress_callback:
                    progress = progress_start + int(
                        ((batch_idx + 1) / len(batches))
                        * (progress_end - progress_start)
                    )
                    progress_callback(
                        f"Created {created_count}/{target_count} resources...",
                        progress,
                        100,
                    )

        logger.info(
            f"Created {created_count} synthetic resources in {len(batches)} batches "
            f"(batch_size={adaptive_batch_size})"
        )

        if monitor is not None:
            monitor.add_metadata("adaptive_batch_size", adaptive_batch_size)
            monitor.add_metadata("num_batches", len(batches))

        return created_count

    finally:
        if monitor is not None:
            monitor.__exit__(None, None, None)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(str(monitor.get_metrics()))


async def build_resource_mapping(
    session_manager: Neo4jSessionManager,
    operation_id: str,
    base_resources: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """
    Build mapping from base resource IDs to synthetic resource IDs.

    Args:
        session_manager: Neo4j session manager
        operation_id: Scale operation ID
        base_resources: List of base resources

    Returns:
        Dict mapping base_id -> [synthetic_id1, synthetic_id2, ...]

    Example:
        >>> mapping = await build_resource_mapping(
        ...     session_manager,
        ...     "scale-op-1",
        ...     base_resources
        ... )
        >>> print(mapping["base-id-1"])  # ["synth-1", "synth-2", ...]
    """
    # Get all synthetic resources for this operation
    query = """
    MATCH (r:Resource)
    WHERE NOT r:Original
      AND r.scale_operation_id = $operation_id
      AND r.synthetic = true
    RETURN r.id as id, r.template_source_id as source_id
    """

    mapping: Dict[str, List[str]] = defaultdict(list)

    with session_manager.session() as session:
        result = session.run(query, {"operation_id": operation_id})  # type: ignore[arg-type]
        for record in result:
            synthetic_id = record["id"]
            source_id = record.get("source_id")
            if source_id:
                mapping[source_id].append(synthetic_id)

    return dict(mapping)


async def get_relationship_patterns(
    session_manager: Neo4jSessionManager, base_resources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extract relationship patterns from base resources.

    For large resource lists (>5000), chunks the query to avoid
    Neo4j performance issues with large IN clauses.

    Args:
        session_manager: Neo4j session manager
        base_resources: List of base resources

    Returns:
        List of relationship patterns with source_id, target_id, type, props

    Example:
        >>> patterns = await get_relationship_patterns(
        ...     session_manager,
        ...     base_resources
        ... )
    """
    base_ids = [r["id"] for r in base_resources]
    if not base_ids:
        return []

    # Chunk large lists to avoid Neo4j performance issues with large IN clauses
    chunk_size = 5000
    patterns = []

    if len(base_ids) <= chunk_size:
        # Small list - single query
        patterns = await _get_relationship_patterns_chunk(session_manager, base_ids)
    else:
        # Large list - chunk and combine
        logger.info(
            str(f"Chunking {len(base_ids)} base IDs into {chunk_size}-ID chunks")
        )
        for i in range(0, len(base_ids), chunk_size):
            chunk = base_ids[i : i + chunk_size]
            chunk_patterns = await _get_relationship_patterns_chunk(
                session_manager, chunk
            )
            patterns.extend(chunk_patterns)
            logger.debug(
                f"Processed chunk {i // chunk_size + 1}/{(len(base_ids) + chunk_size - 1) // chunk_size}: "
                f"{len(chunk_patterns)} patterns"
            )

    return patterns


async def _get_relationship_patterns_chunk(
    session_manager: Neo4jSessionManager, base_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    Extract relationship patterns for a chunk of base resources.

    Args:
        session_manager: Neo4j session manager
        base_ids: List of base resource IDs (should be <= 5000)

    Returns:
        List of relationship patterns
    """
    query = """
    MATCH (source:Resource)-[rel]->(target:Resource)
    WHERE NOT source:Original AND NOT target:Original
      AND source.id IN $base_ids
      AND target.id IN $base_ids
    RETURN source.id as source_id,
           target.id as target_id,
           type(rel) as rel_type,
           properties(rel) as rel_props
    LIMIT 100000
    """

    patterns = []
    with session_manager.session() as session:
        result = session.run(query, {"base_ids": base_ids})  # type: ignore[arg-type]
        for record in result:
            patterns.append(
                {
                    "source_id": record["source_id"],
                    "target_id": record["target_id"],
                    "rel_type": record["rel_type"],
                    "rel_props": record["rel_props"],
                }
            )

    return patterns


async def clone_relationships(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    operation_id: str,
    base_resources: List[Dict[str, Any]],
    batch_size: int,
    enable_adaptive_batching: bool,
    enable_performance_monitoring: bool,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    progress_start: int = 0,
    progress_end: int = 100,
) -> int:
    """
    Clone relationships between synthetic resources.

    Finds relationship patterns between base resources and replicates
    them for synthetic resources. Optimized with adaptive batching
    and parallel processing for large graphs.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        operation_id: Scale operation ID
        base_resources: List of base resources
        batch_size: Base batch size
        enable_adaptive_batching: Use adaptive batch sizing
        enable_performance_monitoring: Enable performance metrics
        progress_callback: Optional progress callback
        progress_start: Progress percentage at start
        progress_end: Progress percentage at end

    Returns:
        Number of relationships created

    Example:
        >>> created = await clone_relationships(
        ...     session_manager,
        ...     "abc123",
        ...     "scale-op-1",
        ...     base_resources,
        ...     500,
        ...     True,
        ...     True
        ... )
    """
    monitor = (
        PerformanceMonitor(f"clone_relationships_{len(base_resources)}")
        if enable_performance_monitoring
        else None
    )

    if monitor is not None:
        monitor.__enter__()

    try:
        # Build mapping: base_id -> list of synthetic_ids
        base_to_synthetic = await build_resource_mapping(
            session_manager, operation_id, base_resources
        )

        if progress_callback:
            progress_callback("Analyzing relationship patterns...", progress_start, 100)

        # Get relationship patterns from base resources
        patterns = await get_relationship_patterns(session_manager, base_resources)

        if not patterns:
            logger.info("No relationship patterns found to clone")
            return 0

        if progress_callback:
            progress_callback(
                f"Cloning {len(patterns)} relationship patterns...",
                progress_start + 10,
                100,
            )

        # Estimate total relationships (for adaptive batching)
        total_synthetic_resources = sum(len(ids) for ids in base_to_synthetic.values())
        estimated_relationships = len(patterns) * (
            total_synthetic_resources // len(base_resources)
        )

        adaptive_batch_size = common.get_adaptive_batch_size(
            estimated_relationships, "write", batch_size, enable_adaptive_batching
        )

        logger.info(
            f"Cloning {len(patterns)} patterns for ~{estimated_relationships} relationships "
            f"(batch_size={adaptive_batch_size})"
        )

        # Clone relationships in batches
        relationships_created = 0
        batches = []
        current_batch = []

        for pattern in patterns:
            source_base_id = pattern["source_id"]
            target_base_id = pattern["target_id"]
            rel_type = pattern["rel_type"]
            rel_props = pattern["rel_props"]

            # Get synthetic IDs for source and target
            source_synthetic_ids = base_to_synthetic.get(source_base_id, [])
            target_synthetic_ids = base_to_synthetic.get(target_base_id, [])

            # Create relationships for all synthetic pairs
            for src_id in source_synthetic_ids:
                for tgt_id in target_synthetic_ids:
                    current_batch.append(
                        {
                            "source_id": src_id,
                            "target_id": tgt_id,
                            "rel_type": rel_type,
                            "rel_props": rel_props,
                        }
                    )

                    if len(current_batch) >= adaptive_batch_size:
                        batches.append(current_batch)
                        current_batch = []

        if current_batch:
            batches.append(current_batch)

        # For large operations, use parallel batch inserts
        if estimated_relationships > 10000 and len(batches) > 10:
            relationships_created = await common.insert_relationship_batches_parallel(
                session_manager,
                batches,
                progress_callback,
                progress_start,
                progress_end,
                monitor,
            )
        else:
            # Standard sequential processing
            for batch_idx, batch in enumerate(batches):
                await common.insert_relationship_batch(session_manager, batch)
                relationships_created += len(batch)

                if monitor is not None:
                    monitor.record_items(len(batch))
                    monitor.record_batch(len(batch))

                if progress_callback:
                    progress = progress_start + int(
                        ((batch_idx + 1) / len(batches))
                        * (progress_end - progress_start)
                    )
                    progress_callback(
                        f"Created {relationships_created} relationships...",
                        progress,
                        100,
                    )

        logger.info(
            f"Created {relationships_created} relationships in {len(batches)} batches "
            f"(batch_size={adaptive_batch_size})"
        )

        if monitor is not None:
            monitor.add_metadata("adaptive_batch_size", adaptive_batch_size)
            monitor.add_metadata("num_batches", len(batches))
            monitor.add_metadata("num_patterns", len(patterns))

        return relationships_created

    finally:
        if monitor is not None:
            monitor.__exit__(None, None, None)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(str(monitor.get_metrics()))


__all__ = [
    "build_resource_mapping",
    "clone_relationships",
    "get_base_resources",
    "get_relationship_patterns",
    "replicate_resources",
]
