#!/usr/bin/env python
"""
Performance Optimizations Demo

This script demonstrates the performance optimizations for handling
large-scale graph operations (40k+ resources).

Run with:
    python examples/performance_optimizations_demo.py
"""

import asyncio
import json
import logging
import os

from src.services.scale_performance import (
    AdaptiveBatchSizer,
    PerformanceMonitor,
    QueryOptimizer,
)
from src.services.scale_up_service import ScaleUpService
from src.utils.session_manager import Neo4jSessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def demo_adaptive_batching():
    """Demonstrate adaptive batch sizing."""
    print("\n" + "=" * 60)
    print("DEMO 1: Adaptive Batch Sizing")
    print("=" * 60)

    test_sizes = [100, 1000, 5000, 10000, 40000, 100000]

    for size in test_sizes:
        write_batch = AdaptiveBatchSizer.calculate_batch_size(size, "write")
        read_batch = AdaptiveBatchSizer.calculate_batch_size(size, "read")
        batch_size, num_batches = AdaptiveBatchSizer.calculate_optimal_batching(
            size, "write"
        )

        print(f"\nGraph Size: {size:,} items")
        print(f"  Write Batch: {write_batch:,}")
        print(f"  Read Batch:  {read_batch:,}")
        print(f"  Batching:    {num_batches} batches of {batch_size} items")


def demo_performance_monitoring():
    """Demonstrate performance monitoring."""
    print("\n" + "=" * 60)
    print("DEMO 2: Performance Monitoring")
    print("=" * 60)

    monitor = PerformanceMonitor("demo_operation")

    with monitor:
        print("\nSimulating work...")

        # Simulate processing items in batches
        for _i in range(5):
            import time

            time.sleep(0.1)

            # Simulate Neo4j query
            with monitor.measure_query():
                time.sleep(0.05)

            monitor.record_items(1000)
            monitor.record_batch(1000)

        monitor.add_metadata("strategy", "template")
        monitor.add_metadata("tenant_id", "demo-tenant")

    # Get and display metrics
    metrics = monitor.get_metrics()
    print("\n" + "-" * 60)
    print(str(metrics))
    print("-" * 60)

    # Export to JSON
    metrics_dict = metrics.to_dict()
    print("\nMetrics as JSON:")
    print(json.dumps(metrics_dict, indent=2))


def demo_query_optimization():
    """Demonstrate query optimization utilities."""
    print("\n" + "=" * 60)
    print("DEMO 3: Query Optimization")
    print("=" * 60)

    # Generate optimized queries
    print("\n1. UNWIND Batch Insert:")
    unwind_query = QueryOptimizer.get_unwind_batch_query()
    print(unwind_query)

    print("\n2. Batch Match Query:")
    match_query = QueryOptimizer.get_batch_match_query()
    print(match_query)

    print("\n3. Query with Hints:")
    base_query = "MATCH (r:Resource) WHERE r.id = $id RETURN r"
    hints = ["USING INDEX r:Resource(id)"]
    optimized_query = QueryOptimizer.add_query_hints(base_query, hints)
    print(f"Original:  {base_query}")
    print(f"Optimized: {optimized_query}")


async def demo_scale_up_with_optimizations():
    """Demonstrate scale-up with all optimizations enabled."""
    print("\n" + "=" * 60)
    print("DEMO 4: Scale-Up with Optimizations")
    print("=" * 60)

    # Check if Neo4j is available
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not neo4j_password:
        print("\n⚠️  Neo4j not configured. Skipping live demo.")
        print("   Set NEO4J_PASSWORD to run this demo.")
        return

    print(f"\nConnecting to Neo4j at {neo4j_uri}...")

    try:
        # Create session manager
        session_manager = Neo4jSessionManager(neo4j_uri, neo4j_user, neo4j_password)

        # Create service with all optimizations
        service = ScaleUpService(
            session_manager,
            enable_performance_monitoring=True,
            enable_adaptive_batching=True,
        )

        print("\n✓ Service initialized with optimizations:")
        print("  - Adaptive batching: ENABLED")
        print("  - Performance monitoring: ENABLED")
        print("  - Parallel processing: AUTO (>10k resources)")
        print("  - Index optimization: ENABLED")

        print("\nNote: Run 'atg scale-up' command for full demo with real data")

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("   Make sure Neo4j is running and credentials are correct")


def demo_performance_comparison():
    """Show theoretical performance comparison."""
    print("\n" + "=" * 60)
    print("DEMO 5: Performance Comparison")
    print("=" * 60)

    print("\nTheoretical Performance (40k resources):")
    print("\nBEFORE Optimizations:")
    print("  - Fixed batch size: 500")
    print("  - Sequential processing")
    print("  - No indexes")
    print("  - No monitoring")
    print("  - Expected time: 15-20 minutes")
    print("  - Throughput: ~30-40 resources/s")

    print("\nAFTER Optimizations:")
    print("  - Adaptive batch size: 2000-3000 (for 40k)")
    print("  - Parallel processing: 5 concurrent batches")
    print("  - Indexed queries: 10-100x faster lookups")
    print("  - Performance monitoring: Built-in")
    print("  - Expected time: 3-5 minutes")
    print("  - Throughput: 100-200 resources/s")

    print("\nSpeedup: 3-5x improvement")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 60)
    print(" Performance Optimizations Demo")
    print(" Azure Tenant Grapher - Issue #427")
    print("=" * 60)

    # Run demonstrations
    demo_adaptive_batching()
    demo_performance_monitoring()
    demo_query_optimization()
    demo_performance_comparison()

    # Async demo
    print("\n" + "=" * 60)
    asyncio.run(demo_scale_up_with_optimizations())

    print("\n" + "=" * 60)
    print(" Demo Complete!")
    print("=" * 60)
    print("\nFor more information:")
    print("  - docs/SCALE_PERFORMANCE_GUIDE.md")
    print("  - docs/PERFORMANCE_OPTIMIZATION_SUMMARY.md")
    print("  - tests/performance/test_scale_performance_benchmarks.py")
    print()


if __name__ == "__main__":
    main()
