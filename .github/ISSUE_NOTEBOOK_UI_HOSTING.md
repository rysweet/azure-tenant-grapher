# Feature Request: Notebook UI Hosting in SPA

## Overview

Add capability to host and interact with Jupyter notebooks directly within the Azure Tenant Grapher SPA (Electron GUI and Web App mode).

## Background

The `atg report well-architected` command generates interactive Jupyter notebooks with Well-Architected Framework analysis. Currently, users must open these notebooks separately in Jupyter. This feature would enable viewing and interacting with notebooks directly in the ATG interface.

## Feature Requirements

### Part 1: Design Notebook Hosting Component

Create a reusable React component that can render and host Jupyter notebooks in the SPA.

**Technical Requirements:**
- Component should accept a notebook file path or URL
- Render notebook cells (markdown, code, outputs)
- Support syntax highlighting for code cells
- Display outputs (text, tables, plots, HTML)
- Read-only mode initially (editable mode is stretch goal)
- Responsive design that works in both Electron and web modes

**Suggested Libraries:**
- `@nteract/notebook-render` or `@nteract/presentational-components` - React components for notebook rendering
- `react-jupyter-notebook` - Alternative notebook renderer
- `prism-react-renderer` or `react-syntax-highlighter` - Code highlighting
- `plotly.js` or similar - For interactive visualizations

**Component API Example:**
```typescript
interface NotebookViewerProps {
  notebookPath?: string;
  notebookUrl?: string;
  notebookData?: NotebookFormat;
  readOnly?: boolean;
  onError?: (error: Error) => void;
}

<NotebookViewer
  notebookPath="/outputs/well_architected_report_20250101/well_architected_analysis.ipynb"
  readOnly={true}
/>
```

### Part 2: Add Well-Architected Report Tab

Add a new tab to the SPA that uses the notebook hosting component to display Well-Architected Framework reports.

**Tab Features:**
- List available Well-Architected reports (from `outputs/well_architected_report_*`)
- Select and view reports in the notebook viewer
- Show report metadata (generation time, patterns detected, etc.)
- Export functionality (download notebook, markdown, JSON)
- Re-generate report button (triggers `atg report well-architected`)

**UI/UX Requirements:**
- Tab icon: 🏗️ or similar architecture/framework icon
- Sidebar with report list (newest first)
- Main pane with notebook viewer
- Action buttons: Refresh, Export, Generate New Report
- Loading states for notebook rendering
- Error handling for missing or corrupt notebooks

## Implementation Plan

### Phase 1: Research & Design (Week 1)
- [ ] Evaluate notebook rendering libraries
- [ ] Create component design and API
- [ ] Design tab mockups/wireframes
- [ ] Determine file loading strategy (local vs API endpoint)

### Phase 2: Component Development (Week 2)
- [ ] Implement basic notebook renderer component
- [ ] Add syntax highlighting for code cells
- [ ] Implement output rendering (text, HTML, images)
- [ ] Add responsive styling
- [ ] Write component tests

### Phase 3: Tab Integration (Week 3)
- [ ] Add "Well-Architected" tab to navigation
- [ ] Implement report list sidebar
- [ ] Integrate notebook viewer component
- [ ] Add report generation trigger
- [ ] Implement export functionality

### Phase 4: Polish & Testing (Week 4)
- [ ] Add loading states and error handling
- [ ] Implement report refresh
- [ ] E2E testing
- [ ] Documentation
- [ ] Screenshots for README

## Success Criteria

- [ ] Users can view Well-Architected reports without leaving the SPA
- [ ] Component is reusable for other notebook types
- [ ] Works in both Electron and web app modes
- [ ] Renders all common notebook elements correctly
- [ ] Performance is acceptable for typical report sizes
- [ ] Error states are handled gracefully

## Technical Considerations

1. **File Loading**
   - Electron mode: Direct file system access
   - Web mode: Need API endpoint to serve notebook files
   - Solution: Backend API endpoint `/api/reports/notebooks/:reportId`

2. **Security**
   - Sanitize notebook HTML output to prevent XSS
   - Validate notebook JSON structure
   - Restrict file paths to outputs directory only

3. **Performance**
   - Large notebooks may be slow to render
   - Consider lazy loading cells
   - Virtualize long notebook lists

4. **Compatibility**
   - Support Jupyter Notebook format (nbformat v4)
   - Handle notebooks with various output types
   - Graceful degradation for unsupported features

## Future Enhancements

- [ ] Interactive code execution (connect to Jupyter kernel)
- [ ] Collaborative viewing/annotations
- [ ] Notebook diff/comparison
- [ ] Export to PDF/HTML
- [ ] Embedded data visualizations (plotly, d3.js)
- [ ] Search within notebooks
- [ ] Bookmark specific cells

## Related Issues

- Architectural Pattern Analysis (#XXX)
- Well-Architected Reporter (#XXX)

## References

- [nteract Components](https://github.com/nteract/nteract)
- [Jupyter Notebook Format](https://nbformat.readthedocs.io/)
- [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/)

---

**Labels**: `enhancement`, `spa`, `ui`, `notebooks`, `well-architected`
**Priority**: Medium
**Effort**: Large (2-4 weeks)
