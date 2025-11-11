# Synthetic Node Visualization Guide

This guide explains how synthetic nodes from scale operations are visualized in the Azure Tenant Grapher graph visualizer, providing clear visual feedback to distinguish synthetic data from real Azure resources.

## Overview

Synthetic nodes are artificial resources created during scale-up operations to test and validate the system at scale. They are marked with the `:Synthetic` label and have a `synthetic: true` property in Neo4j.

The visualization system provides distinct styling and filtering capabilities to help users easily identify and work with synthetic data.

## Visual Distinctions

### Color Scheme

**Synthetic Nodes:**
- **Primary Color**: Orange (`#FFA500`)
- **Border Color**: Gold (`#FFD700`)
- **Highlight**: Dashed gold border
- **Icon**: 🔶 (orange diamond emoji)

**Real Nodes:**
- Standard color scheme based on resource type (blue, green, purple, etc.)
- Solid borders
- No special icons

### Border Styling

**Synthetic Nodes:**
- **Border Width**: 3px (thicker than regular nodes)
- **Border Style**: Dashed (`[5, 5]` pattern)
- **Selected Border Width**: 5px

**Real Nodes:**
- **Border Width**: 2px
- **Border Style**: Solid
- **Selected Border Width**: 4px

### 3D Visualization (HTML Viewer)

In the 3D graph visualization (generated HTML files), synthetic nodes are rendered with:

1. **Main Sphere**: Orange colored sphere
2. **Dashed Ring**: Gold dashed ring around the node for extra visibility
3. **'S' Label**: Small 'S' sprite above the node indicating "Synthetic"

```javascript
// Example 3D rendering for synthetic nodes
if (node.synthetic) {
  const group = new THREE.Group();

  // Main sphere (orange)
  const sphere = new THREE.Mesh(geometry, orangeMaterial);
  group.add(sphere);

  // Dashed ring (gold)
  const ring = new THREE.Line(ringGeometry, dashedGoldMaterial);
  group.add(ring);

  // 'S' label sprite
  const sprite = new THREE.Sprite(spriteMaterial);
  group.add(sprite);

  return group;
}
```

## UI Features

### Synthetic Node Toggle

**Location**: Left control panel in the graph visualization

**Features:**
- **Toggle Button**: Click to show/hide all synthetic nodes
- **Visual Feedback**:
  - Active: Orange background with dashed gold border
  - Inactive: Gray background with faded border
- **Status Chip**: Shows "Shown" or "Hidden" status
- **Count Display**: Shows total number of synthetic nodes in the graph

**Example:**
```
🔶 Synthetic Nodes          [Shown]
42 synthetic nodes
```

### Legend Integration

**Location**: Compact legend panel (right side)

The legend includes a special "Synthetic" entry at the top under a "Special" category:

- **Interactive**: Click to toggle synthetic node visibility
- **Visual Indicator**: Dashed gold circle
- **State Display**: Changes opacity when hidden
- **Hover Effect**: Highlights on mouse hover

### Tooltips

When hovering over or clicking a synthetic node, the tooltip includes:

```
Node Name
Type: Microsoft.Compute/virtualMachines
Resource Group: rg-test
Location: eastus
🔶 SYNTHETIC NODE
Click for more details
```

The synthetic indicator is displayed in **bold orange** at the bottom of the tooltip.

## Filtering Capabilities

### Basic Filtering

1. **Toggle All Synthetic Nodes**:
   - Click the synthetic node toggle button
   - All synthetic nodes are shown/hidden at once
   - Filter applies across all node types

2. **Type-Based Filtering**:
   - Filter by resource type (VM, VNet, etc.) while keeping synthetic filter active
   - Synthetic and type filters work together (AND logic)

3. **Search Filtering**:
   - Search works on synthetic nodes just like regular nodes
   - Search by name, type, or properties

### Advanced Filtering

The advanced filters work seamlessly with synthetic node filtering:

