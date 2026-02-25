# Architecture Replication Plan Logic

## Overview

The Architecture-Based Replication system replicates Azure tenants by operating at the **architecture layer** instead of individual resources. An "architecture" is a pattern grouping of related resource types (e.g., "Web Application" = sites + serverFarms + storageAccounts + components).

**Goal**: Build a target pattern graph that MATCHES the source pattern graph structure while preserving architectural coherence and configuration similarity.

## Core Concepts

### Architectural Patterns

Architectural patterns are detected groupings of resource types that work together:
- **Web Application**: App Service Plans + Web Apps + Storage Accounts + Application Insights
- **VM Workload**: Virtual Machines + Disks + NICs + NSGs + Public IPs
- **Container Platform**: AKS Clusters + Container Registries + Virtual Networks
- **Data Platform**: Cosmos DB + Storage Accounts + Key Vaults

### Pattern Instances

A pattern instance is a **connected subgraph** of actual resources matching a pattern:
- Example: "VM1 + its disk + its NIC + its NSG" (not "all VMs + all disks + all NICs")
- Resources are actually connected to each other through Azure relationships
- Each instance represents a coherent architectural unit

### Configuration Coherence

Resources within an instance have similar configurations:
- **Location**: Same Azure region (e.g., all in "eastus")
- **SKU/Tier**: Similar performance levels (e.g., all "Standard")
- **Tags**: Similar metadata patterns
- **Coherence Score**: Similarity threshold (default: 0.7 = 70% similar)

### Spectral Distance

Graph similarity metric comparing source and target pattern graphs:
- Uses graph Laplacian eigenvalues to measure structural similarity
- Lower distance = better structural match
- Ranges from 0.0 (identical) to ~2.0 (very different)

## Three-Phase Replication Process

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 1: ANALYSIS                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Connect to Neo4j                                  │   │
│  │ 2. Fetch all resource relationships                  │   │
│  │ 3. Build source pattern graph (type-level)           │   │
│  │ 4. Detect architectural patterns                     │   │
│  │ 5. Fetch pattern instances (connected subgraphs)     │   │
│  │ 6. Optional: Split by configuration coherence        │   │
│  │ 7. Optional: Include co-located orphaned resources   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 PHASE 2: PLAN GENERATION                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LAYER 1: Architecture Distribution Analysis          │   │
│  │   - Compute distribution scores for each pattern     │   │
│  │   - Weight by node count, edge count, centrality     │   │
│  │                                                       │   │
│  │ LAYER 2: Proportional Pattern Sampling               │   │
│  │   - Allocate target instances proportionally         │   │
│  │   - Pattern with 40% score → 40% of instances        │   │
│  │                                                       │   │
│  │ LAYER 3: Instance Selection (2 modes)                │   │
│  │   a) Hybrid Spectral-Guided (RECOMMENDED)            │   │
│  │      - Distribution adherence (60%)                  │   │
│  │      - Spectral optimization (40%)                   │   │
│  │   b) Random (fast, no bias)                          │   │
│  │                                                       │   │
│  │ FALLBACK: Greedy Spectral Matching                   │   │
│  │   - Original spectral distance-based selection       │   │
│  │   - Node coverage weight (0.0-1.0)                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                PHASE 3: GAP ANALYSIS                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Build target pattern graph                        │   │
│  │ 2. Identify orphaned nodes (not in any pattern)      │   │
│  │ 3. Find missing resource types                       │   │
│  │ 4. Suggest improvements                              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Phase 1: Source Tenant Analysis

### Method: `analyze_source_tenant()`

**Purpose**: Understand what architectural patterns exist in the source tenant and fetch their instances.

**Steps**:

1. **Connect to Neo4j** and fetch all resource relationships
   - Query: All resource nodes and their connections
   - Result: Raw relationship data

2. **Aggregate relationships** by resource type pairs
   - Group by: (source_type, relationship_type, target_type)
   - Result: Type-level connection patterns

3. **Build source pattern graph** (NetworkX MultiDiGraph)
   - Nodes: Resource types (e.g., "Microsoft.Compute/virtualMachines")
   - Edges: Relationships between types
   - Node attributes: Resource count
   - Result: Structural blueprint of source tenant

4. **Detect architectural patterns**
   - Uses `ArchitecturalPatternAnalyzer.detect_patterns()`
   - Identifies common groupings (Web App, VM, Container, etc.)
   - Computes completeness score for each pattern
   - Result: Dictionary of detected patterns

