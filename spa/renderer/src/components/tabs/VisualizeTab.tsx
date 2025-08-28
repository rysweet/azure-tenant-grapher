import React, { useState } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Grid,
} from '@mui/material';
import { Refresh as RefreshIcon, ZoomIn, ZoomOut, CenterFocusStrong } from '@mui/icons-material';
import MonacoEditor from '@monaco-editor/react';

const VisualizeTab: React.FC = () => {
  const [query, setQuery] = useState('MATCH (n) RETURN n LIMIT 100');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<any>(null);

  const handleVisualize = async () => {
    setError(null);
    setIsLoading(true);

    try {
      const result = await window.electronAPI.cli.execute('visualize', ['--query', query]);
      
      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          // Parse graph data from output
          try {
            const output = data.data.join('');
            if (output.includes('{') && output.includes('}')) {
              const jsonStr = output.substring(output.indexOf('{'), output.lastIndexOf('}') + 1);
              setGraphData(JSON.parse(jsonStr));
            }
          } catch (e) {
            console.error('Failed to parse graph data:', e);
          }
        }
      });

      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsLoading(false);
          if (data.code !== 0) {
            setError(`Visualization failed with exit code ${data.code}`);
          }
        }
      });
      
    } catch (err: any) {
      setError(err.message);
      setIsLoading(false);
    }
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
          <Button startIcon={<ZoomIn />} size="small">Zoom In</Button>
          <Button startIcon={<ZoomOut />} size="small">Zoom Out</Button>
          <Button startIcon={<CenterFocusStrong />} size="small">Reset View</Button>
        </Box>
      </Paper>

      <Paper sx={{ flex: 1, minHeight: 0, p: 2 }}>
        <Box sx={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {graphData ? (
            <Typography color="text.secondary">
              Graph visualization would render here with {graphData.nodes?.length || 0} nodes 
              and {graphData.relationships?.length || 0} relationships
            </Typography>
          ) : (
            <Typography color="text.secondary">
              Execute a query to visualize the graph
            </Typography>
          )}
        </Box>
      </Paper>
    </Box>
  );
};

export default VisualizeTab;