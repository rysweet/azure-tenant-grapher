# Architectural Pattern Analysis

The Architectural Pattern Analyzer is a powerful feature that analyzes your Azure resource graph to identify common architectural patterns and visualize resource relationships.

## Overview

This feature examines the relationships between resources in your Neo4j graph database and identifies common Azure architectural patterns such as:

- **Web Applications**: App Service + Storage + Monitoring
- **Virtual Machine Workloads**: VMs + Networking + Storage + Security
- **Container Platforms**: AKS + Container Registry + Networking
- **Data Platforms**: Databases + Private Endpoints + Storage
- **Serverless Applications**: Function Apps + Storage + Key Vault + Monitoring
- **Data Analytics**: Data clusters + Workspaces + Storage + Event ingestion
- **Secure Workloads**: Key Vault + Private Endpoints + Private DNS + Networking
- **Managed Identity Pattern**: Resources using managed identities for authentication
- **Monitoring & Observability**: Application Insights + Log Analytics + Data Collection
- **Network Security**: NSGs + VNets + Subnets + Bastion

## Usage

### Basic Command

```bash
# Analyze patterns with visualizations
uv run atg analyze-patterns
```

### Command Options

```bash
# Skip visualizations (faster, doesn't require matplotlib/scipy)
uv run atg analyze-patterns --no-visualizations

# Specify custom output directory
uv run atg analyze-patterns -o my_analysis_results

# Include more nodes in visualization
uv run atg analyze-patterns --top-n-nodes 50

# Don't auto-start Neo4j container
uv run atg analyze-patterns --no-container
```

## Prerequisites

1. **Neo4j Database**: You must have scanned an Azure tenant and populated the Neo4j database first:
   ```bash
   uv run atg scan --tenant-id <YOUR_TENANT_ID>
   ```

2. **Dependencies** (for visualizations):
   ```bash
   uv pip install matplotlib scipy
   ```

   Note: These dependencies are included in the main `pyproject.toml` but can be skipped if you use `--no-visualizations`.

## Output Files

The analysis generates the following files in the output directory:

### 1. `resource_graph_aggregated.json`
Complete graph data in JSON format, suitable for import into other visualization tools (D3.js, Cytoscape, Gephi, etc.):

```json
{
  "nodes": [
    {
      "id": "virtualMachines",
      "label": "virtualMachines",
      "count": 1234
    }
  ],
  "edges": [
    {
      "source": "virtualMachines",
      "target": "disks",
      "relationship": "USES",
      "frequency": 856
    }
  ],
  "summary": {
    "total_nodes": 45,
    "total_edges": 234,
    "top_resource_types": [...],
    "aggregation_method": "By Azure resource type and node labels",
    "source_relationships": 12345
  }
}
```

### 2. `analysis_summary.json`
Human-readable summary with pattern detection results:

```json
{
  "total_relationships": 12345,
  "unique_patterns": 234,
  "resource_types": 45,
  "graph_edges": 234,
  "detected_patterns": 8,
  "top_resource_types": [...],
  "patterns": {
    "Web Application": {
      "completeness": 100.0,
      "matched_resources": ["sites", "serverFarms", "storageAccounts", "components"],
      "missing_resources": [],
      "connection_count": 456
    }
  }
}
```

### 3. `architectural_patterns_overview.png`
Visual graph showing:
- **Nodes**: Resource types (sized by connection frequency)
- **Edges**: Relationships between resources
  - Thick colored edges: Intra-pattern connections (within same architectural pattern)
  - Thin gray edges: Cross-pattern connections (between different patterns)
- **Dashed boundaries**: Pattern groupings (convex hulls around pattern resources)
- **Legend**: Shows detected patterns with completeness percentages

## Understanding the Analysis

### Pattern Detection

The analyzer detects patterns based on:
1. **Resource presence**: Which resource types exist in your environment
2. **Resource connections**: How resources are related (USES, DEPENDS_ON, CONNECTED_TO, etc.)
3. **Pattern completeness**: Percentage of expected resources present

Example:
- **Web Application pattern** expects: `sites`, `serverFarms`, `storageAccounts`, `components`
- If your environment has 3 out of 4 resources, the pattern is 75% complete
- The analyzer shows how many connections exist between these resources

### Relationship Aggregation

The analyzer aggregates individual resource relationships by type:

**Before aggregation** (individual resources):
- vm-abc123 → disk-def456
- vm-xyz789 → disk-ghi012
- vm-mno345 → disk-pqr678

