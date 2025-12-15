# Architecture-Based Tenant Replication

## Overview

Architecture-Based Replication is an advanced approach to tenant replication that operates at the **architectural pattern layer** rather than individual resources. Instead of copying resources one-by-one, this approach identifies and replicates connected architectural instances - groups of resources that work together to form coherent patterns.

## Key Concepts

### Pattern Graph vs Instance Graph

- **Instance Resource Graph**: Individual Azure resources (vm-1, vm-2, disk-1, disk-2) as nodes with their relationships
- **Pattern Graph**: Type-level aggregation of the instance graph (virtualMachines, disks as nodes) showing how resource types relate
- **Architectural Instances**: Groups of resources sharing a common parent (ResourceGroup) that match a pattern's resource types

### How It Works

The system transforms instance graphs into pattern graphs through aggregation:

```
Instance Graph (Real Resources):          Pattern Graph (Types):
vm-1 ─USES_DISK→ disk-1                  virtualMachines ─USES_DISK→ disks
vm-2 ─USES_DISK→ disk-2                  (frequency: 2)
```

Resources are connected through:
1. **Shared Parents**: Resources in the same ResourceGroup form architectural instances
2. **Direct Edges**: Explicit relationships like VirtualNetwork→Subnet

### Spectral Comparison

The system uses spectral graph theory to measure structural similarity between source and target pattern graphs:

- **Laplacian Matrix**: Mathematical representation of graph structure
- **Eigenvalues**: Spectral decomposition capturing global structural properties
- **Spectral Distance**: Normalized distance between eigenvalue sets (lower = better match)
- **Goal**: Build target pattern graph that structurally matches source pattern graph

## Architecture

### Core Components

#### ArchitectureBasedReplicator (`src/architecture_based_replicator.py`)

Main class that orchestrates the architecture-based replication workflow.

**Key Methods:**

1. **`analyze_source_tenant()`**: Analyzes source tenant and identifies architectural patterns
   - Builds source pattern graph using ArchitecturalPatternAnalyzer
   - Detects which architectural patterns exist (Web App, VM Workload, etc.)
   - Finds connected instances by grouping resources sharing a ResourceGroup

2. **`_find_connected_pattern_instances()`**: Finds connected architectural instances
   - Primary: Groups resources by shared ResourceGroup (common parent)
   - Secondary: Merges resources connected by direct edges (e.g., VNet→Subnet)
   - Returns list of instances, where each instance is a list of connected resources

3. **`generate_replication_plan()`**: Generates replication plan through iterative selection
   - Selects N architectural instances from all available instances
   - Builds target pattern graph after each instance addition
   - Tracks spectral distance evolution
   - Returns selected instances and spectral history

4. **`_build_target_pattern_graph_from_instances()`**: Constructs pattern graph from instances
   - Queries Neo4j for all relationships involving selected resources
   - Aggregates relationships by type (same as ArchitecturalPatternAnalyzer)
   - Creates NetworkX graph with resource types as nodes

5. **`_compute_spectral_distance()`**: Measures structural similarity
   - Computes Laplacian matrices for both graphs
   - Calculates eigenvalues
   - Returns normalized spectral distance

## Usage

### Jupyter Notebook

The primary interface is the comprehensive Jupyter notebook:

```bash
jupyter notebook notebooks/architecture_based_replication.ipynb
```

**Notebook Structure:**

**Part 1: Pattern Detection & Instance Selection**
- Step 1: Analyze source tenant and detect patterns
- Step 2: Generate replication plan (select N instances)
- Step 3: Build target pattern graph from selected instances

**Part 2: Graph Comparison & Visualization**
- Step 4: Compare graph statistics (nodes, edges, density, degree)
- Step 5: Visualize node overlap (Venn diagram style)
- Step 6: Side-by-side graph visualization with missing edge highlighting
- Step 7: Edge type comparison table
- Step 8: Spectral distance evolution chart

### Python API

```python
from src.architecture_based_replicator import ArchitectureBasedReplicator

# Initialize
replicator = ArchitectureBasedReplicator(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="neo4j123"
)

# Analyze source tenant
analysis = replicator.analyze_source_tenant()
print(f"Detected {analysis['detected_patterns']} patterns")
print(f"Found {analysis['total_pattern_resources']} instances")

# Generate replication plan
selected_instances, spectral_history = replicator.generate_replication_plan(
    target_instance_count=10,  # Select 10 instances
    hops=2
)

# Build target pattern graph
target_graph = replicator._build_target_pattern_graph_from_instances(
    selected_instances
)

# Compute structural similarity
distance = replicator._compute_spectral_distance(
    replicator.source_pattern_graph,
    target_graph
)
print(f"Spectral distance: {distance:.4f}")
```

