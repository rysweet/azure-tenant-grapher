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
            .backgroundColor('#000000') // Pure black to match GUI
            .nodeId('id')
            .nodeLabel(node => {
                // Use display_name if available (includes synthetic indicator)
                const displayName = node.display_name || node.name;
                if (node.type === "Subscription") {
                    return "Subscription: " + displayName;
                }
                return displayName;
            })
            .nodeColor(node => node.color)
            .nodeVal(node => node.size)
            .nodeThreeObject(node => {
                // Synthetic nodes get special rendering with dashed border
                if (node.synthetic) {
                    const group = new window.THREE.Group();

                    // Main sphere
                    const geometry = new window.THREE.SphereGeometry(node.size || 8, 32, 32);
                    const material = new window.THREE.MeshBasicMaterial({ color: node.color || '#FFA500' });
                    const sphere = new window.THREE.Mesh(geometry, material);
                    group.add(sphere);

                    // Dashed ring around synthetic node
                    const ringGeometry = new window.THREE.RingGeometry((node.size || 8) * 1.2, (node.size || 8) * 1.3, 32);
                    const ringMaterial = new window.THREE.LineDashedMaterial({
                        color: '#FFD700',
                        dashSize: 2,
                        gapSize: 1,
                        linewidth: 2
                    });
                    const ring = new window.THREE.Line(ringGeometry, ringMaterial);
                    ring.computeLineDistances();
                    group.add(ring);

                    // Add 'S' label for synthetic
                    const canvas = document.createElement('canvas');
                    const size = 64;
                    canvas.width = size;
                    canvas.height = size;
                    const ctx = canvas.getContext('2d');
                    ctx.font = 'bold 48px Arial';
                    ctx.fillStyle = '#FFD700';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.shadowColor = '#000';
                    ctx.shadowBlur = 4;
                    ctx.fillText('S', size / 2, size / 2);
                    const texture = new window.THREE.CanvasTexture(canvas);
                    const spriteMaterial = new window.THREE.SpriteMaterial({ map: texture, depthTest: false });
                    const sprite = new window.THREE.Sprite(spriteMaterial);
                    sprite.position.set(0, (node.size || 8) + 8, 0);
                    sprite.scale.set(8, 8, 1);
                    group.add(sprite);

                    return group;
                }

                if (node.type === "Region") {
                    // Create a sprite for always-visible region label
                    const sprite = new window.THREE.Sprite(
                        new window.THREE.SpriteMaterial({
                            map: (function() {
                                const canvas = document.createElement('canvas');
                                const size = 256;
                                canvas.width = size;
                                canvas.height = size;
                                const ctx = canvas.getContext('2d');
                                ctx.font = 'bold 48px Arial';
                                ctx.fillStyle = '#fff';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'middle';
                                ctx.shadowColor = '#000';
                                ctx.shadowBlur = 8;
                                ctx.fillText(node.name, size / 2, size / 2);
                                const texture = new window.THREE.CanvasTexture(canvas);
                                return texture;
                            })(),
                            depthTest: false
                        })
                    );
                    sprite.scale.set(40, 20, 1);
                    return sprite;
                }
                if (node.type === "Subscription") {
                    // Render Subscription nodes as a colored sphere with a floating label
                    const group = new window.THREE.Group();
                    const geometry = new window.THREE.SphereGeometry(12, 32, 32);
                    const material = new window.THREE.MeshBasicMaterial({ color: node.color || '#ff6b6b' });
                    const sphere = new window.THREE.Mesh(geometry, material);
                    group.add(sphere);

                    // Add a floating label above the sphere
                    const canvas = document.createElement('canvas');
                    const size = 256;
                    canvas.width = size;
                    canvas.height = size;
                    const ctx = canvas.getContext('2d');
                    ctx.font = 'bold 36px Arial';
                    ctx.fillStyle = '#ff6b6b';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.shadowColor = '#000';
                    ctx.shadowBlur = 8;
                    ctx.fillText("Subscription", size / 2, size / 2);
                    const texture = new window.THREE.CanvasTexture(canvas);
                    const spriteMaterial = new window.THREE.SpriteMaterial({ map: texture, depthTest: false });
                    const sprite = new window.THREE.Sprite(spriteMaterial);
                    sprite.position.set(0, 20, 0);
                    sprite.scale.set(40, 20, 1);
                    group.add(sprite);

                    return group;
                }
                if (node.type === "PrivateEndpoint") {
                    // Render PrivateEndpoint as a diamond
                    const group = new window.THREE.Group();
                    const geometry = new window.THREE.OctahedronGeometry(7, 0);
                    const material = new window.THREE.MeshBasicMaterial({ color: node.color || '#b388ff' });
                    const diamond = new window.THREE.Mesh(geometry, material);
                    group.add(diamond);
                    return group;
                }
                if (node.type === "DNSZone") {
                    // Render DNSZone as a hexagon (prism)
                    const group = new window.THREE.Group();
                    const shape = new window.THREE.Shape();
                    for (let i = 0; i < 6; i++) {
                        const angle = (i / 6) * Math.PI * 2;
                        const x = Math.cos(angle) * 8;
                        const y = Math.sin(angle) * 8;
                        if (i === 0) shape.moveTo(x, y);
                        else shape.lineTo(x, y);
                    }
                    shape.closePath();
                    const extrudeSettings = { depth: 4, bevelEnabled: false };
                    const geometry = new window.THREE.ExtrudeGeometry(shape, extrudeSettings);
                    const material = new window.THREE.MeshBasicMaterial({ color: node.color || '#00bfae' });
                    const hex = new window.THREE.Mesh(geometry, material);
                    group.add(hex);
                    return group;
                }
                return null;
            })
            .linkSource('source')
            .linkTarget('target')
            .linkColor(link => link.color)
            .linkWidth(link => link.width)
            .linkDirectionalParticles(2)
            .linkDirectionalParticleSpeed(0.01)
            .linkCurveRotation(link => {
                // Dashed for CONNECTED_TO_PE, solid for RESOLVES_TO and others
                if (link.type === "CONNECTED_TO_PE") return Math.PI / 16;
                if (link.type === "RESOLVES_TO") return 0;
                return 0;
            })
            .linkMaterial(link => {
                // Dashed for CONNECTED_TO_PE, solid for RESOLVES_TO and others
                if (link.type === "CONNECTED_TO_PE") {
                    return new window.THREE.LineDashedMaterial({
                        color: link.color || '#b388ff',
                        dashSize: 6,
                        gapSize: 4,
                        linewidth: link.width || 2
                    });
                }
                if (link.type === "RESOLVES_TO") {
                    return new window.THREE.LineBasicMaterial({
                        color: link.color || '#00bfae',
                        linewidth: link.width || 2
                    });
                }
                return new window.THREE.LineBasicMaterial({
                    color: link.color || '#ddd',
                    linewidth: link.width || 1
                });
            })
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

            // Add synthetic node filter at the top
            const syntheticFilterItem = createSyntheticFilterItem();
            nodeFiltersContainer.appendChild(syntheticFilterItem);

            // Add divider
            const divider = document.createElement('hr');
            divider.style.margin = '10px 0';
            divider.style.borderColor = 'rgba(255, 255, 255, 0.2)';
            nodeFiltersContainer.appendChild(divider);

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

        function createSyntheticFilterItem() {
            const item = document.createElement('div');
            item.className = 'filter-item synthetic-filter';
            item.style.backgroundColor = 'rgba(255, 165, 0, 0.1)';
            item.style.border = '2px dashed #FFD700';
            item.style.padding = '8px';
            item.style.marginBottom = '10px';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'filter-checkbox';
            checkbox.checked = true;
            checkbox.id = 'syntheticFilter';
            checkbox.addEventListener('change', () => toggleSyntheticFilter(checkbox.checked));

            const colorBox = document.createElement('div');
            colorBox.className = 'filter-color';
            colorBox.style.backgroundColor = '#FFA500';
            colorBox.style.border = '2px dashed #FFD700';

            const label = document.createElement('span');
            label.className = 'filter-label';
            label.style.fontWeight = 'bold';
            label.textContent = '🔶 Synthetic Nodes';

            const countLabel = document.createElement('span');
            countLabel.style.marginLeft = '8px';
            countLabel.style.color = '#FFD700';
            countLabel.style.fontSize = '0.9em';
            const syntheticCount = originalGraphData.nodes.filter(n => n.synthetic).length;
            countLabel.textContent = `(${syntheticCount})`;

            item.appendChild(checkbox);
            item.appendChild(colorBox);
            item.appendChild(label);
            item.appendChild(countLabel);

            item.addEventListener('click', (e) => {
                if (e.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                    toggleSyntheticFilter(checkbox.checked);
                }
            });

            return item;
        }

        let showSyntheticNodes = true;

        function toggleSyntheticFilter(isActive) {
            showSyntheticNodes = isActive;
            updateVisualization();
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
                const syntheticMatch = showSyntheticNodes || !node.synthetic;
                const searchMatch = searchTerm === '' ||
                    node.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    node.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    JSON.stringify(node.properties).toLowerCase().includes(searchTerm.toLowerCase());
                return typeMatch && syntheticMatch && searchMatch;
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

            // Use display_name for title if available (includes synthetic indicator)
            const displayName = node.display_name || node.name;
            nodeInfoTitle.textContent = `${displayName} (${node.type})`;

            let content = '';

            // AI Summary/Description section - prominently displayed at the top
            if (node.properties && node.properties.llm_description) {
                content += '<div style="background: rgba(78, 205, 196, 0.1); border-left: 4px solid #4ecdc4; padding: 15px; margin-bottom: 20px; border-radius: 5px;">';
                content += '<h4 style="color: #4ecdc4; margin: 0 0 10px 0; font-size: 16px;">🤖 AI Summary</h4>';
                content += '<div style="color: #ffffff; font-style: italic; line-height: 1.4;">' + node.properties.llm_description + '</div>';
                content += '</div>';
            }

            // Synthetic node indicator
            if (node.synthetic) {
                content += '<div style="background: rgba(255, 165, 0, 0.15); border: 2px dashed #FFD700; padding: 10px; margin-bottom: 15px; border-radius: 5px; text-align: center;">';
                content += '<span style="color: #FFA500; font-weight: bold; font-size: 14px;">🔶 SYNTHETIC NODE</span>';
                content += '<div style="color: #FFD700; font-size: 11px; margin-top: 5px;">This is a synthetic resource created by scale operations</div>';
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
            // Color palette aligned with GUI (GraphVisualization.tsx)
            const colorMapping = {
                // Special markers
                'Synthetic': '#FFA500', // Orange for synthetic nodes

                // Core Azure hierarchy
                'Tenant': '#FF6B6B',
                'Subscription': '#4ECDC4',
                'ResourceGroup': '#45B7D1',
                'Resource': '#96CEB4', // Fallback for generic resources
                'Region': '#FFB347', // Light orange for regions

                // Compute resources
                'VirtualMachines': '#FFEAA7',
                'VirtualMachine': '#FFEAA7',
                'Microsoft.Compute/virtualMachines': '#FFEAA7',
                'Disks': '#DDA0DD',
                'AvailabilitySets': '#F0E68C',
                'VirtualMachineScaleSets': '#FFB347',

                // Storage resources
                'StorageAccounts': '#74B9FF',
                'StorageAccount': '#74B9FF',
                'Microsoft.Storage/storageAccounts': '#74B9FF',

                // Network resources
                'VirtualNetworks': '#6C5CE7',
                'VirtualNetwork': '#6C5CE7',
                'Microsoft.Network/virtualNetworks': '#6C5CE7',
                'PrivateEndpoint': '#FF69B4', // Hot pink for private endpoints
                'NetworkInterfaces': '#A29BFE',
                'NetworkInterface': '#A29BFE',
                'Microsoft.Network/networkInterfaces': '#A29BFE',
                'NetworkSecurityGroups': '#9966CC',
                'Microsoft.Network/networkSecurityGroups': '#9966CC',
                'PublicIPAddresses': '#87CEEB',
                'Microsoft.Network/publicIPAddresses': '#87CEEB',
                'LoadBalancers': '#20B2AA',
                'Microsoft.Network/loadBalancers': '#20B2AA',
                'ApplicationGateways': '#4682B4',
                'Microsoft.Network/applicationGateways': '#4682B4',

                // Security resources
                'KeyVaults': '#DC143C',
                'Microsoft.KeyVault/vaults': '#DC143C',
                'SecurityCenter': '#8B0000',

                // Database resources
                'SqlServers': '#FF4500',
                'Microsoft.Sql/servers': '#FF4500',
                'CosmosDBAccounts': '#FF6347',
                'Microsoft.DocumentDB/databaseAccounts': '#FF6347',
                'Microsoft.DBforPostgreSQL/servers': '#FF4500',
                'Microsoft.DBforMySQL/servers': '#FF4500',

                // Web resources
                'Websites': '#32CD32',
                'Microsoft.Web/sites': '#32CD32',
                'AppServicePlans': '#228B22',
                'FunctionApps': '#9ACD32',

                // Container resources
                'ContainerInstances': '#48D1CC',
                'ContainerRegistries': '#00CED1',
                'KubernetesClusters': '#5F9EA0',
                'Microsoft.ContainerService/managedClusters': '#5F9EA0',

                // Identity and access
                'User': '#FD79A8',
                'ServicePrincipal': '#FDCB6E',
                'Application': '#E17055',
                'Group': '#00B894',
                'Role': '#00CEC9',
                'Microsoft.Authorization/roleAssignments': '#E17055',
                'Microsoft.ManagedIdentity/userAssignedIdentities': '#00CEC9',

                // Monitoring and management
                'LogAnalytics': '#CD853F',
                'ApplicationInsights': '#D2691E',
                'Microsoft.OperationalInsights/workspaces': '#CD853F',
                'Microsoft.Insights/components': '#D2691E',

                // Security
                'Microsoft.Security/assessments': '#DC143C',
                'Microsoft.Security/securityContacts': '#8B0000',

                // DNS
                'DNSZone': '#00bfae'
            };

            // If exact match not found, try to match by service provider prefix
            if (!(nodeType in colorMapping)) {
                if (nodeType.startsWith('Microsoft.Compute')) return '#FFEAA7'; // Light yellow
                if (nodeType.startsWith('Microsoft.Network')) return '#6C5CE7'; // Purple
                if (nodeType.startsWith('Microsoft.Storage')) return '#74B9FF'; // Light blue
                if (nodeType.startsWith('Microsoft.Web')) return '#32CD32'; // Green
                if (nodeType.startsWith('Microsoft.Sql') || nodeType.startsWith('Microsoft.DB')) return '#FF4500'; // Orange-red
                if (nodeType.startsWith('Microsoft.KeyVault')) return '#DC143C'; // Crimson
                if (nodeType.startsWith('Microsoft.ContainerService')) return '#5F9EA0'; // Cadet blue
                if (nodeType.startsWith('Microsoft.Security')) return '#8B0000'; // Dark red
                if (nodeType.startsWith('Microsoft.Authorization')) return '#E17055'; // Coral
                if (nodeType.startsWith('Microsoft.Insights') || nodeType.startsWith('Microsoft.OperationalInsights')) return '#CD853F'; // Peru
            }

            return colorMapping[nodeType] || '#95A5A6'; // Default gray
        }

        function getRelationshipColor(relType) {
            // Edge color palette aligned with GUI (GraphVisualization.tsx)
            const colorMapping = {
                'CONTAINS': '#2E86DE', // Blue
                'USES_IDENTITY': '#10AC84', // Green
                'CONNECTED_TO': '#FF9F43', // Orange
                'CONNECTED_TO_PE': '#b388ff', // Violet (private endpoint)
                'RESOLVES_TO': '#00bfae', // Teal-green (DNS)
                'DEPENDS_ON': '#A55EEA', // Purple
                'HAS_ROLE': '#EE5A52', // Red
                'MEMBER_OF': '#FD79A8', // Pink
                'ASSIGNED_TO': '#00CEC9', // Teal
                'MANAGES': '#FDCB6E', // Yellow
                'INHERITS': '#6C5CE7', // Indigo
                'ACCESSES': '#A29BFE', // Light Purple
                'OWNS': '#00B894', // Dark Green
                'SUBSCRIBES_TO': '#E17055', // Coral
                'PART_OF': '#74B9FF', // Light Blue
                'DELEGATES_TO': '#55A3FF', // Sky Blue
                'ENABLES': '#26DE81', // Mint Green
                'BELONGS_TO': '#A29BFE' // Light Purple (legacy)
            };
            return colorMapping[relType] || '#95A5A6'; // Default gray
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

        // Fit all nodes on initial load
        setTimeout(() => {{
            if (window.Graph && typeof window.Graph.zoomToFit === "function") {{
                window.Graph.zoomToFit(400, 50);
            }}
        }}, 600);

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
