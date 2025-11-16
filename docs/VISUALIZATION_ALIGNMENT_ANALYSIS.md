# Visualization Alignment Analysis: CLI vs GUI

**Date:** 2025-11-15
**Goal:** Align CLI `atg visualize` output with GUI visualization tab appearance

## Overview

The project has two visualization implementations:
- **CLI**: Uses 3d-force-graph library, generates standalone HTML files
- **GUI**: Uses vis-network library (2D), embedded in Electron React app

## Key Differences Identified

### 1. **Rendering Library**

| Aspect | CLI (3d-force-graph) | GUI (vis-network) |
|--------|---------------------|-------------------|
| Library | 3d-force-graph (THREE.js based) | vis-network |
| Dimensions | 3D | 2D |
| Backend | THREE.js WebGL | HTML5 Canvas |
| Layout | Force-directed 3D | Force-directed 2D |

**Impact:** These are fundamentally different rendering approaches. The CLI uses 3D space while GUI uses 2D.

### 2. **Physics Engine Configuration**

**CLI (javascript_builder.py, line 150-337):**
```javascript
// Uses default 3d-force-graph physics
// No explicit physics configuration visible
```

**GUI (GraphVisualization.tsx, lines 490-516):**
```typescript
physics: {
  enabled: true,
  solver: 'forceAtlas2Based',
  forceAtlas2Based: {
    gravitationalConstant: -50,
    centralGravity: 0.01,
    springLength: 100,
    springConstant: 0.08,
    damping: 0.4,
    avoidOverlap: 0.5
  },
  stabilization: {
    enabled: true,
    iterations: 200,
    updateInterval: 10
  }
}
```

**Issue:** CLI uses default physics; GUI uses tuned forceAtlas2Based algorithm for better layout.

### 3. **Node Colors**

**CLI (javascript_builder.py, lines 606-651):**
- Subscription: `#ff6b6b`
- ResourceGroup: `#45b7d1`
- VirtualMachines: `#6c5ce7`
- VirtualNetworks: `#26de81`
- StorageAccounts: `#f9ca24`
- Synthetic: `#FFA500` (orange)

**GUI (GraphVisualization.tsx, lines 72-135):**
- Tenant: `#FF6B6B`
- Subscription: `#4ECDC4` ⚠️ (different!)
- ResourceGroup: `#45B7D1`
- VirtualMachine: `#FFEAA7` ⚠️ (different!)
- VirtualNetwork: `#6C5CE7` ⚠️ (different!)
- StorageAccount: `#74B9FF` ⚠️ (different!)
- Synthetic: `#FFA500` (matches)

**Issue:** Multiple color mismatches between implementations.

### 4. **Edge/Relationship Colors**

**CLI (javascript_builder.py, lines 653-664):**
- CONTAINS: `#74b9ff`
- BELONGS_TO: `#a29bfe`
- CONNECTED_TO: `#fd79a8`
- DEPENDS_ON: `#fdcb6e`
- MANAGES: `#e17055`

**GUI (GraphVisualization.tsx, lines 138-155):**
- CONTAINS: `#2E86DE` ⚠️ (different!)
- USES_IDENTITY: `#10AC84` (not in CLI)
- CONNECTED_TO: `#FF9F43` ⚠️ (different!)
- DEPENDS_ON: `#A55EEA` ⚠️ (different!)
- MANAGES: `#FDCB6E` ⚠️ (different!)

**Issue:** Edge colors differ significantly. GUI has more edge types defined.

### 5. **Edge Styling**

**CLI:**
- Basic color and width
- Some special handling for dashed lines (CONNECTED_TO_PE)
- Particles for animation

**GUI:**
- Color, width, AND dash patterns
- Arrows configured per edge type
- More sophisticated visual distinction

Example GUI edge style:
```typescript
CONTAINS: { color: '#2E86DE', width: 3, dashes: false, arrows: 'to' }
DEPENDS_ON: { color: '#A55EEA', width: 2, arrows: 'to', dashes: [10, 5] }
```

### 6. **Background Color**

**CLI:** `#1a1a1a` (dark gray)
**GUI:** `#000000` (pure black)

### 7. **Node Size**