## Features

### 1. Connected Instance Detection

Finds groups of resources that actually work together:

```python
# Example: Web Application instance
instance = [
    {"id": "/subscriptions/.../sites/webapp-1", "type": "sites"},
    {"id": "/subscriptions/.../storageAccounts/storage1", "type": "storageAccounts"},
    {"id": "/subscriptions/.../components/insights1", "type": "components"}
]
# All three resources share the same ResourceGroup
```

### 2. Pattern Graph Matching

Ensures target graph structurally matches source:

```
Source Pattern Graph:          Target Pattern Graph:
- 52 resource types            - 16 resource types (subset)
- 188 edges                    - 38 edges
- Architectural patterns       - Same patterns, scaled down
```

### 3. Missing Edge Visualization

Step 6 of the notebook highlights edges in the source graph that are missing in the target:

- **Red edges** (source): Relationships missing in target - need more instances
- **Gray edges** (source): Relationships captured in target
- **Green edges** (target): Successfully captured relationships

This provides immediate visual feedback on coverage gaps.

### 4. Spectral Distance Tracking

Monitors how target graph evolves as instances are added:

```
Instance 1: Spectral distance = 0.1839
Instance 2: Spectral distance = 0.1772 (-3.6%)
...
Instance 10: Spectral distance = 0.1676 (-8.9%)
```

Lower distance = better structural match

## Advantages Over Resource-By-Resource Replication

### ✅ Realistic Architectural Units

Replicates coherent groups of resources that work together, not isolated resources.

### ✅ Guaranteed Connectivity

Selected instances have relationships between resources, ensuring meaningful graphs.

### ✅ Natural Azure Organization

Respects how Azure organizes resources (ResourceGroups as logical containers).

### ✅ Structural Similarity

Uses spectral comparison to measure and optimize structural match to source.

### ✅ Pattern Preservation

Maintains architectural patterns from source tenant in target.

## Metrics and Interpretation

### Node Coverage

```
Common Resource Types: 16/52 (30.8% of source)
```

Percentage of source resource types captured in target.

### Edge Coverage

```
Source edges: 188
Target edges: 38
Ratio: 20.2%
```

Percentage of relationship patterns preserved.

### Spectral Distance

```
Final distance: 0.1676
(Lower = Better, 0.0 = Perfect Match)
```

Overall structural similarity measure. Values < 0.2 indicate good match.

### Graph Density

```
Source density: 0.0714
Target density: 0.1562
```

