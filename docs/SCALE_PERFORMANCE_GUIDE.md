# Scale Operations Performance Guide

## Overview

This guide documents performance optimizations for handling large-scale graph operations (40k+ resources) in Azure Tenant Grapher. The optimizations focus on the 80/20 rule: optimize the 20% of code causing 80% of performance issues.

## Performance Targets

| Graph Size | Operation | Target Time | Min Throughput |
|-----------|-----------|-------------|----------------|
| 100 → 1k | Scale-up template | <30 seconds | 30 resources/s |
| 1k → 5k | Scale-up template | <2 minutes | 40 resources/s |
| 5k → 40k | Scale-up template | <5 minutes | 100 resources/s |
| 40k+ | Scale-up template | <10 minutes | 100+ resources/s |

## Optimizations Implemented

### 1. Adaptive Batch Sizing

**Problem**: Fixed batch size (500) is suboptimal for both small and large graphs.

**Solution**: Dynamic batch sizing based on graph size and operation type.

```python
from src.services.scale_performance import AdaptiveBatchSizer

# Automatically calculates optimal batch size
batch_size = AdaptiveBatchSizer.calculate_batch_size(
    total_items=40000,
    operation_type="write"  # or "read"
)
# Returns: ~2000 for 40k items (write operation)
```

**Batch Size Tiers**:
- Small graphs (<1k): 100-500 batch
- Medium graphs (1k-10k): 500-1000 batch
- Large graphs (10k-100k): 1000-5000 batch
- Very large graphs (>100k): 5000-10000 batch

**Write vs Read**: Write operations use 50% smaller batches for better transaction control.

### 2. Parallel Processing

**Problem**: Sequential batch processing underutilizes database capacity for large operations.

**Solution**: Parallel batch inserts with controlled concurrency for operations >10k resources.

```python
# Automatically enabled for large operations
service = ScaleUpService(
    session_manager,
    enable_adaptive_batching=True  # Default: True
)

# For 40k resources: Uses 5 concurrent batch inserts
result = await service.scale_up_template(
    tenant_id="...",
    scale_factor=8.0  # 5k -> 40k
)
```

**Concurrency Limits**:
- Max concurrent batches: `min(5, total_batches // 10)`
- Uses asyncio.Semaphore for controlled concurrency
- Prevents overwhelming Neo4j with too many concurrent connections

### 3. Neo4j Index Optimization

**Problem**: Queries on large graphs slow down without proper indexes.

**Solution**: Automatic index creation on critical fields.

**Indexes Created**:
1. `Resource.id` - Most critical (primary lookup)
2. `Resource.synthetic` - Filter synthetic resources
3. `Resource.scale_operation_id` - Operation-specific queries
4. `Resource.template_source_id` - Template replication mapping
5. `Resource.tenant_id` - Tenant-specific queries
6. Composite index on `(synthetic, scale_operation_id)`

**Impact**:
- Query time: O(log n) instead of O(n) for indexed lookups
- 10x-100x speedup for large graphs

### 4. Query Optimization

**Problem**: Inefficient query patterns for batch operations.

**Solution**: Use UNWIND for batch inserts and parameterized IN clauses for batch lookups.

```python
# Optimized batch insert
query = """
UNWIND $batch as item
CREATE (n:Resource)
SET n = item.props
"""
session.run(query, {"batch": resources})

# Optimized batch lookup
query = """
MATCH (n:Resource)
WHERE n.id IN $ids
RETURN n
"""
session.run(query, {"ids": id_list})
```

### 5. Performance Monitoring

**Problem**: No visibility into bottlenecks during operations.

**Solution**: Built-in performance metrics collection.

```python
from src.services.scale_performance import PerformanceMonitor

with PerformanceMonitor("scale_up_template") as monitor:
    # Perform operations
    monitor.record_items(1000)
    monitor.record_batch()

    with monitor.measure_query():
        result = session.run(query)

# Get comprehensive metrics
metrics = monitor.get_metrics()
print(metrics)  # Duration, throughput, memory, Neo4j stats
```

**Metrics Collected**:
- Duration (seconds)
- Items processed
- Throughput (items/second)
- Memory usage (start, end, peak)
- Neo4j query count and time
- Batch count and size
- Custom metadata

