# Scale Operations UI Design

## Overview

This document provides the complete UI design for the Scale Operations feature in the Azure Tenant Grapher Electron SPA. The design follows existing SPA architecture patterns and integrates seamlessly with the WebSocket-based real-time communication system.

## Component Architecture

### Component Hierarchy

```
ScaleOperationsTab (Main Container)
├── OperationModeSelector
│   ├── ScaleUpButton
│   └── ScaleDownButton
│
├── ScaleUpPanel (conditionally rendered)
│   ├── StrategySection
│   │   ├── StrategySelector (dropdown: template, scenario, random)
│   │   └── StrategyHelpText
│   ├── ParameterForm (dynamic based on strategy)
│   │   ├── TenantIdInput
│   │   ├── TemplateFileSelector (for template strategy)
│   │   ├── ScenarioTypeSelector (for scenario strategy)
│   │   ├── NodeCountInput (for random strategy)
│   │   └── PatternSelector (for random strategy)
│   ├── ValidationSection
│   │   └── ValidationAlert
│   └── ActionButtons
│       ├── PreviewButton
│       ├── ExecuteButton
│       └── ClearButton
│
├── ScaleDownPanel (conditionally rendered)
│   ├── AlgorithmSection
│   │   ├── AlgorithmSelector (dropdown: forest-fire, mhrw, pattern)
│   │   └── AlgorithmHelpText
│   ├── ParameterForm (dynamic based on algorithm)
│   │   ├── TenantIdInput
│   │   ├── SampleSizeInput
│   │   ├── BurnInInput (for forest-fire)
│   │   ├── WalkLengthInput (for mhrw)
│   │   └── PatternInput (for pattern-based)
│   ├── OutputModeSection
│   │   ├── OutputModeSelector (file, new-tenant, iac)
│   │   ├── OutputPathInput (for file mode)
│   │   └── IacFormatSelector (for iac mode)
│   ├── ValidationSection
│   │   └── ValidationAlert
│   └── ActionButtons
│       ├── PreviewButton
│       ├── ExecuteButton
│       └── ClearButton
│
├── ProgressMonitor (conditionally rendered when operation running)
│   ├── OperationHeader
│   │   ├── OperationTitle
│   │   ├── OperationStatus (idle, validating, running, success, error)
│   │   └── StopButton
│   ├── ProgressBar (with percentage)
│   ├── CurrentPhaseIndicator
│   ├── StatisticsGrid
│   │   ├── NodesCreatedCard (scale-up)
│   │   ├── NodesDeletedCard (scale-down)
│   │   ├── RelationshipsAffectedCard
│   │   ├── ValidationStatusCard
│   │   └── ElapsedTimeCard
│   └── LiveLogViewer (reuse existing LogViewer component)
│
├── ResultsPanel (conditionally rendered after operation completes)
│   ├── OperationSummary
│   │   ├── SuccessIcon / ErrorIcon
│   │   ├── SummaryText
│   │   └── Timestamp
│   ├── BeforeAfterComparison
│   │   ├── BeforeStats (node count, relationship count)
│   │   ├── ArrowIndicator
│   │   └── AfterStats (node count, relationship count)
│   ├── ValidationResults
│   │   ├── ValidationStatusList
│   │   └── IssuesFoundList (if any)
│   ├── OutputLocation (if applicable)
│   │   ├── PathDisplay
│   │   └── OpenFolderButton
│   └── ActionButtons
│       ├── ViewGraphButton (opens Visualize tab)
│       ├── GenerateIaCButton (for scale-down)
│       └── RunAnotherButton
│
└── QuickActionsBar (always visible)
    ├── CleanSyntheticDataButton
    ├── ValidateGraphButton
    ├── ShowStatsButton
    └── HelpButton
```

