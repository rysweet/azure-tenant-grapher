import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Network, DataSet, Node, Edge } from 'vis-network/standalone';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import {
  Box,
  Paper,
  TextField,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Chip,
  IconButton,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress,
  Alert,
  Button,
  ButtonGroup,
  Tooltip,
  Autocomplete,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Collapse,
  Grid,
  Accordion,
  InputAdornment,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import {
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  CenterFocusStrong as FitIcon,
  Search as SearchIcon,
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
  FilterList as FilterIcon,
  Clear as ClearIcon,
  ExpandMore as ExpandMoreIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  ArrowBack as ArrowLeftIcon,
  ArrowForward as ArrowRightIcon,
  TouchApp as SelectIcon,
  GetApp as ExportIcon,
  Cancel as CancelIcon
} from '@mui/icons-material';
import axios from 'axios';

interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, any>;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    nodeCount: number;
    edgeCount: number;
    nodeTypes: Record<string, number>;
    edgeTypes: Record<string, number>;
  };
}

// Define color palette for different node types
const NODE_COLORS: Record<string, string> = {
  // Core Azure hierarchy
  Tenant: '#FF6B6B',
  Subscription: '#4ECDC4',
  ResourceGroup: '#45B7D1',
  Resource: '#96CEB4', // Fallback for generic resources
  Region: '#FFA500', // Orange for regions

  // Compute resources
  VirtualMachines: '#FFEAA7',
  VirtualMachine: '#FFEAA7', // Alternative naming
  Disks: '#DDA0DD',
  AvailabilitySets: '#F0E68C',
  VirtualMachineScaleSets: '#FFB347',

  // Storage resources
  StorageAccounts: '#74B9FF',
  StorageAccount: '#74B9FF', // Alternative naming

  // Network resources
  VirtualNetworks: '#6C5CE7',
  VirtualNetwork: '#6C5CE7', // Alternative naming
  PrivateEndpoint: '#FF69B4', // Hot pink for private endpoints
  NetworkInterfaces: '#A29BFE',
  NetworkInterface: '#A29BFE', // Alternative naming
  NetworkSecurityGroups: '#9966CC',
  PublicIPAddresses: '#87CEEB',
  LoadBalancers: '#20B2AA',
  ApplicationGateways: '#4682B4',

  // Security resources
  KeyVaults: '#DC143C',
  SecurityCenter: '#8B0000',

  // Database resources
  SqlServers: '#FF4500',
  CosmosDBAccounts: '#FF6347',

  // Web resources
  Websites: '#32CD32',
  AppServicePlans: '#228B22',
  FunctionApps: '#9ACD32',

  // Container resources
  ContainerInstances: '#48D1CC',
  ContainerRegistries: '#00CED1',
  KubernetesClusters: '#5F9EA0',

  // Identity and access
  User: '#FD79A8',
  ServicePrincipal: '#FDCB6E',
  Application: '#E17055',
  Group: '#00B894',
  Role: '#00CEC9',

  // Monitoring and management
  LogAnalytics: '#CD853F',
  ApplicationInsights: '#D2691E',

  Default: '#95A5A6'
};

// Edge type styles with distinct colors and patterns
const EDGE_STYLES: Record<string, any> = {
  CONTAINS: { color: '#2E86DE', width: 3, dashes: false, arrows: 'to' }, // Blue
  USES_IDENTITY: { color: '#10AC84', width: 2, dashes: [5, 5], arrows: 'to' }, // Green
  CONNECTED_TO: { color: '#FF9F43', width: 2, arrows: 'to' }, // Orange
  DEPENDS_ON: { color: '#A55EEA', width: 2, arrows: 'to', dashes: [10, 5] }, // Purple
  HAS_ROLE: { color: '#EE5A52', width: 2, arrows: 'to' }, // Red
  MEMBER_OF: { color: '#FD79A8', width: 2, arrows: 'to' }, // Pink
  ASSIGNED_TO: { color: '#00CEC9', width: 2, arrows: 'to' }, // Teal
  MANAGES: { color: '#FDCB6E', width: 2, arrows: 'to', dashes: [3, 3] }, // Yellow
  INHERITS: { color: '#6C5CE7', width: 2, arrows: 'to', dashes: [8, 3] }, // Indigo
  ACCESSES: { color: '#A29BFE', width: 2, arrows: 'to' }, // Light Purple
  OWNS: { color: '#00B894', width: 3, arrows: 'to' }, // Dark Green
  SUBSCRIBES_TO: { color: '#E17055', width: 2, arrows: 'to', dashes: [15, 5] }, // Coral
  PART_OF: { color: '#74B9FF', width: 2, arrows: 'to' }, // Light Blue
  DELEGATES_TO: { color: '#55A3FF', width: 2, arrows: 'to', dashes: [7, 7] }, // Sky Blue
  ENABLES: { color: '#26DE81', width: 2, arrows: 'to' }, // Mint Green
  Default: { color: '#95A5A6', width: 1, arrows: 'to' } // Gray
};

// Get description for edge types
const getEdgeDescription = (type: string): string => {
  const descriptions: Record<string, string> = {
    CONTAINS: 'Hierarchical containment relationship',
    USES_IDENTITY: 'Uses identity or authentication',
    CONNECTED_TO: 'Network or direct connection',
    DEPENDS_ON: 'Has a dependency on another resource',
    HAS_ROLE: 'Has assigned role or permission',
    MEMBER_OF: 'Is a member of a group or collection',
    ASSIGNED_TO: 'Is assigned to a specific resource',
    MANAGES: 'Has management authority over',
    INHERITS: 'Inherits properties or permissions',
    ACCESSES: 'Has access to a resource',
    OWNS: 'Has ownership of a resource',
    SUBSCRIBES_TO: 'Subscribes to events or notifications',
    PART_OF: 'Is part of a larger structure',
    DELEGATES_TO: 'Delegates authority or responsibility',
    ENABLES: 'Enables functionality or access'
  };
  return descriptions[type] || 'Custom relationship type';
};

