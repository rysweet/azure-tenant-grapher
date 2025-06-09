## Overview
This PR adds a new 3D interactive visualization feature to the Azure Tenant Grapher project using the 3d-force-graph library.

## Features Added
- **Interactive 3D Graph Visualization**: Generate stunning 3D visualizations of Azure resource graphs with force-directed layout
- **Comprehensive Controls**: Legend, filtering by node/relationship type, search functionality, and detailed node metadata display
- **Flexible CLI Integration**: New command-line options for visualization generation and management
- **Cross-Platform Support**: Updated shell scripts for both Unix/Linux and Windows environments

## Changes Made
### New Files
- `graph_visualizer.py`: Core visualization module with Neo4j integration and HTML generation
- Updated `.vscode/tasks.json`: Added VS Code tasks for visualization workflows

### Modified Files
- `azure_tenant_grapher.py`: Enhanced with visualization capabilities and new CLI options
- `README.md`: Comprehensive documentation updates with usage examples
- `run-grapher.sh` & `run-grapher.ps1`: Updated scripts with new visualization options

## CLI Options Added
- `--visualize`: Generate visualization after building the graph
- `--visualize-only`: Generate visualization from existing Neo4j data without rebuilding
- `--visualization-path`: Specify custom output path for the HTML file

## Technical Details
- Uses 3d-force-graph library for interactive 3D rendering
- Connects to Neo4j database to extract graph data
- Generates self-contained HTML files with embedded JavaScript
- Supports real-time filtering, search, and node interaction
- Maintains backward compatibility with existing functionality

## Testing
- ✅ Module imports and CLI help functionality
- ✅ HTML template generation with sample data
- ✅ Dependency installation and integration
- ✅ Cross-platform script compatibility

## Usage Examples
```bash
# Generate visualization after building graph
python azure_tenant_grapher.py --tenant-id YOUR_TENANT_ID --visualize

# Generate visualization only from existing data
python azure_tenant_grapher.py --tenant-id dummy --visualize-only

# Specify custom output path
python azure_tenant_grapher.py --tenant-id dummy --visualize-only --visualization-path /custom/path/graph.html
```

Ready for review and testing!
