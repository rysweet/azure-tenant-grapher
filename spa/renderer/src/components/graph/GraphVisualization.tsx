import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Network, DataSet, Node, Edge } from 'vis-network/standalone';
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
  Tooltip
} from '@mui/material';
import {
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  CenterFocusStrong as FitIcon,
  Search as SearchIcon,
  Close as CloseIcon,
  Refresh as RefreshIcon
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
  Tenant: '#FF6B6B',
  Subscription: '#4ECDC4',
  ResourceGroup: '#45B7D1',
  Resource: '#96CEB4',
  VirtualMachine: '#FFEAA7',
  StorageAccount: '#74B9FF',
  NetworkInterface: '#A29BFE',
  VirtualNetwork: '#6C5CE7',
  User: '#FD79A8',
  ServicePrincipal: '#FDCB6E',
  Application: '#E17055',
  Group: '#00B894',
  Role: '#00CEC9',
  Default: '#95A5A6'
};

// Edge type styles
const EDGE_STYLES: Record<string, any> = {
  CONTAINS: { color: '#34495e', width: 2, dashes: false },
  USES_IDENTITY: { color: '#e74c3c', width: 2, dashes: [5, 5] },
  CONNECTED_TO: { color: '#3498db', width: 2, arrows: 'to' },
  DEPENDS_ON: { color: '#f39c12', width: 2, arrows: 'to', dashes: [10, 5] },
  HAS_ROLE: { color: '#9b59b6', width: 2, arrows: 'to' },
  MEMBER_OF: { color: '#1abc9c', width: 2, arrows: 'to' },
  Default: { color: '#95a5a6', width: 1, arrows: 'to' }
};

export const GraphVisualization: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<string>>(new Set());
  const [visibleEdgeTypes, setVisibleEdgeTypes] = useState<Set<string>>(new Set());

  // Fetch graph data from backend
  const fetchGraphData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get('http://localhost:3001/api/graph');
      const data = response.data as GraphData;
      
      // Initialize all types as visible
      setVisibleNodeTypes(new Set(Object.keys(data.stats.nodeTypes)));
      setVisibleEdgeTypes(new Set(Object.keys(data.stats.edgeTypes)));
      
      setGraphData(data);
      renderGraph(data);
    } catch (err: any) {
      console.error('Failed to fetch graph data:', err);
      
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

  // Render the graph with vis-network
  const renderGraph = useCallback((data: GraphData, nodeFilter?: Set<string>, edgeFilter?: Set<string>) => {
    if (!containerRef.current) return;

    const nodeTypes = nodeFilter || new Set(Object.keys(data.stats.nodeTypes));
    const edgeTypes = edgeFilter || new Set(Object.keys(data.stats.edgeTypes));

    // Transform nodes for vis-network
    const visNodes = data.nodes
      .filter(node => nodeTypes.has(node.type))
      .map(node => ({
        id: node.id,
        label: node.label,
        title: `${node.type}: ${node.label}`,
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
      }));

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
        navigationButtons: true,
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
        try {
          const response = await axios.get(`http://localhost:3001/api/graph/node/${nodeId}`);
          setSelectedNode(response.data);
          setDetailsOpen(true);
        } catch (err) {
          console.error('Failed to fetch node details:', err);
        }
      }
    });

    // Stabilization progress
    network.on('stabilizationProgress', (params) => {
      const progress = params.iterations / params.total * 100;
      console.log(`Stabilization progress: ${progress.toFixed(0)}%`);
    });

    network.once('stabilizationIterationsDone', () => {
      console.log('Stabilization complete');
      network.setOptions({ physics: { enabled: false } });
    });
  }, []);

  // Filter graph by node/edge types
  const handleFilterChange = useCallback(() => {
    if (graphData) {
      renderGraph(graphData, visibleNodeTypes, visibleEdgeTypes);
    }
  }, [graphData, visibleNodeTypes, visibleEdgeTypes, renderGraph]);

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
      console.error('Search failed:', err);
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

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  useEffect(() => {
    handleFilterChange();
  }, [visibleNodeTypes, visibleEdgeTypes, handleFilterChange]);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header with stats and controls */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="h6">Graph Visualization</Typography>
            {graphData && (
              <>
                <Chip 
                  label={`${graphData.stats.nodeCount} Nodes`} 
                  color="primary" 
                  size="small" 
                />
                <Chip 
                  label={`${graphData.stats.edgeCount} Edges`} 
                  color="secondary" 
                  size="small" 
                />
              </>
            )}
          </Box>
          
          <Box sx={{ display: 'flex', gap: 1 }}>
            <ButtonGroup size="small">
              <Tooltip title="Zoom In">
                <Button onClick={handleZoomIn}><ZoomInIcon /></Button>
              </Tooltip>
              <Tooltip title="Zoom Out">
                <Button onClick={handleZoomOut}><ZoomOutIcon /></Button>
              </Tooltip>
              <Tooltip title="Fit to Screen">
                <Button onClick={handleFit}><FitIcon /></Button>
              </Tooltip>
            </ButtonGroup>
            <Tooltip title="Refresh">
              <IconButton onClick={fetchGraphData} size="small">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Search bar */}
        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          <TextField
            size="small"
            placeholder="Search nodes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            sx={{ flex: 1 }}
          />
          <Button variant="contained" onClick={handleSearch} startIcon={<SearchIcon />}>
            Search
          </Button>
        </Box>

        {/* Filters */}
        <Box>
          <Typography variant="subtitle2" gutterBottom>Node Types</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
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
                  color: visibleNodeTypes.has(type) ? 'white' : undefined,
                  '&:hover': {
                    backgroundColor: NODE_COLORS[type] || NODE_COLORS.Default,
                    opacity: 0.8,
                    color: 'white'
                  }
                }}
              />
            ))}
          </Box>

          <Typography variant="subtitle2" gutterBottom>Edge Types</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {graphData && Object.entries(graphData.stats.edgeTypes).map(([type, count]) => (
              <Chip
                key={type}
                label={`${type} (${count})`}
                onClick={() => toggleEdgeType(type)}
                color={visibleEdgeTypes.has(type) ? 'secondary' : 'default'}
                variant={visibleEdgeTypes.has(type) ? 'filled' : 'outlined'}
                size="small"
              />
            ))}
          </Box>
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
        
        <Box
          ref={containerRef}
          sx={{ 
            width: '100%', 
            height: '100%',
            backgroundColor: '#f5f5f5'
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
              <IconButton onClick={() => setDetailsOpen(false)}>
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
    </Box>
  );
};