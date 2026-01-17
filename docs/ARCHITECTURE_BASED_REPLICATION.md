# Architecture-Based Tenant Replication

## Overview

Architecture-Based Replication is an advanced approach to tenant replication that operates at the **architectural pattern layer** rather than individual resources. Instead of copying resources one-by-one, this approach identifies and replicates connected architectural instances - groups of resources that work together to form coherent patterns.

**See Also**: [Integrated Architecture Replication](INTEGRATED_ARCHITECTURE_REPLICATION.md) for the complete integrated approach combining pattern-based discovery with configuration-coherent clustering.

## Complete Replication Workflow

The architecture-based replication workflow combines multiple techniques to ensure target tenants are statistically representative of source tenants:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE-BASED REPLICATION                    │
│                         Multi-Layer Workflow                         │
└─────────────────────────────────────────────────────────────────────┘

LAYER 1: ARCHITECTURE DISTRIBUTION ANALYSIS
┌─────────────────────────────────────────────────────────────────────┐
│  Source Tenant (114 instances, 856 resources, 7 patterns)           │
│                                                                      │
│  Compute Distribution Scores per Pattern:                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ VM Workload:        37.8% (45 instances) ──────────────────┐   │ │
│  │ Web Application:    24.1% (32 instances)                   │   │ │
│  │ Container Platform: 15.2% (18 instances)    ┌─────────────┐│   │ │
│  │ Data Platform:      12.3% (12 instances)    │ Metrics:    ││   │ │
│  │ Other Patterns:     10.6% (7 instances)     │ • Instance  ││   │ │
│  └─────────────────────────────────────────────│ • Resource  ││   │ │
│                                                 │ • Strength  ││   │ │
│                                                 │ • Centrality││   │ │
│                                                 └─────────────┘│   │ │
│                                                                │   │ │
└────────────────────────────────────────────────────────────────┼───┘ │
                                                                 │     │
                                                                 ▼     │
LAYER 2: PROPORTIONAL PATTERN SAMPLING                                │
┌─────────────────────────────────────────────────────────────────────┐
│  Target: 20 instances (proportional to distribution scores)         │
│                                                                      │
│  Allocation:                                                         │
│  • VM Workload:        8 instances  (20 × 0.378 = 7.56 → 8)        │
│  • Web Application:    5 instances  (20 × 0.241 = 4.82 → 5)        │
│  • Container Platform: 3 instances  (20 × 0.152 = 3.04 → 3)        │
│  • Data Platform:      2 instances  (20 × 0.123 = 2.46 → 2)        │
│  • Other Patterns:     2 instances  (20 × 0.106 = 2.12 → 2)        │
└────────────────────────────────────────────────────────────────┼────┘
                                                                 │
                                                                 ▼
LAYER 3: CONFIGURATION-COHERENT INSTANCE SELECTION
┌─────────────────────────────────────────────────────────────────────┐
│  For each pattern, select instances with similar configurations     │
│                                                                      │
│  Example: "VM Workload" pattern (need 8 instances)                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Source Config Distribution:                                    │ │
│  │ • Standard_D2s_v3 (westus2, prod):  60% → Select ~5 instances │ │
│  │ • Standard_D4s_v3 (eastus, dev):    30% → Select ~2 instances │ │
│  │ • Standard_B2s (westus2, test):     10% → Select ~1 instance  │ │
│  │                                                                │ │
│  │ Selection Method: Bag-of-words proportional sampling          │ │
│  └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┼────┘
                                                                 │
                                                                 ▼
LAYER 4: VALIDATION & TRACEABILITY
┌─────────────────────────────────────────────────────────────────────┐
│  Validate target matches source at multiple levels:                 │
│                                                                      │
│  Pattern Distribution:                                               │
│  ├─ Target distribution similarity: 0.987 (cosine)                  │
│  └─ Chi-squared p-value: 0.998 (statistically identical)            │
│                                                                      │
│  Configuration Distribution:                                         │
│  ├─ Distribution similarity: 0.998 (per resource type)              │
│  └─ KS statistic: 0.004 (negligible difference)                     │
│                                                                      │
│  Structural Similarity:                                              │
│  └─ Spectral distance: 0.167 (excellent match)                      │
│                                                                      │
│  Traceability Mapping:                                               │
│  └─ resource_mapping.json with complete selection chain             │
└─────────────────────────────────────────────────────────────────────┘