**After aggregation** (by resource type):
- virtualMachines → disks (frequency: 3)

This makes it easy to understand overall patterns without being overwhelmed by individual resources.

### Top Resource Types

The analysis ranks resource types by "connection frequency" - how often they appear in relationships. High-frequency resources are typically:
- Core infrastructure (virtual networks, resource groups)
- Shared services (monitoring, logging)
- Central security resources (key vaults, identity)

## Example Output

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 Azure Architectural Pattern Analysis                        │
│ Output directory: outputs/pattern_analysis_20250101_120000     │
└─────────────────────────────────────────────────────────────────┘

⚙️  Analyzing resource graph...

✅ Analysis Complete!

                 Analysis Statistics
┌─────────────────────┬────────────────────────────┐
│ Metric              │ Value                      │
├─────────────────────┼────────────────────────────┤
│ Total Relationships │ 12,345                     │
│ Unique Patterns     │ 234                        │
│ Resource Types      │ 45                         │
│ Graph Edges         │ 234                        │
│ Detected Patterns   │ 8                          │
└─────────────────────┴────────────────────────────┘

              Top 10 Resource Types
┌────────────────────────┬──────────────────────┐
│ Resource Type          │ Connection Count     │
├────────────────────────┼──────────────────────┤
│ virtualNetworks        │ 2,345               │
│ resourceGroups         │ 1,890               │
│ virtualMachines        │ 1,234               │
│ storageAccounts        │ 987                 │
│ networkInterfaces      │ 856                 │
└────────────────────────┴──────────────────────┘

         Detected Architectural Patterns
┌──────────────────────┬──────────┬────────────┬─────────┐
│ Pattern              │ Complete │ Matched    │ Connect │
├──────────────────────┼──────────┼────────────┼─────────┤
│ Web Application      │ 100%     │ sites, ... │ 456     │
│ VM Workload          │ 100%     │ vms, ...   │ 1234    │
│ Container Platform   │ 75%      │ aks, ...   │ 234     │
└──────────────────────┴──────────┴────────────┴─────────┘

📁 Output Files:
  • JSON Export: outputs/.../resource_graph_aggregated.json
  • Summary Report: outputs/.../analysis_summary.json
  • Visualizations:
    - outputs/.../architectural_patterns_overview.png

✨ Analysis complete! Results saved to: outputs/pattern_analysis_20250101_120000
```

## Integration with Other Tools

The JSON output can be imported into various graph visualization tools:

### D3.js
```javascript
fetch('resource_graph_aggregated.json')
  .then(r => r.json())
  .then(data => {
    // data.nodes, data.edges are ready for D3
  });
```

### Cytoscape
```javascript
cytoscape({
  elements: {
    nodes: data.nodes.map(n => ({ data: n })),
    edges: data.edges.map(e => ({ data: e }))
  }
});
```

### NetworkX (Python)
```python
import json
import networkx as nx

with open('resource_graph_aggregated.json') as f:
    data = json.load(f)

G = nx.DiGraph()
for node in data['nodes']:
    G.add_node(node['id'], **node)
for edge in data['edges']:
    G.add_edge(edge['source'], edge['target'], **edge)
```

## Use Cases

1. **Architecture Review**: Quickly understand what architectural patterns exist in your environment
2. **Cost Optimization**: Identify over-provisioned or under-utilized patterns
3. **Security Audit**: Find patterns that should have security features (Key Vault, Private Endpoints)
4. **Compliance**: Ensure required patterns are deployed consistently
5. **Documentation**: Auto-generate architecture diagrams for documentation
6. **Migration Planning**: Understand dependencies before migrating resources

## Troubleshooting

### "Missing Dependencies" Error

If you see an error about missing matplotlib or scipy:

```bash
# Install visualization dependencies
uv pip install matplotlib scipy

