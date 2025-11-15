# Scale Operations Diagram Manifest

Comprehensive inventory of all architecture diagrams for Issue #427.

## Deliverables Summary

| Diagram | Source | PNG | Resolution | File Size | Status |
|---------|--------|-----|------------|-----------|--------|
| Dual-Graph Architecture | `dual-graph-architecture.mmd` | `dual-graph-architecture.png` | 1904x708 | 117 KB | ✓ Complete |
| Scale-Up Sequence | `scale-up-sequence.mmd` | `scale-up-sequence.png` | 1904x3047 | 359 KB | ✓ Complete |
| Scale-Down Pipeline | `scale-down-pipeline.mmd` | `scale-down-pipeline.png` | 1904x616 | 133 KB | ✓ Complete |
| Component Architecture | `component-architecture.mmd` | `component-architecture.png` | 1904x371 | 138 KB | ✓ Complete |

**Total:** 4 diagrams, 8 files (4 source + 4 rendered), 747 KB

---

## Diagram Details

### 1. Dual-Graph Architecture
- **Type:** Flowchart (TB - Top to Bottom)
- **Complexity:** Medium (3 subgraphs, legend, ~20 nodes)
- **Colors:** Red (Original), Blue (Abstracted), Green (Synthetic)
- **Key Feature:** Shows SCAN_SOURCE_NODE dotted relationships
- **Best For:** Explaining foundational architecture

### 2. Scale-Up Sequence
- **Type:** Sequence diagram
- **Complexity:** High (6 participants, 50+ interactions)
- **Colors:** Multi-colored regions for phases
- **Key Feature:** Alternative failure/rollback path
- **Best For:** Understanding operation flow and error handling
- **Note:** Tallest diagram (3047px) due to detailed sequence

### 3. Scale-Down Pipeline
- **Type:** Left-to-right flowchart (LR)
- **Complexity:** High (4 stages, multiple subgraphs)
- **Colors:** Stage-based coloring with consistent palette
- **Key Feature:** Performance targets annotated on edges
- **Best For:** Understanding sampling algorithms and export formats

### 4. Component Architecture
- **Type:** Class diagram
- **Complexity:** Very High (15+ classes, inheritance, composition)
- **Colors:** Minimal (UML standard)
- **Key Feature:** Complete method signatures and relationships
- **Best For:** Code navigation and architectural understanding
- **Note:** Widest diagram - may need landscape orientation

---

## Technical Specifications

### Rendering Engine
- **Tool:** Mermaid CLI (`@mermaid-js/mermaid-cli`)
- **Version:** Latest (installed via npm)
- **Browser:** Puppeteer (headless Chromium)

### Image Properties
- **Width:** 1904 pixels (requested 1920, mermaid auto-adjusts)
- **Height:** Auto-calculated based on content
- **Format:** PNG with RGBA color space
- **Background:** Transparent (alpha channel)
- **DPI:** Standard screen resolution (96 DPI)
- **Compression:** PNG default (lossless)

### Rendering Command
```bash
mmdc -i <input>.mmd -o <output>.png -w 1920 -H 1080 -b transparent
```

Note: Height (`-H 1080`) is a suggestion. Mermaid auto-calculates actual height based on diagram content.

---

## Quality Metrics

### Visual Quality
- ✓ Text readability: Excellent at 1920px width
- ✓ Color contrast: Meets accessibility standards
- ✓ Anti-aliasing: Smooth edges on all elements
- ✓ Alignment: Proper node and edge alignment
- ✓ Spacing: Adequate whitespace between elements

### Technical Quality
- ✓ No rendering errors
- ✓ All connections valid
- ✓ Labels complete and accurate
- ✓ Color consistency across diagrams
- ✓ Transparent background working

### File Size
- ✓ All PNGs < 400 KB (target: <500 KB)
- ✓ Reasonable for web and document embedding
- ✓ Acceptable for version control

---

## PowerPoint Integration Guide

### Slide Setup
1. **Layout:** 16:9 aspect ratio (standard)
2. **Background:** Any color (diagrams are transparent)
3. **Insert:** Pictures → Select PNG file

### Recommended Sizes

**Full-slide diagrams:**
- Dual-Graph Architecture: Full width (works well)
- Scale-Down Pipeline: Full width (works well)
- Component Architecture: Full width (works well)

**Special handling:**
- Scale-Up Sequence: Very tall (3047px)
  - Option A: Two slides (split at Phase 2 and rollback)
  - Option B: Landscape orientation
  - Option C: Zoom to specific regions

### Presentation Tips
- Use "Zoom to Selection" for detailed views
- Add callout boxes to highlight specific sections
- Combine with bullet points on side for explanations
- Use animations to reveal sections progressively

---

## Markdown Integration

### In README.md
```markdown
## Architecture Overview

![Dual-Graph Architecture](docs/diagrams/dual-graph-architecture.png)

The system uses a dual-graph architecture...
```

### In Documentation
```markdown
# Scale Operations

## Component Structure

![Component Architecture](diagrams/component-architecture.png)

*Figure 1: Service hierarchy and dependencies*
```

