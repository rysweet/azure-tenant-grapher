"""
Performance Benchmarks for Scale Operations

This module contains comprehensive performance benchmarks for testing
scale operations with large graphs (up to 40k+ resources).

Benchmarks:
- Small graphs (100-1k resources)
- Medium graphs (1k-10k resources)
- Large graphs (10k-40k resources)
- Very large graphs (40k-100k resources)

Metrics Collected:
- Execution time
- Memory usage
- Throughput (resources/second)
- Neo4j query performance
- Batch processing efficiency
"""

import asyncio
import logging
import os
from typing import Dict, List

import pytest
from neo4j import GraphDatabase

from src.services.scale_performance import (
    AdaptiveBatchSizer,
    PerformanceMonitor,
    QueryOptimizer,
)
from src.services.scale_up_service import ScaleUpService
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


# Mark all tests in this module as performance tests
pytestmark = [pytest.mark.performance, pytest.mark.slow]


@pytest.fixture
def neo4j_uri():
    """Get Neo4j URI from environment."""
    return os.getenv("NEO4J_URI", "bolt://localhost:7687")


@pytest.fixture
def neo4j_auth():
    """Get Neo4j authentication from environment."""
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "neo4j")
    return (username, password)


@pytest.fixture
async def session_manager(neo4j_uri, neo4j_auth):
    """Create Neo4j session manager."""
    manager = Neo4jSessionManager(neo4j_uri, neo4j_auth[0], neo4j_auth[1])
    yield manager
    # Cleanup after test
    await cleanup_test_data(manager)


async def cleanup_test_data(manager: Neo4jSessionManager):
    """Clean up test data from database."""
    with manager.session() as session:
        session.run(
            """
            MATCH (r:Resource)
            WHERE r.synthetic = true
            DETACH DELETE r
            """
        )


async def create_base_resources(
    manager: Neo4jSessionManager, tenant_id: str, count: int
) -> List[str]:
    """Create base resources for testing."""
    resource_ids = []

    with manager.session() as session:
        for i in range(count):
            resource_id = f"test-resource-{i}"
            session.run(
                """
                CREATE (r:Resource {
                    id: $id,
                    name: $name,
                    type: 'Microsoft.Compute/virtualMachines',
                    tenant_id: $tenant_id,
                    synthetic: false
                })
                """,
                {"id": resource_id, "name": f"vm-{i}", "tenant_id": tenant_id},
            )
            resource_ids.append(resource_id)

    return resource_ids


@pytest.mark.benchmark
class TestAdaptiveBatchSizing:
    """Test adaptive batch sizing algorithms."""

    def test_small_graph_batch_size(self):
        """Test batch size calculation for small graphs (<1k)."""
        batch_size = AdaptiveBatchSizer.calculate_batch_size(500, "write")
        assert 100 <= batch_size <= 500, f"Batch size {batch_size} out of expected range"

    def test_medium_graph_batch_size(self):
        """Test batch size calculation for medium graphs (1k-10k)."""
        batch_size = AdaptiveBatchSizer.calculate_batch_size(5000, "write")
        assert (
            250 <= batch_size <= 1000
        ), f"Batch size {batch_size} out of expected range"

    def test_large_graph_batch_size(self):
        """Test batch size calculation for large graphs (10k-100k)."""
        batch_size = AdaptiveBatchSizer.calculate_batch_size(50000, "write")
        assert (
            500 <= batch_size <= 5000
        ), f"Batch size {batch_size} out of expected range"

    def test_very_large_graph_batch_size(self):
        """Test batch size calculation for very large graphs (>100k)."""
        batch_size = AdaptiveBatchSizer.calculate_batch_size(150000, "write")
        assert (
            2500 <= batch_size <= 10000
        ), f"Batch size {batch_size} out of expected range"

    def test_read_vs_write_batch_size(self):
        """Test that read operations use larger batches than write."""
        read_batch = AdaptiveBatchSizer.calculate_batch_size(10000, "read")
        write_batch = AdaptiveBatchSizer.calculate_batch_size(10000, "write")
        assert read_batch > write_batch, "Read batch should be larger than write batch"

    def test_optimal_batching_calculation(self):
        """Test calculation of batch size and number of batches."""
        batch_size, num_batches = AdaptiveBatchSizer.calculate_optimal_batching(
            40000, "write"
        )
        assert batch_size * num_batches >= 40000, "Batches don't cover all items"
        assert num_batches > 1, "Should create multiple batches"


