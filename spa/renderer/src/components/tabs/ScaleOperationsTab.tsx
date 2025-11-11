import React, { useState } from 'react';
import {
  Box,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Alert,
  Typography,
} from '@mui/material';
import { TrendingUp as ScaleUpIcon, TrendingDown as ScaleDownIcon } from '@mui/icons-material';
import { useScaleOperations, ScaleOperationsProvider } from '../../context/ScaleOperationsContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import ScaleUpPanel from '../scale/ScaleUpPanel';
import ScaleDownPanel from '../scale/ScaleDownPanel';
import ProgressMonitor from '../scale/ProgressMonitor';
import ResultsPanel from '../scale/ResultsPanel';
import QuickActionsBar from '../scale/QuickActionsBar';

const ScaleOperationsTabContent: React.FC = () => {
  const { state, dispatch } = useScaleOperations();
  const { isConnected } = useWebSocket();
  const [operationType, setOperationType] = useState<'scale-up' | 'scale-down'>('scale-up');

  const handleOperationTypeChange = (
    event: React.MouseEvent<HTMLElement>,
    newType: 'scale-up' | 'scale-down' | null
  ) => {
    if (newType !== null) {
      setOperationType(newType);
      dispatch({ type: 'SET_OPERATION_TYPE', payload: newType });
    }
  };

  // Show appropriate view based on operation status
  const isOperationRunning = state.currentOperation.status === 'running' ||
                             state.currentOperation.status === 'validating';
  const showResults = state.showResults && state.lastResult;

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2, p: 2, overflow: 'auto' }}>
      {/* Page Title */}
      <Box>
        <Typography variant="h5" gutterBottom>
          Scale Operations
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Add synthetic nodes (scale-up) or sample the graph (scale-down) for testing and validation
        </Typography>
      </Box>

      {/* Connection Status */}
      {!isConnected && (
        <Alert severity="warning">
          Not connected to backend server. Real-time updates may not work properly.
        </Alert>
      )}

      {/* Operation Mode Selector */}
      {!isOperationRunning && !showResults && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Choose Operation Mode
          </Typography>
          <ToggleButtonGroup
            value={operationType}
            exclusive
            onChange={handleOperationTypeChange}
            fullWidth
            sx={{ mb: 1 }}
            aria-label="operation mode"
          >
            <ToggleButton value="scale-up" aria-label="scale up">
              <ScaleUpIcon sx={{ mr: 1 }} />
              Scale Up (Add Nodes)
            </ToggleButton>
            <ToggleButton value="scale-down" aria-label="scale down">
              <ScaleDownIcon sx={{ mr: 1 }} />
              Scale Down (Sample)
            </ToggleButton>
          </ToggleButtonGroup>
        </Paper>
      )}

      {/* Configuration Panels */}
      {!isOperationRunning && !showResults && (
        <>
          {operationType === 'scale-up' && <ScaleUpPanel />}
          {operationType === 'scale-down' && <ScaleDownPanel />}
        </>
      )}

      {/* Progress Monitor (shown during operation) */}
      {isOperationRunning && <ProgressMonitor />}

      {/* Results Panel (shown after completion) */}
      {showResults && <ResultsPanel result={state.lastResult!} />}

      {/* Quick Actions Bar (always visible) */}
      {!isOperationRunning && <QuickActionsBar />}
    </Box>
  );
};

// Wrap with provider for context
const ScaleOperationsTab: React.FC = () => {
  return (
    <ScaleOperationsProvider>
      <ScaleOperationsTabContent />
    </ScaleOperationsProvider>
  );
};

export default ScaleOperationsTab;