### Visual Layout (ASCII Mockup)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Scale Operations                                                      [Help]│
├────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ╔════════════════════════════════════════════════════════════════════╗   │
│  ║  Choose Operation Mode                                             ║   │
│  ╠════════════════════════════════════════════════════════════════════╣   │
│  ║                                                                     ║   │
│  ║   [ Scale Up (Add Nodes) ]   [ Scale Down (Sample) ]               ║   │
│  ║                                                                     ║   │
│  ╚════════════════════════════════════════════════════════════════════╝   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ Scale Up Configuration                                            │     │
│  ├──────────────────────────────────────────────────────────────────┤     │
│  │                                                                    │     │
│  │  Tenant ID:  [xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx] [↓]         │     │
│  │                                                                    │     │
│  │  Strategy:   [Template ↓]                                        │     │
│  │  ℹ️  Generate nodes based on a predefined template file           │     │
│  │                                                                    │     │
│  │  ┌────────────────────────────────────────────────────────────┐  │     │
│  │  │ Template Configuration                                      │  │     │
│  │  ├────────────────────────────────────────────────────────────┤  │     │
│  │  │  Template File:  [templates/scale_template.yaml] [Browse] │  │     │
│  │  │  Scale Factor:   [2] (2x multiplication)                   │  │     │
│  │  │  Validate First: [✓] Run validation before execution       │  │     │
│  │  └────────────────────────────────────────────────────────────┘  │     │
│  │                                                                    │     │
│  │  ✓ Validation Passed - 0 synthetic nodes currently in graph      │     │
│  │                                                                    │     │
│  │  [Preview Changes]  [Execute Scale-Up]  [Clear Form]            │     │
│  │                                                                    │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ ⚙️  Quick Actions                                                 │     │
│  ├──────────────────────────────────────────────────────────────────┤     │
│  │  [Clean Synthetic] [Validate Graph] [Show Statistics]            │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
```

### Operation In Progress View

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Scale Operations - Executing Scale-Up                                      │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ Scale-Up in Progress                            [Stop Operation] │     │
│  ├──────────────────────────────────────────────────────────────────┤     │
│  │                                                                    │     │
│  │  Progress: ████████████████████░░░░░░░░░  68%                    │     │
│  │  Phase: Creating synthetic nodes                                 │     │
│  │                                                                    │     │
│  │  ┌─────────────┬─────────────┬─────────────┬─────────────┐      │     │
│  │  │ Nodes       │ Relations   │ Validation  │ Elapsed     │      │     │
│  │  │ Created     │ Created     │ Status      │ Time        │      │     │
│  │  ├─────────────┼─────────────┼─────────────┼─────────────┤      │     │
│  │  │    2,458    │    5,123    │  ✓ Passed   │   00:02:34  │      │     │
│  │  └─────────────┴─────────────┴─────────────┴─────────────┘      │     │
│  │                                                                    │     │
│  │  ┌────────────────────────────────────────────────────────────┐  │     │
│  │  │ Live Output                                     [Auto-scroll]│  │     │
│  │  ├────────────────────────────────────────────────────────────┤  │     │
│  │  │ INFO  Starting scale-up operation...                       │  │     │
│  │  │ INFO  Using template: scale_template.yaml                  │  │     │
│  │  │ INFO  Created 245 VirtualMachine nodes                     │  │     │
│  │  │ INFO  Created 125 NetworkInterface nodes                   │  │     │
│  │  │ INFO  Building relationships...                            │  │     │
│  │  │ INFO  Running validation checks...                         │  │     │
│  │  │ ✓     Validation passed - graph is consistent              │  │     │
│  │  │ ▶     Phase 3/4: Finalizing...                            │  │     │
│  │  └────────────────────────────────────────────────────────────┘  │     │
│  │                                                                    │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
```

### Results View

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Scale Operations - Completed                                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ ✓ Scale-Up Completed Successfully          2024-03-15 14:23:45   │     │
│  ├──────────────────────────────────────────────────────────────────┤     │
│  │                                                                    │     │
│  │  Operation Summary:                                               │     │
│  │  Successfully scaled up graph by adding 2,458 synthetic nodes     │     │
│  │  and 5,123 relationships                                          │     │
│  │                                                                    │     │
│  │  Before & After Comparison:                                       │     │
│  │  ┌─────────────────┬──────────┬─────────────────┐               │     │
│  │  │ Metric          │  Before  │      After      │               │     │
│  │  ├─────────────────┼──────────┼─────────────────┤               │     │
│  │  │ Total Nodes     │   1,245  │  3,703 (+2,458) │               │     │
│  │  │ Relationships   │   2,890  │  8,013 (+5,123) │               │     │
│  │  │ Synthetic Nodes │       0  │         2,458   │               │     │
│  │  │ Node Types      │      12  │            12   │               │     │
│  │  └─────────────────┴──────────┴─────────────────┘               │     │
│  │                                                                    │     │
│  │  Validation Results: ✓ All checks passed (5/5)                   │     │
│  │  • Graph structure integrity: ✓ Passed                           │     │
│  │  • Relationship consistency: ✓ Passed                            │     │
│  │  • Synthetic node labeling: ✓ Passed                             │     │
│  │  • No orphaned nodes: ✓ Passed                                   │     │
│  │  • ID uniqueness: ✓ Passed                                       │     │
│  │                                                                    │     │
│  │  [View in Graph Visualizer]  [Run Another Operation]            │     │
│  │                                                                    │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
```

## TypeScript Interfaces & Types

```typescript
// src/types/scaleOperations.ts

export type ScaleOperationType = 'scale-up' | 'scale-down';

export type ScaleUpStrategy = 'template' | 'scenario' | 'random';
export type ScaleDownAlgorithm = 'forest-fire' | 'mhrw' | 'pattern';
export type OutputMode = 'file' | 'new-tenant' | 'iac';

export type OperationStatus =
  | 'idle'
  | 'validating'
  | 'previewing'
  | 'running'
  | 'success'
  | 'error'
  | 'stopped';

export interface ScaleUpConfig {
  tenantId: string;
  strategy: ScaleUpStrategy;
  validate: boolean;
  // Template strategy
  templateFile?: string;
  scaleFactor?: number;
  // Scenario strategy
  scenarioType?: string;
  scenarioParams?: Record<string, any>;
  // Random strategy
  nodeCount?: number;
  pattern?: string;
}

