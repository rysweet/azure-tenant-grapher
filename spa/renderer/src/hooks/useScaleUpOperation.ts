import { useCallback, useEffect, useRef } from 'react';
import axios from 'axios';
import { useScaleOperations } from '../context/ScaleOperationsContext';
import { useWebSocket } from './useWebSocket';
import { ScaleUpConfig, PreviewResult, ExecuteResponse } from '../types/scaleOperations';

const API_BASE_URL = 'http://localhost:3001';

export function useScaleUpOperation() {
  const { state, dispatch } = useScaleOperations();
  const { isConnected, subscribeToProcess, unsubscribeFromProcess, getProcessOutput } = useWebSocket();
  const lastLogCountRef = useRef(0);

  // Listen for WebSocket events - only depend on processId, not log length
  useEffect(() => {
    if (!state.currentOperation.processId) return;

    const processId = state.currentOperation.processId;

    // Use interval to check for new logs instead of effect dependency
    const intervalId = setInterval(() => {
      const output = getProcessOutput(processId);

      if (output.length > lastLogCountRef.current) {
        const newLogs = output.slice(lastLogCountRef.current);
        lastLogCountRef.current = output.length;
        dispatch({ type: 'APPEND_LOGS', payload: newLogs });
      }
    }, 500); // Check every 500ms

    // Cleanup function to unsubscribe from WebSocket when component unmounts
    return () => {
      clearInterval(intervalId);
      if (processId) {
        unsubscribeFromProcess(processId);
      }
      lastLogCountRef.current = 0;
    };
  }, [state.currentOperation.processId, getProcessOutput, dispatch, unsubscribeFromProcess]);

  const executeScaleUp = useCallback(async (config: ScaleUpConfig): Promise<ExecuteResponse> => {
    try {
      dispatch({ type: 'SET_ERROR', payload: null });

      const response = await axios.post<ExecuteResponse>(`${API_BASE_URL}/api/scale/up/execute`, config);
      const { processId, success, error } = response.data;

      if (!success) {
        throw new Error(error || 'Failed to start scale-up operation');
      }

      dispatch({ type: 'START_OPERATION', payload: { processId } });
      subscribeToProcess(processId);

      return { success: true, processId };
    } catch (error: any) {
      const message = error.response?.data?.error || error.message || 'Unknown error occurred';
      dispatch({ type: 'OPERATION_ERROR', payload: message });
      return { success: false, processId: '', error: message };
    }
  }, [dispatch, subscribeToProcess]);

  const previewScaleUp = useCallback(async (config: ScaleUpConfig): Promise<PreviewResult | null> => {
    try {
      dispatch({ type: 'SET_ERROR', payload: null });

      const response = await axios.post<PreviewResult>(`${API_BASE_URL}/api/scale/up/preview`, config);
      dispatch({ type: 'SET_PREVIEW_RESULT', payload: response.data });
      return response.data;
    } catch (error: any) {
      const message = error.response?.data?.error || error.message || 'Failed to preview operation';
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
    } catch (error: any) {
      console.error('Failed to cancel operation:', error);
      dispatch({ type: 'SET_ERROR', payload: 'Failed to cancel operation' });
    }
  }, [state.currentOperation.processId, dispatch, unsubscribeFromProcess]);

  return {
    executeScaleUp,
    previewScaleUp,
    cancelOperation,
    isRunning: state.currentOperation.status === 'running' || state.currentOperation.status === 'validating',
    isConnected,
    progress: state.currentOperation.progress,
    logs: state.currentOperation.logs,
  };
}