# OR run without visualizations
uv run atg analyze-patterns --no-visualizations
```

### "No relationships found"

Ensure you've scanned a tenant first:
```bash
uv run atg scan --tenant-id <TENANT_ID>
```

### Empty Pattern Detection

If no patterns are detected:
- Your environment may use custom or unique architectures
- Resource relationships may not be established (check relationship rules)
- Try scanning with more resources (remove `--resource-limit`)

## Architecture

The pattern analyzer is implemented in `src/architectural_pattern_analyzer.py` and consists of:

1. **ArchitecturalPatternAnalyzer**: Main class that orchestrates analysis
2. **Pattern Definitions**: Dictionary of known architectural patterns
3. **Relationship Aggregation**: Groups individual relationships by resource type
4. **NetworkX Graph Building**: Constructs graph for analysis and visualization
5. **Pattern Detection**: Matches graph structure against known patterns
6. **Visualization**: Generates matplotlib plots with pattern overlays

## Configuration Analysis

In addition to structural pattern detection, the analyzer can examine resource configurations to understand the distribution of different configuration profiles within each resource type.

### Configuration Fingerprinting

For each resource type, the analyzer extracts a **configuration fingerprint** consisting of:

1. **SKU/Size**: Resource tier and size (e.g., `Standard_D2s_v3` for VMs, `Standard_LRS` for storage)
2. **Properties**: Key configuration properties from the `properties` JSON field
3. **Tags**: Resource tags (key-value pairs)
4. **Location**: Azure region where the resource is deployed

### Configuration Distribution

The analyzer computes the distribution of configurations within each resource type:

```json
{
  "virtualMachines": {
    "total_count": 114,
    "configurations": [
      {
        "fingerprint": {
          "sku": "Standard_D2s_v3",
          "location": "westus2",
          "tags": {"Environment": "Production"},
          "properties": {
            "hardwareProfile.vmSize": "Standard_D2s_v3",
            "storageProfile.osDisk.osType": "Linux"
          }
        },
        "count": 68,
        "percentage": 59.6,
        "sample_resources": [
          "/subscriptions/.../virtualMachines/vm-1",
          "/subscriptions/.../virtualMachines/vm-2"
        ]
      },
      {
        "fingerprint": {
          "sku": "Standard_D4s_v3",
          "location": "eastus",
          "tags": {"Environment": "Development"},
          "properties": {
            "hardwareProfile.vmSize": "Standard_D4s_v3",
            "storageProfile.osDisk.osType": "Windows"
          }
        },
        "count": 34,
        "percentage": 29.8,
        "sample_resources": [...]
      }
    ]
  }
}
```

### Use Cases

**Configuration-Based Replication**: When replicating resources to a target tenant, sample resources proportionally to maintain the same configuration distribution. This ensures the target tenant is representative of the source tenant's actual deployment patterns.

**Cost Analysis**: Identify which configurations are most common and estimate costs based on actual usage patterns.

**Compliance Auditing**: Verify that resources follow approved configuration standards (e.g., all VMs use approved SKUs).

**Optimization Opportunities**: Find under-utilized configurations that could be downsized.

## Architecture Distribution Analysis

When analyzing a tenant, it's important to understand not just **what architectural patterns exist**, but **how prevalent each pattern is** in the environment. The Architecture Distribution Analysis uses the weighted resource pattern graph to quantify the distribution of architectural patterns across the tenant.

### Weighted Pattern Graph

The **weighted pattern graph** is the aggregated type-level graph where:

- **Nodes** represent Azure resource types (e.g., `virtualMachines`, `storageAccounts`)
- **Edges** represent relationships between resource types (e.g., `virtualMachines → disks`)
- **Edge weights** represent the frequency of that relationship (how many individual instances exist)
- **Node weights** represent the total connection count for that resource type

Example:
```
virtualMachines → disks (weight: 1,234)
virtualMachines → networkInterfaces (weight: 1,234)
storageAccounts → containers (weight: 4,567)
```

### Distribution Metrics

The architecture distribution can be quantified using multiple metrics:

#### 1. Instance Count Distribution

**Definition**: Count how many distinct architectural instances exist for each pattern.

**Method**:
- For each detected pattern, count the number of ResourceGroups (or clusters) that contain that pattern
- Express as percentages of total instances

**Example**:
```json
{
  "VM Workload": {
    "instance_count": 45,
    "percentage": 39.5
  },
  "Web Application": {
    "instance_count": 32,
    "percentage": 28.1
  },
  "Container Platform": {
    "instance_count": 18,
    "percentage": 15.8
  }
}
```

**Use Case**: Understanding which architectural patterns are most commonly deployed in the tenant.

#### 2. Resource Count Distribution

**Definition**: Count the total number of resources involved in each pattern.

**Method**:
- For each pattern instance, sum up all resources that match the pattern
- Express as percentages of total resources

**Example**:
```json
{
  "VM Workload": {
    "resource_count": 2,345,
    "percentage": 42.3
  },
  "Web Application": {
    "resource_count": 1,234,
    "percentage": 22.3
  }
}
```

**Use Case**: Understanding which patterns consume the most resources (cost proxy).

#### 3. Connection Strength Distribution

**Definition**: Sum the edge weights for all relationships within each pattern.

**Method**:
- For each pattern, sum up the frequency of all intra-pattern relationships
- Express as percentages of total connection strength

**Formula**:
```
connection_strength(pattern) = Σ edge_weight(e) for all edges e within pattern
```

**Example**:
```json
{
  "VM Workload": {
    "connection_strength": 8,934,
    "percentage": 45.2,
    "interpretation": "VM Workload has the strongest internal coupling"
  },
  "Web Application": {
    "connection_strength": 3,456,
    "percentage": 17.5
  }
}
```

**Use Case**: Understanding which patterns have the tightest resource coupling (migration complexity).

#### 4. Node Centrality Distribution

**Definition**: Measure how "central" each pattern's resource types are in the overall graph.

**Method**:
- Compute betweenness centrality for each resource type node
- For each pattern, sum the centrality scores of all its resource types
- Express as percentages

**Formula**:
```
centrality_score(pattern) = Σ betweenness_centrality(node) for all nodes in pattern
```

**Example**:
```json
{
  "Network Security": {
    "centrality_score": 0.85,
    "percentage": 34.2,
    "interpretation": "Network Security resources are central to the architecture"
  },
  "VM Workload": {
    "centrality_score": 0.62,
    "percentage": 24.9
  }
}
```

**Use Case**: Understanding which patterns are foundational vs peripheral to the tenant architecture.

### Composite Distribution Score

To get a holistic view of pattern prevalence, combine multiple metrics into a **composite distribution score**:

**Formula**:
```
distribution_score(pattern) =
  w1 × instance_count_percentage +
  w2 × resource_count_percentage +
  w3 × connection_strength_percentage +
  w4 × centrality_percentage
