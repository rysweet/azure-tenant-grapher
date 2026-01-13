"""
Integration tests for performance optimizations.

These tests verify that performance optimizations are properly integrated
and don't break existing functionality.
"""

from src.services.scale_performance import (
    AdaptiveBatchSizer,
    PerformanceMonitor,
    QueryOptimizer,
)


class TestAdaptiveBatchSizer:
    """Test adaptive batch sizing algorithms."""

    def test_small_graph_batch_size(self):
        """Test batch size calculation for small graphs."""
        batch_size = AdaptiveBatchSizer.calculate_batch_size(500, "write")
        assert 100 <= batch_size <= 500

    def test_medium_graph_batch_size(self):
        """Test batch size calculation for medium graphs."""
        batch_size = AdaptiveBatchSizer.calculate_batch_size(5000, "write")
        assert 250 <= batch_size <= 1000

    def test_large_graph_batch_size(self):
        """Test batch size calculation for large graphs."""
        batch_size = AdaptiveBatchSizer.calculate_batch_size(50000, "write")
        assert 500 <= batch_size <= 5000

    def test_read_vs_write_batching(self):
        """Test that read operations use larger batches."""
        read_batch = AdaptiveBatchSizer.calculate_batch_size(10000, "read")
        write_batch = AdaptiveBatchSizer.calculate_batch_size(10000, "write")
        assert read_batch > write_batch

    def test_optimal_batching(self):
        """Test calculation of batch size and count."""
        batch_size, num_batches = AdaptiveBatchSizer.calculate_optimal_batching(
            40000, "write"
        )
        assert batch_size * num_batches >= 40000
        assert num_batches > 1


class TestPerformanceMonitor:
    """Test performance monitoring utilities."""

    def test_basic_monitoring(self):
        """Test basic performance monitoring."""
        monitor = PerformanceMonitor("test_operation")

        with monitor:
            import time

            time.sleep(0.01)
            monitor.record_items(100)
            monitor.record_batch(100)

        metrics = monitor.get_metrics()

        assert metrics.duration_seconds >= 0.01
        assert metrics.items_processed == 100
        assert metrics.batch_count == 1

    def test_metrics_export(self):
        """Test metrics export to dictionary."""
        monitor = PerformanceMonitor("test_export")

        with monitor:
            monitor.record_items(50)

        metrics_dict = monitor.get_metrics().to_dict()

        assert "operation_name" in metrics_dict
        assert "duration_seconds" in metrics_dict
        assert "items_processed" in metrics_dict
        assert metrics_dict["items_processed"] == 50

    def test_metadata_storage(self):
        """Test metadata storage in monitor."""
        monitor = PerformanceMonitor("test_metadata")

        with monitor:
            monitor.add_metadata("key1", "value1")
            monitor.add_metadata("key2", 42)

        metrics = monitor.get_metrics()

        assert metrics.metadata["key1"] == "value1"
        assert metrics.metadata["key2"] == 42


class TestQueryOptimizer:
    """Test query optimization utilities."""

    def test_unwind_query_generation(self):
        """Test UNWIND query generation."""
        query = QueryOptimizer.get_unwind_batch_query()
        assert "UNWIND" in query
        assert "CREATE" in query
        assert "$batch" in query

    def test_batch_match_query_generation(self):
        """Test batch MATCH query generation."""
        query = QueryOptimizer.get_batch_match_query()
        assert "MATCH" in query
        assert "IN" in query
        assert "$ids" in query

    def test_query_hints_addition(self):
        """Test query hint addition."""
        base_query = "MATCH (r:Resource) WHERE r.id = $id RETURN r"
        hints = ["USING INDEX r:Resource(id)"]

        optimized = QueryOptimizer.add_query_hints(base_query, hints)

        assert "USING INDEX" in optimized
        assert "MATCH" in optimized
        assert "WHERE" in optimized
