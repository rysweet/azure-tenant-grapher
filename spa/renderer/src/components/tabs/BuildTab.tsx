import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Grid,
  FormControl,
  FormControlLabel,
  Checkbox,
  Typography,
  LinearProgress,
  Alert,
  Slider,
  Card,
  CardContent,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
} from '@mui/material';
import { 
  PlayArrow as PlayIcon, 
  Stop as StopIcon, 
  Refresh as RefreshIcon,
  Update as UpdateIcon,
  Storage as StorageIcon,
  AccountTree as TreeIcon,
  Link as LinkIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import axios from 'axios';
import LogViewer from '../common/LogViewer';
import { useApp } from '../../context/AppContext';
import { isValidTenantId, isValidResourceLimit, isValidThreadCount } from '../../utils/validation';

interface DBStats {
  nodeCount: number;
  edgeCount: number;
  nodeTypes: Array<{ type: string; count: number }>;
  edgeTypes: Array<{ type: string; count: number }>;
  lastUpdate: string | null;
  isEmpty: boolean;
  labelCount?: number;
  relTypeCount?: number;
}

const BuildTab: React.FC = () => {
  const { state, dispatch } = useApp();
  const [tenantId, setTenantId] = useState(state.config.tenantId || '');
  const [hasResourceLimit, setHasResourceLimit] = useState(false);
  const [resourceLimit, setResourceLimit] = useState<number>(100);
  const [maxLlmThreads, setMaxLlmThreads] = useState<number>(5);
  const [maxBuildThreads, setMaxBuildThreads] = useState<number>(10);
  const [rebuildEdges, setRebuildEdges] = useState(false);
  const [noAadImport, setNoAadImport] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [currentProcessId, setCurrentProcessId] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  
  // Database stats
  const [dbStats, setDbStats] = useState<DBStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [dbPopulated, setDbPopulated] = useState(false);
  const [neo4jStatus, setNeo4jStatus] = useState<any>(null);
  const [startingNeo4j, setStartingNeo4j] = useState(false);

  useEffect(() => {
    // Check Neo4j status and load DB stats on mount
    checkNeo4jStatus();
    loadEnvConfig();
  }, []);

  const loadEnvConfig = async () => {
    try {
      const response = await axios.get('http://localhost:3001/api/config/env');
      const envData = response.data;
      
      // Set values from .env if available
      if (envData.AZURE_TENANT_ID) {
        setTenantId(envData.AZURE_TENANT_ID);
        dispatch({ type: 'UPDATE_CONFIG', payload: { tenantId: envData.AZURE_TENANT_ID } });
      }
      
      // Note: ResourceLimit is typically not set in .env but could be
      if (envData.RESOURCE_LIMIT) {
        setHasResourceLimit(true);
        setResourceLimit(parseInt(envData.RESOURCE_LIMIT, 10));
      }
    } catch (err) {
      console.error('Failed to load env config:', err);
    }
  };

  const checkNeo4jStatus = async () => {
    try {
      const response = await axios.get('http://localhost:3001/api/neo4j/status');
      setNeo4jStatus(response.data);
      
      // If Neo4j is running, load database stats
      if (response.data.running) {
        await loadDatabaseStats();
      }
    } catch (err) {
      console.error('Failed to check Neo4j status:', err);
      setNeo4jStatus({ status: 'error', running: false });
    }
  };

  const startNeo4j = async () => {
    setStartingNeo4j(true);
    setError(null);
    try {
      await axios.post('http://localhost:3001/api/neo4j/start');
      // Wait a bit for Neo4j to start
      setTimeout(async () => {
        await checkNeo4jStatus();
        setStartingNeo4j(false);
      }, 3000);
    } catch (err: any) {
      setError('Failed to start Neo4j: ' + (err.response?.data?.error || err.message));
      setStartingNeo4j(false);
    }
  };

  const loadDatabaseStats = async () => {
    setLoadingStats(true);
    try {
      const response = await axios.get('http://localhost:3001/api/graph/stats');
      const stats = response.data;
      setDbStats(stats);
      setDbPopulated(!stats.isEmpty);
    } catch (err) {
      console.error('Failed to load database stats:', err);
      setDbPopulated(false);
    } finally {
      setLoadingStats(false);
    }
  };

  const handleStart = async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return;
    }

    if (!isValidTenantId(tenantId)) {
      setError('Invalid Tenant ID format. Must be a valid UUID or domain.');
      return;
    }

    // Only validate resource limit if it's being used
    if (hasResourceLimit && !isValidResourceLimit(resourceLimit)) {
      setError('Resource limit must be between 1 and 10000');
      return;
    }

    if (!isValidThreadCount(maxLlmThreads) || !isValidThreadCount(maxBuildThreads)) {
      setError('Thread counts must be between 1 and 100');
      return;
    }

    setError(null);
    setIsRunning(true);
    setLogs([]);
    setProgress(0);

    const args = [
      '--tenant-id', tenantId,
      '--max-llm-threads', maxLlmThreads.toString(),
      '--max-build-threads', maxBuildThreads.toString(),
    ];

    // Only add resource limit if checkbox is checked
    if (hasResourceLimit) {
      args.push('--resource-limit', resourceLimit.toString());
    }
    
    if (rebuildEdges) args.push('--rebuild-edges');
    if (noAadImport) args.push('--no-aad-import');

    try {
      const result = await window.electronAPI.cli.execute('build', args);
      setCurrentProcessId(result.data.id);
      
      // Listen for output
      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          setLogs((prev) => [...prev, ...data.data]);
          // Update progress based on log patterns
          updateProgress(data.data);
        }
      });

      // Listen for completion
      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsRunning(false);
          setProgress(100);
          if (data.code === 0) {
            setLogs((prev) => [...prev, 'Build completed successfully!']);
            // Reload stats after successful build
            loadDatabaseStats();
          } else {
            setError(`Build failed with exit code ${data.code}`);
          }
        }
      });

      // Save config
      dispatch({ type: 'SET_CONFIG', payload: { tenantId } });
      
    } catch (err: any) {
      setError(err.message);
      setIsRunning(false);
    }
  };

  const handleStop = async () => {
    if (currentProcessId) {
      try {
        await window.electronAPI.cli.cancel(currentProcessId);
        setIsRunning(false);
        setLogs((prev) => [...prev, 'Build cancelled by user']);
      } catch (err: any) {
        setError(err.message);
      }
    }
  };

  const updateProgress = (logLines: string[]) => {
    for (const line of logLines) {
      if (line.includes('Discovering resources')) {
        setProgress(20);
      } else if (line.includes('Processing resources')) {
        setProgress(40);
      } else if (line.includes('Creating relationships')) {
        setProgress(60);
      } else if (line.includes('Building edges')) {
        setProgress(80);
      } else if (line.includes('completed')) {
        setProgress(100);
      }
    }
  };

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp).toLocaleString();
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Neo4j Status Alert - Show when Neo4j is not running */}
      {neo4jStatus && !neo4jStatus.running && (
        <Alert 
          severity="warning" 
          sx={{ mb: 2 }}
          action={
            <Button 
              color="inherit" 
              size="small" 
              onClick={startNeo4j}
              disabled={startingNeo4j}
            >
              {startingNeo4j ? 'Starting...' : 'Start Neo4j'}
            </Button>
          }
        >
          Neo4j database is not running. Start it to begin building or viewing your graph.
        </Alert>
      )}

      {/* Database Stats Section - Show when DB is populated */}
      {dbPopulated && dbStats && neo4jStatus?.running && (
        <Paper sx={{ p: 3, mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <StorageIcon /> Database Status
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title="Refresh Stats">
                <IconButton onClick={checkNeo4jStatus} disabled={loadingStats}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
          
          <Grid container spacing={3}>
            <Grid item xs={12} md={3}>
              <Card variant="outlined">
                <CardContent>
                  <Typography color="textSecondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TreeIcon fontSize="small" /> Total Nodes
                  </Typography>
                  <Typography variant="h4">
                    {formatNumber(dbStats.nodeCount)}
                  </Typography>
                  {dbStats.labelCount && (
                    <Typography variant="caption" color="textSecondary">
                      {dbStats.labelCount} types
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <Card variant="outlined">
                <CardContent>
                  <Typography color="textSecondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <LinkIcon fontSize="small" /> Total Edges
                  </Typography>
                  <Typography variant="h4">
                    {formatNumber(dbStats.edgeCount)}
                  </Typography>
                  {dbStats.relTypeCount && (
                    <Typography variant="caption" color="textSecondary">
                      {dbStats.relTypeCount} types
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <Card variant="outlined">
                <CardContent>
                  <Typography color="textSecondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <ScheduleIcon fontSize="small" /> Last Update
                  </Typography>
                  <Typography variant="body1">
                    {formatTimestamp(dbStats.lastUpdate)}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <Card variant="outlined">
                <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography color="textSecondary" gutterBottom>
                    Quick Actions
                  </Typography>
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={<UpdateIcon />}
                    onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}
                    fullWidth
                  >
                    Update Graph
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Node and Edge Type Breakdown */}
          <Box sx={{ mt: 3 }}>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Node Types</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {dbStats.nodeTypes.slice(0, 10).map((nodeType) => (
                    <Chip
                      key={nodeType.type}
                      label={`${nodeType.type}: ${formatNumber(nodeType.count)}`}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                  {dbStats.nodeTypes.length > 10 && (
                    <Chip
                      label={`+${dbStats.nodeTypes.length - 10} more`}
                      size="small"
                      variant="outlined"
                      color="primary"
                    />
                  )}
                </Box>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Edge Types</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {dbStats.edgeTypes.slice(0, 10).map((edgeType) => (
                    <Chip
                      key={edgeType.type}
                      label={`${edgeType.type}: ${formatNumber(edgeType.count)}`}
                      size="small"
                      variant="outlined"
                      color="secondary"
                    />
                  ))}
                  {dbStats.edgeTypes.length > 10 && (
                    <Chip
                      label={`+${dbStats.edgeTypes.length - 10} more`}
                      size="small"
                      variant="outlined"
                      color="secondary"
                    />
                  )}
                </Box>
              </Grid>
            </Grid>
          </Box>
        </Paper>
      )}

      {/* Build Configuration Section */}
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          {dbPopulated ? 'Update Graph Database' : 'Build Graph Database'}
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Tenant ID"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              disabled={isRunning}
              helperText="Azure Tenant ID or domain (e.g., contoso.onmicrosoft.com)"
              error={!!error && error.includes('Tenant ID')}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={hasResourceLimit}
                    onChange={(e) => setHasResourceLimit(e.target.checked)}
                    disabled={isRunning}
                  />
                }
                label="Set Resource Limit (default: unlimited)"
              />
              {hasResourceLimit && (
                <Box sx={{ mt: 2 }}>
                  <Typography gutterBottom>
                    Resource Limit: {resourceLimit}
                  </Typography>
                  <Slider
                    value={resourceLimit}
                    onChange={(e, value) => setResourceLimit(value as number)}
                    min={10}
                    max={1000}
                    step={10}
                    marks={[
                      { value: 100, label: '100' },
                      { value: 500, label: '500' },
                      { value: 1000, label: '1000' },
                    ]}
                    disabled={isRunning}
                  />
                </Box>
              )}
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <Typography gutterBottom>
                Max LLM Threads: {maxLlmThreads}
              </Typography>
              <Slider
                value={maxLlmThreads}
                onChange={(e, value) => setMaxLlmThreads(value as number)}
                min={1}
                max={20}
                marks
                disabled={isRunning}
              />
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <Typography gutterBottom>
                Max Build Threads: {maxBuildThreads}
              </Typography>
              <Slider
                value={maxBuildThreads}
                onChange={(e, value) => setMaxBuildThreads(value as number)}
                min={1}
                max={20}
                marks
                disabled={isRunning}
              />
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={rebuildEdges}
                  onChange={(e) => setRebuildEdges(e.target.checked)}
                  disabled={isRunning}
                />
              }
              label="Rebuild edges (clears existing relationships)"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={noAadImport}
                  onChange={(e) => setNoAadImport(e.target.checked)}
                  disabled={isRunning}
                />
              }
              label="Skip Azure AD import"
            />
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Button
                variant="contained"
                color={isRunning ? 'error' : 'primary'}
                startIcon={isRunning ? <StopIcon /> : dbPopulated ? <UpdateIcon /> : <PlayIcon />}
                onClick={isRunning ? handleStop : handleStart}
                size="large"
              >
                {isRunning ? 'Stop Build' : dbPopulated ? 'Update Database' : 'Start Build'}
              </Button>
              
              {isRunning && (
                <Box sx={{ flex: 1 }}>
                  <LinearProgress variant="determinate" value={progress} />
                  <Typography variant="caption" color="textSecondary">
                    {progress}% Complete
                  </Typography>
                </Box>
              )}
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Log Output */}
      {logs.length > 0 && (
        <Paper sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="h6">Build Output</Typography>
          </Box>
          <LogViewer logs={logs} />
        </Paper>
      )}
    </Box>
  );
};

export default BuildTab;