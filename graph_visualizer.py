"""
3D Graph Visualization Module

This module provides functionality to generate interactive 3D visualizations
of the Azure resource graph using the 3d-force-graph library.
"""

import json
import logging
import os
from typing import Dict, List, Set, Optional
from datetime import datetime
import tempfile
import webbrowser

from neo4j import GraphDatabase
import colorlog

logger = colorlog.getLogger(__name__)


class GraphVisualizer:
    """Generate interactive 3D visualizations of the Neo4j graph."""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """
        Initialize the Graph Visualizer.
        
        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        
    def connect(self):
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            logger.info(f"Connected to Neo4j at {self.neo4j_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close Neo4j database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def extract_graph_data(self) -> Dict:
        """
        Extract all nodes and relationships from Neo4j for visualization.
        
        Returns:
            Dictionary containing nodes and links for the 3D graph
        """
        logger.info("Extracting graph data from Neo4j...")
        
        if not self.driver:
            self.connect()
        
        nodes = []
        links = []
        node_types = set()
        relationship_types = set()
        
        with self.driver.session() as session:
            # Extract all nodes with their properties
            node_query = """
            MATCH (n)
            RETURN n, labels(n) as node_labels
            """
            
            result = session.run(node_query)
            node_map = {}
            
            for record in result:
                node = record['n']
                labels = record['node_labels']
                
                # Use node's internal id as unique identifier
                node_id = node.element_id if hasattr(node, 'element_id') else str(node.id)
                
                # Determine primary label for node type
                primary_label = labels[0] if labels else 'Unknown'
                node_types.add(primary_label)
                
                # Extract node properties
                properties = dict(node)
                
                # Create node data structure
                node_data = {
                    'id': node_id,
                    'name': properties.get('name', properties.get('display_name', f"{primary_label}_{node_id}")),
                    'type': primary_label,
                    'labels': labels,
                    'properties': properties,
                    'group': self._get_node_group(primary_label),
                    'color': self._get_node_color(primary_label),
                    'size': self._get_node_size(primary_label, properties)
                }
                
                nodes.append(node_data)
                node_map[node_id] = node_data
            
            logger.info(f"Extracted {len(nodes)} nodes")
            
            # Extract all relationships
            relationship_query = """
            MATCH (a)-[r]->(b)
            RETURN a, r, b, type(r) as rel_type
            """
            
            result = session.run(relationship_query)
            
            for record in result:
                source_node = record['a']
                target_node = record['b']
                relationship = record['r']
                rel_type = record['rel_type']
                
                source_id = source_node.element_id if hasattr(source_node, 'element_id') else str(source_node.id)
                target_id = target_node.element_id if hasattr(target_node, 'element_id') else str(target_node.id)
                
                relationship_types.add(rel_type)
                
                # Create link data structure
                link_data = {
                    'source': source_id,
                    'target': target_id,
                    'type': rel_type,
                    'properties': dict(relationship) if relationship else {},
                    'color': self._get_relationship_color(rel_type),
                    'width': self._get_relationship_width(rel_type)
                }
                
                links.append(link_data)
            
            logger.info(f"Extracted {len(links)} relationships")
        
        return {
            'nodes': nodes,
            'links': links,
            'node_types': sorted(list(node_types)),
            'relationship_types': sorted(list(relationship_types))
        }
    
    def _get_node_group(self, node_type: str) -> int:
        """Get node group for clustering visualization."""
        group_mapping = {
            'Subscription': 1,
            'Resource': 2,
            'ResourceGroup': 3,
            'StorageAccount': 4,
            'VirtualMachine': 5,
            'NetworkInterface': 6,
            'VirtualNetwork': 7,
            'KeyVault': 8,
            'SqlServer': 9,
            'WebSite': 10
        }
        return group_mapping.get(node_type, 99)
    
    def _get_node_color(self, node_type: str) -> str:
        """Get node color based on type."""
        color_mapping = {
            'Subscription': '#ff6b6b',      # Red
            'Resource': '#4ecdc4',          # Teal
            'ResourceGroup': '#45b7d1',     # Blue
            'StorageAccount': '#f9ca24',    # Yellow
            'VirtualMachine': '#6c5ce7',    # Purple
            'NetworkInterface': '#a55eea',  # Light Purple
            'VirtualNetwork': '#26de81',    # Green
            'KeyVault': '#fd79a8',          # Pink
            'SqlServer': '#fdcb6e',         # Orange
            'WebSite': '#e17055'            # Dark Orange
        }
        return color_mapping.get(node_type, '#74b9ff')  # Default blue
    
    def _get_node_size(self, node_type: str, properties: Dict) -> int:
        """Get node size based on type and properties."""
        base_sizes = {
            'Subscription': 15,
            'Resource': 8,
            'ResourceGroup': 12,
            'StorageAccount': 10,
            'VirtualMachine': 12,
            'NetworkInterface': 6,
            'VirtualNetwork': 10,
            'KeyVault': 8,
            'SqlServer': 10,
            'WebSite': 8
        }
        return base_sizes.get(node_type, 8)
    
    def _get_relationship_color(self, rel_type: str) -> str:
        """Get relationship color based on type."""
        color_mapping = {
            'CONTAINS': '#74b9ff',
            'BELONGS_TO': '#a29bfe',
            'CONNECTED_TO': '#fd79a8',
            'DEPENDS_ON': '#fdcb6e',
            'MANAGES': '#e17055'
        }
        return color_mapping.get(rel_type, '#ddd')
    
    def _get_relationship_width(self, rel_type: str) -> int:
        """Get relationship width based on type."""
        width_mapping = {
            'CONTAINS': 3,
            'BELONGS_TO': 2,
            'CONNECTED_TO': 2,
            'DEPENDS_ON': 1,
            'MANAGES': 2
        }
        return width_mapping.get(rel_type, 1)
    
    def generate_html_visualization(self, output_path: str = None, specification_path: str = None) -> str:

        """
        Generate HTML file with interactive 3D visualization.
        
        Args:
            output_path: Path where to save the HTML file
            specification_path: Path to the tenant specification markdown file

            
        Returns:
            Path to the generated HTML file
        """
        logger.info("Generating 3D visualization HTML...")
        
        # Extract graph data
        graph_data = self.extract_graph_data()
        
        # Generate output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"azure_graph_visualization_{timestamp}.html"
        
        # Generate HTML content
        html_content = self._generate_html_template(graph_data, specification_path)

        
        # Write HTML file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"3D visualization saved to: {output_path}")
        return output_path
    
    def _generate_specification_link(self, specification_path: str) -> str:
        """Generate HTML for the tenant specification link."""
        if not specification_path or not os.path.exists(specification_path):
            return ""
        
        spec_filename = os.path.basename(specification_path)
        return f"""
        <div class="filter-section">
            <h4>Documentation</h4>
            <a href="{spec_filename}" target="_blank" class="spec-link">
                📄 View Tenant Specification
            </a>
        </div>
        """
    
    def _generate_html_template(self, graph_data: Dict, specification_path: str = None) -> str:

        """Generate the complete HTML template with embedded JavaScript."""
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure Tenant Graph - 3D Visualization</title>
    <script src="https://unpkg.com/3d-force-graph@1.72.2/dist/3d-force-graph.min.js"></script>
    <style>
        body {{
            margin: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a1a;
            color: #ffffff;
            overflow: hidden;
        }}
        
        #visualization {{
            width: 100vw;
            height: 100vh;
        }}
        
        .controls {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 1000;
            background: rgba(0, 0, 0, 0.8);
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            max-width: 300px;
            max-height: 80vh;
            overflow-y: auto;
        }}
        
        .controls h3 {{
            margin-top: 0;
            color: #4ecdc4;
            border-bottom: 2px solid #4ecdc4;
            padding-bottom: 5px;
        }}
        
        .search-box {{
            width: 100%;
            padding: 8px;
            margin-bottom: 15px;
            border: 1px solid #4ecdc4;
            border-radius: 5px;
            background: #2a2a2a;
            color: #ffffff;
            box-sizing: border-box;
        }}
        
        .filter-section {{
            margin-bottom: 20px;
        }}
        
        .filter-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
            cursor: pointer;
            padding: 3px;
            border-radius: 3px;
            transition: background-color 0.2s;
        }}
        
        .filter-item:hover {{
            background-color: rgba(78, 205, 196, 0.2);
        }}
        
        .filter-checkbox {{
            margin-right: 8px;
        }}
        
        .filter-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            border: 1px solid #ccc;
        }}
        
        .filter-label {{
            font-size: 14px;
            user-select: none;
        }}
        
        .stats {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 1000;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            font-size: 14px;
        }}
        
        .node-info {{
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(0, 0, 0, 0.9);
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            max-width: 400px;
            max-height: 80vh;
            overflow-y: auto;
            display: none;
        }}
        
        .node-info h3 {{
            margin-top: 0;
            color: #4ecdc4;
            border-bottom: 2px solid #4ecdc4;
            padding-bottom: 5px;
        }}
        
        .property-row {{
            margin: 8px 0;
            display: flex;
            flex-wrap: wrap;
        }}
        
        .property-key {{
            font-weight: bold;
            color: #fd79a8;
            margin-right: 10px;
            min-width: 100px;
        }}
        
        .property-value {{
            color: #ffffff;
            word-break: break-all;
        }}
        
        .close-btn {{
            position: absolute;
            top: 10px;
            right: 15px;
            background: none;
            border: none;
            color: #ffffff;
            font-size: 20px;
            cursor: pointer;
        }}
        
        .reset-btn {{
            background: #4ecdc4;
            color: #1a1a1a;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 10px;
            width: 100%;
        }}
        
        .reset-btn:hover {{
            background: #45b7d1;
        }}
        
        .spec-link {{
            display: block;
            color: #4ecdc4;
            text-decoration: none;
            padding: 8px 12px;
            border: 1px solid #4ecdc4;
            border-radius: 5px;
            margin-top: 5px;
            transition: all 0.3s ease;
        }}
        
        .spec-link:hover {{
            background: #4ecdc4;
            color: #1a1a1a;
        }}

    </style>
</head>
<body>
    <div id="visualization"></div>
    
    <div class="controls">
        <h3>Azure Graph Controls</h3>
        
        <input type="text" id="searchBox" class="search-box" placeholder="Search nodes..." />
        
        <div class="filter-section">
            <h4>Node Types</h4>
            <div id="nodeFilters"></div>
        </div>
        
        <div class="filter-section">
            <h4>Relationship Types</h4>
            <div id="relationshipFilters"></div>
        </div>
        
        <button class="reset-btn" onclick="resetFilters()">Reset All Filters</button>
        
        {self._generate_specification_link(specification_path)}

    </div>
    
    <div class="stats">
        <div>Nodes: <span id="nodeCount">0</span></div>
        <div>Links: <span id="linkCount">0</span></div>
        <div>Visible Nodes: <span id="visibleNodeCount">0</span></div>
        <div>Visible Links: <span id="visibleLinkCount">0</span></div>
    </div>
    
    <div class="node-info" id="nodeInfo">
        <button class="close-btn" onclick="closeNodeInfo()">&times;</button>
        <h3 id="nodeInfoTitle">Node Information</h3>
        <div id="nodeInfoContent"></div>
    </div>

    <script>
        // Graph data
        const originalGraphData = {json.dumps(graph_data, indent=2)};
        let currentGraphData = JSON.parse(JSON.stringify(originalGraphData));
        let activeNodeFilters = new Set(originalGraphData.node_types);
        let activeRelationshipFilters = new Set(originalGraphData.relationship_types);
        let searchTerm = '';
        
        // Initialize 3D force graph
        const Graph = ForceGraph3D()
            (document.getElementById('visualization'))
            .backgroundColor('#1a1a1a')
            .nodeId('id')
            .nodeLabel('name')
            .nodeColor(node => node.color)
            .nodeVal(node => node.size)
            .linkSource('source')
            .linkTarget('target')
            .linkColor(link => link.color)
            .linkWidth(link => link.width)
            .linkDirectionalParticles(2)
            .linkDirectionalParticleSpeed(0.01)
            .onNodeClick((node, event) => {{
                showNodeInfo(node);
            }})
            .onNodeHover((node, prevNode) => {{
                document.body.style.cursor = node ? 'pointer' : 'default';
            }})
            .enableNodeDrag(true)
            .enableNavigationControls(true);
        
        // Initialize filters
        function initializeFilters() {{
            const nodeFiltersContainer = document.getElementById('nodeFilters');
            const relationshipFiltersContainer = document.getElementById('relationshipFilters');
            
            // Node type filters
            originalGraphData.node_types.forEach(nodeType => {{
                const filterItem = createFilterItem(nodeType, getNodeColor(nodeType), 'node');
                nodeFiltersContainer.appendChild(filterItem);
            }});
            
            // Relationship type filters
            originalGraphData.relationship_types.forEach(relType => {{
                const filterItem = createFilterItem(relType, getRelationshipColor(relType), 'relationship');
                relationshipFiltersContainer.appendChild(filterItem);
            }});
        }}
        
        function createFilterItem(type, color, filterType) {{
            const item = document.createElement('div');
            item.className = 'filter-item';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'filter-checkbox';
            checkbox.checked = true;
            checkbox.addEventListener('change', () => toggleFilter(type, filterType, checkbox.checked));
            
            const colorBox = document.createElement('div');
            colorBox.className = 'filter-color';
            colorBox.style.backgroundColor = color;
            
            const label = document.createElement('span');
            label.className = 'filter-label';
            label.textContent = type;
            
            item.appendChild(checkbox);
            item.appendChild(colorBox);
            item.appendChild(label);
            
            item.addEventListener('click', (e) => {{
                if (e.target !== checkbox) {{
                    checkbox.checked = !checkbox.checked;
                    toggleFilter(type, filterType, checkbox.checked);
                }}
            }});
            
            return item;
        }}
        
        function getNodeColor(nodeType) {{
            const colorMapping = {{
                'Subscription': '#ff6b6b',
                'Resource': '#4ecdc4',
                'ResourceGroup': '#45b7d1',
                'StorageAccount': '#f9ca24',
                'VirtualMachine': '#6c5ce7',
                'NetworkInterface': '#a55eea',
                'VirtualNetwork': '#26de81',
                'KeyVault': '#fd79a8',
                'SqlServer': '#fdcb6e',
                'WebSite': '#e17055'
            }};
            return colorMapping[nodeType] || '#74b9ff';
        }}
        
        function getRelationshipColor(relType) {{
            const colorMapping = {{
                'CONTAINS': '#74b9ff',
                'BELONGS_TO': '#a29bfe',
                'CONNECTED_TO': '#fd79a8',
                'DEPENDS_ON': '#fdcb6e',
                'MANAGES': '#e17055'
            }};
            return colorMapping[relType] || '#ddd';
        }}
        
        function toggleFilter(type, filterType, isActive) {{
            if (filterType === 'node') {{
                if (isActive) {{
                    activeNodeFilters.add(type);
                }} else {{
                    activeNodeFilters.delete(type);
                }}
            }} else {{
                if (isActive) {{
                    activeRelationshipFilters.add(type);
                }} else {{
                    activeRelationshipFilters.delete(type);
                }}
            }}
            updateVisualization();
        }}
        
        function updateVisualization() {{
            // Filter nodes
            const filteredNodes = originalGraphData.nodes.filter(node => {{
                const typeMatch = activeNodeFilters.has(node.type);
                const searchMatch = searchTerm === '' || 
                    node.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    node.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    JSON.stringify(node.properties).toLowerCase().includes(searchTerm.toLowerCase());
                return typeMatch && searchMatch;
            }});
            
            // Get set of visible node IDs
            const visibleNodeIds = new Set(filteredNodes.map(node => node.id));
            
            // Filter links (only show links between visible nodes)
            const filteredLinks = originalGraphData.links.filter(link => {{
                const typeMatch = activeRelationshipFilters.has(link.type);
                const nodeMatch = visibleNodeIds.has(link.source) && visibleNodeIds.has(link.target);
                return typeMatch && nodeMatch;
            }});
            
            currentGraphData = {{
                nodes: filteredNodes,
                links: filteredLinks
            }};
            
            // Update graph
            Graph.graphData(currentGraphData);
            
            // Update stats
            updateStats();
        }}
        
        function updateStats() {{
            document.getElementById('nodeCount').textContent = originalGraphData.nodes.length;
            document.getElementById('linkCount').textContent = originalGraphData.links.length;
            document.getElementById('visibleNodeCount').textContent = currentGraphData.nodes.length;
            document.getElementById('visibleLinkCount').textContent = currentGraphData.links.length;
        }}
        
        function resetFilters() {{
            // Reset active filters
            activeNodeFilters = new Set(originalGraphData.node_types);
            activeRelationshipFilters = new Set(originalGraphData.relationship_types);
            searchTerm = '';
            
            // Reset UI
            document.getElementById('searchBox').value = '';
            document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = true);
            
            updateVisualization();
        }}
        
        function showNodeInfo(node) {{
            const nodeInfo = document.getElementById('nodeInfo');
            const nodeInfoTitle = document.getElementById('nodeInfoTitle');
            const nodeInfoContent = document.getElementById('nodeInfoContent');
            
            nodeInfoTitle.textContent = `${{node.name}} (${{node.type}})`;
            
            let content = '';
            
            // Basic properties
            content += '<div class="property-row"><span class="property-key">ID:</span><span class="property-value">' + node.id + '</span></div>';
            content += '<div class="property-row"><span class="property-key">Type:</span><span class="property-value">' + node.type + '</span></div>';
            
            if (node.labels && node.labels.length > 1) {{
                content += '<div class="property-row"><span class="property-key">Labels:</span><span class="property-value">' + node.labels.join(', ') + '</span></div>';
            }}
            
            // Node properties
            if (node.properties && Object.keys(node.properties).length > 0) {{
                content += '<h4 style="color: #4ecdc4; margin-top: 20px;">Properties:</h4>';
                Object.entries(node.properties).forEach(([key, value]) => {{
                    if (value !== null && value !== undefined && value !== '') {{
                        let displayValue = value;
                        if (typeof value === 'object') {{
                            displayValue = JSON.stringify(value, null, 2);
                        }}
                        content += `<div class="property-row"><span class="property-key">${{key}}:</span><span class="property-value">${{displayValue}}</span></div>`;
                    }}
                }});
            }}
            
            nodeInfoContent.innerHTML = content;
            nodeInfo.style.display = 'block';
        }}
        
        function closeNodeInfo() {{
            document.getElementById('nodeInfo').style.display = 'none';
        }}
        
        // Search functionality
        document.getElementById('searchBox').addEventListener('input', (e) => {{
            searchTerm = e.target.value;
            updateVisualization();
        }});
        
        // Initialize the visualization
        initializeFilters();
        updateVisualization();
        
        // Auto-rotate camera
        let angle = 0;
        setInterval(() => {{
            angle += 0.01;
            Graph.cameraPosition({{
                x: Math.cos(angle) * 800,
                z: Math.sin(angle) * 800
            }});
        }}, 100);
        
        console.log('Azure Tenant Graph 3D Visualization loaded successfully!');
        console.log('Graph data:', originalGraphData);
    </script>
</body>
</html>
        """
        
        return html_template
    
    def open_visualization(self, html_path: str):
        """Open the visualization in the default web browser."""
        try:
            webbrowser.open(f'file://{os.path.abspath(html_path)}')
            logger.info(f"Opened visualization in browser: {html_path}")
        except Exception as e:
            logger.error(f"Failed to open visualization in browser: {e}")