@pytest.mark.benchmark
class TestPerformanceMonitoring:
    """Test performance monitoring utilities."""

    def test_performance_monitor_basic(self):
        """Test basic performance monitoring."""
        monitor = PerformanceMonitor("test_operation")

        with monitor:
            # Simulate work
            import time

            time.sleep(0.1)
            monitor.record_items(100)
            monitor.record_batch(100)

        metrics = monitor.get_metrics()

        assert metrics.duration_seconds >= 0.1
        assert metrics.items_processed == 100
        assert metrics.batch_count == 1
        assert metrics.throughput_per_second > 0

    def test_performance_monitor_memory_tracking(self):
        """Test memory tracking in performance monitor."""
        monitor = PerformanceMonitor("memory_test")

        with monitor:
            # Allocate some memory
            data = [0] * 1000000
            monitor.update_peak_memory()
            del data

        metrics = monitor.get_metrics()

        assert metrics.memory_mb_start >= 0
        assert metrics.memory_mb_end >= 0
        assert metrics.memory_mb_peak >= metrics.memory_mb_start

    def test_performance_monitor_query_timing(self):
        """Test Neo4j query timing."""
        monitor = PerformanceMonitor("query_test")

        with monitor:
            with monitor.measure_query():
                import time

                time.sleep(0.05)

            with monitor.measure_query():
                import time

                time.sleep(0.05)

        metrics = monitor.get_metrics()

        assert metrics.neo4j_query_count == 2
        assert metrics.neo4j_query_time_seconds >= 0.1

    def test_performance_monitor_metadata(self):
        """Test metadata storage in performance monitor."""
        monitor = PerformanceMonitor("metadata_test")

        with monitor:
            monitor.add_metadata("operation_type", "scale_up")
            monitor.add_metadata("resource_count", 1000)

        metrics = monitor.get_metrics()

        assert metrics.metadata["operation_type"] == "scale_up"
        assert metrics.metadata["resource_count"] == 1000