export interface ScaleDownConfig {
  tenantId: string;
  algorithm: ScaleDownAlgorithm;
  sampleSize: number;
  validate: boolean;
  outputMode: OutputMode;
  // Forest-fire algorithm
  burnInSteps?: number;
  // MHRW algorithm
  walkLength?: number;
  // Pattern-based
  pattern?: string;
  // Output settings
  outputPath?: string;
  iacFormat?: 'terraform' | 'arm' | 'bicep';
  newTenantId?: string;
}

export interface OperationProgress {
  processId: string;
  status: OperationStatus;
  phase: string;
  progress: number; // 0-100
  startTime: string;
  elapsedSeconds: number;
}

export interface ScaleUpStats {
  nodesCreated: number;
  relationshipsCreated: number;
  nodeTypeBreakdown: Record<string, number>;
  syntheticNodesCreated: number;
  validationPassed: boolean;
}

export interface ScaleDownStats {
  nodesRetained: number;
  nodesDeleted: number;
  relationshipsRetained: number;
  relationshipsDeleted: number;
  validationPassed: boolean;
  outputPath?: string;
}

export interface GraphStats {
  totalNodes: number;
  totalRelationships: number;
  syntheticNodes: number;
  nodeTypes: Record<string, number>;
  relationshipTypes: Record<string, number>;
}

export interface OperationResult {
  success: boolean;
  operationType: ScaleOperationType;
  beforeStats: GraphStats;
  afterStats: GraphStats;
  scaleUpStats?: ScaleUpStats;
  scaleDownStats?: ScaleDownStats;
  validationResults: ValidationResult[];
  timestamp: string;
  duration: number; // seconds
  error?: string;
}

export interface ValidationResult {
  checkName: string;
  passed: boolean;
  message: string;
  details?: any;
}

export interface PreviewResult {
  estimatedNodes: number;
  estimatedRelationships: number;
  estimatedDuration: number; // seconds
  warnings: string[];
  canProceed: boolean;
}
```

## IPC Channel Definitions

```typescript
// IPC channels for backend communication via Express API

// Scale-Up Operations
POST /api/scale/up/execute
Body: ScaleUpConfig
Response: { processId: string, success: boolean }

POST /api/scale/up/preview
Body: ScaleUpConfig
Response: PreviewResult

// Scale-Down Operations
POST /api/scale/down/execute
Body: ScaleDownConfig
Response: { processId: string, success: boolean }

POST /api/scale/down/preview
Body: ScaleDownConfig
Response: PreviewResult

// Common Operations
POST /api/scale/cancel/:processId
Response: { success: boolean }

GET /api/scale/status/:processId
Response: OperationProgress

// Utility Operations
POST /api/scale/clean-synthetic
Body: { tenantId: string }
Response: { nodesDeleted: number, success: boolean }

POST /api/scale/validate
Body: { tenantId: string }
Response: ValidationResult[]

GET /api/scale/stats/:tenantId
Response: GraphStats

// WebSocket Events (via Socket.IO)
Event: 'scale:output'
Data: { processId: string, type: 'stdout' | 'stderr', data: string[], timestamp: string }

Event: 'scale:progress'
Data: { processId: string, progress: number, phase: string, stats: any }

Event: 'scale:complete'
Data: { processId: string, result: OperationResult }

Event: 'scale:error'
Data: { processId: string, error: string, timestamp: string }
```

## State Management

### React Context Structure

```typescript
// src/context/ScaleOperationsContext.tsx

interface ScaleOperationsState {
  // Current operation mode
  operationType: ScaleOperationType;

  // Configuration
  scaleUpConfig: ScaleUpConfig;
  scaleDownConfig: ScaleDownConfig;

  // Operation state
  currentOperation: {
    processId: string | null;
    status: OperationStatus;
    progress: OperationProgress | null;
    logs: string[];
  };

  // Results
  lastResult: OperationResult | null;
  previewResult: PreviewResult | null;

  // Graph stats
  currentGraphStats: GraphStats | null;

  // UI state
  showResults: boolean;
  autoScroll: boolean;

  // Errors
  error: string | null;
}

type ScaleOperationsAction =
  | { type: 'SET_OPERATION_TYPE'; payload: ScaleOperationType }
  | { type: 'UPDATE_SCALE_UP_CONFIG'; payload: Partial<ScaleUpConfig> }
  | { type: 'UPDATE_SCALE_DOWN_CONFIG'; payload: Partial<ScaleDownConfig> }
  | { type: 'START_OPERATION'; payload: { processId: string } }
  | { type: 'UPDATE_PROGRESS'; payload: OperationProgress }
  | { type: 'APPEND_LOGS'; payload: string[] }
  | { type: 'OPERATION_COMPLETE'; payload: OperationResult }
  | { type: 'OPERATION_ERROR'; payload: string }
  | { type: 'SET_PREVIEW_RESULT'; payload: PreviewResult }
  | { type: 'UPDATE_GRAPH_STATS'; payload: GraphStats }
  | { type: 'CLEAR_OPERATION'; }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'TOGGLE_AUTO_SCROLL'; };

// Reducer
function scaleOperationsReducer(
  state: ScaleOperationsState,
  action: ScaleOperationsAction
): ScaleOperationsState {
  // Implementation...
}

