# Scale Operations Architecture Diagrams

This directory contains comprehensive Mermaid diagrams for the Scale Operations feature (Issue #427).

## Diagrams

### 1. Dual-Graph Architecture (`dual-graph-architecture.mmd`)

**Purpose:** Shows how the dual-graph architecture enables scale operations to work exclusively on the abstracted layer.

**Key Concepts:**
- Original Layer (`:Resource:Original`) - Real Azure IDs from source tenant
- Abstracted Layer (`:Resource`) - IaC-ready hash-based IDs
- Synthetic Resources - Test data created by scale operations
- `SCAN_SOURCE_NODE` relationships linking the layers

**Use Cases:**
- Understanding the separation between original and abstracted data
- Explaining why scale operations don't affect original data
- Showing how synthetic resources integrate with the graph

**File Sizes:**
- Mermaid source: 3.6 KB
- PNG render: 117 KB (1920x1080, transparent)

---

### 2. Scale-Up Sequence (`scale-up-sequence.mmd`)

**Purpose:** Step-by-step flow of a scale-up operation from user command to completion.

**Key Concepts:**
- Session ID generation for tracking
- Base resource analysis
- Adaptive batch processing
- Relationship cloning
- Validation checks
- Rollback on failure

**Use Cases:**
- Understanding the scale-up workflow
- Debugging scale-up issues
- Training developers on the operation flow
- Documenting error handling and rollback

**File Sizes:**
- Mermaid source: 4.2 KB
- PNG render: 359 KB (1920x1080, transparent)

---

### 3. Scale-Down Pipeline (`scale-down-pipeline.mmd`)

**Purpose:** End-to-end pipeline showing how graphs are sampled and exported.

**Key Concepts:**
- Stage 1: Extract (Neo4j → NetworkX)
- Stage 2: Sample (Forest Fire, MHRW, Random Walk, Pattern)
- Stage 3: Validate Quality (KL divergence, clustering, etc.)
- Stage 4: Export (YAML, JSON, Neo4j, IaC)

**Use Cases:**
- Understanding sampling algorithms
- Choosing the right algorithm for use case
- Explaining quality metrics
- Showing export format options

**File Sizes:**
- Mermaid source: 4.1 KB
- PNG render: 133 KB (1920x1080, transparent)

---

### 4. Component Architecture (`component-architecture.mmd`)

**Purpose:** Class diagram showing all services, their relationships, and dependencies.

**Key Concepts:**
- Service inheritance hierarchy
- Dependencies between components
- Data models (ScaleUpResult, QualityMetrics)
- External dependencies (NetworkX, LittleBallOfFur)
- Performance monitoring components

**Use Cases:**
- Understanding code structure
- Planning new features
- Onboarding new developers
- Architecture documentation

**File Sizes:**
- Mermaid source: 7.7 KB
- PNG render: 138 KB (1920x1080, transparent)

---

## Rendering Instructions

### Prerequisites

Install Mermaid CLI globally:

```bash
npm install -g @mermaid-js/mermaid-cli
```

### Render Individual Diagram

```bash
cd docs/diagrams
mmdc -i dual-graph-architecture.mmd -o dual-graph-architecture.png -w 1920 -H 1080 -b transparent
```

### Render All Diagrams

```bash
cd docs/diagrams
for file in *.mmd; do
  mmdc -i "$file" -o "${file%.mmd}.png" -w 1920 -H 1080 -b transparent
done
```

### Custom Rendering Options

```bash
# Different resolution (4K)
mmdc -i diagram.mmd -o diagram.png -w 3840 -H 2160 -b transparent

# White background
mmdc -i diagram.mmd -o diagram.png -w 1920 -H 1080 -b white

# SVG format (vector graphics, scales infinitely)
mmdc -i diagram.mmd -o diagram.svg -w 1920 -H 1080
```

---

## Integration with Documentation

### Markdown Insertion

```markdown
![Dual-Graph Architecture]
```

### PowerPoint Insertion

1. Open PowerPoint
2. Insert → Pictures → Select PNG file
3. Resize as needed (transparent background allows layering)

### GitHub Pages

Place PNG files in `docs/` directory and reference in markdown:

```markdown
![Scale-Up Sequence](diagrams/scale-up-sequence.png)
```

---

## Diagram Maintenance

### When to Update

1. **Architecture changes**: Services added/removed/renamed
2. **Flow changes**: New steps in operation sequences
3. **Algorithm changes**: New sampling algorithms or strategies
4. **Performance targets**: Updated benchmark goals

### Update Process

1. Edit `.mmd` source file
2. Re-render to PNG: `mmdc -i file.mmd -o file.png -w 1920 -H 1080 -b transparent`
3. Verify rendering quality
4. Update this README if concepts changed
5. Commit both `.mmd` and `.png` files

### Style Guidelines

- Use consistent colors across diagrams:
  - Original layer: Red (#ff6b6b)
  - Abstracted layer: Blue (#4dabf7)
  - Synthetic resources: Green (#69db7c)
  - Services: Yellow (#ffd43b)
  - Performance: Pink (#fce7f3)
- Include legends for complex diagrams
- Add performance targets as annotations
- Use clear, concise labels
- Prefer top-down or left-right flow

---

## Related Documentation

- [Scale Operations Specification](../SCALE_OPERATIONS.md)
- [Scale Operations Examples](../SCALE_OPERATIONS_E2E_DEMONSTRATION.md)
- [Neo4j Schema Reference](../NEO4J_SCHEMA_REFERENCE.md)
- [CLAUDE.md](../../CLAUDE.md) - Project overview

---

## Tools Used

- **Mermaid.js**: Diagram syntax and rendering engine
- **@mermaid-js/mermaid-cli**: Command-line rendering tool
- **Puppeteer**: Headless browser for rendering (mermaid-cli dependency)

---

## Performance Notes

Rendering times on standard VM:
- Simple diagrams (dual-graph, scale-down): ~10-15 seconds
- Complex diagrams (sequence, component): ~20-30 seconds
- All diagrams: ~1-2 minutes

For batch rendering, use the provided loop script above.

---

## Quality Checklist

Before committing diagram changes:

- [ ] Diagram renders without errors
- [ ] Text is readable at 1920x1080 resolution
- [ ] Colors are consistent with other diagrams
- [ ] Labels are clear and concise
- [ ] Arrows show correct direction
- [ ] Legend is included (if needed)
- [ ] File sizes are reasonable (<500 KB for PNG)
- [ ] Transparent background (unless specified otherwise)
- [ ] README updated if concepts changed

---

*Last Updated: 2025-11-11*
*Created by: Azure Tenant Grapher Visualization-Architect Agent*
