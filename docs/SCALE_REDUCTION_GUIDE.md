# Scale Reduction Guide

## Overview

Scale Reduction extracts representative subsets from large Azure tenant graphs (40k+ resources) that preserve structural complexity and uniqueness without retaining full scale. This enables faster analysis, testing, and visualization while maintaining all unique node and relationship patterns.

## Use Cases

| Use Case | Description | Size Reduction |
|----------|-------------|----------------|
| **Graph Analysis** | Analyze graph structure without loading full 40k+ nodes | 90-95% |
| **Testing** | Create representative test fixtures from production graphs | 85-95% |
| **Visualization** | Render complex graphs in 3D without performance issues | 90-95% |
| **Pattern Discovery** | Identify unique structural patterns across tenant | 85-90% |
| **Documentation** | Generate architecture diagrams from representative subset | 90-95% |

## How It Works

### Core Algorithm: Pattern-Based Deduplication

Scale Reduction preserves graph uniqueness through a multi-phase approach:

#### Phase 1: Pattern Discovery
```cypher
// Identify all unique (source label, relationship type, target label) triplets
MATCH (a)-[r]->(b)
RETURN DISTINCT
    labels(a) AS sourceLabels,
    type(r) AS relType,
    labels(b) AS targetLabels,
    count(*) AS frequency
ORDER BY frequency DESC
```

#### Phase 2: Representative Selection
For each unique pattern, select N representative nodes (default N=2):
- Preserves diversity (different properties, locations, sizes)
- Maintains structural variety
- Ensures all edge cases are represented

#### Phase 3: Relationship Preservation
Add connecting nodes to maintain graph connectivity:
- Keep intermediate nodes on paths between representatives
- Preserve RBAC chains
- Maintain network connectivity

#### Phase 4: Validation
Verify all unique patterns are present in reduced graph:
- Compare pattern counts (original vs reduced)
- Ensure 100% pattern coverage
- Validate query compatibility

## Performance Targets

| Original Size | Reduced Size | Target Time | Reduction % |
|--------------|--------------|-------------|-------------|
| 1k resources | 100-150 | <10 seconds | 85-90% |
| 5k resources | 250-500 | <30 seconds | 90-95% |
| 40k resources | 2k-4k | <2 minutes | 90-95% |
| 100k+ resources | 5k-10k | <5 minutes | 90-95% |

## Usage

### Command Line Interface

```bash
# Basic usage - reduce to representative subset
azure-tenant-grapher scale-reduce \
    --tenant-id <tenant-id> \
    --representatives-per-pattern 2

# Advanced usage - custom reduction parameters
azure-tenant-grapher scale-reduce \
    --tenant-id <tenant-id> \
    --representatives-per-pattern 3 \
    --output-label "RepresentativeSubset" \
    --preserve-critical-paths true
```

### Python API

```python
from src.services.scale_reduction_service import ScaleReductionService
from src.utils.session_manager import Neo4jSessionManager

# Initialize service
session_manager = Neo4jSessionManager()
service = ScaleReductionService(
    session_manager,
    enable_performance_monitoring=True
)

# Perform reduction
result = await service.reduce_graph(
    tenant_id="your-tenant-id",
    representatives_per_pattern=2,
    preserve_critical_paths=True,
    progress_callback=lambda msg, cur, total: print(f"{msg}: {cur}/{total}")
)

# Access results
print(f"Original nodes: {result.original_node_count}")
print(f"Reduced nodes: {result.reduced_node_count}")
print(f"Reduction: {result.reduction_percentage:.1f}%")
print(f"Patterns preserved: {result.patterns_preserved}/{result.total_patterns}")
print(f"Duration: {result.duration_seconds:.1f}s")
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `representatives_per_pattern` | 2 | Number of representative nodes per unique pattern |
| `preserve_critical_paths` | True | Maintain RBAC and network connectivity paths |
| `output_label` | "Representative" | Label added to reduced graph nodes |
| `enable_performance_monitoring` | True | Track performance metrics |
| `validation_enabled` | True | Validate pattern preservation after reduction |

## Output Structure

### Result Object

```python
@dataclass
class ScaleReductionResult:
    """Results from scale reduction operation."""
    operation_id: str  # Unique operation identifier
    tenant_id: str
    original_node_count: int
    original_relationship_count: int
    reduced_node_count: int
    reduced_relationship_count: int
    reduction_percentage: float
    total_patterns: int  # Unique patterns in original graph
    patterns_preserved: int  # Patterns in reduced graph
    pattern_coverage_percentage: float  # Should be 100%
    duration_seconds: float
    performance_metrics: Optional[PerformanceMetrics] = None