// Context Provider
export function ScaleOperationsProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(scaleOperationsReducer, initialState);

  return (
    <ScaleOperationsContext.Provider value={{ state, dispatch }}>
      {children}
    </ScaleOperationsContext.Provider>
  );
}

// Hook
export function useScaleOperations() {
  const context = useContext(ScaleOperationsContext);
  if (!context) {
    throw new Error('useScaleOperations must be used within ScaleOperationsProvider');
  }
  return context;
}
```

### Custom Hooks

```typescript
// src/hooks/useScaleUpOperation.ts
export function useScaleUpOperation() {
  const { state, dispatch } = useScaleOperations();
  const { subscribeToProcess, unsubscribeFromProcess } = useWebSocket();

  const executeScaleUp = useCallback(async (config: ScaleUpConfig) => {
    try {
      dispatch({ type: 'SET_ERROR', payload: null });

      const response = await axios.post(`${API_BASE_URL}/api/scale/up/execute`, config);
      const { processId } = response.data;

      dispatch({ type: 'START_OPERATION', payload: { processId } });
      subscribeToProcess(processId);

      return { success: true, processId };
    } catch (error) {
      const message = error.response?.data?.error || error.message;
      dispatch({ type: 'OPERATION_ERROR', payload: message });
      return { success: false, error: message };
    }
  }, [dispatch, subscribeToProcess]);

  const previewScaleUp = useCallback(async (config: ScaleUpConfig) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/scale/up/preview`, config);
      dispatch({ type: 'SET_PREVIEW_RESULT', payload: response.data });
      return response.data;
    } catch (error) {
      const message = error.response?.data?.error || error.message;
      dispatch({ type: 'SET_ERROR', payload: message });
      return null;
    }
  }, [dispatch]);

  const cancelOperation = useCallback(async () => {
    if (!state.currentOperation.processId) return;

    try {
      await axios.post(`${API_BASE_URL}/api/scale/cancel/${state.currentOperation.processId}`);
      unsubscribeFromProcess(state.currentOperation.processId);
      dispatch({ type: 'CLEAR_OPERATION' });
    } catch (error) {
      console.error('Failed to cancel operation:', error);
    }
  }, [state.currentOperation.processId, dispatch, unsubscribeFromProcess]);

  return {
    executeScaleUp,
    previewScaleUp,
    cancelOperation,
    isRunning: state.currentOperation.status === 'running',
    progress: state.currentOperation.progress,
    logs: state.currentOperation.logs,
  };
}

// Similar hook for scale-down: useScaleDownOperation.ts

// src/hooks/useGraphStats.ts
export function useGraphStats(tenantId: string | null) {
  const { dispatch } = useScaleOperations();
  const [loading, setLoading] = useState(false);

  const refreshStats = useCallback(async () => {
    if (!tenantId) return;

    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/scale/stats/${tenantId}`);
      dispatch({ type: 'UPDATE_GRAPH_STATS', payload: response.data });
    } catch (error) {
      console.error('Failed to fetch graph stats:', error);
    } finally {
      setLoading(false);
    }
  }, [tenantId, dispatch]);

  useEffect(() => {
    refreshStats();
  }, [refreshStats]);

  return { refreshStats, loading };
}
```

## Component Implementation Patterns

### ScaleOperationsTab Component

```typescript
// spa/renderer/src/components/tabs/ScaleOperationsTab.tsx

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Alert,
} from '@mui/material';
import { TrendingUp as ScaleUpIcon, TrendingDown as ScaleDownIcon } from '@mui/icons-material';
import { useScaleOperations } from '../../context/ScaleOperationsContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import ScaleUpPanel from '../scale/ScaleUpPanel';
import ScaleDownPanel from '../scale/ScaleDownPanel';
import ProgressMonitor from '../scale/ProgressMonitor';
import ResultsPanel from '../scale/ResultsPanel';
import QuickActionsBar from '../scale/QuickActionsBar';

const ScaleOperationsTab: React.FC = () => {
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
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2, p: 2 }}>
      {/* Connection Status */}
      {!isConnected && (
        <Alert severity="warning">
          Not connected to backend server. Real-time updates may not work properly.
        </Alert>
      )}

      {/* Operation Mode Selector */}
      {!isOperationRunning && !showResults && (
        <Paper sx={{ p: 2 }}>
          <ToggleButtonGroup
            value={operationType}
            exclusive
            onChange={handleOperationTypeChange}
            fullWidth
            sx={{ mb: 2 }}
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
      <QuickActionsBar />
    </Box>
  );
};

export default ScaleOperationsTab;
```

### ScaleUpPanel Component

```typescript
// spa/renderer/src/components/scale/ScaleUpPanel.tsx

import React, { useState, useCallback } from 'react';
import {
  Box,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  Typography,
  Alert,
  Checkbox,
  FormControlLabel,
  Grid,
  Divider,
} from '@mui/material';
import {
  PlayArrow as ExecuteIcon,
  Visibility as PreviewIcon,
  Clear as ClearIcon,
  FolderOpen as BrowseIcon,
} from '@mui/icons-material';
import { useScaleOperations } from '../../context/ScaleOperationsContext';
import { useScaleUpOperation } from '../../hooks/useScaleUpOperation';
import { useApp } from '../../context/AppContext';