5. **Fetch pattern instances** (connected subgraphs)
   - Uses `PatternInstanceFinder` brick module
   - Two modes:
     - **Configuration-coherent**: Split by location, SKU, tags similarity
     - **ResourceGroup-based**: Simple RG grouping
   - Result: List of architectural instances per pattern

6. **Optional: Include orphaned resources**
   - Uses `OrphanedResourceManager` brick module
   - Finds resource types not in any pattern
   - Includes them if they co-locate with pattern resources
   - Result: Additional "orphaned_resources" pattern

**Key Parameters**:

- `use_configuration_coherence` (default: True)
  - Splits instances by configuration similarity
  - Ensures architecturally coherent groupings

- `coherence_threshold` (default: 0.7)
  - Minimum similarity for resources in same instance
  - Higher = tighter groupings, Lower = more variation

- `include_colocated_orphaned_resources` (default: True)
  - Preserves co-location relationships
  - Example: KeyVault in same RG as VMs

**Output**:

```python
{
    "total_relationships": 5000,
    "unique_patterns": 150,
    "resource_types": 45,
    "pattern_graph_edges": 120,
    "detected_patterns": 8,
    "total_pattern_resources": 2500,
    "configuration_coherence_enabled": True
}
```

## Phase 2: Replication Plan Generation

### Method: `generate_replication_plan()`

**Purpose**: Select architectural instances that best replicate the source tenant's structure.

### Strategy 1: Distribution-Based Selection (Recommended)

**Uses architecture distribution to proportionally sample patterns.**

#### LAYER 1: Architecture Distribution Analysis

**Goal**: Determine how important each pattern is to the overall structure.

**Process**:

```python
distribution_score = (
    node_weight * normalized_node_count +
    edge_weight * normalized_edge_count +
    centrality_weight * normalized_centrality
)
```

**Components**:

- **Node Count**: How many resource types in the pattern
- **Edge Count**: How many connections between those types
- **Centrality**: How central the pattern is in the graph (PageRank)

**Example**:

```python
{
    "Web Application": {
        "distribution_score": 0.40,  # 40% of total importance
        "source_instances": 100
    },
    "VM Workload": {
        "distribution_score": 0.35,  # 35% of total importance
        "source_instances": 75
    },
    "Container Platform": {
        "distribution_score": 0.25,  # 25% of total importance
        "source_instances": 50
    }
}
```

#### LAYER 2: Proportional Pattern Sampling

**Goal**: Allocate target instances proportionally to pattern importance.

**Process**:

```python
# If target_instance_count = 20
pattern_targets = {
    "Web Application": 8,      # 40% * 20 = 8
    "VM Workload": 7,           # 35% * 20 = 7
    "Container Platform": 5     # 25% * 20 = 5
}
```

**Special Case**: If `target_instance_count = None`, select ALL instances.

#### LAYER 3: Instance Selection

**Two modes available**:

##### Mode A: Hybrid Spectral-Guided (Default, Recommended)

**Combines distribution adherence with spectral optimization.**

**Scoring Function**:

```python
hybrid_score = (
    (1 - spectral_weight) * distribution_score +
    spectral_weight * spectral_improvement
)
```

**Parameters**:

- `spectral_weight` (default: 0.4)
  - 0.0 = pure distribution adherence
  - 0.4 = 60% distribution, 40% spectral (recommended)
  - 1.0 = pure spectral distance

**Process**:

1. Sample candidate instances from each pattern
2. For each candidate, compute:
   - Distribution score (how well it matches target proportion)
   - Spectral improvement (how much it reduces graph distance)
3. Select instance with highest hybrid score
4. Update target graph and repeat

**Configuration Sampling**:

- `max_config_samples` (default: 100)
  - Limits candidates per pattern for performance
  - Uses coverage or diversity sampling strategies

- `sampling_strategy` (default: "coverage")
  - "coverage": Greedy set cover for unique resource types
  - "diversity": Maximin diversity for config variation

**Benefits**:

- Balances distribution and structure
- Improves node coverage (captures more resource types)
- Fast and reliable

##### Mode B: Random Selection (Fast, No Bias)

**Simple random sampling when spectral guidance disabled.**

**Process**:

