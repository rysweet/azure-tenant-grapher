import { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import { useScaleOperations } from '../context/ScaleOperationsContext';
import { GraphStats } from '../types/scaleOperations';

const API_BASE_URL = 'http://localhost:3001';

export function useGraphStats(tenantId: string | null, autoLoad: boolean = false) {
  const { dispatch } = useScaleOperations();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshStats = useCallback(async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return null;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.get<GraphStats>(`${API_BASE_URL}/api/scale/stats/${tenantId}`);
      dispatch({ type: 'UPDATE_GRAPH_STATS', payload: response.data });
      return response.data;
    } catch (err: any) {
      const message = err.response?.data?.error || err.message || 'Failed to fetch graph statistics';
      setError(message);
      console.error('Failed to fetch graph stats:', err);
      return null;
    } finally {
      setLoading(false);
    }
  }, [tenantId, dispatch]);

  // Auto-load stats when tenantId changes if autoLoad is true
  useEffect(() => {
    if (autoLoad && tenantId) {
      refreshStats();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoLoad, tenantId]);

  return { refreshStats, loading, error };
}
