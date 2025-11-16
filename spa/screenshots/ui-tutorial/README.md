# Scale Operations UI Tutorial

Professional visual walkthrough of the Scale Operations feature in Azure Tenant Grapher.

## Overview

This tutorial provides step-by-step annotated screenshots showing how to use Scale Operations through the graphical user interface. Scale Operations allows you to add synthetic test resources (Scale-Up) or remove resources for testing and validation (Scale-Down).

## Tutorial Flow

### 1. Getting Started
**File:** `tutorial-01-getting-started.png`

Learn how to:
- Navigate to the Scale Operations tab
- Choose between Scale-Up (add nodes) and Scale-Down (sample/remove nodes)
- Understand the two operation modes

**Key Concepts:**
- Scale-Up: Add synthetic test resources to your graph for load testing and validation
- Scale-Down: Remove resources in controlled patterns for testing cleanup or graph reduction

---

### 2. Template Strategy (Scale-Up)
**File:** `tutorial-02-template-strategy.png`

Configure template-based scaling:
- Select "Template-Based" strategy
- Choose a predefined YAML template file
- Set the scale factor (multiplier)

**Key Concepts:**
- Templates define resource patterns that are multiplied by the scale factor
- Example: 2x scale factor doubles all resources in the template
- Templates ensure consistent, reproducible resource generation

---

### 3. Scenario Strategy (Scale-Up)
**File:** `tutorial-03-scenario-selection.png`

Generate realistic Azure architectures:
- Select "Scenario-Based" strategy
- Choose a scenario (Hub-Spoke, Multi-Region, Microservices, etc.)
- Configure scenario parameters (number of spokes, regions, etc.)

**Key Concepts:**
- Scenarios create realistic Azure topologies
- Hub-Spoke: Central hub VNet with multiple spoke VNets
- Each scenario has specific parameters to customize the generated architecture

---

### 4. Scale Factor Configuration
**File:** `tutorial-04-scale-factor.png`

Control operation intensity:
- Drag the slider to set scale factor (1-100)
- For Template strategy: multiplies resources
- For Random strategy: controls resource count
- Enable validation (recommended)

**Key Concepts:**
- Higher scale factor = more resources (more intensive testing)
- Lower scale factor = fewer resources (lighter testing)
- Validation ensures graph integrity before and after operations

---

### 5. Preview & Execute
**File:** `tutorial-05-preview-execute.png`

Safe execution workflow:
1. **Preview First**: See exactly what will be created/removed
2. **Then Execute**: Apply the changes to your graph

**IMPORTANT:**
- Always preview before executing
- Preview is non-destructive and shows planned changes
- Execute applies the changes permanently

---

### 6. Quick Actions
**File:** `tutorial-06-quick-actions.png`

Post-operation management tools:
- **CLEAN**: Remove all scaled resources (cleanup test data)
- **VALIDATE**: Check graph integrity and relationship consistency
- **STATS**: View detailed operation metrics and statistics

**Key Concepts:**
- Use CLEAN after testing to remove synthetic data
- Use VALIDATE to verify graph correctness
- Use STATS to analyze operation impact

---

### 7. Validation Options
**File:** `tutorial-07-validation-options.png`

Configure validation behavior:
- Run validation before operations (pre-validation)
- Run validation after operations (post-validation)
- Check graph integrity, relationships, and constraints

**Key Concepts:**
- Validation catches issues before they become problems
- Pre-validation ensures graph is ready for operations
- Post-validation confirms operation success

---

### 8. Scale-Down Mode
**File:** `tutorial-08-scale-down.png`

Remove resources strategically:
- Switch to Scale-Down mode
- Choose removal strategy (Random, Forest Fire, Target-Based)
- Configure strategy parameters (start node, depth, etc.)

**Key Concepts:**
- Random: Remove nodes randomly across the graph
- Forest Fire: Cascading removal starting from a node
- Target-Based: Remove specific node types or patterns