RESULT: Target tenant with 20 instances that statistically represents
        source tenant at pattern, configuration, and structural levels
```

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

#### ArchitecturePatternReplicator (`src/architecture_based_replicator.py`)

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
from src.architecture_based_replicator import ArchitecturePatternReplicator

# Initialize
replicator = ArchitecturePatternReplicator(
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

### 2. Architecture Distribution-Based Instance Selection

**NEW**: Uses weighted architecture distribution analysis to select instances proportionally, ensuring the target tenant reflects the architectural composition of the source tenant.

The replicator now operates in three layers:

#### Layer 1: Architecture Distribution Analysis

Compute distribution scores for each architectural pattern using the weighted pattern graph:

```python
# Example distribution scores
{
  "VM Workload": {
    "distribution_score": 37.8,
    "breakdown": {
      "instance_count": 39.5%,      # How many times pattern appears
      "resource_count": 42.3%,      # How many resources involved
      "connection_strength": 45.2%, # How tightly coupled
      "centrality": 24.9%           # How foundational
    }
  },
  "Web Application": {
    "distribution_score": 24.1,
    "breakdown": {...}
  },
  "Container Platform": {
    "distribution_score": 15.2,
    "breakdown": {...}
  }
}
```

**Composite Score Formula**:
```
distribution_score(pattern) =
  0.30 × instance_count_percentage +
  0.25 × resource_count_percentage +
  0.25 × connection_strength_percentage +
  0.20 × centrality_percentage
```

See [Architecture Distribution Analysis](ARCHITECTURAL_PATTERN_ANALYSIS.md#architecture-distribution-analysis) for complete details on metrics and formulas.

#### Layer 2: Proportional Pattern Sampling

Select architectural instances proportionally based on distribution scores:

```python
# Source tenant: 114 total instances
# Target replication: 20 instances

# Proportional selection based on distribution scores:
selected = {
  "VM Workload": 8 instances,        # 20 × 0.378 = 7.56 → 8
  "Web Application": 5 instances,    # 20 × 0.241 = 4.82 → 5
  "Container Platform": 3 instances, # 20 × 0.152 = 3.04 → 3
  "Data Platform": 2 instances,      # 20 × 0.123 = 2.46 → 2
  "Other Patterns": 2 instances      # 20 × 0.106 = 2.12 → 2
}
```

This ensures the target tenant maintains the same architectural balance as the source.

#### Layer 3: Configuration-Coherent Instance Selection

Within each pattern, select instances with similar configurations (location, SKU, tags):

```python
# For "VM Workload" pattern, select 8 instances
# Use configuration coherence to ensure instances have similar configs

virtualMachines_configs: {
  Standard_D2s_v3 (westus2, prod tags): 60%
  Standard_D4s_v3 (eastus, dev tags):   30%
  Standard_B2s (westus2, test tags):    10%
}