const ScaleUpPanel: React.FC = () => {
  const { state: appState } = useApp();
  const { state, dispatch } = useScaleOperations();
  const { executeScaleUp, previewScaleUp, isRunning } = useScaleUpOperation();

  const config = state.scaleUpConfig;

  const [tenantId, setTenantId] = useState(appState.config.tenantId || '');
  const [strategy, setStrategy] = useState<ScaleUpStrategy>('template');
  const [templateFile, setTemplateFile] = useState('');
  const [scaleFactor, setScaleFactor] = useState(2);
  const [validate, setValidate] = useState(true);

  // Update context when fields change
  const updateConfig = useCallback((updates: Partial<ScaleUpConfig>) => {
    dispatch({ type: 'UPDATE_SCALE_UP_CONFIG', payload: updates });
  }, [dispatch]);

  const handleExecute = async () => {
    const config: ScaleUpConfig = {
      tenantId,
      strategy,
      validate,
      templateFile: strategy === 'template' ? templateFile : undefined,
      scaleFactor: strategy === 'template' ? scaleFactor : undefined,
    };

    await executeScaleUp(config);
  };

  const handlePreview = async () => {
    const config: ScaleUpConfig = {
      tenantId,
      strategy,
      validate,
      templateFile: strategy === 'template' ? templateFile : undefined,
      scaleFactor: strategy === 'template' ? scaleFactor : undefined,
    };

    await previewScaleUp(config);
  };

  const handleBrowse = async () => {
    const result = await window.electronAPI.dialog?.openFile({
      filters: [
        { name: 'YAML Templates', extensions: ['yaml', 'yml'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });

    if (result) {
      setTemplateFile(result);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Scale-Up Configuration
      </Typography>

      {state.error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => dispatch({ type: 'SET_ERROR', payload: null })}>
          {state.error}
        </Alert>
      )}

      {state.previewResult && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Preview: Will create approximately {state.previewResult.estimatedNodes} nodes
          and {state.previewResult.estimatedRelationships} relationships
          (estimated duration: {state.previewResult.estimatedDuration}s)
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
            required
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>Strategy</InputLabel>
            <Select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as ScaleUpStrategy)}
              disabled={isRunning}
              label="Strategy"
            >
              <MenuItem value="template">Template-Based</MenuItem>
              <MenuItem value="scenario">Scenario-Based</MenuItem>
              <MenuItem value="random">Random Generation</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        {strategy === 'template' && (
          <>
            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <TextField
                  fullWidth
                  label="Template File"
                  value={templateFile}
                  onChange={(e) => setTemplateFile(e.target.value)}
                  disabled={isRunning}
                  placeholder="templates/scale_template.yaml"
                />
                <Button
                  variant="outlined"
                  startIcon={<BrowseIcon />}
                  onClick={handleBrowse}
                  disabled={isRunning}
                >
                  Browse
                </Button>
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Scale Factor"
                value={scaleFactor}
                onChange={(e) => setScaleFactor(Number(e.target.value))}
                disabled={isRunning}
                inputProps={{ min: 1, max: 10, step: 1 }}
                helperText="Multiplier for template resources"
              />
            </Grid>
          </>
        )}

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                checked={validate}
                onChange={(e) => setValidate(e.target.checked)}
                disabled={isRunning}
              />
            }
            label="Run validation before and after operation"
          />
        </Grid>

        <Grid item xs={12}>
          <Divider sx={{ my: 2 }} />
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={<PreviewIcon />}
              onClick={handlePreview}
              disabled={isRunning || !tenantId}
            >
              Preview Changes
            </Button>

            <Button
              variant="contained"
              color="primary"
              startIcon={<ExecuteIcon />}
              onClick={handleExecute}
              disabled={isRunning || !tenantId || (strategy === 'template' && !templateFile)}
              size="large"
            >
              Execute Scale-Up
            </Button>

            <Button
              variant="outlined"
              startIcon={<ClearIcon />}
              onClick={() => {
                setTenantId('');
                setTemplateFile('');
                setScaleFactor(2);
                dispatch({ type: 'CLEAR_OPERATION' });
              }}
              disabled={isRunning}
            >
              Clear
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default ScaleUpPanel;
```

### ProgressMonitor Component

```typescript
// spa/renderer/src/components/scale/ProgressMonitor.tsx

import React, { useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  LinearProgress,
  Button,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import { Stop as StopIcon } from '@mui/icons-material';
import { useScaleOperations } from '../../context/ScaleOperationsContext';
import { useScaleUpOperation } from '../../hooks/useScaleUpOperation';
import { useWebSocket } from '../../hooks/useWebSocket';
import LogViewer from '../common/LogViewer';

const ProgressMonitor: React.FC = () => {
  const { state } = useScaleOperations();
  const { cancelOperation } = useScaleUpOperation();
  const { getProcessOutput } = useWebSocket();

  const progress = state.currentOperation.progress;
  const logs = state.currentOperation.logs;

  // Format elapsed time
  const formatElapsedTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          {state.operationType === 'scale-up' ? 'Scale-Up' : 'Scale-Down'} in Progress
        </Typography>
        <Button
          variant="contained"
          color="error"
          startIcon={<StopIcon />}
          onClick={cancelOperation}
          size="small"
        >
          Stop Operation
        </Button>
      </Box>

      {/* Progress Bar */}
      <Box sx={{ mb: 3 }}>
        <LinearProgress
          variant="determinate"
          value={progress?.progress || 0}
          sx={{ height: 8, borderRadius: 1 }}
        />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
          <Typography variant="body2" color="textSecondary">
            {progress?.progress || 0}% Complete
          </Typography>
          <Typography variant="body2" color="primary" fontWeight="bold">
            Phase: {progress?.phase || 'Initializing...'}
          </Typography>
        </Box>
      </Box>

      {/* Statistics Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="textSecondary">
                Nodes Affected
              </Typography>
              <Typography variant="h6">
                {state.operationType === 'scale-up'
                  ? state.currentOperation.progress?.stats?.nodesCreated || 0
                  : state.currentOperation.progress?.stats?.nodesDeleted || 0
                }
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="textSecondary">
                Relationships
              </Typography>
              <Typography variant="h6">
                {state.currentOperation.progress?.stats?.relationshipsAffected || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="textSecondary">
                Validation
              </Typography>
              <Typography variant="h6">
                {state.currentOperation.progress?.stats?.validationPassed ? '✓ Passed' : '⏳ Pending'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption" color="textSecondary">
                Elapsed Time
              </Typography>
              <Typography variant="h6">
                {formatElapsedTime(progress?.elapsedSeconds || 0)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Live Log Viewer */}
      <Paper variant="outlined" sx={{ height: 400 }}>
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2">Live Output</Typography>
        </Box>
        <LogViewer logs={logs} />
      </Paper>
    </Paper>
  );
};

export default ProgressMonitor;
```

## Visualization Integration

### Synthetic Node Styling

```typescript
// Add to visualization service or component

// Synthetic nodes should have visual distinction
const getSyntheticNodeStyle = (node: any) => {
  if (node.properties?.synthetic === true || node.labels?.includes('Synthetic')) {
    return {
      color: '#FF9800', // Orange color
      borderStyle: 'dashed',
      borderWidth: 2,
      borderColor: '#F57C00',
      font: {
        color: '#E65100',
        bold: true,
      },
      // Add icon or label indicator
      label: `🔧 ${node.properties?.name || node.id}`,
    };
  }
  return null; // Use default styling
};

// Apply in vis.js network configuration
const networkOptions = {
  nodes: {
    // ... other options
    chosen: {
      node: (values: any, id: string, selected: boolean, hovering: boolean) => {
        const node = nodes.get(id);
        const syntheticStyle = getSyntheticNodeStyle(node);
        if (syntheticStyle) {
          Object.assign(values, syntheticStyle);
        }
      },
    },
  },
};
```

## Testing Strategy

### Unit Tests

```typescript
// spa/tests/unit/scaleOperations.test.ts

describe('ScaleOperations Context', () => {
  it('should initialize with default state', () => {
    const { result } = renderHook(() => useScaleOperations(), {
      wrapper: ScaleOperationsProvider,
    });

    expect(result.current.state.operationType).toBe('scale-up');
    expect(result.current.state.currentOperation.status).toBe('idle');
  });

  it('should update scale-up config', () => {
    const { result } = renderHook(() => useScaleOperations(), {
      wrapper: ScaleOperationsProvider,
    });

    act(() => {
      result.current.dispatch({
        type: 'UPDATE_SCALE_UP_CONFIG',
        payload: { tenantId: 'test-tenant', strategy: 'template' },
      });
    });

    expect(result.current.state.scaleUpConfig.tenantId).toBe('test-tenant');
    expect(result.current.state.scaleUpConfig.strategy).toBe('template');
  });

  it('should handle operation progress updates', () => {
    const { result } = renderHook(() => useScaleOperations(), {
      wrapper: ScaleOperationsProvider,
    });

    act(() => {
      result.current.dispatch({
        type: 'UPDATE_PROGRESS',
        payload: {
          processId: 'test-process',
          status: 'running',
          phase: 'Creating nodes',
          progress: 50,
          startTime: new Date().toISOString(),
          elapsedSeconds: 30,
        },
      });
    });

    expect(result.current.state.currentOperation.progress?.progress).toBe(50);
    expect(result.current.state.currentOperation.progress?.phase).toBe('Creating nodes');
  });
});

describe('useScaleUpOperation Hook', () => {
  it('should execute scale-up operation', async () => {
    const mockAxios = jest.spyOn(axios, 'post');
    mockAxios.mockResolvedValue({ data: { processId: 'test-123', success: true } });

    const { result } = renderHook(() => useScaleUpOperation());

    const config: ScaleUpConfig = {
      tenantId: 'tenant-1',
      strategy: 'template',
      validate: true,
      templateFile: 'test.yaml',
    };

    await act(async () => {
      const response = await result.current.executeScaleUp(config);
      expect(response.success).toBe(true);
      expect(response.processId).toBe('test-123');
    });

    expect(mockAxios).toHaveBeenCalledWith(
      expect.stringContaining('/api/scale/up/execute'),
      config
    );
  });

  it('should handle errors gracefully', async () => {
    const mockAxios = jest.spyOn(axios, 'post');
    mockAxios.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useScaleUpOperation());

    const config: ScaleUpConfig = {
      tenantId: 'tenant-1',
      strategy: 'template',
      validate: true,
    };

    await act(async () => {
      const response = await result.current.executeScaleUp(config);
      expect(response.success).toBe(false);
      expect(response.error).toBeTruthy();
    });
  });
});
```

### Integration Tests

```typescript
// spa/tests/integration/scaleOperations.test.tsx

describe('ScaleOperationsTab Integration', () => {
  it('should render scale-up form correctly', () => {
    render(
      <ScaleOperationsProvider>
        <ScaleOperationsTab />
      </ScaleOperationsProvider>
    );

    expect(screen.getByText('Scale Up (Add Nodes)')).toBeInTheDocument();
    expect(screen.getByLabelText('Tenant ID')).toBeInTheDocument();
    expect(screen.getByLabelText('Strategy')).toBeInTheDocument();
  });

  it('should switch between scale-up and scale-down modes', () => {
    render(
      <ScaleOperationsProvider>
        <ScaleOperationsTab />
      </ScaleOperationsProvider>
    );

    const scaleDownButton = screen.getByText('Scale Down (Sample)');
    fireEvent.click(scaleDownButton);

    expect(screen.getByLabelText('Algorithm')).toBeInTheDocument();
    expect(screen.getByLabelText('Sample Size')).toBeInTheDocument();
  });

  it('should validate required fields before execution', async () => {
    render(
      <ScaleOperationsProvider>
        <ScaleOperationsTab />
      </ScaleOperationsProvider>
    );

    const executeButton = screen.getByText('Execute Scale-Up');
    expect(executeButton).toBeDisabled(); // Disabled when tenant ID is empty

    const tenantIdInput = screen.getByLabelText('Tenant ID');
    fireEvent.change(tenantIdInput, { target: { value: 'test-tenant-123' } });

    await waitFor(() => {
      expect(executeButton).not.toBeDisabled();
    });
  });
});
```

### E2E Tests (Playwright)

```typescript
// spa/tests/e2e/scale-operations.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Scale Operations Tab', () => {
  test('should complete scale-up operation successfully', async ({ page }) => {
    await page.goto('/');

    // Navigate to Scale Operations tab
    await page.getByRole('tab', { name: /Scale Operations/i }).click();

    // Select scale-up mode
    await page.getByText('Scale Up (Add Nodes)').click();

    // Fill in configuration
    await page.getByLabel('Tenant ID').fill('test-tenant-123');
    await page.getByLabel('Strategy').click();
    await page.getByText('Template-Based').click();
    await page.getByLabel('Template File').fill('templates/test_template.yaml');

    // Preview operation
    await page.getByRole('button', { name: /Preview Changes/i }).click();
    await expect(page.getByText(/Will create approximately/i)).toBeVisible({ timeout: 5000 });

    // Execute operation
    await page.getByRole('button', { name: /Execute Scale-Up/i }).click();

    // Wait for operation to start
    await expect(page.getByText(/in Progress/i)).toBeVisible({ timeout: 5000 });

    // Monitor progress
    await expect(page.getByRole('progressbar')).toBeVisible();

    // Wait for completion (with timeout for CI)
    await expect(page.getByText(/Completed Successfully/i)).toBeVisible({ timeout: 60000 });

    // Verify results are displayed
    await expect(page.getByText(/Operation Summary/i)).toBeVisible();
    await expect(page.getByText(/Before & After Comparison/i)).toBeVisible();
  });

  test('should display validation errors', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Scale Operations/i }).click();

    // Try to execute without required fields
    await page.getByRole('button', { name: /Execute Scale-Up/i }).click();

    // Should show error
    await expect(page.getByText(/Tenant ID is required/i)).toBeVisible();
  });

  test('should cancel running operation', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Scale Operations/i }).click();

    // Start operation
    await page.getByLabel('Tenant ID').fill('test-tenant-123');
    await page.getByRole('button', { name: /Execute Scale-Up/i }).click();

    // Wait for operation to start
    await expect(page.getByText(/in Progress/i)).toBeVisible({ timeout: 5000 });

    // Cancel operation
    await page.getByRole('button', { name: /Stop Operation/i }).click();

    // Verify operation was cancelled
    await expect(page.getByText(/Stopped/i)).toBeVisible({ timeout: 5000 });
  });

  test('should clean synthetic data', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: /Scale Operations/i }).click();

    // Click clean synthetic button
    await page.getByRole('button', { name: /Clean Synthetic/i }).click();

    // Confirm dialog
    await page.getByRole('button', { name: /Confirm/i }).click();

    // Wait for success message
    await expect(page.getByText(/Successfully cleaned/i)).toBeVisible({ timeout: 10000 });
  });

  test('should work in headless CI environment', async ({ page }) => {
    // This test specifically validates headless operation
    await page.goto('/');

    // Check that page loads without rendering issues
    await expect(page.getByRole('tab', { name: /Scale Operations/i })).toBeVisible();

    // Verify all key components are accessible
    await page.getByRole('tab', { name: /Scale Operations/i }).click();
    await expect(page.getByText('Scale Up (Add Nodes)')).toBeVisible();
    await expect(page.getByText('Scale Down (Sample)')).toBeVisible();

    // Verify form interactions work
    await page.getByLabel('Tenant ID').fill('test-tenant');
    await expect(page.getByLabel('Tenant ID')).toHaveValue('test-tenant');
  });
});
```

## Error Handling

### Error States

```typescript
// Common error scenarios and UI handling

