import React, { useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  LinearProgress,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
} from '@mui/material';
import { Stop as StopIcon, CheckCircle, Pending, Error as ErrorIcon } from '@mui/icons-material';
import { useScaleOperations } from '../../context/ScaleOperationsContext';
import { useScaleUpOperation } from '../../hooks/useScaleUpOperation';
import LogViewer from '../common/LogViewer';

const ProgressMonitor: React.FC = () => {
  const { state, dispatch } = useScaleOperations();
  const { cancelOperation } = useScaleUpOperation();
  const logViewerRef = useRef<HTMLDivElement>(null);

  const progress = state.currentOperation.progress;
  const logs = state.currentOperation.logs;

  // Format elapsed time
  const formatElapsedTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Auto-scroll logs if enabled
  useEffect(() => {
    if (state.autoScroll && logViewerRef.current) {
      logViewerRef.current.scrollTop = logViewerRef.current.scrollHeight;
    }
  }, [logs, state.autoScroll]);

  const getStatusIcon = () => {
    switch (state.currentOperation.status) {
      case 'running':
        return <Pending color="primary" />;
      case 'success':
        return <CheckCircle color="success" />;
      case 'error':
        return <ErrorIcon color="error" />;
      default:
        return null;
    }
  };

  const getStatusColor = (): 'default' | 'primary' | 'success' | 'error' | 'warning' => {
    switch (state.currentOperation.status) {
      case 'running':
        return 'primary';
      case 'success':
        return 'success';
      case 'error':
        return 'error';
      case 'validating':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {getStatusIcon()}
          <Box>
            <Typography variant="h6">
              {state.operationType === 'scale-up' ? 'Scale-Up' : 'Scale-Down'} in Progress
            </Typography>
            <Chip
              label={state.currentOperation.status}
              color={getStatusColor()}
              size="small"
              sx={{ mt: 0.5 }}
            />
          </Box>
        </Box>
        <Button
          variant="contained"
          color="error"
          startIcon={<StopIcon />}
          onClick={cancelOperation}
          size="small"
          disabled={state.currentOperation.status !== 'running'}
        >
          Stop Operation
        </Button>
      </Box>

      {/* Progress Bar */}
      <Box sx={{ mb: 3 }}>
        <LinearProgress
          variant="determinate"
          value={progress?.progress || 0}
          sx={{ height: 10, borderRadius: 1 }}
        />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {progress?.progress || 0}% Complete
          </Typography>
          <Typography variant="body2" color="primary" fontWeight="bold">
            {progress?.phase || 'Initializing...'}
          </Typography>
        </Box>
      </Box>

      {/* Statistics Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {state.operationType === 'scale-up' ? 'Nodes Created' : 'Nodes Deleted'}
              </Typography>
              <Typography variant="h5" color="primary">
                {state.operationType === 'scale-up'
                  ? progress?.stats?.nodesCreated || 0
                  : progress?.stats?.nodesDeleted || 0
                }
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                Relationships Affected
              </Typography>
              <Typography variant="h5" color="primary">
                {progress?.stats?.relationshipsAffected || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                Validation Status
              </Typography>
              <Typography variant="h6" color={progress?.stats?.validationPassed ? 'success.main' : 'text.secondary'}>
                {progress?.stats?.validationPassed ? '✓ Passed' : '⏳ Pending'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                Elapsed Time
              </Typography>
              <Typography variant="h5" color="primary">
                {formatElapsedTime(progress?.elapsedSeconds || 0)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Live Log Viewer */}
      <Paper variant="outlined" sx={{ height: 400, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle2">Live Output</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label={state.autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
              size="small"
              color={state.autoScroll ? 'primary' : 'default'}
              onClick={() => dispatch({ type: 'TOGGLE_AUTO_SCROLL' })}
              clickable
            />
            <Chip
              label={`${logs.length} lines`}
              size="small"
              variant="outlined"
            />
          </Box>
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto' }} ref={logViewerRef}>
          <LogViewer logs={logs} />
        </Box>
      </Paper>
    </Paper>
  );
};

export default ProgressMonitor;
