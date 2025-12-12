"""
Common utilities for scale-up operations.

This module provides shared functionality used across all scale-up strategies:
- Batch insertion operations for resources and relationships
- Parallel processing with controlled concurrency
- Adaptive batch sizing for performance optimization
- Index management for query optimization

Philosophy:
- Single responsibility: Each function does one thing well
- Standard library + Neo4j driver only
- Self-contained and regeneratable
- Zero-BS: Every function works, no stubs

Public API:
    insert_resource_batch: Insert batch of resources
    insert_relationship_batch: Insert batch of relationships
    insert_batches_parallel: Parallel batch insertion with concurrency control
    insert_relationship_batches_parallel: Parallel relationship batch insertion
    get_adaptive_batch_size: Calculate optimal batch size
    ensure_indexes: Create critical Neo4j indexes
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from src.services.scale_performance import (
    AdaptiveBatchSizer,
    PerformanceMonitor,
    QueryOptimizer,
)
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


def ensure_indexes(session_manager: Neo4jSessionManager) -> None:
    """
    Ensure critical Neo4j indexes exist for optimal performance.

    Creates indexes on:
    - Resource.scale_operation_id
    - Resource.synthetic
    - Resource.id

    Args:
        session_manager: Neo4j session manager

    Note:
        Does not fail if index creation fails (warns only).
    """
    try:
        with session_manager.session() as session:
            QueryOptimizer.ensure_indexes(session, logger)
    except Exception as e:
        logger.warning(f"Failed to ensure indexes: {e}")


def get_adaptive_batch_size(
    total_items: int, operation_type: str, base_batch_size: int, enable_adaptive: bool
) -> int:
    """
    Calculate optimal batch size using adaptive sizing if enabled.

    Args:
        total_items: Total number of items to process
        operation_type: "read" or "write"
        base_batch_size: Base batch size to use
        enable_adaptive: Whether to use adaptive batching

    Returns:
        Optimal batch size

    Example:
        >>> size = get_adaptive_batch_size(50000, "write", 500, True)
        >>> print(size)  # May be 1000 or 2000 based on total_items
    """
    if enable_adaptive and total_items > 1000:
        return AdaptiveBatchSizer.calculate_batch_size(
            total_items, operation_type, min_size=100, max_size=base_batch_size * 2
        )
    return base_batch_size


async def insert_resource_batch(
    session_manager: Neo4jSessionManager, resources: List[Dict[str, Any]]
) -> None:
    """
    Insert a batch of resources into Neo4j.

    Args:
        session_manager: Neo4j session manager
        resources: List of resource dicts with id, type, props

    Example:
        >>> resources = [
        ...     {"id": "res1", "type": "Microsoft.Compute/vm", "props": {...}},
        ...     {"id": "res2", "type": "Microsoft.Network/vnet", "props": {...}}
        ... ]
        >>> await insert_resource_batch(session_manager, resources)
    """
    query = """
    UNWIND $resources as res
    CREATE (r:Resource)
    SET r = res.props
    """

    with session_manager.session() as session:
        session.run(query, {"resources": resources})


async def insert_relationship_batch(
    session_manager: Neo4jSessionManager, relationships: List[Dict[str, Any]]
) -> None:
    """
    Insert a batch of relationships into Neo4j.

    Groups relationships by type for efficiency, then creates them
    using dynamic relationship type queries.

    Args:
        session_manager: Neo4j session manager
        relationships: List of relationship dicts with source_id, target_id, rel_type, rel_props

    Example:
        >>> relationships = [
        ...     {
        ...         "source_id": "res1",
        ...         "target_id": "res2",
        ...         "rel_type": "CONNECTED_TO",
        ...         "rel_props": {"connection_type": "peering"}
        ...     }
        ... ]
        >>> await insert_relationship_batch(session_manager, relationships)
    """
    # Group by relationship type for efficiency
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rel in relationships:
        by_type[rel["rel_type"]].append(rel)

    with session_manager.session() as session:
        for rel_type, rels in by_type.items():
            # Use dynamic relationship type
            query = f"""
            UNWIND $rels as rel
            MATCH (source:Resource {{id: rel.source_id}})
            MATCH (target:Resource {{id: rel.target_id}})
            CREATE (source)-[r:{rel_type}]->(target)
            SET r = rel.rel_props
            """
            session.run(query, {"rels": rels})


async def insert_batches_parallel(
    session_manager: Neo4jSessionManager,
    batches: List[List[Dict[str, Any]]],
    target_count: int,
    progress_callback: Optional[Callable[[str, int, int], None]],
    progress_start: int,
    progress_end: int,
    monitor: Optional[PerformanceMonitor] = None,
) -> int:
    """
    Insert resource batches in parallel with controlled concurrency.

    Uses asyncio.gather with semaphore to limit concurrent database operations.
    Prevents overwhelming Neo4j with too many simultaneous connections.

    Args:
        session_manager: Neo4j session manager
        batches: List of resource batches
        target_count: Total target count (for progress reporting)
        progress_callback: Optional progress callback
        progress_start: Progress start percentage
        progress_end: Progress end percentage
        monitor: Optional performance monitor

    Returns:
        Total number of resources created

    Example:
        >>> batches = [[{"id": "r1", ...}], [{"id": "r2", ...}]]
        >>> count = await insert_batches_parallel(
        ...     session_manager, batches, 2, None, 0, 100
        ... )
        >>> print(count)  # 2
    """
    # Limit concurrent batch inserts to avoid overwhelming Neo4j
    max_concurrent_batches = min(5, len(batches) // 10)
    semaphore = asyncio.Semaphore(max_concurrent_batches)
    created_count = 0
    completed_batches = 0

    async def insert_with_semaphore(batch: List[Dict[str, Any]]) -> int:
        """Insert batch with semaphore control."""
        nonlocal created_count, completed_batches

        async with semaphore:
            await insert_resource_batch(session_manager, batch)
            count = len(batch)

            # Thread-safe counter update
            created_count += count
            completed_batches += 1

            if monitor:
                monitor.record_items(count)
                monitor.record_batch(count)

            # Update progress
            if progress_callback:
                progress = progress_start + int(
                    (completed_batches / len(batches)) * (progress_end - progress_start)
                )
                progress_callback(
                    f"Created {created_count}/{target_count} resources...",
                    progress,
                    100,
                )

            return count

    # Execute all batch inserts with limited concurrency
    logger.info(
        f"Inserting {len(batches)} batches in parallel "
        f"(max_concurrent={max_concurrent_batches})"
    )

    await asyncio.gather(*[insert_with_semaphore(batch) for batch in batches])

    return created_count


async def insert_relationship_batches_parallel(
    session_manager: Neo4jSessionManager,
    batches: List[List[Dict[str, Any]]],
    progress_callback: Optional[Callable[[str, int, int], None]],
    progress_start: int,
    progress_end: int,
    monitor: Optional[PerformanceMonitor] = None,
) -> int:
    """
    Insert relationship batches in parallel with controlled concurrency.

    Args:
        session_manager: Neo4j session manager
        batches: List of relationship batches
        progress_callback: Optional progress callback
        progress_start: Progress start percentage
        progress_end: Progress end percentage
        monitor: Optional performance monitor

    Returns:
        Total number of relationships created

    Example:
        >>> batches = [[{"source_id": "r1", "target_id": "r2", ...}]]
        >>> count = await insert_relationship_batches_parallel(
        ...     session_manager, batches, None, 0, 100
        ... )
    """
    # Limit concurrent batch inserts
    max_concurrent_batches = min(5, len(batches) // 10)
    semaphore = asyncio.Semaphore(max_concurrent_batches)
    created_count = 0
    completed_batches = 0

    async def insert_with_semaphore(batch: List[Dict[str, Any]]) -> int:
        """Insert batch with semaphore control."""
        nonlocal created_count, completed_batches

        async with semaphore:
            await insert_relationship_batch(session_manager, batch)
            count = len(batch)

            created_count += count
            completed_batches += 1

            if monitor:
                monitor.record_items(count)
                monitor.record_batch(count)

            if progress_callback:
                progress = progress_start + int(
                    (completed_batches / len(batches)) * (progress_end - progress_start)
                )
                progress_callback(
                    f"Created {created_count} relationships...", progress, 100
                )

            return count

    logger.info(
        f"Inserting {len(batches)} relationship batches in parallel "
        f"(max_concurrent={max_concurrent_batches})"
    )

    await asyncio.gather(*[insert_with_semaphore(batch) for batch in batches])

    return created_count


__all__ = [
    "ensure_indexes",
    "get_adaptive_batch_size",
    "insert_batches_parallel",
    "insert_relationship_batch",
    "insert_relationship_batches_parallel",
    "insert_resource_batch",
]
