# Pathfinding Algorithm Evaluation in Azure Tenant Grapher

## Overview

This document describes the pathfinding algorithm evaluation framework used in the Azure Tenant Grapher project. The evaluation focuses on graph topology preservation and query pattern performance in the context of the **dual-graph architecture**, where every Azure resource is stored as two nodes (original and abstracted).

## Evaluation Context

### Dual-Graph Architecture

The system uses a dual-graph architecture where:
- **Original nodes** (`:Resource:Original`): Real Azure IDs from the source tenant
- **Abstracted nodes** (`:Resource`): Translated IDs suitable for cross-tenant deployment
- **Link relationship**: `SCAN_SOURCE_NODE` connects abstracted to original nodes

This architecture enables cross-tenant deployments while maintaining queryable topology in both representations.

## Pathfinding Algorithm Tests

The pathfinding evaluation is primarily located in:
- **Test File**: `tests/test_graph_topology_preservation.py`
- **Query Pattern Tests**: `tests/test_neo4j_query_patterns.py`
- **Performance Benchmarks**: `tests/performance/test_scale_performance_benchmarks.py`

### 1. Shortest Path Preservation

**Location**: `tests/test_graph_topology_preservation.py:339-352`

**Test**: `test_shortest_path_preservation()`

**Methodology**:
- Find shortest path between two resources in the original graph
- Find shortest path between corresponding resources in the abstracted graph
- Compare path characteristics

**Evaluation Metrics**:
- **Path Length**: Verify path length is identical in both graphs
- **Node Types**: Verify intermediate node types match between graphs
- **Path Equivalence**: Ensure structural equivalence (isomorphism)

**Cypher Query Pattern**:
```cypher
# Original Graph
MATCH (start:Original), (end:Original)
WHERE start.name = 'resource1' AND end.name = 'resource2'
MATCH path = shortestPath((start)-[*]-(end))
RETURN path

# Abstracted Graph
MATCH (start:Resource), (end:Resource)
WHERE NOT start:Original AND NOT end:Original
AND start.name = 'resource1' AND end.name = 'resource2'
MATCH path = shortestPath((start)-[*]-(end))
RETURN path
```

**Expected Behavior**: Both queries should return paths with the same length and structure, differing only in node IDs.

### 2. Multi-Hop Path Queries

**Location**: `tests/test_graph_topology_preservation.py:275-296`

**Test**: `test_multi_hop_path_queries_return_same_results()`

**Methodology**:
- Execute multi-hop traversal queries (1-5 hops) in both graphs
- Compare the set of resources discovered

**Evaluation Metrics**:
- **Resource Discovery**: Same resources found in both graphs (by name/type)
- **Path Count**: Same number of paths discovered
- **Hop Distance**: Equivalent hop distances for resource pairs

**Cypher Query Pattern**:
```cypher
# Query all resources connected to a VNet within 5 hops
MATCH path = (vnet:Resource {name: 'vnet-prod'})-[*1..5]-(resource:Resource)
WHERE NOT vnet:Original AND NOT resource:Original
RETURN resource.name, length(path) as hops
```

### 3. Centrality Measures

**Location**: `tests/test_graph_topology_preservation.py:354-366`

**Test**: `test_centrality_measures_preserved()`

**Methodology**:
- Calculate betweenness centrality for nodes in both graphs
- Compare centrality rankings

**Evaluation Metrics**:
- **Betweenness Centrality**: Measure how often nodes appear on shortest paths
- **Ranking Consistency**: Most central nodes should be same resource types in both graphs
- **Relative Centrality**: Centrality ratios between nodes should match

**Algorithm**: Betweenness centrality measures the number of shortest paths that pass through a node, indicating critical connection points in the network topology.

### 4. Strongly Connected Components

**Location**: `tests/test_graph_topology_preservation.py:326-337`

**Test**: `test_strongly_connected_components_match()`

**Methodology**:
- Use graph algorithms to identify strongly connected components (SCCs)
- Verify same component structure exists in both graphs

**Evaluation Metrics**:
- **Component Count**: Same number of SCCs in both graphs
- **Component Size Distribution**: Same distribution of component sizes
- **Component Structure**: Each SCC has equivalent structure (by resource types)

**Algorithm**: Identifies subgraphs where every node is reachable from every other node within the component.

### 5. Query Performance Benchmarks

**Location**: `tests/test_neo4j_query_patterns.py:372-428`

**Test Suite**: `TestQueryPerformance`

**Methodology**:
- Measure query execution time for pathfinding operations
- Verify index usage for optimal performance
- Profile query plans using EXPLAIN/PROFILE

**Evaluation Metrics**:

#### Execution Time
- **Target**: < 100ms for typical shortest path queries
- **Measurement**: End-to-end query execution time

#### Index Usage
- **Abstracted ID Index**: Verify index on `:Resource(id)` for fast node lookups
- **Original ID Index**: Verify index on `:Original(id)` for reverse lookups
- **Label Filtering**: Verify queries use `NodeByLabelScan` or `NodeIndexSeek`

**Test Queries**:
```cypher
# Verify index exists
SHOW INDEXES

# Expected indexes:
# - resource_id_idx: FOR (r:Resource) ON (r.id)
# - Original ID index
```

