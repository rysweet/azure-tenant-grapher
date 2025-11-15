# Graph Visualization Screenshots

This directory contains high-quality 4K screenshots demonstrating the Azure Tenant Grapher's scale operations capabilities, showcasing the progression from baseline to scaled-up to scaled-down states.

## Overview

The Azure Tenant Grapher uses a **dual-graph architecture** where every Azure resource is stored as two nodes:
- **Original nodes** (`:Resource:Original`): Real Azure IDs from the source tenant
- **Abstracted nodes** (`:Resource`): Translated IDs suitable for cross-tenant deployment
- Linked by `SCAN_SOURCE_NODE` relationships

These visualizations demonstrate how the system can scale from thousands to tens of thousands of resources while maintaining graph structure and relationships.

## Screenshots

### 1. BASELINE: Original Graph (3.5k Resources)

**File:** `01-baseline-original.png`

**Description:** Shows the baseline state with ~4,375 Original nodes representing the actual scanned Azure infrastructure. This is the foundation before any scale operations.

**Details:**
- **Total Nodes:** ~4,375 Original resources
- **Node Type:** `:Resource:Original` (real Azure IDs)
- **Relationships:** Network connections, identity relationships, resource containment
- **Resolution:** 3840x2160 (4K)
- **File Size:** 57 KB
- **Use Case:** Initial tenant scan, real infrastructure topology

**Key Characteristics:**
- Represents actual Azure resources with real IDs
- Contains real subscription and resource group hierarchies
- Shows authentic cross-resource relationships (VNets, VMs, Storage, KeyVault, etc.)

---

### 2. SCALED-UP: Abstracted Graph (77k Resources)

**File:** `02-scaled-up-77k.png`

**Description:** Shows the scaled-up state with ~78,602 Abstracted nodes. This demonstrates the system's ability to handle large-scale tenants with tens of thousands of resources.

**Details:**
- **Total Nodes:** ~78,602 Abstracted resources
- **Node Type:** `:Resource` (abstracted IDs like `vm-a1b2c3d4`)
- **Scaling Factor:** ~18x increase from baseline
- **Relationships:** ~41,378 total relationships
- **Resolution:** 3840x2160 (4K)
- **File Size:** 66 KB
- **Use Case:** Large enterprise tenant simulation, load testing, cross-tenant IaC generation

**Key Characteristics:**
- Each node has deterministic abstracted IDs suitable for deployment
- Maintains all relationship types from the original graph
- Demonstrates scalability for large Azure environments
- Ready for cross-tenant deployment scenarios

---

### 3. SCALED-DOWN: 10% Sample (Simulated)

**File:** `03-scaled-down-sample.png`

**Description:** Shows a 10% random sample of the abstracted graph, demonstrating the scale-down capability for creating manageable test datasets or focused analysis.

**Details:**
- **Total Nodes:** ~110 nodes (10% sample visualization)
- **Actual Sample Size:** ~7,700 nodes (10% of 78,602)
- **Node Type:** `:Resource` (abstracted IDs)
- **Sampling Method:** Random node sampling with relationship preservation
- **Resolution:** 3840x2160 (4K)
- **File Size:** 426 KB
- **Use Case:** Testing, development environments, focused analysis, demos

**Key Characteristics:**
- Maintains structural properties of the original graph
- Preserves important relationships and patterns
- Suitable for dev/test environments without full scale
- Demonstrates flexible scale-down capabilities

---

## Visualization Technology

All visualizations are generated using:
- **Backend:** Neo4j graph database with dual-graph architecture
- **Frontend:** D3.js force-directed graph layout
- **Rendering:** Interactive HTML with zoom, pan, and node inspection
- **Screenshot Capture:** Playwright headless browser automation

## Technical Specifications

| Screenshot | Resolution | File Size | Actual Node Count | Shown Nodes* |
|------------|-----------|-----------|-------------------|--------------|
| Baseline   | 3840x2160 | 57 KB     | ~4,375           | ~479         |
| Scaled-Up  | 3840x2160 | 66 KB     | ~78,602          | ~231         |
| Scaled-Down| 3840x2160 | 426 KB    | ~7,700**         | ~110         |

\* For visualization performance, HTML files show a sample of nodes. The actual graph contains the full node counts.
\*\* 10% sample of the scaled-up graph (simulated for demonstration)

## Graph Statistics

### Complete Graph (Current State)
```
Total Nodes:         86,414
Total Relationships: 41,378
Original Nodes:       4,375 (baseline)
Abstracted Nodes:    78,602 (scaled-up)
```

### Progression
1. **BASELINE → SCALED-UP:** ~18x increase (4,375 → 78,602 nodes)
2. **SCALED-UP → SCALED-DOWN:** 10% sample (78,602 → ~7,700 nodes)

## Use Cases

### PowerPoint Presentations
These screenshots are specifically designed for:
- Executive presentations showing scalability
- Technical architecture reviews
- Product demos and capabilities overview
- Academic or conference presentations

### Documentation
- Architecture documentation
- Performance analysis reports
- Scale testing validation
- Customer case studies

### Analysis
- Graph structure analysis
- Relationship pattern identification
- Resource topology understanding
- Cross-tenant deployment planning

## Interactive Visualizations

In addition to these screenshots, the full interactive HTML visualizations are available:
- `01-baseline-original.html` (1.75 MB)
- `02-scaled-up-77k.html` (0.90 MB)
- `03-scaled-down-sample.html` (0.37 MB)

These can be opened in any modern web browser for:
- Interactive exploration with zoom and pan
- Node inspection (click nodes to see properties)
- Relationship tracing
- Real-time graph manipulation

## Reproduction

To regenerate these visualizations:

```bash
# 1. Ensure Neo4j is running with the scaled graph
uv run atg scale-stats

# 2. Generate visualizations
export NEO4J_URI=bolt://localhost:7688
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your-password
uv run python generate_limited_viz.py

# 3. Capture screenshots
# (HTTP server must be running: python3 -m http.server 8765)
node capture-screenshot.js "http://localhost:8765/01-baseline-original.html" \
    "visualizations/01-baseline-original.png" "Baseline" 15000
node capture-screenshot.js "http://localhost:8765/02-scaled-up-77k.html" \
    "visualizations/02-scaled-up-77k.png" "Scaled-Up" 15000
node capture-screenshot.js "http://localhost:8765/03-scaled-down-sample.html" \
    "visualizations/03-scaled-down-sample.png" "Scaled-Down" 15000
```

## Notes

- All screenshots show force-directed graph layouts, which means node positions may vary between generations
- The colored nodes represent different Azure resource types (VMs, Storage, Networks, etc.)
- Relationships (edges) show dependencies, containment, and connectivity between resources
- Node labels are truncated for readability in the visualizations

## Related Documentation

- [Scale Operations Specification](../docs/SCALE_OPERATIONS_SPECIFICATION.md)
- [Scale Operations Summary](../docs/SCALE_OPERATIONS_SUMMARY.md)
- [Neo4j Schema Reference](../docs/NEO4J_SCHEMA_REFERENCE.md)

---

**Generated:** November 11, 2025
**Resolution:** 3840x2160 (4K UHD)
**Format:** PNG, 8-bit RGB
**Tool:** Azure Tenant Grapher v1.x