1. **Name Filter**: Filter synthetic nodes by name pattern
2. **Tags Filter**: Filter by tags (if synthetic nodes have tags)
3. **Region Filter**: Show synthetic nodes in specific regions
4. **Resource Group Filter**: Show synthetic nodes in specific resource groups
5. **Subscription Filter**: Show synthetic nodes in specific subscriptions

**Filter Logic:**
```javascript
// All filters use AND logic
const isVisible =
  showSyntheticNodes_OR_notSynthetic &&
  matchesNodeType &&
  matchesNameFilter &&
  matchesTagsFilter &&
  matchesRegionFilter &&
  matchesResourceGroupFilter &&
  matchesSubscriptionFilter;
```

## Backend Implementation

### Neo4j Query

The backend automatically detects synthetic nodes:

```cypher
MATCH (n)
WHERE n:Synthetic OR n.synthetic = true
RETURN n
```

### API Response

The `/api/graph` endpoint includes the `synthetic` property for each node:

```json
{
  "nodes": [
    {
      "id": "4:abc123",
      "label": "synthetic-vm-001",
      "type": "VirtualMachine",
      "properties": {
        "id": "synthetic-vm-abc123",
        "name": "synthetic-vm-001",
        "synthetic": true,
        "type": "Microsoft.Compute/virtualMachines"
      },
      "synthetic": true
    }
  ],
  "edges": [...],
  "stats": {
    "nodeCount": 100,
    "edgeCount": 150
  }
}
```

### TypeScript Interface

```typescript
interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
  synthetic?: boolean;  // Indicates synthetic node
}
```

## Configuration Options

### Color Customization

To customize synthetic node colors, update the color constants:

**Python (graph_visualizer.py):**
```python
def _get_node_color(self, node_type: str, is_synthetic: bool = False) -> str:
    if is_synthetic:
        return "#FFA500"  # Change to your preferred color
```

**React (GraphVisualization.tsx):**
```typescript
const NODE_COLORS: Record<string, string> = {
  Synthetic: '#FFA500',  // Change to your preferred color
  // ... other colors
};
```

**JavaScript (javascript_builder.py):**
```javascript
// Update in the synthetic node rendering code
const color = '#FFA500';  // Change to your preferred color
const borderColor = '#FFD700';  // Change to your preferred border color
```

### Default Visibility

To change whether synthetic nodes are shown by default:

**React Component:**
```typescript
// In GraphVisualization.tsx
const [showSyntheticNodes, setShowSyntheticNodes] = useState(true);  // Change to false to hide by default
```

**3D Visualization:**
```javascript
// In javascript_builder.py
let showSyntheticNodes = true;  // Change to false to hide by default
```

## Export Functionality

### With Synthetic Nodes

When exporting the graph with synthetic nodes visible:
- All synthetic nodes are included in the export
- Synthetic properties are preserved
- Visual styling is maintained in HTML exports

### Without Synthetic Nodes

When exporting with synthetic nodes hidden:
- Synthetic nodes are excluded from the export
- Only relationships between visible nodes are included
- Cleaner output for production documentation

**Note**: The export respects the current filter state. Hide synthetic nodes before exporting if you want a production-ready view.

## Use Cases

### Development and Testing

1. **Validation**: Verify synthetic data generation
2. **Scale Testing**: Visualize large-scale synthetic topologies
3. **Debugging**: Identify issues with synthetic resource creation

### Production

1. **Comparison**: Compare real vs. synthetic topologies
2. **Planning**: Use synthetic data to plan infrastructure changes
3. **Training**: Use synthetic environments for training without affecting production

### Cleanup

1. **Visual Verification**: Verify all synthetic nodes before cleanup
2. **Selective Cleanup**: Identify which synthetic resources to remove
3. **Confirmation**: Verify cleanup was successful by checking the graph

## Best Practices

### Naming Conventions

