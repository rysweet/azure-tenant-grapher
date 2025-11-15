# Scale Operations UI Screenshots

Comprehensive collection of screenshots captured for the Scale Operations feature in Azure Tenant Grapher SPA.

**Purpose:** PowerPoint presentations, documentation, and feature demonstrations.

**Resolution:** 1920x1080 (Full HD)

**Captured:** 2025-11-11

---

## Screenshot Index

### 01. Initial State - Scale-Up Mode Selected
**File:** `01-initial-scale-up.png`

**Description:** The Scale Operations tab in its initial state with Scale-Up mode selected. Shows the clean, professional UI with the operation mode toggle at the top, featuring both Scale-Up and Scale-Down options. The Scale-Up configuration panel is displayed below with strategy selection and form fields.

**Key Elements:**
- Page title and description
- Operation mode toggle (Scale-Up highlighted)
- Strategy selection dropdown
- Template file input field
- Scale factor slider
- Validation checkbox
- Execute and Preview buttons

**Use Case:** Introduce the Scale Operations feature and show the default view when users first access the tab.

---

### 02. Scale-Down Mode Selected
**File:** `02-scale-down-mode.png`

**Description:** The interface after switching to Scale-Down mode. This demonstrates the alternative operation mode that allows users to sample or reduce the graph size for testing purposes.

**Key Elements:**
- Scale-Down toggle button highlighted
- Different configuration panel focused on graph sampling
- Algorithm selection for sampling strategy
- Target node count input
- Options to preserve relationships and critical nodes

**Use Case:** Show the flexibility of the Scale Operations feature with both scale-up and scale-down capabilities.

---

### 03. Scale-Up Template Strategy Form
**File:** `03-template-strategy-form.png`

**Description:** Detailed view of the Template strategy form for Scale-Up operations. This strategy allows users to generate nodes based on predefined YAML templates.

**Key Elements:**
- Strategy selector set to "Template"
- Template file path input (with browse button)
- Scale factor slider (multiplier for template-defined quantities)
- Description text explaining template-based generation
- Validation options checkbox

**Use Case:** Demonstrate template-based scaling for repeatable, controlled infrastructure generation.

---

### 04. Scale-Up Scenario Strategy (Hub-Spoke)
**File:** `04-scenario-hub-spoke.png`

**Description:** The Scenario strategy interface showing the hub-spoke network topology option. This demonstrates pre-built scenario templates for common Azure architectures.

**Key Elements:**
- Strategy selector set to "Scenario"
- Scenario type dropdown with "hub-spoke" selected
- Visual or textual description of hub-spoke topology
- Configuration options specific to hub-spoke architecture

**Use Case:** Highlight the scenario-based approach for generating realistic Azure architectures without custom templates.

---

### 05. Scale-Up Random Strategy Form
**File:** `05-random-strategy-form.png`

**Description:** Random strategy configuration for generating synthetic nodes with configurable patterns. Useful for stress testing and graph algorithm validation.

**Key Elements:**
- Strategy selector set to "Random"
- Node count input field (showing 5000 nodes)
- Pattern selection for distribution characteristics
- Options for randomization seed and resource type distribution

**Use Case:** Show the random generation capability for large-scale testing and graph performance evaluation.

---

### 06. Scale-Down with Forest Fire Algorithm
**File:** `06-scale-down-forest-fire.png`

**Description:** Scale-Down configuration using the Forest Fire sampling algorithm. This algorithm preserves graph structure while reducing size, making it ideal for creating representative subgraphs.

**Key Elements:**
- Scale-Down mode active
- Algorithm dropdown set to "Forest Fire"
- Target node count input (showing 500 nodes)
- Algorithm-specific parameters (burn probability, forward/backward ratios)
- Explanation of Forest Fire sampling approach

**Use Case:** Demonstrate intelligent graph sampling for creating smaller, representative test environments.

---

### 07. Ready for Preview
**File:** `07-ready-for-preview.png`

**Description:** The interface state when the form is filled out and ready for preview. Shows enabled action buttons and complete configuration.

**Key Elements:**
- Fully configured form with all required fields filled
- Preview button highlighted and enabled
- Execute button also enabled
- Clear button available for form reset

**Use Case:** Show the user flow before executing an operation, emphasizing the preview capability for validating configurations.

---

### 08. Ready for Execution
**File:** `08-ready-for-execution.png`

**Description:** Similar to screenshot 07 but with emphasis on the Execute button. This represents the final state before running the scale operation.

**Key Elements:**
- Complete configuration
- Execute button prominently displayed
- All validation checks passed
- Ready state indicator

**Use Case:** Final step in the configuration workflow before launching the operation.

---

### 09. Quick Actions Menu
**File:** `09-quick-actions.png`

**Description:** The Quick Actions bar at the bottom of the interface, providing convenient access to common operations and utilities.

**Key Elements:**
- Quick action buttons for:
  - View operation history
  - Load saved templates
  - Export configuration
  - Clear form
  - Help/documentation
- Persistent placement at bottom of panel