// 1. Backend not available
if (!isConnected) {
  return (
    <Alert severity="error">
      Backend server is not available. Please ensure the backend is running.
    </Alert>
  );
}

// 2. Validation failures
if (validationErrors.length > 0) {
  return (
    <Alert severity="warning">
      <AlertTitle>Validation Issues Found</AlertTitle>
      <ul>
        {validationErrors.map((error, idx) => (
          <li key={idx}>{error.message}</li>
        ))}
      </ul>
    </Alert>
  );
}

// 3. Operation failures
if (operationError) {
  return (
    <Alert severity="error" onClose={() => setError(null)}>
      <AlertTitle>Operation Failed</AlertTitle>
      {operationError}
      <Button size="small" onClick={handleRetry}>
        Retry
      </Button>
    </Alert>
  );
}

// 4. Timeout handling
const OPERATION_TIMEOUT = 300000; // 5 minutes

useEffect(() => {
  if (isRunning) {
    const timeout = setTimeout(() => {
      setError('Operation timed out. Please check logs and try again.');
      cancelOperation();
    }, OPERATION_TIMEOUT);

    return () => clearTimeout(timeout);
  }
}, [isRunning]);
```

## Accessibility Considerations

```typescript
// ARIA labels and roles

<Button
  aria-label="Execute scale-up operation"
  aria-describedby="scale-up-help-text"
  onClick={handleExecute}