---

## Common Workflows

### Workflow 1: Add Test Resources (Template)
1. Click Scale Operations tab
2. Select SCALE UP mode
3. Choose "Template-Based" strategy
4. Select template file (e.g., `templates/scale_up_template.yaml`)
5. Set scale factor (e.g., 2x for double)
6. Enable validation
7. Click PREVIEW to verify
8. Click EXECUTE to apply
9. Use STATS to view results

### Workflow 2: Generate Hub-Spoke Architecture
1. Click Scale Operations tab
2. Select SCALE UP mode
3. Choose "Scenario-Based" strategy
4. Select "Hub-Spoke Network" scenario
5. Set number of spokes (e.g., 3)
6. Enable validation
7. Click PREVIEW to verify
8. Click EXECUTE to apply
9. Use VALIDATE to check integrity

### Workflow 3: Clean Up Test Data
1. Click Scale Operations tab
2. Use Quick Actions section
3. Click CLEAN button
4. Confirm removal of scaled resources
5. Use VALIDATE to verify cleanup

### Workflow 4: Scale-Down with Forest Fire
1. Click Scale Operations tab
2. Select SCALE DOWN mode
3. Choose "Forest Fire" strategy
4. Select start node (where removal begins)
5. Set depth/spread parameters
6. Click PREVIEW to verify
7. Click EXECUTE to apply

---

## Tips and Best Practices

1. **Always Preview First**
   - Never execute without previewing
   - Preview shows exact changes without side effects
   - Helps catch configuration mistakes

2. **Use Validation**
   - Enable validation for production-like testing
   - Validation catches graph integrity issues
   - Post-validation confirms successful operations

3. **Start Small**
   - Use low scale factors initially
   - Test with small scenarios first
   - Gradually increase complexity

4. **Clean Up Regularly**
   - Use CLEAN after each test session
   - Prevents graph bloat from test data
   - Keeps graph focused on real resources

5. **Monitor with Stats**
   - Use STATS to understand operation impact
   - Track nodes created/removed
   - Analyze relationship changes

6. **Choose Right Strategy**
   - Template: Reproducible patterns
   - Scenario: Realistic architectures
   - Random: Quick testing with variety
   - Forest Fire: Cascading removal testing

---

## Screenshot Details

All screenshots are:
- **Resolution**: 1920x1080
- **Format**: PNG
- **Annotations**:
  - Gold boxes highlight key UI elements
  - Orange arrows point to important areas
  - Blue labels explain each step
  - Callout boxes provide context and tips

## Annotation Script

The annotations were created using `annotate_screenshots.py`, which uses:
- **Pillow (PIL)**: Professional image manipulation
- **Custom annotation classes**: Boxes, arrows, labels, callouts
- **Consistent styling**: Professional blue/gold/orange color scheme

To regenerate annotations:
```bash
cd /home/azureuser/src/atg/worktrees/feat-issue-427-scale-operations/spa/screenshots/ui-tutorial
uv run python annotate_screenshots.py
```

---

## Related Documentation

- **Scale Operations Specification**: `/docs/SCALE_OPERATIONS_SPECIFICATION.md`
- **Scale Operations Index**: `/docs/SCALE_OPERATIONS_INDEX.md`
- **Quick Reference**: `/spa/screenshots/scale-operations/QUICK_REFERENCE.md`
- **Full Screenshot Set**: `/spa/screenshots/scale-operations/README.md`

---

## Feedback and Improvements

This tutorial is designed to be:
- **Visual**: Learn by seeing annotated examples
- **Progressive**: Build from basics to advanced features
- **Practical**: Focus on common workflows
- **Professional**: Clear, consistent, production-ready

For questions or suggestions, refer to the main Scale Operations documentation or the project CLAUDE.md file.

---

**Created**: 2025-11-11
**Version**: 1.0
**Author**: Azure Tenant Grapher Team
**Tool**: Claude Code AI Assistant
