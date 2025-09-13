import { useState, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    nodeCount: number;
    edgeCount: number;
    nodeTypes: Record<string, number>;
    edgeTypes: Record<string, number>;
  };
}

export const useGraphAPI = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async (): Promise<GraphData | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE_URL}/api/graph`);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch graph data';
      setError(message);
      // Console error removed
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const searchNodes = useCallback(async (query: string): Promise<GraphNode[]> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE_URL}/api/graph/search`, {
        params: { query }
      });
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to search nodes';
      setError(message);
      // Console error removed
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const getNodeDetails = useCallback(async (nodeId: string): Promise<any> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE_URL}/api/graph/node/${nodeId}`);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch node details';
      setError(message);
      // Console error removed
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    fetchGraph,
    searchNodes,
    getNodeDetails
  };
};
