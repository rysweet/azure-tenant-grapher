# Graph Visualization

The SPA includes a comprehensive graph visualization component that displays the entire Neo4j graph with interactive features.

## Features

### Full Graph Display
- Loads and displays the entire graph from Neo4j by default
- Automatic layout using force-directed graph algorithms
- Color-coded nodes by type for easy identification
- Styled edges based on relationship types

### Interactive Controls
- **Zoom In/Out**: Scale the graph view
- **Fit to Screen**: Auto-fit all nodes in view
- **Refresh**: Reload graph data from Neo4j

### Node and Edge Statistics
- Display total node count
- Display total edge count  
- Show breakdown by node types with counts
- Show breakdown by edge types with counts

### Filtering
- **Node Type Filtering**: Click node type chips to show/hide specific node types
- **Edge Type Filtering**: Click edge type chips to show/hide specific relationship types
- Filters update the graph display in real-time

### Search Functionality
- Search nodes by name, ID, or display name
- Highlights and focuses on matching nodes
- Auto-centers on single search results

### Node Details Panel
- Click any node to view detailed information
- Shows node ID, type, and all properties
- Lists all connections with relationship types
- Displays connected node information

## Color Scheme

Node types are color-coded for easy identification:

- **Tenant**: Red (#FF6B6B)
- **Subscription**: Teal (#4ECDC4)
- **ResourceGroup**: Blue (#45B7D1)
- **Resource**: Green (#96CEB4)
- **VirtualMachine**: Yellow (#FFEAA7)
- **StorageAccount**: Light Blue (#74B9FF)
- **VirtualNetwork**: Purple (#6C5CE7)
- **User**: Pink (#FD79A8)
- **ServicePrincipal**: Orange (#FDCB6E)
- Other types use default gray

## API Endpoints

The graph visualization uses the following backend API endpoints:

- `GET /api/graph` - Fetch complete graph data
- `GET /api/graph/search?query=<term>` - Search nodes
- `GET /api/graph/node/:nodeId` - Get node details with connections

## Technical Details

- Built with React and TypeScript
- Uses vis-network library for graph rendering
- Material-UI for UI components
- Real-time filtering without server round-trips
- Optimized for large graphs with physics simulation

## Usage

1. Navigate to the "Visualize" tab in the SPA
2. The graph loads automatically on page load
3. Use mouse wheel or zoom buttons to zoom
4. Click and drag to pan around the graph
5. Click nodes to see details
6. Use filters to focus on specific parts of the graph
7. Search for specific nodes using the search bar