>
  Execute Scale-Up
</Button>

<Typography id="scale-up-help-text" variant="caption">
  This will add synthetic nodes to your graph based on the selected strategy
</Typography>

// Progress announcements for screen readers
<div role="status" aria-live="polite" aria-atomic="true">
  {progress > 0 && `Operation is ${progress}% complete. Current phase: ${phase}`}
</div>

// Keyboard navigation
const handleKeyPress = (event: React.KeyboardEvent) => {
  if (event.key === 'Enter' && !isRunning) {
    handleExecute();
  } else if (event.key === 'Escape' && isRunning) {
    cancelOperation();
  }
};

// Focus management
useEffect(() => {
  if (showResults) {
    // Move focus to results when operation completes
    resultsRef.current?.focus();
  }
}, [showResults]);
```

## Performance Considerations

```typescript
// Optimize log rendering with virtualization
import { FixedSizeList } from 'react-window';

const VirtualizedLogViewer: React.FC<{ logs: string[] }> = ({ logs }) => {
  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => (
    <div style={style}>
      <Typography variant="caption" component="pre">
        {logs[index]}
      </Typography>
    </div>
  );

  return (
    <FixedSizeList
      height={400}
      itemCount={logs.length}
      itemSize={20}
      width="100%"
    >
      {Row}
    </FixedSizeList>
  );
};