# Bag-of-words sampling maintains configuration distribution
# Result: ~5 D2s, ~2 D4s, ~1 B2s instances
```

#### Layer 4: Traceability and Validation

Track the complete selection chain:

```json
{
  "target_resource_id": {
    "source_resource_id": "/subscriptions/.../vm-prod-1",
    "architectural_pattern": "VM Workload",
    "selection_reason": "proportional_sampling",
    "selection_weight": 0.378,
    "configuration_fingerprint": {
      "sku": "Standard_D2s_v3",
      "location": "westus2",
      "tags": {"Environment": "Production"}
    },
    "configuration_match_quality": "exact"
  }
}
```

**Key Benefits**:
- ✅ **Architectural Fidelity**: Target tenant has same pattern distribution as source
- ✅ **Configuration Coherence**: Resources within instances have similar configs
- ✅ **Statistical Validity**: Selection maintains distributions at both pattern and config levels
- ✅ **Complete Traceability**: Every resource traceable through pattern → instance → config chain
- ✅ **Representative Sampling**: Target is statistically representative of source

### 3. Pattern Graph Matching

Ensures target graph structurally matches source:

```
Source Pattern Graph:          Target Pattern Graph:
- 52 resource types            - 16 resource types (subset)
- 188 edges                    - 38 edges
- Architectural patterns       - Same patterns, scaled down
- Config distributions         - Same distributions, scaled down
```

### 4. Missing Edge Visualization

Step 6 of the notebook highlights edges in the source graph that are missing in the target:

- **Red edges** (source): Relationships missing in target - need more instances
- **Gray edges** (source): Relationships captured in target
- **Green edges** (target): Successfully captured relationships

This provides immediate visual feedback on coverage gaps.

### 5. Spectral Distance Tracking

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

Replicates coherent groups of resources that work together, not isolated resources. Each instance represents a complete architectural pattern (e.g., VM + Disk + NIC + VNet).

### ✅ Proportional Pattern Distribution

**NEW**: Maintains the same architectural composition as the source tenant. If 40% of source instances are "VM Workload" and 25% are "Web Application", the target tenant will have the same proportions. This ensures:
- Common patterns are adequately represented
- Rare patterns aren't over-represented
- Architectural balance is preserved
- Cost estimates are accurate

### ✅ Configuration Coherence

**NEW**: Resources within each instance have similar configurations (location, SKU, tags), ensuring:
- Realistic resource groupings
- Configuration distributions match source tenant
- Deployment patterns are preserved
- Every resource is traceable to a source template

### ✅ Guaranteed Connectivity

Selected instances have relationships between resources, ensuring meaningful graphs. The spectral distance metric validates that connectivity patterns match the source.

### ✅ Natural Azure Organization

Respects how Azure organizes resources (ResourceGroups as logical containers). Instances are primarily grouped by ResourceGroup, then expanded with direct relationships.

### ✅ Structural Similarity

Uses spectral comparison to measure and optimize structural match to source. Spectral distance captures topological similarity beyond simple node/edge counts.

### ✅ Multi-Level Statistical Validation

**NEW**: Validates correctness at multiple levels:
- **Pattern level**: Distribution scores ensure architectural balance
- **Configuration level**: KS statistic and cosine similarity validate config distributions
- **Structural level**: Spectral distance confirms graph similarity
- **Overall**: Chi-squared tests validate target is statistically representative of source

### ✅ Complete Traceability

**NEW**: Every target resource is traceable through the complete selection chain:
```
Pattern (VM Workload, score: 37.8)
  ↓
Instance (rg-prod-123, 8 resources)
  ↓
Configuration (Standard_D2s_v3, westus2, prod tags)
  ↓