Synthetic resources should use a clear naming pattern:
- Prefix with `synthetic-`
- Include resource type abbreviation
- Add unique identifier

Example: `synthetic-vm-a1b2c3d4`, `synthetic-vnet-e5f6g7h8`

### Labeling

Always apply both:
1. `:Synthetic` label in Neo4j
2. `synthetic: true` property

This ensures compatibility across all visualization tools.

### Documentation

When sharing visualizations:
- Document whether synthetic nodes are included
- Explain the purpose of synthetic data
- Provide cleanup instructions if needed

### Cleanup

After testing:
1. Use the visualization to verify what will be deleted
2. Run `atg scale-clean` to remove synthetic nodes
3. Verify cleanup in the visualization

## Troubleshooting

### Synthetic Nodes Not Showing

**Issue**: Synthetic toggle is on but nodes aren't visible

**Solutions:**
1. Check if node type filter is active
2. Verify Neo4j nodes have `:Synthetic` label or `synthetic: true` property
3. Check browser console for JavaScript errors
4. Refresh the page and try again

### Styling Not Applied

**Issue**: Synthetic nodes appear but don't have orange color

**Solutions:**
1. Clear browser cache and reload
2. Check that backend is returning `synthetic: true` in API response
3. Verify color constants in code match documentation

### Filter Not Working

**Issue**: Toggle doesn't filter synthetic nodes

**Solutions:**
1. Check browser console for errors
2. Verify `showSyntheticNodes` state is updating
3. Check that filter logic includes synthetic check
4. Ensure useEffect dependencies include `showSyntheticNodes`

## Related Commands

### Scale Operations
- `atg scale-up` - Generate synthetic data
- `atg scale-clean` - Remove synthetic data
- `atg scale-stats` - View synthetic data statistics
- `atg scale-validate` - Validate synthetic data integrity

### Visualization
- `atg visualize` - Generate 3D HTML visualization
- Web UI: Access graph visualization tab

## Technical Details

### Graph Schema

Synthetic nodes in Neo4j:

```cypher
// Example synthetic node
(:Resource:Synthetic {
  id: "synthetic-vm-a1b2c3d4",
  name: "synthetic-vm-001",
  type: "Microsoft.Compute/virtualMachines",
  synthetic: true,
  operation_id: "op-12345",
  source_resource: "vm-abc123",
  tenantId: "tenant-123"
})
```

### Relationships

Synthetic nodes have the same relationship types as real nodes:
- `CONTAINS`
- `USES_IDENTITY`
- `CONNECTED_TO`
- `DEPENDS_ON`
- etc.

### Performance

Synthetic node filtering is optimized:
- Client-side filtering (no additional API calls)
- No performance impact when toggling
- Efficient for graphs with thousands of nodes

## Future Enhancements

Potential future improvements:

1. **Bulk Operations**: Select multiple synthetic nodes for export
2. **Color Themes**: Multiple color schemes for synthetic nodes
3. **Animation**: Animated indicators for synthetic nodes
4. **Statistics**: Show synthetic vs. real node ratio
5. **Timeline**: Show when synthetic nodes were created
6. **Grouping**: Group synthetic nodes by operation ID

## Summary

The synthetic node visualization system provides:

✅ **Clear Visual Distinction** - Orange color, dashed borders, and special icons
✅ **Easy Filtering** - One-click toggle to show/hide synthetic nodes
✅ **Flexible Integration** - Works with all existing filters and features
✅ **Comprehensive Support** - Available in both 2D (React) and 3D (HTML) visualizations
✅ **Production Ready** - Hide synthetic data for production documentation
✅ **Well Documented** - Clear examples and troubleshooting guides

For more information, see:
- Scale Operations Guide: `docs/SCALE_OPERATIONS_GUIDE.md`
- Graph Visualization: `docs/VISUALIZATION.md`
- Neo4j Schema: `docs/NEO4J_SCHEMA_REFERENCE.md`