**CLI (graph_visualizer.py, lines 501-522):**
- Subscription: 15
- Resource: 8
- ResourceGroup: 12
- Synthetic: 30% larger

**GUI (GraphVisualization.tsx, line 439):**
- All nodes: size=20 (uniform)
- No size variation by type

### 8. **Special Node Rendering**

**CLI:**
- PrivateEndpoint: Diamond shape (THREE.OctahedronGeometry)
- DNSZone: Hexagon (ExtrudeGeometry)
- Subscription: Sphere with floating label
- Synthetic: Special rendering with dashed ring and 'S' label

**GUI:**
- All nodes: Simple dots (shape: 'dot')
- Synthetic: Dashed border, no special 3D geometry
- No special shapes for PrivateEndpoint/DNSZone

### 9. **Camera Position and Controls**

**CLI:**
- 3D camera with x, y, z coordinates
- Auto-rotate feature available
- Zoom via camera position.z manipulation

**GUI:**
- 2D pan and zoom
- Navigation buttons for up/down/left/right
- Scale-based zoom

### 10. **Layout Algorithm**

**CLI:**
- 3D force-directed layout (default from 3d-force-graph)
- Natural 3D clustering

**GUI:**
- 2D forceAtlas2Based with specific parameters
- Configured for optimal 2D spread
- Overlap avoidance: 0.5

## Critical Misalignment Issues

### Priority 1: Color Palette Inconsistency
- Node colors differ for core types (Subscription, VirtualMachine, etc.)
- Edge colors are completely different schemes
- **Impact:** Users see different visual representations in CLI vs GUI

### Priority 2: Library Incompatibility
- 3D (CLI) vs 2D (GUI) is a fundamental difference
- Cannot be aligned without major refactoring
- **Impact:** Layout and perspective will always differ

### Priority 3: Physics Configuration
- CLI lacks tuned physics parameters
- GUI has optimized forceAtlas2Based configuration
- **Impact:** CLI layout may appear chaotic compared to GUI

### Priority 4: Node Styling
- Size variation differs
- Special shapes only in CLI (3D)
- **Impact:** Node prominence and identification differs

## Recommendations

### Option A: Align Colors Only (Quick Fix)
- Update CLI color palette to match GUI exactly
- Update edge colors to match GUI
- Keep other differences (3D vs 2D, physics)
- **Effort:** Low (1-2 hours)
- **Impact:** Visual consistency improved, but layout differences remain

### Option B: Standardize on vis-network (Full Alignment)
- Migrate CLI to use vis-network instead of 3d-force-graph
- Generate 2D visualizations with same physics
- Perfect alignment with GUI
- **Effort:** High (8-12 hours)
- **Impact:** Complete visual parity

### Option C: Document Differences (No Change)
- Add documentation explaining the two approaches
- Clarify that CLI is 3D, GUI is 2D
- Accept as intentional design decision
- **Effort:** Minimal (30 minutes)
- **Impact:** No technical change, just clarity

## Recommended Approach: Option A (Color Alignment)

**Rationale:**
- Quick to implement
- Provides immediate visual consistency improvement
- Respects the different use cases (3D standalone vs 2D embedded)
- Allows CLI to retain its unique 3D capabilities

**Implementation Plan:**
1. Update `javascript_builder.py` node color mapping to match GUI
2. Update `javascript_builder.py` edge color mapping to match GUI
3. Update background color from `#1a1a1a` to `#000000`
4. Optionally: Add physics configuration hints to improve layout

**Files to Modify:**
- `/src/visualization/javascript_builder.py` (lines 606-664)
- Document the intentional 3D vs 2D difference

## Testing Strategy

After implementing color alignment:
1. Generate CLI visualization: `uv run atg visualize`
2. Open GUI visualization tab
3. Compare:
   - Node colors for same resource types
   - Edge colors for same relationship types
   - Background color
4. Verify synthetic node highlighting matches (orange `#FFA500`)

## Conclusion

The CLI and GUI use different rendering libraries (3D vs 2D), making perfect alignment impossible without major refactoring. However, aligning the color palettes will provide significant visual consistency while respecting each implementation's unique strengths.
