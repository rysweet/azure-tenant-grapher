"""
Performance test for relationship batching optimization.

This test demonstrates the performance improvement from batching vs N+1 queries.
"""

import time
from unittest.mock import Mock

from src.relationship_rules.relationship_rule import RelationshipRule


class MockDatabaseOperations:
    """Mock database operations that simulates query latency."""

    def __init__(self, query_latency_ms: float = 50.0):
        self.query_latency_ms = query_latency_ms
        self.query_count = 0
        self.session_manager = Mock()
        self.session_manager.session = self._mock_session

    def _mock_session(self):
        """Mock session context manager."""
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        # Mock session.run() to simulate query latency
        def mock_run(*args, **kwargs):
            # Simulate network/database latency
            time.sleep(self.query_latency_ms / 1000.0)
            self.query_count += 1

            # Return mock result
            mock_result = Mock()
            mock_result.single = Mock(
                return_value={"created": 1, "abstracted_count": 1}
            )
            return mock_result

        mock_session.run = mock_run
        return mock_session


class TestRelationshipBatchingPerformance:
    """Test suite for relationship batching performance improvements."""

    def test_n_plus_one_vs_batching_performance(self):
        """
        Compare performance of N+1 queries vs batched approach.

        Expected results:
        - N+1 approach: O(N) queries, slow
        - Batched approach: O(1) queries, fast
        - Speedup: 50-100x for typical workloads
        """
        # Test parameters
        num_relationships = 300  # Representative batch size
        query_latency_ms = 10.0  # Conservative estimate (actual: 50-200ms)

        # Create mock database with simulated latency
        MockDatabaseOperations(query_latency_ms=query_latency_ms)

        # Create relationship rule with dual-graph enabled
        rule = RelationshipRule.__new__(RelationshipRule)
        rule.__init__(enable_dual_graph=True)

        # Test 1: N+1 approach (old code)
        print(f"\n{'=' * 80}")
        print("TEST 1: N+1 Query Approach (Old Code)")
        print(f"{'=' * 80}")

        db_ops_n_plus_one = MockDatabaseOperations(query_latency_ms=query_latency_ms)
        rule_n_plus_one = RelationshipRule.__new__(RelationshipRule)
        rule_n_plus_one.__init__(enable_dual_graph=True)

        start_time = time.time()
        for i in range(num_relationships):
            # Simulate creating relationship immediately (N+1 pattern)
            rule_n_plus_one.create_dual_graph_relationship(
                db_ops_n_plus_one,
                f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm{i}",
                "USES_SUBNET",
                f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet{i % 10}",
            )
        n_plus_one_time = time.time() - start_time

        print(f"Relationships created: {num_relationships}")
        print(f"Database queries executed: {db_ops_n_plus_one.query_count}")
        print(f"Time elapsed: {n_plus_one_time:.3f} seconds")
        print(
            f"Time per relationship: {(n_plus_one_time * 1000 / num_relationships):.1f}ms"
        )

        # Test 2: Batched approach (new code)
        print(f"\n{'=' * 80}")
        print("TEST 2: Batched Query Approach (New Code)")
        print(f"{'=' * 80}")

        db_ops_batched = MockDatabaseOperations(query_latency_ms=query_latency_ms)
        rule_batched = RelationshipRule.__new__(RelationshipRule)
        rule_batched.__init__(enable_dual_graph=True)

        start_time = time.time()
        for i in range(num_relationships):
            # Queue relationships instead of creating immediately
            rule_batched.queue_dual_graph_relationship(
                f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm{i}",
                "USES_SUBNET",
                f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet{i % 10}",
            )

        # Flush all at once
        rule_batched.flush_relationship_buffer(db_ops_batched)
        batched_time = time.time() - start_time

        print(f"Relationships created: {num_relationships}")
        print(f"Database queries executed: {db_ops_batched.query_count}")
        print(f"Time elapsed: {batched_time:.3f} seconds")
        print(
            f"Time per relationship: {(batched_time * 1000 / num_relationships):.1f}ms"
        )

        # Performance comparison
        print(f"\n{'=' * 80}")
        print("PERFORMANCE COMPARISON")
        print(f"{'=' * 80}")

        speedup = n_plus_one_time / batched_time if batched_time > 0 else float("inf")
        time_saved = n_plus_one_time - batched_time

        print(
            f"N+1 approach:      {n_plus_one_time:.3f}s ({db_ops_n_plus_one.query_count} queries)"
        )
        print(
            f"Batched approach:  {batched_time:.3f}s ({db_ops_batched.query_count} queries)"
        )
        print(f"Speedup:           {speedup:.1f}x faster")
        print(
            f"Time saved:        {time_saved:.3f}s ({time_saved * 100 / n_plus_one_time:.1f}% reduction)"
        )
        print(
            f"Query reduction:   {db_ops_n_plus_one.query_count - db_ops_batched.query_count} fewer queries"
        )

        # Extrapolate to full scan
        print(f"\n{'=' * 80}")
        print("EXTRAPOLATION TO FULL SCAN (2,891 resources x 3 rels = 8,673 rels)")
        print(f"{'=' * 80}")

        total_relationships = 8673
        scale_factor = total_relationships / num_relationships

        n_plus_one_full = n_plus_one_time * scale_factor
        batched_full = batched_time * scale_factor
        time_saved_full = n_plus_one_full - batched_full

        print(f"N+1 approach:      {n_plus_one_full / 60:.1f} minutes")
        print(f"Batched approach:  {batched_full / 60:.1f} minutes")
        print(
            f"Time saved:        {time_saved_full / 60:.1f} minutes ({time_saved_full / 3600:.2f} hours)"
        )
        print(
            f"Query reduction:   {total_relationships - (total_relationships // 100)} queries"
        )

        # Assertions
        assert db_ops_batched.query_count < db_ops_n_plus_one.query_count, (
            "Batched approach should use fewer queries"
        )
        assert speedup > 10, f"Expected at least 10x speedup, got {speedup:.1f}x"

    def test_auto_flush_mechanism(self):
        """Test that auto-flush triggers at buffer threshold."""
        db_ops = MockDatabaseOperations(query_latency_ms=1.0)

        rule = RelationshipRule.__new__(RelationshipRule)
        rule.__init__(enable_dual_graph=True)
        rule._buffer_size = 10  # Small buffer for testing

        # Add 9 relationships - should not flush yet
        for i in range(9):
            rule.queue_dual_graph_relationship(f"src{i}", "REL_TYPE", f"tgt{i}")

        assert len(rule._relationship_buffer) == 9
        assert db_ops.query_count == 0

        # Add 10th relationship - should trigger auto-flush
        rule.queue_dual_graph_relationship("src9", "REL_TYPE", "tgt9")
        rule.auto_flush_if_needed(db_ops)

        # Buffer should be flushed, queries executed
        assert len(rule._relationship_buffer) == 0
        assert db_ops.query_count > 0

    def test_buffer_grouping_by_relationship_type(self):
        """Test that relationships are grouped by type for optimal batching."""
        db_ops = MockDatabaseOperations(query_latency_ms=1.0)

        rule = RelationshipRule.__new__(RelationshipRule)
        rule.__init__(enable_dual_graph=True)

        # Add different relationship types
        rule.queue_dual_graph_relationship("vm1", "USES_SUBNET", "subnet1")
        rule.queue_dual_graph_relationship("vm2", "USES_SUBNET", "subnet2")
        rule.queue_dual_graph_relationship("subnet1", "SECURED_BY", "nsg1")
        rule.queue_dual_graph_relationship("vm3", "USES_SUBNET", "subnet3")
        rule.queue_dual_graph_relationship("subnet2", "SECURED_BY", "nsg2")

        # Flush and verify grouping efficiency
        flushed = rule.flush_relationship_buffer(db_ops)

        # Should create all 5 relationships
        # Should execute 2 queries (one per relationship type)
        assert flushed == 5
        assert db_ops.query_count == 2  # USES_SUBNET batch + SECURED_BY batch


if __name__ == "__main__":
    """Run performance test standalone."""
    test = TestRelationshipBatchingPerformance()
    test.test_n_plus_one_vs_batching_performance()
    print("\n" + "=" * 80)
    print("Performance test completed successfully!")
    print("=" * 80)