### 6. Memory Management

**Problem**: Large operations can cause memory pressure.

**Solution**:
- Stream large result sets with batching (5000 records/batch)
- Clear intermediate data structures
- Monitor peak memory usage

```python
# Streaming pattern used in scale-down
batch_size = 5000
skip = 0

while True:
    result = session.run(query, {"skip": skip, "limit": batch_size})
    batch = list(result)

    if not batch:
        break

    # Process batch
    for record in batch:
        process(record)

    skip += batch_size
```

## Usage Guide

### Enable All Optimizations

```python
from src.services.scale_up_service import ScaleUpService
from src.utils.session_manager import Neo4jSessionManager

# Create service with all optimizations enabled (default)
service = ScaleUpService(
    session_manager=session_manager,
    enable_performance_monitoring=True,  # Track metrics
    enable_adaptive_batching=True,       # Dynamic batch sizing
    validation_enabled=True              # Post-op validation
)

# Run scale-up operation
result = await service.scale_up_template(
    tenant_id="your-tenant-id",
    scale_factor=8.0,  # 5k -> 40k resources
    progress_callback=lambda msg, cur, total: print(f"{msg}: {cur}/{total}")
)

# Check performance metrics (if debug logging enabled)
# Metrics automatically logged at DEBUG level
```

### Custom Batch Sizing

```python
from src.services.scale_performance import AdaptiveBatchSizer

# Calculate batch size for specific use case
batch_size, num_batches = AdaptiveBatchSizer.calculate_optimal_batching(
    total_items=50000,
    operation_type="write"
)

print(f"Process {num_batches} batches of {batch_size} items")
```

### Manual Performance Monitoring

```python
from src.services.scale_performance import PerformanceMonitor

monitor = PerformanceMonitor("my_operation")

with monitor:
    # Your code here
    for i in range(1000):
        process_item(i)
        monitor.record_items(1)

    monitor.record_batch(1000)
    monitor.add_metadata("custom_metric", 42)

# Export metrics
metrics_dict = monitor.get_metrics().to_dict()
print(json.dumps(metrics_dict, indent=2))
```

## Performance Benchmarks

Run performance benchmarks to validate optimizations:

```bash
# Run all performance benchmarks
pytest tests/performance/ -v -m benchmark

# Run specific benchmark suite
pytest tests/performance/test_scale_performance_benchmarks.py::TestScaleUpPerformance -v

# Skip long-running benchmarks
SKIP_PERF_BENCHMARKS=true pytest tests/performance/ -v
```

### Expected Results

Based on hardware (8-core CPU, 16GB RAM, SSD):

| Test | Base Count | Target Count | Expected Time | Throughput |
|------|-----------|--------------|---------------|------------|
| Small | 100 | 1,000 | 15-30s | 30-60 resources/s |
| Medium | 1,000 | 5,000 | 60-120s | 40-80 resources/s |
| Large | 5,000 | 40,000 | 180-300s | 100-200 resources/s |

## Troubleshooting

### Slow Performance

1. **Check indexes exist**:
```python
with session_manager.session() as session:
    result = session.run("SHOW INDEXES")
    indexes = [record for record in result]
    print(f"Found {len(indexes)} indexes")
```

2. **Enable debug logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

3. **Monitor memory usage**:
```bash
# Check Neo4j memory settings
docker exec neo4j bin/neo4j-admin memrec
```

### Out of Memory

1. **Reduce batch size**:
```python
service = ScaleUpService(
    session_manager,
    batch_size=100  # Reduce from default 500
)
```

2. **Disable parallel processing**:
```python
# Manually set threshold higher to disable parallel processing
service = ScaleUpService(
    session_manager,
    enable_adaptive_batching=False  # Use fixed batch size
)
```

3. **Increase Neo4j heap**:
```bash
# Edit Neo4j config
NEO4J_HEAP_INIT=2G
NEO4J_HEAP_MAX=4G
```

### Neo4j Connection Pool Exhausted

This can happen with aggressive parallel processing.

**Solution**: Limit concurrency by modifying `max_concurrent_batches` in `_insert_batches_parallel()`:

```python
# In scale_up_service.py, line ~896
max_concurrent_batches = min(3, len(batches) // 10)  # Reduce from 5 to 3
```

## Best Practices

### 1. Always Enable Adaptive Batching

For production use with varying graph sizes:
```python
service = ScaleUpService(
    session_manager,
    enable_adaptive_batching=True  # Adapts to graph size
)
```

### 2. Monitor Performance in Production

Use performance monitoring to track real-world performance:
```python
service = ScaleUpService(
    session_manager,
    enable_performance_monitoring=True
)
```

### 3. Tune for Your Hardware

Default settings work for:
- 8+ cores
- 16GB+ RAM
- SSD storage
- Dedicated Neo4j instance

For constrained environments:
```python
service = ScaleUpService(
    session_manager,
    batch_size=250,  # Smaller batches
    enable_adaptive_batching=False  # Fixed sizing
)
```

### 4. Use Progress Callbacks

For long-running operations, provide user feedback:
```python
def progress_callback(message, current, total):
    print(f"\r{message}: {current}/{total} ({current/total*100:.1f}%)", end="")

result = await service.scale_up_template(
    tenant_id=tenant_id,
    scale_factor=8.0,
    progress_callback=progress_callback
)
```

## Architecture Decisions

### Why Adaptive Batching?

Fixed batch sizes cause:
- **Small graphs**: Overhead of many small transactions
- **Large graphs**: Poor memory utilization and throughput

Adaptive batching optimizes for both extremes.

### Why Limited Concurrency?

Unlimited parallel processing causes:
- Neo4j connection pool exhaustion
- Memory pressure from buffering
- CPU contention

Limited concurrency (max 5) balances throughput and stability.

### Why 10k Threshold for Parallelization?

Below 10k resources:
- Overhead of coordination outweighs benefits
- Sequential processing is fast enough

Above 10k resources:
- Parallelization provides significant speedup
- Coordination overhead becomes negligible

### Why UNWIND for Batch Inserts?

UNWIND is Neo4j's recommended pattern for bulk inserts:
- Single query parse and plan
- Efficient parameter passing
- Automatic transaction batching

Alternative (CREATE loops) is 5-10x slower.

## Future Optimizations

Potential future improvements (not yet implemented):

1. **APOC Procedures**: Use APOC for even faster bulk operations
2. **Write-ahead Buffering**: Buffer writes in memory before committing
3. **Relationship Type Indexing**: Index relationship types for faster traversal
4. **Graph Algorithms**: Use Neo4j Graph Data Science for pattern analysis
5. **Streaming Export**: Export to file during generation (constant memory)

## Performance Metrics Reference

### PerformanceMetrics Fields

| Field | Type | Description |
|-------|------|-------------|
| `operation_name` | str | Name of monitored operation |
| `duration_seconds` | float | Total execution time |
| `items_processed` | int | Number of items processed |
| `throughput_per_second` | float | Items per second |
| `memory_mb_start` | float | Memory at start (MB) |
| `memory_mb_end` | float | Memory at end (MB) |
| `memory_mb_peak` | float | Peak memory usage (MB) |
| `batch_count` | int | Number of batches |
| `batch_size` | int | Size of batches |
| `neo4j_query_count` | int | Number of queries |
| `neo4j_query_time_seconds` | float | Time in queries |
| `error_count` | int | Errors encountered |
| `metadata` | dict | Custom metrics |

### Export Metrics

```python
metrics = monitor.get_metrics()

# Export to JSON
import json
with open("metrics.json", "w") as f:
    json.dump(metrics.to_dict(), f, indent=2)

# Export to string
print(str(metrics))

# Export to dict for analysis
data = metrics.to_dict()
print(f"Throughput: {data['throughput_per_second']} items/s")
```

## Related Documentation

- [Scale Operations Specification](SCALE_OPERATIONS.md)
- [Scale Operations Examples](SCALE_OPERATIONS_E2E_DEMONSTRATION.md)
- [Neo4j Schema Reference](NEO4J_SCHEMA_REFERENCE.md)

## Contact

For performance issues or questions:
1. Check this guide first
2. Run performance benchmarks
3. Enable debug logging
4. Collect performance metrics
5. Open GitHub issue with metrics
