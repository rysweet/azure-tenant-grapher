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

## Future Enhancements

Potential improvements for future releases:

- Custom pattern definitions via YAML/JSON
- Pattern recommendations based on best practices
- Cost estimation per pattern
- Security scoring per pattern
- Comparison across multiple tenants
- Time-series analysis (pattern evolution)
- Interactive web-based visualizations
- Export to Azure Architecture diagrams