#### Query Plan Optimization
**Location**: `tests/test_neo4j_query_patterns.py:416-427`

**Test**: `test_label_filtering_uses_index()`

**Methodology**: Use `EXPLAIN` or `PROFILE` to verify query execution plan uses indexes efficiently

## Performance Benchmarking Framework

**Location**: `tests/performance/test_scale_performance_benchmarks.py`

### Scale-Based Performance Tests

The performance evaluation framework tests pathfinding and graph operations at multiple scales:

#### Small Graphs (100-1k resources)
- **Target Time**: < 30 seconds for operations
- **Min Throughput**: 30 resources/second

#### Medium Graphs (1k-10k resources)
- **Target Time**: < 2 minutes for operations
- **Min Throughput**: 40 resources/second

#### Large Graphs (10k-40k resources)
- **Target Time**: < 5 minutes for operations
- **Min Throughput**: 100 resources/second

### Performance Metrics Collection

**Location**: `src/services/scale_performance.py`

**Class**: `PerformanceMetrics`

The framework collects comprehensive metrics for all graph operations:

#### Timing Metrics
- **duration_seconds**: Total operation duration
- **start_time**: Operation start timestamp
- **end_time**: Operation end timestamp

#### Throughput Metrics
- **items_processed**: Number of nodes/relationships processed
- **throughput_per_second**: Items processed per second (calculated as `items_processed / duration_seconds`)

#### Memory Metrics
- **memory_mb_start**: Memory usage at operation start (MB)
- **memory_mb_end**: Memory usage at operation end (MB)
- **memory_mb_peak**: Peak memory usage during operation (MB)
- **memory_delta_mb**: Change in memory usage (`memory_mb_end - memory_mb_start`)

#### Neo4j Query Metrics
- **neo4j_query_count**: Number of Cypher queries executed
- **neo4j_query_time_seconds**: Total time spent in Neo4j queries
- **neo4j_query_overhead_percent**: Percentage of total time spent in queries (`(neo4j_query_time_seconds / duration_seconds) * 100`)

#### Batch Processing Metrics
- **batch_count**: Number of batches processed
- **batch_size**: Size of each batch
- **Adaptive batch sizing**: Dynamic calculation based on graph size

#### Error Tracking
- **error_count**: Number of errors encountered during operation

#### Custom Metadata
- **metadata**: Dictionary for operation-specific metrics

### Adaptive Batch Sizing Algorithm

**Location**: `src/services/scale_performance.py:233-344`

**Class**: `AdaptiveBatchSizer`

The system uses adaptive batch sizing to optimize pathfinding and graph traversal performance:

#### Batch Size Tiers
```python
# Batch size tiers based on graph size:
(1000, 100, 500)          # < 1k nodes: 100-500 batch
(10000, 500, 1000)        # 1k-10k nodes: 500-1000 batch
(100000, 1000, 5000)      # 10k-100k nodes: 1000-5000 batch
(inf, 5000, 10000)        # > 100k nodes: 5000-10000 batch
```

#### Operation Type Optimization
- **Read operations**: Larger batches (base tier size)
- **Write operations**: Smaller batches (50% of base tier size) for better transaction control

#### Metrics
- **Batch size calculation**: Dynamically calculated based on graph size and operation type
- **Number of batches**: `(total_items + batch_size - 1) // batch_size`

### Performance Monitoring

**Location**: `src/services/scale_performance.py:120-231`

**Class**: `PerformanceMonitor`

Context manager for automatic performance tracking:

```python
with PerformanceMonitor("shortest_path_query") as monitor:
    # Execute pathfinding algorithm
    with monitor.measure_query():
        result = session.run(query)

    monitor.record_items(len(result))
    monitor.update_peak_memory()

metrics = monitor.get_metrics()
```

## Graph Topology Validation Metrics

**Location**: `tests/test_graph_topology_preservation.py:428-494`

**Test Suite**: `TestTopologyValidation`

### Isomorphism Verification

**Location**: `tests/test_graph_topology_preservation.py:86-111`

**Test**: `test_original_and_abstracted_graphs_are_isomorphic()`

**Evaluation Metrics**:
1. **Node Count Equality**: Same number of nodes in both graphs
2. **Relationship Count Equality**: Same number of relationships per type
3. **Topology Structure**: Same graph connectivity pattern
4. **Adjacency Equivalence**: Same adjacency relationships (modulo ID translation)

### Graph Structure Metrics

#### Node Metrics
- **Node count**: Total nodes in each graph
- **Node degree distribution**: Distribution of relationship counts per node
- **Isolated nodes**: Nodes with zero relationships

#### Relationship Metrics
- **Relationship count per type**: Count for each relationship type (CONTAINS, USES_IDENTITY, CONNECTED_TO, etc.)
- **Relationship density**: `actual_relationships / possible_relationships`
- **Bidirectional relationships**: Verify symmetric relationships are maintained

#### Path Metrics
- **Shortest path length distribution**: Distribution of shortest path lengths between all node pairs
- **Average path length**: Mean shortest path length across the graph
- **Diameter**: Maximum shortest path length (longest shortest path)