Source Resource (/subscriptions/.../vm-prod-123)
```

This enables audit trails, debugging, and understanding why each resource was selected.

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

### Configuration Distribution Similarity

```
Distribution similarity: 0.998
KS statistic: 0.004
```

Measures how well target configuration distribution matches source:
- **Distribution similarity**: Cosine similarity between distributions (1.0 = identical)
- **KS statistic**: Kolmogorov-Smirnov test (0.0 = identical, <0.05 = statistically similar)

Values > 0.95 indicate excellent match, maintaining representative sampling.

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

### Architecture Distribution-Based Replication Workflow

**NEW**: The replicator now uses a multi-layer selection strategy that combines architecture distribution analysis with configuration-coherent sampling:

#### Complete Workflow

```python
class ArchitecturePatternReplicator:

    def generate_replication_plan(
        self,
        target_instance_count: int,
        use_architecture_distribution: bool = True,
        use_configuration_coherence: bool = True
    ):
        """
        Generate replication plan using architecture distribution and config coherence.

        Workflow:
        1. Analyze source tenant patterns and compute distribution scores
        2. Select instances proportionally based on distribution
        3. Within each pattern, use configuration coherence
        4. Track complete selection chain for traceability
        """

        # Step 1: Compute architecture distribution
        if use_architecture_distribution:
            distribution_scores = self.compute_architecture_distribution(
                self.pattern_resources
            )

            # Step 2: Proportional pattern sampling
            pattern_targets = self._compute_pattern_targets(
                distribution_scores,
                target_instance_count
            )
            # Result: {"VM Workload": 8, "Web Application": 5, ...}

        else:
            # Fallback: uniform sampling across patterns
            pattern_targets = self._uniform_pattern_targets(
                self.pattern_resources,
                target_instance_count
            )

        # Step 3: Configuration-coherent instance selection
        selected_instances = []
        for pattern_name, target_n in pattern_targets.items():
            instances = self.pattern_resources[pattern_name]

            if use_configuration_coherence:
                # Select instances with similar configurations
                selected = self._select_config_coherent_instances(
                    instances,
                    target_n,
                    coherence_threshold=0.5
                )
            else:
                # Random selection without configuration awareness
                selected = random.sample(instances, target_n)

            selected_instances.append((pattern_name, selected))

        # Step 4: Build target pattern graph and track spectral distance
        target_graph = self._build_target_pattern_graph_from_instances(
            selected_instances
        )
        spectral_distance = self._compute_spectral_distance(
            self.source_pattern_graph,
            target_graph
        )

        # Step 5: Generate traceability mapping
        mapping = self._generate_resource_mapping(
            selected_instances,
            distribution_scores,
            pattern_targets
        )

        return selected_instances, spectral_distance, mapping

    def compute_architecture_distribution(
        self,
        patterns: Dict[str, List]
    ) -> Dict[str, float]:
        """
        Compute distribution scores for each architectural pattern.

        Combines four metrics:
        - Instance count (30%): How many times pattern appears
        - Resource count (25%): How many resources involved
        - Connection strength (25%): Sum of edge weights within pattern
        - Centrality (20%): Betweenness centrality of pattern nodes

        Returns:
            Dict mapping pattern_name to distribution_score (0-100)
        """
        pattern_graph = self.analyzer.get_pattern_graph()

        # Compute totals for normalization
        total_instances = sum(len(instances) for instances in patterns.values())
        total_resources = sum(
            sum(len(inst) for inst in instances)
            for instances in patterns.values()
        )
        total_strength = self._compute_total_connection_strength(pattern_graph)
        total_centrality = self._compute_total_centrality(pattern_graph)

        distribution = {}
        for pattern_name, instances in patterns.items():
            # Metric 1: Instance count percentage
            instance_pct = (len(instances) / total_instances) * 100

            # Metric 2: Resource count percentage
            resource_count = sum(len(inst) for inst in instances)
            resource_pct = (resource_count / total_resources) * 100

            # Metric 3: Connection strength percentage
            strength = self._compute_connection_strength(
                pattern_name, pattern_graph
            )
            strength_pct = (strength / total_strength) * 100

            # Metric 4: Centrality percentage
            centrality = self._compute_pattern_centrality(
                pattern_name, pattern_graph
            )
            centrality_pct = (centrality / total_centrality) * 100

            # Composite score with configurable weights
            distribution[pattern_name] = (
                0.30 * instance_pct +
                0.25 * resource_pct +
                0.25 * strength_pct +
                0.20 * centrality_pct
            )

        return distribution

    def _compute_pattern_targets(
        self,
        distribution_scores: Dict[str, float],
        target_count: int
    ) -> Dict[str, int]:
        """
        Calculate how many instances to select from each pattern.

        Uses distribution scores to maintain proportional representation.
        """
        total_score = sum(distribution_scores.values())

        pattern_targets = {}
        for pattern_name, score in distribution_scores.items():
            proportion = score / total_score
            pattern_targets[pattern_name] = int(target_count * proportion)

        # Adjust for rounding to ensure we hit target_count exactly
        total_selected = sum(pattern_targets.values())
        if total_selected < target_count:
            # Give extra instances to highest-scoring patterns
            sorted_patterns = sorted(
                distribution_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for pattern_name, _ in sorted_patterns:
                if total_selected >= target_count:
                    break
                pattern_targets[pattern_name] += 1
                total_selected += 1

        return pattern_targets
```

**Integration Points**:

1. **Architecture Distribution** (Layer 1) → Determines how many instances per pattern
2. **Configuration Coherence** (Layer 3) → Determines which specific instances within each pattern
3. **Spectral Distance** (Validation) → Confirms structural similarity
4. **Traceability Mapping** (Layer 4) → Links everything together

### Configuration-Based Resource Selection (Layer 3 Detail)

Within each pattern, the replicator uses configuration-aware sampling:

#### Step 1: Configuration Fingerprinting

For each resource in the source tenant, extract a configuration fingerprint:

```python
def extract_configuration_fingerprint(resource):
    return {
        "sku": extract_sku(resource),  # e.g., Standard_D2s_v3
        "location": resource.get("location"),
        "tags": resource.get("tags", {}),
        "key_properties": extract_key_properties(resource.get("properties", {}))
    }
```

#### Step 2: Distribution Analysis

Group resources by type and compute configuration distributions:

```python
# For Microsoft.Compute/virtualMachines:
{
  "Standard_D2s_v3 (westus2, prod)": 68 resources (59.6%),
  "Standard_D4s_v3 (eastus, dev)": 34 resources (29.8%),
  "Standard_B2s (westus2, test)": 12 resources (10.5%)
}
```

#### Step 3: Bag-of-Words Sampling

**Selection Mechanism**: Use a **bag-of-words model** to randomly sample resources from a weighted vector of configurations.

For each resource type, create a configuration bag (vector) where each configuration appears proportionally to its frequency in the source:

```python
# Example: Microsoft.Compute/virtualMachines configuration bag
# Source has: 68 D2s, 34 D4s, 12 B2s (total 114)

configuration_bag = [
    # Config 1 appears 68 times (59.6%)
    {"sku": "Standard_D2s_v3", "location": "westus2", "tags": {"Environment": "Production"}},
    {"sku": "Standard_D2s_v3", "location": "westus2", "tags": {"Environment": "Production"}},
    # ... repeated 68 times

    # Config 2 appears 34 times (29.8%)
    {"sku": "Standard_D4s_v3", "location": "eastus", "tags": {"Environment": "Development"}},
    # ... repeated 34 times

    # Config 3 appears 12 times (10.5%)
    {"sku": "Standard_B2s", "location": "westus2", "tags": {"Environment": "Test"}},
    # ... repeated 12 times
]

# To select 10 VMs, randomly sample 10 times WITH replacement
import random
selected_configs = random.choices(configuration_bag, k=10)

# Result (with high probability):
#   ~6 Standard_D2s_v3 (60%)
#   ~3 Standard_D4s_v3 (30%)
#   ~1 Standard_B2s (10%)
```

**Algorithm**:
1. **Build configuration bag** for each resource type:
   ```python
   bag = []
   for config, count in source_distribution.items():
       bag.extend([config] * count)  # Add config 'count' times
   ```

2. **Random sampling** when selecting resources:
   ```python
   for i in range(target_count):
       config = random.choice(bag)  # Pick random config from bag
       resource = find_resource_matching_config(config)
       selected_resources.append(resource)
   ```

3. **Track mappings** for each selected resource:
   ```python
   mappings[target_resource.id] = {
       "source_resource_id": resource.id,
       "configuration_fingerprint": config
   }
   ```

4. **Validate distribution** after selection using statistical tests

**Why Bag-of-Words?**
- ✅ **Naturally proportional**: Sampling is inherently weighted by frequency
- ✅ **Mathematically sound**: Multinomial sampling matches source distribution
- ✅ **Simple implementation**: Just `random.choices()` from weighted list
- ✅ **Statistically valid**: With sufficient samples, converges to source distribution

**Example Output**:
```
Source: [68 D2s, 34 D4s, 12 B2s] → Bag size: 114
Sample 10: [7 D2s, 2 D4s, 1 B2s] (distribution: 70%, 20%, 10%)
Sample 10: [6 D2s, 3 D4s, 1 B2s] (distribution: 60%, 30%, 10%)
Sample 10: [5 D2s, 4 D4s, 1 B2s] (distribution: 50%, 40%, 10%)

Average over many samples → [59.6% D2s, 29.8% D4s, 10.5% B2s] ✓
```

#### Step 4: Traceability

Generate `resource_mapping.json` linking every target resource to its source template:

```cypher
// Store mapping in separate file, not in Neo4j
// This allows mapping to be version-controlled and auditable
{
  "target_resource_id": {
    "source_resource_id": "...",
    "configuration_fingerprint": {...}
  }
}
```

**Benefits**:
- ✅ No database schema changes required
- ✅ Mapping file can be version-controlled
- ✅ Easy to audit and verify
- ✅ Can be regenerated without affecting graph

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
USE_CONFIG_DISTRIBUTION = True  # Enable configuration-based selection
```

## Output

### Files Generated (by notebook)

- Visualization PNGs (node overlap, side-by-side graphs, spectral evolution)
- Analysis summaries printed to console
- **`resource_mapping.json`** (NEW): Source-to-target resource mapping with configuration fingerprints

### Configuration Mapping File

The `resource_mapping.json` file provides complete traceability from target resources back to their source templates, including architecture distribution information:

```json
{
  "metadata": {
    "source_tenant_id": "abc-123",
    "target_tenant_id": "xyz-789",
    "generation_timestamp": "2025-01-13T10:30:00Z",
    "total_resources_mapped": 144,
    "resource_types": 28,
    "total_instances_selected": 20,
    "replication_strategy": "architecture_distribution_proportional"
  },
  "architecture_distribution": {
    "source_tenant_summary": {
      "total_instances": 114,
      "total_resources": 856,
      "total_patterns": 7
    },
    "pattern_distribution_scores": {
      "VM Workload": {
        "distribution_score": 37.8,
        "source_instances": 45,
        "target_instances": 8,
        "breakdown": {
          "instance_count_pct": 39.5,
          "resource_count_pct": 42.3,
          "connection_strength_pct": 45.2,
          "centrality_pct": 24.9
        }
      },
      "Web Application": {
        "distribution_score": 24.1,
        "source_instances": 32,
        "target_instances": 5,
        "breakdown": {
          "instance_count_pct": 28.1,
          "resource_count_pct": 22.3,
          "connection_strength_pct": 20.8,
          "centrality_pct": 19.4
        }
      },
      "Container Platform": {
        "distribution_score": 15.2,
        "source_instances": 18,
        "target_instances": 3,
        "breakdown": {...}
      }
    },
    "proportional_sampling_validation": {
      "target_distribution_match": 0.987,
      "chi_squared_statistic": 0.023,
      "p_value": 0.998,
      "interpretation": "Target distribution is statistically indistinguishable from source"
    }
  },
  "mappings": {
    "/subscriptions/target-sub/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-target-1": {
      "source_resource_id": "/subscriptions/source-sub/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-prod-123",
      "resource_type": "Microsoft.Compute/virtualMachines",
      "architectural_pattern": "VM Workload",
      "pattern_distribution_score": 37.8,
      "selection_reason": "proportional_sampling",
      "selection_weight": 0.378,
      "configuration_fingerprint": {
        "sku": "Standard_D2s_v3",
        "location": "westus2",
        "tags": {
          "Environment": "Production",
          "CostCenter": "Engineering"
        },
        "key_properties": {
          "hardwareProfile.vmSize": "Standard_D2s_v3",
          "storageProfile.osDisk.osType": "Linux",
          "storageProfile.imageReference.offer": "UbuntuServer"
        }
      },
      "configuration_match_quality": "exact",
      "configuration_similarity": 1.0,
      "resource_group": "rg-prod"
    }
  },
  "distribution_analysis": {
    "Microsoft.Compute/virtualMachines": {
      "source_distribution": {
        "Standard_D2s_v3": {"count": 68, "percentage": 59.6},
        "Standard_D4s_v3": {"count": 34, "percentage": 29.8},
        "Standard_B2s": {"count": 12, "percentage": 10.5}
      },
      "target_distribution": {
        "Standard_D2s_v3": {"count": 6, "percentage": 60.0},
        "Standard_D4s_v3": {"count": 3, "percentage": 30.0},
        "Standard_B2s": {"count": 1, "percentage": 10.0}
      },
      "distribution_similarity": 0.998,
      "ks_statistic": 0.004,
      "chi_squared": 0.012,
      "p_value": 0.997
    }
  }
}
```

**Key Fields**:

**Architecture Distribution Section** (NEW):
- **pattern_distribution_scores**: Distribution score and breakdown for each pattern
- **source_instances** / **target_instances**: Number of instances in source vs target per pattern
- **proportional_sampling_validation**: Statistical validation of proportional sampling
- **target_distribution_match**: Cosine similarity between source and target distributions (1.0 = perfect)

**Per-Resource Mapping**:
- **source_resource_id**: Original resource this target resource is based on
- **architectural_pattern**: Which pattern this resource belongs to (NEW)
- **pattern_distribution_score**: The distribution score of the parent pattern (NEW)
- **selection_reason**: Why this resource was selected (`proportional_sampling`, `architectural_instance`, etc.)
- **selection_weight**: Probability weight used in proportional sampling (pattern-level or config-level)
- **configuration_fingerprint**: Complete configuration snapshot (SKU, location, tags, properties)
- **configuration_match_quality**: `exact` | `partial` | `approximate`
- **configuration_similarity**: Numeric similarity score (0-1)

**Distribution Analysis Section**:
- **distribution_similarity**: Statistical measure of how well distributions match (1.0 = perfect)
- **ks_statistic**: Kolmogorov-Smirnov test statistic (lower = better match)
- **chi_squared**: Chi-squared test statistic
- **p_value**: P-value from chi-squared test (>0.95 indicates no significant difference)

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

- ✅ **Operates at the architectural pattern layer** - Identifies and replicates coherent architectural instances
- ✅ **Proportional pattern distribution** - Maintains architectural composition through distribution analysis
- ✅ **Configuration coherence** - Resources within instances have similar configurations
- ✅ **Multi-layer selection strategy**:
  - Layer 1: Architecture distribution analysis (pattern prevalence)
  - Layer 2: Proportional pattern sampling (how many instances per pattern)
  - Layer 3: Configuration-coherent instance selection (which specific instances)
  - Layer 4: Complete traceability and validation
- ✅ **Spectral graph comparison** - Measures structural similarity between source and target
- ✅ **Statistical validation** - Validates distributions match at both pattern and configuration levels
- ✅ **Respects Azure organization** - Uses ResourceGroup-based grouping
- ✅ **Rich visualization tools** - Interactive analysis and comparison
- ✅ **Complete traceability** - Every target resource traceable to source through pattern → instance → config chain

**Key Innovation**: By combining architecture distribution analysis with configuration-coherent sampling, the system ensures target tenants are **statistically representative** of source tenants at multiple levels - preserving both the architectural composition (which patterns and how many) and the configuration characteristics (what SKUs, locations, and settings).

This approach is ideal for:
- **Representative test environments** - Create scaled-down environments that accurately reflect production architecture and configuration
- **Cost modeling** - Estimate costs based on actual architectural and configuration distributions
- **Disaster recovery planning** - Understand architectural dependencies and priorities
- **Architecture analysis** - Discover and document tenant architectural patterns
- **Compliance validation** - Ensure target environments maintain required architectural standards
