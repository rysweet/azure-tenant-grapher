import React, { useState, useRef } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Grid,
  Divider,
  Card,
  CardContent,
  Chip,
} from '@mui/material';
import { 
  Refresh as RefreshIcon, 
  ZoomIn, 
  ZoomOut, 
  CenterFocusStrong,
  Download as DownloadIcon,
} from '@mui/icons-material';
import MonacoEditor from '@monaco-editor/react';
import GraphViewer from '../widgets/GraphViewer';

const VisualizeTab: React.FC = () => {
  const [query, setQuery] = useState('MATCH (n) RETURN n LIMIT 100');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const graphRef = useRef<any>(null);

  const handleVisualize = async () => {
    setError(null);
    setIsLoading(true);
    setNodes([]);
    setEdges([]);

    try {
      const result = await window.electronAPI.cli.execute('visualize', ['--query', query]);
      
      let outputBuffer = '';
      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          outputBuffer += data.data.join('\n');
        }
      });

      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsLoading(false);
          if (data.code === 0) {
            // Parse the graph data from output
            try {
              if (outputBuffer.includes('{') && outputBuffer.includes('}')) {
                const jsonStr = outputBuffer.substring(
                  outputBuffer.indexOf('{'), 
                  outputBuffer.lastIndexOf('}') + 1
                );
                const graphData = JSON.parse(jsonStr);
                
                // Transform data for vis.js
                const transformedNodes = (graphData.nodes || []).map((node: any) => ({
                  id: node.id || node.properties?.id || String(Math.random()),
                  label: node.label || node.properties?.name || 'Unknown',
                  group: node.type || 'default',
                  title: JSON.stringify(node.properties || {}, null, 2),
                  properties: node.properties,
                }));
                
                const transformedEdges = (graphData.relationships || graphData.edges || []).map((edge: any) => ({
                  from: edge.from || edge.source,
                  to: edge.to || edge.target,
                  label: edge.type || edge.label || '',
                  arrows: 'to',
                }));
                
                setNodes(transformedNodes);
                setEdges(transformedEdges);
              } else {
                // Mock data for testing
                setNodes([
                  { id: '1', label: 'Subscription', group: 'subscription' },
                  { id: '2', label: 'Resource Group 1', group: 'resourceGroup' },
                  { id: '3', label: 'VM 1', group: 'virtualMachine' },
                  { id: '4', label: 'Storage Account', group: 'storageAccount' },
                  { id: '5', label: 'VNet', group: 'virtualNetwork' },
                ]);
                setEdges([
                  { from: '1', to: '2', label: 'CONTAINS' },
                  { from: '2', to: '3', label: 'CONTAINS' },
                  { from: '2', to: '4', label: 'CONTAINS' },
                  { from: '2', to: '5', label: 'CONTAINS' },
                  { from: '3', to: '5', label: 'CONNECTED_TO' },
                ]);
              }
            } catch (e) {
              console.error('Failed to parse graph data:', e);
              setError('Failed to parse graph data from response');
            }
          } else {
            setError(`Visualization failed with exit code ${data.code}`);
          }
        }
      });
      
    } catch (err: any) {
      setError(err.message);
      setIsLoading(false);
    }
  };

  const handleNodeClick = (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    setSelectedNode(node);
  };

  const handleZoomIn = () => {
    if (graphRef.current?.network) {
      const scale = graphRef.current.network.getScale();
      graphRef.current.network.moveTo({
        scale: scale * 1.2,
        animation: {
          duration: 300,
          easingFunction: 'easeInOutQuad',
        },
      });
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current?.network) {
      const scale = graphRef.current.network.getScale();
      graphRef.current.network.moveTo({
        scale: scale * 0.8,
        animation: {
          duration: 300,
          easingFunction: 'easeInOutQuad',
        },
      });
    }
  };

  const handleResetView = () => {
    graphRef.current?.fitNetwork();
  };

  const handleExportGraph = () => {
    // Export graph as JSON
    const exportData = {
      nodes,
      edges,
      query,
      timestamp: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `graph_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Visualize Graph
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={8}>
            <TextField
              fullWidth
              label="Cypher Query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isLoading}
              multiline
              rows={2}
              helperText="Enter a Cypher query to visualize the graph"
            />
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={handleVisualize}
                disabled={isLoading || !query}
              >
                {isLoading ? 'Loading...' : 'Execute'}
              </Button>
            </Box>
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
          <Button 
            startIcon={<ZoomIn />} 
            size="small" 
            onClick={handleZoomIn}
            aria-label="Zoom in graph view"
          >
            Zoom In
          </Button>
          <Button 
            startIcon={<ZoomOut />} 
            size="small" 
            onClick={handleZoomOut}
            aria-label="Zoom out graph view"
          >
            Zoom Out
          </Button>
          <Button 
            startIcon={<CenterFocusStrong />} 
            size="small" 
            onClick={handleResetView}
            aria-label="Reset graph view to default"
          >
            Reset View
          </Button>
          <Button 
            startIcon={<DownloadIcon />} 
            size="small" 
            onClick={handleExportGraph}
            aria-label="Export graph data as JSON"
          >
            Export
          </Button>
        </Box>
      </Paper>

      <Box sx={{ flex: 1, display: 'flex', gap: 2 }}>
        <Box sx={{ flex: 1 }}>
          <GraphViewer
            ref={graphRef}
            nodes={nodes}
            edges={edges}
            onNodeClick={handleNodeClick}
            loading={isLoading}
            height="100%"
          />
        </Box>
        
        {selectedNode && (
          <Paper sx={{ width: 300, p: 2, overflow: 'auto' }}>
            <Typography variant="h6" gutterBottom>
              Node Details
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Typography variant="subtitle2" gutterBottom>
              ID: {selectedNode.id}
            </Typography>
            <Typography variant="subtitle2" gutterBottom>
              Label: {selectedNode.label}
            </Typography>
            <Typography variant="subtitle2" gutterBottom>
              Type: {selectedNode.group}
            </Typography>
            
            {selectedNode.properties && (
              <>
                <Typography variant="subtitle2" sx={{ mt: 2 }} gutterBottom>
                  Properties:
                </Typography>
                <Box sx={{ backgroundColor: 'background.default', p: 1, borderRadius: 1 }}>
                  <pre style={{ margin: 0, fontSize: '0.75rem' }}>
                    {JSON.stringify(selectedNode.properties, null, 2)}
                  </pre>
                </Box>
              </>
            )}
          </Paper>
        )}
      </Box>
    </Box>
  );
};

export default VisualizeTab;