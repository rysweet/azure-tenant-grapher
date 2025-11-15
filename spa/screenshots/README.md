# Screenshots Directory

This directory contains screenshots of the Azure Tenant Grapher application for documentation and presentation purposes.

## Quick Start - For PowerPoint

**Best Screenshot:** `cli-viz-20251115_163528-viewport.png` (581KB)
- Shows complete graph with 10,254 nodes
- Clear edge connections visible
- Professional dark theme
- 1920x1080 resolution
- Perfect for presentations

**Quick Reference:** See `POWERPOINT_QUICK_REFERENCE.md` for presentation tips

## Directory Contents

### Graph Visualizations (CLI-generated)
```
cli-viz-20251115_163528-viewport.png  ⭐ RECOMMENDED
cli-viz-20251115_163528-canvas.png    (alternative)
cli-viz-20251115_163528-full.png      (complete page)
```

### GUI Attempt Screenshots (Error State)
```
gui-visualization-full.png            (shows error)
gui-visualization-viewport.png        (shows error)
gui-error-state.png                   (backend issues)
```
*Note: GUI visualize tab had backend connection issues in web mode*

### Scale Operations UI Workflow
```
scale-operations/
├── 01-initial-scale-up.png
├── 02-scale-down-mode.png
├── 03-template-strategy-form.png
├── 04-scenario-hub-spoke.png
├── 05-random-strategy-form.png
├── 06-scale-down-forest-fire.png
├── 07-ready-for-preview.png
├── 08-ready-for-execution.png
├── 09-quick-actions.png
├── 10-validation-options.png
├── 11-scale-factor-slider.png
├── 12-complete-form.png
├── 13-scale-down-complete.png
└── 14-help-text.png
```

## Documentation

- **VISUALIZATION_SCREENSHOTS_SUMMARY.md** - Complete technical documentation
- **POWERPOINT_QUICK_REFERENCE.md** - Presentation guide and tips

## What the Graph Shows

The visualization screenshot displays:

- **Central Cluster:** Highly interconnected Azure resources (cyan/blue nodes)
  - Core infrastructure components
  - Dense relationship network
  - Shows complex dependencies

- **Peripheral Nodes:** Isolated resources (orange/yellow)
  - Standalone services
  - Minimal dependencies
  - Scale operation candidates

- **Edges:** Clear connection lines showing relationships
  - CONTAINS, USES_IDENTITY, CONNECTED_TO, etc.
  - Physics-based layout
  - Visible even at high density

- **Controls:** Interactive graph tools (left sidebar)
  - Zoom, pan, select
  - Search and filter
  - Node type filtering

## Technical Details

- **Database:** Neo4j with 10,254 nodes
- **Rendering:** vis-network library (physics-based layout)
- **Resolution:** 1920x1080
- **Theme:** Dark background for contrast
- **Capture Method:** Playwright headless Chromium

## CLI vs GUI Visualization

**Important:** Both CLI and GUI use the **same visualization library** (vis-network)
- Edge rendering quality: IDENTICAL
- Interactive features: IDENTICAL
- Graph layout: IDENTICAL

**Difference:** Launch method (browser HTML vs Electron app), not rendering quality

## Usage in PowerPoint

### Recommended Settings
```
Format:
- Insert as Picture
- Keep original quality
- Center or full slide layout
- Optional: 1px border for definition

Slide Ideas:
- Full-width visualization
- Annotated with callouts
- Before/after scale operations
- Technical deep-dive
```

### Talking Points

1. "Over 10,000 Azure resources discovered and graphed"
2. "Central cluster shows tightly coupled infrastructure"
3. "Peripheral nodes are candidates for scale-down"
4. "Interactive physics-based layout"
5. "Available via both CLI and GUI"

## File Sizes

```
CLI Visualizations:  581KB each (high quality)
GUI Screenshots:     39-66KB (error states)
Scale Operations:    77-78KB each (UI screenshots)
```

## Access Documentation

For complete details, see:
1. Project root: `SCREENSHOT_CAPTURE_SESSION_SUMMARY.md`
2. This directory: `VISUALIZATION_SCREENSHOTS_SUMMARY.md`
3. This directory: `POWERPOINT_QUICK_REFERENCE.md`

## Quick Copy Command

```bash
# Copy best screenshot to current directory
cp cli-viz-20251115_163528-viewport.png ~/graph-visualization.png
```

---

**Generated:** 2025-11-15
**Purpose:** Documentation and presentation materials
**Status:** Ready for use in PowerPoint