1. For each pattern, randomly select target number of instances
2. No optimization, pure randomness
3. Fast but may miss important structural patterns

**When to use**: Quick prototyping, testing, unbiased baselines

### Strategy 2: Greedy Spectral Matching (Fallback)

**Original algorithm when `use_architecture_distribution = False`.**

**Uses iterative greedy selection to minimize spectral distance.**

#### Process:

```python
while len(selected) < target_instance_count:
    best_instance = None
    best_score = -infinity

    for candidate in available_instances:
        # Build hypothetical target graph
        temp_target = build_graph(selected + [candidate])

        # Compute spectral distance
        distance = spectral_distance(source_graph, temp_target)

        # Compute new node coverage
        new_nodes = nodes_in_candidate_not_in_target

        # Hybrid score
        score = (
            node_coverage_weight * len(new_nodes) -
            (1 - node_coverage_weight) * distance
        )

        if score > best_score:
            best_instance = candidate
            best_score = score

    selected.append(best_instance)
```

**Parameters**:

- `node_coverage_weight` (default: random 0.0 or 1.0)
  - 0.0 = pure spectral distance (structure match)
  - 1.0 = pure node coverage (type diversity)
  - None = randomly choose 0.0 or 1.0 (exploration/exploitation)

- `include_orphaned` (default: True)
  - Include orphaned resource instances for better coverage

**Benefits**:

- Directly optimizes spectral distance
- Explicit node coverage control
- Good for small-scale replication

**Drawbacks**:

- Slower (O(n²) evaluations)
- No distribution guarantee
- Can be greedy and miss global optimum

### Comparison: Distribution vs Greedy

| Aspect | Distribution-Based | Greedy Spectral |
|--------|-------------------|-----------------|
| **Speed** | Fast (O(n)) | Slow (O(n²)) |
| **Distribution** | Guaranteed match | No guarantee |
| **Structure** | Hybrid optimization | Direct optimization |
| **Node Coverage** | Better (via sampling) | Good (via weight) |
| **Use Case** | Production, large-scale | Small-scale, research |

### Configuration-Based Plan (Alternative)

**Method**: `generate_configuration_based_plan()`

**Uses bag-of-words model for proportional configuration sampling.**

**When to use**: Focus on configuration distribution (location, SKU, tags) rather than architectural patterns.

**Process**:

1. **Analyze configuration distributions** in source tenant
2. **Build configuration bags** (weighted by frequency)
3. **Sample resources** using bag-of-words model
4. **Compute distribution similarity** (source vs target)

**Example**:

```python
# Source tenant: 60% eastus, 30% westus, 10% centralus
# Target tenant (10 VMs): 6 eastus, 3 westus, 1 centralus
# Distribution similarity: 0.95 (95% match)
```

**Benefits**:

- Preserves configuration proportions exactly
- Simple and fast
- Good for compliance/governance scenarios

**Drawbacks**:

- Ignores architectural patterns
- No structural optimization
- May miss important connections

## Phase 3: Gap Analysis and Improvement

### Method: `analyze_orphaned_nodes()`

**Purpose**: Identify what's missing from the target tenant.

**Process**:

1. **Identify orphaned nodes in source**
   - Resource types not covered by any detected pattern
   - Example: "Microsoft.Automation/automationAccounts"

2. **Detect patterns in target graph**
   - Analyze what patterns exist in target
   - May differ from source if selection was incomplete

3. **Identify orphaned nodes in target**
   - Compare source and target orphaned nodes

4. **Find missing resource types**
   - `missing_in_target = source_nodes - target_nodes`
   - Critical gap metric

5. **Suggest new patterns**
   - If orphaned nodes are common, suggest new pattern
   - Example: "Automation" pattern for orphaned automation resources

**Output**:

```python
{
    "source_orphaned": ["Microsoft.KeyVault/vaults", ...],
    "target_orphaned": ["Microsoft.KeyVault/vaults", ...],
    "missing_in_target": ["Microsoft.Automation/automationAccounts"],
    "suggested_patterns": [
        {
            "suggested_name": "Automation",
            "resource_types": ["Microsoft.Automation/automationAccounts", ...],
            "reason": "Common orphaned resources"
        }
    ],
    "source_orphaned_count": 12,
    "target_orphaned_count": 15,
    "missing_count": 5
}
```

### Method: `suggest_replication_improvements()`

**Purpose**: Recommend which pattern instances to select next.