```

### Graph Metadata

Reduced graph nodes include metadata:
```python
{
    "representative": True,  # Marks node as part of representative subset
    "scale_operation_id": "<uuid>",  # Links to reduction operation
    "pattern_type": "(Resource:VirtualMachine)-[:DEPENDS_ON]->(Resource:StorageAccount)",
    "original_count": 450,  # Number of this pattern in original graph
    "representative_index": 1  # Which representative (1 of N)
}
```

## Pattern Preservation Examples

### Example 1: Virtual Machine Dependencies

**Original Graph:**
```
450 VirtualMachine → StorageAccount relationships
```

**Reduced Graph (N=2):**
```
2 VirtualMachine → StorageAccount relationships
  - Representative 1: Basic VM with standard disk
  - Representative 2: Premium VM with managed disk
```

**Result:** 99.6% reduction while preserving both VM types

### Example 2: RBAC Chains

**Original Graph:**
```
120 Users → Group → Role → Subscription paths
```

**Reduced Graph (N=2):**
```
2 complete RBAC chains
  - Chain 1: Standard user permissions
  - Chain 2: Admin permissions
```

**Result:** 98.3% reduction with full RBAC pattern coverage

## Performance Optimizations

Scale Reduction leverages existing performance utilities:

### Adaptive Batch Processing
```python
from src.services.scale_performance import AdaptiveBatchSizer

# Automatically calculates optimal batch size for graph operations
batch_size = AdaptiveBatchSizer.calculate_batch_size(
    total_items=pattern_count,
    operation_type="read"
)
```

### Performance Monitoring
```python
from src.services.scale_performance import PerformanceMonitor

with PerformanceMonitor("scale_reduction") as monitor:
    # Reduction operations
    monitor.record_items(nodes_processed)
    monitor.record_batch()

# Comprehensive metrics tracked automatically
```

### Neo4j Query Optimization
```python
from src.services.scale_performance import QueryOptimizer

# Ensures indexes exist for fast pattern queries
QueryOptimizer.ensure_indexes(session)

# Optimized batch queries for pattern extraction
query = QueryOptimizer.get_batch_match_query(
    node_label="Resource",
    id_field="id"
)
```

## Validation

### Pattern Coverage Validation

After reduction, service validates 100% pattern coverage:

```python
# Automatic validation (enabled by default)
result = await service.reduce_graph(
    tenant_id=tenant_id,
    validation_enabled=True  # Default
)

if result.pattern_coverage_percentage < 100:
    raise ValueError(
        f"Pattern coverage {result.pattern_coverage_percentage}% < 100%. "
        f"Missing patterns: {result.total_patterns - result.patterns_preserved}"
    )
```

### Query Compatibility Validation

Reduced graph supports same query patterns as original:

```python
# Query pattern: Find VM dependencies
original_query = """
    MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
          -[:DEPENDS_ON]->(dep:Resource)
    RETURN vm.name, dep.type
"""

# Works on both original and reduced graph
# Reduced graph returns representative examples
```

## Integration with Existing Services

### Scale Up Integration
```python
# Create representative subset, then scale up
reduction_result = await reduction_service.reduce_graph(tenant_id)
scale_result = await scale_service.scale_up_template(
    tenant_id,
    scale_factor=8.0,
    source_filter=f"scale_operation_id = '{reduction_result.operation_id}'"
)
```

### Visualization Integration
```python
# Reduce large graph before visualization
await reduction_service.reduce_graph(tenant_id, representatives_per_pattern=1)

# Visualize reduced graph (fast rendering)
azure-tenant-grapher visualize --filter "representative = true"
```

### IaC Generation Integration
```python
# Generate IaC from representative subset
await reduction_service.reduce_graph(tenant_id)

# IaC generation uses reduced graph (faster, focused)
azure-tenant-grapher generate-iac \
    --format terraform \
    --filter "representative = true"
