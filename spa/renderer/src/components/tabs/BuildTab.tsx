import React, { useState, useEffect, useCallback } from 'react';
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
import { io, Socket } from 'socket.io-client';
import LogViewer from '../common/LogViewer';
import { useApp } from '../../context/AppContext';
import { useBackgroundOperations } from '../../hooks/useBackgroundOperations';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useLogger } from '../../hooks/useLogger';
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
  const { addBackgroundOperation, updateBackgroundOperation, removeBackgroundOperation } = useBackgroundOperations();
  const { isConnected, subscribeToProcess, unsubscribeFromProcess, getProcessOutput } = useWebSocket();
  const logger = useLogger('Build');
  
  // State declarations
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
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const [processSocket, setProcessSocket] = useState<Socket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  
  // Build statistics
  const [buildStats, setBuildStats] = useState({
    resourcesDiscovered: 0,
    nodesCreated: 0,
    edgesCreated: 0,
    currentPhase: 'Initializing'
  });
  
  // Database stats
  const [dbStats, setDbStats] = useState<DBStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [dbPopulated, setDbPopulated] = useState(false);
  const [neo4jStatus, setNeo4jStatus] = useState<any>(null);
  const [startingNeo4j, setStartingNeo4j] = useState(false);

  // All useCallback function definitions (must come before useEffect hooks)
  const loadDatabaseStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const response = await axios.get('http://localhost:3001/api/graph/stats');
      const stats = response.data;
      setDbStats(stats);
      setDbPopulated(!stats.isEmpty);
    } catch (err) {
      // Handle database stats loading error silently
      // Set empty stats when database is empty or error occurs
      setDbStats({
        nodeCount: 0,
        edgeCount: 0,
        nodeTypes: [],
        edgeTypes: [],
        lastUpdate: null,
        isEmpty: true
      });
      setDbPopulated(false);
    } finally {
      setLoadingStats(false);
    }
  }, []);

  const checkNeo4jStatus = useCallback(async () => {
    try {
      const response = await axios.get('http://localhost:3001/api/neo4j/status', {
        timeout: 5000 // 5 second timeout
      });
      setNeo4jStatus(response.data);
      
      // If Neo4j is running, load database stats
      if (response.data.running) {
        await loadDatabaseStats();
      }
    } catch (err: any) {
      // Handle Neo4j status check error
      
      // Check if it's a connection error (backend not running)
      if (err.code === 'ECONNREFUSED' || err.code === 'ERR_NETWORK') {
        throw err; // Rethrow to trigger retry
      }
      
      setNeo4jStatus({ status: 'error', running: false });
    }
  }, [loadDatabaseStats]);

  const loadEnvConfig = useCallback(async () => {
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
      // Handle env config loading error
      throw err; // Re-throw to trigger retry
    }
  }, [dispatch]);

  const updateProgress = useCallback((logLines: string[]) => {
    for (const line of logLines) {
      // Update phase
      if (line.includes('Starting discovery') || line.includes('Discovering')) {
        setProgress(10);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Discovery' }));
      } else if (line.includes('Fetching subscriptions')) {
        setProgress(15);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Fetching Subscriptions' }));
      } else if (line.includes('Discovering resources')) {
        setProgress(20);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Discovering Resources' }));
      } else if (line.includes('Processing') && line.includes('resources')) {
        setProgress(35);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Processing Resources' }));
      } else if (line.includes('Creating nodes')) {
        setProgress(40);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Creating Nodes' }));
      } else if (line.includes('Building relationships') || line.includes('Creating relationships')) {
        setProgress(60);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Building Relationships' }));
      } else if (line.includes('Creating edges') || line.includes('Building edges')) {
        setProgress(75);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Creating Edges' }));
      } else if (line.includes('Applying rules')) {
        setProgress(85);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Applying Rules' }));
      } else if (line.includes('Finalizing') || line.includes('Cleaning up')) {
        setProgress(95);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Finalizing' }));
      } else if (line.includes('✅') && line.includes('completed')) {
        setProgress(100);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Complete' }));
      } else if (line.includes('Build complete') || line.includes('Successfully built')) {
        setProgress(100);
        setBuildStats(prev => ({ ...prev, currentPhase: 'Complete' }));
      }
      
      // Parse statistics from log lines
      const resourceCountMatch = line.match(/Discovered (\d+) resources/);
      if (resourceCountMatch) {
        setBuildStats(prev => ({ ...prev, resourcesDiscovered: parseInt(resourceCountMatch[1]) }));
      }
      
      const nodeCountMatch = line.match(/Created (\d+) nodes/);
      if (nodeCountMatch) {
        setBuildStats(prev => ({ ...prev, nodesCreated: parseInt(nodeCountMatch[1]) }));
      }
      
      const edgeCountMatch = line.match(/Created (\d+) (edges|relationships)/);
      if (edgeCountMatch) {
        setBuildStats(prev => ({ ...prev, edgesCreated: parseInt(edgeCountMatch[1]) }));
      }
      
      // Also check for resource counts to estimate progress
      const resourceMatch = line.match(/Processing (\d+)\/(\d+)/);
      if (resourceMatch) {
        const current = parseInt(resourceMatch[1]);
        const total = parseInt(resourceMatch[2]);
        const pct = Math.round((current / total) * 60) + 20; // 20-80% range for processing
        setProgress(pct);
      }
    }
  }, []);

  // Define event handlers with useCallback to avoid stale closures
  const handleProcessExit = useCallback((event: { processId: string; code?: number; timestamp: string }) => {
    if (event.processId === currentProcessId) {
      setIsRunning(false);
      setProgress(100);
      
      // Update background operation status
      if (event.code === 0) {
        setLogs((prev) => [...prev, '✅ Build completed successfully!']);
        updateBackgroundOperation(event.processId, { status: 'completed' });
        dispatch({ type: 'ADD_LOG', payload: 'Build completed successfully' });
        // Reload stats after successful build
        loadDatabaseStats();
      } else {
        setError(`Build failed with exit code ${event.code}`);
        setLogs((prev) => [...prev, `❌ Build failed with exit code ${event.code}`]);
        updateBackgroundOperation(event.processId, { status: 'error' });
        dispatch({ type: 'ADD_LOG', payload: `Build failed with exit code ${event.code}` });
      }
      
      // Clean up
      unsubscribeFromProcess(event.processId);
      
      // Remove from background operations after 5 seconds
      setTimeout(() => {
        removeBackgroundOperation(event.processId);
      }, 5000);
    }
  }, [currentProcessId, updateBackgroundOperation, dispatch, loadDatabaseStats, unsubscribeFromProcess, removeBackgroundOperation]);

  const handleProcessError = useCallback((event: { processId: string; error?: string; timestamp: string }) => {
    if (event.processId === currentProcessId) {
      setIsRunning(false);
      setError(`Process error: ${event.error}`);
      setLogs((prev) => [...prev, `❌ Process error: ${event.error}`]);
      updateBackgroundOperation(event.processId, { status: 'error' });
      dispatch({ type: 'ADD_LOG', payload: `Process error: ${event.error}` });
      
      // Clean up
      unsubscribeFromProcess(event.processId);
    }
  }, [currentProcessId, updateBackgroundOperation, dispatch, unsubscribeFromProcess]);

  // useEffect hooks (now can safely use the functions defined above)
  // Track WebSocket connection status
  useEffect(() => {
    if (isConnected) {
      setConnectionStatus('connected');
      dispatch({ type: 'ADD_LOG', payload: 'Connected to backend server' });
    } else {
      setConnectionStatus('disconnected');
      dispatch({ type: 'ADD_LOG', payload: 'Disconnected from backend server' });
    }
  }, [isConnected, dispatch]);

  // Set up dedicated Socket.IO connection for process events
  useEffect(() => {
    if (!isConnected || processSocket) {
      return; // Don't create socket if not connected or socket already exists
    }

    const socket = io('http://localhost:3001');
    
    socket.on('connect', () => {
      // Process event socket connected
    });
    
    socket.on('process-exit', handleProcessExit);
    socket.on('process-error', handleProcessError);
    
    setProcessSocket(socket);
    
    return () => {
      socket.disconnect();
      setProcessSocket(null);
    };
  }, [isConnected, handleProcessExit, handleProcessError]);

  // Monitor process output in real-time
  useEffect(() => {
    if (currentProcessId && isRunning) {
      const processOutput = getProcessOutput(currentProcessId);
      if (processOutput.length > logs.length) {
        const newLogs = processOutput.slice(logs.length);
        setLogs(processOutput);
        updateProgress(newLogs);
      }
    }
  }, [currentProcessId, isRunning, getProcessOutput, logs.length, updateProgress]);

  // Cleanup when component unmounts
  useEffect(() => {
    return () => {
      if (currentProcessId && isRunning) {
        unsubscribeFromProcess(currentProcessId);
      }
    };
  }, [currentProcessId, isRunning, unsubscribeFromProcess]);

  useEffect(() => {
    // Check Neo4j status and load DB stats on mount with retry
    const initializeTab = async () => {
      let retries = 0;
      const maxRetries = 5;
      
      const tryInit = async () => {
        try {
          await checkNeo4jStatus();
          await loadEnvConfig();
        } catch (err) {
          if (retries < maxRetries) {
            retries++;
            setTimeout(tryInit, 2000); // Retry after 2 seconds
          } else {
            setNeo4jStatus({ status: 'error', running: false, message: 'Backend server not responding' });
          }
        }
      };
      
      tryInit();
    };
    
    initializeTab();
  }, []); // Remove circular dependencies, run only on mount

  // Separate useEffect for auto-refresh to avoid circular dependency
  useEffect(() => {
    if (!neo4jStatus?.running || isRunning) {
      return; // Don't set up interval if Neo4j not running or build is running
    }

    // Set up auto-refresh every 5 seconds for database stats
    const refreshInterval = setInterval(async () => {
      try {
        await checkNeo4jStatus();
      } catch (err) {
        // Handle refresh error silently
      }
    }, 5000);
    
    return () => clearInterval(refreshInterval);
  }, [neo4jStatus?.running, isRunning, checkNeo4jStatus]);

  // Other function definitions (not used in useEffect hooks)
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

    if (!isConnected) {
      setError('Not connected to backend server. Please check if the backend is running.');
      return;
    }

    logger.info(`Starting build process for tenant: ${tenantId}`, { 
      tenantId, 
      hasResourceLimit, 
      resourceLimit: hasResourceLimit ? resourceLimit : null
    });

    setError(null);
    setIsRunning(true);
    setLogs([]);
    setProgress(0);
    setBuildStats({
      resourcesDiscovered: 0,
      nodesCreated: 0,
      edgesCreated: 0,
      currentPhase: 'Initializing'
    });

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
      // Use backend API instead of Electron API
      const response = await axios.post('http://localhost:3001/api/execute', {
        command: 'build',
        args: args
      });
      
      const processId = response.data.processId;
      setCurrentProcessId(processId);
      
      logger.logProcessEvent(processId, 'started');
      
      // Add to background operations tracker
      addBackgroundOperation({
        id: processId,
        type: 'Build',
        name: `Building graph for ${tenantId}`,
        // Backend handles PID internally, so we don't include it
      });
      
      // Subscribe to process output via WebSocket
      subscribeToProcess(processId);
      
      // Check if process is already running by polling status initially
      setTimeout(async () => {
        try {
          const statusResponse = await axios.get(`http://localhost:3001/api/status/${processId}`);
          // Process status retrieved successfully
        } catch (err) {
          // Process might have already completed, that's ok
        }
      }, 1000);

      // Save config
      dispatch({ type: 'SET_CONFIG', payload: { tenantId } });
      
    } catch (err: any) {
      dispatch({ type: 'ADD_LOG', payload: `Build failed to start: ${err.message}` });
      setError(err.response?.data?.error || err.message);
      setIsRunning(false);
    }
  };

  const handleStop = async () => {
    if (currentProcessId) {
      try {
        dispatch({ type: 'ADD_LOG', payload: `Stopping process: ${currentProcessId}` });
        
        // Cancel the process via backend API
        await axios.post(`http://localhost:3001/api/cancel/${currentProcessId}`);
        
        // Clean up WebSocket subscription
        unsubscribeFromProcess(currentProcessId);
        
        setIsRunning(false);
        setLogs((prev) => [...prev, 'Build cancelled by user']);
        dispatch({ type: 'ADD_LOG', payload: 'Build cancelled by user' });
      } catch (err: any) {
        setError(err.response?.data?.error || err.message);
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
      {/* WebSocket Connection Status */}
      {connectionStatus !== 'connected' && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          WebSocket {connectionStatus === 'connecting' ? 'connecting to' : 'disconnected from'} backend server. 
          Real-time updates may not work properly.
        </Alert>
      )}
      
      {/* Connection Status for Connected State */}
      {connectionStatus === 'connected' && !isRunning && (
        <Alert severity="success" sx={{ mb: 2 }}>
          ✓ Connected to backend server - Ready to start builds with real-time monitoring
        </Alert>
      )}
      
      {/* Backend/Neo4j Status Alert */}
      {neo4jStatus && neo4jStatus.message && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {neo4jStatus.message}
        </Alert>
      )}
      
      {/* Neo4j Status Alert - Show when Neo4j is not running */}
      {neo4jStatus && !neo4jStatus.message && !neo4jStatus.running && (
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

      {/* Neo4j Running Status - Always show when Neo4j is running */}
      {neo4jStatus && neo4jStatus.running && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Neo4j is connected. View database details in the Status tab.
        </Alert>
      )}

      {/* Show Build Dashboard when running, Configuration when not */}
      {isRunning ? (
        // Build Dashboard (CLI-like view)
        <>
          {/* Configuration Overview */}
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom>Build Configuration</Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Typography variant="body2" color="textSecondary">Tenant ID</Typography>
                <Typography variant="body1">{tenantId}</Typography>
              </Grid>
              <Grid item xs={12} md={2}>
                <Typography variant="body2" color="textSecondary">Resource Limit</Typography>
                <Typography variant="body1">{hasResourceLimit ? resourceLimit : 'Unlimited'}</Typography>
              </Grid>
              <Grid item xs={12} md={2}>
                <Typography variant="body2" color="textSecondary">LLM Threads</Typography>
                <Typography variant="body1">{maxLlmThreads}</Typography>
              </Grid>
              <Grid item xs={12} md={2}>
                <Typography variant="body2" color="textSecondary">Build Threads</Typography>
                <Typography variant="body1">{maxBuildThreads}</Typography>
              </Grid>
              <Grid item xs={12} md={2}>
                <Typography variant="body2" color="textSecondary">Options</Typography>
                <Typography variant="body1">
                  {[rebuildEdges && 'Rebuild Edges', noAadImport && 'No AAD'].filter(Boolean).join(', ') || 'None'}
                </Typography>
              </Grid>
            </Grid>
          </Paper>

          {/* Progress Dashboard */}
          <Paper sx={{ p: 2, mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Build Progress</Typography>
              <Button
                variant="contained"
                color="error"
                startIcon={<StopIcon />}
                onClick={handleStop}
                size="small"
              >
                Stop Build
              </Button>
            </Box>
            
            {/* Progress Bar */}
            <LinearProgress variant="determinate" value={progress} sx={{ mb: 1, height: 8 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="body2" color="textSecondary">
                {progress}% Complete
              </Typography>
              <Typography variant="body2" color="primary" fontWeight="bold">
                Phase: {buildStats.currentPhase}
              </Typography>
            </Box>
            
            {/* Build Statistics */}
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={4}>
                <Card variant="outlined" sx={{ p: 1 }}>
                  <Typography variant="caption" color="textSecondary">Resources Discovered</Typography>
                  <Typography variant="h6">{buildStats.resourcesDiscovered}</Typography>
                </Card>
              </Grid>
              <Grid item xs={4}>
                <Card variant="outlined" sx={{ p: 1 }}>
                  <Typography variant="caption" color="textSecondary">Nodes Created</Typography>
                  <Typography variant="h6">{buildStats.nodesCreated}</Typography>
                </Card>
              </Grid>
              <Grid item xs={4}>
                <Card variant="outlined" sx={{ p: 1 }}>
                  <Typography variant="caption" color="textSecondary">Edges Created</Typography>
                  <Typography variant="h6">{buildStats.edgesCreated}</Typography>
                </Card>
              </Grid>
            </Grid>
            
            {/* Current Status */}
            <Box sx={{ mt: 2, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
              <Typography variant="caption" color="textSecondary">Current Activity:</Typography>
              <Typography variant="body2" color="primary">
                {logs.length > 0 ? logs[logs.length - 1] : 'Initializing...'}
              </Typography>
            </Box>
          </Paper>
        </>
      ) : (
        // Build Configuration Form
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
                color="primary"
                startIcon={dbPopulated ? <UpdateIcon /> : <PlayIcon />}
                onClick={handleStart}
                size="large"
              >
                {dbPopulated ? 'Update Database' : 'Start Build'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>
      )}

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