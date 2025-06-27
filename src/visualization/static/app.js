// SPA main JS for Azure Tenant Graph - 3D Visualization
// Matches CLI HTML output: controls, filters, search, node info, cluster labels, stats

document.addEventListener("DOMContentLoaded", function () {
    // --- Progress Bar Elements ---
    const progressBar = document.getElementById('progress-bar');
    const progressBarInner = document.getElementById('progress-bar-inner');
    const vizDiv = document.getElementById('visualization');

    // --- Graph Data Fetch ---
    let originalGraphData = null;
    let currentGraphData = null;
    let activeNodeFilters = new Set();
    let activeRelationshipFilters = new Set();
    let searchTerm = '';

    // --- UI Elements ---
    const nodeCountEl = document.getElementById('nodeCount');
    const linkCountEl = document.getElementById('linkCount');
    const visibleNodeCountEl = document.getElementById('visibleNodeCount');
    const visibleLinkCountEl = document.getElementById('visibleLinkCount');
    const nodeFiltersContainer = document.getElementById('nodeFilters');
    const relationshipFiltersContainer = document.getElementById('relationshipFilters');
    const searchBox = document.getElementById('searchBox');
    const nodeInfo = document.getElementById('nodeInfo');
    const nodeInfoTitle = document.getElementById('nodeInfoTitle');
    const nodeInfoContent = document.getElementById('nodeInfoContent');
    const specLink = document.getElementById('specLink');

    // --- 3D Force Graph Setup ---
    let Graph = null;
    let THREE = null;

    // --- Show Progress Bar ---
    function showProgressBar() {
        progressBar.style.display = "";
        progressBarInner.style.width = "0";
    }
    function setProgressBar(percent) {
        progressBarInner.style.width = percent + "%";
    }
    function hideProgressBar() {
        progressBar.style.display = "none";
        progressBarInner.style.width = "0";
    }

    // --- Fallback for Graph Not Visible ---
    function showGraphError(msg) {
        vizDiv.innerHTML = `<div style="color:#fff;background:#c00;padding:2em;text-align:center;font-size:1.2em;">${msg}</div>`;
    }

    // --- Fetch Graph Data and Initialize ---
    showProgressBar();
    setProgressBar(10);
    fetch("/api/graph")
        .then(resp => {
            setProgressBar(30);
            return resp.json();
        })
        .then(data => {
            setProgressBar(60);
            console.log("[SPA] /api/graph data received:", data);
            originalGraphData = data;
            currentGraphData = JSON.parse(JSON.stringify(data));
            activeNodeFilters = new Set(data.node_types);
            activeRelationshipFilters = new Set(data.relationship_types);

            console.log("[SPA] node_types:", data.node_types, "relationship_types:", data.relationship_types);
            console.log("[SPA] nodes.length:", data.nodes.length, "links.length:", data.links.length);

            if (!data.nodes || !data.links || data.nodes.length === 0 || data.links.length === 0) {
                showGraphError("Graph data loaded, but no nodes or links found. Please check your database.");
                hideProgressBar();
                return;
            }

            initializeFilters();
            updateVisualization();
            setProgressBar(80);
            setupGraph();
            updateStats();
            setProgressBar(100);
            setTimeout(hideProgressBar, 500);
            // Optionally, set spec link if available
            if (data.specification_path) {
                specLink.href = data.specification_path;
                specLink.style.display = "";
            }
        })
        .catch(e => {
            showGraphError("Failed to load graph data: " + e);
            hideProgressBar();
            console.error("[SPA] Failed to load /api/graph:", e);
        });

    function ensureTHREE() {
        if (window.THREE) {
            THREE = window.THREE;
            return true;
        }
        // Try to find THREE from 3d-force-graph
        if (window.ForceGraph3D && window.ForceGraph3D.THREE) {
            THREE = window.ForceGraph3D.THREE;
            return true;
        }
        return false;
    }

    function setupGraph() {
        if (!ensureTHREE()) {
            setTimeout(setupGraph, 100);
            return;
        }
        // Defensive: clear any fallback error
        vizDiv.innerHTML = "";
        vizDiv.style.background = "#1a1a1a";
        vizDiv.style.width = "100vw";
        vizDiv.style.height = "100vh";
        console.log("[SPA] Initializing ForceGraph3D with nodes:", currentGraphData.nodes.length, "links:", currentGraphData.links.length);
        Graph = ForceGraph3D()
            (vizDiv)
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
            .onNodeClick((node, event) => { showNodeInfo(node); })
            .onNodeHover((node, prevNode) => {
                document.body.style.cursor = node ? 'pointer' : 'default';
            })
            .enableNodeDrag(true)
            .enableNavigationControls(true);

        Graph.graphData(currentGraphData);

        // Cluster labels
        setTimeout(() => {
            if (!window.Graph) window.Graph = Graph;
            const renderer = Graph.renderer ? Graph.renderer() : Graph._renderer;
            Graph.onEngineTick(() => {
                updateClusterLabels(Graph.camera(), renderer, currentGraphData.nodes);
            });
            window.addEventListener('resize', () => {
                updateClusterLabels(Graph.camera(), renderer, currentGraphData.nodes);
            });
        }, 500);

        // Fit all nodes on initial load
        setTimeout(() => {
            if (window.Graph && typeof window.Graph.zoomToFit === "function") {
                window.Graph.zoomToFit(400, 50);
            }
        }, 600);
    }

    // --- Filters ---
    function initializeFilters() {
        nodeFiltersContainer.innerHTML = "";
        relationshipFiltersContainer.innerHTML = "";
        originalGraphData.node_types.forEach(nodeType => {
            const filterItem = createFilterItem(nodeType, getNodeColor(nodeType), 'node');
            nodeFiltersContainer.appendChild(filterItem);
        });
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
            if (isActive) activeNodeFilters.add(type);
            else activeNodeFilters.delete(type);
        } else {
            if (isActive) activeRelationshipFilters.add(type);
            else activeRelationshipFilters.delete(type);
        }
        updateVisualization();
    }

    window.resetFilters = function() {
        activeNodeFilters = new Set(originalGraphData.node_types);
        activeRelationshipFilters = new Set(originalGraphData.relationship_types);
        searchTerm = '';
        searchBox.value = '';
        document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = true);
        updateVisualization();
    };

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

        if (Graph) {
            console.log("[SPA] Updating graphData: nodes", currentGraphData.nodes.length, "links", currentGraphData.links.length);
            Graph.graphData(currentGraphData);
        }
        updateStats();
    }

    function updateStats() {
        nodeCountEl.textContent = originalGraphData.nodes.length;
        linkCountEl.textContent = originalGraphData.links.length;
        visibleNodeCountEl.textContent = currentGraphData.nodes.length;
        visibleLinkCountEl.textContent = currentGraphData.links.length;
    }

    // --- Search ---
    searchBox.addEventListener('input', (e) => {
        searchTerm = e.target.value;
        updateVisualization();
    });

    // --- Node Info Panel ---
    window.showNodeInfo = function(node) {
        nodeInfoTitle.textContent = `${node.name} (${node.type})`;
        let content = '';
        if (node.properties && node.properties.llm_description) {
            content += '<div style="background: rgba(78, 205, 196, 0.1); border-left: 4px solid #4ecdc4; padding: 15px; margin-bottom: 20px; border-radius: 5px;">';
            content += '<h4 style="color: #4ecdc4; margin: 0 0 10px 0; font-size: 16px;">🤖 AI Summary</h4>';
            content += '<div style="color: #ffffff; font-style: italic; line-height: 1.4;">' + node.properties.llm_description + '</div>';
            content += '</div>';
        }
        content += '<div class="property-row"><span class="property-key">ID:</span><span class="property-value">' + node.id + '</span></div>';
        content += '<div class="property-row"><span class="property-key">Type:</span><span class="property-value">' + node.type + '</span></div>';
        if (node.labels && node.labels.length > 1) {
            content += '<div class="property-row"><span class="property-key">Labels:</span><span class="property-value">' + node.labels.join(', ') + '</span></div>';
        }
        if (node.properties && Object.keys(node.properties).length > 0) {
            content += '<h4 style="color: #4ecdc4; margin-top: 20px;">Properties:</h4>';
            Object.entries(node.properties).forEach(([key, value]) => {
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
    };
    window.closeNodeInfo = function() {
        nodeInfo.style.display = 'none';
    };

    // --- Zoom, Camera, and Auto-Rotate Controls ---
    document.getElementById('zoomInBtn').addEventListener('click', () => {
        if (!Graph) return;
        const cam = Graph.camera();
        cam.position.z *= 0.8;
        cam.updateProjectionMatrix();
    });
    document.getElementById('zoomOutBtn').addEventListener('click', () => {
        if (!Graph) return;
        const cam = Graph.camera();
        cam.position.z *= 1.2;
        cam.updateProjectionMatrix();
    });
    document.getElementById('resetCameraBtn').addEventListener('click', () => {
        if (!Graph) return;
        Graph.cameraPosition({ x: 0, y: 0, z: 1000 });
    });

    // --- Auto-Rotate ---
    let autoRotate = false;
    let rotateInterval = null;
    let angle = 0;
    function startAutoRotate() {
        if (rotateInterval) return;
        rotateInterval = setInterval(() => {
            angle += 0.01;
            if (Graph) {
                Graph.cameraPosition({
                    x: Math.cos(angle) * 800,
                    z: Math.sin(angle) * 800
                });
            }
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
    stopAutoRotate();
    document.getElementById('toggleRotateBtn').textContent = "Enable Auto-Rotate";
    document.getElementById('toggleRotateBtn').classList.remove("active");
    document.getElementById('toggleRotateBtn').addEventListener('click', toggleAutoRotate);

    // --- Cluster Labels ---
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
        if (!THREE) {
            if (!ensureTHREE()) return;
        }
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
            const vector = new THREE.Vector3(c.x, c.y, c.z);
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

    // --- Color helpers (match CLI) ---
    function getNodeColor(nodeType) {
        const colorMapping = {
            'Subscription': '#ff6b6b',
            'ResourceGroup': '#45b7d1',
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
});