// Debounce config updates
import { debounce } from 'lodash';

const debouncedUpdateConfig = useCallback(
  debounce((updates: Partial<ScaleUpConfig>) => {
    dispatch({ type: 'UPDATE_SCALE_UP_CONFIG', payload: updates });
  }, 300),
  [dispatch]
);

// Memoize expensive computations
const computedStats = useMemo(() => {
  if (!result) return null;

  return {
    nodesDelta: result.afterStats.totalNodes - result.beforeStats.totalNodes,
    relationshipsDelta: result.afterStats.totalRelationships - result.beforeStats.totalRelationships,
    syntheticPercentage: (result.afterStats.syntheticNodes / result.afterStats.totalNodes) * 100,
  };
}, [result]);
```

## Summary

This design provides:

1. **Complete component hierarchy** with clear separation of concerns
2. **Type-safe interfaces** for all data structures
3. **IPC channels** for backend communication via REST API and WebSocket
4. **Context-based state management** with reducer pattern
5. **Custom hooks** for operation execution and state management
6. **Real-time progress monitoring** via WebSocket
7. **Visual mockups** showing different operation states
8. **Comprehensive testing strategy** (unit, integration, e2e)
9. **Error handling** patterns for common scenarios
10. **Accessibility** support for screen readers and keyboard navigation
11. **Performance optimizations** for large log outputs
12. **Synthetic node visualization** with distinct styling

The design follows existing SPA patterns from `ScanTab` and `GenerateIaCTab`, ensuring consistency across the application. It's production-ready, CI-friendly, and includes headless environment support for automated testing.