Target density often higher (it's a connected subgraph). Similar values indicate similar connectivity patterns.

### Average Degree

```
Source avg degree: 7.23
Target avg degree: 4.75
```

Similar values indicate similar resource interconnection levels.

## Implementation Details

### ResourceGroup-Based Grouping

The primary method for finding architectural instances:

```cypher
MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
RETURN r.id, r.type, r.name, rg.id as resource_group_id
```

Resources sharing a ResourceGroup form an architectural instance.

### Direct Edge Merging

Secondary method for expanding instances:

```cypher
MATCH (source:Resource:Original)-[r]->(target:Resource:Original)
WHERE source.id IN $ids AND target.id IN $ids
RETURN source.id, target.id
```

Resources connected by explicit edges are merged even if in different ResourceGroups.

### Pattern Graph Construction

Aggregates instance relationships by type:

```cypher
MATCH (source)-[r]->(target)
WHERE (source:Resource:Original AND source.id IN $ids)
   OR (target:Resource:Original AND target.id IN $ids)
RETURN labels(source), source.type, type(r), labels(target), target.type
```

This creates the pattern graph through type-level aggregation.

## Prerequisites

1. **Scanned Azure Tenant**: Must have run `atg scan` to populate Neo4j
2. **Neo4j Database**: Running Neo4j instance with populated graph
3. **Python Dependencies**: numpy, scipy, networkx, matplotlib (for visualizations)

## Configuration

### Environment Variables

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### Notebook Parameters

```python
TARGET_INSTANCE_COUNT = 10  # Number of instances to select (None = all)
TOP_N = 20                  # Number of nodes to show in visualizations
```

## Output

### Files Generated (by notebook)

- Visualization PNGs (node overlap, side-by-side graphs, spectral evolution)
- Analysis summaries printed to console

### Data Structures

```python
# Selected instances
[
    ("Web Application", [list of connected resources]),
    ("VM Workload", [list of connected resources]),
    ...
]

# Spectral history
[0.1839, 0.1772, 0.1718, ..., 0.1676]  # Distance after each instance

# Target pattern graph
NetworkX MultiDiGraph with:
- Nodes: Resource types (e.g., "virtualMachines", "disks")
- Edges: Relationship types with frequency
```

## Related Documentation

- [Architectural Pattern Analysis](ARCHITECTURAL_PATTERN_ANALYSIS.md) - Pattern detection system
- [Neo4j Schema Reference](NEO4J_SCHEMA_REFERENCE.md) - Graph database schema
- [Dual Graph Architecture](DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt) - Original vs Abstracted nodes

## Future Enhancements

Potential improvements:

1. **Smart Instance Selection**: Optimize which instances to select based on spectral distance
2. **Interactive Visualization**: Web-based interactive graph explorer
3. **CLI Command**: Add `atg replicate-architecture` command
4. **Cross-Tenant Support**: Generate IaC from selected instances for deployment
5. **Pattern Weighting**: Prioritize certain architectural patterns over others

## Technical Background

### Spectral Graph Theory

Spectral methods analyze graphs through the eigenvalues and eigenvectors of their matrix representations. The Laplacian matrix encodes the graph structure, and its eigenvalues (spectrum) capture global structural properties.

**Why Spectral Distance?**
- Captures topological similarity beyond simple node/edge counts
- Robust to graph size differences
- Reflects connectivity patterns and structural organization
- Mathematically rigorous similarity measure

### Laplacian Matrix

For a graph with adjacency matrix A and degree matrix D:

```
L = D - A

where:
D[i,i] = degree of node i
A[i,j] = 1 if edge exists, 0 otherwise
```

Eigenvalues of L characterize the graph's structure.

## Examples

### Example 1: Small-Scale Replication

```python
# Select 5 instances for quick test
selected, history = replicator.generate_replication_plan(target_instance_count=5)

# Result:
# - 5 instances (2-4 resources each)
# - 8 resource types in target
# - 12 edges in target
# - Spectral distance: 0.2341
```

### Example 2: Large-Scale Replication

```python
# Select 50 instances for comprehensive replication
selected, history = replicator.generate_replication_plan(target_instance_count=50)

# Result:
# - 50 instances (2-6 resources each)
# - 35 resource types in target
# - 142 edges in target
# - Spectral distance: 0.0823 (excellent match)
```

### Example 3: Coverage Analysis

```python
# Analyze what's missing
target_graph = replicator._build_target_pattern_graph_from_instances(selected)

source_types = set(replicator.source_pattern_graph.nodes())
target_types = set(target_graph.nodes())
missing_types = source_types - target_types

print(f"Missing resource types: {missing_types}")
# Output: {'eventHubs', 'serviceBusNamespaces', 'dataFactories', ...}
```

## Troubleshooting

### No Instances Found

**Problem**: `Found 0 total architectural instances`

**Cause**: Resources not organized in ResourceGroups, or pattern types don't exist

**Solution**: Check that resources have CONTAINS relationships to ResourceGroups

### Only One Edge in Target Graph

**Problem**: Target graph has very few edges despite selecting multiple instances

**Cause**: Selected instances don't have relationships between their resources

**Solution**: Increase `TARGET_INSTANCE_COUNT` or verify instances have direct edges

### High Spectral Distance

**Problem**: Spectral distance remains high (> 0.3) even with many instances

**Cause**: Target is structurally very different from source

**Solution**: Select more diverse instances or check source graph structure

## Summary

Architecture-Based Replication provides a sophisticated approach to tenant replication that:

- ✅ Operates at the architectural pattern layer
- ✅ Selects connected groups of resources (instances)
- ✅ Uses spectral comparison for structural similarity
- ✅ Respects Azure's ResourceGroup organization model
- ✅ Provides rich visualization and analysis tools
- ✅ Generates realistic, deployable configurations

This approach is ideal for creating representative test environments, disaster recovery planning, or understanding tenant architecture through pattern analysis.