### Recursive Traversal

**Location**: `tests/test_graph_topology_preservation.py:413-425`

**Test**: `test_recursive_relationship_traversal()`

**Methodology**:
- Execute recursive queries with variable-length path patterns
- Compare results across both graphs

**Cypher Pattern**:
```cypher
# Find all resources contained by a subscription (any depth)
MATCH (sub:Resource)-[:CONTAINS*]->(resource:Resource)
WHERE NOT sub:Original AND NOT resource:Original
AND sub.type = 'Microsoft.Subscription'
RETURN resource.name
```

**Evaluation Metrics**:
- **Resource discovery completeness**: All resources found in both graphs
- **Depth distribution**: Same distribution of path depths
- **Traversal consistency**: Same traversal order and results

## Query Optimization

**Location**: `src/services/scale_performance.py:346-503`

**Class**: `QueryOptimizer`

### Index Strategy

The system ensures optimal pathfinding performance through strategic indexing:

#### Core Indexes
1. **resource_id_idx**: Index on `Resource.id` (most critical for lookups)
2. **resource_synthetic_idx**: Index on `Resource.synthetic` (filtering)
3. **resource_scale_op_idx**: Index on `Resource.scale_operation_id` (operation queries)
4. **resource_template_source_idx**: Index on `Resource.template_source_id` (template mapping)
5. **resource_synthetic_op_idx**: Composite index on `(synthetic, scale_operation_id)` (combined filtering)
6. **resource_tenant_idx**: Index on `Resource.tenant_id` (tenant-specific queries)

### Query Patterns

#### Batch Match Query
```cypher
MATCH (n:Resource)
WHERE n.id IN $ids
RETURN n
```
**Performance**: Uses index for O(log n) lookup per ID

#### UNWIND Batch Insert
```cypher
UNWIND $batch as item
CREATE (n:Resource)
SET n = item.props
```
**Performance**: Most efficient method for batch insertion in Neo4j

## Test Status

⚠️ **Note**: Many of the tests described above are marked as **EXPECTED TO FAIL** as part of a Test-Driven Development (TDD) approach. These tests define the specification for pathfinding evaluation but the implementation is still in progress.

### Implemented Tests
- ✅ Adaptive batch sizing calculation
- ✅ Performance metrics collection
- ✅ Index creation and verification
- ✅ Basic query pattern generation

### In-Progress Tests (TDD)
- ⏳ Shortest path preservation verification
- ⏳ Multi-hop path equivalence
- ⏳ Centrality measure calculations
- ⏳ Strongly connected components analysis
- ⏳ Graph isomorphism verification

## Running the Evaluations

### Performance Benchmarks
```bash
# Run all performance benchmarks
pytest tests/performance/ -v -m benchmark

# Run specific scale tests
pytest tests/performance/test_scale_performance_benchmarks.py::TestScaleUpPerformance -v

# Skip slow benchmarks
export SKIP_PERF_BENCHMARKS=true
pytest tests/performance/ -v
```

### Query Pattern Tests
```bash
# Run dual-graph query tests
pytest tests/test_neo4j_query_patterns.py -v -m dual_graph

# Run topology preservation tests
pytest tests/test_graph_topology_preservation.py -v -m dual_graph
```

### Integration Tests
```bash
# Run with test artifacts
./scripts/run_tests_with_artifacts.sh

# Run specific integration test
pytest tests/test_scale_performance_integration.py -v
```

## Performance Targets Summary

| Graph Size | Resources | Target Time | Min Throughput | Batch Size Range |
|------------|-----------|-------------|----------------|------------------|
| Small      | 100-1k    | < 30s       | 30 res/s       | 100-500          |
| Medium     | 1k-10k    | < 2min      | 40 res/s       | 500-1,000        |
| Large      | 10k-40k   | < 5min      | 100 res/s      | 1,000-5,000      |
| Very Large | > 100k    | TBD         | TBD            | 5,000-10,000     |

## References

### Source Code
- **Topology Tests**: `tests/test_graph_topology_preservation.py`
- **Query Pattern Tests**: `tests/test_neo4j_query_patterns.py`
- **Performance Benchmarks**: `tests/performance/test_scale_performance_benchmarks.py`
- **Performance Service**: `src/services/scale_performance.py`

### Documentation
- **Dual Graph Schema**: `docs/DUAL_GRAPH_SCHEMA.md`
- **Neo4j Schema Reference**: `docs/NEO4J_SCHEMA_REFERENCE.md`
- **Project Instructions**: `CLAUDE.md`

## Conclusion

The Azure Tenant Grapher pathfinding evaluation framework provides comprehensive metrics and testing for graph algorithms in the context of dual-graph architecture. The evaluation focuses on:

1. **Correctness**: Ensuring pathfinding algorithms work identically in both original and abstracted graphs
2. **Performance**: Meeting throughput and latency targets at various scales
3. **Optimization**: Using adaptive batching and query optimization for large graphs
4. **Metrics**: Collecting detailed performance data for analysis and optimization

The TDD approach ensures that evaluation criteria are well-defined before implementation, with clear metrics for success.
