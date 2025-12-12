# Azure Tenant Grapher Notebooks

This directory contains Jupyter notebooks for exploring and analyzing Azure tenant data.

## 📓 Available Notebooks

### `explore_entities.ipynb` - Architectural Pattern Analysis

**Updated to use `ArchitecturalPatternAnalyzer`!**

This notebook demonstrates interactive exploration and analysis of your Azure tenant graph, including:

#### Part 1: Basic Entity Exploration
- Connect to Neo4j database
- List all entity types (node labels) and counts
- Explore entity details with examples
- View relationship types and examples
- Query specific resource types (VMs, Storage, Resource Groups)
- Explore resource relationships

#### Part 2: Architectural Pattern Analysis
- **Uses `ArchitecturalPatternAnalyzer` class** from `src/architectural_pattern_analyzer.py`
- Fetches and aggregates all resource relationships
- Builds NetworkX graphs with resource type aggregation
- Detects 10 common architectural patterns:
  - Web Application
  - Virtual Machine Workload
  - Container Platform
  - Data Platform
  - Serverless Application
  - Data Analytics
  - Secure Workload
  - Managed Identity Pattern
  - Monitoring & Observability
  - Network Security

#### Visualizations Generated
1. **Main Overview**: Resource graph with architectural pattern overlay
   - Colored pattern boundaries (convex hulls)
   - Thick colored edges for intra-pattern connections
   - Thin gray edges for cross-pattern connections
   - Node size represents connection frequency

2. **Individual Pattern Views**: Separate visualization for each detected pattern
   - Highlights pattern resources in orange
   - Shows cross-pattern connections in blue
   - Dims unrelated resources in gray

3. **JSON Export**: Aggregated graph data for use with other tools (D3.js, Cytoscape, Gephi)

## 🚀 Getting Started

### Prerequisites

1. **Neo4j Database**: Must be running with scanned tenant data
   ```bash
   uv run atg scan --tenant-id <TENANT_ID>
   ```

2. **Dependencies**: Install visualization libraries
   ```bash
   uv pip install matplotlib scipy numpy networkx jupyter
   ```

### Running the Notebook

1. Start Jupyter:
   ```bash
   cd notebooks
   uv run jupyter notebook
   ```

2. Open `explore_entities.ipynb`

3. Update connection settings in cell 2:
   ```python
   uri = 'bolt://localhost:7687'
   auth = ('neo4j', 'neo4j123')  # Update with your password
   ```

4. Run all cells (Cell → Run All)

## 📊 Output Files

The notebook generates:
- `/tmp/azure_resource_graph_aggregated.json` - Aggregated graph data

## 🔧 Customization

### Adjust Number of Nodes in Visualization

In cell 22, modify:
```python
top_n_nodes = 30  # Change to show more/fewer nodes
```

### Change Layout Algorithm

In cell 22, modify:
```python
pos = nx.spring_layout(G_filtered, k=3, iterations=50, seed=42)
# Try other layouts: circular_layout, kamada_kawai_layout, etc.
```

### Add Custom Patterns

The patterns are loaded from `ArchitecturalPatternAnalyzer.ARCHITECTURAL_PATTERNS`. To add custom patterns, you can:

1. **Option 1**: Modify the class directly in `src/architectural_pattern_analyzer.py`
2. **Option 2**: Override in the notebook:
   ```python
   analyzer.ARCHITECTURAL_PATTERNS["My Custom Pattern"] = {
       "resources": ["resource1", "resource2", "resource3"],
       "description": "My custom architectural pattern"
   }
   ```

## 🎯 Use Cases

1. **Architecture Discovery**: Understand what architectural patterns exist in your tenant
2. **Security Review**: Identify patterns that need security features (Key Vault, Private Endpoints)
3. **Cost Optimization**: Find over-provisioned or under-utilized patterns
4. **Documentation**: Generate architecture diagrams for documentation
5. **Compliance**: Ensure required patterns are deployed consistently

## 🔍 Troubleshooting

### "No module named 'matplotlib'"
```bash
uv pip install matplotlib scipy
```

### "No relationships found"
Ensure you've scanned a tenant first:
```bash
uv run atg scan --tenant-id <TENANT_ID>
```

### Connection Error
Check Neo4j is running:
```bash
docker ps | grep neo4j
```

Start Neo4j if needed:
```bash
uv run atg scan --tenant-id <TENANT_ID>  # Auto-starts Neo4j
```

## 📚 Related Documentation

- [Architectural Pattern Analysis Guide](../docs/ARCHITECTURAL_PATTERN_ANALYSIS.md)
- [Neo4j Schema Reference](../docs/NEO4J_SCHEMA_REFERENCE.md)
- [CLI Commands](../CLAUDE.md#running-the-cli)

## 🆕 What Changed?

**Previous Version**: All graph analysis code was inline in notebook cells

**New Version**:
- Uses `ArchitecturalPatternAnalyzer` class from `src/architectural_pattern_analyzer.py`
- Same visualizations, but with reusable, tested code
- Easier to maintain and extend
- Can be used from CLI: `uv run atg analyze-patterns`
- Consistent pattern detection across notebook and CLI

The notebook now serves as both:
1. **Interactive exploration tool** for data scientists
2. **Example/documentation** for using the `ArchitecturalPatternAnalyzer` API