**Process**:

1. **For each missing resource type**:
   - Find which detected patterns contain it
   - Count instances with that type
   - Sort by instance count (reliability)

2. **Generate recommendation**:
   - "Select more instances from 'Pattern X' to capture Type Y"

**Example**:

```python
[
    {
        "missing_type": "Microsoft.KeyVault/vaults",
        "available_patterns": [
            {
                "pattern_name": "Web Application",
                "instance_count": 45,
                "sample_instance": [...]
            },
            {
                "pattern_name": "VM Workload",
                "instance_count": 20,
                "sample_instance": [...]
            }
        ],
        "recommendation": "Select more instances from 'Web Application' pattern"
    }
]
```

## Brick Modules Used

The replicator uses several modular "brick" components:

| Module | Purpose |
|--------|---------|
| `ResourceTypeResolver` | Maps Azure resource types to canonical names |
| `ConfigurationSimilarity` | Computes similarity between resource configurations |
| `GraphStructureAnalyzer` | Analyzes graph structure and computes spectral distance |
| `PatternInstanceFinder` | Finds connected instances of architectural patterns |
| `OrphanedResourceManager` | Manages resources not in any pattern |
| `TargetGraphBuilder` | Builds target pattern graph from selected instances |
| `InstanceSelector` | Selects instances using various strategies |

## Key Design Decisions

### Why Architectural Patterns?

**Problem**: Individual resource replication doesn't preserve relationships.

**Solution**: Replicate connected groups (patterns) that work together.

**Benefits**:

- Preserves architectural integrity
- Maintains resource relationships
- Natural replication unit

### Why Configuration Coherence?

**Problem**: Resources in same pattern may have wildly different configs.

**Solution**: Split instances by configuration similarity.

**Benefits**:

- More realistic groupings
- Better configuration distribution
- Easier to deploy (homogeneous configs)

### Why Spectral Distance?

**Problem**: How to measure if two graphs are similar?

**Solution**: Graph Laplacian eigenvalues capture structural properties.

**Benefits**:

- Mathematically rigorous
- Captures global structure
- Efficient to compute

### Why Distribution-Based Sampling?

**Problem**: Greedy spectral matching is slow and unpredictable.

**Solution**: Proportional allocation based on pattern importance.

**Benefits**:

- Faster (O(n) vs O(n²))
- Predictable distribution
- Better node coverage

## Usage Patterns

### Basic Workflow

```python
# 1. Initialize
replicator = ArchitecturePatternReplicator(neo4j_uri, user, pwd)

# 2. Analyze source tenant
analysis = replicator.analyze_source_tenant(
    use_configuration_coherence=True,
    coherence_threshold=0.7,
    include_colocated_orphaned_resources=True
)

# 3. Generate replication plan
selected, distances, metadata = replicator.generate_replication_plan(
    target_instance_count=20,
    use_architecture_distribution=True,
    use_spectral_guidance=True,
    spectral_weight=0.4
)

# 4. Build target graph
target_graph = replicator.target_builder.build_from_instances(selected)

# 5. Analyze gaps
orphaned = replicator.analyze_orphaned_nodes(target_graph)

# 6. Get improvement suggestions
improvements = replicator.suggest_replication_improvements(orphaned)
```

### Advanced: Iterative Improvement

```python
# Start with small sample
selected, _, _ = replicator.generate_replication_plan(target_instance_count=10)

# Check coverage
target_graph = replicator.target_builder.build_from_instances(selected)
orphaned = replicator.analyze_orphaned_nodes(target_graph)

# Iteratively add instances to improve coverage
while orphaned['missing_count'] > 0:
    improvements = replicator.suggest_replication_improvements(orphaned)
    # Select more instances from suggested patterns
    # ...
```

### Advanced: Configuration-Based Replication

```python
# Use configuration distribution instead of patterns
selected, metadata = replicator.generate_configuration_based_plan(
    target_resource_counts={
        "Microsoft.Compute/virtualMachines": 5,
        "Microsoft.Storage/storageAccounts": 10
    },
    seed=42  # Reproducible
)

# Check distribution similarity
for resource_type, similarity in metadata['distribution_similarity'].items():
    print(f"{resource_type}: {similarity:.2%} similar")
```

## Parameters Reference

