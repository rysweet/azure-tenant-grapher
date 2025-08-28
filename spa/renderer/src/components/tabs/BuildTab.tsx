import React, { useState } from 'react';
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
} from '@mui/material';
import { PlayArrow as PlayIcon, Stop as StopIcon } from '@mui/icons-material';
import LogViewer from '../common/LogViewer';
import { useApp } from '../../context/AppContext';
import { isValidTenantId, isValidResourceLimit, isValidThreadCount } from '../../utils/validation';

const BuildTab: React.FC = () => {
  const { state, dispatch } = useApp();
  const [tenantId, setTenantId] = useState(state.config.tenantId || '');
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

  const handleStart = async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return;
    }

    if (!isValidTenantId(tenantId)) {
      setError('Invalid Tenant ID format. Must be a valid UUID or domain.');
      return;
    }

    if (!isValidResourceLimit(resourceLimit)) {
      setError('Resource limit must be between 0 and 10000');
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
      '--resource-limit', resourceLimit.toString(),
      '--max-llm-threads', maxLlmThreads.toString(),
      '--max-build-threads', maxBuildThreads.toString(),
    ];

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
    // Parse logs to estimate progress
    for (const line of logLines) {
      if (line.includes('Discovering resources')) setProgress(10);
      else if (line.includes('Processing resources')) setProgress(30);
      else if (line.includes('Creating relationships')) setProgress(60);
      else if (line.includes('Generating descriptions')) setProgress(80);
      else if (line.includes('Complete')) setProgress(100);
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Build Azure Tenant Graph
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
              helperText="Azure AD Tenant ID"
              required
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <Typography gutterBottom>
                Resource Limit: {resourceLimit === 0 ? 'Unlimited' : resourceLimit}
              </Typography>
              <Slider
                value={resourceLimit}
                onChange={(_, value) => setResourceLimit(value as number)}
                min={0}
                max={1000}
                step={10}
                disabled={isRunning}
                marks={[
                  { value: 0, label: '0' },
                  { value: 500, label: '500' },
                  { value: 1000, label: '1000' },
                ]}
              />
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <Typography gutterBottom>
                Max LLM Threads: {maxLlmThreads}
              </Typography>
              <Slider
                value={maxLlmThreads}
                onChange={(_, value) => setMaxLlmThreads(value as number)}
                min={1}
                max={20}
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
                onChange={(_, value) => setMaxBuildThreads(value as number)}
                min={1}
                max={50}
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
              label="Rebuild Edges"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={noAadImport}
                  onChange={(e) => setNoAadImport(e.target.checked)}
                  disabled={isRunning}
                />
              }
              label="Skip AAD Import"
            />
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              {!isRunning ? (
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<PlayIcon />}
                  onClick={handleStart}
                  size="large"
                >
                  Start Build
                </Button>
              ) : (
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={handleStop}
                  size="large"
                >
                  Stop Build
                </Button>
              )}
              
              {isRunning && (
                <Box sx={{ flex: 1 }}>
                  <LinearProgress variant="determinate" value={progress} />
                  <Typography variant="caption" color="text.secondary">
                    {progress}% Complete
                  </Typography>
                </Box>
              )}
            </Box>
          </Grid>
        </Grid>
      </Paper>

      <Box sx={{ flex: 1, minHeight: 0 }}>
        <LogViewer
          logs={logs}
          onClear={() => setLogs([])}
          height="100%"
        />
      </Box>
    </Box>
  );
};

export default BuildTab;