```

## Troubleshooting

### Issue: Pattern Coverage < 100%

**Symptom:** `pattern_coverage_percentage` is less than 100%

**Cause:** Some patterns have zero representatives selected

**Solution:**
```python
# Increase representatives_per_pattern
result = await service.reduce_graph(
    tenant_id=tenant_id,
    representatives_per_pattern=3  # Increase from default 2
)
```

### Issue: Reduction Percentage Too Low

**Symptom:** Reduced graph is > 10% of original

**Cause:** Too many representatives per pattern, or many unique patterns

**Solution:**
```python
# Reduce representatives_per_pattern
result = await service.reduce_graph(
    tenant_id=tenant_id,
    representatives_per_pattern=1  # Minimum for diversity
)
```

### Issue: Critical Paths Missing

**Symptom:** RBAC or network paths broken in reduced graph

**Cause:** `preserve_critical_paths=False`

**Solution:**
```python
# Enable critical path preservation
result = await service.reduce_graph(
    tenant_id=tenant_id,
    preserve_critical_paths=True  # Default, but be explicit
)
```

## Best Practices

### 1. Use for Analysis, Not Production

Reduced graphs are for analysis, testing, and visualization:
```python
# GOOD: Analyze patterns
reduced_graph = await service.reduce_graph(tenant_id)
analyze_patterns(reduced_graph)

# BAD: Generate production IaC from reduced graph
# (Original graph has full configuration details)
```

### 2. Adjust Representatives Based on Use Case

```python
# Testing: Minimum representatives
test_graph = await service.reduce_graph(
    tenant_id, representatives_per_pattern=1
)

# Analysis: Balanced representatives
analysis_graph = await service.reduce_graph(
    tenant_id, representatives_per_pattern=2  # Default
)

# Documentation: Maximum diversity
docs_graph = await service.reduce_graph(
    tenant_id, representatives_per_pattern=3
)
```

### 3. Monitor Performance Metrics

```python
result = await service.reduce_graph(
    tenant_id,
    enable_performance_monitoring=True
)

# Check if performance meets targets
if result.duration_seconds > 120:  # 2 minutes for 40k resources
    logger.warning(f"Reduction took {result.duration_seconds}s (target: 120s)")

if result.performance_metrics:
    print(result.performance_metrics)
```

### 4. Validate Pattern Preservation

```python
result = await service.reduce_graph(tenant_id)

# Always check coverage
assert result.pattern_coverage_percentage == 100, \
    f"Pattern coverage {result.pattern_coverage_percentage}% < 100%"

