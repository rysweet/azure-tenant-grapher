# Synthetic Node Visualization - Quick Reference

## At a Glance

### Visual Indicators

| Feature | Synthetic Nodes | Real Nodes |
|---------|----------------|------------|
| **Color** | 🟠 Orange | 🔵 Type-based colors |
| **Border** | Dashed gold | Solid color |
| **Icon** | 🔶 'S' label | None |
| **Border Width** | 3px | 2px |
| **Tooltip** | Shows "SYNTHETIC NODE" | Standard info |

### Quick Actions

```bash
# View synthetic nodes in graph
atg visualize                    # 3D HTML visualization

# Toggle in UI
# Click the "🔶 Synthetic Nodes" button in the control panel

# Clean up synthetic data
atg scale-clean                  # Remove all synthetic nodes

# Check synthetic stats
atg scale-stats                  # View counts and details
```

## Common Tasks

### Show/Hide Synthetic Nodes

**Web UI:**
1. Open graph visualization tab
2. Click "🔶 Synthetic Nodes" toggle in left panel
3. Status shows "Shown" or "Hidden"

**3D HTML:**
1. Open generated HTML file
2. Check/uncheck "🔶 Synthetic Nodes" in filters panel
3. Nodes update in real-time

### Identify Synthetic Nodes

1. **Color**: Look for orange nodes
2. **Border**: Dashed gold border
3. **Hover**: Tooltip shows "🔶 SYNTHETIC NODE"
4. **Legend**: Gold entry at top of legend

### Filter Synthetic Nodes

**Basic Filter:**
- Click synthetic toggle (shows/hides ALL synthetic)

**Combined Filters:**
- Type filter + synthetic filter
- Search + synthetic filter
- Advanced filters + synthetic filter

**Example: Show only synthetic VMs in eastus**
1. Enable synthetic toggle
2. Select "VirtualMachines" node type
3. Select "eastus" in region filter

### Export Without Synthetic Data

1. Hide synthetic nodes (uncheck toggle)
2. Verify graph shows only real nodes
3. Export or screenshot

**Command line:**
```bash
# Generate spec without synthetic data (if graph filtered)
atg generate-spec

# Generate IaC without synthetic data
atg generate-iac --tenant-id <ID>
```

## Configuration

### Change Colors

**File:** `src/graph_visualizer.py` (Python)
```python
# Line ~430
if is_synthetic:
    return "#FFA500"  # Change to your color
```

**File:** `spa/renderer/src/components/graph/GraphVisualization.tsx` (React)
```typescript
// Line ~73
Synthetic: '#FFA500',  // Change to your color
```

### Default Visibility

**File:** `spa/renderer/src/components/graph/GraphVisualization.tsx`
```typescript
// Line ~194
const [showSyntheticNodes, setShowSyntheticNodes] = useState(true);  // true = shown by default
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Nodes not orange | Check if backend includes `synthetic: true` |
| Toggle not working | Refresh page, clear browser cache |
| Missing 'S' label | Only in 3D HTML visualization |
| Wrong node count | Re-run `atg scale-stats` |

## API Response Example

```json
{
  "nodes": [
    {
      "id": "4:abc123",
      "label": "synthetic-vm-001",
      "type": "VirtualMachine",
      "synthetic": true,
      "properties": {
        "synthetic": true,
        "id": "synthetic-vm-abc123"
      }
    }
  ]
}
```

## Neo4j Queries

```cypher
// Count synthetic nodes
MATCH (n:Synthetic) RETURN count(n)

// Find all synthetic VMs
MATCH (n:Synthetic)
WHERE n.type CONTAINS 'virtualMachines'
RETURN n

// Show synthetic relationships
MATCH (s:Synthetic)-[r]->(t)
RETURN s, r, t
LIMIT 100

// Delete all synthetic nodes
MATCH (n:Synthetic) DETACH DELETE n
```

## Scale Operations Flow

```
1. Create synthetic data
   └─> atg scale-up --scale-factor 2.0

2. Visualize with synthetic
   └─> atg visualize
   └─> Open web UI → Graph tab

3. Toggle synthetic nodes
   └─> Click "🔶 Synthetic Nodes" button

4. Export without synthetic
   └─> Hide synthetic nodes
   └─> Export/screenshot

5. Clean up
   └─> atg scale-clean
   └─> Verify in visualization
```

## Color Reference

### Hex Colors
- **Synthetic Primary**: `#FFA500` (Orange)
- **Synthetic Border**: `#FFD700` (Gold)
- **Real Resources**: Various (blue, green, purple, etc.)

### RGB Colors
- **Synthetic Primary**: `rgb(255, 165, 0)`
- **Synthetic Border**: `rgb(255, 215, 0)`

## Related Commands

```bash
# Scale operations
atg scale-up              # Generate synthetic data
atg scale-down            # Reduce resources
atg scale-clean           # Remove synthetic data
atg scale-stats           # View statistics
atg scale-validate        # Validate integrity

# Visualization
atg visualize             # 3D HTML graph
# Web UI: Graph tab        # 2D interactive graph

# Export
atg generate-spec         # Tenant specification
atg generate-iac          # Infrastructure as Code
```

## Links

- [Full Documentation](SYNTHETIC_NODE_VISUALIZATION.md)
- [Scale Operations Guide](SCALE_CONFIG_REFERENCE.md)
- API Documentation (see ../spa/backend/src/ for backend source code)

---

**Quick Help:**
- Default view: Synthetic nodes **shown**
- Orange nodes = Synthetic
- Toggle in UI to show/hide
- Clean with `atg scale-clean`
