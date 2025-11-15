import { useCallback, useEffect } from 'react';
import axios from 'axios';
import { useScaleOperations } from '../context/ScaleOperationsContext';
import { useWebSocket } from './useWebSocket';
import { ScaleDownConfig, PreviewResult, ExecuteResponse } from '../types/scaleOperations';

const API_BASE_URL = 'http://localhost:3001';

export function useScaleDownOperation() {
  const { state, dispatch } = useScaleOperations();
  const { isConnected, subscribeToProcess, unsubscribeFromProcess, getProcessOutput } = useWebSocket();

  // Listen for WebSocket events
  useEffect(() => {
    if (!state.currentOperation.processId) return;

    const processId = state.currentOperation.processId;
    const output = getProcessOutput(processId);

    if (output.length > state.currentOperation.logs.length) {
      const newLogs = output.slice(state.currentOperation.logs.length);
      dispatch({ type: 'APPEND_LOGS', payload: newLogs });
    }
  }, [state.currentOperation.processId, getProcessOutput, state.currentOperation.logs.length, dispatch]);

  const executeScaleDown = useCallback(async (config: ScaleDownConfig): Promise<ExecuteResponse> => {
    try {
      dispatch({ type: 'SET_ERROR', payload: null });

      const response = await axios.post<ExecuteResponse>(`${API_BASE_URL}/api/scale/down/execute`, config);
      const { processId, success, error } = response.data;

      if (!success) {
        throw new Error(error || 'Failed to start scale-down operation');
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

  const previewScaleDown = useCallback(async (config: ScaleDownConfig): Promise<PreviewResult | null> => {
    try {
      dispatch({ type: 'SET_ERROR', payload: null });

      const response = await axios.post<PreviewResult>(`${API_BASE_URL}/api/scale/down/preview`, config);
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
    executeScaleDown,
    previewScaleDown,
    cancelOperation,
    isRunning: state.currentOperation.status === 'running' || state.currentOperation.status === 'validating',
    isConnected,
    progress: state.currentOperation.progress,
    logs: state.currentOperation.logs,
  };
}