### In GitHub Pages
```markdown
---
layout: page
title: Scale Operations Architecture
---

![Architecture](./diagrams/dual-graph-architecture.png)
```

---

## Version Control

### Committed Files
All source (`.mmd`) and rendered (`.png`) files are committed to git.

**Rationale:**
- ✓ Source allows easy updates and diffs
- ✓ Rendered files ensure consistent viewing (no render dependency)
- ✓ Team members without mermaid-cli can still view diagrams

### File Sizes in Git
```
docs/diagrams/
├── component-architecture.mmd      7.7 KB
├── component-architecture.png      138 KB
├── dual-graph-architecture.mmd     3.6 KB
├── dual-graph-architecture.png     117 KB
├── scale-down-pipeline.mmd         4.1 KB
├── scale-down-pipeline.png         133 KB
├── scale-up-sequence.mmd           4.2 KB
├── scale-up-sequence.png           359 KB
├── README.md                       ~8 KB
└── DIAGRAM_MANIFEST.md            (this file)
```

**Total git impact:** ~780 KB (acceptable for high-quality diagrams)

---

## Maintenance Schedule

### Regular Updates
- **Monthly:** Review for accuracy
- **Per Release:** Update if architecture changes
- **Per Feature:** Add diagrams for new major features

### Update Triggers
1. Service class added/removed/renamed
2. Operation flow changes (new phases, steps)
3. Algorithm changes (new sampling methods)
4. Performance target adjustments
5. Data model changes (new properties, relationships)

### Update Process
1. Edit `.mmd` source file
2. Re-render: `mmdc -i file.mmd -o file.png -w 1920 -H 1080 -b transparent`
3. Visual verification (open PNG)
4. Update documentation (README.md, this file)
5. Git commit both source and rendered files

---

## Accessibility

### Color Blind Friendly
- ✓ Uses distinct colors with different brightness levels
- ✓ Text labels on all elements (not color-dependent)
- ✓ Shapes differ for different element types
- ✓ High contrast maintained

### Screen Reader Support
- Mermaid diagrams in markdown include alt text
- Use descriptive alt text when embedding:
  ```markdown
  ![Dual-graph architecture showing Original and Abstracted layers with synthetic resources](diagrams/dual-graph-architecture.png)
  ```

### Print Friendly
- ✓ High resolution for quality prints
- ✓ Black edges maintain definition on color printers
- ✓ Transparent background adapts to paper color
- ⚠ Scale-Up Sequence requires multiple pages (very tall)

---

## Export Formats

### Available Now
- **PNG:** High-quality raster (delivered)
- **Mermaid:** Text source (delivered)

### Future Options
```bash
# SVG (vector graphics, infinite scaling)
mmdc -i diagram.mmd -o diagram.svg

# PDF (document integration)
mmdc -i diagram.mmd -o diagram.pdf

# Multiple formats at once
mmdc -i diagram.mmd -o diagram.png -o diagram.svg -o diagram.pdf
```

---

## Troubleshooting

### Common Issues

**Issue:** Diagram doesn't render
- **Solution:** Check mermaid syntax with Mermaid Live Editor (https://mermaid.live/)

**Issue:** Text is cut off
- **Solution:** Increase width parameter: `-w 2400` or `-w 3000`

**Issue:** File size too large
- **Solution:** Simplify diagram or split into multiple diagrams

**Issue:** Colors don't match
- **Solution:** Use hex codes from style guide (see README.md)

**Issue:** PNG is blurry
- **Solution:** Increase resolution or export to SVG instead

---

## Related Files

### Documentation
- `README.md` - Diagram-specific documentation
- `../SCALE_OPERATIONS_DIAGRAMS.md` - Usage guide and scenarios
- `../SCALE_OPERATIONS_SPECIFICATION.md` - Technical specification

### Source Code
- `../../src/services/scale_up_service.py` - Scale-up implementation
- `../../src/services/scale_down_service.py` - Scale-down implementation
- `../../src/services/base_scale_service.py` - Base service

### Tests
- `../../tests/test_scale_up_service.py` - Scale-up tests
- `../../tests/test_scale_down_service.py` - Scale-down tests

---

## Acknowledgments

**Tools Used:**
- Mermaid.js - Diagram syntax and rendering
- @mermaid-js/mermaid-cli - Command-line renderer
- Puppeteer - Headless browser for rendering

**Created By:**
- Azure Tenant Grapher Visualization-Architect Agent

**Date:** 2025-11-11

---

## Checklist for New Diagrams

When adding new diagrams to this set:

- [ ] Create `.mmd` source file
- [ ] Follow naming convention: `lowercase-with-hyphens.mmd`
- [ ] Use consistent colors from style guide
- [ ] Add descriptive comments at top of file
- [ ] Render to PNG with standard command
- [ ] Verify resolution and quality
- [ ] Add entry to this manifest
- [ ] Update README.md
- [ ] Update SCALE_OPERATIONS_DIAGRAMS.md
- [ ] Commit both source and rendered files
- [ ] Update related documentation

---

*Last Updated: 2025-11-11*
*Version: 1.0*
*Status: Production Ready*