### `analyze_source_tenant()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_configuration_coherence` | bool | True | Split instances by config similarity |
| `coherence_threshold` | float | 0.7 | Min similarity for same instance (0.0-1.0) |
| `include_colocated_orphaned_resources` | bool | True | Include orphaned types in same RG |

### `generate_replication_plan()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_instance_count` | int \| None | None | Number of instances to select (None = all) |
| `include_orphaned_node_patterns` | bool | True | Include orphaned instances for coverage |
| `node_coverage_weight` | float \| None | None | Weight for node coverage (fallback mode) |
| `use_architecture_distribution` | bool | True | Use distribution-based allocation |
| `use_configuration_coherence` | bool | True | Cluster by config similarity during fetch |
| `use_spectral_guidance` | bool | True | Use hybrid scoring (distribution + spectral) |
| `spectral_weight` | float | 0.4 | Weight for spectral component (0.0-1.0) |
| `max_config_samples` | int | 100 | Max config samples per pattern |
| `sampling_strategy` | str | "coverage" | "coverage" or "diversity" |

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Analyze source tenant | O(E + V) | E = edges, V = vertices |
| Pattern detection | O(V²) | Pattern matching |
| Instance fetching | O(I × R) | I = instances, R = resources/instance |
| Distribution-based selection | O(N × P) | N = target count, P = patterns |
| Greedy spectral selection | O(N² × V²) | Very slow for large N |
| Spectral distance | O(V³) | Eigenvalue computation |

### Space Complexity

| Structure | Size | Notes |
|-----------|------|-------|
| Source pattern graph | O(V + E) | Type-level graph |
| Pattern resources | O(I × R) | All instances |
| Target graph | O(V + E) | Same as source |

### Scalability

| Scale | Instances | Resources | Time |
|-------|-----------|-----------|------|
| Small | 10-50 | 100-500 | Seconds |
| Medium | 50-200 | 500-2000 | Minutes |
| Large | 200-1000 | 2000-10000 | 5-15 min |
| Very Large | 1000+ | 10000+ | 15-30 min |

**Recommendations**:

- Use distribution-based selection for large-scale (1000+ instances)
- Use greedy spectral for small-scale (<50 instances) or research
- Enable `max_config_samples` for very large patterns (>500 instances)
- Use "coverage" sampling for faster execution

## Debugging and Monitoring

### Key Metrics

- **Spectral Distance**: Lower is better (0.0 = perfect match)
- **Node Coverage**: % of source types in target
- **Edge Coverage**: % of source edges in target
- **Distribution Error**: Deviation from target proportions

### Logging

```python
import logging
logging.basicConfig(level=logging.INFO)

# Shows:
# - Pattern detection results
# - Instance counts per pattern
# - Selection progress
# - Spectral distance evolution
# - Gap analysis results
```

### Common Issues

**Issue**: Spectral distance not decreasing

- **Cause**: Poor instance selection, missing key patterns
- **Fix**: Increase `spectral_weight`, check pattern detection

**Issue**: Low node coverage

- **Cause**: Missing orphaned resources, incomplete patterns
- **Fix**: Enable `include_colocated_orphaned_resources`, use "coverage" sampling

**Issue**: Slow execution

- **Cause**: Too many instances, greedy spectral mode
- **Fix**: Use distribution-based selection, reduce `max_config_samples`

**Issue**: Unbalanced distribution

- **Cause**: Greedy spectral mode ignores distribution
- **Fix**: Enable `use_architecture_distribution`

## Summary

The Architecture Replication Plan logic follows a three-phase process:

1. **ANALYSIS**: Understand source tenant structure and patterns
2. **PLANNING**: Select instances that best replicate structure
3. **VALIDATION**: Identify gaps and suggest improvements

**Key Innovation**: Operating at the architecture layer (patterns of related types) instead of individual resources preserves relationships and structural integrity.

**Recommended Settings** for most use cases:

```python
replicator.analyze_source_tenant(
    use_configuration_coherence=True,
    coherence_threshold=0.7,
    include_colocated_orphaned_resources=True
)

selected, distances, metadata = replicator.generate_replication_plan(
    target_instance_count=None,  # or 10-20% of source
    use_architecture_distribution=True,
    use_spectral_guidance=True,
    spectral_weight=0.4,
    max_config_samples=100,
    sampling_strategy="coverage"
)
```

This configuration provides the best balance of speed, accuracy, and structural fidelity for most replication scenarios.
