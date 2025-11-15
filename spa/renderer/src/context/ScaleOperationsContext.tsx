import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import {
  ScaleOperationType,
  ScaleUpConfig,
  ScaleDownConfig,
  OperationProgress,
  OperationResult,
  PreviewResult,
  GraphStats,
  OperationStatus,
} from '../types/scaleOperations';

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
  | { type: 'SET_PREVIEW_RESULT'; payload: PreviewResult | null }
  | { type: 'UPDATE_GRAPH_STATS'; payload: GraphStats }
  | { type: 'CLEAR_OPERATION' }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'TOGGLE_AUTO_SCROLL' }
  | { type: 'SET_SHOW_RESULTS'; payload: boolean };

const initialState: ScaleOperationsState = {
  operationType: 'scale-up',
  scaleUpConfig: {
    tenantId: '',
    strategy: 'template',
    validate: true,
    scaleFactor: 2,
  },
  scaleDownConfig: {
    tenantId: '',
    algorithm: 'forest-fire',
    sampleSize: 500,
    validate: true,
    outputMode: 'file',
    burnInSteps: 5,
    forwardProbability: 0.7,
    preserveRelationships: true,
    includeProperties: false,
  },
  currentOperation: {
    processId: null,
    status: 'idle',
    progress: null,
    logs: [],
  },
  lastResult: null,
  previewResult: null,
  currentGraphStats: null,
  showResults: false,
  autoScroll: true,
  error: null,
};

function scaleOperationsReducer(
  state: ScaleOperationsState,
  action: ScaleOperationsAction
): ScaleOperationsState {
  switch (action.type) {
    case 'SET_OPERATION_TYPE':
      return {
        ...state,
        operationType: action.payload,
        error: null,
        previewResult: null,
      };

    case 'UPDATE_SCALE_UP_CONFIG':
      return {
        ...state,
        scaleUpConfig: { ...state.scaleUpConfig, ...action.payload },
      };

    case 'UPDATE_SCALE_DOWN_CONFIG':
      return {
        ...state,
        scaleDownConfig: { ...state.scaleDownConfig, ...action.payload },
      };

    case 'START_OPERATION':
      return {
        ...state,
        currentOperation: {
          processId: action.payload.processId,
          status: 'running',
          progress: null,
          logs: [],
        },
        showResults: false,
        error: null,
        lastResult: null,
      };

    case 'UPDATE_PROGRESS':
      return {
        ...state,
        currentOperation: {
          ...state.currentOperation,
          progress: action.payload,
          status: action.payload.status,
        },
      };

    case 'APPEND_LOGS':
      return {
        ...state,
        currentOperation: {
          ...state.currentOperation,
          logs: [...state.currentOperation.logs, ...action.payload],
        },
      };

    case 'OPERATION_COMPLETE':
      return {
        ...state,
        currentOperation: {
          ...state.currentOperation,
          status: 'success',
        },
        lastResult: action.payload,
        showResults: true,
        error: null,
      };

    case 'OPERATION_ERROR':
      return {
        ...state,
        currentOperation: {
          ...state.currentOperation,
          status: 'error',
        },
        error: action.payload,
      };

    case 'SET_PREVIEW_RESULT':
      return {
        ...state,
        previewResult: action.payload,
        error: null,
      };

    case 'UPDATE_GRAPH_STATS':
      return {
        ...state,
        currentGraphStats: action.payload,
      };

    case 'CLEAR_OPERATION':
      return {
        ...state,
        currentOperation: {
          processId: null,
          status: 'idle',
          progress: null,
          logs: [],
        },
        showResults: false,
        error: null,
        previewResult: null,
      };

    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
      };

    case 'TOGGLE_AUTO_SCROLL':
      return {
        ...state,
        autoScroll: !state.autoScroll,
      };

    case 'SET_SHOW_RESULTS':
      return {
        ...state,
        showResults: action.payload,
      };

    default:
      return state;
  }
}

interface ScaleOperationsContextValue {
  state: ScaleOperationsState;
  dispatch: React.Dispatch<ScaleOperationsAction>;
}

const ScaleOperationsContext = createContext<ScaleOperationsContextValue | undefined>(undefined);

export function ScaleOperationsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(scaleOperationsReducer, initialState);

  return (
    <ScaleOperationsContext.Provider value={{ state, dispatch }}>
      {children}
    </ScaleOperationsContext.Provider>
  );
}

export function useScaleOperations() {
  const context = useContext(ScaleOperationsContext);
  if (!context) {
    throw new Error('useScaleOperations must be used within ScaleOperationsProvider');
  }
  return context;
}