```

**Default Weights**:
```python
{
  "instance_count": 0.30,      # How many times pattern appears
  "resource_count": 0.25,      # How many resources involved
  "connection_strength": 0.25, # How tightly coupled
  "centrality": 0.20           # How foundational to architecture
}
```

**Example Output**:
```json
{
  "VM Workload": {
    "distribution_score": 37.8,
    "rank": 1,
    "breakdown": {
      "instance_count": 39.5,
      "resource_count": 42.3,
      "connection_strength": 45.2,
      "centrality": 24.9
    }
  },
  "Web Application": {
    "distribution_score": 24.1,
    "rank": 2
  }
}
```

### Proportional Sampling Strategy

Using architecture distribution analysis, we can implement **proportional sampling** for tenant replication:

**Goal**: When selecting N instances to replicate to a target tenant, select them proportionally to maintain the same architectural distribution as the source tenant.

**Algorithm**:
```python
def proportional_sample(patterns, target_count, distribution_scores):
    """
    Sample architectural instances proportionally based on distribution scores.

    Args:
        patterns: Dict of pattern_name -> list of instances
        target_count: Total number of instances to select
        distribution_scores: Dict of pattern_name -> distribution_score

    Returns:
        Dict of pattern_name -> selected instances
    """
    total_score = sum(distribution_scores.values())

    # Calculate target instance count per pattern
    pattern_targets = {}
    for pattern_name, score in distribution_scores.items():
        proportion = score / total_score
        pattern_targets[pattern_name] = int(target_count * proportion)

    # Adjust for rounding (ensure we hit target_count exactly)
    total_selected = sum(pattern_targets.values())
    if total_selected < target_count:
        # Give extra instances to highest-scoring patterns
        sorted_patterns = sorted(distribution_scores.items(),
                                key=lambda x: x[1], reverse=True)
        for pattern_name, _ in sorted_patterns:
            if total_selected >= target_count:
                break
            pattern_targets[pattern_name] += 1
            total_selected += 1

    # Sample instances from each pattern
    selected = {}
    for pattern_name, target_n in pattern_targets.items():
        instances = patterns[pattern_name]
        if len(instances) <= target_n:
            # Select all instances if we don't have enough
            selected[pattern_name] = instances
        else:
            # Random sample proportionally
            selected[pattern_name] = random.sample(instances, target_n)

    return selected