**Use Case:** Highlight the convenience features and workflow enhancements available in the UI.

---

### 10. Validation Options
**File:** `10-validation-options.png`

**Description:** Detailed view of the validation checkbox and options. Shows the ability to enable/disable validation and configure validation rules.

**Key Elements:**
- Validation checkbox (checked state)
- Validation options expanded or visible
- Explanation of what validation checks
- Potential warnings or validation result indicators

**Use Case:** Demonstrate the safety features and validation capabilities that help prevent configuration errors.

---

### 11. Scale Factor Slider (Template Mode)
**File:** `11-scale-factor-slider.png`

**Description:** Close-up or emphasized view of the scale factor slider control in Template strategy mode. Shows how users can easily adjust the multiplier for template-based generation.

**Key Elements:**
- Scale factor slider control
- Current value display (e.g., "2x")
- Min/max labels (typically 1-10x)
- Live preview of what the scale factor means (if available)

**Use Case:** Highlight the intuitive UI control for adjusting generation scale.

---

### 12. Complete Scale-Up Configuration Form
**File:** `12-complete-form.png`

**Description:** A fully completed Scale-Up form with all fields filled in with realistic sample data. This provides a comprehensive view of a production-ready configuration.

**Key Elements:**
- Tenant ID populated
- Template file path specified
- Scale factor set
- Validation enabled
- All required fields completed
- Form in valid state

**Use Case:** Show a complete, real-world example configuration ready for execution.

---

### 13. Scale-Down Complete Configuration
**File:** `13-scale-down-complete.png`

**Description:** A fully completed Scale-Down form showing a production-ready sampling configuration.

**Key Elements:**
- Target node count set (e.g., 1000)
- Algorithm selected
- Preserve relationships option checked
- Complete configuration ready for execution

**Use Case:** Demonstrate a complete Scale-Down workflow configuration.

---

### 14. Help Text and Tooltips
**File:** `14-help-text.png`

**Description:** The interface showing help text, tooltips, or information icons that provide contextual guidance to users.

**Key Elements:**
- Info icons visible
- Tooltip popup (if captured during hover)
- Help text explaining field purposes
- User guidance elements

**Use Case:** Highlight the user-friendly design with built-in help and documentation.

---

## Usage Notes

### For PowerPoint Presentations

1. **Slide Order Recommendation:**
   - Start with screenshot 01 (initial state) to introduce the feature
   - Show screenshots 02-06 to demonstrate different strategies and modes
   - Use screenshots 07-08 to show the user workflow
   - Include screenshot 09 to highlight convenience features
   - Use screenshots 10-14 for detailed feature explanations

2. **Image Insertion:**
   - All images are 1920x1080, suitable for full-screen display
   - For best quality, insert at actual size or scale down proportionally
   - Consider cropping to focus on specific UI elements if needed

3. **Annotations:**
   - Add arrows or highlights to draw attention to specific features
   - Use consistent color scheme matching Azure/ATG branding
   - Add callout boxes for detailed explanations

### For Documentation

1. **Markdown/HTML:**
   ```markdown
   ![Scale Operations Initial State](screenshots/scale-operations/01-initial-scale-up.png)
   ```

2. **README Files:**
   - Link to this index for detailed descriptions
   - Embed screenshots inline for quick reference

3. **User Guides:**
   - Use sequential screenshots to create step-by-step tutorials
   - Combine with written instructions for clarity

### Technical Details

**Capture Method:** Playwright automated browser testing
**Browser:** Chromium (headless mode)
**Test Script:** `spa/tests/e2e/screenshot-scale-ops.spec.ts`

**Regeneration:**
To regenerate these screenshots:
```bash
cd spa
npm run dev:renderer  # Start dev server
npx playwright test screenshot-scale-ops.spec.ts --project=chromium
```

---

## Feature Coverage

This screenshot collection comprehensively covers:

- ✅ Both operation modes (Scale-Up and Scale-Down)
- ✅ All three Scale-Up strategies (Template, Scenario, Random)
- ✅ Multiple Scale-Down algorithms (Forest Fire shown)
- ✅ Form validation and ready states
- ✅ Quick actions and convenience features
- ✅ Help text and user guidance
- ✅ Complete configuration examples

---

## Additional Screenshots Needed (Future)

For complete documentation, consider capturing:

1. **Progress Monitor:** Active operation with progress bars and status updates
2. **Results Panel:** Completed operation showing statistics and outcomes
3. **Error States:** Validation errors and warning messages
4. **Statistics Modal:** Detailed operation statistics and metrics
5. **Operation History:** List of past operations with timestamps
6. **Template Browser:** File selection dialog for templates
7. **Export Dialog:** Configuration export functionality

Note: These require backend integration or mocked responses and were not captured in this session.

---

## Questions or Issues?

For questions about these screenshots or to request additional captures, please contact the development team or file an issue in the repository.

**Last Updated:** 2025-11-11
**Generated By:** Playwright automated screenshot capture
**Feature:** Scale Operations (Issue #427)