@pytest.mark.asyncio
@pytest.mark.benchmark
@pytest.mark.skipif(
    os.getenv("SKIP_PERF_BENCHMARKS") == "true",
    reason="Performance benchmarks disabled",
)
class TestScaleUpPerformance:
    """
    Performance benchmarks for scale-up operations.

    These tests measure actual performance with Neo4j.
    They can be skipped by setting SKIP_PERF_BENCHMARKS=true.
    """

    async def test_scale_up_small_graph(self, session_manager):
        """Benchmark: Scale up with small base graph (100 resources -> 1k)."""
        tenant_id = "perf-test-small"

        # Create base resources
        base_ids = await create_base_resources(session_manager, tenant_id, 100)

        # Create service with performance monitoring
        service = ScaleUpService(
            session_manager,
            enable_performance_monitoring=True,
            enable_adaptive_batching=True,
        )

        # Measure scale-up performance
        result = await service.scale_up_template(
            tenant_id=tenant_id, scale_factor=10.0  # 100 -> 1000 resources
        )

        # Assertions
        assert result.success
        assert result.resources_created >= 900  # 100 * (10-1) = 900
        assert result.duration_seconds < 30, "Small graph should complete in <30s"

        logger.info(
            f"Small graph benchmark: {result.resources_created} resources "
            f"in {result.duration_seconds:.2f}s "
            f"({result.resources_created / result.duration_seconds:.1f} resources/s)"
        )

    async def test_scale_up_medium_graph(self, session_manager):
        """Benchmark: Scale up with medium base graph (1k resources -> 5k)."""
        tenant_id = "perf-test-medium"

        # Create base resources
        base_ids = await create_base_resources(session_manager, tenant_id, 1000)

        service = ScaleUpService(
            session_manager,
            enable_performance_monitoring=True,
            enable_adaptive_batching=True,
        )

        result = await service.scale_up_template(
            tenant_id=tenant_id, scale_factor=5.0  # 1k -> 5k resources
        )

        assert result.success
        assert result.resources_created >= 4000
        assert result.duration_seconds < 120, "Medium graph should complete in <2min"

        logger.info(
            f"Medium graph benchmark: {result.resources_created} resources "
            f"in {result.duration_seconds:.2f}s "
            f"({result.resources_created / result.duration_seconds:.1f} resources/s)"
        )

    @pytest.mark.slow
    async def test_scale_up_large_graph(self, session_manager):
        """Benchmark: Scale up with large base graph (5k resources -> 40k)."""
        tenant_id = "perf-test-large"

        # Create base resources
        base_ids = await create_base_resources(session_manager, tenant_id, 5000)

        service = ScaleUpService(
            session_manager,
            enable_performance_monitoring=True,
            enable_adaptive_batching=True,
        )

        result = await service.scale_up_template(
            tenant_id=tenant_id, scale_factor=8.0  # 5k -> 40k resources
        )

        assert result.success
        assert result.resources_created >= 35000
        assert result.duration_seconds < 300, "Large graph should complete in <5min"

        # Performance target: 40k resources in <5 minutes
        throughput = result.resources_created / result.duration_seconds
        assert throughput >= 100, f"Throughput {throughput:.1f} below target of 100 resources/s"

        logger.info(
            f"Large graph benchmark (40k target): {result.resources_created} resources "
            f"in {result.duration_seconds:.2f}s "
            f"({throughput:.1f} resources/s)"
        )


@pytest.mark.benchmark
class TestQueryOptimization:
    """Test query optimization utilities."""

    @pytest.mark.asyncio
    async def test_ensure_indexes(self, session_manager):
        """Test index creation."""
        with session_manager.session() as session:
            indexes = QueryOptimizer.ensure_indexes(session)
            assert len(indexes) > 0, "Should create at least one index"

    def test_unwind_batch_query_generation(self):
        """Test UNWIND batch query generation."""
        query = QueryOptimizer.get_unwind_batch_query()
        assert "UNWIND" in query
        assert "CREATE" in query

    def test_batch_match_query_generation(self):
        """Test batch MATCH query generation."""
        query = QueryOptimizer.get_batch_match_query()
        assert "MATCH" in query
        assert "IN" in query

    def test_query_hints(self):
        """Test query hint addition."""
        base_query = "MATCH (r:Resource) WHERE r.id = $id RETURN r"
        hints = ["USING INDEX r:Resource(id)"]

        optimized = QueryOptimizer.add_query_hints(base_query, hints)
        assert "USING INDEX" in optimized


def benchmark_summary() -> Dict[str, any]:
    """
    Generate benchmark summary for documentation.

    Returns:
        Dictionary with benchmark results
    """
    return {
        "performance_targets": {
            "small_graph_100_to_1k": {"target_time_seconds": 30, "min_throughput": 30},
            "medium_graph_1k_to_5k": {
                "target_time_seconds": 120,
                "min_throughput": 40,
            },
            "large_graph_5k_to_40k": {
                "target_time_seconds": 300,
                "min_throughput": 100,
            },
        },
        "optimizations": {
            "adaptive_batching": "Enabled",
            "parallel_processing": "Enabled for >10k resources",
            "indexes": "Created on critical fields",
            "performance_monitoring": "Built-in metrics collection",
        },
    }


if __name__ == "__main__":
    # Print benchmark configuration
    print("=== Scale Operations Performance Benchmarks ===")
    print("\nTargets:")
    print("- Small (100 -> 1k): <30 seconds")
    print("- Medium (1k -> 5k): <2 minutes")
    print("- Large (5k -> 40k): <5 minutes (100+ resources/s)")
    print("\nRun with: pytest tests/performance/ -v -m benchmark")