print(f"Successfully preserved {result.patterns_preserved} unique patterns")
```

## Architecture Decisions

### Why Pattern-Based Deduplication?

**Alternative Considered: Forest Fire Sampling**
- Pros: Proven algorithm, maintains statistical properties
- Cons: Random selection may miss unique patterns, no guarantee of 100% coverage

**Chosen: Pattern-Based Deduplication**
- Pros: Deterministic, guarantees 100% pattern coverage, explicit uniqueness preservation
- Cons: More complex implementation
- **Decision**: Pattern-based approach directly addresses "unique types in combination" requirement

### Why Representatives Per Pattern?

**Alternative Considered: Fixed Sample Size**
- Pros: Simpler, predictable output size
- Cons: May over-sample common patterns, under-sample rare ones

**Chosen: Representatives Per Pattern**
- Pros: Fair sampling across all patterns, configurable diversity
- Cons: Output size varies with pattern count
- **Decision**: Ensures rare patterns get equal representation as common ones

### Why Preserve Critical Paths?

**Alternative Considered: Pure Pattern Sampling**
- Pros: Simplest, fastest
- Cons: Breaks RBAC chains, network connectivity

**Chosen: Critical Path Preservation**
- Pros: Maintains graph queryability, preserves security/network analysis capability
- Cons: Slightly larger reduced graphs
- **Decision**: Enables practical use cases (security analysis, network topology)

## Related Documentation

- [Scale Operations Performance Guide](SCALE_PERFORMANCE_GUIDE.md)
- [Scale Operations Examples](SCALE_OPERATIONS_E2E_DEMONSTRATION.md)
- [Neo4j Schema Reference](NEO4J_SCHEMA_REFERENCE.md)
- [Graph Sampling Algorithms (Issue #427)](https://github.com/rysweet/azure-tenant-grapher/issues/427)

## API Reference

### ScaleReductionService

```python
class ScaleReductionService:
    """
    Service for extracting representative subsets from large graphs.

    Preserves structural complexity and uniqueness while achieving
    90-95% size reduction through pattern-based deduplication.
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        enable_performance_monitoring: bool = True,
        validation_enabled: bool = True
    ):
        """
        Initialize scale reduction service.

        Args:
            session_manager: Neo4j session manager
            enable_performance_monitoring: Track performance metrics
            validation_enabled: Validate pattern preservation after reduction
        """

    async def reduce_graph(
        self,
        tenant_id: str,
        representatives_per_pattern: int = 2,
        preserve_critical_paths: bool = True,
        output_label: str = "Representative",
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> ScaleReductionResult:
        """
        Reduce graph to representative subset.

        Args:
            tenant_id: Tenant ID to reduce
            representatives_per_pattern: Number of representatives per unique pattern
            preserve_critical_paths: Maintain RBAC and network paths
            output_label: Label for reduced graph nodes
            progress_callback: Progress reporting function

        Returns:
            ScaleReductionResult with statistics and metadata

        Raises:
            ValueError: If pattern coverage < 100%
            RuntimeError: If reduction fails
        """

    async def get_patterns(
        self,
        tenant_id: str
    ) -> List[GraphPattern]:
        """
        Get all unique patterns in graph.

        Returns list of (source labels, relationship type, target labels) triplets
        with frequency counts.
        """

    async def validate_reduction(
        self,
        operation_id: str
    ) -> ValidationResult:
        """
        Validate reduced graph preserves all patterns.

        Compares original and reduced graphs to ensure 100% pattern coverage.
        """
```

### GraphPattern

```python
@dataclass
class GraphPattern:
    """Unique graph pattern (source, relationship, target)."""
    source_labels: List[str]
    relationship_type: str
    target_labels: List[str]
    frequency: int  # Occurrences in original graph
    examples: List[str]  # Node IDs of representative examples
```

## Example Workflows

### Workflow 1: Analyze Large Tenant

```bash
# 1. Scan full tenant
azure-tenant-grapher scan --tenant-id <tenant-id>

# 2. Reduce to representative subset
azure-tenant-grapher scale-reduce \
    --tenant-id <tenant-id> \
    --representatives-per-pattern 2

# 3. Analyze reduced graph
azure-tenant-grapher visualize --filter "representative = true"
azure-tenant-grapher query --cypher "MATCH (n {representative: true}) RETURN count(n)"

# Result: Fast analysis on 2-4k nodes instead of 40k+
```

### Workflow 2: Create Test Fixture

```python
# 1. Reduce production graph
production_result = await service.reduce_graph(
    tenant_id="prod-tenant",
    representatives_per_pattern=1  # Minimal for testing
)

# 2. Export reduced graph
exporter = Neo4jExporter(session_manager)
test_fixture = await exporter.export_subgraph(
    filter=f"scale_operation_id = '{production_result.operation_id}'"
)

# 3. Import to test environment
await importer.import_graph(test_fixture, tenant_id="test-tenant")

# Result: Representative test graph with 90%+ reduction
```

### Workflow 3: Pattern Discovery

```python
# 1. Get all patterns
patterns = await service.get_patterns(tenant_id="large-tenant")

# 2. Analyze pattern distribution
common_patterns = [p for p in patterns if p.frequency > 100]
rare_patterns = [p for p in patterns if p.frequency < 10]

print(f"Found {len(patterns)} unique patterns")
print(f"Common: {len(common_patterns)}, Rare: {len(rare_patterns)}")

# 3. Reduce with appropriate sampling
result = await service.reduce_graph(
    tenant_id="large-tenant",
    representatives_per_pattern=3  # Extra diversity for analysis
)

# Result: Comprehensive pattern catalog with examples
```

## Contact

For questions or issues with scale reduction:
1. Check this guide first
2. Review [Issue #427](https://github.com/rysweet/azure-tenant-grapher/issues/427)
3. Run with `enable_performance_monitoring=True` and collect metrics
4. Open GitHub issue with:
   - Original graph size
   - Reduction parameters
   - Actual vs expected reduction
   - Performance metrics