```

**Example**:

Source tenant has:
- VM Workload: 45 instances (37.8% distribution score)
- Web Application: 32 instances (24.1% distribution score)
- Container Platform: 18 instances (15.2% distribution score)
- Data Platform: 12 instances (12.3% distribution score)
- Other patterns: 7 instances (10.6% distribution score)

Target replication: 20 instances

Proportional selection:
- VM Workload: 8 instances (20 × 0.378 = 7.56 → 8)
- Web Application: 5 instances (20 × 0.241 = 4.82 → 5)
- Container Platform: 3 instances (20 × 0.152 = 3.04 → 3)
- Data Platform: 2 instances (20 × 0.123 = 2.46 → 2)
- Other patterns: 2 instances (20 × 0.106 = 2.12 → 2)

### Implementation Details

The architecture distribution analysis is implemented in `src/architecture_based_replicator.py`:

```python
class ArchitecturePatternReplicator:

    def compute_architecture_distribution(self, patterns: Dict[str, List]) -> Dict[str, float]:
        """
        Compute distribution scores for each architectural pattern.

        Returns:
            Dict mapping pattern_name to distribution_score (0-100)
        """
        # Get weighted pattern graph from analyzer
        pattern_graph = self.analyzer.get_pattern_graph()

        distribution = {}

        for pattern_name, instances in patterns.items():
            # Metric 1: Instance count
            instance_percentage = (len(instances) / total_instances) * 100

            # Metric 2: Resource count
            resource_count = sum(len(inst) for inst in instances)
            resource_percentage = (resource_count / total_resources) * 100

            # Metric 3: Connection strength
            connection_strength = self._compute_connection_strength(
                pattern_name, pattern_graph
            )
            strength_percentage = (connection_strength / total_strength) * 100

            # Metric 4: Node centrality
            centrality = self._compute_pattern_centrality(
                pattern_name, pattern_graph
            )
            centrality_percentage = (centrality / total_centrality) * 100

            # Composite score
            distribution[pattern_name] = (
                0.30 * instance_percentage +
                0.25 * resource_percentage +
                0.25 * strength_percentage +
                0.20 * centrality_percentage
            )

        return distribution

    def generate_replication_plan(
        self,
        target_instance_count: int,
        use_proportional_sampling: bool = True
    ):
        """
        Generate replication plan using architecture distribution.
        """
        if use_proportional_sampling:
            distribution = self.compute_architecture_distribution(
                self.pattern_resources
            )
            selected = self._proportional_sample(
                self.pattern_resources,
                target_instance_count,
                distribution
            )
        else:
            # Fallback to uniform sampling
            selected = self._uniform_sample(
                self.pattern_resources,
                target_instance_count
            )

        return selected
```

### Use Cases for Architecture Distribution

1. **Representative Tenant Replication**
   - Create target tenants that accurately reflect source tenant architecture
   - Ensure common patterns are represented proportionally
   - Avoid over-representing rare patterns

2. **Cost Modeling**
   - Estimate costs based on actual architectural distribution
   - Identify which patterns drive the most cost
   - Model cost impact of architecture changes

3. **Architecture Standardization**
   - Identify which patterns should be standardized
   - Prioritize standardization efforts on high-distribution patterns
   - Track architectural drift over time

4. **Migration Planning**
   - Prioritize migration waves based on pattern prevalence
   - Estimate migration effort based on pattern distribution
   - Identify dependencies between high-prevalence patterns

5. **Security and Compliance**
   - Focus security reviews on high-distribution patterns
   - Ensure compliance controls cover prevalent architectures
   - Risk assessment weighted by pattern distribution

6. **Capacity Planning**
   - Forecast resource needs based on pattern growth
   - Understand which patterns drive resource consumption
   - Plan quota increases based on architectural trends

### Visualization

The architecture distribution can be visualized using:

1. **Pie Chart**: Show percentage breakdown of patterns
2. **Bar Chart**: Compare distribution scores across patterns
3. **Treemap**: Show hierarchical distribution (pattern → instances → resources)
4. **Sankey Diagram**: Show flow from patterns to resource types
5. **Radar Chart**: Compare patterns across multiple metrics simultaneously

Example output saved to `architecture_distribution.png`:

```
┌─────────────────────────────────────────────────┐
│  Architecture Distribution Analysis             │
├─────────────────────────────────────────────────┤
│                                                 │
│  VM Workload        ████████████████  37.8%    │
│  Web Application    ██████████        24.1%    │
│  Container Platform ██████            15.2%    │
│  Data Platform      ████              12.3%    │
│  Other Patterns     ███               10.6%    │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Future Enhancements

Potential improvements for future releases:

- Custom pattern definitions via YAML/JSON
- Pattern recommendations based on best practices
- Cost estimation per pattern (using configuration distributions)
- Security scoring per pattern
- Configuration drift detection across tenants
- Comparison across multiple tenants
- Time-series analysis (pattern evolution)
- Interactive web-based visualizations
- Export to Azure Architecture diagrams
