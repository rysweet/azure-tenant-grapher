"""
Performance Monitoring and Optimization Utilities for Scale Operations

This module provides performance profiling, metrics collection, and optimization
utilities for large-scale graph operations (40k+ resources).

Key Features:
- Performance metrics collection (time, memory, throughput)
- Adaptive batch sizing based on graph size
- Query optimization utilities
- Memory profiling and monitoring
- Performance benchmarking

Architecture:
- PerformanceMetrics: Dataclass for storing performance data
- PerformanceMonitor: Context manager for operation timing
- AdaptiveBatchSizer: Dynamic batch size calculation
- QueryOptimizer: Neo4j query optimization utilities
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """
    Performance metrics for scale operations.

    Tracks timing, throughput, memory usage, and operation-specific metrics
    for analyzing and optimizing large-scale graph operations.

    Attributes:
        operation_name: Name of the operation being measured
        start_time: Operation start timestamp
        end_time: Operation end timestamp
        duration_seconds: Total operation duration
        items_processed: Number of items processed
        throughput_per_second: Items processed per second
        memory_mb_start: Memory usage at start (MB)
        memory_mb_end: Memory usage at end (MB)
        memory_mb_peak: Peak memory usage during operation (MB)
        batch_count: Number of batches processed
        batch_size: Size of batches used
        neo4j_query_count: Number of Neo4j queries executed
        neo4j_query_time_seconds: Total time spent in Neo4j queries
        error_count: Number of errors encountered
        metadata: Additional operation-specific metrics
    """

    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    items_processed: int = 0
    throughput_per_second: float = 0.0
    memory_mb_start: float = 0.0
    memory_mb_end: float = 0.0
    memory_mb_peak: float = 0.0
    batch_count: int = 0
    batch_size: int = 0
    neo4j_query_count: int = 0
    neo4j_query_time_seconds: float = 0.0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finalize(self) -> None:
        """Calculate final metrics after operation completes."""
        if self.end_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
            if self.duration_seconds > 0:
                self.throughput_per_second = self.items_processed / self.duration_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format."""
        return {
            "operation_name": self.operation_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "items_processed": self.items_processed,
            "throughput_per_second": round(self.throughput_per_second, 2),
            "memory_mb_start": round(self.memory_mb_start, 2),
            "memory_mb_end": round(self.memory_mb_end, 2),
            "memory_mb_peak": round(self.memory_mb_peak, 2),
            "memory_delta_mb": round(self.memory_mb_end - self.memory_mb_start, 2),
            "batch_count": self.batch_count,
            "batch_size": self.batch_size,
            "neo4j_query_count": self.neo4j_query_count,
            "neo4j_query_time_seconds": round(self.neo4j_query_time_seconds, 2),
            "neo4j_query_overhead_percent": (
                round((self.neo4j_query_time_seconds / self.duration_seconds) * 100, 1)
                if self.duration_seconds > 0
                else 0
            ),
            "error_count": self.error_count,
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"""Performance Metrics - {self.operation_name}:
  Duration: {self.duration_seconds:.2f}s
  Items Processed: {self.items_processed:,}
  Throughput: {self.throughput_per_second:.2f} items/sec
  Memory: {self.memory_mb_start:.1f} MB → {self.memory_mb_end:.1f} MB (peak: {self.memory_mb_peak:.1f} MB)
  Batches: {self.batch_count} batches of {self.batch_size} items
  Neo4j Queries: {self.neo4j_query_count} queries, {self.neo4j_query_time_seconds:.2f}s total
  Errors: {self.error_count}"""


class PerformanceMonitor:
    """
    Context manager for monitoring operation performance.

    Automatically tracks timing, memory usage, and provides utilities
    for recording operation-specific metrics.

    Example:
        >>> monitor = PerformanceMonitor("scale_up_template")
        >>> with monitor:
        ...     # Perform operations
        ...     monitor.record_items(1000)
        ...     monitor.record_batch()
        >>> metrics = monitor.get_metrics()
        >>> print(metrics)
    """

    def __init__(self, operation_name: str):
        """
        Initialize performance monitor.

        Args:
            operation_name: Name of operation being monitored
        """
        self.operation_name = operation_name
        self.metrics = PerformanceMetrics(
            operation_name=operation_name, start_time=datetime.now()
        )
        self._process = psutil.Process()
        self._query_start_time: Optional[float] = None

    def __enter__(self) -> "PerformanceMonitor":
        """Start monitoring."""
        self.metrics.memory_mb_start = self._get_memory_mb()
        self.metrics.memory_mb_peak = self.metrics.memory_mb_start
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop monitoring and finalize metrics."""
        self.metrics.end_time = datetime.now()
        self.metrics.memory_mb_end = self._get_memory_mb()
        self.metrics.finalize()

        if exc_type:
            self.metrics.error_count += 1

    def _get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            return self._process.memory_info().rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def update_peak_memory(self) -> None:
        """Update peak memory if current usage is higher."""
        current_mb = self._get_memory_mb()
        if current_mb > self.metrics.memory_mb_peak:
            self.metrics.memory_mb_peak = current_mb

    def record_items(self, count: int) -> None:
        """
        Record items processed.

        Args:
            count: Number of items processed
        """
        self.metrics.items_processed += count
        self.update_peak_memory()

    def record_batch(self, batch_size: int = 0) -> None:
        """
        Record batch processed.

        Args:
            batch_size: Size of batch (optional)
        """
        self.metrics.batch_count += 1
        if batch_size > 0:
            self.metrics.batch_size = batch_size
        self.update_peak_memory()

    @contextmanager
    def measure_query(self) -> Generator[None, None, None]:
        """
        Context manager for measuring Neo4j query time.

        Example:
            >>> with monitor.measure_query():
            ...     result = session.run(query)
        """
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            self.metrics.neo4j_query_count += 1
            self.metrics.neo4j_query_time_seconds += elapsed

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to metrics.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metrics.metadata[key] = value

    def get_metrics(self) -> PerformanceMetrics:
        """Get current metrics snapshot."""
        return self.metrics


class AdaptiveBatchSizer:
    """
    Adaptive batch size calculator for optimal performance.

    Dynamically adjusts batch sizes based on:
    - Total graph size
    - Available memory
    - Operation type (read vs write)
    - Historical performance data

    Design Philosophy:
    - Small graphs (< 1k): Small batches (100-500) for responsiveness
    - Medium graphs (1k-10k): Medium batches (500-1000)
    - Large graphs (10k-100k): Large batches (1000-5000)
    - Very large graphs (> 100k): Very large batches (5000-10000)
    """

    # Batch size tiers based on graph size
    BATCH_TIERS = [
        (1000, 100, 500),  # < 1k nodes: 100-500 batch
        (10000, 500, 1000),  # 1k-10k nodes: 500-1000 batch
        (100000, 1000, 5000),  # 10k-100k nodes: 1000-5000 batch
        (float("inf"), 5000, 10000),  # > 100k nodes: 5000-10000 batch
    ]

    @classmethod
    def calculate_batch_size(
        cls,
        total_items: int,
        operation_type: str = "read",
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> int:
        """
        Calculate optimal batch size for operation.

        Args:
            total_items: Total number of items to process
            operation_type: "read" or "write" (writes use smaller batches)
            min_size: Minimum batch size override
            max_size: Maximum batch size override

        Returns:
            Optimal batch size

        Example:
            >>> size = AdaptiveBatchSizer.calculate_batch_size(50000, "write")
            >>> print(f"Batch size for 50k items: {size}")
            Batch size for 50k items: 2000
        """
        # Find appropriate tier
        for threshold, tier_min, tier_max in cls.BATCH_TIERS:
            if total_items <= threshold:
                # Use tier defaults
                base_min = tier_min
                base_max = tier_max
                break
        else:
            # Fallback (shouldn't reach here due to inf threshold)
            base_min = 5000
            base_max = 10000

        # Apply overrides
        if min_size is not None:
            base_min = max(min_size, base_min)
        if max_size is not None:
            base_max = min(max_size, base_max)

        # Scale within tier based on total items
        if total_items < base_min:
            batch_size = total_items
        else:
            # Linear interpolation within tier
            progress = min(1.0, total_items / threshold)
            batch_size = int(base_min + (base_max - base_min) * progress)

        # Write operations use smaller batches (better transaction control)
        if operation_type == "write":
            batch_size = int(batch_size * 0.5)

        # Ensure reasonable bounds
        batch_size = max(100, min(batch_size, 10000))

        logger.debug(
            f"Calculated batch size {batch_size} for {total_items} items "
            f"(type={operation_type})"
        )

        return batch_size

    @classmethod
    def calculate_optimal_batching(
        cls, total_items: int, operation_type: str = "read"
    ) -> Tuple[int, int]:
        """
        Calculate both batch size and number of batches.

        Args:
            total_items: Total number of items to process
            operation_type: "read" or "write"

        Returns:
            Tuple of (batch_size, num_batches)

        Example:
            >>> batch_size, num_batches = AdaptiveBatchSizer.calculate_optimal_batching(40000)
            >>> print(f"Process {num_batches} batches of {batch_size} items")
        """
        batch_size = cls.calculate_batch_size(total_items, operation_type)
        num_batches = (total_items + batch_size - 1) // batch_size
        return batch_size, num_batches


class QueryOptimizer:
    """
    Neo4j query optimization utilities.

    Provides query hints, index recommendations, and query transformation
    utilities for optimal performance with large graphs.
    """

    @staticmethod
    def ensure_indexes(session, logger_instance: Optional[logging.Logger] = None) -> List[str]:
        """
        Ensure critical indexes exist for scale operations.

        Creates indexes on:
        - Resource.id (abstracted layer)
        - Resource.synthetic (for synthetic resource queries)
        - Resource.scale_operation_id (for operation-specific queries)
        - Resource.template_source_id (for template replication)

        Args:
            session: Neo4j session
            logger_instance: Optional logger for output

        Returns:
            List of indexes created/verified

        Example:
            >>> with session_manager.session() as session:
            ...     indexes = QueryOptimizer.ensure_indexes(session)
            ...     print(f"Created {len(indexes)} indexes")
        """
        log = logger_instance or logger
        indexes_created = []

        # Index definitions with proper IF NOT EXISTS syntax
        index_definitions = [
            # Resource ID index (most critical)
            (
                "CREATE INDEX resource_id_idx IF NOT EXISTS "
                "FOR (r:Resource) ON (r.id)"
            ),
            # Synthetic flag index (for filtering synthetic resources)
            (
                "CREATE INDEX resource_synthetic_idx IF NOT EXISTS "
                "FOR (r:Resource) ON (r.synthetic)"
            ),
            # Scale operation ID index (for operation-specific queries)
            (
                "CREATE INDEX resource_scale_op_idx IF NOT EXISTS "
                "FOR (r:Resource) ON (r.scale_operation_id)"
            ),
            # Template source ID index (for template replication mapping)
            (
                "CREATE INDEX resource_template_source_idx IF NOT EXISTS "
                "FOR (r:Resource) ON (r.template_source_id)"
            ),
            # Composite index for synthetic + operation queries
            (
                "CREATE INDEX resource_synthetic_op_idx IF NOT EXISTS "
                "FOR (r:Resource) ON (r.synthetic, r.scale_operation_id)"
            ),
            # Tenant ID index (for tenant-specific queries)
            (
                "CREATE INDEX resource_tenant_idx IF NOT EXISTS "
                "FOR (r:Resource) ON (r.tenant_id)"
            ),
        ]

        for index_query in index_definitions:
            try:
                session.run(index_query)
                index_name = index_query.split("INDEX")[1].split("IF NOT")[0].strip()
                indexes_created.append(index_name)
                log.debug(f"Ensured index: {index_name}")
            except Exception as e:
                log.warning(f"Failed to create index: {e}")

        log.info(f"Ensured {len(indexes_created)} indexes for scale operations")
        return indexes_created

    @staticmethod
    def get_unwind_batch_query(
        node_label: str = "Resource", batch_param: str = "batch"
    ) -> str:
        """
        Generate optimized UNWIND query for batch insertion.

        UNWIND is the most efficient way to insert batches in Neo4j.

        Args:
            node_label: Node label to create
            batch_param: Parameter name for batch data

        Returns:
            Optimized UNWIND query

        Example:
            >>> query = QueryOptimizer.get_unwind_batch_query()
            >>> session.run(query, {"batch": resource_list})
        """
        return f"""
        UNWIND ${batch_param} as item
        CREATE (n:{node_label})
        SET n = item.props
        """

    @staticmethod
    def get_batch_match_query(
        node_label: str = "Resource", id_field: str = "id", batch_param: str = "ids"
    ) -> str:
        """
        Generate optimized batch MATCH query.

        Uses parameterized IN clause for efficient batch lookups.

        Args:
            node_label: Node label to match
            id_field: ID field name
            batch_param: Parameter name for ID list

        Returns:
            Optimized batch MATCH query

        Example:
            >>> query = QueryOptimizer.get_batch_match_query()
            >>> result = session.run(query, {"ids": ["id1", "id2", "id3"]})
        """
        return f"""
        MATCH (n:{node_label})
        WHERE n.{id_field} IN ${batch_param}
        RETURN n
        """

    @staticmethod
    def add_query_hints(query: str, hints: List[str]) -> str:
        """
        Add query hints for Neo4j query planner.

        Args:
            query: Base Cypher query
            hints: List of hints to add (e.g., ["USING INDEX", "USING SCAN"])

        Returns:
            Query with hints

        Example:
            >>> query = "MATCH (r:Resource) WHERE r.id = $id RETURN r"
            >>> optimized = QueryOptimizer.add_query_hints(
            ...     query,
            ...     ["USING INDEX r:Resource(id)"]
            ... )
        """
        # Insert hints after WHERE clause
        if "WHERE" in query:
            parts = query.split("WHERE", 1)
            hint_str = " ".join(hints)
            return f"{parts[0]}WHERE {hint_str} {parts[1]}"
        return query


# Convenience function for quick performance monitoring
def monitor_performance(operation_name: str) -> PerformanceMonitor:
    """
    Create a performance monitor for an operation.

    Args:
        operation_name: Name of operation to monitor

    Returns:
        PerformanceMonitor context manager

    Example:
        >>> with monitor_performance("scale_up_template") as monitor:
        ...     # Perform operations
        ...     monitor.record_items(1000)
        >>> print(monitor.get_metrics())
    """
    return PerformanceMonitor(operation_name)
