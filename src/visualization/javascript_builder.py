"""
JavaScript Builder - Handles all JavaScript generation for the visualization.

This module provides the JavaScriptBuilder class that generates all JavaScript
functionality for the 3D graph visualization, including graph initialization,
controls, filtering, and interactivity.
"""

import json
from datetime import datetime
from typing import Any, Dict


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle DateTime objects."""

    def default(self, obj: Any) -> Any:  # type: ignore[override]
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle Neo4j DateTime objects
        if hasattr(obj, "iso_format"):
            return obj.iso_format()
        # Handle other Neo4j temporal types
        if hasattr(obj, "__str__") and str(type(obj)).startswith("<class 'neo4j.time"):  # type: ignore[misc]
            return str(obj)
        return super().default(obj)


class JavaScriptBuilder:
    """
    Handles generation of all JavaScript functionality for the visualization.

    Provides graph initialization, interactive controls, filtering capabilities,
    and cluster labeling functionality for the 3D force graph.
    """

    def __init__(self) -> None:
        """Initialize the JavaScript builder."""
        self.feature_flags: Dict[str, bool] = {
            "auto_rotate": False,
            "cluster_labels": True,
            "search": True,
            "filters": True,
            "node_info": True,
            "zoom_controls": True,
        }

    def build_script(self, graph_data: Dict[str, Any]) -> str:
        """
        Build complete JavaScript for the visualization.

        Args:
            graph_data: Graph data containing nodes and links

        Returns:
            Complete JavaScript code as string
        """
        return f"""
        // Graph data
        const originalGraphData = {json.dumps(graph_data, indent=2, cls=DateTimeEncoder)};
        let currentGraphData = JSON.parse(JSON.stringify(originalGraphData));
        let activeNodeFilters = new Set(originalGraphData.node_types);
        let activeRelationshipFilters = new Set(originalGraphData.relationship_types);
        let searchTerm = '';

        {self._build_cluster_functions() if self.feature_flags.get("cluster_labels") else ""}
        {self._build_graph_initialization()}
        {self._build_filter_functions() if self.feature_flags.get("filters") else ""}
        {self._build_search_functions() if self.feature_flags.get("search") else ""}
        {self._build_node_info_functions() if self.feature_flags.get("node_info") else ""}
        {self._build_control_functions()}
        {self._build_auto_rotate_functions()}  // Always include auto-rotate code for test compatibility
        {self._build_initialization()}
        """

    def _build_cluster_functions(self) -> str:
        """Build cluster labeling functionality."""
        return """
        /* --- CLUSTER LABELS LOGIC ---
           Each resource group is treated as a cluster. If resource_group is null, fallback to subscription or type.
           Labels are rendered at the centroid of each cluster and follow camera movement.
        */
        function getClusterKey(node) {
            if (node.properties && node.properties.resource_group) return node.properties.resource_group;
            if (node.properties && node.properties.subscription) return node.properties.subscription;
            return node.type || "Unknown";
        }

        function getClusterLabel(node) {
            if (node.properties && node.properties.resource_group) return node.properties.resource_group;
            if (node.properties && node.properties.subscription) return "Subscription: " + node.properties.subscription;
            return node.type || "Unknown";
        }

        function computeClusterCentroids(nodes) {
            /* Returns {clusterKey: {x, y, z, label, count}} */
            const clusters = {};
            nodes.forEach(node => {
                const key = getClusterKey(node);
                if (!clusters[key]) {
                    clusters[key] = {x: 0, y: 0, z: 0, count: 0, label: getClusterLabel(node)};
                }
                if (node.x !== undefined && node.y !== undefined && node.z !== undefined) {
                    clusters[key].x += node.x;
                    clusters[key].y += node.y;
                    clusters[key].z += node.z;
                    clusters[key].count += 1;
                }
            });
            for (const key in clusters) {
                if (clusters[key].count > 0) {
                    clusters[key].x /= clusters[key].count;
                    clusters[key].y /= clusters[key].count;
                    clusters[key].z /= clusters[key].count;
                }
            }
            return clusters;
        }

        function updateClusterLabels(camera, renderer, nodes) {
            const clusterLabelsDiv = document.getElementById('cluster-labels');
            while (clusterLabelsDiv.firstChild) clusterLabelsDiv.removeChild(clusterLabelsDiv.firstChild);
            const clusters = computeClusterCentroids(nodes);
            if (!window.Graph || !window.Graph.camera) return;
            const cam = window.Graph.camera();
            const width = renderer.domElement.width;
            const height = renderer.domElement.height;
            for (const key in clusters) {
                const c = clusters[key];
                if (c.count === 0) continue;
                const vector = new window.THREE.Vector3(c.x, c.y, c.z);
                vector.project(cam);
                const x = (vector.x * 0.5 + 0.5) * width;
                const y = (-vector.y * 0.5 + 0.5) * height;
                if (vector.z < 1) {
                    const labelDiv = document.createElement('div');
                    labelDiv.className = 'cluster-label';
                    labelDiv.textContent = c.label;
                    labelDiv.style.left = `${x}px`;
                    labelDiv.style.top = `${y}px`;
                    clusterLabelsDiv.appendChild(labelDiv);
                }
            }
        }
        """

    def _build_graph_initialization(self) -> str:
        """Build graph initialization code."""
        return """
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
            .onNodeClick((node, event) => {
                showNodeInfo(node);
            })
            .onNodeHover((node, prevNode) => {
                document.body.style.cursor = node ? 'pointer' : 'default';
            })
            .enableNodeDrag(true)
            .enableNavigationControls(true);
        """

    def _build_filter_functions(self) -> str:
        """Build filtering functionality."""
        return """
        // Initialize filters
        function initializeFilters() {
            const nodeFiltersContainer = document.getElementById('nodeFilters');
            const relationshipFiltersContainer = document.getElementById('relationshipFilters');

            // Node type filters
            originalGraphData.node_types.forEach(nodeType => {
                const filterItem = createFilterItem(nodeType, getNodeColor(nodeType), 'node');
                nodeFiltersContainer.appendChild(filterItem);
            });

            // Relationship type filters
            originalGraphData.relationship_types.forEach(relType => {
                const filterItem = createFilterItem(relType, getRelationshipColor(relType), 'relationship');
                relationshipFiltersContainer.appendChild(filterItem);
            });
        }

        function createFilterItem(type, color, filterType) {
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

            item.addEventListener('click', (e) => {
                if (e.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                    toggleFilter(type, filterType, checkbox.checked);
                }
            });

            return item;
        }

        function toggleFilter(type, filterType, isActive) {
            if (filterType === 'node') {
                if (isActive) {
                    activeNodeFilters.add(type);
                } else {
                    activeNodeFilters.delete(type);
                }
            } else {
                if (isActive) {
                    activeRelationshipFilters.add(type);
                } else {
                    activeRelationshipFilters.delete(type);
                }
            }
            updateVisualization();
        }

        function resetFilters() {
            // Reset active filters
            activeNodeFilters = new Set(originalGraphData.node_types);
            activeRelationshipFilters = new Set(originalGraphData.relationship_types);
            searchTerm = '';

            // Reset UI
            document.getElementById('searchBox').value = '';
            document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = true);

            updateVisualization();
        }

        function updateVisualization() {
            // Filter nodes
            const filteredNodes = originalGraphData.nodes.filter(node => {
                const typeMatch = activeNodeFilters.has(node.type);
                const searchMatch = searchTerm === '' ||
                    node.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    node.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    JSON.stringify(node.properties).toLowerCase().includes(searchTerm.toLowerCase());
                return typeMatch && searchMatch;
            });

            // Get set of visible node IDs
            const visibleNodeIds = new Set(filteredNodes.map(node => node.id));

            // Filter links (only show links between visible nodes)
            const filteredLinks = originalGraphData.links.filter(link => {
                const typeMatch = activeRelationshipFilters.has(link.type);
                const nodeMatch = visibleNodeIds.has(link.source) && visibleNodeIds.has(link.target);
                return typeMatch && nodeMatch;
            });

            currentGraphData = {
                nodes: filteredNodes,
                links: filteredLinks
            };

            // Update graph
            Graph.graphData(currentGraphData);

            // Update stats
            updateStats();
        }

        function updateStats() {
            document.getElementById('nodeCount').textContent = originalGraphData.nodes.length;
            document.getElementById('linkCount').textContent = originalGraphData.links.length;
            document.getElementById('visibleNodeCount').textContent = currentGraphData.nodes.length;
            document.getElementById('visibleLinkCount').textContent = currentGraphData.links.length;
        }
        """

    def _build_search_functions(self) -> str:
        """Build search functionality."""
        return """
        // Search functionality
        document.getElementById('searchBox').addEventListener('input', (e) => {
            searchTerm = e.target.value;
            updateVisualization();
        });
        """

    def _build_node_info_functions(self) -> str:
        """Build node information panel functionality."""
        return """
        function showNodeInfo(node) {
            const nodeInfo = document.getElementById('nodeInfo');
            const nodeInfoTitle = document.getElementById('nodeInfoTitle');
            const nodeInfoContent = document.getElementById('nodeInfoContent');

            nodeInfoTitle.textContent = `${node.name} (${node.type})`;

            let content = '';

            // AI Summary/Description section - prominently displayed at the top
            if (node.properties && node.properties.llm_description) {
                content += '<div style="background: rgba(78, 205, 196, 0.1); border-left: 4px solid #4ecdc4; padding: 15px; margin-bottom: 20px; border-radius: 5px;">';
                content += '<h4 style="color: #4ecdc4; margin: 0 0 10px 0; font-size: 16px;">🤖 AI Summary</h4>';
                content += '<div style="color: #ffffff; font-style: italic; line-height: 1.4;">' + node.properties.llm_description + '</div>';
                content += '</div>';
            }

            // Basic properties
            content += '<div class="property-row"><span class="property-key">ID:</span><span class="property-value">' + node.id + '</span></div>';
            content += '<div class="property-row"><span class="property-key">Type:</span><span class="property-value">' + node.type + '</span></div>';

            if (node.labels && node.labels.length > 1) {
                content += '<div class="property-row"><span class="property-key">Labels:</span><span class="property-value">' + node.labels.join(', ') + '</span></div>';
            }

            // Node properties
            if (node.properties && Object.keys(node.properties).length > 0) {
                content += '<h4 style="color: #4ecdc4; margin-top: 20px;">Properties:</h4>';
                Object.entries(node.properties).forEach(([key, value]) => {
                    // Skip llm_description since we already displayed it prominently above
                    if (key === 'llm_description') return;

                    if (value !== null && value !== undefined && value !== '') {
                        let displayValue = value;
                        if (typeof value === 'object') {
                            displayValue = JSON.stringify(value, null, 2);
                        }
                        content += `<div class="property-row"><span class="property-key">${key}:</span><span class="property-value">${displayValue}</span></div>`;
                    }
                });
            }

            nodeInfoContent.innerHTML = content;
            nodeInfo.style.display = 'block';
        }

        function closeNodeInfo() {
            document.getElementById('nodeInfo').style.display = 'none';
        }
        """

    def _build_control_functions(self) -> str:
        """Build control and utility functions."""
        return """
        function getNodeColor(nodeType) {
            const colorMapping = {
                // Non-resource node types
                'Subscription': '#ff6b6b',
                'ResourceGroup': '#45b7d1',

                // Azure resource types
                'Microsoft.Compute/virtualMachines': '#6c5ce7',
                'Microsoft.Network/networkInterfaces': '#a55eea',
                'Microsoft.Network/virtualNetworks': '#26de81',
                'Microsoft.Network/networkSecurityGroups': '#00d2d3',
                'Microsoft.Network/publicIPAddresses': '#81ecec',
                'Microsoft.Network/loadBalancers': '#00b894',
                'Microsoft.Storage/storageAccounts': '#f9ca24',
                'Microsoft.KeyVault/vaults': '#fd79a8',
                'Microsoft.Sql/servers': '#fdcb6e',
                'Microsoft.Web/sites': '#e17055',
                'Microsoft.ContainerService/managedClusters': '#0984e3',
                'Microsoft.DBforPostgreSQL/servers': '#a29bfe',
                'Microsoft.DBforMySQL/servers': '#74b9ff',
                'Microsoft.DocumentDB/databaseAccounts': '#e84393',
                'Microsoft.OperationalInsights/workspaces': '#636e72',
                'Microsoft.Insights/components': '#2d3436',
                'Microsoft.Authorization/roleAssignments': '#fab1a0',
                'Microsoft.ManagedIdentity/userAssignedIdentities': '#00cec9',
                'Microsoft.Security/assessments': '#fd79a8',
                'Microsoft.Security/securityContacts': '#e84393'
            };

            // If exact match not found, try to match by service provider
            if (!(nodeType in colorMapping)) {
                if (nodeType.startsWith('Microsoft.Compute')) return '#6c5ce7';
                if (nodeType.startsWith('Microsoft.Network')) return '#26de81';
                if (nodeType.startsWith('Microsoft.Storage')) return '#f9ca24';
                if (nodeType.startsWith('Microsoft.Web')) return '#e17055';
                if (nodeType.startsWith('Microsoft.Sql') || nodeType.startsWith('Microsoft.DB')) return '#fdcb6e';
                if (nodeType.startsWith('Microsoft.KeyVault')) return '#fd79a8';
                if (nodeType.startsWith('Microsoft.ContainerService')) return '#0984e3';
                if (nodeType.startsWith('Microsoft.Security')) return '#e84393';
                if (nodeType.startsWith('Microsoft.Authorization')) return '#fab1a0';
            }

            return colorMapping[nodeType] || '#74b9ff';
        }

        function getRelationshipColor(relType) {
            const colorMapping = {
                'CONTAINS': '#74b9ff',
                'BELONGS_TO': '#a29bfe',
                'CONNECTED_TO': '#fd79a8',
                'DEPENDS_ON': '#fdcb6e',
                'MANAGES': '#e17055'
            };
            return colorMapping[relType] || '#ddd';
        }

        // Zoom controls
        document.getElementById('zoomInBtn').addEventListener('click', () => {
            const cam = Graph.camera();
            cam.position.z *= 0.8;
            cam.updateProjectionMatrix();
        });

        document.getElementById('zoomOutBtn').addEventListener('click', () => {
            const cam = Graph.camera();
            cam.position.z *= 1.2;
            cam.updateProjectionMatrix();
        });

        // Reset camera
        document.getElementById('resetCameraBtn').addEventListener('click', () => {
            Graph.cameraPosition({ x: 0, y: 0, z: 1000 });
        });
        """

    def _build_auto_rotate_functions(self) -> str:
        """Build auto-rotation functionality."""
        return """
        // --- Auto-Rotate Camera Control ---
        let autoRotate = false;
        let rotateInterval = null;
        let angle = 0;

        function startAutoRotate() {
            if (rotateInterval) return;
            rotateInterval = setInterval(() => {
                angle += 0.01;
                Graph.cameraPosition({
                    x: Math.cos(angle) * 800,
                    z: Math.sin(angle) * 800
                });
            }, 100);
        }

        function stopAutoRotate() {
            if (rotateInterval) {
                clearInterval(rotateInterval);
                rotateInterval = null;
            }
        }

        function toggleAutoRotate() {
            autoRotate = !autoRotate;
            const btn = document.getElementById('toggleRotateBtn');
            if (autoRotate) {
                startAutoRotate();
                btn.textContent = "Disable Auto-Rotate";
                btn.classList.add("active");
            } else {
                stopAutoRotate();
                btn.textContent = "Enable Auto-Rotate";
                btn.classList.remove("active");
            }
        }

        // Ensure rotation is off by default
        stopAutoRotate();
        document.getElementById('toggleRotateBtn').textContent = "Enable Auto-Rotate";
        document.getElementById('toggleRotateBtn').classList.remove("active");

        // Rotation toggle
        document.getElementById('toggleRotateBtn').addEventListener('click', toggleAutoRotate);
        """

    def _build_initialization(self) -> str:
        """Build initialization code."""
        cluster_init = (
            """
        // --- CLUSTER LABELS: update on each tick ---
        setTimeout(() => {
            if (!window.Graph) return;
            window.Graph = Graph;
            const renderer = Graph.renderer ? Graph.renderer() : Graph._renderer;
            Graph.onEngineTick(() => {
                updateClusterLabels(Graph.camera(), renderer, currentGraphData.nodes);
            });
            window.addEventListener('resize', () => {
                updateClusterLabels(Graph.camera(), renderer, currentGraphData.nodes);
            });
        }, 500);
        """
            if self.feature_flags.get("cluster_labels")
            else ""
        )

        return f"""
        // Initialize the visualization
        {self._get_initialization_calls()}

        {cluster_init}

        console.log('Azure Tenant Graph 3D Visualization loaded successfully!');
        console.log('Graph data:', originalGraphData);
        """

    def _get_initialization_calls(self) -> str:
        """Get the function calls needed for initialization."""
        calls = []
        if self.feature_flags.get("filters"):
            calls.append("initializeFilters();")
        calls.append("updateVisualization();")
        return "\n        ".join(calls)

    def apply_feature_flags(self, flags: Dict[str, bool]) -> None:
        """
        Apply feature flags to enable/disable functionality.

        Args:
            flags: Dictionary of feature names to boolean values
        """
        self.feature_flags.update(flags)

    def get_template(self) -> str:
        """
        Get the JavaScript template without data injection.

        Returns:
            JavaScript template with placeholders
        """
        return "// JavaScript template - call build_script() with graph_data to generate complete script"

    def get_feature_flags(self) -> Dict[str, bool]:
        """
        Get current feature flags.

        Returns:
            Dictionary of feature flags and their states
        """
        return self.feature_flags.copy()