export const GraphVisualization: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const navigate = useNavigate();
  const { dispatch } = useApp();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [legendOpen, setLegendOpen] = useState(false);
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<string>>(new Set());
  const [visibleEdgeTypes, setVisibleEdgeTypes] = useState<Set<string>>(new Set());

  // Selection mode state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedNodesForExport, setSelectedNodesForExport] = useState<Set<string>>(new Set());
  const [selectionPanelOpen, setSelectionPanelOpen] = useState(false);

  // Advanced filtering state
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [nameFilter, setNameFilter] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedRegions, setSelectedRegions] = useState<string[]>([]);
  const [selectedResourceGroups, setSelectedResourceGroups] = useState<string[]>([]);
  const [selectedSubscriptions, setSelectedSubscriptions] = useState<string[]>([]);

  // Filter options derived from data
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [availableRegions, setAvailableRegions] = useState<string[]>([]);
  const [availableResourceGroups, setAvailableResourceGroups] = useState<string[]>([]);
  const [availableSubscriptions, setAvailableSubscriptions] = useState<string[]>([]);

  // Get all connected nodes for a given node
  const getConnectedNodes = useCallback((nodeId: string, data: GraphData): Set<string> => {
    const connected = new Set<string>();
    connected.add(nodeId); // Include the selected node itself

    // Find all edges connected to this node
    data.edges.forEach(edge => {
      if (edge.source === nodeId) {
        connected.add(edge.target);
      } else if (edge.target === nodeId) {
        connected.add(edge.source);
      }
    });

    return connected;
  }, []);

  // Handle node selection for export
  const handleNodeSelectionForExport = useCallback((nodeId: string) => {
    if (!graphData || !selectionMode) return;

    const connectedNodes = getConnectedNodes(nodeId, graphData);
    const newSelection = new Set(selectedNodesForExport);

    // Toggle selection: if main node is already selected, deselect all
    if (selectedNodesForExport.has(nodeId)) {
      connectedNodes.forEach(id => newSelection.delete(id));
    } else {
      connectedNodes.forEach(id => newSelection.add(id));
    }

    setSelectedNodesForExport(newSelection);

    // Update visual selection in the network
    if (networkRef.current) {
      networkRef.current.selectNodes(Array.from(newSelection));
    }
  }, [graphData, selectionMode, selectedNodesForExport, getConnectedNodes]);

  // Fetch graph data from backend
  const fetchGraphData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get('http://localhost:3001/api/graph');
      const data = response.data as GraphData;

      // Initialize all types as visible except Subscription nodes (hidden by default)
      const allNodeTypes = Object.keys(data.stats.nodeTypes);
      const defaultVisibleNodeTypes = allNodeTypes.filter(type => type !== 'Subscription');
      setVisibleNodeTypes(new Set(defaultVisibleNodeTypes));
      setVisibleEdgeTypes(new Set(Object.keys(data.stats.edgeTypes)));

      setGraphData(data);
      extractFilterOptions(data);
      renderGraph(data);
    } catch (err: any) {
      // Handle fetch error

      // Provide more detailed error messages
      if (err.code === 'ERR_NETWORK') {
        setError('Cannot connect to backend server. Please ensure the backend is running on port 3001.');
      } else if (err.response?.status === 500) {
        setError('Neo4j connection error. Please ensure Neo4j is running and accessible.');
      } else if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError(err.message || 'Failed to load graph data');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Extract unique filter options from graph data
  const extractFilterOptions = useCallback((data: GraphData) => {
    const tags = new Set<string>();
    const regions = new Set<string>();
    const resourceGroups = new Set<string>();
    const subscriptions = new Set<string>();

    data.nodes.forEach(node => {
      const props = node.properties;

      // Extract tags
      if (props.tags) {
        if (typeof props.tags === 'object') {
          Object.keys(props.tags).forEach(tag => tags.add(tag));
        } else if (typeof props.tags === 'string') {
          props.tags.split(',').forEach((tag: string) => tags.add(tag.trim()));
        }
      }

      // Extract regions/locations
      if (props.location) regions.add(props.location);
      if (props.region) regions.add(props.region);

      // Extract resource groups
      if (props.resourceGroup) resourceGroups.add(props.resourceGroup);
      if (props.resourceGroupName) resourceGroups.add(props.resourceGroupName);

      // Extract subscriptions
      if (props.subscriptionId) subscriptions.add(props.subscriptionId);
      if (props.subscriptionName) subscriptions.add(props.subscriptionName);

      // Special handling for specific node types
      if (node.type === 'ResourceGroup') {
        resourceGroups.add(node.label);
      }
      if (node.type === 'Subscription') {
        subscriptions.add(node.label);
      }
    });

    setAvailableTags(Array.from(tags).sort());
    setAvailableRegions(Array.from(regions).sort());
    setAvailableResourceGroups(Array.from(resourceGroups).sort());
    setAvailableSubscriptions(Array.from(subscriptions).sort());
  }, []);

  // Check if node matches advanced filters
  const nodeMatchesFilters = useCallback((node: GraphNode) => {
    const props = node.properties;

    // Name filter
    if (nameFilter && !node.label.toLowerCase().includes(nameFilter.toLowerCase()) &&
        !(props.name && props.name.toLowerCase().includes(nameFilter.toLowerCase())) &&
        !(props.displayName && props.displayName.toLowerCase().includes(nameFilter.toLowerCase()))) {
      return false;
    }

    // Tags filter
    if (selectedTags.length > 0) {
      let hasMatchingTag = false;
      if (props.tags) {
        if (typeof props.tags === 'object') {
          hasMatchingTag = selectedTags.some(tag => Object.keys(props.tags).includes(tag));
        } else if (typeof props.tags === 'string') {
          const nodeTags = props.tags.split(',').map((tag: string) => tag.trim());
          hasMatchingTag = selectedTags.some(tag => nodeTags.includes(tag));
        }
      }
      if (!hasMatchingTag) return false;
    }

    // Regions filter
    if (selectedRegions.length > 0) {
      const nodeRegion = props.location || props.region;
      if (!nodeRegion || !selectedRegions.includes(nodeRegion)) {
        return false;
      }
    }

    // Resource groups filter
    if (selectedResourceGroups.length > 0) {
      const nodeRG = props.resourceGroup || props.resourceGroupName || (node.type === 'ResourceGroup' ? node.label : null);
      if (!nodeRG || !selectedResourceGroups.includes(nodeRG)) {
        return false;
      }
    }

    // Subscriptions filter
    if (selectedSubscriptions.length > 0) {
      const nodeSub = props.subscriptionId || props.subscriptionName || (node.type === 'Subscription' ? node.label : null);
      if (!nodeSub || !selectedSubscriptions.includes(nodeSub)) {
        return false;
      }
    }

    return true;
  }, [nameFilter, selectedTags, selectedRegions, selectedResourceGroups, selectedSubscriptions]);

  // Render the graph with vis-network
  const renderGraph = useCallback((data: GraphData, nodeFilter?: Set<string>, edgeFilter?: Set<string>) => {
    if (!containerRef.current) return;

    // Use provided filters or default to all types EXCEPT Subscription nodes
    const nodeTypes = nodeFilter || new Set(
      Object.keys(data.stats.nodeTypes).filter(type => type !== 'Subscription')
    );
    const edgeTypes = edgeFilter || new Set(Object.keys(data.stats.edgeTypes));

    // Transform nodes for vis-network
    const visNodes = data.nodes
      .filter(node => nodeTypes.has(node.type))
      .filter(nodeMatchesFilters)
      .map(node => {
        // Create detailed HTML tooltip content using CSS classes
        const tooltipContent = `
          <div class="vis-tooltip-title">${node.label}</div>
          <div class="vis-tooltip-row"><strong>Type:</strong> ${node.type}</div>
          ${node.properties?.resourceGroup ? `<div class="vis-tooltip-row"><strong>Resource Group:</strong> ${node.properties.resourceGroup}</div>` : ''}
          ${node.properties?.location ? `<div class="vis-tooltip-row"><strong>Location:</strong> ${node.properties.location}</div>` : ''}
          ${node.properties?.subscriptionId ? `<div class="vis-tooltip-row"><strong>Subscription:</strong> ${node.properties.subscriptionId}</div>` : ''}
          ${node.properties?.sku ? `<div class="vis-tooltip-row"><strong>SKU:</strong> ${node.properties.sku}</div>` : ''}
          ${node.properties?.status ? `<div class="vis-tooltip-row"><strong>Status:</strong> ${node.properties.status}</div>` : ''}
          ${node.properties?.provisioningState ? `<div class="vis-tooltip-row"><strong>State:</strong> ${node.properties.provisioningState}</div>` : ''}
          <div class="vis-tooltip-hint">Click for more details</div>
        `;

        return {
          id: node.id,
          label: node.label,
          title: tooltipContent,
          color: NODE_COLORS[node.type] || NODE_COLORS.Default,
          shape: 'dot',
          size: 20,
          font: {
            size: 12,
            color: '#2c3e50'
          },
          borderWidth: 2,
          borderWidthSelected: 4,
          ...node
        };
      });

    // Transform edges for vis-network
    const visEdges = data.edges
      .filter(edge => edgeTypes.has(edge.type))
      .filter(edge => {
        // Only include edges where both nodes are visible
        const sourceVisible = visNodes.some(n => n.id === edge.source);
        const targetVisible = visNodes.some(n => n.id === edge.target);
        return sourceVisible && targetVisible;
      })
      .map(edge => ({
        id: edge.id,
        from: edge.source,
        to: edge.target,
        label: edge.type,
        title: edge.type,
        font: {
          size: 10,
          align: 'middle',
          background: 'white'
        },
        ...(EDGE_STYLES[edge.type] || EDGE_STYLES.Default)
      }));

    const nodes = new DataSet(visNodes);
    const edges = new DataSet(visEdges);

    const options = {
      nodes: {
        font: {
          size: 12
        }
      },
      edges: {
        smooth: {
          type: 'continuous',
          roundness: 0.5
        }
      },
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -50,
          centralGravity: 0.01,
          springLength: 100,
          springConstant: 0.08,
          damping: 0.4,
          avoidOverlap: 0.5
        },
        stabilization: {
          enabled: true,
          iterations: 200,
          updateInterval: 10
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        navigationButtons: false,  // Disabled - using Graph Controls pane instead
        keyboard: true
      },
      layout: {
        improvedLayout: true
      }
    };

    // Clear existing network if it exists
    if (networkRef.current) {
      networkRef.current.destroy();
    }

    // Create new network
    const network = new Network(containerRef.current, { nodes, edges }, options);
    networkRef.current = network;

    // Handle node selection
    network.on('selectNode', async (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];

        if (selectionMode) {
          // In selection mode, select node and connected nodes for export
          handleNodeSelectionForExport(nodeId);
        } else {
          // Normal mode - show node details
          try {
            const response = await axios.get(`http://localhost:3001/api/graph/node/${nodeId}`);
            setSelectedNode(response.data);
            setDetailsOpen(true);
          } catch (err) {
            // Handle node details fetch error
          }
        }
      }
    });

    // Stabilization progress
    network.on('stabilizationProgress', (params) => {
      // Physics stabilization in progress
    });

    network.once('stabilizationIterationsDone', () => {
      network.setOptions({ physics: { enabled: false } });
    });
  }, [nodeMatchesFilters, selectionMode, handleNodeSelectionForExport]);

  // Filter graph by node/edge types and advanced filters
  const handleFilterChange = useCallback(() => {
    if (graphData) {
      renderGraph(graphData, visibleNodeTypes, visibleEdgeTypes);
    }
  }, [graphData, visibleNodeTypes, visibleEdgeTypes, renderGraph]);

  // Clear all filters
  const clearAllFilters = useCallback(() => {
    setNameFilter('');
    setSelectedTags([]);
    setSelectedRegions([]);
    setSelectedResourceGroups([]);
    setSelectedSubscriptions([]);
    if (graphData) {
      // Reset to default visible types (excluding Subscription nodes by default)
      const allNodeTypes = Object.keys(graphData.stats.nodeTypes);
      const defaultVisibleNodeTypes = allNodeTypes.filter(type => type !== 'Subscription');
      setVisibleNodeTypes(new Set(defaultVisibleNodeTypes));
      setVisibleEdgeTypes(new Set(Object.keys(graphData.stats.edgeTypes)));
    }
  }, [graphData]);

  // Toggle node type visibility
  const toggleNodeType = (type: string) => {
    const newTypes = new Set(visibleNodeTypes);
    if (newTypes.has(type)) {
      newTypes.delete(type);
    } else {
      newTypes.add(type);
    }
    setVisibleNodeTypes(newTypes);
  };

  // Toggle edge type visibility
  const toggleEdgeType = (type: string) => {
    const newTypes = new Set(visibleEdgeTypes);
    if (newTypes.has(type)) {
      newTypes.delete(type);
    } else {
      newTypes.add(type);
    }
    setVisibleEdgeTypes(newTypes);
  };

  // Search functionality
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const response = await axios.get(`http://localhost:3001/api/graph/search`, {
        params: { query: searchQuery }
      });

      if (response.data.length > 0 && networkRef.current) {
        const nodeIds = response.data.map((n: GraphNode) => n.id);
        networkRef.current.selectNodes(nodeIds);
        if (nodeIds.length === 1) {
          networkRef.current.focus(nodeIds[0], { scale: 1.5, animation: true });
        }
      }
    } catch (err) {
      // Handle search error
    }
  };

  // Zoom controls
  const handleZoomIn = () => {
    if (networkRef.current) {
      const scale = networkRef.current.getScale();
      networkRef.current.moveTo({
        scale: scale * 1.2,
        animation: { duration: 300, easingFunction: 'easeInOutQuad' }
      });
    }
  };

  const handleZoomOut = () => {
    if (networkRef.current) {
      const scale = networkRef.current.getScale();
      networkRef.current.moveTo({
        scale: scale * 0.8,
        animation: { duration: 300, easingFunction: 'easeInOutQuad' }
      });
    }
  };

  const handleFit = () => {
    if (networkRef.current) {
      networkRef.current.fit({
        animation: { duration: 500, easingFunction: 'easeInOutQuad' }
      });
    }
  };

  // Pan controls
  const handlePan = (direction: 'up' | 'down' | 'left' | 'right') => {
    if (networkRef.current) {
      const viewPosition = networkRef.current.getViewPosition();
      const scale = networkRef.current.getScale();
      const panDistance = 100 / scale; // Adjust pan distance based on zoom level

      let newPosition = { ...viewPosition };
      switch (direction) {
        case 'up':
          newPosition.y -= panDistance;
          break;
        case 'down':
          newPosition.y += panDistance;
          break;
        case 'left':
          newPosition.x -= panDistance;
          break;
        case 'right':
          newPosition.x += panDistance;
          break;
      }

      networkRef.current.moveTo({
        position: newPosition,
        animation: { duration: 200, easingFunction: 'easeInOutQuad' }
      });
    }
  };

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  useEffect(() => {
    handleFilterChange();
  }, [visibleNodeTypes, visibleEdgeTypes, nameFilter, selectedTags, selectedRegions, selectedResourceGroups, selectedSubscriptions, handleFilterChange]);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'row' }}>
      {/* Control Panel - 25% width on the left */}
      <Paper sx={{
        width: '25%',
        minWidth: '350px',
        maxWidth: '400px',
        p: 2,
        mr: 2,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#1a1a1a',
        color: 'white',
        overflowY: 'auto'
      }}>
        {/* Header */}
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ color: 'white', fontSize: '1rem' }}>Graph Controls</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={selectionMode ? "Exit Selection Mode" : "Enter Selection Mode"}>
              <Button
                size="small"
                variant={selectionMode ? "contained" : "outlined"}
                onClick={() => {
                  setSelectionMode(!selectionMode);
                  if (!selectionMode) {
                    setSelectedNodesForExport(new Set());
                    if (networkRef.current) {
                      networkRef.current.unselectAll();
                    }
                  }
                }}
                startIcon={<SelectIcon />}
                sx={{
                  backgroundColor: selectionMode ? '#4caf50' : '#000000',
                  color: selectionMode ? '#000000' : '#4caf50',
                  borderColor: '#4caf50',
                  '&:hover': {
                    backgroundColor: selectionMode ? '#45a049' : '#000000',
                    borderColor: '#4caf50'
                  }
                }}
              >
                Select
              </Button>
            </Tooltip>
          </Box>
        </Box>

        {/* All Controls in Single Line */}
        <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center' }}>
          <ButtonGroup size="small">
            <Tooltip title="Zoom In">
              <Button onClick={handleZoomIn} sx={{
                backgroundColor: '#000000',
                color: '#4caf50',
                borderColor: '#4caf50',
                '&:hover': {
                  backgroundColor: '#000000',
                  borderColor: '#4caf50'
                }
              }}>
                <ZoomInIcon />
              </Button>
            </Tooltip>
            <Tooltip title="Zoom Out">
              <Button onClick={handleZoomOut} sx={{
                backgroundColor: '#000000',
                color: '#4caf50',
                borderColor: '#4caf50',
                '&:hover': {
                  backgroundColor: '#000000',
                  borderColor: '#4caf50'
                }
              }}>
                <ZoomOutIcon />
              </Button>
            </Tooltip>
            <Tooltip title="Fit to Screen">
              <Button onClick={handleFit} sx={{
                backgroundColor: '#000000',
                color: '#4caf50',
                borderColor: '#4caf50',
                '&:hover': {
                  backgroundColor: '#000000',
                  borderColor: '#4caf50'
                }
              }}>
                <FitIcon />
              </Button>
            </Tooltip>
          </ButtonGroup>

          {/* Pan controls inline */}
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 24px)', gap: 0 }}>
              <Box />
              <Tooltip title="Pan Up">
                <IconButton onClick={() => handlePan('up')} size="small" sx={{
                  padding: '2px',
                  color: '#4caf50',
                  backgroundColor: '#000000',
                  border: '1px solid #4caf50',
                  '&:hover': {
                    backgroundColor: '#1a1a1a',
                    borderColor: '#4caf50'
                  }
                }}>
                  <ArrowUpIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Box />
              <Tooltip title="Pan Left">
                <IconButton onClick={() => handlePan('left')} size="small" sx={{
                  padding: '2px',
                  color: '#4caf50',
                  backgroundColor: '#000000',
                  border: '1px solid #4caf50',
                  '&:hover': {
                    backgroundColor: '#1a1a1a',
                    borderColor: '#4caf50'
                  }
                }}>
                  <ArrowLeftIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Box />
              <Tooltip title="Pan Right">
                <IconButton onClick={() => handlePan('right')} size="small" sx={{
                  padding: '2px',
                  color: '#4caf50',
                  backgroundColor: '#000000',
                  border: '1px solid #4caf50',
                  '&:hover': {
                    backgroundColor: '#1a1a1a',
                    borderColor: '#4caf50'
                  }
                }}>
                  <ArrowRightIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Box />
              <Tooltip title="Pan Down">
                <IconButton onClick={() => handlePan('down')} size="small" sx={{
                  padding: '2px',
                  color: '#4caf50',
                  backgroundColor: '#000000',
                  border: '1px solid #4caf50',
                  '&:hover': {
                    backgroundColor: '#1a1a1a',
                    borderColor: '#4caf50'
                  }
                }}>
                  <ArrowDownIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Box />
          </Box>

          {/* Refresh button */}
          <Tooltip title="Refresh">
            <IconButton onClick={fetchGraphData} size="small" sx={{
              padding: '2px',
                color: '#4caf50',
                backgroundColor: '#000000',
                border: '1px solid #4caf50',
                '&:hover': {
                  backgroundColor: '#1a1a1a',
                  borderColor: '#4caf50'
                }
            }}>
              <RefreshIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Selection Info Panel */}
        {selectionMode && (
          <Paper sx={{
            mb: 2,
            p: 2,
            backgroundColor: '#2a2a2a',
            border: '2px solid #4caf50'
          }}>
            <Typography variant="subtitle2" sx={{ color: '#4caf50', mb: 1 }}>
              Selection Mode Active
            </Typography>
            <Typography variant="body2" sx={{ color: 'white', mb: 2 }}>
              Click on nodes to select them and their connected nodes
            </Typography>
            <Typography variant="body2" sx={{ color: 'white', mb: 1 }}>
              Selected: {selectedNodesForExport.size} nodes
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              <Button
                size="small"
                variant="contained"
                disabled={selectedNodesForExport.size === 0}
                onClick={async () => {
                  if (selectedNodesForExport.size === 0) return;

                  // Get selected node IDs and details
                  const nodeIds = Array.from(selectedNodesForExport);
                  
                  // Map node IDs to include resource names for ResourceGroup nodes
                  const nodeDetails = nodeIds.map(nodeId => {
                    const node = graphData?.nodes.find(n => n.id === nodeId);
                    return {
                      id: nodeId,
                      type: node?.type,
                      label: node?.label,
                      resourceName: (node as any)?.resourceName,  // For ResourceGroup nodes
                      azureId: (node as any)?.azureId  // Azure resource ID if available
                    };
                  });

                  // Dispatch event for GenerateIaCTab to pick up
                  const event = new CustomEvent('generateIaCForNodes', {
                    detail: { nodeIds, nodeDetails }
                  });
                  window.dispatchEvent(event);

                  // Navigate to Generate IaC tab
                  navigate('/generate-iac');
                  dispatch({ type: 'SET_ACTIVE_TAB', payload: 'generate-iac' });

                  // Exit selection mode
                  setSelectionMode(false);
                  setSelectedNodesForExport(new Set());
                }}
                startIcon={<ExportIcon />}
                sx={{
                  backgroundColor: '#4caf50',
                  color: '#000000',
                  '&:hover': {
                    backgroundColor: '#45a049'
                  },
                  '&:disabled': {
                    backgroundColor: '#333',
                    color: '#666'
                  }
                }}
              >
                Generate IaC
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => {
                  setSelectedNodesForExport(new Set());
                  if (networkRef.current) {
                    networkRef.current.unselectAll();
                  }
                }}
                startIcon={<ClearIcon />}
                sx={{
                  borderColor: '#f44336',
                  color: '#f44336',
                  '&:hover': {
                    borderColor: '#d32f2f',
                    backgroundColor: 'rgba(244, 67, 54, 0.08)'
                  }
                }}
              >
                Clear
              </Button>
            </Box>
          </Paper>
        )}

        {/* Search bar */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ color: 'white', mb: 1 }}>Search</Typography>
          <TextField
            size="small"
            placeholder="Search nodes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            fullWidth
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <Tooltip title="Search">
                    <IconButton
                      onClick={handleSearch}
                      size="small"
                      sx={{ color: '#4caf50' }}
                    >
                      <SearchIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Clear">
                    <IconButton
                      onClick={clearAllFilters}
                      size="small"
                      sx={{ color: '#4caf50' }}
                    >
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </InputAdornment>
              ),
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                color: 'white',
                '& fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.3)',
                },
                '&:hover fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.5)',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'white',
                },
              },
              '& .MuiInputBase-input::placeholder': {
                color: 'rgba(255, 255, 255, 0.7)',
              },
            }}
          />
        </Box>

        {/* Advanced Filters Toggle */}
        <Box sx={{ mb: 2 }}>
          <Button
            variant="outlined"
            onClick={() => setFiltersOpen(!filtersOpen)}
            startIcon={<FilterIcon />}
            size="small"
            fullWidth
            sx={{
              backgroundColor: '#000000',
              color: '#4caf50',
              borderColor: '#4caf50',
              '&:hover': {
                backgroundColor: '#000000',
                borderColor: '#4caf50'
              }
            }}
          >
            Advanced Filters
          </Button>
        </Box>

        {/* Advanced Filters */}
        <Collapse in={filtersOpen}>
          <Box sx={{ mb: 3, p: 2, border: '1px solid rgba(255, 255, 255, 0.3)', borderRadius: 1 }}>
            <Typography variant="subtitle2" sx={{ color: 'white', mb: 2 }}>Advanced Filters</Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {/* Name Filter */}
              <TextField
                fullWidth
                size="small"
                label="Filter by Name"
                value={nameFilter}
                onChange={(e) => setNameFilter(e.target.value)}
                placeholder="Enter name pattern..."
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: 'white',
                    '& fieldset': {
                      borderColor: 'rgba(255, 255, 255, 0.3)',
                    },
                    '&:hover fieldset': {
                      borderColor: 'rgba(255, 255, 255, 0.5)',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: 'white',
                    },
                  },
                  '& .MuiInputLabel-root': {
                    color: 'rgba(255, 255, 255, 0.7)',
                  },
                  '& .MuiInputBase-input::placeholder': {
                    color: 'rgba(255, 255, 255, 0.5)',
                  },
                }}
              />

              {/* Tags Filter */}
              <Autocomplete
                multiple
                size="small"
                options={availableTags}
                value={selectedTags}
                onChange={(_, newValue) => setSelectedTags(newValue)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Filter by Tags"
                    placeholder="Select tags..."
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        color: 'white',
                        '& fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.3)',
                        },
                        '&:hover fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.5)',
                        },
                        '&.Mui-focused fieldset': {
                          borderColor: 'white',
                        },
                      },
                      '& .MuiInputLabel-root': {
                        color: 'rgba(255, 255, 255, 0.7)',
                      },
                    }}
                  />
                )}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip
                      key={option}
                      label={option}
                      size="small"
                      {...getTagProps({ index })}
                    />
                  ))
                }
              />

              {/* Regions Filter */}
              <Autocomplete
                multiple
                size="small"
                options={availableRegions}
                value={selectedRegions}
                onChange={(_, newValue) => setSelectedRegions(newValue)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Filter by Region"
                    placeholder="Select regions..."
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        color: 'white',
                        '& fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.3)',
                        },
                        '&:hover fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.5)',
                        },
                        '&.Mui-focused fieldset': {
                          borderColor: 'white',
                        },
                      },
                      '& .MuiInputLabel-root': {
                        color: 'rgba(255, 255, 255, 0.7)',
                      },
                    }}
                  />
                )}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip
                      key={option}
                      label={option}
                      size="small"
                      color="primary"
                      {...getTagProps({ index })}
                    />
                  ))
                }
              />

              {/* Resource Groups Filter */}
              <Autocomplete
                multiple
                size="small"
                options={availableResourceGroups}
                value={selectedResourceGroups}
                onChange={(_, newValue) => setSelectedResourceGroups(newValue)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Filter by Resource Group"
                    placeholder="Select resource groups..."
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        color: 'white',
                        '& fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.3)',
                        },
                        '&:hover fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.5)',
                        },
                        '&.Mui-focused fieldset': {
                          borderColor: 'white',
                        },
                      },
                      '& .MuiInputLabel-root': {
                        color: 'rgba(255, 255, 255, 0.7)',
                      },
                    }}
                  />
                )}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip
                      key={option}
                      label={option}
                      size="small"
                      color="secondary"
                      {...getTagProps({ index })}
                    />
                  ))
                }
              />

              {/* Subscriptions Filter */}
              <Autocomplete
                multiple
                size="small"
                options={availableSubscriptions}
                value={selectedSubscriptions}
                onChange={(_, newValue) => setSelectedSubscriptions(newValue)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Filter by Subscription"
                    placeholder="Select subscriptions..."
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        color: 'white',
                        '& fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.3)',
                        },
                        '&:hover fieldset': {
                          borderColor: 'rgba(255, 255, 255, 0.5)',
                        },
                        '&.Mui-focused fieldset': {
                          borderColor: 'white',
                        },
                      },
                      '& .MuiInputLabel-root': {
                        color: 'rgba(255, 255, 255, 0.7)',
                      },
                    }}
                  />
                )}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip
                      key={option}
                      label={option}
                      size="small"
                      color="info"
                      {...getTagProps({ index })}
                    />
                  ))
                }
              />
            </Box>
          </Box>
        </Collapse>

        {/* Node and Edge Type Filters */}
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="subtitle2" sx={{ color: 'white', mb: 1 }}>Node Types</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
            {graphData && Object.entries(graphData.stats.nodeTypes).map(([type, count]) => (
              <Chip
                key={type}
                label={`${type} (${count})`}
                onClick={() => toggleNodeType(type)}
                color={visibleNodeTypes.has(type) ? 'primary' : 'default'}
                variant={visibleNodeTypes.has(type) ? 'filled' : 'outlined'}
                size="small"
                sx={{
                  backgroundColor: visibleNodeTypes.has(type) ? NODE_COLORS[type] || NODE_COLORS.Default : undefined,
                  color: visibleNodeTypes.has(type) ? 'white' : 'rgba(255, 255, 255, 0.7)',
                  borderColor: visibleNodeTypes.has(type) ? undefined : 'rgba(255, 255, 255, 0.3)',
                  '&:hover': {
                    backgroundColor: NODE_COLORS[type] || NODE_COLORS.Default,
                    opacity: 0.8,
                    color: 'white'
                  }
                }}
              />
            ))}
          </Box>

          <Typography variant="subtitle2" sx={{ color: 'white', mb: 1 }}>Edge Types</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {graphData && Object.entries(graphData.stats.edgeTypes).map(([type, count]) => (
              <Chip
                key={type}
                label={`${type} (${count})`}
                onClick={() => toggleEdgeType(type)}
                color={visibleEdgeTypes.has(type) ? 'secondary' : 'default'}
                variant={visibleEdgeTypes.has(type) ? 'filled' : 'outlined'}
                size="small"
                sx={{
                  backgroundColor: visibleEdgeTypes.has(type) ? (EDGE_STYLES[type]?.color || EDGE_STYLES.Default.color) : undefined,
                  color: visibleEdgeTypes.has(type) ? 'white' : 'rgba(255, 255, 255, 0.7)',
                  borderColor: visibleEdgeTypes.has(type) ? undefined : 'rgba(255, 255, 255, 0.3)',
                  '&:hover': {
                    backgroundColor: EDGE_STYLES[type]?.color || EDGE_STYLES.Default.color,
                    opacity: 0.8,
                    color: 'white'
                  }
                }}
              />
            ))}
          </Box>
        </Box>
      </Paper>

      {/* Legend Panel - Inline Compact */}
      <Paper sx={{
        width: '180px',
        p: 1.5,
        mr: 1,
        backgroundColor: '#1a1a1a',
        color: 'white',
        overflowY: 'auto'
      }}>
        <Typography variant="subtitle2" sx={{ mb: 1, fontSize: '0.85rem', color: '#4caf50' }}>Legend</Typography>

        {/* Node Types */}
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.7rem' }}>Nodes</Typography>
        <Box sx={{ mb: 1, mt: 0.5 }}>
          {Object.entries(NODE_COLORS).slice(0, 10).map(([type, color]) => {
            const isVisible = visibleNodeTypes.has(type);
            return (
              <Box
                key={type}
                onClick={() => toggleNodeType(type)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  mb: 0.25,
                  cursor: 'pointer',
                  opacity: isVisible ? 1 : 0.4,
                  '&:hover': {
                    opacity: 0.8
                  }
                }}
              >
                <Box sx={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: color,
                  flexShrink: 0,
                  border: isVisible ? '1px solid #4caf50' : 'none'
                }} />
                <Typography variant="caption" sx={{ fontSize: '0.65rem', color: isVisible ? '#4caf50' : 'rgba(255,255,255,0.8)' }}>
                  {type.replace(/_/g, ' ')}
                </Typography>
              </Box>
            );
          })}
        </Box>

        {/* Edge Types */}
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.7rem', mt: 1 }}>Edges</Typography>
        <Box sx={{ mt: 0.5 }}>
          {Object.entries(EDGE_STYLES).slice(0, 8).map(([type, style]) => {
            const isVisible = visibleEdgeTypes.has(type);
            return (
              <Box
                key={type}
                onClick={() => toggleEdgeType(type)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  mb: 0.25,
                  cursor: 'pointer',
                  opacity: isVisible ? 1 : 0.4,
                  '&:hover': {
                    opacity: 0.8
                  }
                }}
              >
                <Box sx={{
                  width: 16,
                  height: 2,
                  backgroundColor: style.color || '#888',
                  flexShrink: 0,
                  border: isVisible ? '1px solid #4caf50' : 'none'
                }} />
                <Typography variant="caption" sx={{ fontSize: '0.65rem', color: isVisible ? '#4caf50' : 'rgba(255,255,255,0.8)' }}>
                  {type.replace(/_/g, ' ')}
                </Typography>
              </Box>
            );
          })}
        </Box>
      </Paper>

      {/* Graph container */}
      <Paper sx={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {loading && (
          <Box sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 10
          }}>
            <CircularProgress />
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ m: 2 }}>
            {error}
          </Alert>
        )}

        {/* Floating stats */}
        {graphData && (
          <Box sx={{
            position: 'absolute',
            top: 10,
            left: 10,
            zIndex: 5,
            display: 'flex',
            gap: 2,
            pointerEvents: 'none'
          }}>
            <Typography sx={{
              color: '#4caf50',
              fontSize: '0.85rem',
              fontWeight: 'medium',
              textShadow: '0 1px 2px rgba(0,0,0,0.5)'
            }}>
              {graphData.stats.nodeCount.toLocaleString()} nodes
            </Typography>
            <Typography sx={{
              color: '#4caf50',
              fontSize: '0.85rem',
              fontWeight: 'medium',
              textShadow: '0 1px 2px rgba(0,0,0,0.5)'
            }}>
              {graphData.stats.edgeCount.toLocaleString()} edges
            </Typography>
          </Box>
        )}

        <Box
          ref={containerRef}
          sx={{
            width: '100%',
            height: '100%',
            backgroundColor: '#000000'
          }}
        />
      </Paper>

      {/* Node details drawer */}
      <Drawer
        anchor="right"
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        PaperProps={{ sx: { width: 400 } }}
      >
        {selectedNode && (
          <Box sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">Node Details</Typography>
              <IconButton onClick={() => setDetailsOpen(false)} sx={{
                color: '#4caf50',
                backgroundColor: '#000000',
                '&:hover': {
                  backgroundColor: '#000000',
                  filter: 'brightness(1.2)'
                }
              }}>
                <CloseIcon />
              </IconButton>
            </Box>

            <List>
              <ListItem>
                <ListItemText
                  primary="ID"
                  secondary={selectedNode.id}
                  secondaryTypographyProps={{ style: { wordBreak: 'break-all' } }}
                />
              </ListItem>

              <ListItem>
                <ListItemText
                  primary="Type"
                  secondary={selectedNode.labels?.join(', ') || 'Unknown'}
                />
              </ListItem>

              <Divider />

              <ListItem>
                <ListItemText primary="Properties" />
              </ListItem>

              {selectedNode.properties && Object.entries(selectedNode.properties).map(([key, value]) => (
                <ListItem key={key} sx={{ pl: 4 }}>
                  <ListItemText
                    primary={key}
                    secondary={typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                    secondaryTypographyProps={{ style: { wordBreak: 'break-all' } }}
                  />
                </ListItem>
              ))}

              {selectedNode.connections && selectedNode.connections.length > 0 && (
                <>
                  <Divider />
                  <ListItem>
                    <ListItemText primary={`Connections (${selectedNode.connections.length})`} />
                  </ListItem>
                  {selectedNode.connections.map((conn: any, index: number) => (
                    <ListItem key={index} sx={{ pl: 4 }}>
                      <ListItemText
                        primary={`${conn.relationship} (${conn.direction})`}
                        secondary={`${conn.connectedNode.type}: ${conn.connectedNode.label}`}
                      />
                    </ListItem>
                  ))}
                </>
              )}
            </List>
          </Box>
        )}
      </Drawer>

      {/* Legend drawer */}
      <Drawer
        anchor="left"
        open={legendOpen}
        onClose={() => setLegendOpen(false)}
        PaperProps={{ sx: { width: 350 } }}
      >
        <Box sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Typography variant="h6">Graph Legend</Typography>
            <IconButton onClick={() => setLegendOpen(false)} sx={{
              color: '#4caf50',
              backgroundColor: '#000000',
              '&:hover': {
                backgroundColor: '#000000',
                filter: 'brightness(1.2)'
              }
            }}>
              <CloseIcon />
            </IconButton>
          </Box>

          {/* Edge Types Legend */}
          <Typography variant="subtitle1" gutterBottom sx={{ mt: 2, mb: 2, fontWeight: 'bold' }}>
            Edge Types
          </Typography>

          <List dense>
            {Object.entries(EDGE_STYLES).filter(([type]) => type !== 'Default').map(([type, style]) => {
              const markerId = `arrowhead-${type.toLowerCase()}`;
              return (
                <ListItem key={type} sx={{ py: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                    {/* Edge visualization */}
                    <Box sx={{ position: 'relative', width: 60, height: 20 }}>
                      <svg width="60" height="20" style={{ position: 'absolute' }}>
                        <defs>
                          <marker
                            id={markerId}
                            markerWidth="10"
                            markerHeight="7"
                            refX="9"
                            refY="3.5"
                            orient="auto"
                          >
                            <polygon
                              points="0 0, 10 3.5, 0 7"
                              fill={style.color}
                            />
                          </marker>
                        </defs>
                        <line
                          x1="5"
                          y1="10"
                          x2="45"
                          y2="10"
                          stroke={style.color}
                          strokeWidth={Math.max(style.width, 2)}
                          strokeDasharray={style.dashes ? style.dashes.join(',') : 'none'}
                          markerEnd={`url(#${markerId})`}
                        />
                      </svg>
                    </Box>

                    {/* Type name and description */}
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" fontWeight="medium">
                        {type.replace(/_/g, ' ')}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {getEdgeDescription(type)}
                      </Typography>
                    </Box>
                  </Box>
                </ListItem>
              );
            })}
          </List>

          <Divider sx={{ my: 2 }} />

          {/* Node Types Legend */}
          <Typography variant="subtitle1" gutterBottom sx={{ mt: 2, mb: 2, fontWeight: 'bold' }}>
            Node Types
          </Typography>

          <List dense>
            {Object.entries(NODE_COLORS).filter(([type]) => type !== 'Default').map(([type, color]) => (
              <ListItem key={type} sx={{ py: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box
                    sx={{
                      width: 16,
                      height: 16,
                      borderRadius: '50%',
                      backgroundColor: color,
                      border: '1px solid #ddd'
                    }}
                  />
                  <Typography variant="body2">
                    {type.replace(/([A-Z])/g, ' $1').trim()}
                  </Typography>
                </Box>
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>
    </Box>
  );
};
